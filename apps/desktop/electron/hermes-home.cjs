'use strict'

// Pure helper for resolving the Windows HERMES_HOME, extracted so it can be
// unit-tested without booting Electron. See resolveHermesHome() in main.cjs.

const path = require('node:path')

// Choose between the modern %LOCALAPPDATA%\hermes and a legacy ~/.hermes left by
// a prior pip/CLI install.
//
// The desktop installer (hermes-setup.exe) can create %LOCALAPPDATA%\hermes
// *before* the app first runs, so a plain "does the directory exist?" check
// always picks LOCALAPPDATA and silently orphans a CLI-first user's sessions
// (#40178). We instead key off the real data signal — state.db — and only fall
// back to the directory-existence heuristic when neither side has a DB yet.
//
// `dirExists(p)` and `fileExists(p)` are injected so callers (and tests) supply
// their own filesystem probes.
function chooseWindowsHermesHome(localappdata, legacy, { dirExists, fileExists }) {
  const localappdataDb = fileExists(path.join(localappdata, 'state.db'))
  const legacyDb = fileExists(path.join(legacy, 'state.db'))

  // An established desktop install (real data in LOCALAPPDATA) always wins —
  // never hijack it back to legacy.
  if (localappdataDb) {
    return localappdata
  }

  // Real CLI data in ~/.hermes and none in LOCALAPPDATA yet → honour the
  // existing setup even though the installer may have pre-created an empty
  // LOCALAPPDATA\hermes (#40178).
  if (legacyDb) {
    return legacy
  }

  // No DB on either side. Preserve the original heuristic: a brand-new
  // LOCALAPPDATA (not created yet) and an existing legacy dir → keep legacy so
  // config/.env aren't orphaned even before any session has been written.
  if (!dirExists(localappdata) && dirExists(legacy)) {
    return legacy
  }

  return localappdata
}

module.exports = { chooseWindowsHermesHome }
