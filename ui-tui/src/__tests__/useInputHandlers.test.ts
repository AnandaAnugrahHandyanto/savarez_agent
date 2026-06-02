import { PassThrough } from 'stream'

import { Box, type InputHandler, type Key, renderSync } from '@hermes/ink'
import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { InputHandlerContext } from '../app/interfaces.js'
import { resetOverlayState } from '../app/overlayStore.js'
import { patchUiState, resetUiState } from '../app/uiStore.js'
import {
  applyVoiceRecordResponse,
  clearAttachedImages,
  shouldFallThroughForScroll,
  useInputHandlers
} from '../app/useInputHandlers.js'
import { isMac } from '../lib/platform.js'

let capturedInput: InputHandler | null = null

vi.mock('@hermes/ink', async importOriginal => {
  const actual = await importOriginal()

  return {
    ...actual,
    useInput: vi.fn((handler: InputHandler) => {
      capturedInput = handler
    })
  }
})

const baseKey: Key = {
  alt: false,
  backspace: false,
  ctrl: false,
  delete: false,
  downArrow: false,
  end: false,
  escape: false,
  home: false,
  leftArrow: false,
  meta: false,
  pageDown: false,
  pageUp: false,
  return: false,
  rightArrow: false,
  shift: false,
  super: false,
  tab: false,
  upArrow: false,
  wheelDown: false,
  wheelUp: false
}

const makeStreams = () => {
  const stdout = new PassThrough()
  const stdin = new PassThrough()
  const stderr = new PassThrough()

  Object.assign(stdout, { columns: 80, isTTY: false, rows: 20 })
  Object.assign(stdin, { isTTY: false })
  Object.assign(stderr, { isTTY: false })
  stdout.on('data', () => {})

  return { stderr, stdin, stdout }
}

const keyWith = (partial: Partial<Key>): Key => ({ ...baseKey, ...partial })

const flushAsync = async () => {
  await Promise.resolve()
  await Promise.resolve()
}

function Harness({ ctx }: { ctx: InputHandlerContext }) {
  useInputHandlers(ctx)

  return React.createElement(Box, null)
}

const buildContext = () => {
  const die = vi.fn()
  const rpc = vi.fn()
  const sys = vi.fn()

  const ctx: InputHandlerContext = {
    actions: {
      answerClarify: vi.fn(),
      appendMessage: vi.fn(),
      die,
      dispatchSubmission: vi.fn(),
      guardBusySessionSwitch: vi.fn(() => false),
      newSession: vi.fn(),
      sys
    },
    composer: {
      actions: {
        clearIn: vi.fn(),
        dequeue: vi.fn(),
        enqueue: vi.fn(),
        handleTextPaste: vi.fn(),
        openEditor: vi.fn(async () => {}),
        pushHistory: vi.fn(),
        removeQueue: vi.fn(),
        replaceQueue: vi.fn(),
        setCompIdx: vi.fn(),
        setHistoryIdx: vi.fn(),
        setInput: vi.fn(),
        setInputBuf: vi.fn(),
        setPasteSnips: vi.fn(),
        setQueueEdit: vi.fn(),
        syncQueue: vi.fn()
      },
      refs: {
        historyDraftRef: { current: '' },
        historyRef: { current: [] },
        queueEditRef: { current: null },
        queueRef: { current: [] },
        submitRef: { current: vi.fn() }
      },
      state: {
        compIdx: 0,
        compReplace: 0,
        completions: [],
        historyIdx: null,
        input: '',
        inputBuf: [],
        pasteSnips: [],
        queueEditIdx: null,
        queuedDisplay: []
      }
    },
    gateway: {
      gw: {} as never,
      rpc
    },
    terminal: {
      hasSelection: false,
      scrollRef: { current: null },
      scrollWithSelection: vi.fn(),
      selection: {
        captureScrolledRows: vi.fn(),
        clearSelection: vi.fn(),
        copySelection: vi.fn(),
        copySelectionNoClear: vi.fn(),
        getState: vi.fn(),
        shiftAnchor: vi.fn(),
        shiftSelection: vi.fn(),
        version: vi.fn()
      }
    },
    voice: {
      enabled: false,
      recordKey: { ch: 'b', mod: 'ctrl', raw: 'ctrl+b' },
      recording: false,
      setProcessing: vi.fn(),
      setRecording: vi.fn(),
      setVoiceEnabled: vi.fn(),
      setVoiceTts: vi.fn()
    },
    wheelStep: 3
  }

  return { ctx, die, rpc, sys }
}

beforeEach(() => {
  capturedInput = null
  resetUiState()
  resetOverlayState()
})

afterEach(() => {
  resetUiState()
  resetOverlayState()
})

describe('shouldFallThroughForScroll — keep transcript scrolling alive during prompt overlays', () => {
  it('falls through for wheel scrolls', () => {
    expect(shouldFallThroughForScroll({ ...baseKey, wheelUp: true })).toBe(true)
    expect(shouldFallThroughForScroll({ ...baseKey, wheelDown: true })).toBe(true)
  })

  it('falls through for PageUp / PageDown', () => {
    expect(shouldFallThroughForScroll({ ...baseKey, pageUp: true })).toBe(true)
    expect(shouldFallThroughForScroll({ ...baseKey, pageDown: true })).toBe(true)
  })

  it('falls through for Shift+ArrowUp / Shift+ArrowDown', () => {
    expect(shouldFallThroughForScroll({ ...baseKey, shift: true, upArrow: true })).toBe(true)
    expect(shouldFallThroughForScroll({ ...baseKey, shift: true, downArrow: true })).toBe(true)
  })

  it('does NOT fall through for plain arrows — those drive in-prompt selection', () => {
    expect(shouldFallThroughForScroll({ ...baseKey, upArrow: true })).toBe(false)
    expect(shouldFallThroughForScroll({ ...baseKey, downArrow: true })).toBe(false)
  })

  it('does NOT fall through for plain Shift — without an arrow it is a no-op', () => {
    expect(shouldFallThroughForScroll({ ...baseKey, shift: true })).toBe(false)
  })

  it('does NOT fall through for unrelated state (no scroll keys held)', () => {
    expect(shouldFallThroughForScroll(baseKey)).toBe(false)
  })
})

describe('applyVoiceRecordResponse', () => {
  it('reverts optimistic REC state when the gateway reports voice busy', () => {
    const setProcessing = vi.fn()
    const setRecording = vi.fn()
    const sys = vi.fn()

    applyVoiceRecordResponse({ status: 'busy' }, true, { setProcessing, setRecording }, sys)

    expect(setRecording).toHaveBeenCalledWith(false)
    expect(setProcessing).toHaveBeenCalledWith(true)
    expect(sys).toHaveBeenCalledWith('voice: still transcribing; try again shortly')
  })

  it('keeps optimistic REC state for successful recording starts', () => {
    const setProcessing = vi.fn()
    const setRecording = vi.fn()

    applyVoiceRecordResponse({ status: 'recording' }, true, { setProcessing, setRecording }, vi.fn())

    expect(setRecording).not.toHaveBeenCalled()
    expect(setProcessing).not.toHaveBeenCalled()
  })

  it('reverts optimistic REC state when the gateway returns null', () => {
    const setProcessing = vi.fn()
    const setRecording = vi.fn()

    applyVoiceRecordResponse(null, true, { setProcessing, setRecording }, vi.fn())

    expect(setRecording).toHaveBeenCalledWith(false)
    expect(setProcessing).toHaveBeenCalledWith(false)
  })
})

describe('clearAttachedImages', () => {
  it('reports when pending images were cleared', async () => {
    const rpc = vi.fn().mockResolvedValue({ removed: 2 })
    const sys = vi.fn()

    await expect(clearAttachedImages({ rpc }, 'sid-1', sys)).resolves.toBe(true)

    expect(rpc).toHaveBeenCalledWith('image.clear', { session_id: 'sid-1' })
    expect(sys).toHaveBeenCalledWith('cleared 2 attached images')
  })

  it('stays silent when there is nothing to clear', async () => {
    const rpc = vi.fn().mockResolvedValue({ removed: 0 })
    const sys = vi.fn()

    await expect(clearAttachedImages({ rpc }, 'sid-1', sys)).resolves.toBe(false)

    expect(sys).not.toHaveBeenCalled()
  })
})

describe('useInputHandlers attachment clearing shortcuts', () => {
  it('uses Ctrl+C to clear pending images before exiting', async () => {
    const { ctx, die, rpc, sys } = buildContext()
    rpc.mockResolvedValue({ removed: 1 })
    patchUiState({ busy: false, sid: 'sid-1', status: 'ready' })

    const streams = makeStreams()

    const instance = renderSync(React.createElement(Harness, { ctx }), {
      patchConsole: false,
      stderr: streams.stderr as NodeJS.WriteStream,
      stdin: streams.stdin as NodeJS.ReadStream,
      stdout: streams.stdout as NodeJS.WriteStream
    })

    try {
      expect(capturedInput).not.toBeNull()
      const key = keyWith({ ctrl: true })

      capturedInput!('c', key, { input: 'c', key, keypress: {} })
      await flushAsync()

      expect(rpc).toHaveBeenCalledWith('image.clear', { session_id: 'sid-1' })
      expect(sys).toHaveBeenCalledWith('cleared 1 attached image')
      expect(die).not.toHaveBeenCalled()
    } finally {
      instance.unmount()
      instance.cleanup()
    }
  })

  it('falls back to exit when Ctrl+D finds no pending images', async () => {
    const { ctx, die, rpc } = buildContext()
    rpc.mockResolvedValue({ removed: 0 })
    patchUiState({ busy: false, sid: 'sid-1', status: 'ready' })

    const streams = makeStreams()

    const instance = renderSync(React.createElement(Harness, { ctx }), {
      patchConsole: false,
      stderr: streams.stderr as NodeJS.WriteStream,
      stdin: streams.stdin as NodeJS.ReadStream,
      stdout: streams.stdout as NodeJS.WriteStream
    })

    try {
      expect(capturedInput).not.toBeNull()
      const key = keyWith(isMac ? { meta: true } : { ctrl: true })

      capturedInput!('d', key, { input: 'd', key, keypress: {} })
      await flushAsync()

      expect(rpc).toHaveBeenCalledWith('image.clear', { session_id: 'sid-1' })
      expect(die).toHaveBeenCalledTimes(1)
    } finally {
      instance.unmount()
      instance.cleanup()
    }
  })
})
