import { describe, expect, it } from 'vitest'

import type { ChatMessage } from '@/lib/chat-messages'

import { buildRuntimeMessageRepository, chatRenderWindow, chatThreadInstanceKey, recoverTranscriptButtonLabel } from './index'

function userMessage(id: string, text = id): ChatMessage {
  return {
    id,
    role: 'user',
    parts: [{ type: 'text', text }]
  }
}

function assistantMessage(id: string, text = id, options: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id,
    role: 'assistant',
    parts: [{ type: 'text', text }],
    ...options
  }
}

describe('chat recovery control', () => {
  it('labels routed/stored sessions as current transcript recovery', () => {
    expect(recoverTranscriptButtonLabel(true)).toBe('Recover current transcript')
  })

  it('falls back to chat history reload copy when no session is selected yet', () => {
    expect(recoverTranscriptButtonLabel(false)).toBe('Reload chat history')
  })
})

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

describe('chat session thread identity', () => {
  it('changes when switching sessions so Assistant UI does not reuse stale internal render state', () => {
    expect(chatThreadInstanceKey('session-a', 12)).not.toBe(chatThreadInstanceKey('session-b', 12))
  })

  it('changes when the rendered message window changes so capped/full-history views remount cleanly', () => {
    expect(chatThreadInstanceKey('session-a', 300)).not.toBe(chatThreadInstanceKey('session-a', 301))
  })

  it('changes when same-count rendered message windows contain different messages', () => {
    expect(chatThreadInstanceKey('session-a', [userMessage('message-1'), userMessage('message-2')])).not.toBe(
      chatThreadInstanceKey('session-a', [userMessage('message-2'), userMessage('message-3')])
    )
  })
})

describe('buildRuntimeMessageRepository', () => {
  it('builds a linear repository from visible chat messages', () => {
    const cache = new WeakMap<ChatMessage, ReturnType<typeof buildRuntimeMessageRepository>['messages'][number]['message']>()
    const messages = [userMessage('user-1'), assistantMessage('assistant-1')]

    const repository = buildRuntimeMessageRepository(messages, cache)

    expect(repository.headId).toBe('assistant-1')
    expect(repository.messages.map(({ message, parentId }) => ({ id: message.id, parentId }))).toEqual([
      { id: 'user-1', parentId: null },
      { id: 'assistant-1', parentId: 'user-1' }
    ])
  })

  it('keeps hidden messages out of the visible parent chain and head', () => {
    const cache = new WeakMap<ChatMessage, ReturnType<typeof buildRuntimeMessageRepository>['messages'][number]['message']>()

    const messages = [
      userMessage('user-1'),
      assistantMessage('hidden-tool-result', 'tool result', { hidden: true }),
      assistantMessage('assistant-1')
    ]

    const repository = buildRuntimeMessageRepository(messages, cache)

    expect(repository.headId).toBe('assistant-1')
    expect(repository.messages.map(({ message, parentId }) => ({ id: message.id, parentId }))).toEqual([
      { id: 'user-1', parentId: null },
      { id: 'hidden-tool-result', parentId: 'user-1' },
      { id: 'assistant-1', parentId: 'user-1' }
    ])
  })

  it('preserves assistant branch parentage by branch group', () => {
    const cache = new WeakMap<ChatMessage, ReturnType<typeof buildRuntimeMessageRepository>['messages'][number]['message']>()

    const messages = [
      userMessage('user-1'),
      assistantMessage('assistant-branch-a', 'A', { branchGroupId: 'branch-1' }),
      assistantMessage('assistant-branch-b', 'B', { branchGroupId: 'branch-1' })
    ]

    const repository = buildRuntimeMessageRepository(messages, cache)

    expect(repository.messages.map(({ message, parentId }) => ({ id: message.id, parentId }))).toEqual([
      { id: 'user-1', parentId: null },
      { id: 'assistant-branch-a', parentId: 'user-1' },
      { id: 'assistant-branch-b', parentId: 'user-1' }
    ])
  })

  it('populates the runtime message cache for unchanged chat message objects', () => {
    const cache = new WeakMap<ChatMessage, ReturnType<typeof buildRuntimeMessageRepository>['messages'][number]['message']>()
    const messages = [userMessage('user-1'), assistantMessage('assistant-1')]

    buildRuntimeMessageRepository(messages, cache)
    const cachedUserMessage = cache.get(messages[0]!)
    const cachedAssistantMessage = cache.get(messages[1]!)

    buildRuntimeMessageRepository(messages, cache)

    expect(cache.get(messages[0]!)).toBe(cachedUserMessage)
    expect(cache.get(messages[1]!)).toBe(cachedAssistantMessage)
  })

  it('reuses unchanged prefix repository items when appending a tail message', () => {
    const runtimeMessageCache = new WeakMap<
      ChatMessage,
      ReturnType<typeof buildRuntimeMessageRepository>['messages'][number]['message']
    >()

    const repositoryCache = { items: [] }
    const firstUser = userMessage('user-1')
    const firstAssistant = assistantMessage('assistant-1')
    const firstMessages = [firstUser, firstAssistant]

    buildRuntimeMessageRepository(firstMessages, runtimeMessageCache, repositoryCache)
    const firstCachedItems = [...repositoryCache.items]
    const appendedMessages = [...firstMessages, userMessage('user-2')]
    const secondRepository = buildRuntimeMessageRepository(appendedMessages, runtimeMessageCache, repositoryCache)

    expect(repositoryCache.items[0]).toBe(firstCachedItems[0])
    expect(repositoryCache.items[1]).toBe(firstCachedItems[1])
    expect(secondRepository.messages.map(({ message, parentId }) => ({ id: message.id, parentId }))).toEqual([
      { id: 'user-1', parentId: null },
      { id: 'assistant-1', parentId: 'user-1' },
      { id: 'user-2', parentId: 'assistant-1' }
    ])
  })
})
