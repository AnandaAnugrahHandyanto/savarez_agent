import { AssistantRuntimeProvider, type ThreadMessage, useExternalStoreRuntime } from '@assistant-ui/react'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  $composerDraft,
  clearComposerAttachments,
  clearComposerDraft,
  setComposerDraft
} from '@/store/composer'

import { RICH_INPUT_SLOT } from './rich-editor'
import type { ChatBarState } from './types'

import { ChatBar } from './index'

const chatBarState: ChatBarState = {
  model: { canSwitch: false, model: 'test-model', provider: 'test-provider' },
  tools: { enabled: false, label: 'Tools' },
  voice: { active: false, enabled: false }
}

class ResizeObserverStub implements ResizeObserver {
  disconnect = vi.fn()
  observe = vi.fn()
  unobserve = vi.fn()
}

function ensureBrowserStubs() {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      addEventListener: vi.fn(),
      addListener: vi.fn(),
      dispatchEvent: vi.fn(),
      matches: false,
      media: query,
      onchange: null,
      removeEventListener: vi.fn(),
      removeListener: vi.fn()
    }))
  })

  Object.defineProperty(window, 'ResizeObserver', {
    configurable: true,
    value: ResizeObserverStub
  })
}

function Harness({ focusKey = 'session-1', show = true }: { focusKey?: string | null; show?: boolean }) {
  const runtime = useExternalStoreRuntime<ThreadMessage>({
    isRunning: false,
    messages: [],
    onNew: async () => {}
  })

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {show && (
        <ChatBar
          busy={false}
          disabled={false}
          focusKey={focusKey}
          onCancel={vi.fn()}
          onSubmit={vi.fn()}
          state={chatBarState}
        />
      )}
    </AssistantRuntimeProvider>
  )
}

function composerEditor() {
  const editor = document.querySelector(`[data-slot="${RICH_INPUT_SLOT}"]`)

  if (!(editor instanceof HTMLElement)) {
    throw new Error('Composer editor not found')
  }

  return editor
}

function setTextboxText(value: string) {
  const textbox = composerEditor()
  textbox.textContent = value
  fireEvent.input(textbox)

  return textbox
}

beforeEach(() => {
  ensureBrowserStubs()
  clearComposerDraft()
  clearComposerAttachments()
})

afterEach(() => {
  cleanup()
  clearComposerDraft()
  clearComposerAttachments()
  vi.restoreAllMocks()
})

describe('ChatBar draft persistence', () => {
  it('stashes typed composer text and restores it after chat navigation unmounts the bar', async () => {
    const view = render(<Harness />)

    setTextboxText('keep this unsent draft')
    expect($composerDraft.get()).toBe('keep this unsent draft')

    view.rerender(<Harness show={false} />)
    expect(screen.queryByRole('textbox', { name: 'Message' })).toBeNull()
    expect($composerDraft.get()).toBe('keep this unsent draft')

    view.rerender(<Harness />)
    expect($composerDraft.get()).toBe('keep this unsent draft')

    await waitFor(() => {
      expect(composerEditor().textContent).toBe('keep this unsent draft')
    })
  })

  it('hydrates a stashed draft on mount without clearing it first', async () => {
    setComposerDraft('restored from route stash')

    render(<Harness />)

    await waitFor(() => {
      expect(composerEditor().textContent).toBe('restored from route stash')
    })
    expect($composerDraft.get()).toBe('restored from route stash')
  })

  it('clears the visible composer when the session key changes after the route stash is cleared', async () => {
    const view = render(<Harness focusKey="session-1" />)

    setTextboxText('wrong chat draft')
    expect($composerDraft.get()).toBe('wrong chat draft')

    act(() => {
      clearComposerDraft()
    })
    view.rerender(<Harness focusKey="session-2" />)

    await waitFor(() => {
      expect(composerEditor().textContent).toBe('')
    })
  })
})
