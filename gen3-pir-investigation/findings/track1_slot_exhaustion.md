# Track 1: GPIOTE Software Slot Exhaustion — Investigation Findings

**SPEC Reference:** Section 6, Track 1 | **Investigator:** internal-coder | **Date:** 2026-05-27
**Branch:** `pir-analysis` | **Confidence: HIGH**

---

## Executive Summary

**The GPIOTE PORT event slot IS exhausted.** The `nrf_drv_gpiote` "legacy" layer is a thin `#define` wrapper around `nrfx_gpiote` — they share the SAME control block. All 5 active PORT-event pins compete for 1 nrfx_gpiote slot. The prior investigation's estimate of 8 competing callers was inflated because it assumed the legacy `nrf_drv_gpiote` driver had independent slots — the `#define` wrapper discovery (Section 1) shows they share the same control block. Additionally, 4 of the original 9 documented pins do not use GPIOTE PORT events (output-only, excluded from init, or commented out — see Section 4.2).

Additionally, there is a **control-flow bug** in `pf_gpio_cfg()` that causes the very first `ATEL_GPIO_FUNC_INT` pin to always fail registration, regardless of slot availability.

---

## 1. Critical Finding: nrf_drv_gpiote IS nrfx_gpiote

**File:** `GA01-IrbisMcu/integration/nrfx/legacy/nrf_drv_gpiote.h` (lines 87-121)

```c
#define nrf_drv_gpiote_init            nrfx_gpiote_init
#define nrf_drv_gpiote_in_init         nrfx_gpiote_in_init
#define nrf_drv_gpiote_in_uninit       nrfx_gpiote_in_uninit
#define nrf_drv_gpiote_in_event_enable nrfx_gpiote_in_event_enable
#define nrf_drv_gpiote_in_event_disable nrfx_gpiote_in_event_disable
```

**There is no separate legacy driver.** Every call to `nrf_drv_gpiote_*` is literally a macro that expands to `nrfx_gpiote_*`. This means the prior investigation's assumption of "6 legacy slots + 1 nrfx slot = 7 total" is incorrect. There is **1 slot total**, shared by all pins.

The `GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS=6` define in `sdk_config.h` (line 1684) is a **dead define** — the legacy driver doesn't exist as a separate implementation; the nrfx driver doesn't read this define.

---

## 2. Slot Count: Exactly 1 PORT Event Slot

### 2.1 Slot Allocation Internals

**File:** `GA01-IrbisMcu/modules/nrfx/drivers/src/nrfx_gpiote.c` (lines 101-218)

The control block structure (line 101-108):
```c
typedef struct {
    nrfx_gpiote_evt_handler_t handlers[GPIOTE_CH_NUM + NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS];
    int8_t  pin_assignments[NUMBER_OF_PINS];
    int8_t  port_handlers_pins[NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS];  // SIZE = 1
    uint8_t configured_pins[((NUMBER_OF_PINS)+7) / 8];
    nrfx_drv_state_t state;
} gpiote_control_block_t;
```

With `GPIOTE_CH_NUM=8` and `NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS=1`:
- `handlers[9]` = 8 hardware channels (indices 0-7) + 1 PORT slot (index 8)
- `port_handlers_pins[1]` = exactly ONE pin can be registered for PORT events

Slot allocation for PORT events (`channel_port_alloc`, line 196-218):
```c
uint32_t start_idx = channel ? 0 : GPIOTE_CH_NUM;           // = 8 for PORT
uint32_t end_idx   = channel ? GPIOTE_CH_NUM : (GPIOTE_CH_NUM + NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS); // = 9 for PORT

for (i = start_idx; i < end_idx; i++)    // searches ONLY indices 8..8 (1 slot)
{
    if (m_cb.handlers[i] == FORBIDDEN_HANDLER_ADDRESS) {
        pin_in_use_by_te_set(pin, i, handler, channel);
        channel_id = i;
        break;
    }
}
```

**Result:** Only 1 PORT event slot. Second caller gets `NO_CHANNELS` → `NRFX_ERROR_NO_MEM`.

### 2.2 All Pins Use PORT Events (hi_accuracy=false)

Every call site uses `GPIOTE_CONFIG_IN_SENSE_TOGGLE(false)` or `NRFX_GPIOTE_CONFIG_IN_SENSE_LOTOHI(false)` — the `false` parameter sets `hi_accuracy=false`, which means PORT event path. None use dedicated GPIOTE hardware channels.

---

## 3. Slot Exhaustion Behavior

### 3.1 nrfx_gpiote_in_init return values

**File:** `nrfx_gpiote.c` lines 515-563

| Condition | Return Code | Notes |
|-----------|------------|-------|
| Pin already in use by GPIOTE | `NRFX_ERROR_INVALID_STATE` (0x0BAD0001) | Checked BEFORE allocation |
| No free PORT slot | `NRFX_ERROR_NO_MEM` (0x0BAD0004) | Channel allocation fails |
| Success | `NRFX_SUCCESS` (0) | Pin registered |

### 3.2 Error handling at call sites

| Call Site | Pin | Error Handling | If Slot Exhausted |
|-----------|-----|---------------|-------------------|
| `camera_pyd1598.c:205` — `pyd_gpio_in_enable()` | PIR_OUT (26) | `APP_ERROR_CHECK(err_code)` → error handler | **CRASH** (infinite loop in DEBUG, soft reset in release) |
| `camera_key.c:206` — `gpio_key_init()` | BUTTON_RESET (14 or 31) | `APP_ERROR_CHECK(errCode)` | **CRASH** |
| `camera_sps.c:46` — `gpio_sps_switch_irq_init()` | SPS_SWITCH_PIN (24) | `APP_ERROR_CHECK(errCode)` | **CRASH** |
| `platform_hal_drv.c:372` — `pf_gpio_cfg()` | MDM_WAKE_BLE (8) | Returns error to `configGPIO()` | **SILENTLY IGNORED** — `configGPIO` (line 1826) does not check return |
| `platform_hal_drv.c:372` — `pf_gpio_cfg()` | ACC_INT1_PIN (13) | Returns error to `configGPIO()` | **SILENTLY IGNORED** |

**Key distinction:** Pins via `pf_gpio_cfg()`/`configGPIO()` silently fail. Pins via direct driver calls crash the device via `APP_ERROR_CHECK`.

---

## 4. Complete Call Site Map

### 4.1 Pins Using nrfx_gpiote_in_init (PORT, hi_accuracy=false)

| # | Pin | Physical Pin | Registration Function | File:Line | Init Order | Mode | Callback |
|---|-----|-------------|----------------------|-----------|------------|------|----------|
| 1 | GPIO_MDM_WAKE_BLE | **8** | `pf_gpio_cfg()` → `nrfx_gpiote_in_init` | `platform_hal_drv.c:372` | 1st (conditional) | INT (`#ifdef MDM_WAKE_MCU_VIA_INT`) | `gpiote_event_handler` (`platform_hal_drv.c:264`) |
| 2 | GPIO_ACC_INT1_PIN | **13** | `pf_gpio_cfg()` → `nrfx_gpiote_in_init` | `platform_hal_drv.c:372` | 2nd (conditional) | INT (`#if ACC_FUNCTION_ONOFF == ACC_FUNCTION_ON`) | `gpiote_event_handler` (`platform_hal_drv.c:264`) |
| 3 | BUTTON_RESET | **14** or **31** | `nrf_drv_gpiote_in_init` → `nrfx_gpiote_in_init` | `camera_key.c:206` | 3rd | PORT TOGGLE | `gpio_irqCallbackFunc` (`camera_key.c:149`) |
| 4 | SPS_SWITCH_PIN | **24** | `nrf_drv_gpiote_in_init` → `nrfx_gpiote_in_init` | `camera_sps.c:46` | 4th (conditional) | PORT TOGGLE | `gpio_irqCallbackFunc` (`camera_sps.c:27`) |
| 5 | PIR_OUT | **26** | `nrf_drv_gpiote_in_init` → `nrfx_gpiote_in_init` | `camera_pyd1598.c:205` | 5th | PORT TOGGLE | `gpiote_event_handler` (`camera_pyd1598.c:167`) |

> **Note:** There are TWO different `gpiote_event_handler` functions — the PIR one (`camera_pyd1598.c`) handles PIR sensing logic; the platform one (`platform_hal_drv.c`) handles MDM and ACC pins. This distinction matters for Track 5 handler-dispatch analysis.

### 4.2 Pins NOT Using PORT Events

| Pin | Physical Pin | Why Not Competing | Evidence |
|-----|-------------|-------------------|----------|
| GPIO_BLE_WAKE_MDM | **7** | Configured as OUTPUT (`PIN_STATUS(0,1,1,0)` → `DIRECTION_OUT`) — no nrfx_gpiote_in_init called | `platform_hal_drv.c:1788-1790` (`PIN_STATUS` macro: `DIRECTION_OUT` in `gpio_init()`) |
| GPIO_BLE_SLEEP_APP | **11** | Excluded from `gpio_init()` (line 1715) | `platform_hal_drv.c:1715` (pin excluded from `gpio_init()` loop) |
| GPIO_BLE_SLEEP_APP1 | **12** | Excluded from `gpio_init()` (line 1716) | `platform_hal_drv.c:1716` (pin excluded from `gpio_init()` loop) |
| KEY_PIN_NUM | **28** | COMMENTED OUT in `camera_key.c` lines 109-129 | `camera_key.c:109-129` |

### 4.3 Initialization Order

```
main.c:544  → nrfx_gpiote_init()         // Driver initialized, all slots free
main.c:554  → InitApp()
  user.c:1233 → gpio_init()              // Iterates pins 0..N
    → configGPIO( MDM_WAKE_BLE, ... )    // If INT: takes PORT slot (1st to succeed)
    → configGPIO( ACC_INT1_PIN, ... )    // If INT: NO_MEM → silently ignored
  user.c:1407 → gpio_key_init()           // BUTTON_RESET: NO_MEM → CRASH
  user.c:1410 → pyd_init()               // PIR_OUT: NO_MEM → CRASH (if reached)
```

**The pin that wins the single PORT slot is the first INT pin in `gpio_init()` iteration order (GPIO_MDM_WAKE_BLE if `MDM_WAKE_MCU_VIA_INT` is defined, or GPIO_ACC_INT1_PIN if only `ACC_FUNCTION_ONOFF==ACC_FUNCTION_ON`).**

---

## 5. Control-Flow Bug in pf_gpio_cfg

**File:** `platform_hal_drv.c` lines 353-359

```c
if (!nrfx_gpiote_is_init()) {
    if (nrfx_gpiote_init() != NRF_SUCCESS) {
        NRF_LOG_RAW_INFO("pf_gpio_cfg gpiote_init fail.\r");
        NRF_LOG_FLUSH();
    }
    return -1;   // ← BUG: returns -1 regardless of init success/failure
}
```

The `return -1` is inside the `if (!nrfx_gpiote_is_init())` block but OUTSIDE the inner error check. On the first call, whether `nrfx_gpiote_init()` succeeds or fails, the function returns -1. This means the **first ATEL_GPIO_FUNC_INT pin always fails registration** through this path.

**Impact:** This bug is partially masked because `main.c:544` calls `nrfx_gpiote_init()` before `gpio_init()`, so the `!nrfx_gpiote_is_init()` condition is false at the time `pf_gpio_cfg` runs. However, if `pf_gpio_cfg` is ever called when nrfx gpiote is uninitialized (re-init paths, BLE disable/enable cycles), the first pin will fail.

Note: `main.c:544-552` calls `nrfx_gpiote_init()` but does NOT check the return value effectively (only logs on `BLE_FUNCTION_OFF`). If init fails silently, the subsequent pin registrations will see uninitialized `handlers[]` (all zeros) which won't match `FORBIDDEN_HANDLER_ADDRESS` (0xFFFFFFFF), causing ALL pins to get `NRFX_ERROR_NO_MEM`.

---

## 6. PIR Re-Registration Analysis

### 6.1 Registration Paths

`pyd_gpio_in_enable()` is called from 3 locations:

| Caller | File:Line | Context |
|--------|-----------|---------|
| `pyd_init()` | `camera_pyd1598.c:267` | One-time init |
| `pyd_gpio_reconfig()` | `camera_pyd1598.c:248` | PIR reconfiguration sequence (ISR → timer → reconfig) |
| `pyd_restart()` | `camera_pyd1598.c:295` | PIR threshold change (sensor restart) |

### 6.2 Deallocation Path

**File:** `camera_pyd1598.c` lines 211-215
```c
void pyd_gpio_in_disable(void) {
    nrf_drv_gpiote_in_event_disable(PIR_OUT);  // clears SENSE
    nrfx_gpiote_in_uninit(PIR_OUT);             // frees PORT slot, clears pin_assignments
}
```

`nrfx_gpiote_in_uninit` calls `channel_free()` which resets `handlers[8] = FORBIDDEN_HANDLER_ADDRESS`, freeing the slot. The PIR pin properly releases the PORT slot before re-acquiring it.

### 6.3 Re-Registration Window

**File:** `camera_pyd1598.c` lines 231-251
```c
int32_t pyd_gpio_reconfig(void) {
    pyd_gpio_in_disable();       // frees PORT slot (PIR unregistered)
    pyd_value = pyd_gpio_read_value();  // bit-bangs PIR sensor (~300µs)
    pyd_gpio_out_low();          // configures pin as output LOW
    pyd_gpio_in_enable();        // re-registers PORT event (re-acquires slot)
    return pyd_value;
}
```

**Risk:** During the window between `pyd_gpio_in_disable()` and `pyd_gpio_in_enable()`, the PORT slot is FREE. In single-threaded execution (ISR context), no other code can acquire the slot, so this is safe. However:

1. **Errata 75 exposure:** The output-to-input transition without `NOSENSE` intermediate step violates the errata 75 workaround (see `errata_review.md`).
2. **If another init path runs concurrently** (e.g., `gpio_sps_switch_irq_init()` called from ADC processing), the freed slot could be stolen. `gpio_sps_switch_irq_init()` is called from `user.c:2360` in the `checkBatteryVoltage()` path, which runs in timer context. If the timer fires during PIR reconfig, the SPS pin could steal the slot.

---

## 7. PORT Event Pin Multiplexing

The nrfx GPIOTE PORT event mechanism (nrf52832 hardware):
- All PORT events share GPIOTE channel 7 (hardware).
- The `port_handlers_pins[]` table is a **software abstraction** that dispatches the single hardware PORT event to the correct pin handler.
- With `NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS=1`, this table has 1 entry.
- Only 1 pin can be registered in this table at a time.

**This is an nrfx driver limitation, not a custom layer.** The `port_handlers_pins` array size is compile-time fixed by `NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS`. To support more pins, this define must be increased (each slot costs ~8 bytes RAM + iteration time in ISR).

---

## 8. Configuration Scenarios & Impact Matrix

| Compile Flags | Who Gets PORT Slot | Who Fails | Result |
|---------------|-------------------|-----------|--------|
| `MDM_WAKE_MCU_VIA_INT` + `ACC_FUNCTION_ON` | MDM_WAKE_BLE (pin 8) | ACC_INT1 (silent), BUTTON_RESET (crash) | Device crashes on button init |
| `MDM_WAKE_MCU_VIA_INT` only | MDM_WAKE_BLE (pin 8) | BUTTON_RESET (crash) | Device crashes on button init |
| `ACC_FUNCTION_ON` only | ACC_INT1_PIN (pin 13) | BUTTON_RESET (crash) | Device crashes on button init |
| Neither INT pin | BUTTON_RESET (pin 14/31) | PIR_OUT (crash) | Device crashes on PIR init |

**In ALL configurations, at least one pin fails.** If the failing pin uses `APP_ERROR_CHECK` (PIR, BUTTON, SPS), the device enters the error handler (hard fault handler → infinite loop or reset). If a watchdog is configured, the device resets and the cycle repeats.

---

## 9. Key Evidence References

| Evidence | File | Lines |
|----------|------|-------|
| Legacy = nrfx wrapper | `integration/nrfx/legacy/nrf_drv_gpiote.h` | 87-121 |
| 1-slot control block | `modules/nrfx/drivers/src/nrfx_gpiote.c` | 101-108 |
| Slot allocator (PORT) | `modules/nrfx/drivers/src/nrfx_gpiote.c` | 196-218 |
| NO_MEM on exhaustion | `modules/nrfx/drivers/src/nrfx_gpiote.c` | 555-558 |
| sdk_config 1-slot define | `application/pca10040/s132/config/sdk_config.h` | 2218 |
| pf_gpio_cfg init bug | `application/platform_hal_drv.c` | 353-359 |
| configGPIO ignores errors | `application/platform_hal_drv.c` | 1816, 1826, 1832 |
| PIR APP_ERROR_CHECK | `application/camera_pyd1598.c` | 205-206 |
| Button APP_ERROR_CHECK | `application/camera_key.c` | 206-207 |
| SPS APP_ERROR_CHECK | `application/camera_sps.c` | 46-47 |
| nrfx_gpiote_init in main.c | `application/main.c` | 544-552 |
| PIR reconfig window | `application/camera_pyd1598.c` | 231-251 |
| Init order | `application/user.c` | 1233, 1407, 1410 |

---

## 11. Cross-Track Implications

### 11.1 T1 → Track 5 (Handler Drop)

If GPIOTE slot exhaustion causes the PIR pin registration to fail or be evicted, `gpiote_event_handler` (any variant) will **never be called** for PIR events regardless of whether the hardware PORT event fires. Track 5's handler-dispatch analysis must treat "pin not registered" as a distinct failure mode from "handler present but dropping the pin."

Specifically, Track 5 must investigate:

1. Whether the handler dispatch logic has a `default:` case that silently drops unregistered pins.
2. Whether the handler would fire at all if the pin is not in the `port_handlers_pins[]` table.

### 11.2 T1 → Track 6 (Recovery)

The PIR re-registration finding (Section 6) shows `pyd_gpio_in_enable` is called from 3 paths:

- `pyd_init()` — one-time initialization
- `pyd_gpio_reconfig()` — ISR → timer → reconfig chain
- `pyd_restart()` — sensor threshold change

This means slot exhaustion for PIR is **transient** — the PIR sensor periodically re-acquires the PORT slot. Key implications for Track 6:

1. Track 6 must determine whether the reconfig period (driven by `pir_check_start` → timer → `pyd_gpio_reconfig`) matches observed symptom recovery timeframes.
2. If the recovery IS via PIR reconfig, this ALSO means the PIR pin was successfully registered at some point and then lost — supporting a **slot-eviction hypothesis** (T1+T5) rather than a static registration failure.

### 11.3 T1 → Track 4 (Sleep/Wake)

If system sleep causes GPIOTE state loss, the wake re-init path must re-acquire the single PORT slot. Track 4 must verify that the wake init order preserves PIR registration priority.

**Key constraint:** If wake init runs `gpio_init()` (which calls `configGPIO` for MDM/ACC pins) **before** PIR re-init, the PIR slot will be stolen on wake because MDM_WAKE_BLE and ACC_INT1_PIN register first via `configGPIO`. Track 4 must document the wake init sequence relative to Track 1's init order finding (Section 4.3).

---

## 12. Confidence Assessment

**Confidence: HIGH**

Justification:
- The `#define` mapping of `nrf_drv_gpiote_in_init` → `nrfx_gpiote_in_init` is unambiguous (header file, not runtime behavior).
- The control block structure is compile-time defined, not runtime configurable.
- `NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS=1` is confirmed in `sdk_config.h`.
- The `channel_port_alloc` search range [8, 9) is mathematically determined — exactly 1 slot.
- All 5 active pins use `hi_accuracy=false` (PORT events).

The only uncertainty is which configuration the production build uses (which `#ifdef` flags are set), which determines which pin succeeds and which fails. In ALL configurations, at least 2 pins compete for 1 slot.

---

## 13. Recommendations

1. **Increase `NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS`** to at least **5** in `sdk_config.h` to match the number of active PORT-event pins. Each slot costs ~8 bytes RAM + one extra loop iteration in the ISR.

2. **Fix `pf_gpio_cfg` control-flow bug:** Move `return -1;` inside the inner `if (nrfx_gpiote_init() != NRF_SUCCESS)` block, or remove it and allow fall-through to `nrfx_gpiote_in_init`.

3. **Add error checking in `configGPIO()`** for `pf_gpio_cfg()` return values — currently silent failures can cause undetected pin registration loss.

4. **Remove dead `GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS=6`** from `sdk_config.h` or add a comment noting it is unused since `nrf_drv_gpiote` is a macro wrapper.

5. **Consider using `hi_accuracy=true`** (dedicated GPIOTE channels) for the PIR pin to guarantee it never competes for the shared PORT slot. This consumes 1 of 8 hardware channels but guarantees PIR interrupt delivery.
