import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const createCustomProvider = vi.fn()
const deleteEnvVar = vi.fn()
const getEnvVars = vi.fn()
const listOAuthProviders = vi.fn()
const revealEnvVar = vi.fn()
const setEnvVar = vi.fn()

vi.mock('@/hermes', () => ({
  createCustomProvider: (body: unknown) => createCustomProvider(body),
  deleteEnvVar: (key: string) => deleteEnvVar(key),
  getEnvVars: () => getEnvVars(),
  listOAuthProviders: () => listOAuthProviders(),
  revealEnvVar: (key: string) => revealEnvVar(key),
  setEnvVar: (key: string, value: string) => setEnvVar(key, value)
}))

vi.mock('@/store/notifications', () => ({
  notify: vi.fn(),
  notifyError: vi.fn()
}))

beforeEach(() => {
  createCustomProvider.mockResolvedValue({
    ok: true,
    provider: 'ai-router',
    slug: 'ai-router',
    key_env: 'CUSTOM_PROVIDER_AI_ROUTER_API_KEY',
    model: 'openai/gpt-4.1-mini',
    models: ['openai/gpt-4.1-mini']
  })
  getEnvVars.mockResolvedValue({})
  listOAuthProviders.mockResolvedValue({ providers: [] })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

async function renderProvidersSettings() {
  const { ProvidersSettings } = await import('./providers-settings')

  return render(<ProvidersSettings onViewChange={vi.fn()} view="keys" />)
}

describe('ProvidersSettings', () => {
  it('saves a custom provider from the API keys settings view', async () => {
    await renderProvidersSettings()

    const keyInput = await screen.findByPlaceholderText('Paste custom provider key')
    expect(keyInput).toBeTruthy()
    expect(screen.queryByLabelText('Base URL')).toBeNull()

    fireEvent.click(await screen.findByRole('button', { name: /Custom provider/i }))
    fireEvent.change(screen.getByLabelText('Base URL'), { target: { value: 'https://ai-router.app/v1' } })
    fireEvent.change(keyInput, { target: { value: 'router-secret' } })

    expect(screen.queryByLabelText('Provider name')).toBeNull()
    expect(screen.queryByLabelText('Model')).toBeNull()
    expect(screen.queryByLabelText('Key environment variable')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: /Save custom provider/i }))

    await waitFor(() =>
      expect(createCustomProvider).toHaveBeenCalledWith({
        api_key: 'router-secret',
        base_url: 'https://ai-router.app/v1'
      })
    )
  })
})
