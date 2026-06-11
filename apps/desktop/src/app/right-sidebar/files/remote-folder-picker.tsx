import { useCallback, useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import { notifyError } from '@/store/notifications'

// The OS-native folder dialog (selectPaths → dialog.showOpenDialog) can only
// browse the *local* machine. When the workspace lives on a remote gateway the
// File Explorer reads the remote filesystem over SSH (hermes:fs:readDir), so the
// folder picker must browse there too — otherwise "change folder" would silently
// offer local directories that the remote agent can't see (#38369). This dialog
// reuses the same remote-aware readDir to navigate and pick a remote directory.

interface RemoteEntry {
  name: string
  path: string
}

// POSIX parent of a remote path (remote hosts are POSIX; the local OS may not
// be, so we never use Node path semantics here).
function parentDir(input: string): string {
  const trimmed = input.replace(/\/+$/, '')
  const idx = trimmed.lastIndexOf('/')

  return idx <= 0 ? '/' : trimmed.slice(0, idx)
}

interface RemoteFolderPickerProps {
  hostLabel: string
  initialPath: string
  onClose: () => void
  onSelect: (path: string) => void
  open: boolean
}

export function RemoteFolderPicker({ hostLabel, initialPath, onClose, onSelect, open }: RemoteFolderPickerProps) {
  const [path, setPath] = useState(initialPath || '/')
  const [dirs, setDirs] = useState<RemoteEntry[]>([])
  const [loading, setLoading] = useState(false)

  const load = useCallback(async (target: string) => {
    setLoading(true)

    try {
      const result = await window.hermesDesktop?.readDir(target)

      if (result?.error) {
        throw new Error(result.error)
      }

      const folders = (result?.entries ?? [])
        .filter(entry => entry.isDirectory)
        .map(entry => ({ name: entry.name, path: entry.path }))
        .sort((a, b) => a.name.localeCompare(b.name))

      setDirs(folders)
      setPath(target)
    } catch (error) {
      notifyError(error, `Could not open ${target}`)
    } finally {
      setLoading(false)
    }
  }, [])

  // (Re)load from the initial path each time the dialog opens.
  useEffect(() => {
    if (open) {
      void load(initialPath || '/')
    }
  }, [open, initialPath, load])

  const atRoot = path === '/' || path === ''

  return (
    <Dialog onOpenChange={next => (next ? undefined : onClose())} open={open}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Open remote folder</DialogTitle>
          <DialogDescription>Browse {hostLabel} over SSH and pick a working directory.</DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-2">
          <Button
            disabled={loading || atRoot}
            onClick={() => void load(parentDir(path))}
            size="xs"
            type="button"
            variant="secondary"
          >
            <Codicon name="arrow-up" size="0.75rem" />
            Up
          </Button>
          <span className="min-w-0 flex-1 truncate font-mono text-[0.6875rem] text-(--ui-text-secondary)" title={path}>
            {path}
          </span>
        </div>

        <div className="max-h-72 min-h-32 overflow-auto rounded border border-(--ui-stroke-secondary)">
          {loading ? (
            <div className="px-3 py-2 text-xs text-muted-foreground">Loading…</div>
          ) : dirs.length === 0 ? (
            <div className="px-3 py-2 text-xs text-muted-foreground">No subfolders here.</div>
          ) : (
            dirs.map(entry => (
              <button
                className={cn(
                  'flex w-full items-center gap-1.5 px-3 py-1.5 text-left text-xs text-(--ui-text-primary)',
                  'hover:bg-(--chrome-action-hover)'
                )}
                key={entry.path}
                onClick={() => void load(entry.path)}
                type="button"
              >
                <Codicon className="shrink-0 text-(--ui-text-tertiary)" name="folder" size="0.875rem" />
                <span className="truncate">{entry.name}</span>
              </button>
            ))
          )}
        </div>

        <DialogFooter>
          <Button onClick={onClose} type="button" variant="text">
            Cancel
          </Button>
          <Button disabled={loading} onClick={() => onSelect(path)} type="button">
            Use this folder
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
