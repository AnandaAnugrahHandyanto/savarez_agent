/**
 * WhatsApp contact card (vCard) helpers.
 *
 * The bridge needs two representations for incoming contact cards:
 * 1. a readable summary for the agent message body
 * 2. the original vCard payload preserved as a cached .vcf document
 */

export function decodeVCardValue(value = '') {
  return String(value)
    .replace(/\\n/g, '\n')
    .replace(/\\,/g, ',')
    .replace(/\\;/g, ';')
    .trim();
}

export function unfoldVCardLines(vcard = '') {
  const rawLines = String(vcard || '').split(/\r?\n/);
  const lines = [];
  for (const raw of rawLines) {
    if (/^[ \t]/.test(raw) && lines.length) {
      // RFC 6350 line folding: continuation lines start with space/tab.
      lines[lines.length - 1] += raw.slice(1);
    } else {
      lines.push(raw);
    }
  }
  return lines;
}

function parseVCardParams(key = '') {
  const parts = String(key || '').split(';');
  const field = (parts.shift() || '').toUpperCase();
  const params = [];
  for (const part of parts) {
    const [rawName, rawValue] = part.split('=');
    const name = String(rawName || '').toUpperCase();
    const values = rawValue ? rawValue.split(',') : [part];
    for (const value of values) {
      const cleaned = String(value || '').replace(/^"|"$/g, '').trim();
      if (cleaned && name !== 'VALUE') params.push(cleaned);
    }
  }
  return { field, params };
}

function uniqueItems(values) {
  const unique = [];
  const seen = new Set();
  for (const item of values) {
    const value = item.value || '';
    if (!value) continue;
    const key = `${item.type || ''}\u0000${value}`;
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(item);
  }
  return unique;
}

function formatVCardValues(label, values) {
  const unique = uniqueItems(values);
  if (!unique.length) return '';
  if (unique.length === 1) {
    const item = unique[0];
    return `${label}: ${item.type ? `${item.type}: ` : ''}${item.value}`;
  }
  return `${label}:\n${unique.map((item, i) => `  ${i + 1}. ${item.type ? `${item.type}: ` : ''}${item.value}`).join('\n')}`;
}

export function summarizeVCard(vcard = '', fallbackName = '') {
  const lines = unfoldVCardLines(vcard);
  const names = [];
  const orgs = [];
  const phones = [];
  const emails = [];
  const addresses = [];
  const urls = [];
  const notes = [];
  const birthdays = [];
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) continue;
    const idx = line.indexOf(':');
    if (idx === -1) continue;
    const { field, params } = parseVCardParams(line.slice(0, idx));
    const value = decodeVCardValue(line.slice(idx + 1));
    if (!value) continue;
    const type = params.join('/');
    if (field === 'FN') names.push(value);
    else if (field === 'N' && !names.length) names.push(value.split(';').filter(Boolean).join(' '));
    else if (field === 'ORG') orgs.push(value.split(';').filter(Boolean).join(' / '));
    else if (field === 'TEL') phones.push({ type, value });
    else if (field === 'EMAIL') emails.push({ type, value });
    else if (field === 'ADR') addresses.push({ type, value: value.split(';').filter(Boolean).join(', ') });
    else if (field === 'URL') urls.push({ type, value });
    else if (field === 'NOTE') notes.push(value);
    else if (field === 'BDAY') birthdays.push(value);
  }
  const name = names[0] || fallbackName || 'Unbekannter Kontakt';
  const parts = [`Kontakt: ${name}`];
  if (orgs.length) parts.push(`Organisation: ${Array.from(new Set(orgs)).join(', ')}`);
  const phoneText = formatVCardValues('Telefon', phones);
  const emailText = formatVCardValues('E-Mail', emails);
  const addressText = formatVCardValues('Adresse', addresses);
  const urlText = formatVCardValues('URL', urls);
  if (phoneText) parts.push(phoneText);
  if (emailText) parts.push(emailText);
  if (addressText) parts.push(addressText);
  if (birthdays.length) parts.push(`Geburtstag: ${Array.from(new Set(birthdays)).join(', ')}`);
  if (urlText) parts.push(urlText);
  if (notes.length) parts.push(`Notiz: ${Array.from(new Set(notes)).join(' / ')}`);
  return parts.join('\n');
}

export function ensureVCardEnvelope(vcard = '', displayName = '') {
  const text = String(vcard || '').trim();
  if (text) {
    if (/BEGIN:VCARD/i.test(text)) return text.endsWith('\n') ? text : `${text}\n`;
    return `BEGIN:VCARD\nVERSION:3.0\nFN:${displayName || 'Unbekannter Kontakt'}\n${text}\nEND:VCARD\n`;
  }
  return `BEGIN:VCARD\nVERSION:3.0\nFN:${displayName || 'Unbekannter Kontakt'}\nEND:VCARD\n`;
}

export function safeContactFilename(name = 'contact') {
  return String(name || 'contact')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9._-]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 80) || 'contact';
}

export function buildVCardDocumentContent(vcards, displayName = 'contacts') {
  return (Array.isArray(vcards) ? vcards : [vcards])
    .map((entry) => ensureVCardEnvelope(entry?.vcard || entry || '', entry?.displayName || displayName))
    .filter(Boolean)
    .join('\n');
}

export function summarizeContactMessage(contactMessage = {}) {
  return summarizeVCard(contactMessage.vcard || '', contactMessage.displayName || '');
}

export function summarizeContactsArrayMessage(contactsArrayMessage = {}) {
  const contacts = contactsArrayMessage.contacts || [];
  const summaries = contacts.map((contact, index) => {
    const summary = summarizeVCard(contact.vcard || '', contact.displayName || '');
    return `${index + 1}. ${summary}`;
  });
  return summaries.length
    ? `Kontakte empfangen:\n${summaries.join('\n')}`
    : '[contacts received]';
}
