import { atom, computed } from 'nanostores'

export interface FileChange {
  additions: number
  diff: string
  path: string
  timestamp: number
  toolCallId: string
  toolName: string
}

export interface ToolCallSummary {
  count: number
  errorCount: number
  toolName: string
  totalDuration: number
}

export const $sessionChanges = atom<FileChange[]>([])

export const $sessionChangeSummary = computed($sessionChanges, changes => {
  let totalAdditions = 0
  let totalDeletions = 0
  for (const c of changes) {
    totalAdditions += c.additions
    for (const line of stripAnsi(c.diff).split('\n')) {
      if (line.startsWith('-') && !line.startsWith('---')) totalDeletions++
    }
  }
  return { files: changes.filter(c => c.diff.trim().length > 0).length, totalAdditions, totalDeletions }
})

export const $toolCallSummary = computed($sessionChanges, changes => {
  const byTool = new Map<string, { count: number; totalDuration: number }>()
  for (const c of changes) {
    const existing = byTool.get(c.toolName)
    if (existing) {
      existing.count++
    } else {
      byTool.set(c.toolName, { count: 1, totalDuration: 0 })
    }
  }
  const result: ToolCallSummary[] = []
  for (const [toolName, stats] of byTool) {
    result.push({
      count: stats.count,
      errorCount: 0,
      toolName,
      totalDuration: stats.totalDuration
    })
  }
  return result.sort((a, b) => b.count - a.count)
})

export function addSessionChange(change: FileChange) {
  const current = $sessionChanges.get()
  $sessionChanges.set([...current, change])
}

export function clearSessionChanges() {
  $sessionChanges.set([])
}

export function stripAnsi(str: string): string {
  return str.replace(/\x1B\[[0-9;]*[a-zA-Z]/g, '')
}

export function parseDiffStats(diff: string): { additions: number; deletions: number } {
  const clean = stripAnsi(diff)
  let additions = 0
  let deletions = 0
  for (const line of clean.split('\n')) {
    if (line.startsWith('+') && !line.startsWith('+++')) additions++
    if (line.startsWith('-') && !line.startsWith('---')) deletions++
  }
  return { additions, deletions }
}

export function extractFilePath(diff: string): string {
  const clean = stripAnsi(diff)
  // Standard unified diff header: +++ b/path
  const match = clean.match(/\+\+\+ b\/(.+)/)
  if (match) return match[1]
  // Gateway ANSI-rendered format: "a/path → b/path"
  const match2 = clean.match(/a\/(.+?)\s*→\s*b\/(.+)/)
  if (match2) return match2[2]
  // Hunk header fallback
  const match3 = clean.match(/@@.*@@\s+(.+)/)
  return match3 ? match3[1] : 'unknown file'
}
