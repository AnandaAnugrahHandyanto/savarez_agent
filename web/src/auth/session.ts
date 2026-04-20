export interface AuthSession {
  email: string;
  token: string;
  expiresAt: string;
  remember: boolean;
  loggedInAt: string;
}

const AUTH_STORAGE_KEY = 'hermes.chat-studio.auth.v1';

declare global {
  interface Window {
    __HERMES_USER_TOKEN__?: string;
  }
}

function isBrowser() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

function normalizeSession(raw: unknown): AuthSession | null {
  if (!raw || typeof raw !== 'object') return null;
  const candidate = raw as Partial<AuthSession>;
  if (
    typeof candidate.email !== 'string'
    || typeof candidate.token !== 'string'
    || typeof candidate.expiresAt !== 'string'
    || typeof candidate.loggedInAt !== 'string'
  ) {
    return null;
  }

  return {
    email: candidate.email.trim().toLowerCase(),
    token: candidate.token.trim(),
    expiresAt: candidate.expiresAt,
    remember: Boolean(candidate.remember),
    loggedInAt: candidate.loggedInAt,
  };
}

export function loadAuthSession(): AuthSession | null {
  if (!isBrowser()) return null;
  try {
    const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const session = normalizeSession(JSON.parse(raw));
    if (!session) return null;
    window.__HERMES_USER_TOKEN__ = session.token;
    return session;
  } catch {
    return null;
  }
}

export function saveAuthSession(session: Omit<AuthSession, 'loggedInAt'> & { loggedInAt?: string }): AuthSession {
  const normalized: AuthSession = {
    ...session,
    email: session.email.trim().toLowerCase(),
    token: session.token.trim(),
    expiresAt: session.expiresAt,
    remember: Boolean(session.remember),
    loggedInAt: session.loggedInAt ?? new Date().toISOString(),
  };

  if (isBrowser()) {
    window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(normalized));
    window.__HERMES_USER_TOKEN__ = normalized.token;
  }

  return normalized;
}

export function clearAuthSession() {
  if (!isBrowser()) return;
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  delete window.__HERMES_USER_TOKEN__;
}

export function getAuthToken() {
  if (typeof window !== 'undefined' && window.__HERMES_USER_TOKEN__) {
    return window.__HERMES_USER_TOKEN__;
  }
  const session = loadAuthSession();
  return session?.token ?? null;
}

export function getStoredAuthSession() {
  return loadAuthSession();
}
