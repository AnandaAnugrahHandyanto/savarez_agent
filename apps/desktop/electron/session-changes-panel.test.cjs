'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const appRoot = path.join(__dirname, '..')
const rightSidebar = fs.readFileSync(path.join(appRoot, 'src/app/right-sidebar/index.tsx'), 'utf8')
const changesPanel = fs.readFileSync(path.join(appRoot, 'src/app/right-sidebar/changes.tsx'), 'utf8')
const previewFile = fs.readFileSync(path.join(appRoot, 'src/app/chat/right-rail/preview-file.tsx'), 'utf8')
const hermesClient = fs.readFileSync(path.join(appRoot, 'src/hermes.ts'), 'utf8')
const webServer = fs.readFileSync(path.join(appRoot, '../..', 'hermes_cli/web_server.py'), 'utf8')

test('Desktop Changes tab uses the stored session id, not the transient runtime id', () => {
  assert.match(rightSidebar, /\$selectedStoredSessionId/)
  assert.match(rightSidebar, /\$sessions/)
  assert.match(rightSidebar, /selectedStoredSession\?\.profile \?\? null/)
  assert.match(rightSidebar, /<ChangesPanel profile=\{selectedStoredSession\?\.profile \?\? null\} sessionId=\{selectedStoredSessionId\} \/>/)
  assert.doesNotMatch(rightSidebar, /<ChangesPanel sessionId=\{activeSessionId\} \/>/)
})

test('Desktop Changes tab sends the owning profile with the session-changes request', () => {
  assert.match(changesPanel, /getSessionChanges\(sessionId, profile\)/)
  assert.match(hermesClient, /export function getSessionChanges\(id: string, profile\?: string \| null\)/)
  assert.match(hermesClient, /\.\.\.\(profile \? \{ profile \} : \{\}\)/)
  assert.match(hermesClient, /\/api\/sessions\/\$\{encodeURIComponent\(id\)\}\/changes\$\{suffix\}/)
})

test('Desktop Changes tab opens diffs and full remote files as content tabs', () => {
  assert.match(changesPanel, /setSessionPreviewTarget\(sessionId, diffPreviewTarget\(turn, file\), 'manual', file\.path\)/)
  assert.match(changesPanel, /normalizeOrLocalPreviewTarget\(file\.path, currentCwd \|\| undefined\)/)
  assert.match(changesPanel, /window\.setInterval\(\(\) => void refresh\(\{ quiet: true \}\), 2500\)/)
  assert.match(previewFile, /function DiffPreview/)
  assert.match(previewFile, /target\.previewKind === 'diff'/)
})

test('Workspace preview APIs support explorer and file previews', () => {
  assert.match(webServer, /@app\.get\("\/api\/workspace\/file\/text"\)/)
  assert.match(webServer, /@app\.get\("\/api\/workspace\/fs\/read-dir"\)/)
  assert.match(webServer, /@app\.get\("\/api\/workspace\/preview\/normalize"\)/)
})
