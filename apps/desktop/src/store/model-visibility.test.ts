import { describe, expect, it } from 'vitest'

import type { ModelOptionProvider } from '@/types/hermes'

import {
  effectiveVisibleKeys,
  modelVisibilityKey,
  providerHiddenVisibilityKey,
  toggleVisibleModelKey
} from './model-visibility'

const provider = (slug: string, models: string[]): ModelOptionProvider => ({
  models,
  name: slug,
  slug
})

describe('model visibility', () => {
  it('keeps newly configured providers visible when stored choices are stale', () => {
    const stored = new Set([modelVisibilityKey('copilot', 'claude-sonnet-4.6')])

    const visible = effectiveVisibleKeys(stored, [
      provider('copilot', ['claude-sonnet-4.6']),
      provider('local-ollama', ['qwen3:latest', 'llama3.2:latest'])
    ])

    expect(visible.has(modelVisibilityKey('copilot', 'claude-sonnet-4.6'))).toBe(true)
    expect(visible.has(modelVisibilityKey('local-ollama', 'qwen3:latest'))).toBe(true)
    expect(visible.has(modelVisibilityKey('local-ollama', 'llama3.2:latest'))).toBe(true)
  })

  it('does not re-add models from a provider that already has stored choices', () => {
    const stored = new Set([modelVisibilityKey('local-ollama', 'qwen3:latest')])

    const visible = effectiveVisibleKeys(stored, [
      provider('local-ollama', ['qwen3:latest', 'llama3.2:latest'])
    ])

    expect(visible.has(modelVisibilityKey('local-ollama', 'qwen3:latest'))).toBe(true)
    expect(visible.has(modelVisibilityKey('local-ollama', 'llama3.2:latest'))).toBe(false)
  })

  it('keeps a provider hidden when its last visible model is toggled off', () => {
    const providers = [
      provider('copilot', ['claude-sonnet-4.6']),
      provider('local-ollama', ['qwen3:latest'])
    ]

    const stored = new Set([
      modelVisibilityKey('copilot', 'claude-sonnet-4.6'),
      modelVisibilityKey('local-ollama', 'qwen3:latest')
    ])

    const next = toggleVisibleModelKey(stored, providers, providers[1], 'qwen3:latest')
    const visible = effectiveVisibleKeys(next, providers)

    expect(next.has(providerHiddenVisibilityKey('local-ollama'))).toBe(true)
    expect(visible.has(modelVisibilityKey('copilot', 'claude-sonnet-4.6'))).toBe(true)
    expect(visible.has(modelVisibilityKey('local-ollama', 'qwen3:latest'))).toBe(false)
  })

  it('removes the hidden-provider marker when a model is toggled back on', () => {
    const providers = [provider('local-ollama', ['qwen3:latest'])]
    const stored = new Set([providerHiddenVisibilityKey('local-ollama')])

    const next = toggleVisibleModelKey(stored, providers, providers[0], 'qwen3:latest')

    expect(next.has(providerHiddenVisibilityKey('local-ollama'))).toBe(false)
    expect(next.has(modelVisibilityKey('local-ollama', 'qwen3:latest'))).toBe(true)
  })
})
