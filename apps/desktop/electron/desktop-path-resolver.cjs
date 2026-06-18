'use strict'

const path = require('node:path')
const {
  buildDesktopBackendPath,
  currentPathValue,
  delimiterForPlatform,
  pathModuleForPlatform
} = require('./backend-env.cjs')

function buildDesktopResolverPath({
  hermesHome,
  venvRoot,
  currentEnv = process.env,
  platform = process.platform,
  pathModule = pathModuleForPlatform(platform)
} = {}) {
  return buildDesktopBackendPath({
    hermesHome,
    venvRoot,
    currentPath: currentPathValue(currentEnv, platform),
    platform,
    pathModule
  })
}

function executableExtensions({ platform = process.platform, currentEnv = process.env } = {}) {
  if (platform !== 'win32') return ['']
  return ['', ...(currentEnv?.PATHEXT || '.COM;.EXE;.BAT;.CMD').split(';').filter(Boolean)]
}

function commandIncludesPathSeparator(command, { platform = process.platform, pathModule = pathModuleForPlatform(platform) } = {}) {
  return command.includes(pathModule.sep) || (platform === 'win32' && command.includes('/'))
}

function findExecutableOnPath(command, {
  searchPath,
  currentEnv = process.env,
  platform = process.platform,
  pathModule = pathModuleForPlatform(platform),
  fileExists,
  isWindowsBinaryPathInWsl = () => false,
  isWsl = false
} = {}) {
  if (!command || typeof fileExists !== 'function') return null

  if (pathModule.isAbsolute(command) || commandIncludesPathSeparator(command, { platform, pathModule })) {
    if (!fileExists(command)) return null
    if (isWindowsBinaryPathInWsl(command, { isWsl })) return null
    return command
  }

  const pathEntries = String(searchPath ?? currentPathValue(currentEnv, platform) ?? '')
    .split(delimiterForPlatform(platform))
    .filter(Boolean)
  const extensions = executableExtensions({ platform, currentEnv })

  for (const entry of pathEntries) {
    for (const extension of extensions) {
      const candidate = pathModule.join(entry, `${command}${extension}`)
      if (fileExists(candidate)) return candidate
    }
  }

  return null
}

module.exports = {
  buildDesktopResolverPath,
  findExecutableOnPath
}
