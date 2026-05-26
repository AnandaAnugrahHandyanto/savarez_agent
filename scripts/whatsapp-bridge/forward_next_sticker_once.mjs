import { makeWASocket, useMultiFileAuthState, fetchLatestBaileysVersion, DisconnectReason, downloadMediaMessage } from '@whiskeysockets/baileys';
import { Boom } from '@hapi/boom';
import pino from 'pino';
import { randomBytes } from 'crypto';
import { mkdirSync, writeFileSync } from 'fs';
import path from 'path';

const fromJids = new Set((process.argv[2] || '').split(',').filter(Boolean));
const toJid = process.argv[3];
const sessionDir = process.argv[4] || '/root/.hermes/whatsapp/session';
const cacheDir = '/root/.hermes/document_cache';

if (!fromJids.size || !toJid) {
  console.error('usage: node forward_next_sticker_once.mjs <fromJid[,fromJid2]> <toJid> [sessionDir]');
  process.exit(2);
}

const logger = pino({ level: 'silent' });
const { state, saveCreds } = await useMultiFileAuthState(sessionDir);
const { version } = await fetchLatestBaileysVersion();

let done = false;
let sock;
function finish(code, payload) {
  if (done) return;
  done = true;
  if (payload) console.log(typeof payload === 'string' ? payload : JSON.stringify(payload));
  try { sock?.end?.(); } catch {}
  setTimeout(() => process.exit(code), 300);
}

function unwrapMessage(message) {
  if (!message) return message;
  if (message.ephemeralMessage?.message) return unwrapMessage(message.ephemeralMessage.message);
  if (message.viewOnceMessage?.message) return unwrapMessage(message.viewOnceMessage.message);
  if (message.viewOnceMessageV2?.message) return unwrapMessage(message.viewOnceMessageV2.message);
  return message;
}

function isFromAllowed(msg) {
  const remote = msg?.key?.remoteJid;
  const participant = msg?.key?.participant;
  return fromJids.has(remote) || fromJids.has(participant);
}

sock = makeWASocket({
  version,
  auth: state,
  logger,
  printQRInTerminal: false,
  browser: ['Hermes Sticker Forwarder', 'Chrome', '120.0'],
  syncFullHistory: false,
  markOnlineOnConnect: false,
  getMessage: async () => ({ conversation: '' }),
});

sock.ev.on('creds.update', saveCreds);

sock.ev.on('connection.update', (update) => {
  const { connection, lastDisconnect, qr } = update;
  if (qr) return finish(3, { success: false, error: 'QR requested; session not authenticated' });
  if (connection === 'close') {
    const reason = new Boom(lastDisconnect?.error)?.output?.statusCode;
    if (reason === DisconnectReason.loggedOut) finish(4, { success: false, error: 'logged out' });
  }
  if (connection === 'open') {
    console.log(JSON.stringify({ listening: true, from: Array.from(fromJids), toJid, timeoutMs: 120000 }));
  }
});

sock.ev.on('messages.upsert', async ({ messages, type }) => {
  if (done || type !== 'notify') return;
  for (const msg of messages || []) {
    if (done || msg?.key?.fromMe) continue;
    if (!isFromAllowed(msg)) continue;
    const unwrapped = unwrapMessage(msg.message);
    const sticker = unwrapped?.stickerMessage;
    if (!sticker) continue;
    try {
      let response;
      try {
        response = await sock.sendMessage(toJid, { forward: msg, force: true });
        return finish(0, { success: true, method: 'native_forward', toJid, messageId: response?.key?.id || null, sourceMessageId: msg?.key?.id || null });
      } catch (forwardErr) {
        mkdirSync(cacheDir, { recursive: true });
        const filePath = path.join(cacheDir, `sticker_${randomBytes(6).toString('hex')}.webp`);
        const buf = await downloadMediaMessage(msg, 'buffer', {}, { logger, reuploadRequest: sock.updateMediaMessage });
        writeFileSync(filePath, buf);
        response = await sock.sendMessage(toJid, { sticker: { url: filePath } });
        return finish(0, { success: true, method: 'sticker_reupload', toJid, messageId: response?.key?.id || null, sourceMessageId: msg?.key?.id || null, filePath, forwardError: forwardErr?.message || String(forwardErr) });
      }
    } catch (err) {
      return finish(1, { success: false, error: err?.stack || err?.message || String(err), sourceMessageId: msg?.key?.id || null });
    }
  }
});

setTimeout(() => finish(124, { success: false, error: 'timed out waiting for sticker' }), 120000);
