import { describe, expect, it } from 'vitest'

import type { SessionInfo, SessionMessage } from '@/types/hermes'

import { collectArtifactsForSession, formatArtifactTime } from './index'

function makeSession(overrides: Partial<SessionInfo> = {}): SessionInfo {
  return {
    ended_at: null,
    id: 'session-1',
    input_tokens: 0,
    is_active: false,
    last_active: 1000,
    message_count: 1,
    model: null,
    output_tokens: 0,
    preview: null,
    source: null,
    started_at: 1000,
    title: 'Session',
    tool_call_count: 0,
    ...overrides
  }
}

describe('collectArtifactsForSession', () => {
  it('indexes plain https links from assistant text', () => {
    const artifacts = collectArtifactsForSession(makeSession(), [
      {
        content: 'Reference: https://example.com/docs/getting-started',
        role: 'assistant',
        timestamp: 2000
      }
    ])

    expect(artifacts).toHaveLength(1)
    expect(artifacts[0]).toMatchObject({
      href: 'https://example.com/docs/getting-started',
      kind: 'link',
      value: 'https://example.com/docs/getting-started'
    })
  })

  it('indexes http links present in tool JSON payloads', () => {
    const messages: SessionMessage[] = [
      {
        content: JSON.stringify({ source_url: 'https://example.com/changelog/latest' }),
        role: 'tool',
        timestamp: 3000
      }
    ]

    const artifacts = collectArtifactsForSession(makeSession({ id: 'session-2' }), messages)

    expect(artifacts).toHaveLength(1)
    expect(artifacts[0]).toMatchObject({
      href: 'https://example.com/changelog/latest',
      kind: 'link',
      value: 'https://example.com/changelog/latest'
    })
  })
})

describe('formatArtifactTime', () => {
  it('treats epoch-seconds timestamps (below 1e12) as seconds and multiplies by 1000', () => {
    // 1781773226 is 2026-06-18T17:00:26Z in epoch seconds
    const result = formatArtifactTime(1781773226)
    // Should show a June date, not Jan 1970
    expect(result).toContain('Jun')
    expect(result).not.toContain('Jan')
  })

  it('handles millisecond timestamps (above 1e12) without double-multiplying', () => {
    // 1781773226000 is the same date in milliseconds
    const result = formatArtifactTime(1781773226000)
    expect(result).toContain('Jun')
    expect(result).not.toContain('Jan')
  })

  it('handles typical session timestamps from state.db', () => {
    // Python's time.time() returns ~1.78e9 in 2026
    const epochSeconds = 1781773226.453548
    const result = formatArtifactTime(epochSeconds)
    // Should not render as Jan 1970 (the bug symptom)
    expect(result).not.toContain('1970')
    expect(result).toContain('Jun')
  })

  it('renders old timestamps correctly when already in milliseconds', () => {
    // A timestamp from 2024 in milliseconds (well above 1e12)
    const ts2024 = 1700000000000
    const result = formatArtifactTime(ts2024)
    expect(result).toContain('Nov')
  })
})
