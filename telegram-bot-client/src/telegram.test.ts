import { describe, expect, it } from 'vitest';
import { extractChatsFromUpdates, mergeMessageCache } from './telegram';

describe('extractChatsFromUpdates', () => {
  it('deduplicates chats and keeps latest message previews', () => {
    const updates = [
      { update_id: 1, message: { message_id: 10, date: 100, chat: { id: 1, type: 'private', first_name: 'A' }, text: 'hello' } },
      { update_id: 2, channel_post: { message_id: 11, date: 101, chat: { id: -100, type: 'channel', title: 'News' }, text: 'post' } },
      { update_id: 3, message: { message_id: 12, date: 102, chat: { id: 1, type: 'private', first_name: 'A' }, text: 'newer' } },
    ];

    expect(extractChatsFromUpdates(updates)).toEqual([
      expect.objectContaining({ id: 1, label: 'A', type: 'private', lastText: 'newer' }),
      expect.objectContaining({ id: -100, label: 'News', type: 'channel', lastText: 'post' }),
    ]);
  });
});

describe('mergeMessageCache', () => {
  it('deduplicates messages by chat id and message id', () => {
    const existing = [{ message_id: 1, date: 1, chat: { id: 2, type: 'group', title: 'G' }, text: 'old' }];
    const incoming = [
      { message_id: 1, date: 1, chat: { id: 2, type: 'group', title: 'G' }, text: 'old duplicate' },
      { message_id: 2, date: 2, chat: { id: 2, type: 'group', title: 'G' }, text: 'new' },
    ];

    expect(mergeMessageCache(existing, incoming)).toEqual([
      expect.objectContaining({ message_id: 1, text: 'old' }),
      expect.objectContaining({ message_id: 2, text: 'new' }),
    ]);
  });
});
