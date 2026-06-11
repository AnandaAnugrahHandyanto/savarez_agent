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
const fileTools = fs.readFileSync(path.join(appRoot, '../..', 'tools/file_tools.py'), 'utf8')

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

test('Desktop Changes tab avoids hot polling and blocks profile-scoped full-file local fallback', () => {
  assert.match(changesPanel, /window\.addEventListener\('focus', onFocus\)/)
  assert.doesNotMatch(changesPanel, /setInterval\(/)
  assert.match(changesPanel, /const canOpenFullFile = connection\?\.mode === 'local' && \(!profile \|\| profile === 'default'\)/)
  assert.match(changesPanel, /disabled=\{file\.status === 'deleted' \|\| !canOpenFullFile\}/)
  assert.match(changesPanel, /Full-file preview is only available for local sessions\./)
  assert.match(changesPanel, /normalizeOrLocalPreviewTarget\(file\.path, currentCwd \|\| undefined\)/)
})

test('Desktop Changes tab opens diffs as content tabs without reading full files', () => {
  assert.match(changesPanel, /setSessionPreviewTarget\(sessionId, diffPreviewTarget\(turn, file\), 'manual', file\.path\)/)
  assert.match(previewFile, /function DiffPreview/)
  assert.match(previewFile, /target\.previewKind === 'diff'/)
})

test('Workspace preview APIs are root-scoped, guarded, and bounded', () => {
  assert.match(webServer, /def _resolve_workspace_path\(raw_path: str, base_dir: str \| None = None\)/)
  assert.match(webServer, /Path outside workspace root/)
  assert.match(webServer, /get_read_block_error\(str\(candidate\)\)/)
  assert.match(webServer, /handle\.read\(_WORKSPACE_TEXT_PREVIEW_MAX_BYTES \+ 1\)/)
  assert.doesNotMatch(webServer, /target\.read_bytes\(\)\[: _WORKSPACE_TEXT_PREVIEW_MAX_BYTES \+ 1\]/)
  assert.match(webServer, /async def read_workspace_file_text\(path: str, base_dir: Optional\[str\] = None\)/)
  assert.match(webServer, /async def read_workspace_dir\(path: str, base_dir: Optional\[str\] = None\)/)
})

test('write_file tool results do not persist removed old file contents as diffs', () => {
  assert.match(fileTools, /Return no persisted before\/after diff for write_file tool results/)
  assert.match(fileTools, /return ""/)
  assert.doesNotMatch(fileTools, /old_content = target\.read_text/)
  assert.doesNotMatch(fileTools, /difflib\.unified_diff/)
})
