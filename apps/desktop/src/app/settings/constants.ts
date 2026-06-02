import {
  Brain,
  type IconComponent,
  Lock,
  MessageCircle,
  Mic,
  Monitor,
  Moon,
  Palette,
  Sparkles,
  Sun,
  Wrench
} from '@/lib/icons'
import { t } from '@/locales'
import type { ThemeMode } from '@/themes/context'

import type { DesktopConfigSection } from './types'

interface ProviderPrefix {
  prefix: string
  name: string
  priority: number
}

export const EMPTY_SELECT_VALUE = '__hermes_empty__'
export const CONTROL_TEXT = 'text-[0.8125rem]'

export const PROVIDER_GROUPS: ProviderPrefix[] = [
  { prefix: 'NOUS_', name: 'Nous Portal', priority: 0 },
  { prefix: 'ANTHROPIC_', name: 'Anthropic', priority: 1 },
  { prefix: 'DASHSCOPE_', name: 'DashScope (Qwen)', priority: 2 },
  { prefix: 'HERMES_QWEN_', name: 'DashScope (Qwen)', priority: 2 },
  { prefix: 'DEEPSEEK_', name: 'DeepSeek', priority: 3 },
  { prefix: 'GOOGLE_', name: 'Gemini', priority: 4 },
  { prefix: 'GEMINI_', name: 'Gemini', priority: 4 },
  { prefix: 'GLM_', name: 'GLM / Z.AI', priority: 5 },
  { prefix: 'ZAI_', name: 'GLM / Z.AI', priority: 5 },
  { prefix: 'Z_AI_', name: 'GLM / Z.AI', priority: 5 },
  { prefix: 'HF_', name: 'Hugging Face', priority: 6 },
  { prefix: 'KIMI_', name: 'Kimi / Moonshot', priority: 7 },
  { prefix: 'MINIMAX_', name: 'MiniMax', priority: 8 },
  { prefix: 'MINIMAX_CN_', name: 'MiniMax (China)', priority: 9 },
  { prefix: 'OPENCODE_GO_', name: 'OpenCode Go', priority: 10 },
  { prefix: 'OPENCODE_ZEN_', name: 'OpenCode Zen', priority: 11 },
  { prefix: 'OPENROUTER_', name: 'OpenRouter', priority: 12 },
  { prefix: 'XIAOMI_', name: 'Xiaomi MiMo', priority: 13 }
]

export const BUILTIN_PERSONALITIES = [
  'helpful',
  'concise',
  'technical',
  'creative',
  'teacher',
  'kawaii',
  'catgirl',
  'pirate',
  'shakespeare',
  'surfer',
  'noir',
  'uwu',
  'philosopher',
  'hype'
]

// Schema-side select overrides for desktop-relevant enum fields whose
// backend schema only declares a string type.
export const ENUM_OPTIONS: Record<string, string[]> = {
  'agent.image_input_mode': ['auto', 'native', 'text'],
  'approvals.mode': ['manual', 'smart', 'off'],
  'code_execution.mode': ['project', 'strict'],
  'context.engine': ['compressor', 'default', 'custom'],
  'delegation.reasoning_effort': ['', 'minimal', 'low', 'medium', 'high', 'xhigh'],
  'memory.provider': ['', 'builtin', 'honcho'],
  'stt.elevenlabs.model_id': ['scribe_v2', 'scribe_v1'],
  'stt.local.model': ['tiny', 'base', 'small', 'medium', 'large-v3'],
  'tts.openai.voice': ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
}

export function getFieldLabels(): Record<string, string> {
  const f = t().fields
  return {
    model: f.model,
    model_context_length: f.modelContextLength,
    fallback_providers: f.fallbackProviders,
    toolsets: f.toolsets,
    timezone: f.timezone,
    'display.personality': f.personality,
    'display.show_reasoning': f.showReasoning,
    'agent.max_turns': f.maxTurns,
    'agent.image_input_mode': f.imageInputMode,
    'terminal.cwd': f.terminalCwd,
    'terminal.backend': f.terminalBackend,
    'terminal.timeout': f.terminalTimeout,
    'terminal.persistent_shell': f.persistentShell,
    'terminal.env_passthrough': f.envPassthrough,
    file_read_max_chars: f.fileReadMaxChars,
    'tool_output.max_bytes': f.toolOutputMaxBytes,
    'tool_output.max_lines': f.toolOutputMaxLines,
    'tool_output.max_line_length': f.toolOutputMaxLineLength,
    'code_execution.mode': f.codeExecutionMode,
    'approvals.mode': f.approvalsMode,
    'approvals.timeout': f.approvalsTimeout,
    'approvals.mcp_reload_confirm': f.approvalsMcpReloadConfirm,
    command_allowlist: f.commandAllowlist,
    'security.redact_secrets': f.redactSecrets,
    'security.allow_private_urls': f.allowPrivateUrls,
    'browser.allow_private_urls': f.browserAllowPrivateUrls,
    'browser.auto_local_for_private_urls': f.browserAutoLocalForPrivateUrls,
    'checkpoints.enabled': f.checkpointsEnabled,
    'checkpoints.max_snapshots': f.checkpointsMaxSnapshots,
    'voice.record_key': f.voiceRecordKey,
    'voice.max_recording_seconds': f.voiceMaxRecordingSeconds,
    'voice.auto_tts': f.voiceAutoTts,
    'stt.enabled': f.sttEnabled,
    'stt.provider': f.sttProvider,
    'stt.local.model': f.sttLocalModel,
    'stt.local.language': f.sttLocalLanguage,
    'stt.elevenlabs.model_id': f.sttElevenlabsModelId,
    'stt.elevenlabs.language_code': f.sttElevenlabsLanguageCode,
    'stt.elevenlabs.tag_audio_events': f.sttElevenlabsTagAudioEvents,
    'stt.elevenlabs.diarize': f.sttElevenlabsDiarize,
    'tts.provider': f.ttsProvider,
    'tts.edge.voice': f.ttsEdgeVoice,
    'tts.openai.model': f.ttsOpenaiModel,
    'tts.openai.voice': f.ttsOpenaiVoice,
    'tts.elevenlabs.voice_id': f.ttsElevenlabsVoiceId,
    'tts.elevenlabs.model_id': f.ttsElevenlabsModelId,
    'memory.memory_enabled': f.memoryEnabled,
    'memory.user_profile_enabled': f.memoryUserProfileEnabled,
    'memory.memory_char_limit': f.memoryCharLimit,
    'memory.user_char_limit': f.memoryUserCharLimit,
    'memory.provider': f.memoryProvider,
    'context.engine': f.contextEngine,
    'compression.enabled': f.compressionEnabled,
    'compression.threshold': f.compressionThreshold,
    'compression.target_ratio': f.compressionTargetRatio,
    'compression.protect_last_n': f.compressionProtectLastN,
    'agent.api_max_retries': f.apiMaxRetries,
    'agent.service_tier': f.serviceTier,
    'agent.tool_use_enforcement': f.toolUseEnforcement,
    'delegation.model': f.delegationModel,
    'delegation.provider': f.delegationProvider,
    'delegation.max_iterations': f.delegationMaxIterations,
    'delegation.max_concurrent_children': f.delegationMaxConcurrentChildren,
    'delegation.child_timeout_seconds': f.delegationChildTimeoutSeconds,
    'delegation.reasoning_effort': f.delegationReasoningEffort
  }
}

export function getFieldDescriptions(): Record<string, string> {
  const d = t().fieldDesc
  return {
    model: d.model,
    model_context_length: d.modelContextLength,
    fallback_providers: d.fallbackProviders,
    'display.personality': d.personality,
    timezone: d.timezone,
    'display.show_reasoning': d.showReasoning,
    'agent.image_input_mode': d.imageInputMode,
    'terminal.cwd': d.terminalCwd,
    'code_execution.mode': d.codeExecutionMode,
    'terminal.persistent_shell': d.persistentShell,
    'terminal.env_passthrough': d.envPassthrough,
    file_read_max_chars: d.fileReadMaxChars,
    'approvals.mode': d.approvalsMode,
    'approvals.timeout': d.approvalsTimeout,
    'security.redact_secrets': d.redactSecrets,
    'checkpoints.enabled': d.checkpointsEnabled,
    'memory.memory_enabled': d.memoryEnabled,
    'memory.user_profile_enabled': d.memoryUserProfileEnabled,
    'context.engine': d.contextEngine,
    'compression.enabled': d.compressionEnabled,
    'voice.auto_tts': d.voiceAutoTts,
    'stt.enabled': d.sttEnabled,
    'stt.elevenlabs.language_code': d.sttElevenlabsLanguageCode,
    'agent.max_turns': d.maxTurns
  }
}

// Curated desktop config surface: only fields a user might tune from the app.
export function getSections(): DesktopConfigSection[] {
  const s = t().settings
  return [
    {
      id: 'model',
      label: s.sectionModel,
      icon: Sparkles,
      keys: ['model_context_length', 'fallback_providers']
    },
    {
      id: 'chat',
      label: s.sectionChat,
      icon: MessageCircle,
      keys: ['display.personality', 'timezone', 'display.show_reasoning', 'agent.image_input_mode']
    },
    {
      id: 'appearance',
      label: s.sectionAppearance,
      icon: Palette,
      keys: []
    },
    {
      id: 'workspace',
      label: s.sectionWorkspace,
      icon: Monitor,
      keys: [
        'terminal.cwd',
        'code_execution.mode',
        'terminal.persistent_shell',
        'terminal.env_passthrough',
        'file_read_max_chars'
      ]
    },
    {
      id: 'safety',
      label: s.sectionSafety,
      icon: Lock,
      keys: [
        'approvals.mode',
        'approvals.timeout',
        'approvals.mcp_reload_confirm',
        'command_allowlist',
        'security.redact_secrets',
        'security.allow_private_urls',
        'browser.allow_private_urls',
        'browser.auto_local_for_private_urls',
        'checkpoints.enabled'
      ]
    },
    {
      id: 'memory',
      label: s.sectionMemory,
      icon: Brain,
      keys: [
        'memory.memory_enabled',
        'memory.user_profile_enabled',
        'memory.memory_char_limit',
        'memory.user_char_limit',
        'memory.provider',
        'context.engine',
        'compression.enabled',
        'compression.threshold',
        'compression.target_ratio',
        'compression.protect_last_n'
      ]
    },
    {
      id: 'voice',
      label: s.sectionVoice,
      icon: Mic,
      keys: [
        'tts.provider',
        'stt.enabled',
        'stt.provider',
        'voice.auto_tts',
        'tts.edge.voice',
        'tts.openai.model',
        'tts.openai.voice',
        'tts.elevenlabs.voice_id',
        'tts.elevenlabs.model_id',
        'stt.local.model',
        'stt.local.language',
        'stt.elevenlabs.model_id',
        'stt.elevenlabs.language_code',
        'stt.elevenlabs.tag_audio_events',
        'stt.elevenlabs.diarize',
        'voice.record_key',
        'voice.max_recording_seconds'
      ]
    },
    {
      id: 'advanced',
      label: s.sectionAdvanced,
      icon: Wrench,
      keys: [
        'toolsets',
        'terminal.backend',
        'terminal.timeout',
        'tool_output.max_bytes',
        'tool_output.max_lines',
        'tool_output.max_line_length',
        'checkpoints.max_snapshots',
        'agent.max_turns',
        'agent.api_max_retries',
        'agent.service_tier',
        'agent.tool_use_enforcement',
        'delegation.model',
        'delegation.provider',
        'delegation.max_iterations',
        'delegation.max_concurrent_children',
        'delegation.child_timeout_seconds',
        'delegation.reasoning_effort'
      ]
    }
  ]
}

export interface ModeOption {
  id: ThemeMode
  label: string
  description: string
  icon: IconComponent
}

export function getModeOptions(): ModeOption[] {
  const a = t().appearance
  return [
    { id: 'light', label: a.light, description: a.lightDesc, icon: Sun },
    { id: 'dark', label: a.dark, description: a.darkDesc, icon: Moon },
    { id: 'system', label: a.system, description: a.systemDesc, icon: Monitor }
  ]
}

export function getSearchPlaceholder(): Record<'about' | 'config' | 'gateway' | 'keys' | 'mcp' | 'sessions', string> {
  const s = t().settings
  return {
    about: s.searchAbout,
    config: s.searchSettings,
    gateway: s.searchGateway,
    keys: s.searchKeys,
    mcp: s.searchMcp,
    sessions: s.searchSessions
  }
}
