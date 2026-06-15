import { api } from "@/lib/api";
import { hasResumeExactParam, stripResumeParam } from "@/lib/chatResumeUrl";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

export interface ResolvedResumeParam {
  /** Raw `?resume=` from the URL. */
  resumeParam: string | null;
  /** Validated session id to bind (exact — never rewritten to a branch child). */
  targetId: string | null;
  /** False while validating a non-empty resume param. */
  ready: boolean;
  /** True when `?resume_exact=` requests an exact stored-session resume. */
  resumeExact: boolean;
}

/**
 * Validate `?resume=` exists in the session store before bind / PTY spawn.
 *
 * Uses the exact id from the URL. Descendant resolution is intentionally
 * omitted — sidebar picks and deep-links must open the session the user chose,
 * not the newest child branch.
 */
export function useResolvedResumeParam(profile: string): ResolvedResumeParam {
  const [searchParams, setSearchParams] = useSearchParams();
  const resumeParam = searchParams.get("resume")?.trim() || null;
  const resumeExact = hasResumeExactParam(searchParams.toString());

  const [targetId, setTargetId] = useState<string | null>(null);
  const [ready, setReady] = useState(!resumeParam);

  useEffect(() => {
    if (!resumeParam) {
      setTargetId(null);
      setReady(true);
      return;
    }

    let cancelled = false;
    setReady(false);

    api
      .getSessionMessages(resumeParam, profile)
      .then(() => {
        if (cancelled) return;
        setTargetId(resumeParam);
      })
      .catch(() => {
        if (cancelled) return;
        setSearchParams((prev) => stripResumeParam(prev), { replace: true });
        setTargetId(null);
      })
      .finally(() => {
        if (!cancelled) setReady(true);
      });

    return () => {
      cancelled = true;
    };
  }, [resumeParam, profile, setSearchParams]);

  return {
    resumeParam,
    targetId: resumeParam && targetId ? targetId : null,
    ready,
    resumeExact,
  };
}
