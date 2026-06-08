import { act, cleanup, fireEvent, render } from '@testing-library/react'
import { useRef, useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { SLASH_COMMAND_RE } from '@/lib/chat-runtime'

// Faithful mirror of index.tsx's contentEditable submit race: input writes the
// latest text to draftRef synchronously, then Enter can fire before React has
// committed the new `draft` render snapshot. submitDraft must use draftRef or a
// quickly typed `/goal ...` can submit the stale bare `/` and show
// "empty slash command".
function Harness({ onQueue, onSubmit }: { onQueue?: (text: string) => void; onSubmit: (text: string) => void }) {
  const draftRef = useRef('/')
  const [draft, setDraft] = useState('/')

  const flushEditorToDraft = (editor: HTMLDivElement) => {
    const next = editor.textContent ?? ''

    if (next !== draftRef.current) {
      draftRef.current = next
      setDraft(next)
    }
  }

  const submitDraft = (busy = false) => {
    const currentDraft = draftRef.current
    const currentTrimmedDraft = currentDraft.trim()

    if (busy) {
      if (currentTrimmedDraft) {
        onQueue?.(currentDraft)
      }

      return
    }

    if (SLASH_COMMAND_RE.test(currentTrimmedDraft)) {
      onSubmit(currentDraft)
    } else if (currentTrimmedDraft) {
      onSubmit(currentDraft)
    }
  }

  return (
    <div
      contentEditable
      data-draft={draft}
      data-testid="editor"
      onInput={event => flushEditorToDraft(event.currentTarget)}
      onKeyDown={event => {
        if (event.key === 'Enter') {
          event.preventDefault()
          submitDraft(event.shiftKey)
        }
      }}
      suppressContentEditableWarning
    >
      /
    </div>
  )
}

describe('composer submit uses the synchronously-updated draft ref', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('does not submit a stale bare slash when Enter follows /goal typing in the same event turn', async () => {
    const onSubmit = vi.fn()
    const { getByTestId } = render(<Harness onSubmit={onSubmit} />)
    const editor = getByTestId('editor')

    await act(async () => {
      editor.textContent = '/goal investigate milestone readiness'
      fireEvent.input(editor)
      fireEvent.keyDown(editor, { key: 'Enter' })
    })

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith('/goal investigate milestone readiness')
    expect(onSubmit).not.toHaveBeenCalledWith('/')
  })

  it('queues the synchronously-updated draft instead of stale state while busy', async () => {
    const onQueue = vi.fn()
    const onSubmit = vi.fn()
    const { getByTestId } = render(<Harness onQueue={onQueue} onSubmit={onSubmit} />)
    const editor = getByTestId('editor')

    await act(async () => {
      editor.textContent = 'normal message while busy'
      fireEvent.input(editor)
      fireEvent.keyDown(editor, { key: 'Enter', shiftKey: true })
    })

    expect(onQueue).toHaveBeenCalledTimes(1)
    expect(onQueue).toHaveBeenCalledWith('normal message while busy')
    expect(onQueue).not.toHaveBeenCalledWith('/')
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
