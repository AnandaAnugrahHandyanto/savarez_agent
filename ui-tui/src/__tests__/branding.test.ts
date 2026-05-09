import { describe, expect, it } from 'vitest'

import { normalizeSessionPanelCatalogs } from '../components/branding.js'

describe('normalizeSessionPanelCatalogs', () => {
  it('keeps existing skills and tools catalogs', () => {
    expect(
      normalizeSessionPanelCatalogs({
        skills: { writing: ['plan'] },
        tools: { terminal: ['terminal'] }
      })
    ).toEqual({
      skills: { writing: ['plan'] },
      tools: { terminal: ['terminal'] }
    })
  })

  it('treats missing or null catalogs as empty objects', () => {
    expect(normalizeSessionPanelCatalogs({ skills: null, tools: null })).toEqual({
      skills: {},
      tools: {}
    })
    expect(normalizeSessionPanelCatalogs({})).toEqual({ skills: {}, tools: {} })
  })
})
