import { describe, expect, it } from 'vitest'

import { composerPlainText, renderComposerContents, RICH_INPUT_SLOT } from './rich-editor'

describe('renderComposerContents', () => {
  it('renders refs and raw text without interpreting user text as HTML', () => {
    const editor = document.createElement('div')
    editor.dataset.slot = RICH_INPUT_SLOT

    renderComposerContents(editor, '@file:`<img src=x onerror=alert(1)>` <b>raw</b>')

    expect(editor.querySelector('img')).toBeNull()
    expect(editor.querySelector('b')).toBeNull()
    expect(editor.textContent).toContain('<img src=x onerror=alert(1)>')
    expect(editor.textContent).toContain('<b>raw</b>')
    expect(composerPlainText(editor)).toBe('@file:`<img src=x onerror=alert(1)>` <b>raw</b>')
  })
})

describe('composerPlainText', () => {
  it('serializes plain contenteditable text', () => {
    const editor = document.createElement('div')
    editor.dataset.slot = RICH_INPUT_SLOT
    editor.textContent = 'hi'

    expect(composerPlainText(editor)).toBe('hi')
  })

  it('serializes CJK contenteditable text', () => {
    const editor = document.createElement('div')
    editor.dataset.slot = RICH_INPUT_SLOT
    editor.textContent = '你好'

    expect(composerPlainText(editor)).toBe('你好')
  })

  it('serializes numeric contenteditable text', () => {
    const editor = document.createElement('div')
    editor.dataset.slot = RICH_INPUT_SLOT
    editor.textContent = '1'

    expect(composerPlainText(editor)).toBe('1')
  })

  it('serializes a browser empty-editor break as a newline', () => {
    const editor = document.createElement('div')
    editor.dataset.slot = RICH_INPUT_SLOT
    editor.append(document.createElement('br'))

    expect(composerPlainText(editor)).toBe('\n')
  })
})
