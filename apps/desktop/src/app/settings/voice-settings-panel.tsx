import { useStore } from '@nanostores/react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { type AudioStatusResponse, getAudioStatus } from '@/hermes'
import { useI18n } from '@/i18n'
import { type AudioInputDevice, listAudioInputDevices, primeMicrophoneDeviceLabels } from '@/lib/audio-devices'
import { AlertCircle, Check, Globe, Loader2, Mic, Monitor, RefreshCw } from '@/lib/icons'
import { cn } from '@/lib/utils'
import {
  $selectedMicrophoneDeviceId,
  setSelectedMicrophoneDeviceId,
  SYSTEM_MICROPHONE_DEVICE_ID
} from '@/store/microphone'
import { $connection } from '@/store/session'

import { CONTROL_TEXT } from './constants'
import { ListRow, Pill, SectionHeading } from './primitives'

const SYSTEM_SELECT_VALUE = '__system_microphone__'

function providerLabel(provider: string) {
  if (!provider || provider === 'none') {
    return 'None'
  }

  if (provider === 'local') {
    return 'Local'
  }

  return provider
    .split(/[-_]/)
    .filter(Boolean)
    .map(part => part[0]?.toUpperCase() + part.slice(1))
    .join(' ')
}

function selectedDeviceMissing(deviceId: string, devices: AudioInputDevice[]) {
  return Boolean(deviceId) && devices.length > 0 && !devices.some(device => device.deviceId === deviceId)
}

function isMissingAudioStatusEndpoint(error: unknown) {
  const message = error instanceof Error ? error.message : String(error ?? '')

  return /\b404\b/.test(message) && message.includes('/api/audio/status') && message.includes('No such API endpoint')
}

export function VoiceSettingsPanel() {
  const { t } = useI18n()
  const copy = t.settings.voice
  const connection = useStore($connection)
  const selectedDeviceId = useStore($selectedMicrophoneDeviceId)
  const [devices, setDevices] = useState<AudioInputDevice[]>([])
  const [devicesLoading, setDevicesLoading] = useState(false)
  const [deviceError, setDeviceError] = useState<string | null>(null)
  const [audioStatus, setAudioStatus] = useState<AudioStatusResponse | null>(null)
  const [audioStatusLoading, setAudioStatusLoading] = useState(false)
  const [audioStatusError, setAudioStatusError] = useState<string | null>(null)
  const [audioStatusUnsupported, setAudioStatusUnsupported] = useState(false)
  const canEnumerateDevices = Boolean(navigator.mediaDevices?.enumerateDevices)
  const selectedMissing = selectedDeviceMissing(selectedDeviceId, devices)

  const refreshDevices = useCallback(async (requestAccess = false) => {
    if (!navigator.mediaDevices?.enumerateDevices) {
      setDevices([])
      setDeviceError(copy.devicesUnavailable)

      return
    }

    setDevicesLoading(true)
    setDeviceError(null)

    try {
      if (requestAccess) {
        await primeMicrophoneDeviceLabels()
      }

      setDevices(await listAudioInputDevices())
    } catch (error) {
      setDeviceError(error instanceof Error ? error.message : copy.devicesUnavailable)
    } finally {
      setDevicesLoading(false)
    }
  }, [copy.devicesUnavailable])

  const refreshAudioStatus = useCallback(async () => {
    setAudioStatusLoading(true)
    setAudioStatusError(null)
    setAudioStatusUnsupported(false)

    try {
      setAudioStatus(await getAudioStatus())
    } catch (error) {
      setAudioStatus(null)

      if (isMissingAudioStatusEndpoint(error)) {
        setAudioStatusUnsupported(true)

        return
      }

      setAudioStatusError(error instanceof Error ? error.message : copy.statusFailed)
    } finally {
      setAudioStatusLoading(false)
    }
  }, [copy.statusFailed])

  useEffect(() => {
    void refreshDevices(false)

    const mediaDevices = navigator.mediaDevices

    if (!mediaDevices?.addEventListener) {
      return
    }

    const onChange = () => void refreshDevices(false)
    mediaDevices.addEventListener('devicechange', onChange)

    return () => mediaDevices.removeEventListener('devicechange', onChange)
  }, [refreshDevices])

  useEffect(() => {
    void refreshAudioStatus()
  }, [connection?.baseUrl, connection?.mode, connection?.profile, refreshAudioStatus])

  const sttDescription = useMemo(() => {
    if (audioStatusLoading && !audioStatus) {
      return copy.checkingStatus
    }

    if (audioStatusUnsupported) {
      return copy.statusUnsupported
    }

    if (audioStatusError) {
      return copy.statusError(audioStatusError)
    }

    if (!audioStatus) {
      return copy.statusUnavailable
    }

    if (!audioStatus.enabled) {
      return copy.sttDisabled
    }

    const provider = providerLabel(audioStatus.configured_provider)

    if (audioStatus.available) {
      return copy.sttReady(provider)
    }

    if (audioStatus.configured_provider === 'local') {
      const missing = audioStatus.local.missing_packages.join(', ')

      return audioStatus.lazy_installs_allowed
        ? copy.localSttInstallable(missing || 'faster-whisper')
        : copy.localSttMissing(missing || 'faster-whisper')
    }

    return copy.sttUnavailable(provider)
  }, [audioStatus, audioStatusError, audioStatusLoading, audioStatusUnsupported, copy])

  const localPackageSummary = useMemo(() => {
    if (!audioStatus) {
      return null
    }

    const missing = audioStatus.local.missing_packages

    if (missing.length === 0) {
      return copy.localPackagesReady
    }

    if (audioStatus.local.local_command_available) {
      return copy.localCommandAvailable(missing.join(', '))
    }

    return copy.localPackagesMissing(missing.join(', '))
  }, [audioStatus, copy])

  return (
    <div className="mb-6 grid gap-1">
      <SectionHeading icon={Mic} title={copy.title} />

      <ListRow
        action={
          <div className="flex min-w-0 items-center justify-end gap-2">
            <Select
              disabled={!canEnumerateDevices}
              onValueChange={value =>
                setSelectedMicrophoneDeviceId(value === SYSTEM_SELECT_VALUE ? SYSTEM_MICROPHONE_DEVICE_ID : value)
              }
              value={selectedDeviceId || SYSTEM_SELECT_VALUE}
            >
              <SelectTrigger className={cn(CONTROL_TEXT, 'w-full min-w-0 sm:w-72')}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={SYSTEM_SELECT_VALUE}>{copy.systemDefault}</SelectItem>
                {selectedMissing && (
                  <SelectItem disabled value={selectedDeviceId}>
                    {copy.missingDeviceOption}
                  </SelectItem>
                )}
                {devices.map(device => (
                  <SelectItem key={device.deviceId} value={device.deviceId}>
                    {device.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              className="h-8 shrink-0 gap-1.5 px-2.5"
              disabled={devicesLoading || !canEnumerateDevices}
              onClick={() => void refreshDevices(true)}
              size="sm"
              type="button"
              variant="outline"
            >
              {devicesLoading ? <Loader2 className="size-3.5 animate-spin" /> : <RefreshCw className="size-3.5" />}
              <span>{copy.refreshDevices}</span>
            </Button>
          </div>
        }
        description={deviceError ?? copy.microphoneDesc}
        hint={selectedMissing ? copy.selectedDeviceUnavailable : undefined}
        title={copy.microphoneTitle}
        wide
      />

      <ListRow
        action={
          <Pill tone={connection?.mode === 'remote' ? 'primary' : 'muted'}>
            {connection?.mode === 'remote' ? copy.remoteBackend : copy.localBackend}
          </Pill>
        }
        description={
          connection?.mode === 'remote'
            ? copy.remoteBackendDesc(connection.baseUrl || copy.remoteBackend)
            : copy.localBackendDesc
        }
        title={
          <span className="inline-flex items-center gap-1.5">
            {connection?.mode === 'remote' ? <Globe className="size-3.5" /> : <Monitor className="size-3.5" />}
            {copy.backendTitle}
          </span>
        }
      />

      <ListRow
        action={
          <div className="flex items-center justify-end gap-2">
            {audioStatusLoading ? (
              <Loader2 className="size-4 animate-spin text-muted-foreground" />
            ) : audioStatus?.available ? (
              <Check className="size-4 text-emerald-500" />
            ) : audioStatusUnsupported ? (
              <AlertCircle className="size-4 text-muted-foreground" />
            ) : (
              <AlertCircle className="size-4 text-amber-500" />
            )}
            <Button
              className="h-8 px-2.5"
              disabled={audioStatusLoading}
              onClick={() => void refreshAudioStatus()}
              size="sm"
              type="button"
              variant="outline"
            >
              {copy.refreshStatus}
            </Button>
          </div>
        }
        description={sttDescription}
        hint={localPackageSummary ?? undefined}
        title={copy.sttTitle}
      />
    </div>
  )
}
