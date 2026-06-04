import type { SessionInfo } from '@/types/hermes'

/** Session sources that represent scheduled/automated runs, not manual desktop chat. */
const AUTOMATED_SOURCES = new Set(['cron', 'gateway', 'api_server', 'api-server', 'scheduled', 'autonomous'])

export function isManualChatSession(session: Pick<SessionInfo, 'source'>): boolean {
  const src = (session.source || 'cli').trim().toLowerCase()

  return !AUTOMATED_SOURCES.has(src)
}
