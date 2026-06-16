import { atom } from 'nanostores'

const ZOOM_BASE = 1.2
const MIN_ZOOM_LEVEL = -9
const MAX_ZOOM_LEVEL = 9

export const MIN_ZOOM_PERCENT = 50
export const MAX_ZOOM_PERCENT = 200
export const ZOOM_PERCENT_STEP = 5

const clamp = (n: number, min: number, max: number): number => Math.min(max, Math.max(min, n))

export function clampZoomLevel(value: number): number {
  return clamp(Number.isFinite(value) ? Math.round(value * 100) / 100 : 0, MIN_ZOOM_LEVEL, MAX_ZOOM_LEVEL)
}

export function zoomLevelToPercent(level: number): number {
  return Math.round(Math.pow(ZOOM_BASE, clampZoomLevel(level)) * 100)
}

export function percentToZoomLevel(percent: number): number {
  const clampedPercent = clamp(Number.isFinite(percent) ? percent : 100, MIN_ZOOM_PERCENT, MAX_ZOOM_PERCENT)

  return clampZoomLevel(Math.log(clampedPercent / 100) / Math.log(ZOOM_BASE))
}

export const $zoomLevel = atom<number>(0)

export async function refreshZoomLevel(): Promise<void> {
  if (typeof window === 'undefined') {
    return
  }

  const response = await window.hermesDesktop?.getZoomLevel?.()

  if (response && typeof response.zoomLevel === 'number') {
    $zoomLevel.set(clampZoomLevel(response.zoomLevel))
  }
}

export async function setZoomPercent(percent: number): Promise<void> {
  const zoomLevel = percentToZoomLevel(percent)
  $zoomLevel.set(zoomLevel)

  if (typeof window === 'undefined') {
    return
  }

  const response = await window.hermesDesktop?.setZoomLevel?.({ zoomLevel })

  if (response && typeof response.zoomLevel === 'number') {
    $zoomLevel.set(clampZoomLevel(response.zoomLevel))
  }
}

if (typeof window !== 'undefined') {
  void refreshZoomLevel().catch(() => {
    // The bridge is unavailable in browser-only tests and static previews.
  })

  window.hermesDesktop?.onZoomChanged?.(payload => {
    if (payload && typeof payload.zoomLevel === 'number') {
      $zoomLevel.set(clampZoomLevel(payload.zoomLevel))
    }
  })
}
