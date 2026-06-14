'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')

const desktopPackage = require('../package.json')
const {
  WINDOWS_APP_USER_MODEL_ID,
  registerWindowsAppUserModelId
} = require('./windows-app-id.cjs')

test('Windows app user model id matches the packaged desktop app id', () => {
  assert.equal(WINDOWS_APP_USER_MODEL_ID, desktopPackage.build.appId)
})

test('registers the app user model id on Windows', () => {
  const calls = []
  const registered = registerWindowsAppUserModelId(
    { setAppUserModelId: id => calls.push(id) },
    'win32'
  )

  assert.equal(registered, true)
  assert.deepEqual(calls, [WINDOWS_APP_USER_MODEL_ID])
})

test('does not register the app user model id outside Windows', () => {
  const calls = []
  const registered = registerWindowsAppUserModelId(
    { setAppUserModelId: id => calls.push(id) },
    'darwin'
  )

  assert.equal(registered, false)
  assert.deepEqual(calls, [])
})

test('does not throw when the Electron app lacks the registration API', () => {
  assert.equal(registerWindowsAppUserModelId({}, 'win32'), false)
  assert.equal(registerWindowsAppUserModelId(null, 'win32'), false)
})
