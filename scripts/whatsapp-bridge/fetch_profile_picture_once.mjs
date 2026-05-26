import makeWASocket, { useMultiFileAuthState, DisconnectReason } from '@whiskeysockets/baileys';
import pino from 'pino';

const chatId = process.argv[2];
if (!chatId) {
  console.error('usage: node fetch_profile_picture_once.mjs <jid>');
  process.exit(2);
}
const sessionDir = '/root/.hermes/whatsapp/session';
const logger = pino({ level: 'silent' });
let finished = false;
function finish(code, obj, sock) {
  if (finished) return;
  finished = true;
  clearTimeout(timeout);
  const out = JSON.stringify(obj);
  if (code === 0) console.log(out); else console.error(out);
  try { sock?.end?.(); } catch {}
  process.exit(code);
}
const timeout = setTimeout(() => finish(1, { success: false, chatId, error: 'timeout' }), 45000);

const { state, saveCreds } = await useMultiFileAuthState(sessionDir);
const sock = makeWASocket({ auth: state, logger, printQRInTerminal: false, browser: ['Hermes', 'Chrome', '1.0.0'], syncFullHistory: false, markOnlineOnConnect: false });
sock.ev.on('creds.update', saveCreds);
sock.ev.on('connection.update', async (update) => {
  const { connection, lastDisconnect } = update;
  if (connection === 'open') {
    try {
      const url = await sock.profilePictureUrl(chatId, 'image');
      finish(0, { success: true, chatId, profilePictureUrl: url }, sock);
    } catch (err) {
      finish(1, { success: false, chatId, error: err?.message || String(err) }, sock);
    }
  }
  if (connection === 'close') {
    const code = lastDisconnect?.error?.output?.statusCode;
    if (!finished && code !== DisconnectReason.restartRequired) {
      finish(1, { success: false, chatId, error: 'Connection Closed', statusCode: code }, sock);
    }
  }
});
