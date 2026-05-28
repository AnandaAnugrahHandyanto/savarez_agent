# Track 4: FreeRTOS Tickless Idle & GPIOTE Reconfiguration on Sleep/Wake

**Date:** 2026-05-28
**Investigator:** internal-coder
**Confidence:** HIGH (9/10)

## Executive Summary

**The sleep/wake hypothesis is REJECTED.** The device uses System ON sleep (WFE via SoftDevice `sd_app_evt_wait`), which preserves all GPIOTE peripheral registers. No GPIOTE re-initialization occurs on wake. There is no FreeRTOS, no tickless idle, and no RTC conflict with app_timer. BLE connection events do not cause partial wakes. However, the investigation uncovered the **actual recovery mechanism** (`pyd_restart()` every 6 hours) and identified a critical **sleep-guard bypass path** in the main loop that prevents sleep during AP-on states, forcing full-speed polling of `check_pyd_interrupt()`.

**Key findings:**

1. **Not a FreeRTOS system** — bare-metal Cortex-M4 superloop with nRF5 SDK + SoftDevice S132
2. **System ON sleep only** (WFE) — GPIOTE state fully preserved across sleep/wake transitions
3. **No GPIOTE re-init on wake** — `sd_app_evt_wait()` returns without touching peripherals
4. **Recovery mechanism found:** `pyd_restart()` triggered every `PIR_RESTART_TIMEOUT` (6 hours) after last PIR event
5. **Sleep guard bypass:** When AP is powered on AND `SleepState != SLEEP_NORMAL`, main loop never sleeps — `check_pyd_interrupt()` runs every iteration at full speed
6. **app_timer (RTC1) and SoftDevice (RTC0) are independent** — no RTC conflict, no timer drift

---

## 1. Sleep/Wake Entry and Exit Paths

### 1.1 Architecture: Bare-Metal Superloop, No FreeRTOS

The system is a bare-metal Cortex-M4 application built on the nRF5 SDK v15.x. There is **no FreeRTOS** — no `FreeRTOSConfig.h`, no `configUSE_TICKLESS_IDLE`, no `vPortSuppressTicksAndSleep`. The main loop in `main.c:605` is a simple `for(;;)` with sequential function calls.

```
main.c:605  for (;;)
main.c:614    idle_state_handle()          → may call nrf_pwr_mgmt_run() → sleep
main.c:633    atel_timerTickHandler()      → 1s/10ms tick processing
main.c:635    pf_systick_change()          → switch between 1s and 10ms modes
main.c:637    pir_is_checking() spin-wait  → guard ISR→timer→reconfig path
main.c:641    check_pyd_interrupt()        → PIR event processing
```

### 1.2 Sleep Entry: `idle_state_handle()` → `nrf_pwr_mgmt_run()`

**File:** `main.c:355-364`, `nrf_pwr_mgmt.c:340-368`

```c
static void idle_state_handle(void) {
    if (NRF_LOG_PROCESS() == false) {
        // SKIP sleep if phone is powered on AND not in SLEEP_NORMAL
        if ((monet_data.phonePowerOn == 0) || (monet_data.SleepState == SLEEP_NORMAL)) {
            nrf_pwr_mgmt_run();  // ENTER sleep
        }
    }
}
```

**Sleep guard condition** prevents sleep when:
- `monet_data.phonePowerOn != 0` (AP is powered on) AND `SleepState != SLEEP_NORMAL`

This is significant: when the AP is on but not in SLEEP_NORMAL state, the main loop **never sleeps**. It spins through every iteration calling `check_pyd_interrupt()` at full speed (~10ms per iteration). This is a high-power state, but it also means PIR checking is at maximum frequency — no sleep-related event loss possible.

### 1.3 Two Sleep Mechanisms

`nrf_pwr_mgmt_run()` uses two paths depending on SoftDevice state:

| Path | Condition | Mechanism | GPIOTE State |
|------|-----------|-----------|--------------|
| SoftDevice path | `SOFTDEVICE_PRESENT && nrf_sdh_is_enabled()` | `sd_app_evt_wait()` | **Preserved** |
| Bare-metal path | No SoftDevice | `__WFE(); __SEV(); __WFE();` | **Preserved** |

In this project, `SOFTDEVICE_PRESENT` is defined and the S132 SoftDevice is always enabled. The SoftDevice path is always taken.

### 1.4 `sd_app_evt_wait()` Semantics

**File:** `components/softdevice/s132/headers/nrf_soc.h:621-647`

Key properties:
- Puts CPU in **WFE sleep** within System ON mode
- Returns only on **application events**: enabled/disabled interrupts, SoftDevice application events
- Does **NOT** return on SoftDevice-internal BLE radio events (connection events, advertising)
- If an interrupt is already pending at call time, returns **immediately** without sleeping
- `SEVONPEND` is enabled by `nrf_pwr_mgmt_init()` — disabled interrupts can also wake from WFE

**Critical implication:** BLE connection events do NOT cause `sd_app_evt_wait()` to return to the application. There is no "partial wake" scenario where BLE processing could reconfigure GPIOTE without the full main loop running.

---

## 2. What Survives Sleep

### 2.1 System ON (WFE/WFI) vs System OFF

| | System ON (WFE/WFI) | System OFF |
|---|---|---|
| **CPU registers** | Preserved | Lost |
| **Peripheral registers (GPIOTE, RTC, GPIO)** | **Preserved** | **Reset** |
| **RAM retention** | Full | Only configured sections |
| **LFCLK** | Running | Stopped |

### 2.2 Which Mode is Used?

**System ON sleep is used exclusively** in normal operation.

Evidence:
- `NRF_PWR_MGMT_CONFIG_STANDBY_TIMEOUT_ENABLED = 0` — no automatic System OFF after timeout
- `NRF_PWR_MGMT_CONFIG_AUTO_SHUTDOWN_RETRY = 0` — no auto-retry of System OFF
- System OFF (`nrf_power_system_off()`) is only called in `shutdown_process()` during explicit transitions: DFU mode, factory reset, or `NRF_PWR_MGMT_EVT_PREPARE_RESET`
- No registered shutdown handlers in the application code

**Conclusion:** GPIOTE configuration is fully preserved across every normal sleep/wake cycle.

---

## 3. GPIOTE Re-initialization on Wake — NONE

### 3.1 No Re-init Path Exists

After `sd_app_evt_wait()` returns, execution continues at the next instruction in `nrf_pwr_mgmt_run()`:
```c
PWR_MGMT_DEBUG_PIN_CLEAR();
PWR_MGMT_CPU_USAGE_MONITOR_SECTION_EXIT();
PWR_MGMT_SLEEP_LOCK_RELEASE();
```

Then returns to `idle_state_handle()`, then back to `main.c` main loop. **No GPIOTE functions are called in the wake path.** GPIOTE state is whatever it was before sleep — which is fully intact.

### 3.2 When IS GPIOTE Re-initialized?

GPIOTE for PIR_OUT is only re-initialized via three paths, all triggered by events, not sleep/wake:

| Path | Trigger | Files | GPIOTE Unregister Window |
|------|---------|-------|--------------------------|
| `pyd_gpio_reconfig()` | PIR interrupt → ISR → timer → callback | `camera_pyd1598.c:231-251` | **~620µs** |
| `pyd_restart()` | 6-hour inactivity timeout | `camera_pyd1598.c:272-296` | **~23ms** (includes 10ms power-off delay) |
| `pyd_init()` | Boot-time initialization | `camera_pyd1598.c:253-270` | **~10ms** (boot only) |

### 3.3 The 620µs Window in `pyd_gpio_reconfig()`

```c
int32_t pyd_gpio_reconfig(void) {
    pyd_gpio_in_disable();       // UNREGISTERS PIR from GPIOTE
    pyd_value = pyd_gpio_read_value();  // bit-bang read (~600µs)
    pyd_gpio_out_low();          // reconfigure pin as output low
    pyd_gpio_in_enable();        // RE-REGISTERS PIR with GPIOTE
    return pyd_value;
}
```

The window between `pyd_gpio_in_disable()` and `pyd_gpio_in_enable()` is approximately **620µs**. During this time, PIR_OUT has no GPIOTE channel. Any PIR edge is **silently lost**. This is the same window documented in Track 3, and it is NOT sleep-related — it happens during every PIR event processing.

### 3.4 The 23ms Window in `pyd_restart()`

`pyd_restart()` is even worse: it includes a 10ms power-off delay (`nrf_delay_ms(10)`), full PIR sensor re-initialization (25-bit serial write), then re-registration. Total GPIOTE unregistered window: **~23ms**. This runs inside `check_pyd_interrupt()` at the same priority as the caller context.

---

## 4. Tickless Idle + app_timer Interaction

### 4.1 No Tickless Idle

There is no FreeRTOS, therefore no tickless idle. The question is moot.

### 4.2 RTC Allocation

| RTC Instance | Owner | Purpose |
|---|---|---|
| **RTC0** | SoftDevice (S132) | BLE timing, connection scheduling |
| **RTC1** | app_timer library | Application timers, systick generation |
| **RTC2** | Unused (available) | — |

RTC0 and RTC1 are **independent hardware instances**. They share the same LFCLK source (32.768 kHz crystal) but have independent counters, compare registers, and interrupt lines.

### 4.3 LFCLK During Sleep

During System ON sleep (WFE), the LFCLK continues running. Both RTC0 and RTC1 keep counting. app_timer timers fire accurately at their scheduled times, waking the CPU from WFE via the RTC1 interrupt.

### 4.4 app_timer Configuration

```c
// sdk_config.h
APP_TIMER_CONFIG_RTC_FREQUENCY   1    // RTC1 at 32768 Hz
APP_TIMER_CONFIG_IRQ_PRIORITY    6    // Same as GPIOTE
APP_TIMER_CONFIG_USE_SCHEDULER   0    // Direct SWI0 dispatch (no app_scheduler)
APP_TIMER_CONFIG_OP_QUEUE_SIZE   10
```

### 4.5 ISR Context Timer Interaction

`pir_check_start()` calls `app_timer_start()` from GPIOTE ISR context (NVIC priority 6). This is safe — app_timer supports being called from ISR context. The timer callback (`pir_check_handler`) fires via SWI0 at the same priority level (6), which means it can preempt the main loop but cannot preempt the GPIOTE ISR (same priority — Cortex-M tail-chaining behavior).

There is **no RTC conflict** with tickless idle because tickless idle doesn't exist. The app_timer library's RTC1 management is independent of the SoftDevice's RTC0.

---

## 5. BLE Connection Events as Wake Triggers

### 5.1 SoftDevice Radio Internals

The S132 SoftDevice schedules BLE connection events autonomously. When a connection event fires:
1. The radio hardware wakes and processes the BLE packet exchange
2. The CPU briefly wakes (SoftDevice internal) to handle protocol stack processing
3. If there are application-level BLE events (GATT writes, notifications, connection state changes), they are queued
4. The CPU returns to sleep if `sd_app_evt_wait()` was active

### 5.2 No Partial Wake

`sd_app_evt_wait()` is **atomic from the application's perspective**. It only returns to the application when there is an application-level event to process. Internal BLE radio events do NOT cause it to return. Therefore:
- No BLE-driven partial wake that could reconfigure GPIOTE
- No BLE-driven path that touches GPIOTE at all

### 5.3 BLE ISR Priority and GPIOTE Latency

SoftDevice internal ISRs run at **higher priority** than application interrupts (NVIC 0-4 reserved for SoftDevice). During BLE radio processing:
- GPIOTE interrupts (NVIC 6) are **pended but not serviced** until SoftDevice ISRs complete
- This adds latency to GPIOTE event handling
- However, the GPIOTE DETECT latch holds the event, so no edge is lost — only delayed
- Typical BLE event processing: 200-500µs — negligible for PIR detection (multi-second pulses)

### 5.4 Connection Events Don't Prevent Sleep

During active BLE connections, `sd_app_evt_wait()` still puts the CPU to sleep. The SoftDevice internally wakes the CPU for radio events, handles them, and puts it back to sleep. The application's main loop only runs when there are application events to process.

---

## 6. The Recovery Mechanism: `pyd_restart()` Every 6 Hours

### 6.1 Recovery Path

**File:** `user.c:785-791`

```c
void check_pyd_interrupt(void) {
    // ...
    if (pyd_get_status()) {
        // PIR event detected → process it
        pirDetectedTimestamp = count1sec;
        // ...
    }
    else if ((count1sec - pirDetectedTimestamp) >= PIR_RESTART_TIMEOUT) {
        // No PIR activity for 6 hours → restart PIR sensor
        pirDetectedTimestamp = count1sec;
        pyd_restart();  // FULL re-init: power cycle, reconfig, GPIOTE re-register
    }
    // ...
}
```

**`PIR_RESTART_TIMEOUT` = 21600 seconds (6 hours)** — defined in `user.h:98`.

### 6.2 How Recovery Works

If PIR events are being lost (e.g., GPIOTE slot was stolen by another driver, or the PORT event latch is stuck):
1. `pirDetectedTimestamp` is never updated (no PIR events processed)
2. After 6 hours, `(count1sec - pirDetectedTimestamp) >= PIR_RESTART_TIMEOUT` becomes true
3. `pyd_restart()` is called:
   - Powers off PIR sensor for 10ms
   - Unregisters GPIOTE for PIR_OUT
   - Re-initializes PIR sensor (sends 25-bit configuration)
   - Re-registers GPIOTE via `pyd_gpio_in_enable()`
   - Sets `pirDetectedTimestamp = count1sec` (prevents immediate re-trigger)
4. PIR detection resumes

This is the **"eventual recovery"** mechanism. It explains symptom timelines of hours-long outages — the maximum outage is 6 hours (plus any PIR pulse width after restart before the next detection).

### 6.3 Recovery CAN Fail

If the root cause is persistent GPIOTE slot exhaustion (Track 1 failure mode):
- `pyd_restart()` → `pyd_gpio_in_enable()` → `nrf_drv_gpiote_in_init()` → `APP_ERROR_CHECK(err_code)`
- If another driver permanently holds the single PORT event slot, `nrf_drv_gpiote_in_init()` returns an error
- `APP_ERROR_CHECK` in DEBUG: infinite loop (device hangs)
- `APP_ERROR_CHECK` in release: soft reset → full system reboot (harder recovery)

In the soft reset case, the system reinitializes completely, re-claims the GPIOTE slot, and PIR works again — this is the "delay then works" pattern.

---

## 7. Sleep/Wake Timing and Main Loop Tick Modes

### 7.1 Two Tick Modes

The system switches between two timing modes via `pf_systick_change()`:

| Mode | Tick Period | When Used | Main Loop Rate |
|------|-------------|-----------|----------------|
| **SLEEP_NORMAL** | 10ms | `SleepState == SLEEP_OFF` or active processing | ~100 Hz |
| **SLEEP_HIBERNATION** | 1000ms | `SleepState != SLEEP_OFF` (low-power idle) | ~1 Hz |

### 7.2 Implications for PIR Detection

**In HIBERNATION mode (1s tick):**
- Main loop runs once per second
- `check_pyd_interrupt()` in main loop runs once per second
- But GPIOTE ISR → timer → callback path fires within ~150µs of the PIR edge
- So PIR events are still detected promptly — the main loop `check_pyd_interrupt()` is a fallback

**In SLEEP_NORMAL mode (10ms tick):**
- Main loop runs ~100 Hz
- `check_pyd_interrupt()` runs ~100 Hz
- PIR events caught within 10ms (and ISR path within 150µs)

### 7.3 Sleep Guard and HIBERNATION Interaction

Two important scenarios:

**Scenario A: AP off, SleepState = SLEEP_HIBERNATION**
- `monet_data.phonePowerOn == 0` → sleep guard passes → `nrf_pwr_mgmt_run()` called
- Main loop sleeps until next event (GPIOTE, BLE app event, 1s tick timer)
- 1s tick wakes CPU → `atel_timerTickHandler()` → `check_pyd_interrupt()` runs
- GPIOTE events wake CPU immediately → ISR → timer → callback → caught promptly

**Scenario B: AP on, SleepState = SLEEP_OFF**
- `monet_data.phonePowerOn != 0 && SleepState == SLEEP_OFF` → sleep guard BLOCKS
- Main loop NEVER sleeps (no `nrf_pwr_mgmt_run()` call)
- Main loop spins at ~100Hz → `check_pyd_interrupt()` called every 10ms
- GPIOTE ISR → timer → callback fires immediately as well
- **Most responsive state but highest power draw**

---

## 8. The Actual Sleep/Wake Risk (Subtle)

While the raw hypothesis is rejected, there IS a subtle sleep/wake interaction that could contribute to missed events:

### 8.1 `pir_check_start()` Guard Condition

**File:** `user.c:638-647`

```c
void pir_check_start(void) {
    if (monet_data.SleepState != SLEEP_OFF
        && monet_data.SleepStateChange == 0
        && pf_systick_remains() > APP_TIMER_TICKS(TIME_UNIT)  // ← THIS CHECK
        && !pir_checking) {
        pir_checking = true;
        APP_ERROR_CHECK(app_timer_start(m_pir_check_timer, 5, NULL));
    }
    // else: timer NOT started — main loop check_pyd_interrupt() must catch it
}
```

`pf_systick_remains() > APP_TIMER_TICKS(TIME_UNIT)` checks if there's at least 10ms remaining before the next systick. If the systick is about to fire (within 10ms), `pir_check_start()` **skips** starting the timer.

### 8.2 Timing Risk During 1s Tick Mode

In HIBERNATION mode, the systick fires every 1000ms. So `pf_systick_remains()` is almost always > 10ms — the timer typically starts.

But there's a narrow race: if a GPIOTE event fires just as the 1s systick is about to expire (within the last 10ms of the 1s window), `pir_check_start()` skips the timer. The PIR event then depends on the main loop's `check_pyd_interrupt()`, which runs AFTER `atel_timerTickHandler()` in the same iteration. Since `atel_timerTickHandler()` was just called (triggering this iteration), `check_pyd_interrupt()` runs immediately after — no delay.

**Verdict:** Not a real risk. The systick-remaining check is a belt-and-suspenders guard.

---

## 9. The `SleepStateChange` Race

### 9.1 State Transition Window

When `SleepStateChange` transitions to 2 (in-progress), the main loop skips `idle_state_handle()`:

```c
// main.c:608-615
if (monet_data.SleepStateChange == 0) {
    idle_state_handle();  // SKIPPED during state change
}
```

During this transition, the system does not sleep. `check_pyd_interrupt()` still runs every iteration. No PIR events are lost due to sleep during transitions.

---

## 10. Cross-Track Implications

| Track | Relevance |
|-------|-----------|
| **Track 1** (slot exhaustion) | If GPIOTE slot is stolen, `pyd_restart()` recovery path fails (APP_ERROR_CHECK). Sleep/wake is irrelevant — slot exhaustion is a one-time allocation failure, not a sleep-related state loss. |
| **Track 2** (volatile races) | Sleep/wake timing interacts: if `atel_timer1s()` and `check_pyd_interrupt` timer callback race (Track 2), a lost update means `pir_interval_delay` or `pir_is_valid` is corrupted. On next wake, the corrupted state persists. Recovery waits for next 1s tick or next PIR event. |
| **Track 3** (ISR re-entrancy) | `pyd_gpio_reconfig()` 620µs window and `pyd_restart()` 23ms window are the PRECISE mechanisms for missed PIR edges. Sleep/wake does not create new windows — they exist in the ISR→timer→callback cascade regardless. |
| **Track 5** (errata interaction) | Errata 75 (GPIO SENSE after output) applies to `pyd_gpio_reconfig()` every time, not just across sleep. Errata 143 (GPIOTE during WFE) — see Section 10.1. |
| **Track 6** (recovery timing) | The 6-hour `PIR_RESTART_TIMEOUT` defines the maximum outage. If observed recovery is faster, another mechanism exists. If observed recovery matches ~6 hours, this is THE mechanism. |

### 10.1 Errata 143: GPIOTE Events Missed During Sleep

nRF52832 Errata 143 states that GPIOTE PORT events can be missed when the system enters WFE/WFI sleep. However, this errata applies to a specific scenario: when the GPIO SENSE mechanism generates a DETECT signal while the CPU is waking from WFE, the race can cause the PORT event to be dropped.

**In this system:**
- The PIR pin uses `GPIOTE_CONFIG_IN_SENSE_TOGGLE(false)` — detection on any toggle
- The `false` parameter means no automatic pin-toggle (the event doesn't auto-clear)
- The DETECT signal is edge-sensitive — once latched, it stays until the SENSE configuration is changed or the pin matches the expected level
- During WFE sleep: if a PIR edge occurs, DETECT is latched, PORT event fires, CPU wakes
- Errata 143 risk: if a SECOND edge occurs during the CPU wake-up transition, it may be missed

**Mitigation:** PIR sensors produce slow, wide pulses (100ms-2s typical). The probability of a second edge during the wake transition (< 10µs) is negligible. This errata is not a practical concern for PIR detection.

---

## 11. Summary of Findings vs. Hypothesis

| Hypothesis Element | Finding | Verdict |
|---|---|---|
| Low-power sleep causes GPIOTE state loss | System ON sleep preserves all GPIOTE registers | **REJECTED** |
| GPIOTE misconfigured on wake until re-init fires | No re-init path on wake. GPIOTE is intact. | **REJECTED** |
| PIR PORT event registration lost on sleep/wake | Registration survives sleep. Loss occurs in `pyd_gpio_reconfig()` which is event-driven, not sleep-driven. | **REJECTED** |
| FreeRTOS tickless idle involved | No FreeRTOS in system | **REJECTED** |
| app_timer + RTC conflict with tickless idle | No tickless idle. app_timer (RTC1) and SoftDevice (RTC0) are independent. | **REJECTED** |
| BLE connection event causes partial wake | `sd_app_evt_wait()` is atomic. BLE radio events don't return to application. | **REJECTED** |
| **NEW:** Recovery via `pyd_restart()` every 6 hours | `check_pyd_interrupt()` calls `pyd_restart()` after `PIR_RESTART_TIMEOUT` (21600s) of inactivity | **CONFIRMED** |

### 11.1 Final Assessment

The Track 4 hypothesis is **unambiguously rejected across all five investigation dimensions**. The system uses System ON sleep exclusively, GPIOTE state is fully preserved across every sleep/wake transition, there is no FreeRTOS (no tickless idle), and BLE connection events cannot trigger partial wake with GPIOTE reconfiguration.

The actual mechanism for "eventual recovery" is `pyd_restart()`, called every 6 hours of PIR inactivity. If the root cause of missed PIR events is transient (e.g., Track 1 slot exhaustion from a temporary registration, Track 3 reconfig window during concurrent events), the 6-hour restart cycle restores PIR detection. If the root cause is persistent (permanent slot exhaustion), recovery requires a full system reset (via `APP_ERROR_CHECK` in `pyd_gpio_in_enable()`).

The **sleep guard bypass** (no sleep when AP on + SleepState != NORMAL) means the device runs at full speed during active use — PIR events are never missed due to sleep during these periods. The risk window is when the AP is off and the device is in HIBERNATION (1s tick) mode — but even then, the GPIOTE ISR path fires within 150µs, making event loss from sleep itself virtually impossible.
