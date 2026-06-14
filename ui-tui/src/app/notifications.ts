import { spawn } from 'node:child_process'
import { appendFileSync, existsSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

import type { ConfigFullResponse, SessionTitleResponse } from '../gatewayTypes.js'
import { rpcErrorMessage } from '../lib/rpc.js'
import { stripAnsi } from '../lib/text.js'

import type { GatewayRpc } from './interfaces.js'

export const SESSION_TITLE_TIMEOUT_MS = 650
export const NOTIFICATION_CONFIG_TIMEOUT_MS = 650

export type NotificationCategory = 'blocked.error' | 'done.review' | 'wait.input'

interface NotificationStdout {
  isTTY?: boolean
  write: (chunk: string) => unknown
}

export interface MacNotificationControllerOptions {
  bellOnComplete?: boolean | null
  getSessionId: () => null | string
  rpc: GatewayRpc
  stdout?: NotificationStdout
}

const hermesHome = () => process.env.HERMES_HOME?.trim() || join(homedir(), '.hermes')

export const agentNotifyScriptPath = () =>
  process.env.HERMES_AGENT_NOTIFY_SCRIPT || join(hermesHome(), 'bin', 'agent-notify')

export const debugNotify = (message: string) => {
  if (process.env.HERMES_TUI_NOTIFY_DEBUG !== '1') {
    return
  }

  try {
    appendFileSync(join(hermesHome(), 'logs', 'tui-notify-debug.log'), `${new Date().toISOString()} ${message}\n`)
  } catch {
    // Debug logging must never affect the TUI event loop.
  }
}

export const cleanNotifyPart = (value: unknown, max = 48) =>
  String(value ?? '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, max)

const KEY_VALUE_SECRET_RE =
  /\b((?:api[_-]?key|apikey|token|access[_-]?token|refresh[_-]?token|secret|password|passwd|pwd|authorization|auth[_-]?code|oauth[_-]?code|connection[_-]?string)\b\s*[:=]\s*)(?:"[^"]+"|'[^']+'|[^\s&;,]+)/giu
const URL_SECRET_PARAM_RE = /([?&](?:api[_-]?key|apikey|token|secret|password|passwd|pwd|code|authorization)=)[^&#\s]+/giu
const TOKEN_PREFIX_RE = /\b(?:sk-[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9_]{10,}|github_pat_[A-Za-z0-9_]{10,}|xoxb-[A-Za-z0-9-]{10,})\b/gu
const BEARER_SECRET_RE = /\bBearer\s+[A-Za-z0-9._~+/=-]{10,}/giu
const CONNECTION_STRING_RE = /\b((?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis):\/\/[^:\s/@]+:)[^@\s]+@/giu
const OPAQUE_SECRET_RE =
  /\b(?=[A-Za-z0-9_./+=-]{40,}\b)(?=[A-Za-z0-9_./+=-]*[A-Za-z])(?=[A-Za-z0-9_./+=-]*[0-9])[A-Za-z0-9_./+=-]+\b/gu

export const redactSensitiveText = (value: string) =>
  value
    .replace(URL_SECRET_PARAM_RE, '$1[REDACTED]')
    .replace(CONNECTION_STRING_RE, '$1[REDACTED]@')
    .replace(BEARER_SECRET_RE, 'Bearer [REDACTED]')
    .replace(KEY_VALUE_SECRET_RE, '$1[REDACTED]')
    .replace(TOKEN_PREFIX_RE, '[REDACTED]')
    .replace(OPAQUE_SECRET_RE, '[REDACTED]')

export const sanitizeNotifyText = (value: unknown, max = 180, fallback = '') => {
  const text = redactSensitiveText(
    stripAnsi(String(value ?? ''))
      .replace(/\s+/g, ' ')
      .trim()
  )

  return (text || fallback).slice(0, max)
}

export const sanitizeCommandPreview = (command: unknown, max = 160) => sanitizeNotifyText(command, max, '명령 확인 필요')

export const formatChoicesPreview = (question: unknown, choices: unknown) => {
  const cleanQuestion = sanitizeNotifyText(question, 120, 'Hermes가 답변을 기다리고 있습니다.')
  const cleanChoices = (Array.isArray(choices) ? choices : [])
    .map(choice => sanitizeNotifyText(choice, 32))
    .filter(Boolean)
    .slice(0, 4)

  return cleanChoices.length ? `질문: ${cleanQuestion} · 선택지: ${cleanChoices.join(' / ')}` : `질문: ${cleanQuestion}`
}

export const formatApprovalPreview = (description: unknown, command: unknown) => {
  const cleanDescription = sanitizeNotifyText(description, 80, '위험 작업 승인 필요')
  const cleanCommand = sanitizeCommandPreview(command)

  return `${cleanDescription} · 실행: ${cleanCommand}`
}

export const formatSecretPreview = (prompt: unknown) =>
  `요청: ${sanitizeNotifyText(prompt, 160, 'Hermes가 비밀값 입력을 기다리고 있습니다.')}`

export const formatErrorPreview = (message: unknown) => sanitizeNotifyText(message, 180, '오류가 발생했습니다. TUI를 확인하세요.')

export const macNotificationsDisabledByEnv = () => /^(?:0|false|off|no)$/i.test((process.env.HERMES_TUI_MAC_NOTIFICATIONS ?? '').trim())

const truthyEnv = (value: string | undefined) => /^(?:1|true|yes|on)$/i.test((value ?? '').trim())

export const notifyEnv = (app?: string) => {
  const env = { ...process.env }

  if (
    app === 'Hermes' &&
    !truthyEnv(env.HERMES_NOTIFY_DISABLE_CLICK_FOCUS) &&
    !truthyEnv(env.AGENT_NOTIFY_DISABLE_CLICK_FOCUS) &&
    !env.AGENT_NOTIFY_CLICK_ROUTE &&
    !env.HERMES_NOTIFY_CLICK_ROUTE
  ) {
    env.AGENT_NOTIFY_CLICK_ROUTE = 'applescript-stable-id'
  }

  return env
}

export const withTimeoutFallback = <T,>(promise: Promise<T>, ms: number, fallback: T): Promise<T> =>
  new Promise(resolve => {
    const timer = setTimeout(() => resolve(fallback), ms)

    promise.then(
      value => {
        clearTimeout(timer)
        resolve(value)
      },
      () => {
        clearTimeout(timer)
        resolve(fallback)
      }
    )
  })

export const notifyMac = (app: string, context: string, subtitle: string, body: string, category: NotificationCategory) => {
  const script = agentNotifyScriptPath()

  if (process.platform !== 'darwin' || !existsSync(script)) {
    debugNotify(`notifyMac skipped platform=${process.platform} exists=${existsSync(script)} category=${category}`)

    return
  }

  try {
    // A successful spawn means the alert was handed to the local notification helper.
    // macOS Focus / Do Not Disturb suppression remains an external OS state, not
    // something this helper bypasses with sender or ignoreDnD options.
    debugNotify(`notifyMac spawn app=${app} context=${cleanNotifyPart(context)} subtitle=${subtitle} category=${category}`)
    const child = spawn(
      script,
      ['--app', app, '--context', context, '--subtitle', subtitle, '--message', body, '--category', category],
      { detached: true, env: notifyEnv(app), stdio: 'ignore' }
    )

    child.unref()
  } catch {
    debugNotify(`notifyMac spawn_error app=${app} subtitle=${subtitle} category=${category}`)
    // Notification delivery is best-effort. Never disturb the TUI event loop or agent turn.
  }
}

export class MacNotificationController {
  private cachedSessionTitle = ''
  private cachedSessionTitleAt = 0
  private cachedSessionTitleSid: null | string = null
  private readonly bellOnComplete: boolean | null | undefined
  private readonly getSessionId: () => null | string
  private readonly rpc: GatewayRpc
  private readonly stdout: NotificationStdout | undefined

  constructor(options: MacNotificationControllerOptions) {
    this.bellOnComplete = options.bellOnComplete
    this.getSessionId = options.getSessionId
    this.rpc = options.rpc
    this.stdout = options.stdout
  }

  notifyWaitUser(subtitle: string, body: string) {
    void this.resolveMacNotificationsEnabled().then(enabled => {
      if (enabled) {
        this.notifyUser(subtitle, body, 'wait.input')
      }
    })
  }

  notifyCompletionUser(subtitle: string, body: string) {
    if (this.bellOnComplete === true && this.stdout?.isTTY) {
      this.stdout.write('\x07')
    }

    void this.resolveMacNotificationsEnabled().then(enabled => {
      if (enabled) {
        this.notifyUser(subtitle, body, 'done.review')
      }
    })
  }

  notifyBlockedUser(subtitle: string, body: string) {
    void this.resolveMacNotificationsEnabled().then(enabled => {
      if (enabled) {
        this.notifyUser(subtitle, body, 'blocked.error')
      }
    })
  }

  private notifyUser(subtitle: string, body: string, category: NotificationCategory) {
    debugNotify(`notifyUser requested subtitle=${subtitle} category=${category} sid=${this.getSessionId() ?? ''}`)
    void this.resolveSessionTitle()
      .catch(e => {
        debugNotify(`notifyUser title_error=${rpcErrorMessage(e)} subtitle=${subtitle} category=${category}`)

        return ''
      })
      .then(sessionTitle => {
        debugNotify(`notifyUser resolved_title=${cleanNotifyPart(sessionTitle)} subtitle=${subtitle} category=${category}`)
        notifyMac('Hermes', sessionTitle, subtitle, body, category)
      })
  }

  private resolveMacNotificationsEnabled() {
    if (macNotificationsDisabledByEnv()) {
      return Promise.resolve(false)
    }

    return withTimeoutFallback(
      this.rpc<ConfigFullResponse>('config.get', { key: 'full' })
        .then(cfg => cfg?.config?.display?.tui_mac_notifications !== false)
        .catch(() => true),
      NOTIFICATION_CONFIG_TIMEOUT_MS,
      true
    )
  }

  private async resolveSessionTitle() {
    const sid = this.getSessionId()

    if (!sid) {
      return ''
    }

    const now = Date.now()

    if (this.cachedSessionTitleSid === sid && now - this.cachedSessionTitleAt < 30_000) {
      return this.cachedSessionTitle
    }

    this.cachedSessionTitleSid = sid
    this.cachedSessionTitleAt = now

    try {
      const response = await withTimeoutFallback<null | SessionTitleResponse>(
        this.rpc<SessionTitleResponse>('session.title', { session_id: sid }),
        SESSION_TITLE_TIMEOUT_MS,
        null
      )

      this.cachedSessionTitle = cleanNotifyPart(response?.title ?? '')
    } catch {
      this.cachedSessionTitle = ''
    }

    return this.cachedSessionTitle
  }
}
