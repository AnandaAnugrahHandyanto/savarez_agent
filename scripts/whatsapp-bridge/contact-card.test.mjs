import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildVCardDocumentContent,
  ensureVCardEnvelope,
  safeContactFilename,
  summarizeContactMessage,
  summarizeContactsArrayMessage,
  summarizeVCard,
  unfoldVCardLines,
} from './contact-card.js';

test('summarizeVCard extracts rich contact fields', () => {
  const vcard = [
    'BEGIN:VCARD',
    'VERSION:3.0',
    'FN:Ada Lovelace',
    'ORG:Analytical Engines;Research',
    'TEL;TYPE=CELL,VOICE:+4912345',
    'EMAIL;TYPE=WORK:ada@example.com',
    'ADR;TYPE=HOME:;;Example Street 1;London;;;UK',
    'BDAY:1815-12-10',
    'URL:https://example.com/ada',
    'NOTE:Friend\\, mathematician',
    'END:VCARD',
  ].join('\n');

  const summary = summarizeVCard(vcard);

  assert.match(summary, /Kontakt: Ada Lovelace/);
  assert.match(summary, /Organisation: Analytical Engines \/ Research/);
  assert.match(summary, /Telefon: CELL\/VOICE: \+4912345/);
  assert.match(summary, /E-Mail: WORK: ada@example\.com/);
  assert.match(summary, /Adresse: HOME: Example Street 1, London, UK/);
  assert.match(summary, /Geburtstag: 1815-12-10/);
  assert.match(summary, /URL: https:\/\/example\.com\/ada/);
  assert.match(summary, /Notiz: Friend, mathematician/);
});

test('summarizeContactMessage uses displayName fallback', () => {
  const summary = summarizeContactMessage({ displayName: 'Fallback Name', vcard: 'TEL:+123' });

  assert.match(summary, /Kontakt: Fallback Name/);
  assert.match(summary, /Telefon: \+123/);
});

test('summarizeContactsArrayMessage numbers multiple contacts', () => {
  const summary = summarizeContactsArrayMessage({
    contacts: [
      { displayName: 'One', vcard: 'FN:One\nTEL:+1' },
      { displayName: 'Two', vcard: 'FN:Two\nEMAIL:two@example.com' },
    ],
  });

  assert.match(summary, /^Kontakte empfangen:/);
  assert.match(summary, /1\. Kontakt: One/);
  assert.match(summary, /2\. Kontakt: Two/);
  assert.match(summary, /E-Mail: two@example\.com/);
});

test('buildVCardDocumentContent preserves and envelopes incoming vCards', () => {
  const content = buildVCardDocumentContent([
    { displayName: 'Raw', vcard: 'BEGIN:VCARD\nFN:Raw\nEND:VCARD' },
    { displayName: 'Partial', vcard: 'TEL:+42' },
  ]);

  assert.match(content, /BEGIN:VCARD\nFN:Raw\nEND:VCARD\n/);
  assert.match(content, /BEGIN:VCARD\nVERSION:3\.0\nFN:Partial\nTEL:\+42\nEND:VCARD\n/);
});

test('ensureVCardEnvelope creates an empty card when no payload exists', () => {
  assert.equal(
    ensureVCardEnvelope('', 'No Payload'),
    'BEGIN:VCARD\nVERSION:3.0\nFN:No Payload\nEND:VCARD\n',
  );
});

test('safeContactFilename strips unsafe characters', () => {
  assert.equal(safeContactFilename('Äda / Lovelace:work'), 'Ada_Lovelace_work');
});

test('unfoldVCardLines joins folded continuation lines', () => {
  assert.deepEqual(
    unfoldVCardLines('NOTE:very long\n line\nFN:Name'),
    ['NOTE:very longline', 'FN:Name'],
  );
});
