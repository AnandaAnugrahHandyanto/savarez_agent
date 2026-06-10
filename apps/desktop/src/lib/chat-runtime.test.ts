import { describe, expect, it } from 'vitest'

import { coerceThinkingText, parseCommandDispatch } from './chat-runtime'

describe('parseCommandDispatch', () => {
  it('parses send and prefill notices from command.dispatch', () => {
    expect(
      parseCommandDispatch({
        type: 'send',
        message: 'write a hello-world script',
        notice: '⊙ Goal set (20-turn budget): write a hello-world script'
      })
    ).toEqual({
      type: 'send',
      message: 'write a hello-world script',
      notice: '⊙ Goal set (20-turn budget): write a hello-world script'
    })

    expect(
      parseCommandDispatch({
        type: 'prefill',
        message: 'edit me',
        notice: '↶ Undid 1 turn (2 message(s)).'
      })
    ).toEqual({
      type: 'prefill',
      message: 'edit me',
      notice: '↶ Undid 1 turn (2 message(s)).'
    })
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
