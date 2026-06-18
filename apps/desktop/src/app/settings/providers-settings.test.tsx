import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { atom } from 'nanostores'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { OAuthProvider } from '@/types/hermes'

const listOAuthProviders = vi.fn()
const disconnectOAuthProvider = vi.fn()
const getEnvVars = vi.fn()
const startManualProviderOAuth = vi.fn()
const onboarding = atom({ manual: false })
const runInTerminal = vi.fn()
const notify = vi.fn()
const desktopWindow = window as unknown as { hermesDesktop?: Window['hermesDesktop'] }
const initialHermesDesktop = desktopWindow.hermesDesktop

vi.mock('@/hermes', () => ({
  disconnectOAuthProvider: (providerId: string) => disconnectOAuthProvider(providerId),
  getEnvVars: () => getEnvVars(),
  listOAuthProviders: () => listOAuthProviders()
}))

vi.mock('@/app/right-sidebar/store', () => ({
  runInTerminal: (command: string) => runInTerminal(command)
}))

vi.mock('@/store/notifications', () => ({
  notify: (toast: unknown) => notify(toast),
  notifyError: vi.fn()
}))

vi.mock('@/store/onboarding', () => ({
  $desktopOnboarding: onboarding,
  startManualProviderOAuth: (providerId: string) => startManualProviderOAuth(providerId)
}))

function provider(id: string, loggedIn: boolean, patch: Partial<OAuthProvider> = {}): OAuthProvider {
  return {
    cli_command: `hermes auth add ${id}`,
    disconnectable: true,
    docs_url: '',
    flow: 'device_code',
    id,
    name: id === 'nous' ? 'Nous Portal' : 'MiniMax',
    status: {
      logged_in: loggedIn
    },
    ...patch
  }
}

beforeEach(() => {
  onboarding.set({ manual: false })
  getEnvVars.mockResolvedValue({})
  disconnectOAuthProvider.mockResolvedValue({ ok: true, provider: 'nous' })
  listOAuthProviders.mockResolvedValue({
    providers: [provider('nous', true), provider('minimax-oauth', false)]
  })
  vi.spyOn(window, 'confirm').mockReturnValue(true)
})

afterEach(() => {
  cleanup()
  desktopWindow.hermesDesktop = initialHermesDesktop
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

async function renderProvidersSettings() {
  const { ProvidersSettings } = await import('./providers-settings')

  return render(<ProvidersSettings onClose={vi.fn()} onViewChange={vi.fn()} view="accounts" />)
}

describe('ProvidersSettings', () => {
  it('disconnects a connected provider account and refreshes the accounts list', async () => {
    await renderProvidersSettings()

    const remove = await screen.findByRole('button', { name: 'Remove Nous Portal' })
    fireEvent.click(remove)

    await waitFor(() => expect(disconnectOAuthProvider).toHaveBeenCalledWith('nous'))
    expect(listOAuthProviders).toHaveBeenCalledTimes(2)
  })

  it('keeps provider selection separate from account removal', async () => {
    await renderProvidersSettings()

    fireEvent.click(await screen.findByText('Nous Portal'))

    expect(startManualProviderOAuth).toHaveBeenCalledWith('nous')
    expect(disconnectOAuthProvider).not.toHaveBeenCalled()
  })

  it('does not offer removal for externally managed providers', async () => {
    listOAuthProviders.mockResolvedValue({
      providers: [
        provider('qwen-oauth', true, {
          cli_command: 'hermes auth add qwen-oauth',
          disconnect_hint: 'Use `hermes auth add qwen-oauth` or that provider\'s CLI to remove it.',
          disconnectable: false,
          flow: 'external',
          name: 'Qwen (via Qwen CLI)'
        })
      ]
    })

    await renderProvidersSettings()

    expect(await screen.findByText('Qwen Code')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Remove Qwen Code' })).toBeNull()
    expect(screen.getByText(/managed by its own CLI/)).toBeTruthy()
  })

  it('keeps Claude Code OAuth caveat visible on unconnected provider rows without using it as the title', async () => {
    listOAuthProviders.mockResolvedValue({
      providers: [
        provider('claude-code', false, {
          cli_command: 'claude setup-token',
          description: 'Requires extra usage credits on top of a Claude Max plan.',
          disconnectable: false,
          docs_url: 'https://docs.claude.com/en/docs/claude-code',
          flow: 'external',
          name: 'Anthropic OAuth: Required Extra Usage Credits to Use Subscription'
        })
      ]
    })

    await renderProvidersSettings()

    fireEvent.click(await screen.findByRole('button', { name: /Other providers/ }))

    expect(await screen.findByText('Anthropic OAuth (Claude Code)')).toBeTruthy()
    expect(screen.queryByText(/Required Extra Usage Credits to Use Subscription/)).toBeNull()
    expect(screen.getByText(/Requires extra usage credits on top of a Claude Max plan/)).toBeTruthy()
  })

  it('keeps Claude Code OAuth caveat out of the connected title and raw command out of the confirmation', async () => {
    const onClose = vi.fn()
    const command = 'security delete-generic-password -s "Claude Code-credentials" 2>/dev/null; rm -f ~/.claude/.credentials.json'
    desktopWindow.hermesDesktop = { terminal: {} } as Window['hermesDesktop']
    listOAuthProviders.mockResolvedValue({
      providers: [
        provider('claude-code', true, {
          cli_command: 'claude setup-token',
          description: 'Requires extra usage credits on top of a Claude Max plan.',
          disconnect_command: command,
          disconnectable: false,
          docs_url: 'https://docs.claude.com/en/docs/claude-code',
          flow: 'external',
          name: 'Anthropic OAuth: Required Extra Usage Credits to Use Subscription'
        })
      ]
    })

    const { ProvidersSettings } = await import('./providers-settings')
    render(<ProvidersSettings onClose={onClose} onViewChange={vi.fn()} view="accounts" />)

    expect(await screen.findByText('Anthropic OAuth (Claude Code)')).toBeTruthy()
    expect(screen.queryByText(/Required Extra Usage Credits to Use Subscription/)).toBeNull()
    expect(screen.getByText(/Requires extra usage credits on top of a Claude Max plan/)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Disconnect Anthropic OAuth (Claude Code)' }))

    expect(window.confirm).toHaveBeenCalledWith(
      'Disconnect Anthropic OAuth (Claude Code)? This will remove the saved credentials for Anthropic OAuth (Claude Code). The removal command runs in the embedded terminal so you can review exactly what executes.'
    )
    expect(window.confirm).not.toHaveBeenCalledWith(expect.stringContaining(command))
    expect(onClose).toHaveBeenCalled()
    expect(runInTerminal).toHaveBeenCalledWith(command)
    expect(notify).toHaveBeenCalledWith(expect.objectContaining({ message: 'Running Anthropic OAuth (Claude Code) disconnect in the terminal…' }))
  })
})
