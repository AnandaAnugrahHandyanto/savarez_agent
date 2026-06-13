'use strict'

const RESOLVER_CACHE_SCHEMA_VERSION = 1

/**
 * Small, dependency-injected helpers for deciding whether Desktop can reuse an
 * already-installed Hermes Agent runtime. Keep this separate from main.cjs so
 * the decision is unit-testable without booting Electron.
 */
function hasUsableActiveInstall(opts) {
  const {
    activeRoot,
    appVersion,
    canImportHermesCli,
    fileExists,
    getVenvPython,
    isHermesSourceRoot,
    readResolverCache,
    rememberLog,
    venvRoot,
    writeResolverCache
  } = opts || {}

  if (!activeRoot || !venvRoot) return false
  if (typeof isHermesSourceRoot !== 'function' || typeof fileExists !== 'function') return false
  if (typeof getVenvPython !== 'function' || typeof canImportHermesCli !== 'function') return false

  if (!isHermesSourceRoot(activeRoot)) return false

  const venvPython = getVenvPython(venvRoot)
  if (!venvPython || !fileExists(venvPython)) return false

  if (isResolverCacheHit({ activeRoot, appVersion, readResolverCache, venvPython })) {
    return true
  }

  if (!canImportHermesCli(venvPython)) {
    if (typeof rememberLog === 'function') {
      rememberLog(`Ignoring existing Hermes install at ${activeRoot}: hermes_cli is not importable from ${venvPython}.`)
    }
    return false
  }

  writeResolverCacheHit({ activeRoot, appVersion, venvPython, writeResolverCache })
  return true
}

function isResolverCacheHit(opts) {
  const { activeRoot, appVersion, readResolverCache, venvPython } = opts || {}
  if (!activeRoot || !appVersion || !venvPython || typeof readResolverCache !== 'function') return false

  try {
    const cache = readResolverCache()
    return Boolean(
      cache &&
        cache.schemaVersion === RESOLVER_CACHE_SCHEMA_VERSION &&
        cache.activeRoot === activeRoot &&
        cache.venvPython === venvPython &&
        cache.appVersion === appVersion &&
        cache.canImportHermesCli === true
    )
  } catch {
    return false
  }
}

function writeResolverCacheHit(opts) {
  const { activeRoot, appVersion, venvPython, writeResolverCache } = opts || {}
  if (!activeRoot || !appVersion || !venvPython || typeof writeResolverCache !== 'function') return

  try {
    writeResolverCache({
      schemaVersion: RESOLVER_CACHE_SCHEMA_VERSION,
      activeRoot,
      venvPython,
      appVersion,
      canImportHermesCli: true,
      checkedAt: new Date().toISOString()
    })
  } catch {
    // Cache writes are strictly an optimization; runtime resolution must not
    // fail just because userData is read-only or temporarily unavailable.
  }
}

module.exports = { hasUsableActiveInstall, isResolverCacheHit, writeResolverCacheHit }
