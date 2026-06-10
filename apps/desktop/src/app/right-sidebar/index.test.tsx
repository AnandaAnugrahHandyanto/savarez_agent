import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { getPaneStateSnapshot, setPaneOpen } from '@/store/panes'
import { clearSessionPreviewRegistry } from '@/store/preview'
import { $activeSessionId, $currentCwd } from '@/store/session'

import { RightSidebarPane } from './index'

vi.mock('@/lib/local-preview', () => ({
  normalizeOrLocalPreviewTarget: vi.fn(async (path: string) => ({
    kind: 'file',
    language: 'markdown',
    previewKind: 'text',
    source: path,
    title: 'README.md',
    url: path
  }))
}))

vi.mock('./files/use-project-tree', () => ({
  useProjectTree: () => ({
    collapseAll: vi.fn(),
    collapseNonce: 0,
    data: [{ id: '/project/README.md', name: 'README.md', isDirectory: false }],
    loadChildren: vi.fn(),
    openState: {},
    refreshRoot: vi.fn(),
    rootError: null,
    rootLoading: false,
    setNodeOpen: vi.fn()
  })
}))

class ResizeObserverMock {
  private callback: ResizeObserverCallback

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback
  }

  observe(target: Element) {
    this.callback([{ target, contentRect: { height: 300, width: 400 } } as ResizeObserverEntry], this)
  }

  disconnect() {}
  unobserve() {}
}

describe('RightSidebarPane preview actions', () => {
  const originalResizeObserver = window.ResizeObserver
  const originalGetBoundingClientRect = Element.prototype.getBoundingClientRect

  beforeEach(() => {
    window.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver
    Element.prototype.getBoundingClientRect = vi.fn(() => ({
      bottom: 300,
      height: 300,
      left: 0,
      right: 400,
      top: 0,
      width: 400,
      x: 0,
      y: 0,
      toJSON: () => ({})
    }))
    $activeSessionId.set('session-1')
    $currentCwd.set('/project')
    clearSessionPreviewRegistry()
    setPaneOpen('preview', false)
  })

  afterEach(() => {
    cleanup()
    window.ResizeObserver = originalResizeObserver
    Element.prototype.getBoundingClientRect = originalGetBoundingClientRect
    $activeSessionId.set(null)
    $currentCwd.set('')
    clearSessionPreviewRegistry()
  })

  it('opens the preview pane when a file is previewed from the file tree', async () => {
    render(
      <RightSidebarPane onActivateFile={vi.fn()} onActivateFolder={vi.fn()} onChangeCwd={vi.fn()} />
    )

    fireEvent.doubleClick(await screen.findByText('README.md'))

    await waitFor(() => expect(getPaneStateSnapshot('preview')?.open).toBe(true))
  })
})
