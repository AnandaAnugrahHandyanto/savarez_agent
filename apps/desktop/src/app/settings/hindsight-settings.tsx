import { useCallback, useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { getHindsightConfig, saveHindsightConfig } from '@/hermes'
import { Brain, Check, Loader2, Save } from '@/lib/icons'
import { notify, notifyError } from '@/store/notifications'
import type { HindsightConfig, HindsightMode, HindsightRecallBudget } from '@/types/hermes'

import { CONTROL_TEXT } from './constants'
import { LoadingState, Pill, SectionHeading } from './primitives'

const DEFAULT_HINDSIGHT_CONFIG: HindsightConfig = {
  mode: 'cloud',
  api_url: 'https://api.hindsight.vectorize.io',
  bank_id: 'hermes',
  recall_budget: 'mid',
  api_key_set: false
}

const HINDSIGHT_MODES: readonly { label: string; value: HindsightMode }[] = [
  { label: 'Cloud', value: 'cloud' },
  { label: 'Local external', value: 'local_external' },
  { label: 'Local embedded', value: 'local_embedded' }
]

const RECALL_BUDGETS: readonly HindsightRecallBudget[] = ['low', 'mid', 'high']

export function HindsightSettings() {
  const [config, setConfig] = useState<HindsightConfig | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const next = await getHindsightConfig()
      setConfig({ ...DEFAULT_HINDSIGHT_CONFIG, ...next })
    } catch (err) {
      notifyError(err, 'Hindsight settings failed to load')
      setConfig(DEFAULT_HINDSIGHT_CONFIG)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const save = useCallback(async () => {
    if (!config) {
      return
    }

    setSaving(true)

    try {
      await saveHindsightConfig({
        mode: config.mode,
        api_url: config.api_url,
        api_key: apiKey,
        bank_id: config.bank_id,
        recall_budget: config.recall_budget
      })
      setApiKey('')
      notify({ kind: 'success', title: 'Hindsight saved', message: 'Memory provider configuration updated.' })
      await refresh()
    } catch (err) {
      notifyError(err, 'Failed to save Hindsight settings')
    } finally {
      setSaving(false)
    }
  }, [apiKey, config, refresh])

  if (!config) {
    return <LoadingState label="Loading Hindsight settings..." />
  }

  return (
    <section className="rounded-xl bg-background/60 p-4">
      <SectionHeading
        icon={Brain}
        meta={config.api_key_set ? 'API key set' : 'API key not set'}
        title="Configure Hindsight"
      />

      <div className="mt-4 grid gap-4">
        <label className="grid gap-1.5">
          <span className="text-xs font-medium text-muted-foreground">Mode</span>
          <Select
            onValueChange={value => setConfig(c => (c ? { ...c, mode: value as HindsightMode } : c))}
            value={config.mode}
          >
            <SelectTrigger className={CONTROL_TEXT}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {HINDSIGHT_MODES.map(mode => (
                <SelectItem key={mode.value} value={mode.value}>
                  {mode.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>

        <label className="grid gap-1.5">
          <span className="text-xs font-medium text-muted-foreground">API key</span>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              className="min-w-64 flex-1 font-mono"
              onChange={event => setApiKey(event.target.value)}
              placeholder={config.api_key_set ? 'Leave blank to keep current key' : 'Enter Hindsight API key'}
              type="password"
              value={apiKey}
            />
            {config.api_key_set && (
              <Pill tone="primary">
                <Check className="size-3" />
                Set
              </Pill>
            )}
          </div>
        </label>

        <label className="grid gap-1.5">
          <span className="text-xs font-medium text-muted-foreground">API URL</span>
          <Input
            className="font-mono"
            onChange={event => setConfig(c => (c ? { ...c, api_url: event.target.value } : c))}
            value={config.api_url}
          />
        </label>

        <label className="grid gap-1.5">
          <span className="text-xs font-medium text-muted-foreground">Bank ID</span>
          <Input
            className="font-mono"
            onChange={event => setConfig(c => (c ? { ...c, bank_id: event.target.value } : c))}
            value={config.bank_id}
          />
        </label>

        <label className="grid gap-1.5">
          <span className="text-xs font-medium text-muted-foreground">Recall budget</span>
          <Select
            onValueChange={value =>
              setConfig(c => (c ? { ...c, recall_budget: value as HindsightRecallBudget } : c))
            }
            value={config.recall_budget}
          >
            <SelectTrigger className={CONTROL_TEXT}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {RECALL_BUDGETS.map(budget => (
                <SelectItem key={budget} value={budget}>
                  {budget}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>

        <div className="flex justify-end">
          <Button disabled={saving} onClick={() => void save()} size="sm">
            {saving ? <Loader2 className="size-3.5 animate-spin" /> : <Save />}
            Save
          </Button>
        </div>
      </div>
    </section>
  )
}
