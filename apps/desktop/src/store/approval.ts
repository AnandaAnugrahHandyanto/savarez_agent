import { atom } from 'nanostores'

// The four choices the backend accepts for `approval.respond` (see
// tools/approval.py:resolve_gateway_approval and the TUI's approvalAction:
// 1→once, 2→session, 3→always, 4/escape→deny).
export type ApprovalChoice = 'always' | 'deny' | 'once' | 'session'

export interface ApprovalRequest {
  command: string
  description: string
  sessionId: string | null
}

// Holds the most recent in-flight dangerous-command approval. The
// ApprovalOverlay reads this to render the modal and to know which
// session_id to echo back over `approval.respond`. The Python agent thread
// is blocked in tools/approval.py:_await_gateway_decision until a choice
// arrives — silence denies on timeout — so without surfacing this, a desktop
// user never sees the gate and every dangerous command times out.
// Backend emits it via tui_gateway/server.py:578
// (register_gateway_notify → _emit('approval.request', sid, {command, description})).
export const $approvalRequest = atom<ApprovalRequest | null>(null)

export function setApprovalRequest(request: ApprovalRequest): void {
  $approvalRequest.set(request)
}

export function clearApprovalRequest(sessionId?: string): void {
  const current = $approvalRequest.get()

  if (!current) {
    return
  }

  // Guard against a stale clear racing a newer request for a different
  // session (e.g. two sessions each hitting a gate in quick succession).
  if (sessionId && current.sessionId !== sessionId) {
    return
  }

  $approvalRequest.set(null)
}
