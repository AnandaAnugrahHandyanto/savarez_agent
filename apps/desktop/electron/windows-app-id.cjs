'use strict'

const WINDOWS_APP_USER_MODEL_ID = 'com.nousresearch.hermes'

function registerWindowsAppUserModelId(app, platform = process.platform) {
  if (platform !== 'win32') return false
  if (typeof app?.setAppUserModelId !== 'function') return false

  app.setAppUserModelId(WINDOWS_APP_USER_MODEL_ID)
  return true
}

module.exports = {
  WINDOWS_APP_USER_MODEL_ID,
  registerWindowsAppUserModelId
}
