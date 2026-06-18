export interface AudioInputDevice {
  deviceId: string
  groupId: string
  label: string
}

export async function primeMicrophoneDeviceLabels(): Promise<boolean> {
  const permitted = await window.hermesDesktop?.requestMicrophoneAccess?.()

  if (permitted === false || !navigator.mediaDevices?.getUserMedia) {
    return false
  }

  let stream: MediaStream | null = null

  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true })

    return true
  } finally {
    stream?.getTracks().forEach(track => track.stop())
  }
}

export async function listAudioInputDevices(): Promise<AudioInputDevice[]> {
  if (!navigator.mediaDevices?.enumerateDevices) {
    return []
  }

  const devices = await navigator.mediaDevices.enumerateDevices()
  const seen = new Set<string>()
  let index = 0

  return devices
    .filter(device => device.kind === 'audioinput' && device.deviceId !== 'default')
    .filter(device => {
      const key = device.deviceId || `${device.groupId}:${device.label}`

      if (!key || seen.has(key)) {
        return false
      }

      seen.add(key)

      return true
    })
    .map(device => {
      index += 1

      return {
        deviceId: device.deviceId,
        groupId: device.groupId,
        label: device.label || `Microphone ${index}`
      }
    })
}
