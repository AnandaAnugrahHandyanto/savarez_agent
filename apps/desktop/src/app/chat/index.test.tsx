import { describe, expect, it } from 'vitest'

import type { ChatMessage } from '@/lib/chat-messages'

import { chatRenderWindow } from './index'

function userMessage(id: string, text = id): ChatMessage {
  return {
    id,
    role: 'user',
    parts: [{ type: 'text', text }]
  }
}

describe('chat render window', () => {
  it('caps large sessions to the latest render window until full history is loaded', () => {
    const messages = [
      userMessage('message-1'),
      userMessage('message-2'),
      userMessage('message-3'),
      userMessage('message-4')
    ]

    expect(chatRenderWindow(messages, false, 3)).toEqual({
      cappedMessageCount: 1,
      renderMessages: messages.slice(1)
    })
  })

  it('returns all messages when full history is loaded', () => {
    const messages = [
      userMessage('message-1'),
      userMessage('message-2'),
      userMessage('message-3'),
      userMessage('message-4')
    ]

    expect(chatRenderWindow(messages, true, 3)).toEqual({
      cappedMessageCount: 1,
      renderMessages: messages
    })
  })
})
