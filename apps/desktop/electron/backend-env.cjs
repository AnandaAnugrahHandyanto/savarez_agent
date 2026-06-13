const path = require('node:path')
const fs = require('node:fs')

// Match the POSIX fallback surface used by the Python terminal environment.
// macOS apps launched from Finder/Dock often inherit only /usr/bin:/bin:/usr/sbin:/sbin,
// which misses Apple Silicon Homebrew and user-installed CLI tools such as codex.
const POSIX_SANE_PATH_ENTRIES = Object.freeze([
  '/opt/homebrew/bin',
  '/opt/homebrew/sbin',
  '/usr/local/sbin',
  '/usr/local/bin',
  '/usr/sbin',
  '/usr/bin',
  '/sbin',
  '/bin'
])

function delimiterForPlatform(platform = process.platform) {
  return platform === 'win32' ? ';' : ':'
}

function pathModuleForPlatform(platform = process.platform) {
  return platform === 'win32' ? path.win32 : path.posix
}

function pathEnvKey(env = process.env, platform = process.platform) {
  if (platform !== 'win32') return 'PATH'
  return Object.keys(env || {}).find(key => key.toUpperCase() === 'PATH') || 'PATH'
}

function currentPathValue(env = process.env, platform = process.platform) {
  const key = pathEnvKey(env, platform)
  return env?.[key] || ''
}

function appendUniquePathEntries(entries, { delimiter = path.delimiter } = {}) {
  const seen = new Set()
  const ordered = []

  for (const entry of entries) {
    if (!entry) continue
    const parts = Array.isArray(entry) ? entry : String(entry).split(delimiter)
    for (const part of parts) {
      if (!part || seen.has(part)) continue
      seen.add(part)
      ordered.push(part)
    }
  }

  return ordered.join(delimiter)
}

function buildDesktopBackendPath({
  hermesHome,
  venvRoot,
  currentPath = '',
  platform = process.platform,
  pathModule = pathModuleForPlatform(platform)
} = {}) {
  const delimiter = delimiterForPlatform(platform)
  const hermesNodeBin = hermesHome ? pathModule.join(hermesHome, 'node', 'bin') : null
  const venvBin = venvRoot ? pathModule.join(venvRoot, platform === 'win32' ? 'Scripts' : 'bin') : null
  const saneEntries = platform === 'win32' ? [] : POSIX_SANE_PATH_ENTRIES

  return appendUniquePathEntries(
    [hermesNodeBin, venvBin, currentPath, saneEntries],
    { delimiter }
  )
}

function buildDesktopBackendEnv({
  hermesHome,
  pythonPathEntries = [],
  venvRoot,
  currentEnv = process.env,
  platform = process.platform,
  pathModule = pathModuleForPlatform(platform)
} = {}) {
  const delimiter = delimiterForPlatform(platform)
  const currentPythonPath = currentEnv?.PYTHONPATH || ''
  const key = pathEnvKey(currentEnv, platform)

  return {
    PYTHONPATH: appendUniquePathEntries([...pythonPathEntries, currentPythonPath], { delimiter }),
    [key]: buildDesktopBackendPath({
      hermesHome,
      venvRoot,
      currentPath: currentPathValue(currentEnv, platform),
      platform,
      pathModule
    })
  }
}

/**
 * Read and parse a .env file at the given home path.
 *
 * Returns a flat object of KEY=VALUE pairs found in {homePath}/.env, or an
 * empty object when the file is missing or unreadable.  Supports:
 *   - KEY=VALUE and KEY="VALUE" (double-quoted) and KEY='VALUE' (single-quoted)
 *   - Blank lines and #-prefixed comment lines
 *   - Leading/trailing whitespace trimming around key and value
 *
 * Designed to complement Python's python-dotenv so that the Electron main
 * process can forward .env-sourced variables (e.g. OPENROUTER_API_KEY) to
 * the spawned backend child without waiting for load_hermes_dotenv() in
 * Python — essential on Windows where process.env may not always include
 * the user's shell-sourced .env values when the app is launched outside a
 * terminal context (Start Menu, auto-start, etc.).
 *
 * Does NOT do variable expansion ($VAR).  The child process receives the raw
 * values; Python's dotenv handles expansion when load_hermes_dotenv() runs.
 */
function readDotenvFile(homePath) {
  const envPath = path.join(homePath, '.env')
  try {
    const text = fs.readFileSync(envPath, 'utf8')
    const result = {}
    for (const rawLine of text.split('\n')) {
      const line = rawLine.replace('\r', '').trim()
      if (!line || line.startsWith('#')) continue
      const eqIndex = line.indexOf('=')
      if (eqIndex === -1) continue
      const key = line.slice(0, eqIndex).trim()
      if (!key) continue
      let val = line.slice(eqIndex + 1).trim()
      // Strip matching surrounding quotes
      if ((val.startsWith('"') && val.endsWith('"')) ||
          (val.startsWith("'") && val.endsWith("'"))) {
        val = val.slice(1, -1)
      }
      result[key] = val
    }
    return result
  } catch {
    // ENOENT or permission error — no .env file or not readable
    return {}
  }
}

module.exports = {
  POSIX_SANE_PATH_ENTRIES,
  appendUniquePathEntries,
  buildDesktopBackendEnv,
  buildDesktopBackendPath,
  delimiterForPlatform,
  pathEnvKey,
  readDotenvFile
}
