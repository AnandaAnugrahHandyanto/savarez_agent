'use strict'

const ZOOM_STORAGE_KEY = 'hermes:desktop:zoomLevel'
const ZOOM_STATE_FILE_NAME = 'ui-zoom.json'
const MIN_ZOOM_LEVEL = -9
const MAX_ZOOM_LEVEL = 9
const DEFAULT_ZOOM_LEVEL = 0

function finiteNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function clampZoomLevel(value) {
  const number = finiteNumber(value)
  if (number == null) return DEFAULT_ZOOM_LEVEL
  return Math.min(Math.max(number, MIN_ZOOM_LEVEL), MAX_ZOOM_LEVEL)
}

function zoomLevelToFactor(level) {
  return Math.pow(1.2, clampZoomLevel(level))
}

function zoomFactorToLevel(factor) {
  const number = finiteNumber(factor)
  if (number == null || number <= 0) return DEFAULT_ZOOM_LEVEL
  return clampZoomLevel(Math.log(number) / Math.log(1.2))
}

function normalizeZoomState(raw) {
  if (raw == null) return null

  if (typeof raw === 'number' || typeof raw === 'string') {
    const level = finiteNumber(raw)
    return level == null ? null : serializeZoomState(level)
  }

  if (typeof raw !== 'object') return null

  const level = finiteNumber(raw.level ?? raw.zoomLevel)
  if (level != null) return serializeZoomState(level)

  const factor = finiteNumber(raw.factor ?? raw.zoomFactor)
  if (factor != null && factor > 0) return serializeZoomState(zoomFactorToLevel(factor))

  const percent = finiteNumber(raw.percent ?? raw.zoomPercent)
  if (percent != null && percent > 0) return serializeZoomState(zoomFactorToLevel(percent / 100))

  return null
}

function serializeZoomState(level) {
  const nextLevel = clampZoomLevel(level)
  const factor = zoomLevelToFactor(nextLevel)
  return {
    version: 1,
    level: Number(nextLevel.toFixed(4)),
    factor: Number(factor.toFixed(4)),
    percent: Math.round(factor * 100)
  }
}

function shouldHandleZoomShortcut(input, isMac) {
  if (!input || input.type === 'keyUp') return false

  const mod = isMac ? input.meta : input.control
  if (!mod || input.alt) return false

  const key = String(input.key || '')
  if (key === '0') return !input.shift ? 'reset' : false
  if (key === '-' || key === '_') return 'out'
  if (key === '=' || key === '+') return 'in'

  return false
}

module.exports = {
  DEFAULT_ZOOM_LEVEL,
  MAX_ZOOM_LEVEL,
  MIN_ZOOM_LEVEL,
  ZOOM_STATE_FILE_NAME,
  ZOOM_STORAGE_KEY,
  clampZoomLevel,
  normalizeZoomState,
  serializeZoomState,
  shouldHandleZoomShortcut,
  zoomFactorToLevel,
  zoomLevelToFactor
}
