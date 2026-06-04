import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { $desktopOnboarding, type DesktopOnboardingState, type OnboardingContext } from '@/store/onboarding'
import type { OAuthProvider } from '@/types/hermes'

import { Picker } from './desktop-onboarding-overlay'

function provider(id: string, name = id): OAuthProvider {
  return {
    cli_command: `hermes login ${id}`,
    docs_url: `https://example.com/${id}`,
    flow: 'pkce',
    id,
    name,
    status: { logged_in: false }
  }
}

function setProviders(providers: OAuthProvider[]) {
  $desktopOnboarding.set({
    configured: false,
    flow: { status: 'idle' },
    mode: 'oauth',
    providers,
    reason: null,
    requested: false,
    manual: false
  } satisfies DesktopOnboardingState)
}

const ctx: OnboardingContext = { requestGateway: async () => undefined as never }

function installApiMock(api: (request: { body?: unknown; path: string }) => Promise<unknown>) {
  Object.defineProperty(window, 'hermesDesktop', {
    configurable: true,
    value: { api }
  })
}

afterEach(() => {
  cleanup()
  $desktopOnboarding.set({
    configured: null,
    flow: { status: 'idle' },
    mode: 'oauth',
    providers: null,
    reason: null,
    requested: false,
    manual: false
  })
})

describe('onboarding Picker', () => {
  it('features Nous Portal and hides other providers behind a disclosure', () => {
    setProviders([provider('anthropic', 'Anthropic Claude'), provider('nous', 'Nous Portal')])
    render(<Picker ctx={ctx} />)

    expect(screen.getByText('Nous Portal')).toBeTruthy()
    expect(screen.getByText('Recommended')).toBeTruthy()
    expect(screen.queryByText('Anthropic API Key')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Other providers' }))

    expect(screen.getByText('Anthropic API Key')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Collapse' })).toBeTruthy()
  })

  it('shows every provider directly when Nous Portal is absent', () => {
    setProviders([provider('anthropic', 'Anthropic Claude'), provider('openai-codex', 'OpenAI Codex / ChatGPT')])
    render(<Picker ctx={ctx} />)

    expect(screen.getByText('Anthropic API Key')).toBeTruthy()
    expect(screen.getByText('OpenAI OAuth (ChatGPT)')).toBeTruthy()
    expect(screen.queryByText('Other sign-in options')).toBeNull()
    expect(screen.queryByText('Recommended')).toBeNull()
  })

  it('collects base URL and API key for a custom provider', async () => {
    setProviders([])

    const calls: { body?: unknown; path: string }[] = []
    installApiMock(async ({ body, path }: { body?: unknown; path: string }) => {
      calls.push({ body, path })

      if (path === '/api/providers/custom') {
        return {
          ok: true,
          provider: 'ai-router',
          slug: 'ai-router',
          key_env: 'CUSTOM_PROVIDER_AI_ROUTER_API_KEY',
          model: 'openai/gpt-4.1-mini',
          models: ['openai/gpt-4.1-mini']
        }
      }

      throw new Error(`unexpected api path: ${path}`)
    })

    const readyCtx: OnboardingContext = {
      requestGateway: async method => {
        if (method === 'reload.env') {
          return {} as never
        }

        if (method === 'setup.status') {
          return { provider_configured: true } as never
        }

        if (method === 'setup.runtime_check') {
          return { ok: true } as never
        }

        throw new Error(`unexpected gateway method: ${method}`)
      }
    }

    render(<Picker ctx={readyCtx} />)

    fireEvent.click(screen.getByRole('button', { name: /Local \/ custom endpoint/i }))
    fireEvent.change(screen.getByLabelText('Base URL'), { target: { value: 'https://ai-router.app/v1' } })
    fireEvent.change(screen.getByLabelText('API key'), { target: { value: 'router-secret' } })

    expect(screen.queryByLabelText('Provider name')).toBeNull()
    expect(screen.queryByLabelText('Model')).toBeNull()
    expect(screen.queryByLabelText('Key environment variable')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: /Connect/i }))

    await waitFor(() => {
      expect(calls).toEqual([
        {
          path: '/api/providers/custom',
          body: {
            api_key: 'router-secret',
            base_url: 'https://ai-router.app/v1',
            make_active: true
          }
        }
      ])
    })
  })
})
