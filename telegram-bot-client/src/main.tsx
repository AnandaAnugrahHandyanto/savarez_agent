import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  callTelegram,
  ChatSummary,
  extractChatsFromUpdates,
  mergeUpdateCache,
  messagePreview,
  messagesForChat,
  TelegramMessage,
  TelegramUpdate,
  tokenCacheKey,
} from './telegram';
import './styles.css';

type BotMe = { id: number; is_bot: boolean; first_name: string; username?: string; can_join_groups?: boolean; can_read_all_group_messages?: boolean };

type LogEntry = { at: string; level: 'ok' | 'error' | 'info'; text: string };

const TOKEN_KEY = 'telegram-bot-client.token';

function timeLabel(seconds?: number) {
  if (!seconds) return '—';
  return new Date(seconds * 1000).toLocaleString();
}

function senderLabel(message: TelegramMessage) {
  if (message.from) return [message.from.first_name, message.from.last_name].filter(Boolean).join(' ') || message.from.username || String(message.from.id);
  if (message.sender_chat) return message.sender_chat.title || message.sender_chat.username || String(message.sender_chat.id);
  return 'unknown';
}

function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY) || '');
  const [cacheKey, setCacheKey] = useState<string>('empty');
  const [updates, setUpdates] = useState<TelegramUpdate[]>([]);
  const [selectedChatId, setSelectedChatId] = useState<number | null>(null);
  const [me, setMe] = useState<BotMe | null>(null);
  const [busy, setBusy] = useState(false);
  const [testText, setTestText] = useState('Test from local Telegram API tester');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [rawResult, setRawResult] = useState<unknown>(null);

  const addLog = (level: LogEntry['level'], text: string) => {
    setLogs((old) => [{ at: new Date().toLocaleTimeString(), level, text }, ...old].slice(0, 30));
  };

  useEffect(() => {
    sessionStorage.setItem(TOKEN_KEY, token);
    let cancelled = false;
    tokenCacheKey(token || 'empty').then((key) => {
      if (cancelled) return;
      setCacheKey(key);
      const cached = localStorage.getItem(`telegram-bot-client.updates.${key}`);
      setUpdates(cached ? JSON.parse(cached) : []);
      setSelectedChatId(null);
    });
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    if (cacheKey !== 'empty') localStorage.setItem(`telegram-bot-client.updates.${cacheKey}`, JSON.stringify(updates));
  }, [cacheKey, updates]);

  const chats = useMemo<ChatSummary[]>(() => extractChatsFromUpdates(updates), [updates]);
  const selectedChat = chats.find((chat) => chat.id === selectedChatId) || null;
  const messages = useMemo(() => (selectedChatId == null ? [] : messagesForChat(updates, selectedChatId)), [updates, selectedChatId]);
  const latestUpdateId = updates.length ? Math.max(...updates.map((update) => update.update_id)) : undefined;

  async function run<T>(label: string, fn: () => Promise<T>, onSuccess?: (result: T) => void) {
    if (!token.trim()) {
      addLog('error', 'Paste a bot token first.');
      return;
    }
    setBusy(true);
    try {
      const result = await fn();
      setRawResult(result);
      onSuccess?.(result);
      addLog('ok', label);
    } catch (error) {
      addLog('error', error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  const refreshUpdates = (offsetMode: 'all' | 'new') =>
    run<TelegramUpdate[]>(
      offsetMode === 'all' ? 'Pulled cached/recent updates.' : 'Pulled new updates.',
      () => callTelegram<TelegramUpdate[]>(token, 'getUpdates', { timeout: 0, allowed_updates: ['message', 'edited_message', 'channel_post', 'edited_channel_post', 'my_chat_member', 'chat_member'], ...(offsetMode === 'new' && latestUpdateId ? { offset: latestUpdateId + 1 } : {}) }),
      (result) => {
        setUpdates((old) => mergeUpdateCache(old, result));
      },
    );

  const getMe = () => run<BotMe>('Bot identity loaded.', () => callTelegram<BotMe>(token, 'getMe'), setMe);
  const getWebhookInfo = () => run('Webhook info loaded.', () => callTelegram(token, 'getWebhookInfo'));
  const getChat = () => selectedChat && run('Chat info loaded.', () => callTelegram(token, 'getChat', { chat_id: selectedChat.id }));
  const getAdmins = () => selectedChat && run('Admins loaded.', () => callTelegram(token, 'getChatAdministrators', { chat_id: selectedChat.id }));
  const sendTestMessage = () => selectedChat && run('Test message sent.', () => callTelegram(token, 'sendMessage', { chat_id: selectedChat.id, text: testText }));

  return (
    <main className="shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Local tester</p>
          <h1>Telegram Bot API Client</h1>
          <p className="muted">Paste a bot token, discover chats from updates, cache them locally, inspect messages, and hit common group-testing actions.</p>
        </div>
        <div className="status-card">
          <strong>{me ? `@${me.username || me.first_name}` : 'No bot loaded'}</strong>
          <span>{updates.length} cached updates</span>
          <span>{chats.length} chats/groups/channels</span>
        </div>
      </header>

      <section className="token-panel">
        <label>
          Bot API token <small>stored in sessionStorage only</small>
          <input value={token} onChange={(event) => setToken(event.target.value.trim())} placeholder="123456:ABC..." type="password" autoComplete="off" />
        </label>
        <div className="button-row">
          <button disabled={busy} onClick={getMe}>Get bot</button>
          <button disabled={busy} onClick={() => refreshUpdates('all')}>Pull chats</button>
          <button disabled={busy} onClick={() => refreshUpdates('new')}>Refresh new</button>
          <button disabled={busy} onClick={getWebhookInfo}>Webhook info</button>
          <button className="ghost" onClick={() => { localStorage.removeItem(`telegram-bot-client.updates.${cacheKey}`); setUpdates([]); setSelectedChatId(null); addLog('info', 'Local cache cleared.'); }}>Clear cache</button>
        </div>
      </section>

      <section className="grid">
        <aside className="card chats">
          <div className="card-header"><h2>Chats</h2><span>{busy ? 'Working…' : 'Ready'}</span></div>
          {chats.length === 0 ? <p className="empty">No chats yet. Send the bot a message or add it to a group, then click Pull chats.</p> : chats.map((chat) => (
            <button key={chat.id} className={`chat-row ${chat.id === selectedChatId ? 'selected' : ''}`} onClick={() => setSelectedChatId(chat.id)}>
              <strong>{chat.label}</strong>
              <span>{chat.type} · {chat.id}</span>
              <small>{chat.lastText || 'No message preview'} · {timeLabel(chat.lastDate)}</small>
            </button>
          ))}
        </aside>

        <section className="card messages">
          <div className="card-header">
            <div><h2>{selectedChat ? selectedChat.label : 'Messages'}</h2><span>{selectedChat ? `${selectedChat.type} ${selectedChat.id}` : 'Pick a chat'}</span></div>
            {selectedChat && <button onClick={() => navigator.clipboard.writeText(String(selectedChat.id))}>Copy chat id</button>}
          </div>

          {selectedChat && <div className="action-box">
            <button disabled={busy} onClick={getChat}>getChat</button>
            <button disabled={busy} onClick={getAdmins}>Admins</button>
            <button disabled={busy} onClick={sendTestMessage}>Send test</button>
            <input value={testText} onChange={(event) => setTestText(event.target.value)} />
          </div>}

          <div className="message-list">
            {!selectedChat && <p className="empty">Select a chat/group/channel to inspect cached updates.</p>}
            {selectedChat && messages.length === 0 && <p className="empty">No message updates cached for this chat.</p>}
            {messages.map((message) => (
              <article className="message" key={`${message.chat.id}:${message.message_id}`}>
                <header><strong>{senderLabel(message)}</strong><span>{timeLabel(message.date)} · #{message.message_id}</span></header>
                <p>{messagePreview(message)}</p>
              </article>
            ))}
          </div>
        </section>

        <aside className="card logs">
          <div className="card-header"><h2>Testing</h2><span>raw API output</span></div>
          <div className="log-list">
            {logs.map((log, i) => <div key={`${log.at}-${i}`} className={`log ${log.level}`}><span>{log.at}</span>{log.text}</div>)}
          </div>
          <pre>{rawResult ? JSON.stringify(rawResult, null, 2) : 'Run a command to see raw JSON here.'}</pre>
        </aside>
      </section>

      <footer className="note">Bot API limitation: it cannot fetch arbitrary chat history or list every group. It discovers chats/messages from updates the bot receives. For full user-account MTProto testing, this would need a different auth flow.</footer>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
