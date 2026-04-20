import type { ChatAttachment, ChatMessage, ChatThread, MemoryItem, MessageSegment, OutputMode } from './types';
import { normalizeText } from './persistence';

export interface AssistantDraft {
  content: string;
  segments: MessageSegment[];
}

export function stripMarkdown(input: string) {
  return input
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/```[\s\S]*?```/g, 'bloco de código')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/\[(.*?)\]\((.*?)\)/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function hashString(value: string) {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  }
  return hash;
}

function escapeXml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function buildSvgPoster(title: string, subtitle: string, seed: string) {
  const hash = hashString(seed);
  const hue = hash % 360;
  const hue2 = (hue + 46) % 360;
  const hue3 = (hue + 180) % 360;
  const glint = `hsl(${hue3} 70% 62%)`;
  const accent = `hsl(${hue2} 78% 68%)`;
  const base = `hsl(${hue} 42% 13%)`;
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800" role="img" aria-label="${escapeXml(title)}">
      <defs>
        <radialGradient id="bg" cx="20%" cy="18%" r="90%">
          <stop offset="0%" stop-color="${accent}" stop-opacity="0.35"/>
          <stop offset="55%" stop-color="${base}" stop-opacity="0.96"/>
          <stop offset="100%" stop-color="#09090b"/>
        </radialGradient>
        <linearGradient id="line" x1="0" x2="1">
          <stop offset="0%" stop-color="${glint}" stop-opacity="0.9"/>
          <stop offset="100%" stop-color="#f3eadf" stop-opacity="0.35"/>
        </linearGradient>
        <filter id="blur">
          <feGaussianBlur stdDeviation="28"/>
        </filter>
      </defs>
      <rect width="1200" height="800" fill="url(#bg)"/>
      <circle cx="1040" cy="120" r="160" fill="${accent}" opacity="0.18" filter="url(#blur)"/>
      <circle cx="140" cy="640" r="220" fill="${glint}" opacity="0.10" filter="url(#blur)"/>
      <path d="M0 610 C180 530, 340 500, 540 520 S980 590, 1200 500" fill="none" stroke="url(#line)" stroke-width="2" opacity="0.65"/>
      <path d="M0 690 C220 620, 420 620, 620 660 S980 760, 1200 700" fill="none" stroke="${accent}" stroke-width="1.5" opacity="0.45"/>
      <rect x="72" y="72" width="1056" height="656" rx="36" fill="none" stroke="#f3eadf" stroke-opacity="0.18"/>
      <text x="96" y="170" fill="#f3eadf" font-size="56" font-family="Mondwest, serif" letter-spacing="2">${escapeXml(title)}</text>
      <text x="96" y="235" fill="#f3eadf" fill-opacity="0.72" font-size="22" font-family="Courier Prime, monospace">${escapeXml(subtitle)}</text>
      <g fill="none" stroke="#f3eadf" stroke-opacity="0.18">
        <path d="M96 318H1104"/>
        <path d="M96 350H1104"/>
        <path d="M96 382H1104"/>
      </g>
      <text x="96" y="610" fill="#f3eadf" fill-opacity="0.7" font-size="18" font-family="Courier Prime, monospace">Hermes chat studio • imagem conceitual gerada localmente</text>
    </svg>
  `;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

function buildCodeSnippet(_topic: string, input: string) {
  const normalized = normalizeText(input);
  if (/netlify|github|deploy|supabase/.test(normalized)) {
    return {
      language: 'toml',
      title: 'netlify.toml',
      content: `[build]\n  base = \"web\"\n  command = \"npm run build\"\n  publish = \"dist\"\n\n[[redirects]]\n  from = \"/*\"\n  to = \"/index.html\"\n  status = 200`,
    };
  }

  if (/memoria|memory|lembrar/.test(normalized)) {
    return {
      language: 'ts',
      title: 'memory-store.ts',
      content: `export function upsertMemory(state, memory) {\n  const next = state.memories.filter((item) => item.id !== memory.id);\n  return { ...state, memories: [...next, memory] };\n}`,
    };
  }

  if (/ui|interface|chat|composer|sidebar/.test(normalized)) {
    return {
      language: 'tsx',
      title: 'ChatComposer.tsx',
      content: `function ChatComposer({ value, onChange }) {\n  return (\n    <textarea\n      value={value}\n      onChange={(event) => onChange(event.target.value)}\n      placeholder=\"Escreva sua mensagem...\"\n    />\n  );\n}`,
    };
  }

  return {
    language: 'ts',
    title: 'reply.ts',
    content: `export function buildReply(input: string) {\n  return input.trim() || 'Sem conteúdo';\n}`,
  };
}

function pickTopic(input: string) {
  const normalized = normalizeText(input);
  if (/arquitet|stack|netlify|github|supabase|deploy|mvp|wireframe/.test(normalized)) return 'architecture';
  if (/interface|chat|composer|sidebar|layout|ux|ui|desktop|mobile/.test(normalized)) return 'ui';
  if (/memoria|lembrar|preferenc|global|chat/.test(normalized)) return 'memory';
  if (/codigo|code|tsx|react|typescript|json|script/.test(normalized)) return 'code';
  if (/imagem|image|visual|foto|anexo/.test(normalized) || normalized.includes('📷')) return 'image';
  return 'general';
}

function cleanExcerpt(text: string) {
  return text.replace(/\s+/g, ' ').trim();
}

export function buildAssistantDraft(params: {
  userText: string;
  chat: ChatThread;
  memories: MemoryItem[];
  attachments: ChatAttachment[];
  selectedModes: OutputMode[];
  _messages: ChatMessage[];
}): AssistantDraft {
  const topic = pickTopic(params.userText);
  const hasImageAttachment = params.attachments.some((attachment) => attachment.mimeType.startsWith('image/'));
  const selectedModes = new Set(params.selectedModes);
  const contextSummary = params.memories
    .filter((memory) => memory.pinned || memory.scope === 'global' || memory.chatId === params.chat.id)
    .slice(0, 4)
    .map((memory) => `- ${memory.content}`)
    .join('\n');

  const leadIn = hasImageAttachment
    ? 'Recebi uma imagem como contexto e já a deixei anexada ao fluxo do chat.'
    : 'Entendi o pedido e vou responder de forma direta.';

  let content = '';
  if (topic === 'architecture') {
    content = [
      '### Direção sugerida',
      '',
      'Eu seguiria por uma arquitetura simples, local-first e fácil de migrar para Netlify + Supabase.',
      '',
      '1. **Frontend único** em React/TypeScript com layout responsivo.',
      '2. **Persistência local no MVP** para chats, mensagens e memórias.',
      '3. **Camada de integração** preparada para trocar o backend depois sem reescrever a UI.',
      '4. **Separação clara de chats** para manter assunto, contexto e histórico.',
      '',
      'Se quiser, eu posso transformar isso em backlog executável e estrutura de pastas.'
    ].join('\n');
  } else if (topic === 'ui') {
    content = [
      '### Direção de interface',
      '',
      'Eu faria a tela como um workspace editorial: sidebar de chats, conversa central e painel de memória à direita.',
      '',
      '- conversa com streaming',
      '- composer rico com anexos',
      '- memória visível e editável',
      '- comportamento bom em desktop e mobile',
      '',
      'O detalhe mais importante é a clareza: cada chat precisa parecer um assunto isolado.'
    ].join('\n');
  } else if (topic === 'memory') {
    content = [
      '### Memória persistente',
      '',
      'A melhor forma de não bagunçar o contexto é separar em duas camadas:',
      '',
      '- **memória global**: preferências e fatos duráveis',
      '- **memória do chat**: decisões e contexto daquele assunto',
      '',
      'Assim você consegue revisar, corrigir e apagar sem perder o controle.'
    ].join('\n');
  } else if (topic === 'code') {
    content = [
      '### Caminho de implementação',
      '',
      'Vou te devolver um bloco de código útil para o contexto do pedido.',
      '',
      'Se você quiser, eu também posso adaptar o snippet para Netlify, Supabase ou o layout do chat.'
    ].join('\n');
  } else if (topic === 'image') {
    content = [
      '### Leitura do pedido visual',
      '',
      'Sem inventar nada: a imagem foi recebida como contexto e pode ser usada na resposta para comparação, referência ou organização.'
    ].join('\n');
  } else {
    content = [
      '### Resposta',
      '',
      leadIn,
      '',
      'Eu também vou manter o chat separado por assunto para não misturar contextos.'
    ].join('\n');
  }

  if (contextSummary) {
    content += `\n\n### Memória usada\n${contextSummary}`;
  }

  const segments: MessageSegment[] = [];

  if (selectedModes.has('code')) {
    const snippet = buildCodeSnippet(topic, params.userText);
    segments.push({
      id: `seg_${topic}_code`,
      kind: 'code',
      title: snippet.title,
      language: snippet.language,
      content: snippet.content,
    });
  }

  if (selectedModes.has('image')) {
    segments.push({
      id: `seg_${topic}_image`,
      kind: 'image',
      title: 'Cartão visual',
      imageUrl: buildSvgPoster(
        params.chat.title || 'Hermes',
        cleanExcerpt(params.userText).slice(0, 96) || 'Interface de chat multimodal',
        `${params.chat.id}:${params.userText}`,
      ),
      subtitle: 'Imagem conceitual gerada localmente para demonstrar a resposta multimodal.',
    });
  }

  if (selectedModes.has('audio')) {
    segments.push({
      id: `seg_${topic}_audio`,
      kind: 'audio',
      title: 'Versão em áudio',
      audioText: stripMarkdown(content),
      subtitle: 'Use o botão tocar para ouvir a resposta em voz do navegador.',
    });
  }

  return {
    content,
    segments,
  };
}
