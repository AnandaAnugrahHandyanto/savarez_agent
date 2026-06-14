import { describe, expect, it } from 'vitest'

import {
  agentNotifyScriptPath,
  formatApprovalPreview,
  formatChoicesPreview,
  formatErrorPreview,
  formatSecretPreview,
  macNotificationsDisabledByEnv,
  notifyEnv,
  sanitizeNotifyText
} from '../app/notifications.js'

describe('notification formatting helpers', () => {
  it('redacts sensitive values before text leaves the TUI process', () => {
    const fakeTokenValue = ['secret', 'code'].join('-')
    const fakePasswordValue = ['hunter', '2'].join('')
    const fakeBearerValue = ['abc', 'def', '123', '456'].join('')
    const fakeGitHubToken = ['ghp', '_', 'abc', 'def', 'ghi', 'jkl', 'mno', 'pqr', 'stu', 'vwx', 'yz'].join('')
    const fakeApprovalCommand = [
      'curl https://example.test/deploy?to',
      'ken=',
      fakeTokenValue,
      ' -H "',
      ['Auth', 'orization: Be', 'arer '].join(''),
      fakeBearerValue,
      '" --data pass',
      'word=',
      fakePasswordValue
    ].join('')
    const approval = formatApprovalPreview('Deploy production', fakeApprovalCommand)
    const choices = formatChoicesPreview(`Continue with pass${'word'}=${fakePasswordValue}?`, [
      `Use to${'ken'}=${fakeGitHubToken}`,
      `postgres://user:${fakePasswordValue}@example.test/db`,
      'Cancel'
    ])
    const secret = formatSecretPreview(`Paste API key api_${'key'}=abc123`)
    const fakeOauthCode = ['oauth', 'secret'].join('-')
    const fakeOpaqueToken = `${'abcdef'.repeat(4)}${'123456'.repeat(4)}`
    const error = formatErrorPreview(`Provider failed oauth_code=${fakeOauthCode} ${fakeOpaqueToken}`)

    expect(approval).toContain('Deploy production')
    expect(approval).toContain('[REDACTED]')
    expect(approval).not.toContain(fakeTokenValue)
    expect(approval).not.toContain(fakePasswordValue)
    expect(approval).not.toContain(fakeBearerValue)

    expect(choices).toContain('password=[REDACTED]')
    expect(choices).toContain('token=[REDACTED]')
    expect(choices).toContain('postgres://user:')
    expect(choices).not.toContain(fakeGitHubToken)
    expect(choices).not.toContain(fakePasswordValue)

    expect(secret).toBe('요청: Paste API key api_key=[REDACTED]')
    expect(error).toContain('oauth_code=[REDACTED]')
    expect(error).not.toContain(fakeOauthCode)
    expect(error).not.toContain(fakeOpaqueToken)
  })

  it('normalizes whitespace, strips ANSI, and applies fallback text', () => {
    expect(sanitizeNotifyText('\u001b[31m  hello\n\tworld  \u001b[0m')).toBe('hello world')
    expect(sanitizeNotifyText('', 180, 'fallback')).toBe('fallback')
  })
})

describe('notification runtime environment', () => {
  it('uses the local Hermes notification helper path without hardcoding a user home', () => {
    const oldHermesHome = process.env.HERMES_HOME
    const oldHome = process.env.HOME
    const oldOverride = process.env.HERMES_AGENT_NOTIFY_SCRIPT

    try {
      delete process.env.HERMES_AGENT_NOTIFY_SCRIPT
      delete process.env.HERMES_HOME
      process.env.HOME = '/tmp/home'
      expect(agentNotifyScriptPath()).toBe('/tmp/home/.hermes/bin/agent-notify')

      process.env.HERMES_HOME = '/tmp/hermes-home'
      expect(agentNotifyScriptPath()).toBe('/tmp/hermes-home/bin/agent-notify')

      process.env.HERMES_AGENT_NOTIFY_SCRIPT = '/tmp/custom-agent-notify'
      expect(agentNotifyScriptPath()).toBe('/tmp/custom-agent-notify')
    } finally {
      if (oldHermesHome === undefined) {
        delete process.env.HERMES_HOME
      } else {
        process.env.HERMES_HOME = oldHermesHome
      }

      if (oldHome === undefined) {
        delete process.env.HOME
      } else {
        process.env.HOME = oldHome
      }

      if (oldOverride === undefined) {
        delete process.env.HERMES_AGENT_NOTIFY_SCRIPT
      } else {
        process.env.HERMES_AGENT_NOTIFY_SCRIPT = oldOverride
      }
    }
  })

  it('passes only a stable-id route hint by default for Hermes notifications', () => {
    const snapshot = { ...process.env }

    try {
      delete process.env.AGENT_NOTIFY_CLICK_ROUTE
      delete process.env.HERMES_NOTIFY_CLICK_ROUTE
      delete process.env.AGENT_NOTIFY_DISABLE_CLICK_FOCUS
      delete process.env.HERMES_NOTIFY_DISABLE_CLICK_FOCUS

      expect(notifyEnv('Hermes')).toEqual(expect.objectContaining({ AGENT_NOTIFY_CLICK_ROUTE: 'applescript-stable-id' }))

      process.env.HERMES_NOTIFY_DISABLE_CLICK_FOCUS = '1'
      expect(notifyEnv('Hermes')).not.toHaveProperty('AGENT_NOTIFY_CLICK_ROUTE')
    } finally {
      process.env = snapshot
    }
  })

  it('treats explicit false-like env values as the macOS notification off switch', () => {
    const oldValue = process.env.HERMES_TUI_MAC_NOTIFICATIONS

    try {
      process.env.HERMES_TUI_MAC_NOTIFICATIONS = 'false'
      expect(macNotificationsDisabledByEnv()).toBe(true)

      process.env.HERMES_TUI_MAC_NOTIFICATIONS = '1'
      expect(macNotificationsDisabledByEnv()).toBe(false)
    } finally {
      if (oldValue === undefined) {
        delete process.env.HERMES_TUI_MAC_NOTIFICATIONS
      } else {
        process.env.HERMES_TUI_MAC_NOTIFICATIONS = oldValue
      }
    }
  })
})
