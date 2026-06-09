import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createCronJob, getCronJobs, listAllProfileSessions, listSessions } from './hermes'

const emptySessionsResponse = {
  limit: 0,
  offset: 0,
  sessions: [],
  total: 0
}

describe('Hermes REST session helpers', () => {
  let api: ReturnType<typeof vi.fn>

  beforeEach(() => {
    api = vi.fn().mockResolvedValue(emptySessionsResponse)
    Object.defineProperty(window, 'hermesDesktop', {
      configurable: true,
      value: { api }
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    Reflect.deleteProperty(window, 'hermesDesktop')
  })

  it('uses a longer timeout for the single-profile session list', async () => {
    await listSessions(50, 1)

    expect(api).toHaveBeenCalledWith(
      expect.objectContaining({
        path: '/api/sessions?limit=50&offset=0&min_messages=1&archived=exclude&order=recent',
        timeoutMs: 60_000
      })
    )
  })

  it('uses a longer timeout for the all-profile session list', async () => {
    await listAllProfileSessions(50, 1)

    expect(api).toHaveBeenCalledWith(
      expect.objectContaining({
        path: '/api/profiles/sessions?limit=50&offset=0&min_messages=1&archived=exclude&order=recent&profile=all',
        timeoutMs: 60_000
      })
    )
  })
})

describe('Hermes REST cron helpers', () => {
  let api: ReturnType<typeof vi.fn>

  beforeEach(() => {
    api = vi.fn().mockResolvedValue([])
    Object.defineProperty(window, 'hermesDesktop', {
      configurable: true,
      value: { api }
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    Reflect.deleteProperty(window, 'hermesDesktop')
  })

  it('scopes the cron job listing to a concrete profile', async () => {
    await getCronJobs('coder')

    expect(api).toHaveBeenCalledWith({ path: '/api/cron/jobs?profile=coder' })
  })

  it('passes profile=all for the unified cron view', async () => {
    await getCronJobs('all')

    expect(api).toHaveBeenCalledWith({ path: '/api/cron/jobs?profile=all' })
  })

  it('omits the profile query when none is given (legacy default)', async () => {
    await getCronJobs()

    expect(api).toHaveBeenCalledWith({ path: '/api/cron/jobs' })
  })

  it('encodes profile names with reserved characters', async () => {
    await getCronJobs('team a/b')

    expect(api).toHaveBeenCalledWith({ path: '/api/cron/jobs?profile=team%20a%2Fb' })
  })

  it('creates a cron job in the given profile', async () => {
    const body = { prompt: 'do thing', schedule: '0 9 * * *' }
    await createCronJob(body, 'coder')

    expect(api).toHaveBeenCalledWith({
      path: '/api/cron/jobs?profile=coder',
      method: 'POST',
      body
    })
  })

  it('creates a cron job without a profile (backend defaults to default)', async () => {
    const body = { prompt: 'do thing', schedule: '0 9 * * *' }
    await createCronJob(body)

    expect(api).toHaveBeenCalledWith({
      path: '/api/cron/jobs',
      method: 'POST',
      body
    })
  })
})
