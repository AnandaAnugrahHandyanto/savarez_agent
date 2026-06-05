// Hermes Agent Session Isolation — FIXED version
// bug_sessionEnd does NOT clear previousSummaryExists
// fix_sessionEnd DOES clear it — proving the fix works.

module session_isolation {

  var previousSummaryExists: bool
  var sessionEnded: bool
  var newSessionStarted: bool
  var leaked: bool

  action init = all {
    previousSummaryExists' = false,
    sessionEnded' = false,
    newSessionStarted' = false,
    leaked' = false,
  }

  action compress = all {
    sessionEnded == false,
    newSessionStarted == false,
    previousSummaryExists' = true,
    sessionEnded' = false,
    newSessionStarted' = false,
    leaked' = false,
  }

  // FIX: on_session_end clears _previous_summary
  action sessionEnd = all {
    previousSummaryExists == true,
    sessionEnded == false,
    previousSummaryExists' = false,   // <-- THE FIX
    sessionEnded' = true,
    newSessionStarted' = false,
    leaked' = false,
  }

  action newSession = all {
    sessionEnded == true,
    newSessionStarted == false,
    newSessionStarted' = true,
    // previousSummaryExists is false (cleared above), so leaked stays false
    leaked' = previousSummaryExists,
    previousSummaryExists' = previousSummaryExists,
    sessionEnded' = false,
  }

  action step = any {
    compress,
    sessionEnd,
    newSession,
  }

  val no_cross_contamination = not(leaked)
}
