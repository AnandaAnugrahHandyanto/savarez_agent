'use strict'

/**
 * after-pack.cjs — electron-builder afterPack hook.
 *
 * Stamps the Hermes icon + identity onto the packed Windows Hermes.exe via
 * rcedit (delegated to set-exe-identity.cjs). This runs for EVERY packed build
 * — first install, `hermes desktop`, the installer's --update rebuild, and a
 * dev's manual `npm run pack` — so the branded exe can never silently revert
 * to the stock "Electron" icon/name (the bug when the stamp lived only in
 * install.ps1, which the update path doesn't use).
 *
 * Also cleans up the backup unpacked directory stashed by before-pack.cjs.
 * Because afterPack only runs on a successful pack, the backup is safely
 * removed here — if we reach this hook, the new build is complete.
 *
 * Windows-only stamp: rcedit edits PE resources, irrelevant on macOS/Linux
 * where the app identity comes from the bundle Info.plist / desktop entry.
 * Best-effort: a stamp failure must never fail an otherwise-good build (worst
 * case is the stock icon, not a broken app), so we log and resolve rather
 * than throw.
 *
 * electron-builder passes a context with:
 *   - electronPlatformName: 'win32' | 'darwin' | 'linux'
 *   - appOutDir:            the unpacked app directory for this target
 *   - packager.appInfo.productFilename: the exe basename (e.g. 'Hermes')
 */

const fs = require('node:fs')
const path = require('node:path')

const { stampExeIdentity } = require('./set-exe-identity.cjs')

/** Remove the backup dir stashed by before-pack.cjs, if present. */
function removeBackupDir(appOutDir) {
  const backupDir = appOutDir + '.backup'
  if (fs.existsSync(backupDir)) {
    fs.rmSync(backupDir, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 })
    console.log(`[after-pack] removed backup unpacked dir: ${backupDir}`)
  }
}

exports.removeBackupDir = removeBackupDir

exports.default = async function afterPack(context) {
  // Always clean up the backup first — this only runs on successful pack.
  try {
    if (context && context.appOutDir) {
      removeBackupDir(context.appOutDir)
    }
  } catch (err) {
    console.warn(`[after-pack] could not remove backup dir (${err.message}); continuing`)
  }

  if (context.electronPlatformName !== 'win32') {
    return
  }

  const productName = context.packager?.appInfo?.productFilename || 'Hermes'
  const exe = path.join(context.appOutDir, `${productName}.exe`)
  const desktopRoot = path.resolve(__dirname, '..')

  try {
    await stampExeIdentity(exe, desktopRoot)
  } catch (err) {
    // Never fail the build over a cosmetic stamp.
    console.warn(`[after-pack] exe identity stamp failed (${err.message}); Hermes.exe keeps the stock Electron icon`)
  }
}
