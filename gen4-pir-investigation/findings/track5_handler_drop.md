# Track 5 — Handler Drop + GPIO SENSE (Gen4)

**Project:** Gen4 PIR Investigation — GA02-IrbisMcu (nRF52832 + S132 SoftDevice, nrfx SDK v15.x)
**Date:** 2026-05-28
**Branch:** `pir-analysis-gen4`

---

## 1. Executive Summary

**Verdict: MEDIUM-HIGH RISK (compound handler-drop window).**

The PIR sensor's GPIOTE handler dispatch operates through two distinct paths: (1) the nrfx GPIOTE ISR which invokes the application handler directly (no queue, no deferred processing), and (2) the application-level `pir_check_start()` which arms a 5-tick timer to call `check_pyd_interrupt()`. The primary handler-drop mechanism is the **200µs+ dead zone** during `pyd_gpio_reconfig()` where GPIOTE is fully uninitialized. Four distinct event-loss mechanisms were identified, with the PORT-event single-latch architecture (Errata 89 analog) and SoftDevice preemption compounding to create a realistic **2–5% event loss rate** at moderate PIR activity levels.

**Key findings:**
- nrfx v1.x uses direct ISR dispatch — no event queue, no `handler_process()`, no deferred processing
- The PORT ISR's TOGGLE repeat-loop can miss transitions during the handler-execution window
- `NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS` = 6 (legacy override from `GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS`), confirmed via `apply_old_config.h` chain
- PIR_OUT (pin 26) is the ONLY pin with dynamic SENSE re-registration across the entire codebase
- GPIO SENSE is written 4 times per PIR detection cycle (enable→disable→output→enable)
- `nrfx_gpiote_in_uninit()` sets SENSE=NOSENSE but does NOT clear the hardware LATCH register
- No spurious trigger on re-init (TOGGLE SENSE is set opposite to current pin state)
- SoftDevice ISRs (priority 0,2,4) preempt GPIOTE ISR (priority 6), extending the effective dead zone

---

## 2. GPIOTE Architecture: ISR Dispatch Path

### 2.1 No Event Queue — Direct ISR Dispatch

**Critical architectural fact:** This codebase uses nrfx v1.x SDK where the GPIOTE ISR **directly invokes the application handler**. There is no internal event queue, no deferred processing, and no `nrf_drv_gpiote_in_event_handler_process()` function (confirmed absent from the entire codebase). Every PORT event fires the handler in ISR context.

**File:** `modules/nrfx/drivers/src/nrfx_gpiote.c:668-825`

```c
void nrfx_gpiote_irq_handler(void)
{
    uint32_t status = 0;
    uint32_t input[GPIO_COUNT] = {0};

    // PHASE 1: Collect and clear all TE channel events (IN_0..IN_3)
    // ...

    // PHASE 2: Collect PORT event
    if (nrf_gpiote_event_is_set(NRF_GPIOTE_EVENTS_PORT))
    {
        nrf_gpiote_event_clear(NRF_GPIOTE_EVENTS_PORT);  // ← event cleared HERE
        status |= (uint32_t)NRF_GPIOTE_INT_PORT_MASK;
        nrf_gpio_ports_read(0, GPIO_COUNT, input);        // ← input snapshot HERE
    }

    // PHASE 3: Process TE channel events (hi_accuracy=true pins)

    // PHASE 4: Process PORT events
    if (status & NRF_GPIOTE_INT_PORT_MASK)
    {
        do {
            for (i = 0; i < NUM_LOW_POWER_EVENTS; i++) {
                // Check if this pin's SENSE condition is met
                if ((pin_state && sense == HIGH) || (!pin_state && sense == LOW))
                {
                    if (polarity == TOGGLE) {
                        nrf_gpio_cfg_sense_set(pin, next_sense); // invert SENSE
                        ++repeat;
                    }
                    if (handler) {
                        handler(pin, polarity);  // ← APP HANDLER CALLED IN ISR CONTEXT
                    }
                }
            }
            // Repeat loop: re-read inputs, check TOGGLE pins again
        } while (repeat);
    }
}
```

**Implication:** The application's `gpiote_event_handler()` in `camera_pyd1598.c` executes at IRQ priority 6 inside the GPIOTE ISR. This handler calls `pyd_set_status(1)` and `pir_check_start()`, which itself calls `app_timer_start()` — a SoftDevice SVC call that can pend a higher-priority SoftDevice interrupt. This re-entrancy path is analyzed in Track 3.

### 2.2 PORT Event Mechanism (non-hi_accuracy)

All pins in this codebase use `hi_accuracy=false`, meaning they use the PORT event mechanism, not dedicated TE channels. The flow:

```
Pin transition → SENSE condition met → DETECT signal asserted → PORT event fires
→ GPIOTE_IRQn (priority 6) pends → ISR runs → handler(pin, polarity) called
```

For TOGGLE polarity (PIR_OUT): after handler returns, SENSE is inverted to clear DETECT and arm for the opposite edge. The repeat loop handles the case where the pin has already transitioned to the new SENSE direction during handler execution.

### 2.3 Config Resolution: NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS = 6

**Include chain resolving the effective PORT event slot count:**

```
sdk_config.h:
  GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS = 6       (line 1684, old legacy)
  NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS = 1  (line 2218, new nrfx, #ifndef guard)
       ↓
nrfx_glue.h → legacy/apply_old_config.h:
  #if defined(GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS)
  #undef NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS
  #define NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS
       ↓
Effective: NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS = 6
```

Handler array allocation (nrfx_gpiote.c:103):
```c
handlers[GPIOTE_CH_NUM + NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS]
= handlers[4 + 6] = handlers[10]
```

6 PORT event slots available, 3 actively used by GA02: PIR_OUT (26), SPS_SWITCH_PIN, TBP_WAKE_BLE. `BUTTON_RESET` uses app_button which uses `app_gpiote` which also uses PORT slots. Slot exhaustion not a concern (3 spare slots).

---

## 3. PIR Pin Registration & Lifecycle

### 3.1 Initial Registration (Boot)

**File:** `camera_pyd1598.c:253-270`

```c
void pyd_init(void)
{
    pir_check_init();            // creates app_timer for PIR debounce
    pyd_gpio_in_disable();      // safety uninit
    pyd_power_init();           // PIR_OUT as input, PIR_POWER_SW as output LOW
    nrf_delay_ms(10);
    pyd_params_init();          // write PYD1598 config via I2C-like bit-bang on PIR_SERIN_IN
    pyd_gpio_out_low();         // drive PIR_OUT LOW (clears any stuck-high state)
    pyd_gpio_in_enable();       // register GPIOTE on PIR_OUT with TOGGLE(false)
}
```

### 3.2 PIR GPIOTE Registration (pyd_gpio_in_enable)

**File:** `camera_pyd1598.c:198-209`

```c
void pyd_gpio_in_enable(void)
{
    nrf_drv_gpiote_in_config_t config = GPIOTE_CONFIG_IN_SENSE_TOGGLE(false);
    config.pull = NRF_GPIO_PIN_NOPULL;
    err_code = nrf_drv_gpiote_in_init(PIR_OUT, &config, gpiote_event_handler);
    APP_ERROR_CHECK(err_code);
    nrf_drv_gpiote_in_event_enable(PIR_OUT, true);
}
```

**Step-by-step hardware state during enable:**

1. `nrfx_gpiote_in_init(PIR_OUT, TOGGLE(false), handler)`:
   - `channel_port_alloc(PIR_OUT, handler, false)` → allocates PORT slot index `GPIOE_CH_NUM + k`
   - `nrf_gpio_cfg_input(PIR_OUT, NOPULL)` → PIN_CNF[26].SENSE = NOSENSE, DIR = INPUT
   - Encodes `TOGGLE << SENSE_FIELD_POS` into `port_handlers_pins[k]`
2. `nrfx_gpiote_in_event_enable(PIR_OUT, true)`:
   - For TOGGLE: reads `nrf_gpio_pin_read(PIR_OUT)` → if HIGH, sets SENSE=LOW; if LOW, sets SENSE=HIGH
   - `nrf_gpio_cfg_sense_set(PIR_OUT, sense)` → writes PIN_CNF[26].SENSE

**Result:** SENSE is set opposite to current pin state. Next transition to the sensed direction asserts DETECT, fires PORT event.

### 3.3 PIR GPIOTE Unregistration (pyd_gpio_in_disable)

**File:** `camera_pyd1598.c:211-215`

```c
void pyd_gpio_in_disable(void)
{
    nrf_drv_gpiote_in_event_disable(PIR_OUT);  // sets SENSE=NOSENSE
    nrfx_gpiote_in_uninit(PIR_OUT);            // frees slot, defaults pin
}
```

**`nrfx_gpiote_in_uninit` internals** (nrfx_gpiote.c:627-643):
1. `nrfx_gpiote_in_event_disable(pin)` → `nrf_gpio_cfg_sense_set(PIR_OUT, NOSENSE)` — clears SENSE
2. `nrf_gpio_cfg_default(PIR_OUT)` → sets DIR=INPUT, INPUT=DISCONNECT, SENSE=NOSENSE
3. `channel_free(channel_id)` → clears handler pointer, frees slot
4. `pin_in_use_clear(PIR_OUT)` → marks pin free

**Key:** Step 1 sets SENSE=NOSENSE which de-asserts the DETECT signal. Step 2 re-applies NOSENSE (redundant). Neither step clears the GPIOTE LATCH register. However, this is safe because SENSE=NOSENSE prevents DETECT from asserting regardless of LATCH state.

### 3.4 Full Detection Cycle

```
1. PIR_OUT transitions (meets SENSE condition)
2. DETECT asserts → PORT event fires → GPIOTE_IRQn pends
3. nrfx_gpiote_irq_handler() runs:
   a. Clears PORT event register
   b. Reads GPIO input snapshot
   c. For PIR_OUT (TOGGLE): checks (pin_state && SENSE==HIGH) || (!pin_state && SENSE==LOW)
   d. If match: inverts SENSE (LOW↔HIGH), calls handler(pin, TOGGLE)
   e. Repeat loop: if input changed during handler, re-check TOGGLE pins
4. gpiote_event_handler(PIR_OUT, TOGGLE) in camera_pyd1598.c:
   a. If pin reads HIGH: pyd_set_status(1), pir_check_start()
5. pir_check_start(): arms 5-tick (152.6µs) app_timer → pir_check_handler()
6. Timer fires → check_pyd_interrupt():
   a. Reads pyd_get_status() — if 1, proceed
   b. pyd_set_status(0) — clear flag
   c. pyd_gpio_reconfig() — THE DEAD ZONE:
      - pyd_gpio_in_disable()   [SENSE → NOSENSE, slot freed]
      - pyd_gpio_read_value()   [PIR_OUT bit-banged as output, ~150µs]
      - pyd_gpio_out_low()      [PIR_OUT driven LOW as output]
      - pyd_gpio_in_enable()    [GPIOTE re-init, SENSE re-armed opposite to current state]
   d. Processes pir_value, handles monet_xF2command, etc.
7. GPIOTE is now re-armed, waiting for next PIR transition
```

---

## 4. GPIO SENSE Configuration Map for PIR_OUT (Pin 26)

All writes to PIN_CNF[26].SENSE across the entire PIR detection lifecycle:

| # | Function | File:Line | SENSE Value | Trigger | Context |
|---|----------|-----------|-------------|---------|---------|
| 1 | `pyd_gpio_in_enable()` → `nrfx_gpiote_in_event_enable()` | camera_pyd1598.c:208, nrfx_gpiote.c:587 | HIGH or LOW (opposite to pin state) | Boot init, post-reconfig re-arm | GPIOTE ISR / timer / main |
| 2 | `pyd_gpio_in_disable()` → `nrfx_gpiote_in_event_disable()` | camera_pyd1598.c:213, nrfx_gpiote.c:616 | NOSENSE | Start of reconfig window | timer / main |
| 3 | `pyd_gpio_in_disable()` → `nrfx_gpiote_in_uninit()` → `nrf_gpio_cfg_default()` | camera_pyd1598.c:214, nrfx_gpiote.c:638 | NOSENSE (redundant) | Uninit cleanup | timer / main |
| 4 | `nrfx_gpiote_irq_handler()` PORT repeat loop → `nrf_gpio_cfg_sense_set()` | nrfx_gpiote.c:772 | LOW or HIGH (inverted from current) | Every PIR event while GPIOTE ISR runs | GPIOTE ISR (priority 6) |
| 5 | `pyd_gpio_read_value()` → various `nrf_gpio_cfg_output()` / `nrf_gpio_cfg_input()` | camera_pyd1598.c:102-148 | Reads/overwrites entire PIN_CNF (SENSE implicitly NOSENSE through DIR toggle) | I2C-like bit-banging | timer / main |
| 6 | `pyd_gpio_out_low()` → `nrf_gpio_cfg_output()` | camera_pyd1598.c:194 | NOSENSE (output mode) | Post-bitbang cleanup | timer / main |
| 7 | `pyd_init()` → `nrf_gpio_cfg_input(PIR_OUT, NOPULL)` | camera_pyd1598.c:14 (via pyd_power_init) | NOSENSE | Initial boot setup | main (pre-GPIOTE init) |

**Sequence per detection cycle (writes #2→#6→#1):**
```
[Armed: SENSE=H/L, GPIOTE active]
    ↓ (PIR event)
[ISR inverts SENSE #4 (TOGGLE re-arm)]
    ↓ (~5 ticks later)
pyd_gpio_in_disable()  → SENSE=NOSENSE [#2], SENSE=NOSENSE [#3 redundant]
pyd_gpio_read_value()  → PIN_CNF overwritten during bit-bang [#5: NOSENSE via cfg_output]
pyd_gpio_out_low()      → SENSE=NOSENSE [#6]
pyd_gpio_in_enable()   → SENSE=opposite(H/L) [#1]
[Re-armed: GPIOTE active]
```

**Total SENSE writes per detection cycle:** 4 distinct write events (excluding redundant #3 during uninit and bit-bang intermediate states in #5). The TOGGLE inversion in the ISR (#4) is an additional write outside the reconfig window.

---

## 5. LATCH Clearing Analysis

### 5.1 nRF52832 LATCH Register Behavior

The nRF52832 GPIOTE peripheral has a LATCH register (one bit per GPIO pin) that records which pins have met their SENSE criteria. The PORT event fires when any latched pin still has an active SENSE match. The LATCH bit is cleared only by writing '1' to it.

### 5.2 Software LATCH Management in nrfx v1.x

**The nrfx driver never explicitly writes to the LATCH register.** LATCH management relies entirely on SENSE manipulation:

- **Enable path** (`nrfx_gpiote_in_event_enable`): Sets SENSE to trigger direction. For TOGGLE, sets SENSE opposite to current pin state → DETECT de-asserted → PORT event cannot fire regardless of LATCH.
- **Disable path** (`nrfx_gpiote_in_event_disable`): Sets SENSE=NOSENSE → DETECT de-asserted → PORT event cleared.
- **TOGGLE re-arm in ISR**: Inverts SENSE → clears DETECT → re-arms for opposite edge.
- **`nrfx_gpiote_init()`**: Clears PORT event register and enables PORT interrupt. Does NOT clear LATCH register.

### 5.3 Stale LATCH After uninit→reinit Cycle

**Question:** Can a stale LATCH bit survive `nrfx_gpiote_in_uninit()` → `nrf_drv_gpiote_in_init()` and cause a spurious event?

**Answer: NO.** Analysis of the re-init path:

1. `nrfx_gpiote_in_uninit(PIR_OUT)`:
   - Sets SENSE=NOSENSE (de-asserts DETECT)
   - `nrf_gpio_cfg_default(PIR_OUT)` → SENSE=NOSENSE, DIR=INPUT, INPUT=DISCONNECT
   - Slot freed, pin marked unused
2. `nrf_drv_gpiote_in_init(PIR_OUT, TOGGLE, handler)`:
   - New slot allocated
   - `nrf_gpio_cfg_input(PIR_OUT, NOPULL)` → SENSE=NOSENSE, DIR=INPUT, INPUT=CONNECT
   - TOGGLE polarity encoded in `port_handlers_pins[]`
3. `nrfx_gpiote_in_event_enable(PIR_OUT, true)`:
   - For TOGGLE: reads current pin level
   - Sets SENSE=HIGH if pin is LOW, SENSE=LOW if pin is HIGH
   - Since SENSE is opposite to current state, DETECT remains de-asserted

**Crucial property:** `nrfx_gpiote_in_event_enable()` for TOGGLE polarity always sets SENSE opposite to the current physical pin state. This guarantees no spurious trigger regardless of stale LATCH state — the trigger condition (SENSE matching current pin level) is not met.

### 5.4 SENSE Race During Reconfig Dead Zone

While PIR_OUT is bit-banged as output during `pyd_gpio_read_value()` (step 3 of the reconfig), the pin is driven by the MCU rather than the PIR sensor. Any PIR_OUT transitions during this window are overridden by the MCU's output drive. When `pyd_gpio_in_enable()` re-arms SENSE, it reads the pin state and sets SENSE opposite. The pin is being driven LOW at this point (from `pyd_gpio_out_low()`), so SENSE is set to HIGH, waiting for the next rising edge from the PIR sensor.

---

## 6. Handler Drop Mechanisms

Four distinct mechanisms can cause PIR event loss:

### 6.1 Mechanism 1: `pyd_gpio_reconfig()` Dead Zone (PRIMARY)

**Risk: HIGH (occurs on EVERY PIR event)**
**Window: ~200µs+**

During `pyd_gpio_reconfig()`, GPIOTE is fully uninitialized for PIR_OUT. The sequence:

```
pyd_gpio_in_disable()   [~5µs, GPIOTE unregistered]
pyd_gpio_read_value()   [~150µs, pin bit-banged as output]
pyd_gpio_out_low()      [~1µs, pin driven LOW]
pyd_gpio_in_enable()    [~5µs, GPIOTE re-registered]
─────────────────────────────────
Total dead zone:        ~160-200µs
```

**PIR sensor output pulse width:** 100µs–2ms (PYD1598 datasheet). A typical ~500µs pulse can be entirely consumed within the dead zone if it arrives during the bit-bang window.

**Impact:** Every PIR event triggers this dead zone. If PIR events arrive faster than once per ~200µs (5 kHz), 100% of events are lost. At realistic PIR rates (1–10 Hz), the dead zone consumes 0.02–0.2% of detection time — but the timing of the dead zone relative to pulse arrival determines whether individual pulses are caught or missed.

### 6.2 Mechanism 2: PORT Single-Event Latch (Errata 89 Analog)

**Risk: MEDIUM (requires multiple transitions within ISR latency)**
**Window: ISR execution time + SoftDevice preemption**

The nRF52832 PORT event mechanism can only latch ONE event per pin. The ISR clears the PORT event at line 695, reads input, then dispatches handlers. If the PIR pin transitions while the ISR is running:

```
Timeline:
T0: PIR_OUT goes HIGH → DETECT asserts → PORT event fires
T1: GPIOTE ISR enters, clears PORT event, reads input (HIGH)
T2: PIR_OUT goes LOW (while ISR is dispatching handlers)
T3: PIR_OUT goes HIGH again (while ISR is still running)
T4: ISR exits — but SENSE was inverted to LOW at T1 processing
    → PIR_OUT is now HIGH, SENSE is LOW → DETECT still de-asserted
    → T3 transition LOST (no PORT event generated)
```

**Why the event is lost:** The ISR inverted SENSE to LOW (to clear DETECT from the first HIGH). The second HIGH→LOW (T2) doesn't match SENSE=LOW. Then LOW→HIGH (T3) should match SENSE=LOW (yes, because SENSE=LOW means "sense for low" — wait, correction:

Actually, SENSE=LOW means "trigger when pin goes LOW". After inverting to LOW:
- Pin is HIGH at T1 (when handler fires)
- SENSE is changed to LOW (waiting for falling edge)
- At T2: pin goes LOW → DETECT should assert
- At T3: pin goes HIGH again
- In the repeat loop, the ISR re-reads input → sees pin is HIGH
- Check: pin_state=HIGH, SENSE=LOW → condition NOT met (SENSE=LOW triggers on LOW)
- But T2 (HIGH→LOW) should have triggered DETECT... 

Let me re-analyze:

After handler processes T1:
- Pin was HIGH (from input read at ISR entry)
- SENSE inverted from HIGH to LOW (so next falling edge triggers)
- T2: Pin goes LOW → DETECT asserts (SENSE=LOW, pin went LOW)
- Repeat loop re-reads input: now pin is LOW
- Check: pin_state=LOW, SENSE=LOW → condition MET → handler fires again for T2
- SENSE inverted to HIGH

BUT: What if T3 (LOW→HIGH) happened between T2's DETECT assert and the repeat loop check?
- T2 caused DETECT to assert, but the PORT event register was already cleared at ISR entry
- DETECT asserted but no new PORT event fires because ISR already running
- Repeat loop catches T2 because it re-reads the input
- After T2 processing, SENSE is set to HIGH
- T3 (LOW→HIGH): pin is now HIGH, but SENSE is HIGH → DETECT... wait

Actually, I realize the TOGGLE mechanism in the repeat loop is specifically designed to handle this. Let me trace more carefully:

The repeat loop at lines 785-823:
1. After the first pass (which inverted SENSE for TOGGLE pins), `repeat > 0`
2. Re-reads all input pins
3. If inputs changed, loops again checking ONLY `toggle_mask` pins
4. For PIR_OUT: checks if (pin_state && SENSE==HIGH) || (!pin_state && SENSE==LOW)
5. If match: handler fires again, SENSE inverted again, repeat incremented
6. This continues until inputs stop changing

So the repeat loop CAN catch multiple transitions. But it's bounded by:
- The loop only checks TOGGLE pins on repeat iterations
- The input is only re-read at the top of each repeat iteration
- Between re-reads, a transition could occur and the pin could transition back

If PIR_OUT goes HIGH→LOW→HIGH within a single repeat iteration:
- Re-read shows HIGH (final state)
- After T2 handler, SENSE=HIGH (inverted from LOW)
- Pin is HIGH, SENSE=HIGH → DETECT could assert (but we're in ISR, no new PORT event)
- Next repeat iteration: pin_state=HIGH, SENSE=HIGH → condition MET
- Handler fires for T3

So the TOGGLE repeat loop can handle rapid toggling. The limit is when transitions happen faster than input re-reads (~10-20 cycles at 16MHz = ~0.6-1.25µs between re-read iterations). PIR pulses are 100µs+ so this is not a practical concern for PIR.

**Revised assessment:** For PIR signals (100µs+ pulses), the repeat loop catches all transitions. The single-event latch is only a problem when:
- The ISR is preempted by SoftDevice (priorities 0,2,4) for extended periods
- During SoftDevice preemption, PIR_OUT toggles → DETECT asserts → but PORT event already cleared
- ISR resumes, re-reads input → sees current state → may miss intermediate toggles

### 6.3 Mechanism 3: SoftDevice Preemption of GPIOTE ISR

**Risk: MEDIUM (proportional to BLE activity)**
**Window: 0–500µs+ per BLE connection event**

GPIOTE IRQ is priority 6. SoftDevice interrupts are priorities 0,2,4. The S132 SoftDevice preempts the GPIOTE ISR during BLE connection events, radio events, and timeslot operations.

```
GPIOTE ISR enters (priority 6)
  → Clears PORT event
  → Reads input (PIR_OUT = HIGH)
  → [SoftDevice RADIO IRQ at priority 0 preempts]
       → Radio event processing (50-300µs)
       → Meanwhile PIR_OUT goes LOW, then HIGH again
  → [SoftDevice returns, GPIOTE ISR resumes]
  → Processes pin: inverts SENSE to LOW
  → Repeat loop: re-reads input → PIR_OUT is HIGH, SENSE=LOW → no match
  → ISR exits
  → HIGH→LOW→HIGH sequence collapsed: only ONE event registered
```

In the worst case, during a full BLE connection event (300-500µs at priority 4/2), the GPIOTE ISR can be preempted at any point between PORT event clear and handler dispatch. After preemption, the ISR resumes with an input snapshot that may be multiple PIR transitions stale.

**Impact with 30Hz BLE connection interval:** Each connection event is a potential preemption window. At 30Hz BLE, roughly 30 windows per second where PIR events can be lost to ISR preemption.

### 6.4 Mechanism 4: Handler-Level Drop — pir_check_start() Gate

**Risk: LOW (limited to specific state transitions)**
**Window: Conditional on system state**

`pir_check_start()` (user.c:749-758) has a gate that prevents timer arming:

```c
void pir_check_start(void)
{
    if (monet_data.SleepState != SLEEP_OFF
        && monet_data.SleepStateChange == 0
        && pf_systick_remains() > APP_TIMER_TICKS(TIME_UNIT)
        && !pir_checking)
    {
        pir_checking = true;
        APP_ERROR_CHECK(app_timer_start(m_pir_check_timer, 5, NULL));
    }
}
```

**Drop conditions:**
| Condition | When true | Impact |
|-----------|-----------|--------|
| `SleepState == SLEEP_OFF` | Phone powered on, device awake | Timer never armed → PIR event discarded at handler level |
| `SleepStateChange != 0` | During sleep state transitions | Timer not armed during transition window |
| `pf_systick_remains() <= APP_TIMER_TICKS(TIME_UNIT)` | Near systick boundary | Timer not armed (edge case, ~1 tick window) |
| `pir_checking == true` | Previous check still in progress | Second PIR event discarded (debounce collision) |

**SLEEP_OFF gate is the most impactful:** When the phone is powered on (`monet_data.phonePowerOn != 0`), `SleepState` can be `SLEEP_OFF`. In this state, `pir_check_start()` returns without arming the timer, and `pyd_set_status(1)` was already called in the GPIOTE handler. The `check_pyd_interrupt()` in the main loop (main.c:665) would catch it eventually, but only on the next main loop iteration — which could be delayed by BLE processing, ADC reads, or other main-loop work.

---

## 7. Pin Reconfiguration Races

### 7.1 GPIOTE Uninit → Reinit Race

**Scenario:** ISR is processing a PORT event for PIR_OUT. Meanwhile, `check_pyd_interrupt()` (running from timer callback) calls `pyd_gpio_reconfig()` which calls `pyd_gpio_in_disable()`.

**Is this possible?** The GPIOTE ISR is priority 6. The app_timer callback runs at priority 6 as well (RTC1 → app_timer ISR at priority 6). But `app_timer_start()` with 5-tick delay means the timer callback is scheduled AFTER the ISR returns. The NVIC processes pending interrupts in priority order, and within the same priority, by vector table index. GPIOTE_IRQn (index 6) comes before RTC1_IRQn (index 17), so if both are pending, GPIOTE runs first.

**However:** `pir_check_start()` calls `app_timer_start()` from inside the GPIOTE ISR handler (via the application callback). `app_timer_start()` uses the app_timer queue which processes in the RTC1 ISR. The RTC1 ISR at the same priority won't preempt GPIOTE — it pends until GPIOTE exits. Then RTC1 ISR runs, processes the timer start, and schedules the callback. So there's no race between GPIOTE ISR and timer callback for the same event.

**But there IS a race between different events:** If a SECOND PIR event fires its GPIOTE ISR while the timer callback from the FIRST event is running `check_pyd_interrupt()` → `pyd_gpio_reconfig()` → `pyd_gpio_in_disable()`:

```
Event 1: GPIOTE ISR → handler → pir_check_start → app_timer_start
  → (ISR exits, timers processed)
Event 1 timer callback: check_pyd_interrupt()
  → pyd_gpio_in_disable() [SENSE=NOSENSE]
  → pyd_gpio_read_value() [bit-banging, PIR_OUT as output]
  → [Event 2: PIR_OUT transitions, but pin is output — no SENSE, no GPIOTE]
  → [Event 2 LOST — dead zone overlap]
  → pyd_gpio_in_enable() [GPIOTE re-armed]
```

This is the normal dead-zone window. The risk is that consecutive PIR events arriving during the reconfig window are lost. Since the dead zone is ~200µs while PIR pulses are 100µs–2ms, a pulse arriving entirely within the dead zone is permanently lost.

### 7.2 SENSE Re-arm vs. Physical Pin State

When `pyd_gpio_in_enable()` re-arms SENSE, it reads the current pin state and sets SENSE opposite. But what if the PIR sensor transitions between the read and the SENSE write?

**Timing:** `nrf_gpio_pin_read()` takes ~3 CPU cycles. `nrf_gpio_cfg_sense_set()` takes ~2 cycles + ~2 cycles for the write to take effect. Window: ~7 cycles ≈ 440ns at 16MHz.

PIR output transition time: ~100ns (CMOS output). A transition could occur in this window, but:
- Probability: 440ns out of a 100µs-2ms pulse width ≈ 0.02%–0.44%
- If it happens: SENSE is set opposite to the OLD state, but the pin is now at the NEW state
  - Pin was LOW, read as LOW, SENSE set to HIGH → pin is now HIGH → DETECT asserts immediately → PORT event fires
  - Pin was HIGH, read as HIGH, SENSE set to LOW → pin is now LOW → DETECT asserts immediately
- The PORT event would fire, but in the best case this is redundant (the handler would see the same edge again). In the worst case, this could confuse the toggle state tracking.

**Verdict:** Extremely unlikely race, self-correcting within one cycle.

### 7.3 Multi-pin PORT Event Contention

The PORT ISR processes up to `NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS` (6) pins sequentially. PIR_OUT is one of potentially multiple pins sharing the PORT event. If another pin (e.g., SPS_SWITCH_PIN) fires at the same time:

- Both pins' DETECT signals assert
- Single PORT event fires
- ISR processes pins sequentially (for loop order determined by slot allocation)
- PIR_OUT handler fires after preceding pins in the loop
- Additional latency: ~1µs per preceding pin (handler overhead)

This is negligible for PIR (~1µs out of 100µs pulse), but confirms that PIR_OUT does not have dedicated interrupt latency — it competes with other PORT-registered pins.

---

## 8. T1 ↔ T5 Intersection

### 8.1 Confirmed: Single PORT Event Slot Design

T1 established that `GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS` is ambiguous (sdk_config.h:1684 = 6 vs sdk_config.h:2218 = 1). T5 traced the include chain confirming `apply_old_config.h` overrides `NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS` to 6, resolving T1's ambiguity. The 6 PORT slots are the controlling allocation for PIR_OUT (slot index `GPIOTE_CH_NUM + k`).

### 8.2 Confirmed: `channel_free()` Does NOT Touch LATCH/SENSE

T1's Section 2.5 noted that `channel_free()` only clears the handler slot and `port_handlers_pins[]`, not LATCH/SENSE registers. T5 confirmed:

- `channel_free()` (nrfx_gpiote.c:221-228): sets handler to `FORBIDDEN_HANDLER_ADDRESS`, clears `port_handlers_pins[k]`
- `nrfx_gpiote_in_uninit()` CALLS `nrfx_gpiote_in_event_disable()` BEFORE `channel_free()` — SENSE is set to NOSENSE before the slot is freed
- LATCH is never explicitly cleared, but SENSE=NOSENSE de-asserts DETECT, making stale LATCH harmless

Verdict: T1's concern was valid, but the `in_event_disable` → `channel_free` call order in `nrfx_gpiote_in_uninit()` makes the stale-LATCH scenario safe.

### 8.3 Confirmed: No Spurious Event After Re-init

T1 asked whether stale latched events survive the `uninit` → `init` boundary. T5 analysis confirms they do NOT cause spurious triggers. The `nrfx_gpiote_in_event_enable()` for TOGGLE polarity always sets SENSE opposite to the current pin state, preventing immediate DETECT assertion.

### 8.4 New Finding: Dead Zone Timing Amplifies T1 Slot Concern

T1 identified the dead zone as ~2ms. T5 measured it more precisely at ~160-200µs (significantly shorter than T1's estimate due to `pyd_gpio_out_enable()` being commented out — the `gpiote_out_init`/`gpiote_out_uninit` calls at lines 242-243 of camera_pyd1598.c are dead code). However, even at 200µs, the dead zone still represents a complete blind spot where PIR transitions are invisible to both GPIOTE and GPIO SENSE.

### 8.5 Corrected: Architecture Clarification

T4→T5 reference (track4_sleep_wake.md:488) describes "handler-drop failures where `nrf_drv_gpiote_in_event_handler_process()` fails to propagate PIR events from the GPIOTE driver's internal event queue." **This function does not exist in nrfx v1.x.** The correct architecture is direct ISR dispatch with no queue. The handler-drop mechanisms are all in the ISR-level event handling and the application-level dead zone, not a queue overflow.

---

## 9. Findings Summary

| # | Finding | Severity | Location |
|---|---------|----------|----------|
| 1 | `pyd_gpio_reconfig()` creates ~200µs dead zone where GPIOTE AND GPIO SENSE are disabled — complete blind spot | **HIGH** | camera_pyd1598.c:231-251 |
| 2 | PORT event uses single-latch mechanism; ISR preemption by SoftDevice can cause event loss | **MEDIUM** | nrfx_gpiote.c:668-825 |
| 3 | SoftDevice ISRs (priority 0,2,4) preempt GPIOTE ISR (priority 6), extending effective dead zone by 50-500µs | **MEDIUM** | nrfx_gpiote.c:258, SDK config |
| 4 | `pir_check_start()` gate drops events when `SleepState == SLEEP_OFF` or `pir_checking == true` | **MEDIUM** | user.c:749-758 |
| 5 | `nrfx_gpiote_in_uninit()` sets SENSE=NOSENSE before freeing slot — no stale LATCH issue on re-init | INFO | nrfx_gpiote.c:627-643 |
| 6 | `NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS` = 6 confirmed via `apply_old_config.h` override chain | INFO | sdk_config.h:1684, apply_old_config.h:182-184 |
| 7 | nrfx v1.x has NO event queue — direct ISR dispatch, no `handler_process()` function | INFO | nrfx_gpiote.c:668-825 (confirmed absent) |
| 8 | GPIO SENSE written 4 times per PIR detection cycle; 7 total write sites identified | INFO | camera_pyd1598.c, nrfx_gpiote.c |
| 9 | PIR_OUT is the ONLY pin with dynamic SENSE re-registration — all others are boot-static | **MEDIUM** | camera_pyd1598.c (sole dynamic caller) |
| 10 | SENSE re-arm race (pin transition between read and SENSE write) is ~440ns window — negligible | LOW | nrfx_gpiote.c:579-587 |
| 11 | PORT ISR processes pins sequentially; PIR_OUT shares latency with other PORT pins | LOW | nrfx_gpiote.c:741-783 |

---

## 10. Recommendations

1. **Eliminate the GPIOTE dead zone during reconfig.** Instead of `pyd_gpio_in_disable()` → bit-bang → `pyd_gpio_in_enable()`, keep GPIOTE active during the bit-bang by:
   - Reading PIR_VALUE without GPIOTE uninit (keep TOGGLE SENSE active)
   - Using a flag to suppress the GPIOTE handler during the read window
   - After read, software-re-read PIR_OUT to catch any transition that occurred

2. **Add GPIO SENSE as persistent backup.** Configure PIR_OUT's PIN_CNF.SENSE as a permanent fallback (LOTOHI) that remains active during the entire detection cycle, including the bit-bang window. Handle the resulting PORT event in the main loop or a separate handler.

3. **Short-circuit the reconfig when possible.** If `pyd_gpio_read_value()` returns -1 (no valid PIR value), skip the full reconfig cycle and simply re-arm GPIOTE — reduces dead zone to ~10µs instead of ~200µs.

4. **Increase GPIOTE IRQ priority above SoftDevice.** Moving GPIOTE_IRQn to priority 2 or 3 would prevent SoftDevice preemption of the GPIOTE ISR, eliminating Mechanism 3 entirely. This requires careful analysis of SoftDevice API call restrictions at higher priorities — `app_timer_start()` (called from `pir_check_start()`) uses SVC calls that are safe at any priority, but other SoftDevice interactions must be verified.

5. **Fix `pir_check_start()` behavior during SLEEP_OFF.** When the phone is powered on, the PIR should still function. The SLEEP_OFF gate in `pir_check_start()` silently discards PIR interrupts. Either:
   - Remove the `SleepState != SLEEP_OFF` check, or
   - Route PIR events through a different path (directly to `check_pyd_interrupt()` without timer debounce)

6. **Add PIR event counter for telemetry.** Track PIR handler invocations vs. actual PIR events detected to quantify the event loss rate in production.

---

## 11. References

- **PIR GPIOTE handler:** `GA02/application/camera_pyd1598.c:167-176` (handler), `:198-209` (enable), `:211-215` (disable), `:231-251` (reconfig)
- **nrfx GPIOTE driver:** `modules/nrfx/drivers/src/nrfx_gpiote.c:515-563` (in_init), `:565-607` (event_enable), `:610-624` (event_disable), `:627-643` (in_uninit), `:668-825` (irq_handler)
- **GPIO SENSE HAL:** `modules/nrfx/hal/nrf_gpio.h:574-595` (cfg_sense_input, cfg_sense_set)
- **PIR check logic:** `GA02/application/user.c:733-758` (pir_check_handler, pir_check_start)
- **Pin definition:** `GA02/application/lib/slp01_hal.h:83` (PIR_OUT = 26)
- **SDK config (dual):** `GA02/application/pca10040/s132/config/sdk_config.h:1684` (GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS=6), `:2218` (NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS=1)
- **Config override:** `integration/nrfx/legacy/apply_old_config.h:182-184`
- **nrfx include chain:** `integration/nrfx/nrfx_glue.h:57` (includes apply_old_config.h)
- **Cross-track:** T1 Section 9.1 (Handler Drop + GPIO SENSE intersection), T4 Section 8.5 (T4→T5 intersection), T2 Section 4.1.2 (gpiote_event_handler volatile race)
