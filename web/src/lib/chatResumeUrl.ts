/** Active chat session id (`?resume=`). */
export function getResumeParamFromSearch(search: string): string | null {
  const value = new URLSearchParams(search).get("resume");
  return value?.trim() || null;
}

export function isChatRoutePath(pathname: string): boolean {
  return (pathname.replace(/\/$/, "") || "/") === "/chat";
}

/** Query flag: chat sidebar is in the drilled-down session list mode. */
export const CHAT_SESSIONS_SIDEBAR_PARAM = "sessions";

export function hasSessionsSidebarParam(search: string): boolean {
  const value = new URLSearchParams(search).get(CHAT_SESSIONS_SIDEBAR_PARAM);
  if (value === null) return false;
  const trimmed = value.trim().toLowerCase();
  return trimmed === "" || trimmed === "1" || trimmed === "true";
}

/** True when the URL requests the drilled session sidebar on /chat. */
export function shouldDrillChatSidebar(pathname: string, search: string): boolean {
  return isChatRoutePath(pathname) && hasSessionsSidebarParam(search);
}

export function withSessionsSidebarParam(
  params: URLSearchParams,
): URLSearchParams {
  const next = new URLSearchParams(params);
  next.set(CHAT_SESSIONS_SIDEBAR_PARAM, "1");
  return next;
}

export function withoutSessionsSidebarParam(
  params: URLSearchParams,
): URLSearchParams {
  const next = new URLSearchParams(params);
  next.delete(CHAT_SESSIONS_SIDEBAR_PARAM);
  return next;
}

/** Drop all chat URL state (resume + drilled sidebar). */
export function clearChatSessionQueryParams(
  params: URLSearchParams,
): URLSearchParams {
  return stripResumeParam(withoutSessionsSidebarParam(params));
}

/** Remove `?resume=` and `?resume_exact=` from the URL. */
export function stripResumeParam(params: URLSearchParams): URLSearchParams {
  const next = new URLSearchParams(params);
  next.delete("resume");
  next.delete(RESUME_EXACT_PARAM);
  return next;
}

/** User picked a specific stored session — resume that id exactly. */
export const RESUME_EXACT_PARAM = "resume_exact";

export function hasResumeExactParam(search: string): boolean {
  const value = new URLSearchParams(search).get(RESUME_EXACT_PARAM);
  if (value === null) return false;
  const trimmed = value.trim().toLowerCase();
  return trimmed === "" || trimmed === "1" || trimmed === "true";
}

export function withResumeSession(
  params: URLSearchParams,
  storedId: string,
  opts?: { exact?: boolean },
): URLSearchParams {
  const next = new URLSearchParams(params);
  next.set("resume", storedId);
  if (opts?.exact !== false) {
    next.set(RESUME_EXACT_PARAM, "1");
  } else {
    next.delete(RESUME_EXACT_PARAM);
  }
  return next;
}
