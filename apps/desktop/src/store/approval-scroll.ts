import { atom } from 'nanostores'

// The inline Run/Reject approval bar is the single response surface for a
// dangerous-command / execute_code approval, and it lives deep in the thread
// transcript on the pending tool row. The "jump to approval" pill lives by the
// composer (OUTSIDE that subtree), so the bar mirrors its own viewport
// visibility here — via an IntersectionObserver — and registers a
// scroll-into-view handler the pill fires. Mirrors the thread-scroll jump-button
// bridge; deliberately NOT a second approve/reject surface.
//
//   null  → no inline bar mounted (nothing to jump to)
//   false → mounted but scrolled out of view  → show the pill
//   true  → mounted and visible               → hide the pill
export const $approvalInView = atom<boolean | null>(null)

// Skip no-op writes so the pill doesn't churn on every IntersectionObserver tick.
const setInView = (value: boolean | null) => {
  if ($approvalInView.get() !== value) {
    $approvalInView.set(value)
  }
}

export const setApprovalInView = (visible: boolean) => setInView(visible)
export const resetApprovalInView = () => setInView(null)

// Cross-subtree bridge: the pill fires; the inline bar (which owns the DOM node)
// scrolls itself into view. Mirrors thread-scroll's `onScrollToBottomRequest`.
const handlers = new Set<() => void>()

export const onScrollToApprovalRequest = (handler: () => void) => {
  handlers.add(handler)

  return () => void handlers.delete(handler)
}

export const requestScrollToApproval = () => handlers.forEach(handler => handler())
