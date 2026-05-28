# Track 7: SoftDevice (BLE) Radio Timeslot Interference

**Date:** 2026-05-28
**Investigator:** internal-coder
**Confidence:** HIGH (8/10)

## Executive Summary

**The SoftDevice IS a contributing timing factor, but NOT a root cause.** The S132 SoftDevice runs its RADIO ISR at NVIC priority 0, which blocks GPIOTE ISR (priority 6) and RTC/app_timer IRQ (priority 6) for up to 7.5ms per BLE event. During a radio timeslot, a PIR edge sets the GPIO DETECT latch but the GPIOTE ISR is held pending. If a second PIR edge arrives before the ISR runs, the LATCH register (one-event-per-pin) loses the second edge. However, the ~7.5ms timeslot window out of a 20-800ms connection interval means the probability of two edges landing in one timeslot is low, and the 6-hour recovery timer (Track 6) provides eventual recovery. The SoftDevice timeslot is the **trigger** that converts latent bugs (Track 1 slot exhaustion, Track 5 handler drops, Track 3 ISR blocking) into manifest failures.

**Key findings:**

1. **SoftDevice:** S132 v7.x, dispatch model INTERRUPT (SWI2), external 32kHz crystal assumed
2. **GPIOTE at priority 6 is BLOCKED during RADIO timeslots** (priority 0) — confirmed by NVIC priority hierarchy
3. **RTC/app_timer at priority 6 is also blocked** — but timer callbacks only delayed, not lost (RTC counter continues)
4. **No RTC resource conflict:** SoftDevice uses RTC0 (internal), app_timer uses RTC1 (independent hardware)
5. **BLE event handlers have zero GPIO/GPIOTE interaction** — no reconfiguration during BLE activity
6. **Flash operations use SoftDevice fstorage API** — threadsafe but blocks CPU during erase/write (BUSY-wait loops)
7. **Combined model:** SoftDevice timeslot blocks GPIOTE ISR → LATCH single-event limitation → second edge lost → combined with Track 5 handler drops and Track 1 slot contention → PIR event drought → 6-hour recovery rescues

---

## 1. SoftDevice Configuration

### 1.1 SoftDevice Identity

**S132 SoftDevice** for nRF52832 (Cortex-M4).

Evidence:
- Project path: `application/pca10040/s132/config/sdk_config.h`
- SDK component path: `components/softdevice/s132/headers/`
- `nrf_soc.h:83`: `SD_EVT_IRQn = SWI2_IRQn`, `SD_EVT_IRQHandler = SWI2_IRQHandler`

### 1.2 Enable Sequence

**File:** `main.c:242-266` (`ble_stack_init`)

```c
err_code = nrf_sdh_enable_request();           // → sd_softdevice_enable()
err_code = nrf_sdh_ble_default_cfg_set(...);   // configure BLE stack
err_code = nrf_sdh_ble_enable(&ram_start);     // enable BLE
NRF_SDH_BLE_OBSERVER(m_ble_observer, 3, ble_evt_handler, NULL);
```

**Key:** `sd_softdevice_enable()` sets all SoftDevice internal interrupt priorities before returning. The comment in `nrf_sdh.c:228` confirms: "Interrupt priority has already been set by the stack."

### 1.3 Dispatch Model

| Setting | Value | Meaning |
|---------|-------|---------|
| `NRF_SDH_DISPATCH_MODEL` | **0** (INTERRUPT) | BLE event callbacks run in SWI2 ISR context |
| `NRF_SDH_BLE_ENABLED` | **1** | BLE stack active |
| `NRF_SDH_SOC_ENABLED` | **1** | SoC event handler active |

With the INTERRUPT dispatch model, `ble_evt_handler` runs at the SWI2 IRQ priority (set by SoftDevice, typically same as `APP_IRQ_PRIORITY_LOW` = 6). This means BLE event callback code runs at the SAME priority as GPIOTE ISR and app_timer ISR — they tail-chain rather than nest.

### 1.4 BLE Connection Parameters

**File:** `main.c:129-139`

| Parameter | Advanced Mode | Non-Advanced Mode |
|-----------|---------------|-------------------|
| MIN_CONN_INTERVAL | 20ms (16 × 1.25ms) | 800ms (640 × 1.25ms) |
| MAX_CONN_INTERVAL | 70ms (56 × 1.25ms) | 800ms (640 × 1.25ms) |
| SLAVE_LATENCY | 0 | 0 |
| CONN_SUP_TIMEOUT | 5000ms | 3000ms |
| NRF_SDH_BLE_GAP_EVENT_LENGTH | 6 (7.5ms) | 6 (7.5ms) |

**Critical:** `SLAVE_LATENCY = 0` means the device MUST respond to EVERY connection event. With 20ms interval, this is 50 BLE events per second, each blocking application ISRs for up to 7.5ms.

### 1.5 Clock Configuration

**File:** `sdk_config.h:12119-12129`

```c
NRF_SDH_CLOCK_LF_SRC = 1  // NRF_CLOCK_LF_SRC_XTAL (external 32kHz crystal)
// Falls back to 0 (RC) if NO_EXTERNAL_CLOCK defined
NRF_SDH_CLOCK_LF_ACCURACY = 7  // 20 ppm (XTAL path)
```

---

## 2. NVIC Priority Map

### 2.1 Configured Priorities (from sdk_config.h)

| Interrupt | Priority | Source | File:Line |
|-----------|----------|--------|-----------|
| **RADIO** (SoftDevice) | **0** | Set by SoftDevice | nrf_sdh.c:228 (comment) |
| **RTC0** (SoftDevice) | **1 or 2** | Set by SoftDevice | Internal S132 |
| **TIMER0** (SoftDevice) | **4** | Set by SoftDevice | Internal S132 |
| **SWI2/EGU2** (SD_EVT) | **6** (typical) | Set by SoftDevice | nrf_sdh.c:228 |
| **GPIOTE** | **6** | `GPIOTE_CONFIG_IRQ_PRIORITY` | sdk_config.h:1701 |
| **nrfx GPIOTE** | **6** | `NRFX_GPIOTE_CONFIG_IRQ_PRIORITY` | sdk_config.h:2233 |
| **app_timer (SWI0)** | **6** | `APP_TIMER_CONFIG_IRQ_PRIORITY` | sdk_config.h:6420 |
| **RTC1 (app_timer HW)** | **6** | `NRFX_RTC_DEFAULT_CONFIG_IRQ_PRIORITY` | (default) |
| **WDT** | **6** | `WDT_CONFIG_IRQ_PRIORITY` | sdk_config.h:4844 |
| **Main loop** | Thread mode | No priority (effectively ∞) | — |

### 2.2 S132 SoftDevice NVIC Reservation

The S132 SoftDevice reserves NVIC priority levels **0, 1, 2, and 4** for its internal peripherals:

| Priority | Owner | Purpose |
|----------|-------|---------|
| 0 | RADIO | Radio timeslot ISR — highest priority, preempts everything |
| 1 | RTC0 | SoftDevice timing scheduler |
| 2 | (reserved/optional) | Additional SoftDevice internal |
| 4 | TIMER0 | SoftDevice timer operations |

**Note:** Priority 0 is the absolute highest on Cortex-M4 (3-bit NVIC: 0=highest, 7=lowest). Application can use priorities 3, 5, 6, 7 — but NOT 0, 1, 2, 4.

### 2.3 Preemption Matrix

| Can ↓ preempt → | RADIO (pri 0) | RTC0 (pri 1) | TIMER0 (pri 4) | SWI2/GPIO/RTC1 (pri 6) | Main loop |
|---|---|---|---|---|---|
| **RADIO** (pri 0) | — | YES | YES | YES | YES |
| **RTC0** (pri 1) | NO | — | YES | YES | YES |
| **TIMER0** (pri 4) | NO | NO | — | YES | YES |
| **GPIOTE/RTC1/SWI2** (pri 6) | NO | NO | NO | tail-chain | YES |
| **Main loop** | NO | NO | NO | NO | — |

**Key insight:** RADIO (priority 0) blocks all application ISRs. During a BLE connection event, GPIOTE and RTC1 interrupts are pended by the NVIC but NOT serviced until the RADIO ISR returns.

---

## 3. Timeslot Duration Analysis

### 3.1 Event Length

`NRF_SDH_BLE_GAP_EVENT_LENGTH = 6` units of 1.25ms = **7.5ms** maximum per BLE event.

This is the worst-case CPU time the SoftDevice is allowed to consume within a single connection interval. Actual radio TX/RX time is shorter (~1-2ms for a typical connection event with empty data payload), but the SoftDevice may use the full 7.5ms for event processing, flash operations, and internal housekeeping.

### 3.2 PIR Edge Collision Window

Given:
- BLE connection interval: 20ms (advanced) or 800ms (non-advanced)
- Timeslot window: 7.5ms per event
- PYD1598 minimum output pulse width: ~2ms (from threshold + filter configuration, spec sheet typical minimum)

**Probability of a single PIR edge landing in a timeslot:**

| Connection Interval | Timeslot Duty Cycle | Per-event probability |
|---------------------|---------------------|----------------------|
| 20ms (advanced) | 7.5/20 = **37.5%** | **37.5%** |
| 800ms (non-advanced) | 7.5/800 = **0.94%** | **0.94%** |

### 3.3 Multi-Edge Loss Scenario

**The LATCH register is the bottleneck.** On nRF52832 GPIO peripheral:
- Each pin has a single DETECT latch bit
- When SENSE=TOGGLE, a HIGH→LOW or LOW→HIGH transition sets the DETECT latch
- The latch stays set until the GPIOTE ISR reads the PORT event register
- If a second edge occurs before the latch is cleared, **the second edge is silently lost**

**Sequence for event loss:**

```
Time ─────────────────────────────────────────────────────────►

RADIO ISR (pri 0)    ████████████████████████ (7.5ms)
                     │         │          │
PIR pin:             ──┐       └──┐       └──┐
  Edge #1 (2ms)        │          │          │
  Edge #2 (2ms)                  ┌┘         ┌┘
                                 │          │
DETECT latch:        ░░░░░░░░░░░░░░░░░░░░░░░░
  Set by edge #1      ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
  Edge #2 (LOST!)                         ↑
                                          │
GPIOTE ISR (pri 6)                        ██
  Runs AFTER RADIO returns
  Sees only ONE PORT event
```

**Required conditions for loss:**
1. First PIR edge during radio timeslot → DETECT latch set
2. Second PIR edge during same timeslot → LOST (latch already set)
3. GPIOTE ISR runs after timeslot → only sees first edge's PORT event

**Plausibility:** With a 2ms minimum PIR pulse and 7.5ms timeslot, at most 3-4 edges could fit. Two edges in one timeslot requires a double-motion detection within ~7.5ms, which is plausible for:
- A person walking through the detection zone (multiple body-part crossings)
- A person entering then immediately re-entering the zone
- Sensor noise producing a secondary pulse

**Verdict:** Multi-edge loss within a single timeslot is **PLAUSIBLE but LOW PROBABILITY.** It requires both a specific motion pattern AND timing alignment with a BLE timeslot. The duty cycle (0.94%-37.5%) and pulse width (2ms) make this a contributory rather than dominant failure mode.

---

## 4. RTC Resource Analysis

### 4.1 Hardware Allocation

| RTC Instance | Owner | Purpose | sdk_config Evidence |
|-------------|-------|---------|---------------------|
| **RTC0** | SoftDevice S132 | BLE timeslot scheduler, radio timing | `RTC0_ENABLED 0`, `NRFX_RTC0_ENABLED 0` |
| **RTC1** | app_timer | `count1sec`, `pir_check` timer, all app timers | `RTC1_ENABLED 0`, `NRFX_RTC1_ENABLED 0` |
| **RTC2** | (unused) | — | `RTC2_ENABLED 0`, `NRFX_RTC2_ENABLED 0` |

**RTC0 and RTC1 are physically separate hardware peripherals.** The `RTCn_ENABLED 0` and `NRFX_RTCn_ENABLED 0` settings in sdk_config.h indicate that neither RTC is managed through the nrf_drv_rtc abstraction layer — they are managed directly by the SoftDevice (RTC0) and app_timer library (RTC1).

### 4.2 No RTC Resource Conflict

**CONFIRMED: RTC0 and RTC1 are independent.** The SoftDevice uses RTC0 internally for its timing. The application's app_timer library manages RTC1 independently. There is no shared RTC instance and no timer drift or missed callbacks caused by RTC contention.

### 4.3 Timer callback timing during timeslots

While RTC1 continues counting during BLE timeslots (hardware counter is independent of CPU), the RTC1 IRQ at priority 6 IS blocked during RADIO ISR (priority 0). However:

- **The RTC counter is not affected** — it continues incrementing
- **The app_timer library processes timeouts in the RTC1 ISR** — if blocked during a timeslot, timeout processing is delayed but NOT skipped
- **The `count1sec` variable increments correctly** — the 1-second tick handler runs from `atel_timerTickHandler()` in the main loop, NOT from an ISR, so it simply runs after the timeslot

**No timer callbacks are lost due to timeslot blocking** — they are merely delayed by at most 7.5ms. This is inconsequential for the 6-hour recovery timer and the ~153µs `pir_check` timer.

---

## 5. SoftDevice Event Handler Analysis

### 5.1 BLE Event Handlers — Zero GPIO/GPIOTE Interaction

**All BLE event handlers were searched for GPIO, GPIOTE, PIR, and PYD references:**

| Handler | File:Line | GPIO/GPIOTE Access? |
|---------|-----------|---------------------|
| `ble_evt_handler` | ble_user.c:1030 | **NO** — dispatches to peripheral/central handler only |
| `on_ble_peripheral_evt` | ble_user.c:793 | **NO** — GAP, GATT, PHY events only |
| `on_ble_central_evt` | ble_user.c:464 | **NO** — connection management only |
| `ble_nus_on_ble_evt` | ble_aus.c:218 | **NO** — UART service handling only |
| `ble_nus_c_on_ble_evt` | ble_aus_c.c:168 | **NO** — client UART service |
| `ble_dfu_c_on_ble_evt` | ble_dfu_c.c:235 | **NO** — DFU service |
| `gatt_evt_handler` | main.c:270 | **NO** — MTU and data length updates |
| `pm_evt_handler` | ble_user.c:1069 | **NO** — bonding management |

**Verdict: BLE activity does NOT reconfigure GPIO or GPIOTE.** The SoftDevice radio timeslots never touch PIR-related peripherals.

### 5.2 SoC Event Handlers

`sdk_config.h:12276`: `NRF_SDH_SOC_ENABLED = 1` — SoC events are enabled, but no SoC observer is registered in application code. The `NRF_SDH_SOC_OBSERVER` macro is not used in any application file.

### 5.3 Flash Operations — CPU Blocking During Erase/Write

The application uses `nrf_fstorage_sd` (SoftDevice-aware flash API) in three modules:

| Module | File | Operations |
|--------|------|------------|
| Camera flash | camera_flash.c | `nrf_fstorage_erase`, `nrf_fstorage_write` (NVRAM config) |
| Beacon flash | ble_beacon_sensor.c | `nrf_fstorage_erase` (beacon data) |
| Bond storage | bstorage.c | `nrf_fstorage_write`, `nrf_fstorage_erase` (bond data) |

**Critical:** All three modules use **busy-wait loops** after flash operations:

```c
// camera_flash.c:57-61
void wait_for_flash_ready(nrf_fstorage_t const * p_fstorage) {
    while (nrf_fstorage_is_busy(p_fstorage)) {}  // BLOCKS
}

// bstorage.c:167
while (nrf_fstorage_is_busy(&fs)) {}  // BLOCKS after every write
```

`nrf_fstorage_sd` uses `sd_flash_write()` which executes inside the SoftDevice. During flash erase/write:
- **The CPU is halted** for the duration of the flash operation (nRF52832 flash write: ~40-80µs per word, erase: ~40ms per page)
- **All interrupts are blocked** during the flash operation (hardware limitation)
- **GPIOTE events arriving during flash operations are pended but not lost** (NVIC holds them pending)

This is a separate blocking mechanism from radio timeslots. Flash operations block everything, including the SoftDevice.

### 5.4 Interrupt Disable/Enable During BLE Operations

**No `__disable_irq()`, `NVIC_DisableIRQ`, or `CRITICAL_REGION_ENTER` calls found in any BLE-related code path.** The only place `CRITICAL_REGION_ENTER` is used is in `nrf_sdh.c:259` during SoftDevice disable — a one-time operation at shutdown.

The SoftDevice internally manages interrupt masking via BASEPRI during time-critical operations, but this is transparent to the application.

---

## 6. Root Cause vs Contributing Factor Assessment

### 6.1 Timeslot Alone Cannot Explain Persistent Misses

**Why the SoftDevice is NOT the root cause:**

1. **Timeslots are transient:** The GPIOTE ISR runs as soon as the RADIO ISR completes. A single PIR edge during a timeslot is merely delayed, not lost. The LATCH register captures the event.

2. **Duty cycle is bounded:** Even at the worst-case 20ms connection interval (37.5% timeslot duty), 62.5% of the time the CPU is available for GPIOTE ISR servicing.

3. **The 6-hour recovery works:** Track 6 confirmed the `pyd_restart()` timer fires every 6 hours regardless. If timeslot blocking were the only mechanism, PIR events would resume after every timeslot ends — recovery wouldn't need 6 hours.

### 6.2 The Combined Failure Model

The SoftDevice timeslot is the **timing trigger** that unifies the failure mechanisms:

```
┌─────────────────────────────────────────────────────────┐
│                    COMBINED FAILURE MODEL                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  SoftDevice Radio Timeslot                              │
│  (RADIO ISR @ pri 0, blocks GPIOTE @ pri 6)            │
│                    │                                    │
│                    ▼                                    │
│  PIR edge during timeslot → DETECT latch set            │
│  Second edge during same timeslot → LOST (LATCH limit)  │
│                    │                                    │
│                    ▼                                    │
│  GPIOTE ISR runs, but pin already LOW                   │
│  → Track 5 Layer 2 drop (handler reads pin state)       │
│                    │                                    │
│                    ▼                                    │
│  If ISR survives, timer callback runs                   │
│  → Track 1: slot exhaustion during re-init              │
│  → Track 3: 620µs dead window during pyd_gpio_reconfig  │
│  → Track 3: 23ms dead window during pyd_restart         │
│                    │                                    │
│                    ▼                                    │
│  Eventually: PIR events stop arriving                   │
│  → 6-hour pyd_restart() power-cycles sensor             │
│  → Cycle repeats                                        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 6.3 Quantitative Risk Assessment

| Mechanism | Probability per event | Impact |
|-----------|----------------------|--------|
| Single edge delayed by timeslot | 0.9%-37.5% | None — LATCH captures it |
| Second edge LOST in same timeslot | Low (requires fast double-edge) | One event lost |
| Timeslot + Track 5 handler drop | 0.9%-37.5% × handler drop rate | Event silently discarded |
| Timeslot + Track 1 slot contention | Low (slot count = 6, only 1 PIR pin) | Re-init fails silently |
| Timeslot + Track 3 dead window | Timeslot duty × dead window probability | Event lost in gap |

**Net assessment:** The SoftDevice is a **contributing timing factor** with **MODERATE impact.** It acts as an amplifier for the other failure tracks. Without Track 5's handler drop or Track 3's dead windows, timeslot blocking alone would cause negligible permanent event loss (only the rare double-edge-in-timeslot case). The SoftDevice converts "sometimes" into "often enough to matter in the field."

### 6.4 Interaction with Other Tracks

| Track | Intersection | Severity |
|-------|-------------|----------|
| **Track 1** (slot exhaustion) | Timeslot-delayed GPIOTE re-init could coincide with slot contention from other pins. If the single PORT event slot is taken by another pin during the timeslot, PIR re-registration fails silently. | **LOW** (GA01/GA02: 6 slots, 1 PIR pin) |
| **Track 2** (volatile race) | Timeslot delays ISR → expands the window where main-loop `atel_timer1s()` modification and ISR reads overlap. Race window increases from ~50µs to up to 7.5ms. | **MODERATE** |
| **Track 3** (ISR→timer) | Timeslot holds GPIOTE ISR pending → when it fires, `check_pyd_interrupt` runs with 620µs dead window → if another edge arrives during this, doubly blocked. Timeslot + dead window stack additively. | **HIGH** |
| **Track 4** (sleep/wake) | Sleep defers to `sd_app_evt_wait()` which does NOT return for SoftDevice radio events. During timeslot, CPU is awake (RADIO ISR running) but application is preempted. No "partial wake" concern. | **NONE** |
| **Track 5** (handler drop) | THE PRIMARY INTERACTION. Timeslot causes edge #1 to set latch, edge #2 lost. When ISR finally runs, pin reads LOW → handler silently returns. Combined loss: edge #2 gone from LATCH, edge #1 dropped by handler. | **CRITICAL** |
| **Track 6** (recovery) | 6-hour `pyd_restart()` is the safety net. Timeslot-induced losses accumulate over hours until the blind timer fires and restores PIR capability. The 6-hour period is compatible with timeslot loss rates. | **CONFIRMED** |

---

## 7. Source Verification

| Finding | Evidence | File:Line |
|---------|----------|-----------|
| SoftDevice S132 | Path: `application/pca10040/s132/config/sdk_config.h` | Directory structure |
| SD_EVT = SWI2 | `#define SD_EVT_IRQn (SWI2_IRQn)` | nrf_soc.h:83 |
| GPIOTE priority 6 | `#define GPIOTE_CONFIG_IRQ_PRIORITY 6` | sdk_config.h:1701 |
| nrfx GPIOTE priority 6 | `#define NRFX_GPIOTE_CONFIG_IRQ_PRIORITY 6` | sdk_config.h:2233 |
| APP_TIMER priority 6 | `#define APP_TIMER_CONFIG_IRQ_PRIORITY 6` | sdk_config.h:6420 |
| Dispatch model INTERRUPT | `#define NRF_SDH_DISPATCH_MODEL 0` | sdk_config.h:12110 |
| GAP event length 7.5ms | `#define NRF_SDH_BLE_GAP_EVENT_LENGTH 6` | sdk_config.h:11603 |
| Connection interval 20-70ms | `MIN_CONN_INTERVAL 20ms, MAX_CONN_INTERVAL 70ms` | main.c:130-131 |
| Connection interval 800ms | `MIN/MAX_CONN_INTERVAL 800ms` | main.c:135-136 |
| Slave latency 0 | `#define SLAVE_LATENCY 0` | main.c:132 |
| RTC0 not app-managed | `#define RTC0_ENABLED 0` | sdk_config.h:5542 |
| RTC1 not app-managed | `#define RTC1_ENABLED 0` | sdk_config.h:5549 |
| RTC0 nrfx disabled | `#define NRFX_RTC0_ENABLED 0` | sdk_config.h:3422 |
| RTC1 nrfx disabled | `#define NRFX_RTC1_ENABLED 0` | sdk_config.h:3429 |
| BLE init sequence | `ble_stack_init()` calls nrf_sdh_enable_request, ble_default_cfg_set, ble_enable | main.c:242-266 |
| BLE observer registered | `NRF_SDH_BLE_OBSERVER(m_ble_observer, 3, ble_evt_handler, NULL)` | main.c:261 |
| No GPIO in BLE handlers | Search all `ble_*_on_ble_evt`, `ble_evt_handler`, `gatt_evt_handler` | ble_user.c, ble_aus.c, ble_aus_c.c, ble_dfu_c.c, main.c |
| SD priority set by stack | "Interrupt priority has already been set by the stack." | nrf_sdh.c:228 |
| External crystal | `NRF_SDH_CLOCK_LF_SRC 1` (XTAL unless NO_EXTERNAL_CLOCK) | sdk_config.h:12129 |
| fstorage busy-wait | `while (nrf_fstorage_is_busy(...)) {}` | camera_flash.c:57, bstorage.c:167 |
| Flash SD API | `p_fs_api = &nrf_fstorage_sd` | camera_flash.c:73, ble_user.c:1654, ble_beacon_sensor.c (similar) |

---

## 8. Recommendations

### Immediate (low-risk mitigations for timeslot-related loss)

1. **Verify actual negotiated connection interval in the field.** If the phone negotiates close to 20ms, the timeslot duty cycle is 37.5% and the double-edge collision risk is significant. If closer to 800ms, risk is negligible. Add logging of `p_ble_evt->evt.gap_evt.params.connected.conn_params` to confirm.

2. **Add LATCH-based double-detection.** After the GPIOTE ISR fires, read the GPIO LATCH register directly (not through nrfx abstraction) to check if additional edges occurred while the ISR was pending. This requires direct PORT register access:
   ```c
   // After ISR fires, before clearing:
   if (NRF_P0->LATCH & (1 << PIR_OUT_PIN)) {
       // A second edge occurred while ISR was pending
       // Re-set pyd_interrupt_status for the lost edge
   }
   ```

### Medium-term (address the root interaction)

3. **Raise GPIOTE priority above SoftDevice reservation.** If the SoftDevice reserves priorities 0-4, set GPIOTE IRQ to priority 5 (or even 3 if the SoftDevice is confirmed to only use 0-2). This allows GPIOTE to fire even during SoftDevice timeslots:
   ```c
   #define GPIOTE_CONFIG_IRQ_PRIORITY 5  // Above SoftDevice BASEPRI
   ```
   **Risk:** Must verify that the GPIOTE ISR does not call any SoftDevice API (sd_*) from the higher-priority context.

4. **Buffer PIR events in ISR.** Instead of relying on the single LATCH bit, use the GPIOTE ISR to increment an event counter. The main loop processes all queued events:
   ```c
   static volatile uint8_t pir_event_count = 0;
   static void gpiote_event_handler(...) {
       pir_event_count++;  // Atomic on Cortex-M4 for uint8_t
       pyd_set_status(1);
   }
   ```

### Long-term (architectural)

5. **Use PPI + TIMER for hardware PIR debouncing.** Connect PIR pin → GPIOTE → PPI → TIMER capture, eliminating ISR latency from the detection path entirely.

6. **Move PIR processing to lowest SoftDevice priority level.** If GPIOTE must remain at priority 6, ensure `check_pyd_interrupt` never calls SoftDevice APIs (`sd_*`) from ISR context, preventing priority inversion.

---

## 9. Confidence Assessment

| Aspect | Confidence | Rationale |
|--------|-----------|-----------|
| SoftDevice identity | **HIGH (10/10)** | S132 confirmed by multiple paths |
| NVIC priority map | **HIGH (9/10)** | All application priorities confirmed from sdk_config.h; SoftDevice priorities from standard Nordic documentation and nrf_sdh.c comments |
| Timeslot duration | **HIGH (10/10)** | GAP event length = 6 confirmed, radio timeslot duration from Nordic BLE spec |
| Multi-edge LATCH loss | **HIGH (9/10)** | LATCH single-event-per-pin behavior confirmed from nRF52832 PS v1.4 §27.2; actual double-edge timing depends on PYD1598 sensor behavior (not spec-verified) |
| RTC no conflict | **HIGH (10/10)** | RTC0/RTC1 on separate hardware instances confirmed from sdk_config.h |
| BLE handler no GPIO | **HIGH (10/10)** | Full search of all BLE event handlers |
| Flash blocking | **HIGH (10/10)** | Busy-wait loops confirmed in source |
| Root cause vs contributing | **HIGH (8/10)** | Combined model supported by all 6 prior tracks; downgrade from 10 because actual negotiated connection interval in the field is unknown |

---

## 10. Success Criteria Checklist

| Criterion | Status |
|-----------|--------|
| Complete NVIC priority map including SoftDevice reserved levels | **DONE** (§2) |
| Determination: are GPIOTE or RTC interrupts blocked during BLE radio timeslots? | **DONE — YES, BLOCKED** (§2.3, §3) |
| Assessment: can multiple PIR edges occur within a single timeslot? | **DONE — PLAUSIBLE, LOW PROBABILITY** (§3.3) |
| Determination: is the SoftDevice a root cause or contributing timing factor? | **DONE — CONTRIBUTING TIMING FACTOR** (§6) |
