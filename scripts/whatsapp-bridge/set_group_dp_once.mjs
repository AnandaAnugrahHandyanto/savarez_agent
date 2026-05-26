import { makeWASocket, useMultiFileAuthState, fetchLatestBaileysVersion, DisconnectReason } from '@whiskeysockets/baileys';
import { Boom } from '@hapi/boom';
import pino from 'pino';

const groupJid = process.argv[2];
const imagePath = process.argv[3];
const sessionDir = process.argv[4] || '/root/.hermes/whatsapp/session';
if (!groupJid || !imagePath) {
  console.error('usage: node set_group_dp_once.mjs <groupJid> <imagePath> [sessionDir]');
  process.exit(2);
}

const logger = pino({ level: 'silent' });
const { state, saveCreds } = await useMultiFileAuthState(sessionDir);
const { version } = await fetchLatestBaileysVersion();

let done = false;
let sock;
function finish(code, msg) {
  if (done) return;
  done = true;
  if (msg) console.log(msg);
  try { sock?.end?.(); } catch {}
  setTimeout(() => process.exit(code), 300);
}

sock = makeWASocket({
  version,
  auth: state,
  logger,
  printQRInTerminal: false,
  browser: ['Hermes DP Setter', 'Chrome', '120.0'],
  syncFullHistory: false,
  markOnlineOnConnect: false,
  getMessage: async () => ({ conversation: '' }),
});

sock.ev.on('creds.update', saveCreds);
sock.ev.on('connection.update', async (update) => {
  const { connection, lastDisconnect, qr } = update;
  if (qr) {
    console.error('QR requested; existing WhatsApp session is not authenticated.');
    finish(3);
    return;
  }
  if (connection === 'close') {
    const reason = new Boom(lastDisconnect?.error)?.output?.statusCode;
    if (reason === DisconnectReason.loggedOut) finish(4, 'logged out');
  }
  if (connection === 'open') {
    try {
      await sock.updateProfilePicture(groupJid, { url: imagePath });
      let url = '';
      try { url = await sock.profilePictureUrl(groupJid, 'image'); } catch {}
      finish(0, JSON.stringify({ success: true, groupJid, profilePictureUrl: url }));
    } catch (err) {
      console.error(err?.stack || err?.message || String(err));
      finish(1);
    }
  }
});

setTimeout(() => finish(124, 'timed out waiting for WhatsApp connection/update'), 60000);
