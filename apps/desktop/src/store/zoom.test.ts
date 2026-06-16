import { describe, expect, it } from 'vitest'

import { percentToZoomLevel, zoomLevelToPercent } from './zoom'

describe('desktop zoom store helpers', () => {
  it('round-trips common interface scale percentages', () => {
    expect(zoomLevelToPercent(percentToZoomLevel(100))).toBe(100)
    expect(zoomLevelToPercent(percentToZoomLevel(125))).toBe(125)
    expect(zoomLevelToPercent(percentToZoomLevel(150))).toBe(150)
  })

  it('clamps the settings slider range', () => {
    expect(zoomLevelToPercent(percentToZoomLevel(10))).toBe(50)
    expect(zoomLevelToPercent(percentToZoomLevel(500))).toBe(200)
  })
})
