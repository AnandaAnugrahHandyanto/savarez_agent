/**
 * Helpers for the contenteditable composer surface: serialize refs to chip
 * HTML, walk the DOM back to plain `@kind:value` text, and place the caret.
 *
 * Chip values are always wrapped in backticks/quotes so REF_RE stops at the
 * fence — without that, typing after a chip would get re-absorbed on the next
 * plain-text round-trip.
 */
import {
  DIRECTIVE_CHIP_CLASS,
  directiveIconElement,
  directiveIconSvg,
  formatRefValue
} from '@/components/assistant-ui/directive-text'

export const RICH_INPUT_SLOT = 'composer-rich-input'

export const REF_RE = /@(file|folder|url|image|tool|line|terminal):(`[^`\n]+`|"[^"\n]+"|'[^'\n]+'|\S+)/g

const ESC: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }

export function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, ch => ESC[ch] || ch)
}

export function unquoteRef(raw: string) {
  const head = raw[0]
  const tail = raw[raw.length - 1]
  const quoted = (head === '`' && tail === '`') || (head === '"' && tail === '"') || (head === "'" && tail === "'")

  return quoted ? raw.slice(1, -1) : raw.replace(/[,.;!?]+$/, '')
}

export function refLabel(id: string) {
  return id.split(/[\\/]/).filter(Boolean).pop() || id
}

/** Always-quote variant of formatRefValue — chips need a fence even for safe values. */
export function quoteRefValue(value: string) {
  if (!value.includes('`')) {
    return `\`${value}\``
  }

  if (!value.includes('"')) {
    return `"${value}"`
  }

  if (!value.includes("'")) {
    return `'${value}'`
  }

  return formatRefValue(value)
}

export function refChipHtml(kind: string, rawValue: string) {
  const id = unquoteRef(rawValue)
  const text = `@${kind}:${quoteRefValue(id)}`

  return `<span contenteditable="false" data-ref-text="${escapeHtml(text)}" data-ref-id="${escapeHtml(id)}" data-ref-kind="${escapeHtml(kind)}" class="${DIRECTIVE_CHIP_CLASS}">${directiveIconSvg(kind)}<span class="truncate">${escapeHtml(refLabel(id))}</span></span>`
}

export function refChipElement(kind: string, rawValue: string) {
  const id = unquoteRef(rawValue)
  const text = `@${kind}:${quoteRefValue(id)}`
  const chip = document.createElement('span')
  const label = document.createElement('span')

  chip.contentEditable = 'false'
  chip.dataset.refText = text
  chip.dataset.refId = id
  chip.dataset.refKind = kind
  chip.className = DIRECTIVE_CHIP_CLASS
  label.className = 'truncate'
  label.textContent = refLabel(id)
  chip.append(directiveIconElement(kind), label)

  return chip
}

function appendTextWithBreaks(target: DocumentFragment | HTMLElement, text: string) {
  const lines = text.split('\n')

  lines.forEach((line, index) => {
    if (index > 0) {
      target.append(document.createElement('br'))
    }

    if (line) {
      target.append(document.createTextNode(line))
    }
  })
}

export function appendComposerContents(target: DocumentFragment | HTMLElement, text: string) {
  let cursor = 0

  REF_RE.lastIndex = 0

  for (const match of text.matchAll(REF_RE)) {
    const index = match.index ?? 0
    appendTextWithBreaks(target, text.slice(cursor, index))
    target.append(refChipElement(match[1] || 'file', match[2] || ''))
    cursor = index + match[0].length
  }

  appendTextWithBreaks(target, text.slice(cursor))
}

export function renderComposerContents(target: HTMLElement, text: string) {
  target.replaceChildren()
  appendComposerContents(target, text)
}

export interface ComposerSelectionSnapshot {
  end: number
  start: number
}

/** Serialize a draft string into chip-HTML for the contenteditable surface. */
export function composerHtml(text: string) {
  let cursor = 0
  let html = ''

  REF_RE.lastIndex = 0

  for (const match of text.matchAll(REF_RE)) {
    const index = match.index ?? 0
    html += escapeHtml(text.slice(cursor, index)).replace(/\n/g, '<br>')
    html += refChipHtml(match[1] || 'file', match[2] || '')
    cursor = index + match[0].length
  }

  return html + escapeHtml(text.slice(cursor)).replace(/\n/g, '<br>')
}

/** Walk a DOM subtree back to the plain `@kind:value` text it represents. */
export function composerPlainText(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) {
    return node.textContent || ''
  }

  if (node.nodeType !== Node.ELEMENT_NODE) {
    return ''
  }

  const el = node as HTMLElement

  if (el.dataset.refText) {
    return el.dataset.refText
  }

  if (el.tagName === 'BR') {
    return '\n'
  }

  const text = Array.from(node.childNodes).map(composerPlainText).join('')
  const block = el.tagName === 'DIV' || el.tagName === 'P'

  return block && text && el.dataset.slot !== RICH_INPUT_SLOT ? `${text}\n` : text
}

function nodeTextLength(node: Node): number {
  return composerPlainText(node).length
}

function childIndex(node: Node): number {
  const parent = node.parentNode

  return parent ? Array.prototype.indexOf.call(parent.childNodes, node) : 0
}

function offsetForPosition(root: Node, target: Node, targetOffset: number): number | null {
  const visit = (node: Node): { found: true; offset: number } | { found: false; length: number } => {
    if (node === target) {
      if (node.nodeType === Node.TEXT_NODE) {
        return { found: true, offset: Math.max(0, Math.min(targetOffset, node.textContent?.length ?? 0)) }
      }

      if (node.nodeType === Node.ELEMENT_NODE) {
        const children = Array.from(node.childNodes).slice(0, targetOffset)

        return { found: true, offset: children.reduce((sum, child) => sum + nodeTextLength(child), 0) }
      }

      return { found: true, offset: 0 }
    }

    if (node.nodeType !== Node.ELEMENT_NODE) {
      return { found: false, length: nodeTextLength(node) }
    }

    let length = 0

    for (const child of Array.from(node.childNodes)) {
      const result = visit(child)

      if (result.found) {
        return { found: true, offset: length + result.offset }
      }

      length += result.length
    }

    return { found: false, length }
  }

  const result = visit(root)

  return result.found ? result.offset : null
}

function domPositionForOffset(root: HTMLElement, targetOffset: number): { node: Node; offset: number } {
  let remaining = Math.max(0, targetOffset)

  const walk = (node: Node): { node: Node; offset: number } | null => {
    if (node.nodeType === Node.TEXT_NODE) {
      const length = node.textContent?.length ?? 0

      if (remaining <= length) {
        return { node, offset: remaining }
      }

      remaining -= length

      return null
    }

    if (node.nodeType !== Node.ELEMENT_NODE) {
      return null
    }

    const el = node as HTMLElement

    if (el.dataset.refText || el.tagName === 'BR') {
      const length = nodeTextLength(el)

      if (remaining <= length) {
        return { node: el.parentNode || root, offset: childIndex(el) + (remaining > 0 ? 1 : 0) }
      }

      remaining -= length

      return null
    }

    for (const child of Array.from(node.childNodes)) {
      const position = walk(child)

      if (position) {
        return position
      }
    }

    return null
  }

  return walk(root) || { node: root, offset: root.childNodes.length }
}

export function captureComposerSelection(element: HTMLElement): ComposerSelectionSnapshot | null {
  const selection = window.getSelection()

  if (!selection || selection.rangeCount === 0) {
    return null
  }

  const range = selection.getRangeAt(0)

  if (!element.contains(range.startContainer) || !element.contains(range.endContainer)) {
    return null
  }

  const start = offsetForPosition(element, range.startContainer, range.startOffset)
  const end = offsetForPosition(element, range.endContainer, range.endOffset)

  return start === null || end === null ? null : { start, end }
}

export function restoreComposerSelection(element: HTMLElement, snapshot: ComposerSelectionSnapshot | null) {
  if (!snapshot) {
    return false
  }

  const selection = window.getSelection()

  if (!selection) {
    return false
  }

  const textLength = composerPlainText(element).length
  const start = Math.max(0, Math.min(snapshot.start, textLength))
  const end = Math.max(0, Math.min(snapshot.end, textLength))
  const startPosition = domPositionForOffset(element, start)
  const endPosition = domPositionForOffset(element, end)
  const range = document.createRange()

  range.setStart(startPosition.node, startPosition.offset)
  range.setEnd(endPosition.node, endPosition.offset)
  selection.removeAllRanges()
  selection.addRange(range)

  return true
}

export function placeCaretEnd(element: HTMLElement) {
  const range = document.createRange()
  const selection = window.getSelection()

  range.selectNodeContents(element)
  range.collapse(false)
  selection?.removeAllRanges()
  selection?.addRange(range)
}
