# Track 4 — Sleep/Wake GPIOTE Reconfig (Gen4)

**Project:** Gen4 PIR Investigation — GA02-IrbisMcu (nRF52832 + S132 SoftDevice, nrfx SDK v15.x)
**Date:** 2026-05-28
**Branch:** `pir-analysis-gen4`

---

## 1. Executive Summary

**Verdict: LOW-MEDIUM RISK (sleep itself), MEDIUM RISK (PIR GPIOTE reconfig window).**

The system uses **System ON sleep** via `sd_app_evt_wait()` (WFE-based), never System OFF. All peripheral state — including GPIOTE channel allocation, RTC1 timing, and GPIO SENSE — is preserved across sleep/wake transitions. There is **no GPIOTE re-initialization on wake** from System ON sleep. The primary sleep/wake hazard is NOT in the sleep mechanism itself, but in the **PIR sensor's GPIOTE disable→re-enable cycle** (`pyd_gpio_reconfig()`) which executes on every PIR interrupt and creates a vulnerable window where PIR transitions can be permanently lost.

**Key findings:**
- No FreeRTOS — bare-metal loop with `nrf_pwr_mgmt_run()` → `sd_app_evt_wait()`
- No System OFF used — `pf_enter_deep_sleep()` is a modem-sleep no-op for the MCU
- GPIOTE state persists across all sleep/wake cycles (System ON preserves peripheral config)
- app_timer uses RTC1 (16384 Hz), SoftDevice owns RTC0 — no direct RTC conflict
- `NRF_SDH_DISPATCH_MODEL = INTERRUPT` — BLE observer chain runs in soft-interrupt context before main loop resumes, creating a narrow re-entrancy window with `monet_data`
- PIR GPIOTE reconfig (`pyd_gpio_reconfig`) creates a ~150µs+ dead zone on every PIR event

---

## 2. Sleep Architecture

### 2.1 Sleep Entry Path

**File:** `GA02/application/main.c:355-364`

```c
static void idle_state_handle(void)
{
    if (NRF_LOG_PROCESS() == false)
    {
        if ((monet_data.phonePowerOn == 0) || (monet_data.SleepState == SLEEP_NORMAL))
        {
            nrf_pwr_mgmt_run();
        }
    }
}
```

**Sleep entry chain:**
```
main loop → idle_state_handle() → nrf_pwr_mgmt_run() → sd_app_evt_wait() → __WFE (in SoftDevice SVC)
```

**Sleep gate conditions (BOTH must be true):**
1. `NRF_LOG_PROCESS() == false` — no pending log data to flush
2. `monet_data.phonePowerOn == 0` OR `monet_data.SleepState == SLEEP_NORMAL`

**When sleep is skipped:**
- Log data pending (UART-backed log flushing takes priority)
- Phone powered on AND sleep state is SLEEP_OFF or SLEEP_HIBERNATE
- `SleepStateChange != 0` during sleep-state transitions (HIBERNATE→NORMAL→OFF)

### 2.2 `nrf_pwr_mgmt_run()` Internals

**File:** `components/libraries/pwr_mgmt/nrf_pwr_mgmt.c:340-368`

```c
void nrf_pwr_mgmt_run(void)
{
    PWR_MGMT_FPU_SLEEP_PREPARE();
    PWR_MGMT_SLEEP_LOCK_ACQUIRE();
    PWR_MGMT_CPU_USAGE_MONITOR_SECTION_ENTER();
    PWR_MGMT_DEBUG_PIN_SET();

#ifdef SOFTDEVICE_PRESENT
    if (nrf_sdh_is_enabled())
    {
        ret_code_t ret_code = sd_app_evt_wait();
        ASSERT((ret_code == NRF_SUCCESS) || (ret_code == NRF_ERROR_SOFTDEVICE_NOT_ENABLED));
    }
    else
#endif
    {
        __WFE();
        __SEV();
        __WFE();
    }

    PWR_MGMT_DEBUG_PIN_CLEAR();
    PWR_MGMT_CPU_USAGE_MONITOR_SECTION_EXIT();
    PWR_MGMT_SLEEP_LOCK_RELEASE();
}
```

With SoftDevice present (this project): `sd_app_evt_wait()` is called. This is a **supervisor call (SVC)** into the SoftDevice that:
1. Issues `__WFE` to put the CPU into sleep (System ON mode)
2. Returns when any interrupt wakes the CPU
3. **All peripheral state (GPIOTE channels, RTC, GPIO SENSE, NVIC) is preserved across this call**

Without SoftDevice: standard `__WFE(); __SEV(); __WFE();` sequence to clear the event register.

### 2.3 Sleep State Machine

**File:** `GA02/application/lib/user.h:289-291`

```c
typedef enum {
    SLEEP_OFF,          // Full operation, 10ms system tick
    SLEEP_NORMAL,       // Normal sleep mode, 10ms tick, idle sleep allowed
    SLEEP_HIBERNATE,    // Hibernate mode, 1000ms tick, idle sleep allowed
} SleepState_e;
```

**State transition mechanism** (via `monet_data.SleepStateChange`):
1. App sets `SleepState` to new value and `SleepStateChange = 1`
2. `pf_systick_change()` detects `SleepStateChange == 1`, sets it to 2, reconfigures timer
3. `pf_systick_change()` detects `SleepStateChange == 2`, adjusts `sysTickUnit`, sets to 0
4. Main loop condition `(monet_data.SleepStateChange == 0)` re-enables `idle_state_handle()`

**During the transition (`SleepStateChange != 0`):**
- `idle_state_handle()` is **skipped** — the MCU does NOT sleep
- This blocks WFE-based sleep for up to one full main-loop iteration
- All other loop processing (BLE, PIR check, queue processing) continues

**File:** `GA02/application/main.c:626-638`
```c
for (;;)
{
    if (extend_data.in_deep_sleep == 2)
    {
        pf_enter_deep_sleep();
    } else if (
#if TIME_UNIT_CHANGE_WHEN_SLEEP
        (monet_data.SleepStateChange == 0)
#endif
    ) {
        idle_state_handle();
    }
    // ... queue processing, timer ticks, PIR check, BLE processing ...
}
```

---

## 3. System ON vs System OFF

### 3.1 System ON (Used Exclusively)

The system operates **entirely in System ON mode**. `sd_app_evt_wait()` puts the CPU core into WFE sleep while:
- All RAM is retained
- All peripherals remain powered and clocked
- RTC1 continues counting (if started)
- GPIOTE channels remain configured and active
- GPIO SENSE/LATCH remains active
- BLE SoftDevice timeslot engine continues running

**Wake sources:**
| Source | Mechanism | Effect |
|--------|-----------|--------|
| GPIOTE PORT event | PIR_OUT toggles → PORT event → GPIOTE_IRQn | CPU wakes, ISR runs, GPIOTE handler dispatches |
| RTC1 COMPARE0 | app_timer fires → RTC1_IRQn | CPU wakes, timer callback executes |
| BLE SoftDevice events | Connection event, advertising event, GATT write | SD_EVT_IRQHandler → observer chain |
| UART RX | UART FIFO triggers interrupt | CPU wakes, UART ISR processes received byte |
| GPIO PORT (SENSE) | Any SENSE-configured pin changes | CPU wakes |

### 3.2 System OFF (NOT Used)

**File:** `GA02/application/platform_hal_drv.c:2055-2062`

```c
void pf_enter_deep_sleep(void)
{
#ifdef PM_SUPPORT_VIA_I2C
    tbp_data.test_payload[0] = TBP_I2C_CMD_TRANSPORT;
    tbp_data.test_payload[1] = 1;
    tbp_data.toRead = 1;
#endif
}
```

**`pf_enter_deep_sleep()` is a NO-OP for the MCU.** It does NOT:
- Enter System OFF mode
- Call `sd_power_system_off()`
- Disable any peripherals
- Clear RAM

All it does is queue a TBP I2C command to notify the companion PM chip that transport (modem) is entering deep sleep. The MCU itself continues running the main loop — it just skips BLE and modem processing because `in_deep_sleep == 2` short-circuits to the no-op.

**The deep sleep flow:**
1. External command sets `extend_data.in_deep_sleep = 1` (ext_cmd.c:226)
2. Modem power-off timer fires → `pf_mdm_pwr_off()` sets `in_deep_sleep = 2` (platform_hal_drv.c:2104)
3. Main loop sees `in_deep_sleep == 2`, calls `pf_enter_deep_sleep()` (no-op), then repeats
4. The MCU never enters System OFF — it spins calling the no-op

**Finding: No System OFF RAM corruption risk.** Errata [74] (RAM retention in System OFF) and [84] (RTC spurious after System OFF) are **NOT APPLICABLE** to this codebase.

---

## 4. GPIOTE State Across Sleep/Wake

### 4.1 GPIOTE Initialization (One-Time)

**File:** `GA02/application/main.c:541-549`

```c
if (!nrfx_gpiote_is_init()) {
    if (nrfx_gpiote_init() != NRF_SUCCESS) {
#if (BLE_FUNCTION_ONOFF == BLE_FUNCTION_OFF)
        NRF_LOG_RAW_INFO("nrfx_gpiote_init fail.\r");
        NRF_LOG_FLUSH();
#endif
    }
}
```

`nrfx_gpiote_init()` is called **exactly once** at startup, inside `main()` after BLE stack init. The `nrfx_gpiote_is_init()` guard prevents re-initialization. The init:
- Clears all pin-in-use flags
- Frees all GPIOTE channels (8 IN/OUT channels + low-power events)
- Sets GPIOTE_IRQn priority to 6
- Enables PORT event interrupts
- Sets driver state to INITIALIZED

**This state persists across ALL `sd_app_evt_wait()` sleep cycles.** There is no `nrfx_gpiote_uninit()` call anywhere in the main loop or power management code.

### 4.2 PIR GPIOTE Reconfiguration (Per-Interrupt)

**File:** `GA02/application/camera_pyd1598.c:198-251`

```c
void pyd_gpio_in_enable(void)
{
    nrf_drv_gpiote_in_config_t config = GPIOTE_CONFIG_IN_SENSE_TOGGLE(false);
    config.pull = NRF_GPIO_PIN_NOPULL;
    err_code = nrf_drv_gpiote_in_init(PIR_OUT, &config, gpiote_event_handler);
    nrf_drv_gpiote_in_event_enable(PIR_OUT, true);
}

void pyd_gpio_in_disable(void)
{
    nrf_drv_gpiote_in_event_disable(PIR_OUT);
    nrfx_gpiote_in_uninit(PIR_OUT);
}

int32_t pyd_gpio_reconfig(void)
{
    int32_t pyd_value = 0;
    pyd_gpio_in_disable();          // (1) Disable events + uninit channel
    pyd_value = pyd_gpio_read_value();  // (2) Bit-bang read (~150µs dead zone)
    pyd_gpio_out_low();             // (3) Pull PIR_OUT low
    pyd_gpio_in_enable();           // (4) Re-init channel + enable events
    return pyd_value;
}
```

**This re-configuration happens on EVERY PIR interrupt** (called from `gpiote_event_handler` in camera_pyd1598.c line ~140).

**Dead-zone analysis:**
1. `pyd_gpio_in_disable()` — GPIOTE channel uninitialized, PORT event latch cleared
2. `pyd_gpio_read_value()` — bit-banged I2C-like protocol over PIR_OUT GPIO, ~150µs
3. `pyd_gpio_out_low()` — pin reconfigured as output driven low
4. `pyd_gpio_in_enable()` — GPIOTE channel re-allocated, event detection re-armed

**During steps 1-4 (total ~200µs+), PIR_OUT transitions are SILENTLY LOST.** The GPIOTE channel is either uninitialized or in the process of re-initialization. Combined with Errata 89 (PORT event can be missed during reconfiguration), this creates a confirmed event-loss path.

**This is NOT a sleep/wake issue — it's an every-interrupt issue.** The PIR sensor interrupts, the GPIOTE is disabled for reconfiguration, and during that window the sensor could produce another transition that goes undetected.

---

## 5. Tickless Idle + app_timer RTC Analysis

### 5.1 No FreeRTOS Tickless Idle

**Confirmed: No RTOS present.** There is no `FreeRTOSConfig.h`, no `vPortSuppressTicksAndSleep`, no `configUSE_TICKLESS_IDLE`. The system uses bare-metal cooperative multitasking with a main loop and interrupt-driven event handling.

### 5.2 app_timer Architecture

**File:** `components/libraries/timer/app_timer.c:163`

```c
static void rtc1_init(uint32_t prescaler)
{
    NRF_RTC1->PRESCALER = prescaler;
    NVIC_SetPriority(RTC1_IRQn, RTC1_IRQ_PRI);
}
```

**RTC configuration:**
| Parameter | Value | Meaning |
|-----------|-------|---------|
| `APP_TIMER_CONFIG_RTC_FREQUENCY` | 1 | 32768/(1+1) = **16384 Hz** |
| `APP_TIMER_CONFIG_IRQ_PRIORITY` | 6 | Same as GPIOTE, SAADC |
| `APP_TIMER_CONFIG_OP_QUEUE_SIZE` | 10 | Max 10 concurrent timer ops |
| `APP_TIMER_CONFIG_USE_SCHEDULER` | 0 | No scheduler deferral — callbacks run in interrupt context |
| `APP_TIMER_KEEPS_RTC_ACTIVE` | 0 | RTC1 stops when no timers active |

### 5.3 RTC1 Stop/Start Behavior

Because `APP_TIMER_KEEPS_RTC_ACTIVE == 0`:

```c
static void rtc1_start(void)
{
    NRF_RTC1->EVTENSET = RTC_EVTEN_COMPARE0_Msk;
    NRF_RTC1->INTENSET = RTC_INTENSET_COMPARE0_Msk;
    NVIC_ClearPendingIRQ(RTC1_IRQn);
    NVIC_EnableIRQ(RTC1_IRQn);
    NRF_RTC1->TASKS_START = 1;
    m_rtc1_running = true;
}

static void rtc1_stop(void)
{
    NVIC_DisableIRQ(RTC1_IRQn);
    NRF_RTC1->EVTENCLR = RTC_EVTEN_COMPARE0_Msk;
    NRF_RTC1->INTENCLR = RTC_INTENSET_COMPARE0_Msk;
    NRF_RTC1->TASKS_STOP = 1;
    NRF_RTC1->TASKS_CLEAR = 1;
    m_ticks_latest = 0;
    m_rtc1_running = false;
}
```

**Implication:** When all app_timer instances are stopped, RTC1 is stopped and its counter is cleared. The next `app_timer_start()` re-initializes RTC1 from zero. This means:
- **No drift accumulation:** RTC1 counter is always relative to the most recent timer start
- **No absolute timekeeping:** RTC1 cannot serve as a system uptime clock
- **Timer precision at 16384 Hz:** ~61µs tick resolution

### 5.4 System Tick Timer (`pf_systick_timer`)

**File:** `GA02/application/platform_hal_drv.c:1314-1321`

The system tick uses a dynamically configured `pf_systick_timer`:

```c
ret = app_timer_create(&pf_systick_timer, APP_TIMER_MODE_SINGLE_SHOT, timer_systick_handler);
// OR
ret = app_timer_create(&pf_systick_timer, APP_TIMER_MODE_REPEATED, timer_systick_handler);

ret = app_timer_start(pf_systick_timer, APP_TIMER_TICKS(period_ms), NULL);
```

**Tick rates per sleep state:**
| Sleep State | Tick Period | Behavior |
|-------------|-------------|----------|
| `SLEEP_OFF` | `TIME_UNIT` (10ms) | Full-speed operation, `APP_TIMER_MODE_REPEATED` |
| `SLEEP_NORMAL` | `TIME_UNIT_IN_SLEEP_NORMAL = TIME_UNIT` (10ms) | Same rate but idle sleep allowed |
| `SLEEP_HIBERNATE` | `TIME_UNIT_IN_SLEEP_HIBERNATION` (1000ms) | Reduced tick, `APP_TIMER_MODE_SINGLE_SHOT` |

### 5.5 RTC Conflict Analysis (SoftDevice RTC0 vs app_timer RTC1)

| RTC Instance | Owner | Usage |
|-------------|-------|-------|
| RTC0 | S132 SoftDevice | BLE connection timing, advertising intervals, timeslot scheduling |
| RTC1 | app_timer library | Application timers (system tick, LED timer, PIR check timer, debounce, modem timeout) |
| RTC2 | Unused | Available |

**No direct RTC resource conflict.** RTC0 and RTC1 are independent hardware instances with separate clocks, prescalers, and compare registers.

**Indirect timing concern:** RTC0 (SoftDevice) and RTC1 (app_timer) both derive from the same 32.768 kHz LFCLK, but RTC1 has a prescaler of 1 (16.384 kHz effective) while RTC0 is configured by the SoftDevice. BLE connection events scheduled by RTC0 may time differently than app_timer callbacks scheduled by RTC1.

**Potential jitter:** If RTC1 is stopped/started while a BLE connection event is pending, the app_timer callback could fire during the BLE event window. With `APP_TIMER_CONFIG_USE_SCHEDULER = 0`, the callback runs in interrupt context (priority 6), which **cannot preempt** the SoftDevice's higher-priority BLE handlers (priority 0, 2, 4). This means app_timer callbacks can be delayed by BLE processing.

---

## 6. BLE Event Wake Interaction

### 6.1 SoftDevice Dispatch Model

**File:** `GA02/application/pca10040/s132/config/sdk_config.h:12109-12110`

```c
#define NRF_SDH_DISPATCH_MODEL 0   // NRF_SDH_DISPATCH_MODEL_INTERRUPT
```

With `NRF_SDH_DISPATCH_MODEL_INTERRUPT`:

```
sd_app_evt_wait() called
  → SoftDevice issues __WFE
  → [CPU sleeps in System ON]
  → Any interrupt fires (GPIOTE, RTC1, BLE event, UART)
  → CPU wakes
  → If interrupt is SD_EVT_IRQ (SoftDevice event):
       → SD_EVT_IRQHandler() runs (priority 2 or 4, in SoftDevice)
       → nrf_sdh_evts_poll() dispatches to stack observers + BLE observers
       → ble_evt_handler() runs IN INTERRUPT CONTEXT
       → [BLE event fully processed before sd_app_evt_wait returns]
  → sd_app_evt_wait() returns to nrf_pwr_mgmt_run()
  → Returns to idle_state_handle()
  → Returns to main loop
```

**File:** `components/softdevice/common/nrf_sdh.c:363-368`

```c
#if (NRF_SDH_DISPATCH_MODEL == NRF_SDH_DISPATCH_MODEL_INTERRUPT)
void SD_EVT_IRQHandler(void)
{
    nrf_sdh_evts_poll();
}
#endif
```

### 6.2 BLE Observer Chain

**File:** `GA02/application/main.c:261`

```c
NRF_SDH_BLE_OBSERVER(m_ble_observer, APP_BLE_OBSERVER_PRIO, ble_evt_handler, NULL);
```

The `ble_evt_handler` is registered as a BLE observer. It runs when `nrf_sdh_evts_poll()` iterates through the `sdh_ble_observers` section. This happens **inside** `sd_app_evt_wait()`, before control returns to the main loop.

### 6.3 Re-entrancy Hazard with monet_data

**The BLE observer chain (`ble_evt_handler`) executes in soft-interrupt context while the main loop was mid-iteration:**

```
Main loop iteration N:
  atel_io_queue_process();     // reads monet_data members
  atel_timerTickHandler();     // reads/writes monet_data members
  check_pyd_interrupt();       // reads monet_data.SleepState, .pir_report_on
  → idle_state_handle()
    → sd_app_evt_wait()
      → BLE connection event fires
      → SD_EVT_IRQHandler() 
        → ble_evt_handler()    // MODIFIES monet_data members!
      → sd_app_evt_wait() returns
    → nrf_pwr_mgmt_run() returns
  → Next iteration starts with ble_evt_handler's changes
  CheckInterrupt();            // sees modified monet_data
```

**Specific `monet_data` fields modified in `ble_evt_handler` call chain:**
- `ble_info.bleConnectionStatus`
- `ble_info.scan_on`
- `monet_data.phonePowerOn` (indirectly via connection management)
- `ble_info.ble_enable_adv`

**Risk assessment:** The BLE observer runs to completion during `sd_app_evt_wait()`. While it's technically "re-entrant" relative to the main loop, the main loop is suspended inside the SVC call — it's not preempted mid-instruction. The hazard is **logical**: the main loop iteration may have read `monet_data` state before sleep, then the BLE handler modifies it during sleep, and the main loop continues with stale reads from before the modification.

**This is the same class of hazard identified in Track 2 (volatile race) and Track 3 (re-entrancy)** — the main loop reads `monet_data` members that can be modified between loop iterations by interrupt-context handlers.

---

## 7. Sleep/Wake Timing Analysis

### 7.1 WFE Wake Latency

For `sd_app_evt_wait()` on nRF52832:
- **Interrupt latency:** ~12 CPU cycles (at 64 MHz = ~188ns) to vector to ISR
- **SVC exit overhead:** Additional ~20-30 cycles for SVC return
- **Total wake-to-first-instruction:** ~500ns-1µs

This is negligible for the PIR sensor which operates on millisecond timescales.

### 7.2 Sleep Skip Scenarios

Sleep is skipped (CPU spins in main loop without WFE) when:
1. **Log data pending** (`NRF_LOG_PROCESS() != false`) — log flushing takes priority
2. **Phone powered on during SLEEP_OFF or SLEEP_HIBERNATE** — UART communication ongoing
3. **`SleepStateChange != 0`** — sleep state transition in progress

During these periods, the main loop runs continuously (busy-wait style), processing all handlers at full speed.

---

## 8. Cross-Track Intersections

### 8.1 T4 → T1 (Slot Exhaustion)

The GPIOTE channel allocation for PIR_OUT is dynamically managed by `nrfx_gpiote_in_init()` / `nrfx_gpiote_in_uninit()`. The `pyd_gpio_reconfig()` cycle deallocates and reallocates the GPIOTE channel on every PIR interrupt. If the channel allocation/deallocation interacts with the SENSE-to-channel mapping analyzed in Track 1, the PIR_OUT slot could be silently dropped during reconfiguration.

### 8.2 T4 → T2 (Volatile Race)

`monet_data.SleepState`, `monet_data.phonePowerOn`, and `monet_data.SleepStateChange` are all non-volatile members of `monet_data` accessed from:
- Main loop (reads `SleepState`, `phonePowerOn`)
- `pf_systick_change()` app_timer callback (reads/writes `SleepStateChange`)
- `pf_mdm_pwr_off()` app_timer callback (writes `phonePowerOn`, `in_deep_sleep`)

Compiler optimization can cache these values in registers across `sd_app_evt_wait()` calls, causing stale reads after wake. The Track 2 finding applies directly: these fields need `volatile` qualification or atomic access.

### 8.3 T4 → T3 (Re-entrancy)

`ble_evt_handler()` executes during `sd_app_evt_wait()` in soft-interrupt context (priority 2-4, higher than app priority 6). This means BLE observer callbacks can modify `monet_data` while the main loop is logically "between" operations. The Track 3 re-entrancy analysis extends to the sleep/wake boundary: the main loop may have read `monet_data.SleepState` before calling `idle_state_handle()`, then the BLE handler modifies it, and the post-sleep main loop iteration operates on stale state.

### 8.4 T4 → T6 (Self-Recovery)

The system has no software watchdog for stuck sleep states. If `sd_app_evt_wait()` blocks indefinitely (no wake source fires), the system is hung. The hardware watchdog (`pf_wdt_init()` at main.c:467) provides the only recovery. If the watchdog timeout is longer than the expected maximum sleep duration (1 second in HIBERNATE mode), a hung sleep can go undetected for multiple watchdog periods.

### 8.5 T4 → T5 (Handler Drop + GPIO SENSE)

Track 5 identifies handler-drop failures where `nrf_drv_gpiote_in_event_handler_process()` fails to propagate PIR events from the GPIOTE driver's internal event queue to the application handler. The sleep/wake cycle amplifies this in two ways:

**Dead-zone negation of GPIO SENSE backup.** Track 5 documents that GPIO SENSE on PIR_OUT serves as a backup mechanism when the GPIOTE event queue overflows — a SENSE event triggers the PORT ISR which then processes pending GPIOTE events. However, during `pyd_gpio_reconfig()` (called on every PIR interrupt including post-wake), GPIO SENSE is cycled to NOSENSE while the pin is bit-banged as an output:

```
pyd_gpio_in_disable()       → nrfx_gpiote_in_uninit() → SENSE disabled for PIR_OUT
pyd_gpio_read_value()       → I2C-like bit-banging over PIR_OUT (~150µs+)
pyd_gpio_out_low()          → PIR_OUT driven as output LOW
pyd_gpio_in_enable()        → GPIOTE re-initialized, SENSE re-armed
```

If the system just woke from System ON sleep via a PIR interrupt, the immediate `pyd_gpio_reconfig()` creates a dead zone where the T5 GPIO SENSE backup mechanism is **negated** — SENSE is temporarily disabled, so any PIR transition during this window cannot trigger a PORT event either. The primary GPIOTE channel is uninitialized AND the SENSE fallback is disabled: a double-blind window.

**Sleep-skip amplification.** When sleep is skipped (via SleepStateChange transition or pending log data), the main loop runs continuously at full speed without WFE pauses. This increases the frequency of PIR interrupt arrivals relative to sleep mode, because the CPU is always awake to service them. Higher interrupt frequency directly amplifies Track 5's handler-drop rate — the GPIOTE event queue fills faster with less idle time for draining, and the dead-zone windows from `pyd_gpio_reconfig()` occur more frequently per unit time. In sleep mode, the WFE between interrupts provides natural back-pressure; without sleep, the system runs at maximum PIR throughput, maximizing handler-drop probability.

### 8.6 T4 → T7 (SoftDevice BLE Timeslot Interference)

Track 7 identifies BLE SoftDevice timeslot interference as a competing wake source that can delay or suppress PIR interrupt servicing. The sleep/wake path creates a combined failure mode:

**BLE wake steals the wake cycle.** When `sd_app_evt_wait()` returns due to a BLE connection event rather than a PIR event, the BLE observer chain (`ble_evt_handler` and its callbacks) executes inside the SVC handler at SoftDevice priority levels (0–4) **before** the main loop resumes. If a PIR interrupt arrived during the BLE event window, it sits pending at priority 6 behind the SoftDevice's higher-priority handlers. The wake cycle that should have serviced the PIR was instead consumed by BLE processing. The PIR GPIOTE ISR does not run until after `sd_app_evt_wait()` returns and the NVIC tail-chains to the pending priority-6 ISR.

**Combined T4+T7 event-loss path.** If a second PIR edge arrives before the pending GPIOTE ISR runs (because the CPU is still in the BLE handler chain), the nRF52832's single-event GPIOTE LATCH register (Errata 89) loses the second transition. The failure sequence:

```
1. System in WFE sleep (sd_app_evt_wait)
2. BLE connection event fires → CPU wakes, SD_EVT_IRQHandler (priority 2) runs
3. PIR_OUT transitions → GPIOTE PORT event fires → GPIOTE_IRQn pends at priority 6
4. BLE observer chain runs (ble_evt_handler, GATT callbacks, etc.)
5. PIR_OUT transitions again (second edge) while GPIOTE ISR still pending
   → SINGLE-EVENT LATCH overwritten → second transition LOST
6. BLE handlers complete → sd_app_evt_wait() returns → NVIC tail-chains GPIOTE_IRQn
7. GPIOTE ISR runs but only captures ONE transition instead of TWO
```

**Competing wake-source frequency.** During high BLE activity (connection events every 20–30ms per the S132 SoftDevice specification), the CPU wakes frequently for BLE processing. Each BLE-induced wake is a cycle where PIR events are deprioritized behind SoftDevice handlers. The PIR sensor's output pulses last 100µs–2ms — well within the sub-millisecond BLE interrupt service times — so the timing overlap is realistic. When BLE events fire at 30–50 Hz and PIR events at comparable rates, a significant fraction of PIR interrupts queue behind BLE handlers, increasing the probability of the combined event-loss failure.

---

## 9. Findings Summary

| # | Finding | Severity | Location |
|---|---------|----------|----------|
| 1 | No System OFF usage — MCU always in System ON, GPIOTE state preserved | INFO | platform_hal_drv.c:2055 |
| 2 | PIR GPIOTE reconfig creates ~200µs dead zone on every interrupt | **MEDIUM** | camera_pyd1598.c:231-251 |
| 3 | Errata 89 interaction: GPIOTE reconfig + PORT event race = event loss | **MEDIUM** | camera_pyd1598.c + errata |
| 4 | BLE observer runs in soft-interrupt context during `sd_app_evt_wait()` | LOW | main.c:261, nrf_sdh.c:363 |
| 5 | No FreeRTOS tickless idle — bare-metal WFE sleep, no RTOS complexity | INFO | (confirmed absent) |
| 6 | RTC1 stop/start (APP_TIMER_KEEPS_RTC_ACTIVE=0) resets counter on each start | LOW | app_timer.c:163-204 |
| 7 | No GPIOTE re-init on wake from System ON sleep | INFO | main.c:541-549 |
| 8 | Sleep skipped during state transitions — no sleep during HIBERNATE↔NORMAL↔OFF | LOW | main.c:633-638 |
| 9 | `monet_data.SleepState`/`SleepStateChange` lack volatile — stale-read risk | MEDIUM | user.h:490-491 |
| 10 | `pf_enter_deep_sleep()` is a no-op — misleading name, no System OFF | INFO | platform_hal_drv.c:2055-2062 |

---

## 10. Recommendations

1. **Audit PIR GPIOTE reconfig window** — Measure actual dead-zone duration (`pyd_gpio_reconfig()`) with an oscilloscope. If > PIR minimum pulse width, add a software GPIO re-read after re-enable to catch transitions during the window.

2. **Consider `APP_TIMER_KEEPS_RTC_ACTIVE = 1`** — This prevents RTC1 counter reset on every timer start, enabling drift measurement and consistent timekeeping across sleep cycles. Cost: ~1-2µA additional sleep current.

3. **Add post-wake validation in main loop** — After `idle_state_handle()` returns, re-read `monet_data.SleepState` and `monet_data.phonePowerOn` to detect state changes that occurred during sleep (via BLE observer or timer callbacks).

4. **Document `pf_enter_deep_sleep()` behavior** — Rename or add a comment clarifying that this function does NOT enter System OFF and is a modem-power-down notification only.

5. **Consider GPIO SENSE backup for PIR** — If the GPIOTE channel for PIR_OUT is being re-initialized, configure PIR_OUT with GPIO SENSE as a fallback to catch transitions via the PORT event during the dead zone.
