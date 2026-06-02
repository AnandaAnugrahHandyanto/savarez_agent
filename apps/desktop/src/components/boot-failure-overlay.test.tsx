import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { DesktopConnectionConfig } from '@/global'
import { $desktopBoot, failDesktopBoot } from '@/store/boot'
import { $desktopOnboarding } from '@/store/onboarding'

import { BootFailureOverlay } from './boot-failure-overlay'

// Unique to the env-override guidance — the boot error box also echoes the env
// var names, so match on this sentence to avoid colliding with it.
const ENV_GUIDANCE = /switching to the local gateway from here won't help/i

const desktopWindow = window as unknown as { hermesDesktop?: Window['hermesDesktop'] }
const initialHermesDesktop = desktopWindow.hermesDesktop

function connectionConfig(partial: Partial<DesktopConnectionConfig> = {}): DesktopConnectionConfig {
  return {
    envOverride: false,
    mode: 'local',
    remoteTokenPreview: null,
    remoteTokenSet: false,
    remoteUrl: '',
    ...partial
  }
}

function installDesktopBridge(config: DesktopConnectionConfig) {
  desktopWindow.hermesDesktop = {
    applyConnectionConfig: vi.fn().mockResolvedValue(config),
    getConnectionConfig: vi.fn().mockResolvedValue(config),
    getRecentLogs: vi.fn().mockResolvedValue({ path: '', lines: [] }),
    repairBootstrap: vi.fn().mockResolvedValue({ ok: true }),
    resetBootstrap: vi.fn().mockResolvedValue({ ok: true }),
    revealLogs: vi.fn().mockResolvedValue({ ok: true, path: '' })
  } as unknown as Window['hermesDesktop']
}

beforeEach(() => {
  $desktopOnboarding.set({
    configured: true,
    flow: { status: 'idle' },
    mode: 'oauth',
    providers: null,
    reason: null,
    requested: false,
    manual: false
  })
  failDesktopBoot('HERMES_DESKTOP_REMOTE_URL is set but HERMES_DESKTOP_REMOTE_TOKEN is not.')
})

afterEach(() => {
  vi.restoreAllMocks()
  cleanup()
  $desktopBoot.set({
    error: null,
    fakeMode: false,
    message: '',
    phase: 'renderer.ready',
    progress: 100,
    running: false,
    timestamp: 0,
    visible: false
  })

  if (initialHermesDesktop) {
    desktopWindow.hermesDesktop = initialHermesDesktop
  } else {
    delete desktopWindow.hermesDesktop
  }
})

describe('BootFailureOverlay', () => {
  it('offers the local-gateway recovery when no env override is forcing remote mode', async () => {
    installDesktopBridge(connectionConfig({ envOverride: false }))

    render(<BootFailureOverlay />)

    expect(await screen.findByRole('button', { name: 'Use local gateway' })).toBeTruthy()
    expect(screen.queryByText(ENV_GUIDANCE)).toBeNull()
  })

  it('hides the dead local-gateway button and explains the env override when remote is forced', async () => {
    installDesktopBridge(connectionConfig({ envOverride: true, mode: 'remote', remoteUrl: 'https://gw.example.com' }))

    render(<BootFailureOverlay />)

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Use local gateway' })).toBeNull()
    })
    expect(screen.getByText(ENV_GUIDANCE)).toBeTruthy()
  })
})
