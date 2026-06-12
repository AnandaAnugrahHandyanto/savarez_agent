import assert from 'node:assert/strict';
import test from 'node:test';

import {
  extractQuotedMessageText,
  getContextInfo,
  getMessageContent,
  sanitizeMessageSnippet,
} from './message-utils.js';

test('extracts text from a quoted WhatsApp conversation payload', () => {
  const msg = {
    message: {
      extendedTextMessage: {
        text: 'yes',
        contextInfo: {
          stanzaId: 'orig-msg-1',
          participant: '15551234567@s.whatsapp.net',
          quotedMessage: {
            conversation: 'Should I book the 4pm flight?',
          },
        },
      },
    },
  };

  const content = getMessageContent(msg);
  const contextInfo = getContextInfo(content);

  assert.equal(extractQuotedMessageText(contextInfo), 'Should I book the 4pm flight?');
});

test('extracts caption/type context from quoted media payloads', () => {
  const contextInfo = {
    quotedMessage: {
      imageMessage: {
        caption: 'Use this design for the launch post',
      },
    },
  };

  assert.equal(
    extractQuotedMessageText(contextInfo),
    '[image message] Use this design for the launch post',
  );
});

test('quoted snippets are sanitized and bounded', () => {
  const dirty = `first${String.fromCharCode(0, 7)}\r\n${'x'.repeat(1200)}`;
  const snippet = sanitizeMessageSnippet(dirty, 80);

  assert.equal(snippet.includes(String.fromCharCode(0)), false);
  assert.equal(snippet.includes(String.fromCharCode(7)), false);
  assert.equal(snippet.includes('\r'), false);
  assert.equal(snippet.endsWith('…'), true);
  assert.equal(snippet.length <= 80, true);
});
