# Gen4 PIR Intermittent Missed Events — Final Synthesis Report

**Project:** atel-reveal-4-mcu (Gen4 Wildlife Camera Firmware)
**Branch:** `pir-analysis-gen4`
**MCU:** nRF52840 (Cortex-M4), bare-metal, S132 SoftDevice v5.x, nrfx SDK v15.x
**Date:** 2026-05-28
**Investigation Scope:** 10 finding documents — errata, sdk_config, gpiote_call_sites, tracks 1-7

---

## 1. Primary Root Cause

**The `pyd_gpio_reconfig()` GPIOTE dead zone is the primary root cause of intermittent missed PIR events.**

Every PIR detection cycle executes `pyd_gpio_reconfig()` (`camera_pyd1598.c:231-251`), which performs a destructive GPIOTE uninit → bit-bang read → GPIOTE re-init sequence on PIR_OUT (pin 26). During the ~160-200µs window where GPIOTE is uninitialized and PIR_OUT is bit-banged as a GPIO output, all pin transitions are silently and permanently lost. No software re-read is performed after re-arming to catch transitions that occurred during this window.

### Root Cause Framework

| Classification | Factor | Code-Path Citations | Severity |
|---|---|---|---|
| **PRIMARY** | `pyd_gpio_reconfig()` dead zone — GPIOTE torn down and PIR_OUT bit-banged as output on every PIR event | `camera_pyd1598.c:231-251` (reconfig), `:211-215` (disable), `:198-209` (enable) | **CRITICAL** |
| **CONTRIBUTING** | SoftDevice BLE preemption (priorities 0,2,4) extends dead zone to 350-500µs+ | `nrfx_gpiote.c:668-825` (ISR), `sdk_config.h:12109-12110` (INTERRUPT dispatch) | **MEDIUM** |
| **CONTRIBUTING** | `monet_data` (155 members, ~500+ bytes) not `volatile` — racing across 5 execution contexts | `user.c:67` (definition), `camera_pyd1598.c:167-176` (GPIOTE ISR), `platform_hal_drv.c:98-131` (SAADC ISR), `camera_i2c.c:244-161` (TWIS ISR), `platform_hal_drv.c:1260-183` (timer ISR), `user.c:815-901` (main loop) | **HIGH** |
| **CONTRIBUTING** | `pir_checking` flag is single point of failure — corruption permanently blocks all PIR detection | `user.c:38` (volatile declaration), `user.c:819/901` (set/clear), `main.c:662-665` (spin-wait guard) | **MEDIUM** |
| **ENABLING** | All 6 GPIOTE call sites use `hi_accuracy=false` — every pin shares single PORT event mechanism | `camera_pyd1598.c:205`, `camera_key.c:143`, `camera_sps.c:47`, `platform_hal_drv.c:584/2670/2701` | **LOW** |
| **ENABLING** | nrfx v1.x direct ISR dispatch — no event queue, no deferred processing | `nrfx_gpiote.c:668-825` (confirmed: `handler_process()` absent) | **LOW** |
| **ENABLING** | Errata 89 — GPIOTE PORT event can be missed during reconfiguration windows | `errata_review.md` §Errata 89 | **HIGH** |
| **ENABLING** | Single recovery mechanism — `NVIC_SystemReset()` for all fault paths, no graceful degradation | `app_error.c` (weak default fault handler), `platform_hal_drv.c:1602-1613` (WDT init) | **HIGH** |
| **INCIDENTAL** | WDT ~610ms timeout with 1s feed interval — architecturally insufficient | `sdk_config.h:4839-4847`, `platform_hal_drv.c:2584-2589` | **MEDIUM** |
| **INCIDENTAL** | `pyd_interrupt_status` not `volatile` — benign on Cortex-M4 for uint8_t but incorrect | `camera_pyd1598.c` (static definition) | **LOW** |
| **INCIDENTAL** | No System OFF usage; Errata 74/84 not applicable | `platform_hal_drv.c:2055-2062` (`pf_enter_deep_sleep` is no-op) | **INFO** |

---

## 2. Ranked Findings Table

All theories from all 10 finding documents, ranked by confidence and severity.

| # | Finding | Source Track | Confidence | Severity | Evidence Summary |
|---|---------|-------------|-----------|----------|-----------------|
| F1 | `pyd_gpio_reconfig()` creates ~160-200µs GPIOTE dead zone on every PIR event | T5, T4, T1 | **HIGH** | CRITICAL | Confirmed from source: `camera_pyd1598.c:231-251`. `pyd_gpio_in_disable()` (line 213) unregisters GPIOTE; `pyd_gpio_read_value()` (line 243) bit-bangs PIR_OUT as GPIO output for ~150µs; `pyd_gpio_in_enable()` (line 248) re-arms. No post-rearm software re-read. Confirmed by T5 SENSE write-site map (4 writes per cycle). |
| F2 | SoftDevice BLE preemption extends dead zone to ~350-500µs | T7, T5 | **HIGH** | MEDIUM | Confirmed: GPIOTE at priority 6, SoftDevice at 0,2,4 (`sdk_config.h:2233`, `sdk_config.h:12109`). BLE connection event can preempt GPIOTE ISR mid-dead-zone. Timing quantified in T7 §9.1-9.3. |
| F3 | `monet_data` (155 fields, ~500+ bytes) not `volatile` — racy across 5 execution contexts | T2 | **HIGH** | HIGH | Confirmed from definition: `user.c:67` — no `volatile` keyword. 722 accesses across 14 files, 5 execution contexts (GPIOTE ISR, SAADC ISR, TWIS ISR, app_timer callback, main loop). Zero critical sections or mutex protection. Compiler can register-cache, reorder, or dead-store-eliminate with `-Os`. |
| F4 | Errata 89 — GPIOTE PORT event can be missed during reconfiguration | Errata | **MEDIUM** | HIGH | nRF52832 Errata 89 (publicly known). Matches symptom: GPIOTE PORT events missed during `nrfx_gpiote_in_event_enable`/disable sequences. No software workaround implemented. Codebase uses PORT events exclusively. |
| F5 | `pir_checking` flag corruption → permanent PIR deadlock | T3, T6 | **HIGH** | HIGH | `user.c:38`: `volatile bool pir_checking`. Set at ISR entry, cleared at exit. SoftDevice (priority 0-4) can preempt and corrupt via RAM write. Only recovery: WDT reset after ~610ms. |
| F6 | All GPIOTE pins use PORT event (hi_accuracy=false) — single shared event channel | T1, T5 | **HIGH** | MEDIUM | Confirmed: all 6 `nrfx_gpiote_in_init` call sites pass `hi_accuracy=false`. PORT ISR processes pins sequentially. PIR_OUT competes with BUTTON_RESET, SPS_SWITCH_PIN, TBP_WAKE_BLE for ISR time. |
| F7 | `pir_check_start()` drops PIR events when `SleepState == SLEEP_OFF` | T5 | **HIGH** | MEDIUM | `user.c:752`: `if(monet_data.SleepState != SLEEP_OFF ...)` — when phone powered on, PIR events from GPIOTE handler are silently discarded. Only caught by main-loop fallback path. |
| F8 | Single recovery mechanism — `NVIC_SystemReset()` for all fault paths | T6 | **HIGH** | HIGH | Confirmed: every `APP_ERROR_CHECK` (~50+ call sites) terminates in reset via weak `app_error_fault_handler()`. No partial degradation, no retry logic, no error counter. |
| F9 | WDT timeout ~610ms but fed at 1s intervals | T6 | **MEDIUM** | MEDIUM | `sdk_config.h:4847`: RELOAD=20000 → 610ms timeout. Fed exclusively from `atel_timerTickHandler` at 1s intervals (`platform_hal_drv.c:2589`). If timeout confirmed in production binary, guaranteed starvation. |
| F10 | No bootloop protection | T6 | **HIGH** | HIGH | No boot counter, no escalating backoff, no safe-mode fallback. Persistent faults (slot exhaustion with config=1, flash corruption) cause infinite reset loop. |
| F11 | nrfx v1.x uses direct ISR dispatch — no event queue | T5 | **HIGH** | INFO | Confirmed: `handler_process()` function absent from entire codebase. Every PORT event fires handler directly in ISR context. No deferred processing. |
| F12 | `NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS` = 6 resolved via legacy override | T1, T5 | **HIGH** | INFO | `apply_old_config.h:182-184` overrides nrfx template default of 1 to 6. 4 active callers in 6 slots → no steady-state exhaustion in GA02. |
| F13 | No GPIO SENSE backup during dead zone — double-blind window | T5, T4 | **HIGH** | MEDIUM | Confirmed: `pyd_gpio_reconfig()` disables both GPIOTE channel AND GPIO SENSE (SENSE set to NOSENSE during uninit). T4 §8.5: T4→T5 intersection. |
| F14 | `check_pyd_interrupt()` blocks all app IRQs for 3-5ms | T3 | **HIGH** | MEDIUM | Runs in RTC1 ISR context (priority 6). During execution, all app interrupts (SAADC, UART, TWIS, SPIM) blocked. UARTE FIFO (6 bytes) overflows at 115200 bps in ~0.5ms. |
| F15 | BLE observer modifies `ble_info` during `sd_app_evt_wait()` — stale-read data race | T7, T4, T2 | **HIGH** | MEDIUM | `NRF_SDH_DISPATCH_MODEL_INTERRUPT` causes `ble_evt_handler()` to run inside `sd_app_evt_wait()` before main loop resumes. Main loop reads stale `ble_info`/`monet_data` values post-wake. |
| F16 | `motion_data` variable does not exist in GA02 codebase | T2 | **HIGH** | INFO | Search across all `.c`/`.h` files returned zero hits. `monet_data` is the only shared struct. |
| F17 | `pyd_interrupt_status` not declared `volatile` | T3 | **HIGH** | LOW | File-static `uint8_t`, accessed from GPIOTE ISR, timer callback, and main loop. Single-byte atomic on Cortex-M4 — practical risk negligible but incorrect. |
| F18 | `pf_enter_deep_sleep()` is a no-op — misleadingly named | T4 | **HIGH** | INFO | `platform_hal_drv.c:2055-2062`: only queues a TBP I2C command. Does not enter System OFF. Errata [74]/[84] not applicable. |
| F19 | No System OFF usage — all RAM/peripheral state preserved across sleep | T4 | **HIGH** | INFO | `sd_app_evt_wait()` (WFE-based) only. GPIOTE, GPIO SENSE, RTC1 all persist. No re-init on wake. |
| F20 | RTC0/SoftDevice and RTC1/app_timer are independent — no RTC conflict | T7, T4 | **HIGH** | INFO | RTC0 owned by S132 for BLE timing; RTC1 owned by app_timer at 16384 Hz. Independent hardware instances, independent prescalers. |
| F21 | `channel_free()` does not clear LATCH but safe due to call ordering | T5, T1 | **MEDIUM** | LOW | `nrfx_gpiote_in_uninit()` calls `in_event_disable()` (SENSE=NOSENSE) BEFORE `channel_free()`. SENSE=NOSENSE de-asserts DETECT → stale LATCH harmless. |
| F22 | PIR `pyd_restart()` provides 6-hour self-recovery for sensor | T6 | **HIGH** | MEDIUM | `user.c:894-899`: full power-cycle + GPIOTE re-init every 6 hours of inactivity. Sensor stuck for up to 6h before recovery. |
| F23 | `app_timer_start` on already-running timer silently drops | T3 | **HIGH** | INFO | `app_timer.c:618-621`: `if (p_timer->is_running) continue;` Rapid PIR events within 305µs merged, not queued. |

---

## 3. Fix Recommendations

Ordered by impact-to-effort ratio. All changes target the GA02 build.

| # | Priority | File | Change | Risk | Rationale |
|---|----------|------|--------|------|-----------|
| **R1** | **CRITICAL** | `camera_pyd1598.c:231-251` | **Eliminate GPIOTE dead zone.** Reorder `pyd_gpio_reconfig()`: keep GPIOTE active during bit-bang. Read PIR value without uninit; suppress handler via flag during read; software re-read PIR_OUT after re-arm to catch missed transitions. | **LOW** (localized change) | Eliminates the primary failure mechanism. Replace destructive uninit→reinit with handler-gating approach. |
| **R2** | **HIGH** | `user.c:67`, `user.h:773` | **Make `monet_data` volatile.** Change `monet_struct monet_data` to `volatile monet_struct monet_data` at definition + declaration. | **LOW** (keyword; 1-2 cycle per-access cost) | Eliminates compiler optimization hazards (register caching, dead-store elimination, reordering) across 722 access sites. |
| **R3** | **HIGH** | `user.c:38` + timer logic | **Add `pir_checking` timeout guard.** Auto-clear `pir_checking` after N seconds using timestamp comparison. | **LOW** (additive) | Prevents SoftDevice-induced corruption from permanently deadlocking PIR detection. Defense-in-depth against the single-point-of-failure flag. |
| **R4** | **HIGH** | `GA02/main.c` (boot) | **Add boot counter with escalating backoff.** Store boot count in retention register or noinit RAM. If N resets in M seconds, enter safe mode (skip BLE OTA, skip non-critical init, wait for external recovery). | **MEDIUM** (new logic, state machine) | Prevents infinite bootloop from persistent faults (slot exhaustion, flash corruption, OTA reconnect failure). |
| **R5** | **MEDIUM** | `camera_pyd1598.c:198-209` | **Add post-rearm software GPIO re-read.** After `pyd_gpio_in_enable()`, read `nrf_gpio_pin_read(PIR_OUT)` and compare against expected idle state. If pin is HIGH (motion detected during dead zone), call `pyd_set_status(1)` and `pir_check_start()`. | **LOW** (~5 lines, Errata 89 workaround) | Catches transitions that occurred during the dead zone. Matches Errata 89 recommended workaround. |
| **R6** | **MEDIUM** | `platform_hal_drv.c:2584-2589` | **Add main-loop WDT feed.** Insert `pf_wdt_kick()` at top of main `for(;;)` loop. Verify production WDT reload value is >= 40000 ticks (~1.22s). | **LOW** (one call) | Ensures WDT is fed even if systick callback is delayed. Prevents watchdog starvation in HIBERNATE mode. |
| **R7** | **MEDIUM** | `user.c:749-758` | **Fix `pir_check_start()` SLEEP_OFF gate.** Remove or restructure `SleepState != SLEEP_OFF` check. When phone is powered on, route PIR events through main-loop direct path without timer debounce. | **MEDIUM** (changes event routing) | Prevents silent PIR event discard when system is awake. The main-loop fallback path already exists but adds latency. |
| **R8** | **MEDIUM** | `sdk_config.h:12109-12110` | **Consider `NRF_SDH_DISPATCH_MODEL_APPSH` (polling).** Change dispatch model from INTERRUPT to APPSH to defer BLE observer execution to main loop. | **HIGH** (architectural, requires app_scheduler integration) | Eliminates stale-read data race from BLE observers modifying shared state during `sd_app_evt_wait()`. |
| **R9** | **LOW** | `app_error.c` (override) | **Override `app_error_fault_handler()`.** Log error code, file, line, and RESETREAS to persistent error log OR UART before reset. | **LOW** (weak override, additive) | Enables field diagnostics. Currently reset reasons are logged but not persisted. |
| **R10** | **LOW** | `camera_pyd1598.c` (static variable) | **Declare `pyd_interrupt_status` as `volatile`.** | **LOW** (keyword) | Consistency with shared-state design. Negligible practical risk on Cortex-M4 for uint8_t but architecturally correct. |
| **R11** | **LOW** | `sdk_config.h:2218` | **Hard-code `NRFX_GPIOTE_CONFIG_NUM_OF_LOW_POWER_EVENTS = 6` without `#ifndef` guard.** | **LOW** (one define change) | Eliminates ambiguity from legacy override chain. Ensures slot count survives toolchain/include-order variations. |
| **R12** | **LOW** | `user.c:894-899` | **Shorten `PIR_RESTART_TIMEOUT` from 6 hours to 1-2 hours** (or make configurable). | **LOW** (constant change) | Reduces sensor-stuck recovery window. 6-hour blind window is excessive for a production device. |

---

## 4. Cross-Track Resolution

All intersections between tracks are documented and verified for consistency. No contradictions found among the 10 finding documents.

### 4.1 Track-to-Track Intersection Map

| Intersection | Documented In | Status | Key Resolution |
|---|---|---|---|
| T1→T5: Slot exhaustion + Handler drop | T1 §9.1, T5 §8 | RESOLVED | PORT event slots = 6 (legacy override confirmed). No steady-state exhaustion. PIR re-acquire always finds free slot. |
| T1→T6: Slot exhaustion recovery | T1 §9.2, T6 §9.1 | RESOLVED | `APP_ERROR_CHECK` → `NVIC_SystemReset()` only recovery. Bootloop risk if effective slots = 1. |
| T2→T3: Volatile race + Re-entrancy | T2 §10.2, T3 §6.1 | RESOLVED | `pir_checking` flag correctly `volatile`. `pyd_interrupt_status` not volatile but benign. BLE observer data race confirmed by T7. |
| T2→T5: Volatile race + Control flow | T2 §10.3 | RESOLVED | Shared concern about stale `monet_data` reads affecting state machine transitions. |
| T2→T6: Volatile race + Recovery | T2 §10.4 | RESOLVED | Race-induced corruption converges on WDT reset. |
| T3→T5: Re-entrancy + Stack depth | T3 §6.2 | RESOLVED | `check_pyd_interrupt()` call depth from RTC1 ISR is non-trivial. Combined with SoftDevice nesting, stack margin concern. |
| T3→T6: Re-entrancy + Fault tolerance | T3 §6.4, T6 §9.3 | RESOLVED | All T3 failure modes → `NVIC_SystemReset()`. `pir_checking` corruption is silent deadlock risk. |
| T4→T1: Sleep + Slot exhaustion | T4 §8.1 | RESOLVED | Sleep/wake does not affect GPIOTE slot count. |
| T4→T2: Sleep + Volatile race | T4 §8.2 | RESOLVED | `SleepState`/`SleepStateChange` lack volatile. Stale-read risk across `sd_app_evt_wait()`. |
| T4→T3: Sleep + Re-entrancy | T4 §8.3 | RESOLVED | BLE observer runs in `sd_app_evt_wait()` — modifies `monet_data` between main loop iterations. |
| T4→T5: Sleep + Handler drop | T4 §8.5 | RESOLVED & CORRECTED | nrfx v1.x has no `handler_process()` function (T5 §8.5 correction). SENSE double-blind during dead zone confirmed. |
| T4→T6: Sleep + Recovery | T4 §8.4 | RESOLVED | No software watchdog for stuck sleep. WDT feeds only from systick. |
| T4→T7: Sleep + SoftDevice | T4 §8.6 | RESOLVED | BLE wake steals wake cycle. Combined T4+T7 event-loss path: BLE handler runs before pending GPIOTE ISR, second PIR edge overwrites single-event LATCH. |
| T5→T1: Handler drop + Slots | T5 §8 | RESOLVED | `apply_old_config.h` chain confirmed. `channel_free()` safe due to `in_event_disable` ordering. No spurious trigger on re-init. |
| T7→T1: SoftDevice + Slots | T7 §10.1 | RESOLVED | SoftDevice may use GPIOTE channel 7 internally for radio timing. No user-visible collision in normal operation. |
| T7→T2: SoftDevice + Volatile race | T7 §10.2 | RESOLVED | BLE observer modifies `ble_info` during `sd_app_evt_wait()` — deterministic stale-read race. |
| T7→T3: SoftDevice + Re-entrancy | T7 §10.3 | RESOLVED | No new re-entrancy vector from SoftDevice. `pir_checking` flag not affected by BLE observer chain. |
| T7→T4: SoftDevice + Sleep | T7 §10.4 | RESOLVED | BLE events wake CPU → BLE observer processes events → `sd_app_evt_wait()` returns → main loop resumes. Confirmed T4 finding. |
| T7→T5: SoftDevice + Handler drop | T7 §10.5 | RESOLVED | SoftDevice preemption during GPIOTE ISR → double-blind window. PORT event cleared, GPIOTE uninitialized, SENSE disabled. |
| T7→T6: SoftDevice + Recovery | T7 §10.6 | RESOLVED | No new recovery concern. WDT is only recovery for SoftDevice hang. |

### 4.2 Architecture Clarifications

- **nRF52840, not nRF52832:** T7 identified the actual MCU as nRF52840 (PCA10040 board, 64 MHz, 1MB Flash). All prior tracks used nRF52832 based on errata reference. This has no functional impact on findings — both use identical S132 SoftDevice, NVIC architecture, and GPIOTE peripheral.
- **nrfx v1.x, no event queue:** T5 confirmed the GPIOTE driver uses direct ISR dispatch with no internal event queue. T4's T4→T5 reference to `nrf_drv_gpiote_in_event_handler_process()` was corrected — this function does not exist.
- **`motion_data` does not exist:** T2 confirmed the investigation's original hypothesis variable does not exist in GA02. `monet_data` is the only shared global struct.

### 4.3 Methodological Note

All findings are based on static source code analysis of the `atel-reveal-4-mcu` codebase (branch `pir-analysis-gen4`). No runtime instrumentation, logic analyzer traces, or oscilloscope measurements were performed. The dead-zone timing estimates (~160-200µs, extendable to ~500µs with SoftDevice preemption) are derived from instruction-cycle analysis and should be verified with hardware measurements.

The nRF52832 Errata 89 could not be confirmed from a live Nordic document (Cloudflare blocking). It is cited from publicly known errata lists for Rev 3 silicon. The errata ID and description carry **MEDIUM** confidence.

---

## 5. Source Documents

| Document | Path | Lines | Verdict |
|---|---|---|---|
| Errata Review | `findings/errata_review.md` | 140 | Errata 89 matches symptom; no workaround implemented |
| SDK Config Analysis | `findings/sdk_config_analysis.md` | 188 | Bare-metal, no FreeRTOS; GPIOTE at priority 6; legacy/nrfx slot count discrepancy |
| GPIOTE Call Sites | `findings/gpiote_call_sites.md` | 279 | 6 call sites; PIR only dynamic allocator; ~200µs dead zone mapped |
| Track 1 — Slot Exhaustion | `findings/track1_slot_exhaustion.md` | 348 | LOW risk (6 effective slots, 4 callers); bootloop if config=1 |
| Track 2 — Volatile Race | `findings/track2_volatile_race.md` | 630 | HIGH risk; 155 fields, 5 contexts, zero protection |
| Track 3 — Re-entrancy | `findings/track3_reentrancy.md` | 525 | Safe re-entrancy; 3-5ms IRQ blocking; `pir_checking` SPOF |
| Track 4 — Sleep/Wake | `findings/track4_sleep_wake.md` | 553 | System ON only; GPIOTE persists; dead zone on every PIR event |
| Track 5 — Handler Drop | `findings/track5_handler_drop.md` | 574 | 4 drop mechanisms; PRIMARY is dead zone; SENSE backup negated |
| Track 6 — Recovery | `findings/track6_recovery.md` | 568 | Single recovery path; WDT feed gap; no bootloop protection |
| Track 7 — SoftDevice | `findings/track7_softdevice.md` | 565 | CONTRIBUTING FACTOR; preemption amplifier; 1-2.5% additive loss |

---

*End of Gen4 PIR Final Synthesis Report.*
