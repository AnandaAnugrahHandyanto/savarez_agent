import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  $approvalInView,
  onScrollToApprovalRequest,
  requestScrollToApproval,
  resetApprovalInView,
  setApprovalInView
} from '@/store/approval-scroll'
import { clearAllPrompts, setApprovalRequest } from '@/store/prompts'
import { $activeSessionId } from '@/store/session'

import { ScrollToApprovalButton } from './scroll-to-approval-button'

function setRequest() {
  $activeSessionId.set('sess-1')
  setApprovalRequest({ command: 'rm -rf /tmp/x', description: 'dangerous command', sessionId: 'sess-1' })
}

afterEach(() => {
  cleanup()
  clearAllPrompts()
  resetApprovalInView()
  $activeSessionId.set(null)
})

// `getByRole('button')` excludes aria-hidden nodes, so "queryByRole null" is the
// pill's hidden state. The pill shows iff an approval is pending AND its inline
// bar is scrolled out of view ($approvalInView === false).
describe('ScrollToApprovalButton', () => {
  it('stays hidden when no approval is pending', () => {
    setApprovalInView(false)
    render(<ScrollToApprovalButton />)

    expect(screen.queryByRole('button')).toBeNull()
  })

  it('stays hidden while the inline bar is still mounted and visible', () => {
    setRequest()
    setApprovalInView(true)
    render(<ScrollToApprovalButton />)

    expect(screen.queryByRole('button')).toBeNull()
  })

  it('stays hidden before the bar has reported visibility (null)', () => {
    setRequest()
    render(<ScrollToApprovalButton />)

    expect(screen.queryByRole('button')).toBeNull()
  })

  it('surfaces only when a pending approval is scrolled out of view', () => {
    setRequest()
    setApprovalInView(false)
    render(<ScrollToApprovalButton />)

    expect(screen.getByRole('button', { name: /Approval needed/ })).toBeTruthy()
  })

  it('fires a scroll-to-approval request on click', () => {
    const handler = vi.fn()
    const stop = onScrollToApprovalRequest(handler)
    setRequest()
    setApprovalInView(false)
    render(<ScrollToApprovalButton />)

    fireEvent.click(screen.getByRole('button', { name: /Approval needed/ }))

    expect(handler).toHaveBeenCalledTimes(1)
    stop()
  })
})

describe('approval-scroll store', () => {
  it('skips no-op writes and round-trips null/true/false', () => {
    const seen: (boolean | null)[] = []
    const unsub = $approvalInView.listen(value => seen.push(value))

    setApprovalInView(false)
    setApprovalInView(false)
    setApprovalInView(true)
    resetApprovalInView()
    unsub()

    expect(seen).toEqual([false, true, null])
  })

  it('drops a scroll handler once it is unregistered', () => {
    const handler = vi.fn()
    const stop = onScrollToApprovalRequest(handler)

    requestScrollToApproval()
    stop()
    requestScrollToApproval()

    expect(handler).toHaveBeenCalledTimes(1)
  })
})
