import { atom, computed } from 'nanostores'

import type { OverlayState } from './interfaces.js'

const buildOverlayState = (): OverlayState => ({
  agents: false,
  agentsInitialHistoryIndex: 0,
  approval: null,
  clarify: null,
  confirm: null,
  modelPicker: false,
  pager: null,
  picker: false,
  secret: null,
  skillsHub: false,
  sudo: null
})

export const $overlayState = atom<OverlayState>(buildOverlayState())

/** Increments on every overlay mutation for tests and optional subscribers (cross-backend render sequencing). */
export const $overlayRevision = atom(0)

export const $isBlocked = computed(
  $overlayState,
  ({ agents, approval, clarify, confirm, modelPicker, pager, picker, secret, skillsHub, sudo }) =>
    Boolean(agents || approval || clarify || confirm || modelPicker || pager || picker || secret || skillsHub || sudo)
)

export const getOverlayState = () => $overlayState.get()

export const patchOverlayState = (next: Partial<OverlayState> | ((state: OverlayState) => OverlayState)) => {
  const prev = $overlayState.get()
  const merged = typeof next === 'function' ? next(prev) : { ...prev, ...next }

  $overlayState.set(merged)
  $overlayRevision.set($overlayRevision.get() + 1)
}

/** Full reset — used by session/turn teardown and tests. */
export const resetOverlayState = () => {
  $overlayState.set(buildOverlayState())
  $overlayRevision.set($overlayRevision.get() + 1)
}

/**
 * Soft reset: drop FLOW-scoped overlays (approval / clarify / confirm / sudo
 * / secret / pager) but PRESERVE user-toggled ones — agents dashboard, model
 * picker, skills hub, session picker.  Those are opened deliberately and
 * shouldn't vanish when a turn ends.  Called from turnController.idle() on
 * every turn completion / interrupt; the old "reset everything" behaviour
 * silently closed /agents the moment delegation finished.
 */
export const resetFlowOverlays = () => {
  const prev = $overlayState.get()
  $overlayState.set({
    ...buildOverlayState(),
    agents: prev.agents,
    agentsInitialHistoryIndex: prev.agentsInitialHistoryIndex,
    modelPicker: prev.modelPicker,
    picker: prev.picker,
    skillsHub: prev.skillsHub
  })
  $overlayRevision.set($overlayRevision.get() + 1)
}
