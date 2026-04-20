import type {
  ChatAppState,
  ChatAttachment,
  ChatMessage,
  ChatThread,
  ChatWorkspace,
  MemoryItem,
  OutputMode,
} from './types';

const STORAGE_KEY = 'hermes.chat-studio.state.v1';
export const APP_VERSION = 1;

const now = () => new Date().toISOString();

function id(prefix: string) {
  const suffix = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  return `${prefix}_${suffix}`;
}

export function normalizeText(value: string) {
  return value
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
}

export function deriveChatTitle(text: string) {
  const cleaned = text
    .replace(/\s+/g, ' ')
    .replace(/[\u2018\u2019\u201c\u201d"'`]/g, '')
    .replace(/[!?.,;:]+$/g, '')
    .trim();

  const keywords = cleaned
    .split(' ')
    .filter((word) => word.length > 2)
    .slice(0, 6)
    .join(' ')
    .trim();

  if (!keywords) return 'Novo chat';
  return keywords[0].toUpperCase() + keywords.slice(1);
}

export function createChat(workspaceId: string, title = 'Novo chat'): ChatThread {
  const stamp = now();
  return {
    id: id('chat'),
    workspaceId,
    title,
    summary: 'Conversa pronta para começar.',
    createdAt: stamp,
    updatedAt: stamp,
    archivedAt: null,
    pinned: false,
  };
}

export function createUserMessage(params: {
  chatId: string;
  content: string;
  attachments?: ChatAttachment[];
}): ChatMessage {
  return {
    id: id('msg'),
    chatId: params.chatId,
    role: 'user',
    content: params.content,
    createdAt: now(),
    segments: [],
    attachments: params.attachments ?? [],
  };
}

export function createAssistantMessage(params: {
  chatId: string;
  content: string;
  segments?: ChatMessage['segments'];
}): ChatMessage {
  return {
    id: id('msg'),
    chatId: params.chatId,
    role: 'assistant',
    content: params.content,
    createdAt: now(),
    segments: params.segments ?? [],
    attachments: [],
  };
}

export function createMemory(params: {
  scope: MemoryItem['scope'];
  chatId: string | null;
  kind: MemoryItem['kind'];
  content: string;
  sourceMessageId: string | null;
  confidence?: number;
  pinned?: boolean;
}): MemoryItem {
  const stamp = now();
  return {
    id: id('mem'),
    scope: params.scope,
    chatId: params.chatId,
    kind: params.kind,
    content: params.content.trim(),
    sourceMessageId: params.sourceMessageId,
    confidence: params.confidence ?? 0.82,
    pinned: params.pinned ?? false,
    createdAt: stamp,
    updatedAt: stamp,
  };
}

export function createAttachment(params: {
  chatId: string;
  messageId: string;
  name: string;
  mimeType: string;
  url: string;
  size: number;
}): ChatAttachment {
  return {
    id: id('att'),
    chatId: params.chatId,
    messageId: params.messageId,
    name: params.name,
    type: params.mimeType.startsWith('image/') ? 'image' : 'file',
    mimeType: params.mimeType,
    url: params.url,
    size: params.size,
  };
}

function seedState(): ChatAppState {
  const workspaces: ChatWorkspace[] = [
    {
      id: 'ws_personal',
      name: 'Pessoal',
      description: 'Conversas rápidas, decisões e memória pessoal.',
      accent: 'amber',
    },
    {
      id: 'ws_mcf',
      name: 'MCF',
      description: 'Estratégia, marketing e liderança.',
      accent: 'teal',
    },
    {
      id: 'ws_product',
      name: 'Produto',
      description: 'Interfaces, protótipos e execução.',
      accent: 'violet',
    },
  ];

  const chats: ChatThread[] = [
    {
      id: 'chat_blueprint',
      workspaceId: 'ws_product',
      title: 'Blueprint do chat pessoal',
      summary: 'Interface de chat com memória, multimodalidade e deploy simples.',
      createdAt: '2026-04-19T11:00:00.000Z',
      updatedAt: '2026-04-19T11:08:00.000Z',
      archivedAt: null,
      pinned: true,
    },
    {
      id: 'chat_deploy',
      workspaceId: 'ws_product',
      title: 'Deploy Netlify / GitHub',
      summary: 'Uma base estática com persistência local e caminho claro para Supabase.',
      createdAt: '2026-04-19T10:50:00.000Z',
      updatedAt: '2026-04-19T10:58:00.000Z',
      archivedAt: null,
      pinned: false,
    },
    {
      id: 'chat_memory',
      workspaceId: 'ws_personal',
      title: 'Preferências e memória global',
      summary: 'Tom direto, português do Brasil e histórico persistente por assunto.',
      createdAt: '2026-04-19T10:35:00.000Z',
      updatedAt: '2026-04-19T10:42:00.000Z',
      archivedAt: null,
      pinned: false,
    },
  ];

  const messages: ChatMessage[] = [
    createAssistantMessage({
      chatId: 'chat_blueprint',
      content: [
        '### Pronto para começar.',
        '',
        'Vou te ajudar a organizar este chat como uma interface pessoal com:',
        '',
        '- múltiplos chats por assunto',
        '- memória global e memória por chat',
        '- entrada de texto e imagem no MVP',
        '- saída em texto, imagem, áudio e código',
        '',
        'Use o composer abaixo para testar o fluxo.'
      ].join('\n'),
      segments: [],
    }),
    createUserMessage({
      chatId: 'chat_blueprint',
      content: 'Quero uma interface de chat online com memória persistente, bem organizada por assuntos.',
    }),
    createAssistantMessage({
      chatId: 'chat_memory',
      content: '### Memória ativa\n\n- português do Brasil\n- tom direto\n- uso pessoal, sem multiusuário no início\n- foco em desktop e mobile',
      segments: [],
    }),
  ];

  const memories: MemoryItem[] = [
    createMemory({
      scope: 'global',
      chatId: null,
      kind: 'preference',
      content: 'Idioma padrão: português do Brasil.',
      sourceMessageId: null,
      confidence: 0.99,
      pinned: true,
    }),
    createMemory({
      scope: 'global',
      chatId: null,
      kind: 'preference',
      content: 'Estilo de comunicação: direto, sem rodeios.',
      sourceMessageId: null,
      confidence: 0.96,
      pinned: true,
    }),
    createMemory({
      scope: 'chat',
      chatId: 'chat_blueprint',
      kind: 'project',
      content: 'Projeto atual: interface de chat pessoal com memória persistente, imagens no MVP e áudio na fase 2.',
      sourceMessageId: null,
      confidence: 0.94,
      pinned: false,
    }),
  ];

  return {
    version: APP_VERSION,
    workspaces,
    chats,
    messages,
    memories,
    activeWorkspaceId: 'ws_product',
    activeChatId: 'chat_blueprint',
  };
}

export function loadAppState(): ChatAppState {
  if (typeof window === 'undefined') return seedState();

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return seedState();

    const parsed = JSON.parse(raw) as Partial<ChatAppState>;
    if (!parsed || !Array.isArray(parsed.workspaces) || !Array.isArray(parsed.chats)) {
      return seedState();
    }

    return {
      version: APP_VERSION,
      workspaces: parsed.workspaces,
      chats: parsed.chats,
      messages: Array.isArray(parsed.messages) ? parsed.messages : [],
      memories: Array.isArray(parsed.memories) ? parsed.memories : [],
      activeWorkspaceId: parsed.activeWorkspaceId || parsed.workspaces[0]?.id || 'ws_product',
      activeChatId: parsed.activeChatId || parsed.chats[0]?.id || 'chat_blueprint',
    };
  } catch {
    return seedState();
  }
}

export function saveAppState(state: ChatAppState) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

export function getChatMessages(state: ChatAppState, chatId: string) {
  return state.messages.filter((message) => message.chatId === chatId);
}

export function sortChats(chats: ChatThread[]) {
  return [...chats].sort((a, b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
    return b.updatedAt.localeCompare(a.updatedAt);
  });
}

export function deriveMemorySuggestions(params: {
  chatId: string;
  messageId: string;
  userText: string;
}) {
  const text = params.userText.trim();
  const normalized = normalizeText(text);
  const memories: MemoryItem[] = [];

  const add = (scope: MemoryItem['scope'], kind: MemoryItem['kind'], content: string, pinned = false) => {
    memories.push(createMemory({
      scope,
      chatId: scope === 'chat' ? params.chatId : null,
      kind,
      content,
      sourceMessageId: params.messageId,
      pinned,
    }));
  };

  if (/me chame de|pode me chamar de|sempre me chame de/.test(normalized)) {
    add('global', 'preference', `Preferência de tratamento extraída: ${text}`, true);
  }

  if (/sempre em portugues|portugues do brasil|pt[- ]?br|sempre em pt/.test(normalized)) {
    add('global', 'preference', 'Idioma padrão: português do Brasil.', true);
  }

  if (/direto|sem rodeios|objetivo|conciso/.test(normalized)) {
    add('global', 'preference', 'Tom preferido: direto, sem rodeios, com objetividade.', true);
  }

  if (/netlify|github|supabase|deploy|mvp|wireframe|arquitet|interface|chat|memoria|audio|imagem|codigo/.test(normalized)) {
    add(
      'chat',
      'project',
      `Contexto deste chat: ${text.slice(0, 180)}${text.length > 180 ? '…' : ''}`,
      false,
    );
  }

  return memories;
}

export function dedupeMemories(existing: MemoryItem[], incoming: MemoryItem[]) {
  const seen = new Set(existing.map((memory) => normalizeText(memory.content)));
  return incoming.filter((memory) => {
    const key = normalizeText(memory.content);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function mergeChatChanges(
  state: ChatAppState,
  chatId: string,
  patch: Partial<ChatThread>,
) {
  return {
    ...state,
    chats: state.chats.map((chat) => (chat.id === chatId ? { ...chat, ...patch } : chat)),
  };
}

export function updateChatSummary(state: ChatAppState, chatId: string, summary: string) {
  return mergeChatChanges(state, chatId, {
    summary,
    updatedAt: now(),
  });
}

export function pinChat(state: ChatAppState, chatId: string, pinned: boolean) {
  return mergeChatChanges(state, chatId, {
    pinned,
    updatedAt: now(),
  });
}

export function archiveChat(state: ChatAppState, chatId: string) {
  return mergeChatChanges(state, chatId, {
    archivedAt: now(),
    updatedAt: now(),
  });
}

export function unarchiveChat(state: ChatAppState, chatId: string) {
  return mergeChatChanges(state, chatId, {
    archivedAt: null,
    updatedAt: now(),
  });
}

export function updateWorkspaceForChat(state: ChatAppState, chatId: string, workspaceId: string) {
  return mergeChatChanges(state, chatId, {
    workspaceId,
    updatedAt: now(),
  });
}

export function appendMessage(state: ChatAppState, message: ChatMessage) {
  return {
    ...state,
    messages: [...state.messages, message],
  };
}

export function replaceMessage(state: ChatAppState, message: ChatMessage) {
  return {
    ...state,
    messages: state.messages.map((item) => (item.id === message.id ? message : item)),
  };
}

export function upsertMemory(state: ChatAppState, memory: MemoryItem) {
  const idx = state.memories.findIndex((item) => item.id === memory.id);
  if (idx >= 0) {
    const next = [...state.memories];
    next[idx] = memory;
    return { ...state, memories: next };
  }
  return { ...state, memories: [...state.memories, memory] };
}

export function removeMemory(state: ChatAppState, memoryId: string) {
  return {
    ...state,
    memories: state.memories.filter((item) => item.id !== memoryId),
  };
}

export function removeChat(state: ChatAppState, chatId: string) {
  const remainingChats = state.chats.filter((chat) => chat.id !== chatId);
  const remainingMessages = state.messages.filter((message) => message.chatId !== chatId);
  const remainingMemories = state.memories.filter((memory) => memory.chatId !== chatId);
  const nextActive = remainingChats.find((chat) => chat.workspaceId === state.activeWorkspaceId) ?? remainingChats[0] ?? null;

  return {
    ...state,
    chats: remainingChats,
    messages: remainingMessages,
    memories: remainingMemories,
    activeChatId: nextActive?.id ?? '',
    activeWorkspaceId: nextActive?.workspaceId ?? state.activeWorkspaceId,
  };
}

export function createAttachmentRecord(params: {
  chatId: string;
  messageId: string;
  name: string;
  mimeType: string;
  url: string;
  size: number;
}): ChatAttachment {
  return createAttachment(params);
}

export function mergeChatAppStates(remote: ChatAppState, local: ChatAppState): ChatAppState {
  const mergeUniqueById = <T extends { id: string }>(base: T[], incoming: T[]) => {
    const map = new Map<string, T>();
    for (const item of base) map.set(item.id, item);
    for (const item of incoming) map.set(item.id, item);
    return [...map.values()];
  };

  const mergeUpdatedById = <T extends { id: string; updatedAt?: string }>(base: T[], incoming: T[]) => {
    const map = new Map<string, T>();
    for (const item of base) map.set(item.id, item);
    for (const item of incoming) {
      const current = map.get(item.id);
      if (!current) {
        map.set(item.id, item);
        continue;
      }
      const currentStamp = current.updatedAt ?? '';
      const incomingStamp = item.updatedAt ?? '';
      if (incomingStamp >= currentStamp) {
        map.set(item.id, item);
      }
    }
    return [...map.values()];
  };

  const workspaces = mergeUniqueById(remote.workspaces, local.workspaces);
  const chats = sortChats(mergeUpdatedById(remote.chats, local.chats));
  const messages = mergeUniqueById(remote.messages, local.messages);
  const memories = mergeUpdatedById(remote.memories, local.memories);
  const hasLocalWorkspace = workspaces.some((workspace) => workspace.id === local.activeWorkspaceId);
  const hasLocalChat = chats.some((chat) => chat.id === local.activeChatId);

  return {
    version: APP_VERSION,
    workspaces,
    chats,
    messages,
    memories,
    activeWorkspaceId: hasLocalWorkspace ? local.activeWorkspaceId : remote.activeWorkspaceId,
    activeChatId: hasLocalChat ? local.activeChatId : remote.activeChatId,
  };
}

export function createAssistantModesText(modes: OutputMode[]) {
  return modes.includes('image') || modes.includes('audio') || modes.includes('code')
    ? `Modos ativos: ${modes.filter((m) => m !== 'text').join(', ')}`
    : 'Modo ativo: texto';
}
