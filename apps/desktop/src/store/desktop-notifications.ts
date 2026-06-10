import { atom } from 'nanostores'

import { persistBoolean, storedBoolean } from '@/lib/storage'

const DESKTOP_NOTIFICATIONS_STORAGE_KEY = 'hermes.desktop.notifications.enabled'

/**
 * When true, a native OS notification is fired when the agent completes a
 * response while the window is not focused.  Uses Electron's Notification API
 * via the `hermes:notify` IPC channel (already wired in preload + main).
 */
export const $desktopNotificationsEnabled = atom<boolean>(
  storedBoolean(DESKTOP_NOTIFICATIONS_STORAGE_KEY, true)
)

$desktopNotificationsEnabled.subscribe(value =>
  persistBoolean(DESKTOP_NOTIFICATIONS_STORAGE_KEY, value)
)

export function setDesktopNotificationsEnabled(value: boolean) {
  $desktopNotificationsEnabled.set(value)
}

export function toggleDesktopNotificationsEnabled() {
  $desktopNotificationsEnabled.set(!$desktopNotificationsEnabled.get())
}
