import type { ReactNode } from 'react'
import { ContextMenu as ContextMenuPrimitive } from 'radix-ui'

import { Codicon } from '@/components/ui/codicon'
import { useI18n } from '@/i18n'

import type { ContextMenuTarget } from './tree'

interface FileTreeContextMenuProps {
  children: ReactNode
  cwd: string
  target: ContextMenuTarget | null
  onOpenChange: (open: boolean) => void
}

export function FileTreeContextMenu({ children, cwd, target, onOpenChange }: FileTreeContextMenuProps) {
  const { t } = useI18n()

  const handleCopyPath = async () => {
    if (!target) {
      return
    }

    await navigator.clipboard.writeText(target.nodeId)
  }

  const handleCopyRelativePath = async () => {
    if (!target) {
      return
    }

    const relative = cwd && target.nodeId.startsWith(cwd)
      ? target.nodeId.slice(cwd.length).replace(/^[/\\]+/, '')
      : target.nodeId

    await navigator.clipboard.writeText(relative)
  }

  return (
    <ContextMenuPrimitive.Root onOpenChange={onOpenChange}>
      <ContextMenuPrimitive.Trigger asChild>
        {children}
      </ContextMenuPrimitive.Trigger>
      <ContextMenuPrimitive.Portal>
        <ContextMenuPrimitive.Content
          className="z-50 min-w-36 rounded-lg border border-(--ui-stroke-secondary) bg-[color-mix(in_srgb,var(--ui-bg-elevated)_96%,transparent)] p-1 text-xs text-popover-foreground shadow-md backdrop-blur-md"
        >
          <ContextMenuPrimitive.Item
            className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1 outline-hidden select-none focus:bg-(--ui-control-active-background) focus:text-foreground"
            onSelect={handleCopyPath}
          >
            <Codicon name="clippy" size="0.75rem" />
            {t.rightSidebar.copyPath}
          </ContextMenuPrimitive.Item>
          <ContextMenuPrimitive.Item
            className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1 outline-hidden select-none focus:bg-(--ui-control-active-background) focus:text-foreground"
            onSelect={handleCopyRelativePath}
          >
            <Codicon name="file-symlink-file" size="0.75rem" />
            {t.rightSidebar.copyRelativePath}
          </ContextMenuPrimitive.Item>
        </ContextMenuPrimitive.Content>
      </ContextMenuPrimitive.Portal>
    </ContextMenuPrimitive.Root>
  )
}
