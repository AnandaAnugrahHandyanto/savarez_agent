export type TelegramChat = {
  id: number;
  type: 'private' | 'group' | 'supergroup' | 'channel' | string;
  title?: string;
  username?: string;
  first_name?: string;
  last_name?: string;
};

export type TelegramMessage = {
  message_id: number;
  date: number;
  chat: TelegramChat;
  text?: string;
  caption?: string;
  from?: { id: number; first_name?: string; last_name?: string; username?: string; is_bot?: boolean };
  sender_chat?: TelegramChat;
  [key: string]: unknown;
};

export type TelegramUpdate = {
  update_id: number;
  message?: TelegramMessage;
  edited_message?: TelegramMessage;
  channel_post?: TelegramMessage;
  edited_channel_post?: TelegramMessage;
  my_chat_member?: { chat: TelegramChat; date?: number };
  chat_member?: { chat: TelegramChat; date?: number };
  [key: string]: unknown;
};

export type ChatSummary = TelegramChat & {
  label: string;
  lastMessageId?: number;
  lastDate?: number;
  lastText?: string;
  updateCount: number;
};

export type ApiResponse<T> = { ok: true; result: T } | { ok: false; description?: string; error_code?: number };

export function messageFromUpdate(update: TelegramUpdate): TelegramMessage | undefined {
  return update.message ?? update.edited_message ?? update.channel_post ?? update.edited_channel_post;
}

export function chatFromUpdate(update: TelegramUpdate): TelegramChat | undefined {
  return messageFromUpdate(update)?.chat ?? update.my_chat_member?.chat ?? update.chat_member?.chat;
}

export function chatLabel(chat: TelegramChat): string {
  const fullName = [chat.first_name, chat.last_name].filter(Boolean).join(' ').trim();
  return chat.title || fullName || chat.username || String(chat.id);
}

export function messagePreview(message: TelegramMessage): string {
  if (message.text) return message.text;
  if (message.caption) return message.caption;
  if (message.photo) return '[photo]';
  if (message.document) return '[document]';
  if (message.voice) return '[voice]';
  if (message.video) return '[video]';
  if (message.sticker) return '[sticker]';
  return '[non-text update]';
}

export function extractChatsFromUpdates(updates: TelegramUpdate[]): ChatSummary[] {
  const byId = new Map<number, ChatSummary>();

  for (const update of updates) {
    const chat = chatFromUpdate(update);
    if (!chat) continue;
    const message = messageFromUpdate(update);
    const existing = byId.get(chat.id);
    const candidate: ChatSummary = {
      ...(existing ?? chat),
      ...chat,
      label: chatLabel(chat),
      updateCount: (existing?.updateCount ?? 0) + 1,
      lastMessageId: message?.message_id ?? existing?.lastMessageId,
      lastDate: message?.date ?? update.my_chat_member?.date ?? update.chat_member?.date ?? existing?.lastDate,
      lastText: message ? messagePreview(message) : existing?.lastText,
    };
    byId.set(chat.id, candidate);
  }

  return [...byId.values()].sort((a, b) => (b.lastDate ?? 0) - (a.lastDate ?? 0));
}

export function messagesForChat(updates: TelegramUpdate[], chatId: number): TelegramMessage[] {
  return updates
    .map(messageFromUpdate)
    .filter((message): message is TelegramMessage => Boolean(message && message.chat?.id === chatId))
    .sort((a, b) => a.date - b.date || a.message_id - b.message_id);
}

export function mergeMessageCache(existing: TelegramMessage[], incoming: TelegramMessage[]): TelegramMessage[] {
  const byKey = new Map<string, TelegramMessage>();
  for (const message of existing) byKey.set(`${message.chat.id}:${message.message_id}`, message);
  for (const message of incoming) {
    const key = `${message.chat.id}:${message.message_id}`;
    if (!byKey.has(key)) byKey.set(key, message);
  }
  return [...byKey.values()].sort((a, b) => a.date - b.date || a.message_id - b.message_id);
}

export function mergeUpdateCache(existing: TelegramUpdate[], incoming: TelegramUpdate[]): TelegramUpdate[] {
  const byId = new Map<number, TelegramUpdate>();
  for (const update of existing) byId.set(update.update_id, update);
  for (const update of incoming) byId.set(update.update_id, update);
  return [...byId.values()].sort((a, b) => a.update_id - b.update_id).slice(-1000);
}

export async function tokenCacheKey(token: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(token));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('').slice(0, 16);
}

export async function callTelegram<T>(token: string, method: string, params: Record<string, unknown> = {}): Promise<T> {
  const response = await fetch(`/api/telegram/${method}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, params }),
  });
  const json = (await response.json()) as ApiResponse<T>;
  if (!json.ok) throw new Error(json.description || `Telegram API error ${response.status}`);
  return json.result;
}
