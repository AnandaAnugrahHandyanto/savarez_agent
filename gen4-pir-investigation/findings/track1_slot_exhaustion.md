# Track 1 — GPIOTE Software Slot Exhaustion Analysis (Gen4)

**Date:** 2026-05-28
**Codebase:** atel-reveal-4-mcu (branch: pir-analysis-gen4)
**MCU:** nRF52832 (Cortex-M4), bare-metal, SoftDevice S132

---

## Executive Summary

**Verdict: Slot exhaustion is architecturally possible, but the effective risk level depends on how the legacy config compatibility layer resolves `NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS` at compile time.**

Two scenarios exist depending on whether `apply_old_config.h` is reached before or after `sdk_config.h` finals the value:

| Scenario | Effective PORT Slots | Active Callers (GA02) | Risk |
|----------|---------------------|----------------------|------|
| Legacy override active (6) | 6 | 4 | **LOW** — slots exceed callers; PIR re-acquire always has spares |
| nrfx template default (1) | 1 | 4 | **CRITICAL** — boot-time reset via `APP_ERROR_CHECK` |

The public finding in `sdk_config_analysis.md` that described a "discrepancy" was refined here: the legacy compatibility layer (`apply_old_config.h`) does *override* the nrfx value, but the override may or may not be in effect depending on the toolchain's `-include` / include-search order used for the actual firmware build.

---

## 1. SDK Configuration Analysis

### 1.1 Raw Config Values

From `sdk_config.h` (lines 1682-1684, 2216-2218):

```
GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS       = 6    (legacy)
NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS  = 1    (nrfx template, #ifndef-guarded)
```

The `NRFX_...` variant uses `#ifndef`, so it only takes effect if not already defined.

### 1.2 Legacy Compatibility Override

File: `integration/nrfx/legacy/apply_old_config.h` (lines 177-185):

```c
#if defined(GPIOTE_ENABLED)                              // 1 from sdk_config.h
#undef NRFX_GPIOTE_ENABLED
#define NRFX_GPIOTE_ENABLED  GPIOTE_ENABLED

#if defined(GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS)       // 6 from sdk_config.h
#undef NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS
#define NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS  GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS
#endif
...
#endif // defined(GPIOTE_ENABLED)
```

This file is included from `nrfx_glue.h` (line 57), which is included by the main `nrfx.h` header.

**Critical note:** This uses `#undef` + `#define` — NOT `#ifndef`. It will unconditionally overwrite any prior value. If included after `sdk_config.h` (which is the standard SDK include order), the effective value = **6**. If a toolchain flag causes `apply_old_config.h` to be evaluated before the config section of `sdk_config.h`, or if `GPIOTE_ENABLED` is not yet defined at the point of inclusion, the legacy override is skipped and the nrfx template default of **1** applies.

**Recommendation:** Verify the actual build value with a preprocessor diagnostic (`#pragma message` or `-E` dump). The safest assumption is that the effective value could be 1, which is catastrophic.

### 1.3 Caller Count vs Slot Count

If effective slots = 1:
- Active callers (GA02): BUTTON_RESET (31), SPS_SWITCH_PIN (24), TBP_WAKE_BLE (29), PIR_OUT (26) = **4**
- **4 callers > 1 slot → guaranteed slot exhaustion at boot**

If effective slots = 6:
- **4 callers < 6 slots → no steady-state exhaustion**
- The PIR's dynamic allocate/deallocate cycle is a *different* class of problem (see Track 4 / Errata 89 interaction)

---

## 2. GPIOTE Abstraction Layer

### 2.1 Architecture

The codebase uses a **single unified nrfx driver** with a thin legacy wrapper layer:

```
nrf_drv_gpiote_in_init()  →  #define →  nrfx_gpiote_in_init()
nrf_drv_gpiote_init()     →  #define →  nrfx_gpiote_init()
nrf_drv_gpiote_is_init()  →  #define →  nrfx_gpiote_is_init()
```

All defined in `integration/nrfx/legacy/nrf_drv_gpiote.h`. There is NO separate legacy control block — all state lives in a single `gpiote_control_block_t` instance (`m_cb`) in `nrfx_gpiote.c`.

### 2.2 Control Block Structure

```c
typedef struct {
    nrfx_gpiote_evt_handler_t handlers[GPIOTE_CH_NUM + NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS];
    int8_t  pin_assignments[NUMBER_OF_PINS];           // -1=free, -2=OUT-task, 0..7=TE, >=8=PORT
    int8_t  port_handlers_pins[NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS];
    uint8_t configured_pins[((NUMBER_OF_PINS)+7)/8];
    nrfx_drv_state_t state;
} gpiote_control_block_t;
```

### 2.3 Channel Namespace

```
handlers[0..7]   → TE (Task/Event) channels  → hi_accuracy=true → dedicated GPIOTE HW channels
handlers[8..13]  → PORT event slots           → hi_accuracy=false → SENSE-based, shared PORT event ISR

GPIOTE_CH_NUM = 8 (from nrf52832_peripherals.h)
```

With `NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS = 6`:
- Total handler entries: 8 + 6 = 14
- PORT event slots: indices 8 through 13 (6 slots, each tracking one pin)

### 2.4 Allocation Algorithm (`channel_port_alloc`, line 196)

```c
static int8_t channel_port_alloc(uint32_t pin, nrfx_gpiote_evt_handler_t handler, bool channel) {
    int8_t channel_id = NO_CHANNELS;
    uint32_t start_idx = channel ? 0 : GPIOTE_CH_NUM;     // 0 for TE, 8 for PORT
    uint32_t end_idx = channel ? GPIOTE_CH_NUM : (GPIOTE_CH_NUM + NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS);
    for (i = start_idx; i < end_idx; i++) {
        if (m_cb.handlers[i] == FORBIDDEN_HANDLER_ADDRESS) {  // 0xFFFFFFFF = free slot
            pin_in_use_by_te_set(pin, i, handler, channel);
            channel_id = i;
            break;   // first free slot wins
        }
    }
    return channel_id;
}
```

Key behaviors:
- Scans from lowest index upward — first free slot is taken
- For PORT events (channel=false): searches indices 8 to 8+NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS
- If no free slot: returns `NO_CHANNELS` (-1)

### 2.5 Deallocation (`channel_free`, line 221)

```c
static void channel_free(uint8_t channel_id) {
    m_cb.handlers[channel_id] = FORBIDDEN_HANDLER_ADDRESS;
    if (channel_id >= GPIOTE_CH_NUM) {
        m_cb.port_handlers_pins[channel_id - GPIOTE_CH_NUM] = (int8_t)PIN_NOT_USED;
    }
}
```

---

## 3. Complete Call Site Map

### 3.1 All `nrfx_gpiote_in_init` / `nrf_drv_gpiote_in_init` Call Sites

| # | File | Line | API | Pin | Config | Callback | Variant | Status (GA02) | PIR? |
|---|------|------|-----|-----|--------|----------|---------|---------------|------|
| 1 | `camera_pyd1598.c` | 205 | `nrf_drv_...` | PIR_OUT (26) | TOGGLE(false) | `gpiote_event_handler` (local) | GA01, GA02 | DYNAMIC | **YES** |
| 2 | `camera_key.c` | 143 | `nrf_drv_...` | BUTTON_RESET (31) | TOGGLE(false) | `gpio_irqCallbackFunc` | GA01(14), GA02(31) | STATIC | No |
| 3 | `camera_sps.c` | 47 | `nrf_drv_...` | SPS_SWITCH_PIN (24) | TOGGLE(false) | `gpio_irqCallbackFunc` | GA01, GA02 | CONDITIONAL | No |
| 4 | `platform_hal_drv.c` | 584 | `nrfx_...` | `gpin[index].pin` (dynamic) | LOTOHI(false) | `gpiote_event_handler` (global) | GA01, GA02 | COMPILE-OFF | No |
| 5 | `platform_hal_drv.c` | 2670 | `nrf_drv_...` | USB_DET_MCU (29) | TOGGLE(false) | `usb_vbus_detection_handler` | GA01, GA02 | COMPILE-OFF (TBP wins) | No |
| 6 | `platform_hal_drv.c` | 2701 | `nrf_drv_...` | TBP_WAKE_BLE (29) | TOGGLE(false) | `tbp_wakeup_detection_handler` | GA01, GA02 | STATIC | No |

**All 6 use `hi_accuracy=false` → all compete for PORT event slots.** No caller uses `hi_accuracy=true` (dedicated TE channel).

### 3.2 Compile-Time Active/Inactive Breakdown (GA02 Configuration)

From `lib/slp01_hal.h`:
- `BLE_FUNCTION_ONOFF = BLE_FUNCTION_OFF` → MDM_WAKE_BLE GPIO NOT configured as interrupt
- `ACC_FUNCTION_ONOFF = ACC_FUNCTION_OFF` → ACC_INT1_PIN GPIO NOT configured as interrupt
- `#define TBP_WAKE_MCU_SUPPORT` (user.h line 20) → TBP (pin 29) active
- `//#define AP_USB_DETECT_VIA_MCU` (user.h line 18, commented out) → USB (pin 29) inactive

**Active at runtime (GA02):** 4 PORT event pins — BUTTON_RESET, SPS_SWITCH_PIN, TBP_WAKE_BLE, PIR_OUT

### 3.3 Error Handling at Call Sites

Every call site uses `APP_ERROR_CHECK(err_code)` on the return value of `nrfx/drv_gpiote_in_init()`. In release builds (`#ifndef DEBUG`), `APP_ERROR_CHECK` calls `app_error_handler_bare()` → `app_error_fault_handler()` (weak default) → `NVIC_SystemReset()`. **Any `NRFX_ERROR_NO_MEM` return triggers a chip reset.**

The exception is `platform_hal_drv.c` line 584 which returns the error code to the caller (`pf_gpio_cfg`), but that caller is unreachable in GA02 (both `ATEL_GPIO_FUNC_INT` configurations are compile-disabled).

---

## 4. Slot Allocation Semantics on Exhaustion

### 4.1 Normal Flow

```
nrfx_gpiote_in_init(pin, config, handler) →
    channel_port_alloc(pin, handler, hi_accuracy=false) →
        scan handlers[8..13] for FORBIDDEN_HANDLER_ADDRESS →
            found → allocate slot → return NRFX_SUCCESS
            not found → return NRFX_ERROR_NO_MEM
```

### 4.2 Exhaustion Outcome

When all PORT event slots are occupied:
1. `channel_port_alloc` returns `NO_CHANNELS` (-1)
2. `nrfx_gpiote_in_init` returns `NRFX_ERROR_NO_MEM` (typically value 4, `NRF_ERROR_NO_MEM`)
3. Call site's `APP_ERROR_CHECK` triggers `app_error_handler_bare()` → `NVIC_SystemReset()`
4. System reboots — no graceful degradation, no logging of which pin failed

### 4.3 SoftDevice Interactions

The SoftDevice (S132) can reserve up to 2 GPIOTE TE channels (indices 0-1 typically) for BLE radio timing. This does NOT affect PORT event slots (indices 8+), which are SENSE-based GPIO events handled entirely by the application at priority 6.

---

## 5. `nrfx_gpiote_in_uninit` Call Map

| # | File | Line | Target | Context |
|---|------|------|--------|---------|
| 1 | `camera_pyd1598.c` | 214 | PIR_OUT (26) | `pyd_gpio_in_disable()` — called from `pyd_gpio_reconfig()`, `pyd_init()`, `pyd_restart()` |
| 2 | `camera_pyd1598.c` | 245 | PIR_OUT (26) | Commented out in `pyd_gpio_reconfig()` |
| 3 | `platform_hal_drv.c` | 1680 | MDM_WAKE_BLE (pin 8) | `pf_bootloader_pre_enter()` — compile-guarded by BLE enable |
| 4 | `platform_hal_drv.c` | 1682 | ACC_INT1_PIN | `pf_bootloader_pre_enter()` — compile-guarded by ACC enable |

**PIR uninit is the only runtime uninit for an active PORT slot.** The PIR pin is torn down (`nrfx_gpiote_in_uninit(PIR_OUT)`) and re-acquired (`nrf_drv_gpiote_in_init(PIR_OUT, ...)`) on every detection cycle. The bootloader uninit calls (MDM_WAKE_BLE, ACC_INT1_PIN) are both compile-disabled in GA02.

---

## 6. `pyd_gpio_in_enable` Call Site Analysis

### 6.1 Definition

```c
// camera_pyd1598.c:198-209
void pyd_gpio_in_enable(void) {
    uint32_t err_code;
    nrf_drv_gpiote_in_config_t config = GPIOTE_CONFIG_IN_SENSE_TOGGLE(false);
    config.pull = NRF_GPIO_PIN_NOPULL;
    err_code = nrf_drv_gpiote_in_init(PIR_OUT, &config, gpiote_event_handler);
    APP_ERROR_CHECK(err_code);                          // RESET ON FAILURE
    nrf_drv_gpiote_in_event_enable(PIR_OUT, true);
}
```

### 6.2 All Callers

| Caller | Line | Context |
|--------|------|---------|
| `pyd_init()` | 267 | Boot-time initialization — once |
| `pyd_gpio_reconfig()` | 248 | PIR detection cycle — **after every motion event** |
| `pyd_restart()` | 295 | PIR restart (threshold change, power cycle) — infrequent |

### 6.3 PIR Detection Cycle — The Dead Zone

The `pyd_gpio_reconfig()` function (line 231) is the critical path:

```
1. pyd_gpio_in_disable()       → uninit PIR_OUT  → SLOT FREED
2. pyd_gpio_read_value()       → bit-bang PIR_OUT → ~2ms, PIR_OUT is GPIO output
3. pyd_gpio_out_low()          → drive PIR_OUT low
4. pyd_gpio_in_enable()        → re-init PIR_OUT  → SLOT RE-ACQUIRED
```

Between steps 1 and 4, the PIR GPIOTE is completely inactive. If the PYD1598 sensor pulses PIR_OUT high during this window:
- No GPIOTE ISR fires (channel is de-allocated)
- The transition is permanently lost
- No software re-read is performed after step 4 to catch missed edges

**This is the primary mechanism for missed PIR events — NOT slot exhaustion.** See Track 4 for detailed analysis of this vulnerability window.

### 6.4 Slot Re-Acquisition Failure Scenario

If `pyd_gpio_in_enable()` at step 4 fails (slot exhaustion):
- `APP_ERROR_CHECK` triggers `NVIC_SystemReset()`
- The system reboots
- On reboot, PIR re-initializes normally

For this to happen, ALL 6 PORT slots must be occupied when step 4 executes. With only 4 total callers and the PIR itself having just freed a slot, this scenario requires 2 other unknown callers — which do not exist in the codebase. **Slot exhaustion during PIR re-acquisition is NOT a plausible failure mode in the current build.**

---

## 7. Architectural Risk Assessment

### 7.1 If `NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS = 1` (nrfx template default)

**CRITICAL — Boot failure.** The system cannot initialize. The second GPIOTE init call will return `NRFX_ERROR_NO_MEM` and `APP_ERROR_CHECK` will reset. Init order (`main.c` line 551-560):

```
nrfx_gpiote_init()              → initialize driver
gpio_key_init()                 → BUTTON_RESET (pin 31) → takes only PORT slot
tbp_wakeup_detection_init()     → TBP_WAKE_BLE (pin 29) → PORT slot exhausted → RESET
```

The system never reaches `camera_sps.c` initialization or the PIR init.

### 7.2 If `NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS = 6` (legacy override active)

**LOW — Steady-state OK; dynamic re-acquisition safe.** 4 callers < 6 slots. The PIR re-acquire at step 4 always finds a free slot. The system boots correctly.

However, **the PORT event ISR (line 723-824) only processes `NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS` pins.** With 6 slots and 4 active pins, the ISR correctly processes all 4. But the ISR loop does a linear scan — more slots = more ISR latency.

### 7.3 Future Risk: Adding Pin 30 LPCOMP

GA02 currently has `LPCOMP_ENABLED = 1` for key detection. LPCOMP uses its own peripheral (not GPIOTE), so it does NOT consume a GPIOTE slot. However, if LPCOMP were ever migrated to use GPIOTE SENSE-triggered detection, it would be a 5th PORT event caller — still within the 6-slot budget but reducing headroom from 2 to 1.

---

## 8. Key Findings

1. **The `sdk_config_analysis.md` "discrepancy" (6 vs 1) is resolved by `apply_old_config.h`** — the legacy compatibility layer overrides the nrfx template value. But the override is conditional on include order; the actual build value should be verified with a preprocessor dump.

2. **If the effective value is 1, slot exhaustion is guaranteed** — the system resets during boot before PIR is ever initialized.

3. **If the effective value is 6, steady-state exhaustion does NOT occur** — 4 callers in 6 slots leaves 2 spare slots at all times.

4. **All callers use `hi_accuracy=false`** — every pin uses the SENSE-based PORT event mechanism. No pin uses a dedicated TE channel. This is architecturally unusual for a real-time system.

5. **The PIR's vulnerability is the GPIOTE dead zone during `pyd_gpio_reconfig()`**, NOT slot exhaustion. The ~2ms window where PIR_OUT is bit-banged as GPIO output is the primary mechanism for missed events (see Track 4).

6. **`APP_ERROR_CHECK` on GPIOTE init failure → NVIC_SystemReset** — there is no graceful error handling for slot exhaustion. The system simply reboots.

---

## 9. T1→T5, T1→T6 Cross-Track Implications

### 9.1 T1→T5: Handler Drop + GPIO SENSE

Track 5 investigates the `gpiote_event_handler` dispatch and GPIO SENSE configuration. Track 1's findings provide critical constraints and focus areas for Track 5:

| T1 Finding | T5 Implication |
|-----------|---------------|
| All callers use `hi_accuracy=false` | Track 5's analysis operates entirely within the PORT event ISR path — not TE channel IN events. The SENSE mechanism (LOTOHI/TOGGLE on pin transitions) triggers a shared PORT event, and `gpiote_event_handler()` performs the pin-to-handler dispatch in software. |
| PIR is the ONLY pin with dynamic SENSE re-registration | During `pyd_gpio_reconfig()`, the PIR pin's SENSE configuration is torn down (`nrfx_gpiote_in_uninit`) and re-established (`nrf_drv_gpiote_in_init` with `GPIOTE_CONFIG_IN_SENSE_TOGGLE`). Other pins (BUTTON_RESET, SPS_SWITCH_PIN, TBP_WAKE_BLE) are configured once at boot and never changed. Track 5 should focus on the PIR pin's SENSE latch clearing behavior during this tear-down/re-establish cycle. |
| T1's dead-zone discovery (~2ms GPIO output window) affects SENSE re-registration | While PIR_OUT is bit-banged as GPIO output (step 2 of `pyd_gpio_reconfig()`), the pin is NOT configured for SENSE. Any pin transitions during this window are invisible to GPIOTE. After re-registration (step 4), the SENSE mechanism resumes — but the question Track 5 must answer is whether the initial SENSE level latched post-reconfig matches the current physical pin state, or whether a stale latch from the pre-uninit state can persist. |
| `channel_free()` nulls the handler but does NOT touch LATCH/SENSE registers | Section 2.5 shows `channel_free()` only clears the handler slot and `port_handlers_pins[]`. It does not clear the GPIOTE LATCH register or reconfigure PIN_CNF[SENSE]. Track 5 must determine whether stale latched events from the SENSE mechanism survive the `nrfx_gpiote_in_uninit` → `nrf_drv_gpiote_in_init` boundary, potentially triggering a spurious event immediately after re-registration. |

### 9.2 T1→T6: Recovery Mechanism

Track 6 analyzes recovery and fault tolerance. Track 1's findings define the boundaries of what recovery is architecturally possible:

| T1 Finding | T6 Implication |
|-----------|---------------|
| `APP_ERROR_CHECK` → `NVIC_SystemReset()` is the ONLY error path | There is no graceful degradation, no fallback to polling, no retry mechanism, no logging, no error counter. Any GPIOTE init failure is fatal. Track 6's recovery analysis is constrained: the **only** recovery from GPIOTE slot exhaustion is a full system reboot via `NVIC_SystemReset()`. |
| PIR's `pyd_gpio_in_disable()` is the ONLY active runtime uninit | T1 mapped all 4 `nrfx_gpiote_in_uninit` call sites (Section 5). The PIR is the sole dynamic deallocator. The other 3 call sites (commented-out PIR, bootloader BLE/ACC) are compile-disabled in GA02. Track 6's analysis of runtime re-init paths should focus exclusively on `pyd_gpio_in_enable()` as the primary dynamic re-init path. |
| With 6 effective slots, `pyd_gpio_in_enable()` always finds a free slot | Section 6.4 demonstrates that 4 active callers in 6 slots means the PIR's re-acquisition at step 4 of the detection cycle is architecturally safe. Even under worst-case timing (all 3 other pins occupying slots simultaneously), 2 spares remain. The PIR's re-init path is immune to slot exhaustion regardless of timing. |
| Boot-time catastrophic failure with 1 effective slot | If the effective slot count is 1, the system enters an unrecoverable boot loop: `gpio_key_init()` takes the only slot → `tbp_wakeup_detection_init()` fails with `NRFX_ERROR_NO_MEM` → `APP_ERROR_CHECK` → `NVIC_SystemReset()` → boot → repeat. Track 6 should classify this as a **catastrophic unrecoverable failure mode**: no watchdog recovery, no fallback, no partial functionality — the device is bricked until firmware is reflashed with a corrected slot count. |

---

## 10. Recommendations

1. **Verify the build-time value of `NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS`** with a preprocessor diagnostic (`-E -dM` or `#pragma message`).

2. **Bump `NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS` to an explicit, non-`#ifndef`-guarded value in `sdk_config.h`** (e.g., `#define NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS 6` without the `#ifndef` guard) to eliminate the ambiguity.

3. **Consider changing `BUTTON_RESET` to use `hi_accuracy=true`** — a dedicated TE channel for a button debounce timer that runs 3000ms is wasteful of a TE channel, but the button is the only always-on, non-PIR input. With `hi_accuracy=false`, the button shares the PORT event ISR with TBP and SPS, and its 3000ms debounce timer firing would delay processing of other PORT events.

4. **For the PIR specifically:** The slot exhaustion concern is secondary to the dead-zone concern. After `pyd_gpio_in_enable()` re-acquires a slot, add a software re-read of `PIR_OUT` to catch transitions that occurred during the bit-bang window (see Track 4 / Errata 89 workaround).
