export type Role = 'user' | 'assistant' | 'system';
export type OutputMode = 'text' | 'image' | 'audio' | 'code';
export type MemoryScope = 'global' | 'chat';
export type MemoryKind = 'preference' | 'decision' | 'project' | 'note';

export interface ChatWorkspace {
  id: string;
  name: string;
  description: string;
  accent: string;
}

export interface ChatThread {
  id: string;
  workspaceId: string;
  title: string;
  summary: string;
  createdAt: string;
  updatedAt: string;
  archivedAt: string | null;
  pinned: boolean;
}

export interface ChatAttachment {
  id: string;
  chatId: string;
  messageId: string;
  name: string;
  type: string;
  mimeType: string;
  url: string;
  size: number;
}

export interface MessageSegment {
  id: string;
  kind: 'code' | 'image' | 'audio';
  title: string;
  content?: string;
  language?: string;
  imageUrl?: string;
  audioText?: string;
  subtitle?: string;
}

export interface ChatMessage {
  id: string;
  chatId: string;
  role: Role;
  content: string;
  createdAt: string;
  segments: MessageSegment[];
  attachments: ChatAttachment[];
  pending?: boolean;
}

export interface MemoryItem {
  id: string;
  scope: MemoryScope;
  chatId: string | null;
  kind: MemoryKind;
  content: string;
  sourceMessageId: string | null;
  confidence: number;
  pinned: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface ChatAppState {
  version: number;
  workspaces: ChatWorkspace[];
  chats: ChatThread[];
  messages: ChatMessage[];
  memories: MemoryItem[];
  activeWorkspaceId: string;
  activeChatId: string;
}
