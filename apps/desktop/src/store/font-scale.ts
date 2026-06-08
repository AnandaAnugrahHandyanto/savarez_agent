import { atom } from 'nanostores'

const FONT_SCALE_KEY = 'hermes.desktop.fontScale'

function loadFontScale(): number {
  if (typeof window === 'undefined') {
    return 1
  }

  try {
    const raw = window.localStorage.getItem(FONT_SCALE_KEY)
    const val = raw ? parseFloat(raw) : 1
    return Number.isFinite(val) && val >= 0.8 && val <= 2 ? val : 1
  } catch {
    return 1
  }
}

export const $fontScale = atom<number>(loadFontScale())

$fontScale.subscribe(scale => {
  if (typeof window === 'undefined') {
    return
  }

  try {
    window.localStorage.setItem(FONT_SCALE_KEY, String(scale))
  } catch {
    // Ignore storage failures.
  }

  document.documentElement.style.setProperty('--dt-font-scale', String(scale))
})

export function setFontScale(scale: number) {
  const clamped = Math.round(Math.max(80, Math.min(200, scale * 100))) / 100
  $fontScale.set(clamped)
}

/** Apply persisted font scale on boot (before React mounts). */
export function applyFontScaleBoot() {
  const scale = loadFontScale()
  if (scale !== 1 && typeof document !== 'undefined') {
    document.documentElement.style.setProperty('--dt-font-scale', String(scale))
  }
}
