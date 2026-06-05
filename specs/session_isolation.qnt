// Hermes Agent Session Isolation — Quint Spec
// Models context compaction cross-contamination (#38788)
//
// MECHANISM: ContextCompressor.on_session_end() is a no-op.
// _previous_summary survives session end and leaks into next session.
//
// Each session lifecycle: compress → session_end → new_session_starts
// THE BUG: session_end doesn't clear summary, so new session inherits it.
// THE FIX: session_end clears _previous_summary = None.

module session_isolation {

  var previousSummaryExists: bool  // _previous_summary is not None
  var sessionEnded: bool           // on_session_end was called
  var newSessionStarted: bool      // new session has begun
  var leaked: bool                 // cross-contamination detected

  action init = all {
    previousSummaryExists' = false,
    sessionEnded' = false,
    newSessionStarted' = false,
    leaked' = false,
  }

  // ---- Buggy lifecycle (on_session_end is a NO-OP) ----

  action bug_compress = all {
    sessionEnded == false,
    newSessionStarted == false,
    previousSummaryExists' = true,
    sessionEnded' = false,
    newSessionStarted' = false,
    leaked' = false,
  }

  action bug_sessionEnd = all {
    previousSummaryExists == true,
    sessionEnded == false,
    // BUG: does NOT clear previousSummaryExists
    previousSummaryExists' = true,
    sessionEnded' = true,
    newSessionStarted' = false,
    leaked' = false,
  }

  action bug_newSession = all {
    sessionEnded == true,
    newSessionStarted == false,
    // BUG: previousSummaryExists is still true → LEAK
    newSessionStarted' = true,
    // The leak: summary from old session is visible in new session
    leaked' = previousSummaryExists,
    previousSummaryExists' = previousSummaryExists,
    sessionEnded' = false,  // reset for next cycle
  }

  // ---- Fixed lifecycle (on_session_end clears summary) ----

  action fix_compress = all {
    sessionEnded == false,
    newSessionStarted == false,
    previousSummaryExists' = true,
    sessionEnded' = false,
    newSessionStarted' = false,
    leaked' = false,
  }

  action fix_sessionEnd = all {
    previousSummaryExists == true,
    sessionEnded == false,
    // FIX: clear _previous_summary
    previousSummaryExists' = false,
    sessionEnded' = true,
    newSessionStarted' = false,
    leaked' = false,
  }

  action fix_newSession = all {
    sessionEnded == true,
    newSessionStarted == false,
    // FIX: previousSummaryExists is now false, so no leak possible
    newSessionStarted' = true,
    leaked' = previousSummaryExists,
    previousSummaryExists' = previousSummaryExists,
    sessionEnded' = false,
  }

  // ---- Choice: buggy or fixed ----

  action step = any {
    // Buggy cycle
    bug_compress,
    bug_sessionEnd,
    bug_newSession,
    // Fixed cycle
    fix_compress,
    fix_sessionEnd,
    fix_newSession,
  }

  val no_cross_contamination = not(leaked)
}
