import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.fn()
const desktopWindow = window as unknown as { hermesDesktop?: { api: typeof api } }

const boardsResponse = {
  boards: [
    {
      counts: { blocked: 0, done: 7, review: 2, running: 2, todo: 5 },
      description: 'PackShop board',
      name: 'PackShop',
      slug: 'packshop',
      total_tasks: 16
    }
  ]
}

const tasksResponse = {
  board: { name: 'PackShop', slug: 'packshop' },
  counts: { blocked: 0, done: 7, review: 2, running: 2, todo: 5 },
  tasks: [
    {
      id: 't_f581c744',
      title: 'implement portrait HUD polish',
      status: 'running',
      progress: 68,
      recent_events: [{ kind: 'heartbeat', message: 'stale lock reclaimed' }],
      updated_at: 1_716_000_000
    },
    { id: 't_46587107', title: 'implement polished shop scene props', status: 'running', progress: 51 },
    { id: 't_f39be40b', title: 'status/progress wiring', status: 'todo' },
    { id: 't_blocked1', title: 'blocked worker handoff', status: 'blocked' },
    { id: 't_63ed18c0', title: 'reviewer QA', status: 'review' },
    { id: 't_done0001', title: 'graybox scene pass', status: 'done', completed_at: 1_716_000_100 }
  ]
}

beforeEach(() => {
  api.mockImplementation(({ path }: { path: string }) => {
    if (path === '/api/kanban/boards') {
      return Promise.resolve(boardsResponse)
    }
    if (path === '/api/kanban/tasks?board=packshop') {
      return Promise.resolve(tasksResponse)
    }
    throw new Error(`Unexpected path: ${path}`)
  })
  desktopWindow.hermesDesktop = { api }
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  delete desktopWindow.hermesDesktop
})

async function renderKanbanViewer() {
  const { KanbanView, KanbanBoardIcon } = await import('./index')

  return {
    KanbanBoardIcon,
    ...render(
      <MemoryRouter initialEntries={['/kanban']}>
        <KanbanView />
      </MemoryRouter>
    )
  }
}

describe('KanbanView', () => {
  it('loads the selected board and renders native quiet columns with task rows', async () => {
    await renderKanbanViewer()

    expect(await screen.findByRole('heading', { name: 'Kanban Viewer' })).toBeTruthy()
    expect(screen.getByRole('combobox', { name: 'Board' }).textContent).toContain('PackShop')
    expect(screen.getByText('Done: 7')).toBeTruthy()
    expect(screen.getByText('Running: 2')).toBeTruthy()
    expect(screen.getByText('Todo: 5')).toBeTruthy()
    expect(screen.getByText('Blocked: 0')).toBeTruthy()
    expect(screen.getByPlaceholderText('Filter tasks…')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Refresh kanban board' })).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Dispatch kanban workers unavailable in viewer' }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByRole('button', { name: 'Toggle compact kanban density' })).toBeTruthy()

    for (const column of ['Todo', 'Running', 'Review', 'Done']) {
      expect(screen.getByRole('region', { name: `${column} tasks` })).toBeTruthy()
    }

    expect(screen.getAllByText('t_f581c744').length).toBeGreaterThan(0)
    expect(screen.getAllByText('implement portrait HUD polish').length).toBeGreaterThan(0)
    expect(screen.getAllByText('stale lock reclaimed').length).toBeGreaterThan(0)
    expect(screen.getByText('blocked worker handoff')).toBeTruthy()
    expect(screen.getByText('68%')).toBeTruthy()
  })

  it('filters rows without changing the native sidebars or route shell', async () => {
    await renderKanbanViewer()
    await screen.findAllByText('implement portrait HUD polish')

    fireEvent.change(await screen.findByPlaceholderText('Filter tasks…'), { target: { value: 'HUD' } })

    expect(screen.getAllByText('implement portrait HUD polish').length).toBeGreaterThan(0)
    expect(screen.queryByText('implement polished shop scene props')).toBeNull()
    expect(screen.queryByText('status/progress wiring')).toBeNull()
  })

  it('keeps the selected-task inspector integrated in the workspace', async () => {
    await renderKanbanViewer()

    fireEvent.click((await screen.findAllByText('implement portrait HUD polish'))[0])

    const inspector = await screen.findByRole('complementary', { name: 'Selected task inspector' })
    expect(inspector.textContent).toContain('t_f581c744')
    expect(inspector.textContent).toContain('implement portrait HUD polish')
    expect(inspector.textContent).toContain('running')
    expect(inspector.textContent).toContain('HUD overlay compile · 68%')
  })

  it('renders the generated tab icon as currentColor-only SVG for every color mode', async () => {
    const { KanbanBoardIcon } = await renderKanbanViewer()
    const { container } = render(<KanbanBoardIcon data-testid="kanban-icon" />)
    const icon = screen.getByTestId('kanban-icon')

    expect(icon.getAttribute('viewBox')).toBe('0 0 16 16')
    expect(container.querySelectorAll('[stroke="currentColor"], [fill="currentColor"]').length).toBeGreaterThan(0)
    expect(container.innerHTML).not.toMatch(/#[0-9a-f]{3,8}/i)
  })

  it('refreshes the current board payload without switching boards', async () => {
    await renderKanbanViewer()

    fireEvent.click(await screen.findByRole('button', { name: 'Refresh kanban board' }))

    await waitFor(() => expect(api).toHaveBeenCalledWith({ path: '/api/kanban/tasks?board=packshop' }))
  })
})
