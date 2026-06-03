import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApprovalOverlay } from '@/components/approval-overlay'
import type { HermesGateway } from '@/hermes'
import { $approvalRequest, setApprovalRequest } from '@/store/approval'
import { setGateway } from '@/store/gateway'

const request = vi.fn()

function mockGateway(): void {
  setGateway({ request } as unknown as HermesGateway)
}

function open(command = 'rm -rf /tmp/old', sessionId: string | null = 'sess-1'): void {
  act(() => {
    setApprovalRequest({ command, description: 'recursive delete', sessionId })
  })
}

beforeEach(() => {
  request.mockResolvedValue({ ok: true })
})

afterEach(() => {
  cleanup()
  act(() => {
    $approvalRequest.set(null)
  })
  setGateway(null)
  vi.clearAllMocks()
})

describe('ApprovalOverlay', () => {
  it('renders nothing when there is no pending approval', () => {
    const { container } = render(<ApprovalOverlay />)

    expect(container.firstChild).toBeNull()
  })

  it('surfaces the command and description once a request arrives', () => {
    render(<ApprovalOverlay />)
    open()

    expect(screen.getByText('recursive delete')).toBeTruthy()
    expect(screen.getByText('rm -rf /tmp/old')).toBeTruthy()
  })

  it('sends approval.respond with the chosen action and clears the request', async () => {
    mockGateway()
    render(<ApprovalOverlay />)
    open()

    fireEvent.click(screen.getByText('Approve once'))

    await waitFor(() =>
      expect(request).toHaveBeenCalledWith('approval.respond', { choice: 'once', session_id: 'sess-1' })
    )
    await waitFor(() => expect($approvalRequest.get()).toBeNull())
  })

  it('denies on Escape as the safe default', async () => {
    mockGateway()
    render(<ApprovalOverlay />)
    open()

    fireEvent.keyDown(window, { key: 'Escape' })

    await waitFor(() =>
      expect(request).toHaveBeenCalledWith('approval.respond', { choice: 'deny', session_id: 'sess-1' })
    )
  })

  it('does not dispatch when the gateway is disconnected', () => {
    render(<ApprovalOverlay />)
    open()

    fireEvent.click(screen.getByText('Always allow'))

    expect(request).not.toHaveBeenCalled()
    // Request stays open so the user can retry once the gateway reconnects.
    expect($approvalRequest.get()).not.toBeNull()
  })
})
