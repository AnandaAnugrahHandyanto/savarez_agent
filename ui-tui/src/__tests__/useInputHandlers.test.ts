import { describe, expect, it, vi } from 'vitest'

import { applyVoiceRecordResponse } from '../app/useInputHandlers.js'

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

describe('Ctrl+D exit keybinding', () => {
  it('isCtrl matches ctrl+d on all platforms', () => {
    const isCtrl = (key: { ctrl: boolean }, ch: string, target: string) =>
      key.ctrl && ch.toLowerCase() === target

    expect(isCtrl({ ctrl: true }, 'd', 'd')).toBe(true)
    expect(isCtrl({ ctrl: false }, 'd', 'd')).toBe(false)
    expect(isCtrl({ ctrl: true }, 'D', 'd')).toBe(true)
    expect(isCtrl({ ctrl: true }, 'x', 'd')).toBe(false)
  })

  it('isAction matches Cmd+d on macOS and Ctrl+d on Linux/Windows', () => {
    const isMac = process.platform === 'darwin'
    const isActionMod = (key: { ctrl: boolean; meta: boolean; super?: boolean }): boolean =>
      isMac ? key.meta || key.super === true : key.ctrl
    const isAction = (key: { ctrl: boolean; meta: boolean; super?: boolean }, ch: string, target: string): boolean =>
      isActionMod(key) && ch.toLowerCase() === target

    if (isMac) {
      // macOS: Cmd+D (meta) or Cmd+D (super) should match
      expect(isAction({ ctrl: false, meta: true }, 'd', 'd')).toBe(true)
      expect(isAction({ ctrl: false, meta: false, super: true }, 'd', 'd')).toBe(true)
      // Ctrl+D alone should NOT match isAction on macOS
      expect(isAction({ ctrl: true, meta: false }, 'd', 'd')).toBe(false)
    } else {
      // Linux/Windows: Ctrl+D should match
      expect(isAction({ ctrl: true, meta: false }, 'd', 'd')).toBe(true)
      expect(isAction({ ctrl: false, meta: true }, 'd', 'd')).toBe(false)
    }
  })

  it('combined isCtrl || isAction allows both Ctrl+D and Cmd+D on macOS', () => {
    const isMac = process.platform === 'darwin'
    const isActionMod = (key: { ctrl: boolean; meta: boolean; super?: boolean }): boolean =>
      isMac ? key.meta || key.super === true : key.ctrl
    const isAction = (key: { ctrl: boolean; meta: boolean; super?: boolean }, ch: string, target: string): boolean =>
      isActionMod(key) && ch.toLowerCase() === target
    const isCtrl = (key: { ctrl: boolean }, ch: string, target: string) =>
      key.ctrl && ch.toLowerCase() === target

    const exitBinding = (key: { ctrl: boolean; meta: boolean; super?: boolean }, ch: string) =>
      isCtrl(key, ch, 'd') || isAction(key, ch, 'd')

    if (isMac) {
      // Ctrl+D works on macOS
      expect(exitBinding({ ctrl: true, meta: false }, 'd')).toBe(true)
      // Cmd+D still works on macOS
      expect(exitBinding({ ctrl: false, meta: true }, 'd')).toBe(true)
      // Cmd+D via super also works
      expect(exitBinding({ ctrl: false, meta: false, super: true }, 'd')).toBe(true)
    } else {
      // Linux/Windows: Ctrl+D works
      expect(exitBinding({ ctrl: true, meta: false }, 'd')).toBe(true)
      // Meta+D does not work on Linux/Windows
      expect(exitBinding({ ctrl: false, meta: true }, 'd')).toBe(false)
    }
  })
})
