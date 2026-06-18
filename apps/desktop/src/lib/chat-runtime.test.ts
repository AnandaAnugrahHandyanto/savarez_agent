import { describe, expect, it } from 'vitest'

import type { ComposerAttachment } from '@/store/composer'

import { coerceThinkingText, optimisticAttachmentRef, parseCommandDispatch } from './chat-runtime'

const DATA_URL = 'data:image/png;base64,iVBORw0KGgoAAAANS'

function attachment(overrides: Partial<ComposerAttachment> & Pick<ComposerAttachment, 'kind'>): ComposerAttachment {
  return { id: 'a', label: 'file.png', ...overrides }
}

describe('optimisticAttachmentRef', () => {
  it('renders an image from its in-hand base64 preview (no @image: path ref)', () => {
    const ref = optimisticAttachmentRef(attachment({ kind: 'image', detail: '/tmp/shot.png', previewUrl: DATA_URL }))

    // The raw data URL flows through extractEmbeddedImages → inline thumbnail,
    // dodging the remote /api/media 403 an @image:<localpath> ref would hit.
    expect(ref).toBe(DATA_URL)
  })

  it('falls back to an @image: path ref when no preview is available', () => {
    expect(optimisticAttachmentRef(attachment({ kind: 'image', detail: '/tmp/shot.png' }))).toBe('@image:/tmp/shot.png')
  })

  it('ignores a non-data preview url and uses the path ref', () => {
    const ref = optimisticAttachmentRef(
      attachment({ kind: 'image', detail: '/tmp/shot.png', previewUrl: 'https://example.com/x.png' })
    )

    expect(ref).toBe('@image:/tmp/shot.png')
  })

  it('passes non-image attachments straight through to attachmentDisplayText', () => {
    expect(optimisticAttachmentRef(attachment({ kind: 'file', refText: '@file:src/a.ts', previewUrl: DATA_URL }))).toBe(
      '@file:src/a.ts'
    )
  })
})

describe('coerceThinkingText', () => {
  it('strips streaming status prefixes from thinking deltas', () => {
    expect(coerceThinkingText("◉_◉ processing... checking the user's request")).toBe("checking the user's request")
    expect(coerceThinkingText('(¬‿¬) analyzing... reading the file')).toBe('reading the file')
  })

  it('drops empty thinking rewrite placeholder text', () => {
    expect(
      coerceThinkingText(
        "◉_◉ processing... I don't see any current rewritten thinking or next thinking to process. Could you provide the thinking content you'd like me to rewrite?"
      )
    ).toBe('')
  })
})

describe('parseCommandDispatch', () => {
  it('returns null for non-object input', () => {
    expect(parseCommandDispatch(null)).toBeNull()
    expect(parseCommandDispatch(undefined)).toBeNull()
    expect(parseCommandDispatch('string')).toBeNull()
  })

  it('parses exec type with output', () => {
    expect(parseCommandDispatch({ type: 'exec', output: 'result' })).toEqual({ type: 'exec', output: 'result' })
  })

  it('parses alias type with target', () => {
    expect(parseCommandDispatch({ type: 'alias', target: 'other' })).toEqual({ type: 'alias', target: 'other' })
  })

  it('parses skill type with name and message', () => {
    expect(parseCommandDispatch({ type: 'skill', name: 'foo', message: 'bar' })).toEqual({
      type: 'skill',
      name: 'foo',
      message: 'bar'
    })
  })

  it('parses send type with message only', () => {
    expect(parseCommandDispatch({ type: 'send', message: 'hello' })).toEqual({ type: 'send', message: 'hello' })
  })

  it('parses send type with message and notice', () => {
    const result = parseCommandDispatch({
      type: 'send',
      message: 'fix the login bug',
      notice: '⊙ Goal set (20-turn budget): fix the login bug'
    })
    expect(result).toEqual({
      type: 'send',
      message: 'fix the login bug',
      notice: '⊙ Goal set (20-turn budget): fix the login bug'
    })
  })

  it('returns null for send type without message', () => {
    expect(parseCommandDispatch({ type: 'send', notice: 'hi' })).toBeNull()
  })

  it('returns null for unknown type', () => {
    expect(parseCommandDispatch({ type: 'unknown' })).toBeNull()
  })
})
