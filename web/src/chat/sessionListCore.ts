/** Shared session-list merge helpers (ported from ui-tui activeSessionSwitcher). */

export interface SessionListItem {
  id: string;
  title: string;
  preview: string;
  started_at: number;
  message_count: number;
  source?: string;
}

export type LiveSessionStatus =
  | "idle"
  | "starting"
  | "waiting"
  | "working";

export interface SessionActiveItem {
  id: string;
  session_key?: string;
  title?: string;
  preview?: string;
  model?: string;
  status: LiveSessionStatus;
  current?: boolean;
  started_at?: number;
  last_active?: number;
  message_count?: number;
}

export interface SessionListResponse {
  sessions?: SessionListItem[];
}

export interface SessionActiveListResponse {
  sessions?: SessionActiveItem[];
}

/** Drop live sessions from the resumable history list (dedupe by id / session_key). */
export function resumableHistory(
  history: readonly SessionListItem[],
  live: readonly SessionActiveItem[],
): SessionListItem[] {
  const liveIds = new Set<string>();
  for (const s of live) {
    liveIds.add(s.id);
    const key = (s.session_key ?? "").trim();
    if (key) liveIds.add(key);
  }
  return history.filter((h) => !liveIds.has(h.id));
}

export function relativeSessionAge(ts?: number): string {
  if (!ts) return "";
  const days = (Date.now() / 1000 - ts) / 86400;
  if (days < 1) return "today";
  if (days < 2) return "yesterday";
  return `${Math.floor(days)}d ago`;
}

export function sessionDisplayTitle(
  title?: string,
  preview?: string,
  untitledLabel = "Untitled",
): string {
  const trimmed = (title ?? "").trim();
  if (trimmed) return trimmed;
  const p = (preview ?? "").trim();
  if (p) return p.slice(0, 60);
  return untitledLabel;
}
