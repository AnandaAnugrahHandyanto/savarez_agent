import { atom } from 'nanostores'

import { persistString, storedString } from '@/lib/storage'

const STORAGE_KEY = 'hermes.desktop.microphoneDeviceId'

export const SYSTEM_MICROPHONE_DEVICE_ID = ''

function normalizeDeviceId(deviceId: string | null | undefined): string {
  return typeof deviceId === 'string' ? deviceId.trim() : SYSTEM_MICROPHONE_DEVICE_ID
}

export const $selectedMicrophoneDeviceId = atom(normalizeDeviceId(storedString(STORAGE_KEY)))

$selectedMicrophoneDeviceId.subscribe(deviceId =>
  persistString(STORAGE_KEY, deviceId ? normalizeDeviceId(deviceId) : null)
)

export function setSelectedMicrophoneDeviceId(deviceId: string | null | undefined) {
  $selectedMicrophoneDeviceId.set(normalizeDeviceId(deviceId))
}

export function selectedMicrophoneDeviceId(): string {
  return $selectedMicrophoneDeviceId.get()
}
