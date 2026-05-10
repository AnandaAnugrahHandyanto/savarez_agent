import { createContext, type ReactNode, useContext, useMemo } from 'react'

export const LOCALES = ['en', 'zh'] as const
export type Locale = (typeof LOCALES)[number]

type TranslationValue = string | string[] | Record<string, string>
export type TranslationKey = keyof typeof EN

export { TRAIL_PATTERNS } from './i18n-consts.js'

export interface I18nApi {
  locale: Locale
  t: (key: TranslationKey, vars?: Record<string, string | number>) => string
  tStatus: (status: string) => string
  toolVerb: (name: string) => string
  verbs: string[]
}

const TOOL_VERBS_EN: Record<string, string> = {
  browser: 'browsing',
  clarify: 'asking',
  create_file: 'creating',
  delegate_task: 'delegating',
  delete_file: 'deleting',
  execute_code: 'executing',
  image_generate: 'generating',
  list_files: 'listing',
  memory: 'remembering',
  patch: 'patching',
  read_file: 'reading',
  run_command: 'running',
  search_code: 'searching',
  search_files: 'searching',
  terminal: 'terminal',
  web_extract: 'extracting',
  web_search: 'searching',
  write_file: 'writing'
}

const TOOL_VERBS_ZH: Record<string, string> = {
  browser: '浏览',
  clarify: '询问',
  create_file: '创建',
  delegate_task: '委托',
  delete_file: '删除',
  execute_code: '执行',
  image_generate: '生成',
  list_files: '列出',
  memory: '记忆',
  patch: '修改',
  read_file: '读取',
  run_command: '运行',
  search_code: '搜索',
  search_files: '搜索',
  terminal: '终端',
  web_extract: '提取',
  web_search: '搜索',
  write_file: '写入'
}

const VERBS_EN = [
  'pondering', 'contemplating', 'musing', 'cogitating', 'ruminating',
  'deliberating', 'mulling', 'reflecting', 'processing', 'reasoning',
  'analyzing', 'computing', 'synthesizing', 'formulating', 'brainstorming'
]

const VERBS_ZH = ['思考', '沉思', '琢磨', '推敲', '斟酌', '整理', '处理', '推理', '分析', '计算', '综合', '组织', '构思']

const STATUS_EN: Record<string, string> = {
  'approval needed': 'approval needed',
  'forging session…': 'forging session…',
  'gateway exited': 'gateway exited',
  'gateway startup timeout': 'gateway startup timeout',
  interrupted: 'interrupted',
  'protocol warning': 'protocol warning',
  ready: 'ready',
  resuming: 'resuming…',
  'resuming most recent…': 'resuming most recent…',
  'resuming…': 'resuming…',
  running: 'running…',
  'running…': 'running…',
  'secret input needed': 'secret input needed',
  'setup required': 'setup required',
  'starting agent…': 'starting agent…',
  'sudo password needed': 'sudo password needed',
  'summoning hermes…': 'summoning hermes…',
  'waiting for input…': 'waiting for input…'
}

const STATUS_ZH: Record<string, string> = {
  'approval needed': '需要确认',
  'forging session…': '正在创建会话…',
  'gateway exited': '网关已退出',
  'gateway startup timeout': '网关启动超时',
  interrupted: '已中断',
  'protocol warning': '协议警告',
  ready: '就绪',
  resuming: '正在恢复…',
  'resuming most recent…': '正在恢复最近会话…',
  'resuming…': '正在恢复…',
  running: '运行中…',
  'running…': '运行中…',
  'secret input needed': '需要输入密钥',
  'setup required': '需要配置',
  'starting agent…': '正在启动 Agent…',
  'sudo password needed': '需要 sudo 密码',
  'summoning hermes…': '正在唤醒 Hermes…',
  'waiting for input…': '等待输入…'
}

export const EN = {
  'background.short': 'bg',
  'common.chars': 'chars',
  'common.lines': 'lines',
  'common.warning': 'warning',
  'errors.gatewayExited': 'error: gateway exited',
  'errors.invalidResponse': 'error: invalid response: {method}',
  'errors.rpc': 'error: {message}',
  'gateway.commandCatalogUnavailable': 'command catalog unavailable: {message}',
  'gateway.exitedInspectLogs': 'gateway exited · /logs to inspect',
  'gateway.protocolNoise': 'protocol noise: {preview}',
  'gateway.protocolNoiseDetected': 'protocol noise detected · /logs to inspect',
  'gateway.startupTimedOut': 'gateway startup timed out{trace} · /logs to inspect',
  'image.attached': '📎 Image #{count} attached from clipboard{meta}',
  'input.promptCancelled': 'prompt cancelled',
  'paste.noImage': 'No image found in clipboard',
  'section.thinking': 'Thinking',
  'section.toolCalls': 'Tool calls',
  'section.progress': 'Progress',
  'section.activity': 'Activity',
  'section.subagents': 'Subagents',
  'setup.action.configureModel': 'configure provider + model in-place',
  'setup.action.exitSetup': 'exit and run `hermes setup` manually',
  'setup.action.runWizard': 'run full first-time setup wizard in-place',
  'setup.body': 'Hermes needs a model provider before the TUI can start a session.',
  'setup.title': 'Setup Required',
  'setup.actions': 'Actions',
  'session.titleQueuedSuffix': ' (queued while session initializes)',
  'session.titleSet': 'session title set: {title}{suffix}',
  'session.titleSetFailed': 'warning: failed to set session title: {message}',
  'session.switchBusy': 'interrupt the current turn before trying to {what}',
  'transcript.bgComplete': '[bg {taskId}] {text}',
  'transcript.credentialWarning': 'warning: {message}',
  'transcript.configWarning': 'warning: {message}',
  'tool.drafting': 'drafting {name}…',
  'tool.outputAnalysis': 'analyzing tool output…',
  'usage.tokensShort': 'tok',
  'usage.compressionsShort': 'cmp',
  'voice.idle': 'voice {state}',
  'voice.noSpeechStopped': 'voice: no speech detected 3 times, continuous mode stopped',
  'voice.off': 'off',
  'voice.on': 'on',
  'input.interruptHint': 'Ctrl+C to interrupt…',
  'input.interruptHintMac': 'Ctrl+C cancel',
  'input.typeOther': 'Other (type your answer)',
  'help.quickHelp': '? quick help',
  'help.dismissHint': '  ·  type /help for the full panel  ·  backspace to dismiss',
  'help.commonCommands': 'Common commands',
  'help.hotkeys': 'Hotkeys',
  'help.fullList': 'full list of commands + hotkeys',
  'help.newSession': 'start a new session',
  'help.resumeSession': 'resume a prior session',
  'help.detailsDesc': 'control transcript detail level',
  'help.copyDesc': 'copy selection or last assistant message',
  'help.exitDesc': 'exit hermes',
  'picker.cancel': 'Esc/q cancel',
  'picker.confirmHint': 'y/Enter confirm · n/Esc cancel',
  'picker.selectHint': '↑/↓ select · Enter choose · d disconnect · Esc/q cancel',
  'picker.sessionHint': '↑/↓ select · Enter resume · 1-9 quick · d delete · Esc/q cancel',
  'picker.skillHint': '↑/↓ select · Enter open · 1-9,0 quick · Esc/q cancel',
  'queue.editHint': ' · editing {idx} · Ctrl+X delete · Esc cancel',
  'section.budget': 'Budget',
  'section.files': 'Files',
  'section.output': 'Output',
  'section.summary': 'Summary',
  'section.spawned': 'Spawned',
  'section.spawnTree': 'Spawn tree',
  'branding.availableTools': 'Available Tools',
  'branding.availableSkills': 'Available Skills',
  'branding.systemPrompt': 'System Prompt',
  'prompt.selectHint': '↑/↓ select · Enter confirm · {n} quick pick · Ctrl+C deny',
  'prompt.selectHintEsc': '↑/↓ select · Enter confirm · {n} quick pick · Esc/Ctrl+C cancel',
  'prompt.typeHint': 'Enter send · Esc {action}',
  'prompt.typeHintBack': 'back',
  'prompt.typeHintCancel': 'cancel',
  'prompt.confirmHint': '↑/↓ select · Enter confirm · Y/N quick · Esc cancel',
  'voice.statusTitle': 'Voice Mode Status',
  'voice.modeLabel': 'Mode',
  'voice.ttsLabel': 'TTS',
  'voice.recordKeyLabel': 'Record key',
  'voice.requirements': 'Requirements',
  'voice.ttsEnabled': 'Voice TTS enabled.',
  'voice.ttsDisabled': 'Voice TTS disabled.',
  'voice.modeEnabled': 'Voice mode enabled{tts}',
  'voice.modeDisabled': 'Voice mode disabled.',
  'voice.recordHint': '{key} to start/stop recording',
  'voice.ttsToggleHint': '/voice tts  to toggle speech output',
  'voice.disableHint': '/voice off  to disable voice mode'
} as const satisfies Record<string, TranslationValue>

const ZH: Record<TranslationKey, TranslationValue> = {
  'background.short': '后台',
  'common.chars': '字符',
  'common.lines': '行',
  'common.warning': '警告',
  'errors.gatewayExited': '错误：网关已退出',
  'errors.invalidResponse': '错误：无效响应：{method}',
  'errors.rpc': '错误：{message}',
  'gateway.commandCatalogUnavailable': '命令目录不可用：{message}',
  'gateway.exitedInspectLogs': '网关已退出 · 用 /logs 查看日志',
  'gateway.protocolNoise': '协议噪声：{preview}',
  'gateway.protocolNoiseDetected': '检测到协议噪声 · 用 /logs 查看日志',
  'gateway.startupTimedOut': '网关启动超时{trace} · 用 /logs 查看日志',
  'image.attached': '📎 图片 #{count} 已从剪贴板附加{meta}',
  'input.promptCancelled': '输入已取消',
  'paste.noImage': '剪贴板中没有图片',
  'section.thinking': '思考',
  'section.toolCalls': '工具调用',
  'section.progress': '进度',
  'section.activity': '活动',
  'section.subagents': '子代理',
  'setup.action.configureModel': '就地配置提供商和模型',
  'setup.action.exitSetup': '退出并手动运行 `hermes setup`',
  'setup.action.runWizard': '就地运行完整首次配置向导',
  'setup.body': 'Hermes 需要先配置模型提供商，TUI 才能启动会话。',
  'setup.title': '需要配置',
  'setup.actions': '操作',
  'session.titleQueuedSuffix': '（会话初始化后排队设置）',
  'session.titleSet': '会话标题已设置：{title}{suffix}',
  'session.titleSetFailed': '警告：设置会话标题失败：{message}',
  'session.switchBusy': '请先中断当前轮次，再尝试{what}',
  'transcript.bgComplete': '[后台 {taskId}] {text}',
  'transcript.credentialWarning': '警告：{message}',
  'transcript.configWarning': '警告：{message}',
  'tool.drafting': '正在生成 {name}…',
  'tool.outputAnalysis': '正在分析工具输出…',
  'usage.tokensShort': 'tok',
  'usage.compressionsShort': '压缩',
  'voice.idle': '语音{state}',
  'voice.noSpeechStopped': '语音：连续 3 次未检测到说话，已停止连续模式',
  'voice.off': '关',
  'voice.on': '开',
  'input.interruptHint': 'Ctrl+C 中断…',
  'input.interruptHintMac': 'Ctrl+C 取消',
  'input.typeOther': '其他（输入你的回答）',
  'help.quickHelp': '? 快速帮助',
  'help.dismissHint': '  ·  输入 /help 查看完整面板  ·  按退格键关闭',
  'help.commonCommands': '常用命令',
  'help.hotkeys': '快捷键',
  'help.fullList': '命令和快捷键完整列表',
  'help.newSession': '开始新会话',
  'help.resumeSession': '恢复之前的会话',
  'help.detailsDesc': '控制对话详情级别',
  'help.copyDesc': '复制选中内容或上一条助手消息',
  'help.exitDesc': '退出 Hermes',
  'picker.cancel': 'Esc/q 取消',
  'picker.confirmHint': 'y/Enter 确认 · n/Esc 取消',
  'picker.selectHint': '↑/↓ 选择 · Enter 选定 · d 断开 · Esc/q 取消',
  'picker.sessionHint': '↑/↓ 选择 · Enter 恢复 · 1-9 快速 · d 删除 · Esc/q 取消',
  'picker.skillHint': '↑/↓ 选择 · Enter 打开 · 1-9,0 快速 · Esc/q 取消',
  'queue.editHint': ' · 正在编辑 {idx} · Ctrl+X 删除 · Esc 取消',
  'section.budget': '预算',
  'section.files': '文件',
  'section.output': '输出',
  'section.summary': '摘要',
  'section.spawned': '已孵出',
  'section.spawnTree': '孵化树',
  'branding.availableTools': '可用工具',
  'branding.availableSkills': '可用技能',
  'branding.systemPrompt': '系统提示词',
  'prompt.selectHint': '↑/↓ 选择 · Enter 确认 · {n} 快速选择 · Ctrl+C 拒绝',
  'prompt.selectHintEsc': '↑/↓ 选择 · Enter 确认 · {n} 快速选择 · Esc/Ctrl+C 取消',
  'prompt.typeHint': 'Enter 发送 · Esc {action}',
  'prompt.typeHintBack': '返回',
  'prompt.typeHintCancel': '取消',
  'prompt.confirmHint': '↑/↓ 选择 · Enter 确认 · Y/N 快速选择 · Esc 取消',
  'voice.statusTitle': '语音模式状态',
  'voice.modeLabel': '模式',
  'voice.ttsLabel': 'TTS',
  'voice.recordKeyLabel': '录制键',
  'voice.requirements': '运行要求',
  'voice.ttsEnabled': '语音 TTS 已启用。',
  'voice.ttsDisabled': '语音 TTS 已禁用。',
  'voice.modeEnabled': '语音模式已启用{tts}',
  'voice.modeDisabled': '语音模式已禁用。',
  'voice.recordHint': '{key} 开始/停止录音',
  'voice.ttsToggleHint': '/voice tts  切换语音输出',
  'voice.disableHint': '/voice off  禁用语音模式'
}

const CATALOGS: Record<Locale, Record<TranslationKey, TranslationValue>> = { en: EN, zh: ZH }
const STATUS_CATALOGS: Record<Locale, Record<string, string>> = { en: STATUS_EN, zh: STATUS_ZH }
const TOOL_VERB_CATALOGS: Record<Locale, Record<string, string>> = { en: TOOL_VERBS_EN, zh: TOOL_VERBS_ZH }
const VERB_CATALOGS: Record<Locale, string[]> = { en: VERBS_EN, zh: VERBS_ZH }

const interpolate = (template: string, vars: Record<string, string | number> = {}) =>
  template.replace(/\{(\w+)\}/g, (_m, key: string) => String(vars[key] ?? `{${key}}`))

export const normalizeLocale = (value: unknown): Locale => {
  if (typeof value !== 'string') return 'en'
  const raw = value.trim().toLowerCase()
  if (!raw) return 'en'
  if (raw === 'zh' || raw === 'zh-cn' || raw === 'zh-tw' || raw === 'zh-hans' || raw === 'zh-hant' || raw === 'chinese') return 'zh'
  return raw === 'en' || raw === 'en-us' || raw === 'en-gb' || raw === 'english' ? 'en' : 'en'
}

export const translate = (locale: Locale, key: TranslationKey, vars?: Record<string, string | number>) => {
  const value = CATALOGS[locale][key] ?? CATALOGS.en[key] ?? key
  return typeof value === 'string' ? interpolate(value, vars) : key
}

export const translateStatus = (locale: Locale, status: string) => STATUS_CATALOGS[locale][status] ?? status
export const getToolVerb = (locale: Locale, name: string) => TOOL_VERB_CATALOGS[locale][name] ?? TOOL_VERBS_EN[name] ?? 'running'
export const getThinkingVerbs = (locale: Locale) => VERB_CATALOGS[locale] ?? VERBS_EN

const defaultApi: I18nApi = {
  locale: 'en',
  t: (key, vars) => translate('en', key, vars),
  tStatus: status => translateStatus('en', status),
  toolVerb: name => getToolVerb('en', name),
  verbs: VERBS_EN
}

const I18nContext = createContext<I18nApi>(defaultApi)

export function I18nProvider({ children, locale }: { children: ReactNode; locale: Locale }) {
  const api = useMemo<I18nApi>(
    () => ({
      locale,
      t: (key, vars) => translate(locale, key, vars),
      tStatus: status => translateStatus(locale, status),
      toolVerb: name => getToolVerb(locale, name),
      verbs: getThinkingVerbs(locale)
    }),
    [locale]
  )
  return <I18nContext.Provider value={api}>{children}</I18nContext.Provider>
}

export const useI18n = () => useContext(I18nContext)
