# Track 2 — monet_data/motion_data Volatile Race Condition (Gen4)

**Project:** Gen4 PIR Investigation — GA02-IrbisMcu (nRF52832 + S132 SoftDevice, nrfx SDK v15.x)
**Date:** 2025-05-28
**Branch:** `pir-analysis-gen4`

---

## 1. Executive Summary

**Verdict: HIGH RISK.** `monet_data` is a 155-member global struct (~500+ bytes) declared **without `volatile`** qualifier, accessed concurrently from **five distinct execution contexts** (GPIOTE ISR, SAADC ISR, TWIS ISR, app_timer callback, main loop) with **zero critical sections or mutex protection**. The `motion_data` variable does **not exist** anywhere in the GA02 codebase.

**Primary hazard:** Compiler optimization can cache, reorder, or elide reads/writes across context boundaries. On nRF52 Cortex-M4 with `-Os` or `-O2`, non-volatile global accesses are eligible for:
- Register caching across function boundaries
- Load/store reordering
- Dead-store elimination (writes in ISR silently dropped)
- Read tearing on multi-byte fields (e.g., `uint32_t` members)

---

## 2. Variable Definition

### 2.1 Definition Site

**File:** `GA02/application/user.c:67`
```c
monet_struct monet_data = {{(IoCmdState)0}};
```

**File:** `GA02/application/lib/user.h:773`
```c
extern monet_struct monet_data;
```

**Verdict: NO `volatile` keyword on either definition or declaration.**

### 2.2 Struct Type

**File:** `GA02/application/lib/user.h:449-605`

```c
typedef struct {
    IoRxFrameStruct     iorxframe;          // nested struct
    atel_ring_buff_t    txQueueU1;           // ring buffer (multi-byte)
    // ... 155 members total, spanning:
    //   uint8_t/is_test_mode, is_ota_mode, is_net_scan, is_udisk_mode...
    //   uint16_t/AdcMain, AdcBackup, AdcLi, AdcBatC, bat_voltage...
    //   uint32_t/InMotion, bbofftime, SleepAlarm, sysTickUnit...
    //   bool/apPowerOn, pir_report_on...
    //   SleepState_e/SleepState
    //   MainState_e/MainState
    //   nested structs: CAMERAGLASS_BREAK_t glass_break
    uint8_t         rawCollisionThreshold;
} monet_struct;
```

**Size:** ~500+ bytes (155 members). Not atomically accessible as a whole.

### 2.3 motion_data

**Does NOT exist** anywhere in the GA02 codebase. Search across all `.c` and `.h` files returned zero hits.

---

## 3. Execution Context Architecture

The nRF52832 firmware has these relevant execution contexts:

| Context | Priority | Preempts |
|---------|----------|----------|
| GPIOTE ISR | High (6) | SAADC, app_timer, main loop |
| SAADC ISR | Medium-High (6) | app_timer, main loop |
| TWIS ISR | Medium-High (6) | app_timer, main loop |
| SoftDevice BLE callbacks | Varies (0-4) | app_timer, main loop |
| app_timer callbacks (RTC2) | Low (3 = APP_IRQ_PRIORITY_LOW) | main loop |
| Main loop (thread mode) | Lowest | — |

**Key insight:** app_timer callbacks run in RTC2 interrupt context at APP_IRQ_PRIORITY_LOW. They preempt the main loop. They are NOT main-thread code.

---

## 4. Complete Access Catalog by Context

### 4.1 GPIOTE ISR Context (HIGH PRIORITY)

#### 4.1.1 `gpio_irqCallbackFunc` — camera_sps.c:28

```c
static void gpio_irqCallbackFunc(nrf_drv_gpiote_pin_t pin, nrf_gpiote_polarity_t action)
{
    if(!nrf_gpio_pin_read(SPS_SWITCH_PIN)) {
        sps_switch_bat_low();
        monet_data.AdcMain = 0;                          // ⚠️ WRITE in ISR
        NRF_LOG_RAW_INFO("... sps removed\n");
        NRF_LOG_FLUSH();
    }
}
```

**Fields written:** `AdcMain` (uint16_t)
**Race partner:** `saadc_callback` also writes `AdcMain`; main loop reads `AdcMain` via `monet_requestAdc()` / `atel_timerTickHandler`.

#### 4.1.2 `gpiote_event_handler` — camera_pyd1598.c:167

```c
static void gpiote_event_handler(nrf_drv_gpiote_pin_t pin, nrf_gpiote_polarity_t action)
{
    if(nrf_gpio_pin_read(PIR_OUT)) {
        pyd_set_status(1);  // ✅ writes static volatile pyd_interrupt_status — safe
    }
}
```

**Fields written:** NONE in monet_data. This handler is correctly written — it only sets a `static volatile` flag.

### 4.2 SAADC ISR Context (HIGH PRIORITY)

#### 4.2.1 `saadc_callback` — platform_hal_drv.c:98

```c
static void saadc_callback(nrf_drv_saadc_evt_t const * p_event)
{
    if (p_event->type == NRF_DRV_SAADC_EVT_DONE) {
        // ... rolling average calculation ...
        monet_data.AdcMain = (main_val > 0) ? main_val : 0;         // ⚠️ WRITE
        monet_data.AdcBackup = (bub_val > 0) ? bub_val : 0;         // ⚠️ WRITE
        monet_data.AdcLi = (li_val > 0) ? li_val : 0;               // ⚠️ WRITE
        monet_data.mcuTemperature = (int16_t)PF_TEMP_RAW_TO_DEGREES(...); // ⚠️ WRITE
        // ... more reads/writes to monet_data.is_adc_paused, monet_data.powerStateMask...
    }
}
```

**Fields written:** `AdcMain`, `AdcBackup`, `AdcLi`, `AdcBatC`, `mcuTemperature`, `powerStateMask`, `bat_voltage`, `bat_voltage_int`
**Fields read:** `is_adc_paused`
**Race partners:** `gpio_irqCallbackFunc` (ISR) writes `AdcMain = 0`. Main loop reads all these ADC values.

### 4.3 TWIS (I2C Slave) ISR Context (HIGH PRIORITY)

#### 4.3.1 `mcu_slave_i2c_write` — camera_i2c.c:244

Triggered via `twi_slave_event_handler` → `TWIS_EVT_WRITE_DONE`:

```c
static void mcu_slave_i2c_write(size_t cnt)
{
    switch(m_rxbuff[0]) {
        case 0x5A: monet_data.is_test_mode = 1; break;               // ⚠️ WRITE
        case 0x5B: monet_data.is_udisk_mode = (m_rxbuff[1] == 1);   // ⚠️ WRITE
                   monet_data.apConnectTimeout = AP_TIMEOUT_DELAY;    // ⚠️ WRITE
        case 0x5D: // mode switch — writes monet_data.is_factory_ap, pir_interval_delay, 
                   // pir_is_valid, apPowerOnTask, apPowerOnDelay, apPowerOffNormally
        case 0x5E: monet_data.is_ota_mode = m_rxbuff[1]; break;     // ⚠️ WRITE
        case 0x5F: monet_data.is_net_scan = m_rxbuff[1]; break;     // ⚠️ WRITE
        case 0x48: monet_data.is_factory_ap = 0;                    // ⚠️ WRITE
                   monet_data.apPowerOnTask = DEV_BOOT_TASK_GO_TO_SLEEP;
                   monet_data.pir_is_enable = 1;
        // ... many more fields modified ...
    }
}
```

**Fields written:** `is_test_mode`, `is_udisk_mode`, `is_ota_mode`, `is_net_scan`, `is_factory_ap`, `apConnectTimeout`, `pir_interval_delay`, `pir_is_valid`, `apPowerOnTask`, `apPowerOnDelay`, `apPowerOffNormally`, `pir_is_enable`, `led_timer_cnt`, `led_effect`
**Race partners:** `check_pyd_interrupt` (main/timer) reads `is_test_mode`, `is_ota_mode`, `is_udisk_mode`, `is_factory_ap`, `pir_is_valid`, `pir_is_enable`. `atel_timerTickHandler` (main) reads `is_factory_ap`.

### 4.4 app_timer Callback Context (LOW PRIORITY, but preempts main loop)

#### 4.4.1 `timer_systick_handler` — platform_hal_drv.c:1260

```c
static void timer_systick_handler(void * p_context)
{
    gTimer++;
    if (1 == monet_data.SleepStateChange) {         // ⚠️ READ in timer ISR
        monet_data.SleepStateChange = 2;             // ⚠️ WRITE in timer ISR
        if(SLEEP_OFF != monet_data.SleepState ...)  // ⚠️ READ in timer ISR
            scan_stop();
    }
    if (SLEEP_OFF == monet_data.SleepState)         // ⚠️ READ
        app_timer_start(pf_systick_timer, APP_TIMER_TICKS(TIME_UNIT_IN_SLEEP_NORMAL), NULL);
    else
        app_timer_start(pf_systick_timer, APP_TIMER_TICKS(TIME_UNIT_IN_SLEEP_HIBERNATION), NULL);
}
```

**Fields read:** `SleepStateChange`, `SleepState`
**Fields written:** `SleepStateChange`
**Race partners:** Main loop writes `SleepStateChange = 1` in `MCU_TurnOff_MDM()`/`pic_turnOnBaseband()`/`pic_turnOffBaseband()`. Main loop also reads these fields throughout.

#### 4.4.2 `pir_check_handler` → `check_pyd_interrupt` — user.c:733/815

```c
static void pir_check_handler(void * p_context)
{
    check_pyd_interrupt();  // full monet_data multi-field access (see §4.5.1)
}
```

**Context note:** `pir_check_start()` in user.c:749 arms this timer only when `SleepState != SLEEP_OFF` and `pir_checking == false`. The timer fires at ~5 ticks into the future while the device is in low-power state. When it fires, `check_pyd_interrupt()` executes inside the timer callback ISR context.

### 4.5 Main Loop Context (THREAD MODE)

#### 4.5.1 `check_pyd_interrupt` — user.c:815 (DUAL-CONTEXT: main loop + timer callback)

Called from **both**:
- `main()` loop at main.c:665 (spin-waits on `pir_is_checking()` first)
- `pir_check_handler` timer callback at user.c:736

```c
void check_pyd_interrupt(void)
{
    pir_checking = true;                              // ✅ volatile flag
    if(pyd_get_status()) {
        pirDetectedTimestamp = count1sec;             // ✅ volatile flag
    
        if (monet_data.appActive)                     // ⚠️ READ (uint8_t)
            ; // log
        
        pir_value = pyd_gpio_reconfig();
        
        if(!pyd_check_first_interrupt()) { ... }
        else {
            if (monet_data.is_factory_ap != 0) {      // ⚠️ READ
                monet_xF2command(pir_value);
            }
            
            if (!device_battery_too_low() 
                && monet_data.is_pir_paused == 0       // ⚠️ READ
                && monet_data.is_ota_mode == 0         // ⚠️ READ
                && extend_data.breaktime == 0) {
                
                if(monet_data.apPowerOn == false        // ⚠️ READ
                   && monet_data.pir_is_enable          // ⚠️ READ
                   && monet_data.pir_is_valid           // ⚠️ READ
                   && monet_work_mode.status != DEV_MODE_SETUP
                   && monet_work_mode.status != DEV_MODE_OFF
                   && monet_data.lte_is_turning_off == 0) {  // ⚠️ READ
                    
                    monet_data.apPowerOnReason = DEV_BOOT_REASON_PIR;  // ⚠️ WRITE
                    monet_data.apPowerOnTask = DEV_BOOT_TASK_NONE;     // ⚠️ WRITE
                    
                    mcu_wakeup_ap_pir();
                    MCU_TurnOn_AP();
                    
                    monet_data.pir_interval_delay = ...;    // ⚠️ WRITE
                    monet_data.pir_is_valid = 0;            // ⚠️ WRITE
                    monet_data.pir_triggered_secs = 0;      // ⚠️ WRITE
                    monet_gpio.Intstatus |= MASK_FOR_BIT(INT_PIR);
                }
                else if(monet_data.is_test_mode == 1        // ⚠️ READ
                        && monet_data.apPowerOn             // ⚠️ READ
                        && monet_data.pir_is_valid          // ⚠️ READ
                        && monet_data.pir_trigger_test_delay == 0) {  // ⚠️ READ
                    monet_data.pir_trigger_test_delay = 2;  // ⚠️ WRITE
                }
            }
        }
    }
    pir_checking = false;                             // ✅ volatile flag
}
```

**Dual-context analysis:** The `pir_checking` flag provides a basic spinlock. In `main()`:
```c
if (pir_is_checking()) {
    nrf_delay_us(1);
    while (pir_is_checking()) nrf_delay_us(1);
}
check_pyd_interrupt();
```

And `pir_check_start()`:
```c
if(monet_data.SleepState != SLEEP_OFF && monet_data.SleepStateChange == 0 
   && pf_systick_remains() > APP_TIMER_TICKS(TIME_UNIT) && !pir_checking) {
    pir_checking = true;
    APP_ERROR_CHECK(app_timer_start(m_pir_check_timer, 5, NULL));
}
```

**Assessment:** The `pir_checking` flag provides re-entrancy protection for `check_pyd_interrupt` itself, but does NOT protect `monet_data` fields from concurrent access by OTHER ISRs (SAADC, GPIOTE, TWIS, BLE SoftDevice callbacks) that run at higher priority.

#### 4.5.2 `atel_timerTickHandler` — platform_hal_drv.c:2544

Called from `main()` loop every `sysTickUnit` (10ms awake, 1s hibernating):

```c
void atel_timerTickHandler(uint32_t tickUnit_ms) {
    // Reads: monet_data.AccChipAdd, monet_data.led_effect, monet_data.is_factory_ap, monet_data.apPowerOn
    // Writes: monet_data.sysRealTimeSeconds (uint32_t)
    // Calls: atel_adc_converion() → triggers SAADC → saadc_callback(ISR) writes AdcMain etc.
    // Calls: device_ble_status_report(), accInterruptHandle(), m_led_timer_handler()
}
```

#### 4.5.3 Other Main-Context Functions

| Function | File | Fields Accessed |
|----------|------|----------------|
| `MCU_TurnOn_AP()` | user.c:978 | RW: `apPowerOn`, `apConnectTimeout`, `apPowerDuration`, `apPowerOffNormally` |
| `MCU_TurnOff_AP()` | user.c:956 | RW: `apPowerOn`, `apConnectTimeout`, `apPowerDuration`, `apPowerOnReason`, `is_adc_paused` |
| `MCU_TurnOff_MDM()` | user.c:999 | RW: `bbofftime`, `SleepState`, `SleepStateChange`, `lte_is_turning_off` |
| `pic_turnOnBaseband()` | system.c:13 | RW: `SleepState`, `SleepStateChange`, `bbPowerOnDelay`, `SleepAlarm`, `bbPowerOffDelay` |
| `pic_turnOffBaseband()` | system.c:40 | RW: `phonePowerOn`, `SleepState`, `SleepStateChange`, `bbPowerOffDelay` |
| `device_uart_alive_handle()` | user.c:910 | RW: `uartAliveDebounce`, `uartAliveCount`, `phonePowerOn`, `SleepState` |
| `device_led_handle()` | user.c:793 | RW: `bat_vol_value`, `lte_sig_level` |
| `pir_set_threshold()` | user.c:765 | RW: `pir_is_enable` |
| `pir_check_start()` | user.c:749 | R: `SleepState`, `SleepStateChange` |
| `ble_recv_queue_process()` | ble_iocmd.c:109 | R: `phonePowerOn`, `appActive`, `txQueueU1.Size` |
| `DeclareBleWakeupApp()` | ble_iocmd.c:478 | R: `SleepState` |
| `monet_Icommand()` | ext_cmd.c:9 | W: `bbPowerOnDelay` |
| `monet_requestAdc()` | ext_cmd.c:43 | R: `AdcMain`, `AdcBackup` |
| `mcu_is_ap_cool()` | camera_power.c:102 | RW: `apPowerOn`, `apCoolTime`, `apPowerDuration`, `is_ota_mode`, `is_net_scan` |
| `sps_switch_bat_low()` | camera_sps.c:237 | W: `bat_switch` |
| `sps_switch_sps_high()` | camera_sps.c:245 | W: `bat_switch` |
| `aw9523_deinit()` | camera_aw9523.c:147 | W: `led_timer_cnt`, `led_effect` |

### 4.6 BLE SoftDevice Event Callbacks (VARIABLE PRIORITY)

BLE callbacks from the SoftDevice run at priority levels granted by `sd_ble_enable()`. These can preempt the main loop and may preempt app_timer callbacks depending on configuration.

| Function | File | Fields Accessed |
|----------|------|----------------|
| BLE data received handler | ble_user.c:219 | R: `SleepState` |
| `ble_recv_queue_process_advanced` | ble_iocmd.c:73 | R: `phonePowerOn`, `appActive` |
| BLE scan event handler (commented out) | ble_user.c:1714 | W: `ble_peer_mac_addr` (commented) |

---

## 5. `check_pyd_interrupt` Dual-Context Execution Analysis

### 5.1 Call Sites

| Call Site | Context | Protection |
|-----------|---------|------------|
| `main()` at main.c:665 | Thread mode | Spin-waits on `pir_checking` flag |
| `pir_check_handler` at user.c:736 | app_timer callback (IRQ) | Sets `pir_checking = true` before arming timer |

### 5.2 Race Window

```
TIME →
─────────────────────────────────────────────────────────────────────
main():                  [spin-wait pir_checking]  [check_pyd_interrupt]
pir_check_start():                                     [sets pir_checking, arms timer]
pir_check_handler():                                             [check_pyd_interrupt]
                              ↑ RACE WINDOW ↑
```

Between `pir_check_start()` setting `pir_checking = true` and the main loop noticing it, there is a narrow window. But more critically:

**The `pir_checking` flag only protects `check_pyd_interrupt` from itself.** All other ISRs (SAADC callback, GPIOTE callback, TWIS callback) can still freely read/write `monet_data` fields while `check_pyd_interrupt` is executing, because they run at higher priority and the flag does not disable interrupts.

### 5.3 Critical Race: TWIS writes during PIR check

When `check_pyd_interrupt` executes in the main loop:
1. It reads `monet_data.is_ota_mode`, `monet_data.is_test_mode`, `monet_data.is_factory_ap`
2. A TWIS interrupt fires (AP sends I2C command `0x5E` = enter OTA mode)
3. `mcu_slave_i2c_write` sets `monet_data.is_ota_mode = 1`
4. `check_pyd_interrupt` continues with stale `is_ota_mode == 0` value
5. PIR triggers AP power-on when it should not (OTA in progress)

---

## 6. Critical Section / Mutex Analysis

### 6.1 Search Results

**Zero critical sections found** in application code that protect `monet_data`:
- `CRITICAL_REGION_ENTER/EXIT`: **Not used anywhere**
- `__disable_irq()/__enable_irq()`: **Not used anywhere**
- `sd_nvic_critical_region_enter/exit`: **Not used in application code**
- Mutex/semaphore: **No RTOS mutex primitives used**

### 6.2 Existing Protection Mechanisms

| Mechanism | Scope | Adequate? |
|-----------|-------|-----------|
| `pir_checking` (volatile bool) | `check_pyd_interrupt` re-entrancy only | ❌ Does not protect against higher-priority ISRs |
| `monet_data.is_adc_paused` flag | ADC sampling gating | ❌ Only gates sample collection, doesn't protect the fields |
| `monet_data.SleepStateChange` mechanism | Sleep state transition handshake | ⚠️ Partial — sequence counter pattern but no memory barrier |

---

## 7. Compiler Optimization Risk Assessment

### 7.1 Non-Volatile Access Hazards

The Cortex-M4 GCC compiler with `-Os` or `-O2` can legally:

1. **Register-cache a read:** If `monet_data.apPowerOn` is read twice in a function, the compiler may cache it in a register and reuse it, missing an ISR update between reads.

   Example from `check_pyd_interrupt`:
   ```c
   if(monet_data.apPowerOn == false && ...) {  // read #1
       // TWIS ISR fires here, could toggle is_ota_mode
       if(monet_data.is_ota_mode == 0) {       // read #2 — may use stale value
   ```

2. **Dead-store elimination:** A write to `monet_data` in an ISR that the compiler proves is only read in an ISR could be eliminated entirely if the compiler doesn't see the cross-context read.

   Example: `gpio_irqCallbackFunc` writes `monet_data.AdcMain = 0`. If the compiler inlines and analyzes the call graph, it might determine the write has no visible effect (since the SAADC callback overwrites it later) and eliminate it.

3. **Store merging/reordering:** Multiple adjacent writes to `monet_data` fields can be reordered or merged.

   Example from `MCU_TurnOn_AP`:
   ```c
   monet_data.apPowerOn = true;
   monet_data.apConnectTimeout = AP_TIMEOUT_DELAY;
   monet_data.apPowerDuration = 0;
   monet_data.apPowerOffNormally = false;
   ```
   These may be written in any order from the perspective of an ISR reading `apPowerOn` to decide whether to proceed.

4. **Read-tearing on multi-byte members:** Fields like `uint32_t bbofftime`, `uint32_t SleepAlarm`, `uint32_t sysRealTimeSeconds` are not guaranteed to be read atomically. On Cortex-M4, aligned 32-bit reads are atomic, but:
   - `uint16_t` fields on odd-byte boundaries within the packed struct are NOT atomic
   - The compiler may split a 32-bit read into two 16-bit reads if targeting Thumb-2

### 7.2 Struct-Level Risk

The `monet_struct` contains `#pragma pack`-affected nested types (`IoRxFrameStruct`) and multi-byte buffers (`atel_ring_buff_t txQueueU1`). The struct is NOT marked `__attribute__((packed))` but nested types may force misalignment of subsequent members, increasing the risk of non-atomic access.

### 7.3 Optimization Level

The project likely compiles with `-Os` (size-optimized, typical for nRF52 bare-metal). This enables all of the above hazards. The `-O0` case would be safer but is not used in production firmware.

---

## 8. Specific Hazard Scenarios

### Scenario 1: Stale PIR detection during mode change (HIGH)

```
1. Main loop: check_pyd_interrupt() reads monet_data.is_ota_mode == 0
2. TWIS ISR: AP sends "enter OTA" → mcu_slave_i2c_write sets monet_data.is_ota_mode = 1
3. Main loop: check_pyd_interrupt() continues, sees is_ota_mode == 0 (stale)
4. PIR wakeup triggers AP power-on during OTA → potential flash corruption
```

### Scenario 2: ADC value corruption (MEDIUM)

```
1. SAADC ISR: saadc_callback computes main_val, writes monet_data.AdcMain = 1234
2. GPIOTE ISR: gpio_irqCallbackFunc fires, writes monet_data.AdcMain = 0 (SPS removed)
3. Main loop: monet_requestAdc() reads monet_data.AdcMain = 0 → reports zero voltage
4. Or: compiler reorders store → main loop reads half-updated 16-bit value
```

### Scenario 3: Sleep state inconsistency (HIGH)

```
1. main loop: MCU_TurnOff_MDM() sets monet_data.SleepStateChange = 1, then monet_data.SleepState = SLEEP_HIBERNATE
2. timer_systick_handler ISR: sees SleepStateChange == 1, writes SleepStateChange = 2
3. main loop: MCU_TurnOff_MDM() continues, expects SleepStateChange == 1 for its handshake
   → state machine confusion, potential watchdog reset
```

### Scenario 4: Compiler eliminates ISR write (LOW-MEDIUM)

```
1. saadc_callback writes monet_data.AdcMain = computed_value
2. Compiler with LTO (link-time optimization) sees that AdcMain is overwritten
   every SAADC cycle and the only reader is in main loop context
3. Compiler may optimize: treat AdcMain as "last writer wins" and reorder
4. If main loop read gets hoisted before SAADC completion, reads stale value
```

---

## 9. Remediation Recommendations

### 9.1 Immediate (Critical)

**Make `monet_data` volatile:**
```c
// user.c
volatile monet_struct monet_data = {{(IoCmdState)0}};

// user.h
extern volatile monet_struct monet_data;
```

**Impact:** Forces every access to go through memory (no register caching). This eliminates the compiler optimization hazards but adds ~1-2 cycles per access. Given that `monet_data` is accessed pervasively, expect a small code size increase (~5-10% larger) and slight performance impact.

**Why not per-field volatile:** 155 members. Per-field annotation is error-prone to maintain. Struct-level `volatile` is the pragmatic solution.

### 9.2 Short-term (High Priority)

**Add critical sections around multi-field write sequences:**

```c
void MCU_TurnOn_AP(void) {
    CRITICAL_REGION_ENTER();
    monet_data.apPowerOn = true;
    monet_data.apConnectTimeout = AP_TIMEOUT_DELAY;
    monet_data.apPowerDuration = 0;
    monet_data.apPowerOffNormally = false;
    CRITICAL_REGION_EXIT();
}
```

Applies to: `MCU_TurnOn_AP`, `MCU_TurnOff_AP`, `MCU_TurnOff_MDM`, `check_pyd_interrupt` (PIR wakeup block), `mcu_slave_i2c_write` (mode-change sequences).

**Note:** `CRITICAL_REGION_ENTER/EXIT` affects only priority levels up to APP_IRQ_PRIORITY_LOW. For GPIOTE/SAADC-level ISRs, use `__disable_irq()/__enable_irq()` or `sd_nvic_critical_region_enter/exit`.

### 9.3 Medium-term

**Use atomic primitives for multi-byte fields:**
- Replace `volatile uint32_t` counters with atomic operations
- Use `__LDREX/__STREX` for Cortex-M4 load-linked/store-conditional

### 9.4 Structural

**Consider data ownership model:**
- ISR-owned fields (ADC values) → only ISRs write, main loop only reads after flag
- Main-owned fields (mode flags) → only main loop writes, ISRs only read
- Shared state → use proper atomic or locked access

---

## 10. Cross-Track Implications

### 10.1 T1→T2 (GPIOTE Slot Exhaustion → Volatile Race)

T1 found that PIR dynamic SENSE re-registration consumes GPIOTE slots. The `gpiote_event_handler` in camera_pyd1598.c runs in GPIOTE ISR context. If the PIR GPIO pin is dynamically reconfigured (as T1 describes), additional GPIOTE handlers may fire during `monet_data` access windows, compounding the race surface.

### 10.2 T2→T3 (Volatile Race → Memory Management / Synchronization)

Track 3 is expected to cover heap/stack analysis, mutex/synchronization primitives, interrupt latency, and memory management. The `monet_data` volatile race findings have direct and cascading implications for all of these domains.

#### 10.2.1 Heap Corruption via monet_data-Controlled Allocation

Several `monet_data` fields influence dynamic routing and mode decisions that in turn affect memory allocation patterns:

| Field | Allocation Impact | Race Hazard |
|-------|------------------|-------------|
| `is_ota_mode` | Controls whether OTA buffers are allocated | Stale read → allocation in wrong mode → leak or double-free |
| `is_udisk_mode` | USB mass-storage buffer reservation | Race with TWIS ISR write → buffer sizing mismatch |
| `apPowerOn` | Triggers AP communication path allocation | Stale false → allocation skipped → null-deref on AP path |
| `is_factory_ap` | Factory-reset allocation path | Race-driven wrong path → stale pointers |
| `txQueueU1` (ring buffer) | Embedded `atel_ring_buff_t` with size/capacity fields | Corrupted size field from partial ISR write → buffer overflow/underflow |

**Forward-looking recommendation for Track 3:** Any analysis of heap allocation call sites must account for the fact that the deciding `monet_data` fields can change mid-decision due to ISR preemption. A static call-graph analysis that assumes `is_ota_mode` is stable across a function's execution is invalid — the compiler may also register-cache it across function boundaries (see §7.1).

#### 10.2.2 Stack Depth Under Interrupt Nesting with Corrupted State

The five execution contexts (§3) nest arbitrarily. The worst-case nesting chain:

```
Main loop → app_timer ISR (RTC2) → SAADC ISR → GPIOTE ISR → HardFault
```

When `monet_data` state fields are corrupted by race conditions:

- **Wrong-mode code paths:** If `check_pyd_interrupt` reads stale `is_ota_mode == 0` and triggers AP power-on during an OTA session, the AP communication stack (BLE GATT operations, UART buffering) pushes additional stack frames that were not budgeted for the current mode.
- **Re-entrancy through corrupted flags:** The `pir_checking` spinlock only protects against self-re-entrancy. If `SleepState` is read as `SLEEP_OFF` when the device is actually hibernating, `pir_check_start()` arms the PIR check timer, injecting an app_timer callback into a stack context that may already be near its limit.
- **SAADC callback depth:** `atel_timerTickHandler` (main loop) triggers SAADC sampling via `atel_adc_conversion()`. If `monet_data.is_adc_paused` is read as false when it should be true (race with `MCU_TurnOff_AP` writing it), the SAADC ISR fires and deepens the stack at an unexpected point.

**Forward-looking recommendation for Track 3:** Stack depth analysis must model not just the static call tree but the dynamic path variability introduced by corrupted `monet_data` reads. The remediation proposed in §9.1 (struct-level `volatile`) eliminates the compiler-optimization source of corruption but does not eliminate the logical races — two ISRs can still interleave writes to the same field. Track 3 should instrument worst-case stack depth with `__get_MSP()` probes at each ISR entry and exit, running with and without the `volatile` fix to quantify the delta.

#### 10.2.3 Synchronization Primitive Interactions

Track 2 found **zero critical sections or mutexes** protecting `monet_data` (§6.1). The only synchronization mechanisms in play are:

| Mechanism | Type | Track 3 Relevance |
|-----------|------|-------------------|
| `pir_checking` (volatile bool) | Hand-rolled spinlock | One-shot re-entrancy guard — Track 3 should evaluate whether this pattern is used elsewhere and whether it's correct under the C11 memory model on Cortex-M4 |
| `SleepStateChange` sequence | Hand-rolled two-phase handshake (1→2 pattern) | Track 3 should analyze this as a synchronization primitive. Without memory barriers, the compiler and CPU can reorder the `SleepStateChange` write relative to the `SleepState` write. On Cortex-M4 with `-Os`, a `DMB` instruction is required between the two stores to guarantee ordering to the `timer_systick_handler` observer. |
| `is_adc_paused` flag | Simple gating boolean | Same volatile-race vulnerability as all other monet_data fields. Track 3 should verify whether any gating flags in the system are correctly declared `volatile`. |

**Critical question for Track 3:** If Track 2's recommended remediation (§9.2) introduces `CRITICAL_REGION_ENTER/EXIT` (which maps to `__disable_irq()/__enable_irq()` at APP_IRQ_PRIORITY_LOW), what is the worst-case interrupt latency increase? The answer depends on the maximum time spent inside each critical section. Track 3 should measure or model:

- `check_pyd_interrupt` critical section duration (currently unbounded — contains I2C/GPIO operations)
- `MCU_TurnOn_AP` critical section duration (~100-200 µs estimated for register writes)
- `mcu_slave_i2c_write` critical section duration (multi-byte I2C transfer, potentially hundreds of µs)

If any of these exceed the SoftDevice's real-time constraints (~100 µs for BLE connection events), `sd_nvic_critical_region_enter/exit` (which defers rather than disables SoftDevice interrupts) must be used instead of raw `__disable_irq()`.

#### 10.2.4 Non-Atomic Multi-Byte Access and Memory Ordering

The `monet_struct` contains multi-byte members accessed from multiple contexts (§7.1, point 4):

- `uint32_t bbofftime` — written in main loop (`MCU_TurnOff_MDM`), read in SoftDevice BLE callback
- `uint32_t SleepAlarm` — written in main loop, read in app_timer callback
- `uint32_t sysRealTimeSeconds` — written in `atel_timerTickHandler` (main), read in BLE context
- `uint16_t AdcMain`, `AdcBackup`, `AdcLi`, `AdcBatC` — written in SAADC ISR, written in GPIOTE ISR, read in main loop

While Cortex-M4 guarantees atomicity for aligned 32-bit loads/stores, the struct's internal alignment (influenced by nested packed types like `IoRxFrameStruct`) may misalign subsequent members. Track 3 should verify struct member alignment via `__attribute__((aligned(4)))` assertions or linker-map inspection.

**Forward-looking recommendation for Track 3:** Even with `volatile`, the compiler does not guarantee atomicity of multi-byte accesses. If Track 3 finds that any `uint32_t` field is accessed from both ISR and main-loop contexts, it must be protected with `__LDREX/__STREX` (load-linked/store-conditional) or moved to a critical-section-guarded access pattern. A plain `volatile uint32_t` read can tear on misaligned boundaries or under specific Thumb-2 instruction sequences.

### 10.3 T2→T5 (Volatile Race → Stack/Control Flow)

The volatile race in `monet_data.apPowerOn`, `SleepState`, and mode flags directly feeds into T5's analysis of system state machine transitions. Incorrect state reads can cause:
- Premature AP power-on → unexpected stack depth
- Missed sleep transitions → stale state machine decisions
- Wrong mode execution paths → untested code paths

### 10.4 T2→T6 (Volatile Race → Robustness/Recovery)

Race-induced state corruption can lead to watchdog resets (the only recovery mechanism per T1). If `monet_data.apPowerOn` is read as true when AP is actually off, the system enters an inconsistent state that may only be recoverable via `NVIC_SystemReset`.

---

## 11. Appendix: File List

All GA02 files accessing `monet_data` (non-comment, dot-notation access):

| File | Access Count | Primary Context |
|------|-------------|-----------------|
| `user.c` | 481 | Main loop + timer callback |
| `platform_hal_drv.c` | 84 | Main loop + SAADC ISR + timer ISR |
| `system.c` | 30 | Main loop |
| `camera_i2c.c` | 28 | TWIS ISR |
| `ble/ble_iocmd.c` | 25 | Main loop + BLE SoftDevice callback |
| `ext_cmd.c` | 19 | Main loop |
| `camera_power.c` | 19 | Main loop |
| `main.c` | 12 | Main loop |
| `ble/ble_user.c` | 8 | BLE SoftDevice callbacks |
| `ble/ble_dfu_cb.c` | 4 | Main loop |
| `ble/ble_advanced.c` | 4 | BLE SoftDevice callbacks |
| `camera_sps.c` | 3 | GPIOTE ISR + main loop |
| `camera_aw9523.c` | 2 | Main loop |
| `ble/ble_beacon_sensor.c` | 1 | BLE SoftDevice callbacks |

**Total:** ~722 accesses across 14 files.

---

*End of Track 2 analysis.*
