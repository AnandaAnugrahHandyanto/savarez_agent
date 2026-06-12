const DEFAULT_SNIPPET_LIMIT = 1000;

function toPositiveLimit(value, fallback = DEFAULT_SNIPPET_LIMIT) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 1) return fallback;
  return Math.floor(parsed);
}

export function sanitizeMessageSnippet(value, maxLength = DEFAULT_SNIPPET_LIMIT) {
  if (value === null || value === undefined) return '';
  const limit = toPositiveLimit(maxLength);
  let text = String(value)
    .replace(/\r\n?/g, '\n')
    // Keep newlines, but strip other control characters before this text is
    // injected into the Python-side reply-context prefix.
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, ' ')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  if (!text) return '';
  if (text.length <= limit) return text;
  return `${text.slice(0, Math.max(0, limit - 1)).trimEnd()}…`;
}

export function unwrapMessageContent(content) {
  let current = content && typeof content === 'object' ? content : {};

  for (let i = 0; i < 8; i += 1) {
    if (current.ephemeralMessage?.message) {
      current = current.ephemeralMessage.message;
      continue;
    }
    if (current.viewOnceMessage?.message) {
      current = current.viewOnceMessage.message;
      continue;
    }
    if (current.viewOnceMessageV2?.message) {
      current = current.viewOnceMessageV2.message;
      continue;
    }
    if (current.documentWithCaptionMessage?.message) {
      current = current.documentWithCaptionMessage.message;
      continue;
    }
    if (current.templateMessage?.hydratedTemplate) {
      return current.templateMessage.hydratedTemplate;
    }
    if (current.buttonsMessage) return current.buttonsMessage;
    if (current.listMessage) return current.listMessage;
    return current;
  }

  return current;
}

export function getMessageContent(msg) {
  return unwrapMessageContent(msg?.message || {});
}

export function getContextInfo(messageContent) {
  if (!messageContent || typeof messageContent !== 'object') return {};
  if (messageContent.contextInfo) return messageContent.contextInfo;
  for (const value of Object.values(messageContent)) {
    if (value && typeof value === 'object' && value.contextInfo) {
      return value.contextInfo;
    }
  }
  return {};
}

function mediaText(kind, caption, maxLength) {
  const cleanCaption = sanitizeMessageSnippet(caption, maxLength);
  return cleanCaption ? `[${kind} message] ${cleanCaption}` : `[${kind} message]`;
}

export function extractMessageText(messageContent, maxLength = DEFAULT_SNIPPET_LIMIT) {
  const content = unwrapMessageContent(messageContent);
  let text = '';

  if (content.conversation) {
    text = content.conversation;
  } else if (content.extendedTextMessage?.text) {
    text = content.extendedTextMessage.text;
  } else if (content.imageMessage) {
    text = mediaText('image', content.imageMessage.caption || '', maxLength);
  } else if (content.videoMessage) {
    text = mediaText('video', content.videoMessage.caption || '', maxLength);
  } else if (content.documentMessage) {
    const fileName = content.documentMessage.fileName
      ? `: ${content.documentMessage.fileName}`
      : '';
    const caption = content.documentMessage.caption || '';
    const cleanCaption = sanitizeMessageSnippet(caption, maxLength);
    text = cleanCaption
      ? `[document message${fileName}] ${cleanCaption}`
      : `[document message${fileName}]`;
  } else if (content.audioMessage || content.pttMessage) {
    text = content.pttMessage ? '[voice message]' : '[audio message]';
  } else if (content.stickerMessage) {
    text = '[sticker message]';
  } else if (content.locationMessage) {
    const name = content.locationMessage.name || content.locationMessage.address || '';
    text = name ? `[location message] ${name}` : '[location message]';
  } else if (content.contactMessage) {
    const name = content.contactMessage.displayName || '';
    text = name ? `[contact message] ${name}` : '[contact message]';
  } else if (content.contactsArrayMessage?.contacts?.length) {
    const names = content.contactsArrayMessage.contacts
      .map(contact => contact.displayName)
      .filter(Boolean)
      .join(', ');
    text = names ? `[contacts message] ${names}` : '[contacts message]';
  } else if (content.buttonsResponseMessage) {
    text = content.buttonsResponseMessage.selectedDisplayText
      || content.buttonsResponseMessage.selectedButtonId
      || '';
  } else if (content.listResponseMessage) {
    text = content.listResponseMessage.title
      || content.listResponseMessage.singleSelectReply?.selectedRowId
      || '';
  } else if (content.templateButtonReplyMessage) {
    text = content.templateButtonReplyMessage.selectedDisplayText
      || content.templateButtonReplyMessage.selectedId
      || '';
  } else if (content.pollCreationMessage?.name || content.pollCreationMessageV3?.name) {
    text = `[poll message] ${content.pollCreationMessage?.name || content.pollCreationMessageV3?.name}`;
  }

  return sanitizeMessageSnippet(text, maxLength);
}

export function extractQuotedMessageText(contextInfo, maxLength = DEFAULT_SNIPPET_LIMIT) {
  if (!contextInfo?.quotedMessage) return '';
  return extractMessageText(contextInfo.quotedMessage, maxLength);
}
