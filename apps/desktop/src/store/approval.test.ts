import { afterEach, describe, expect, it } from 'vitest'

import { $approvalRequest, clearApprovalRequest, setApprovalRequest } from './approval'

afterEach(() => {
  $approvalRequest.set(null)
})

describe('approval store', () => {
  it('stores the latest approval request', () => {
    setApprovalRequest({ command: 'rm -rf old', description: 'recursive delete', sessionId: 'sess-1' })

    expect($approvalRequest.get()).toEqual({
      command: 'rm -rf old',
      description: 'recursive delete',
      sessionId: 'sess-1'
    })
  })

  it('clears unconditionally when no sessionId is supplied', () => {
    setApprovalRequest({ command: 'a', description: 'b', sessionId: 'sess-1' })
    clearApprovalRequest()

    expect($approvalRequest.get()).toBeNull()
  })

  it('only clears when the sessionId matches, guarding against a stale race', () => {
    setApprovalRequest({ command: 'a', description: 'b', sessionId: 'sess-1' })

    clearApprovalRequest('sess-2')
    expect($approvalRequest.get()).not.toBeNull()

    clearApprovalRequest('sess-1')
    expect($approvalRequest.get()).toBeNull()
  })
})
