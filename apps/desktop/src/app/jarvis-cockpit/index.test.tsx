import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.fn()
const openExternal = vi.fn()

const cockpitResponse = {
  status: 'ok',
  updated_at: '2026-06-07T10:00:00+02:00',
  dispatch_boundary: {
    dispatch_embedded: false,
    dispatch_url: 'http://127.0.0.1:3001',
    rule: 'Dispatch stays in real Dispatch Dashboard'
  },
  jarvis_todo: [{ id: 'cockpit-local-report', title: 'Regenerate local Cockpit report', status: 'todo' }],
  gates: [],
  status_cards: [],
  artifacts: [],
  sources: [],
  missing: [],
  safety: {
    read_only: true,
    microsoft_writes: false,
    blikk_writes: false,
    mail_mutation: false,
    secrets_read: false,
    dispatch_embedded: false
  }
}

beforeEach(() => {
  api.mockImplementation(({ method, path }: { method?: string; path: string }) => {
    if (path === '/api/jarvis/cockpit/local-report' && method === 'POST') {
      return Promise.resolve({
        status: 'ok',
        report_path: '/tmp/jarvis-cockpit-local-report.md',
        safety: { local_only: true, external_writes: false }
      })
    }
    if (path === '/api/jarvis/cockpit') {
      return Promise.resolve(cockpitResponse)
    }
    return Promise.reject(new Error(`unexpected api call: ${method || 'GET'} ${path}`))
  })
  Object.defineProperty(window, 'hermesDesktop', {
    configurable: true,
    value: { api, openExternal }
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('JarvisCockpitView', () => {
  it('generates a local-only cockpit report via the safe POST endpoint', async () => {
    const { JarvisCockpitView } = await import('./index')

    render(<JarvisCockpitView />)

    const button = await screen.findByRole('button', { name: /generate local report/i })
    fireEvent.click(button)

    await waitFor(() =>
      expect(api).toHaveBeenCalledWith({ path: '/api/jarvis/cockpit/local-report', method: 'POST' })
    )
    expect(await screen.findByText(/Local report created/i)).toBeTruthy()
  })
})
