import type * as React from 'react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { PageLoader } from '@/components/page-loader'
import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import {
  createCronJob,
  type CronJob,
  deleteCronJob,
  getCronJobs,
  pauseCronJob,
  resumeCronJob,
  triggerCronJob,
  updateCronJob
} from '@/hermes'
import { AlertTriangle, Clock, Pause, Pencil, Play, Trash2, Zap } from '@/lib/icons'
import { cn } from '@/lib/utils'
import { t, tp, useTranslations } from '@/locales'
import { notify, notifyError } from '@/store/notifications'

import { PageSearchShell } from '../page-search-shell'
import type { SetStatusbarItemGroup } from '../shell/statusbar-controls'

const DEFAULT_DELIVER = 'local'

function getDeliveryOptions(): ReadonlyArray<{ label: string; value: string }> {
  const tc = t().cron
  return [
    { label: tc.thisDesktop, value: 'local' },
    { label: tc.telegram, value: 'telegram' },
    { label: tc.discord, value: 'discord' },
    { label: tc.slack, value: 'slack' },
    { label: tc.email, value: 'email' }
  ]
}

function getScheduleOptions(): ReadonlyArray<ScheduleOption> {
  const tc = t().cron
  return [
    { expr: '0 9 * * *', hint: tc.dailyDesc, label: tc.daily, value: 'daily' },
    { expr: '0 9 * * 1-5', hint: tc.weekdaysDesc, label: tc.weekdays, value: 'weekdays' },
    { expr: '0 9 * * 1', hint: tc.weeklyDesc, label: tc.weekly, value: 'weekly' },
    { expr: '0 9 1 * *', hint: tc.monthlyDesc, label: tc.monthly, value: 'monthly' },
    { expr: '0 * * * *', hint: tc.hourlyDesc, label: tc.hourly, value: 'hourly' },
    { expr: '*/15 * * * *', hint: tc.every15min, label: tc.every15min, value: 'every-15-minutes' },
    { hint: tc.customScheduleDesc, label: tc.customSchedule, value: 'custom' }
  ]
}

const STATE_TONE: Record<string, 'good' | 'muted' | 'warn' | 'bad'> = {
  enabled: 'good',
  scheduled: 'good',
  running: 'good',
  paused: 'warn',
  disabled: 'muted',
  error: 'bad',
  completed: 'muted'
}

const PILL_TONE: Record<'good' | 'muted' | 'warn' | 'bad', string> = {
  good: 'bg-primary/10 text-primary',
  muted: 'bg-muted text-muted-foreground',
  warn: 'bg-amber-500/10 text-amber-600 dark:text-amber-300',
  bad: 'bg-destructive/10 text-destructive'
}

const asText = (value: unknown): string => (typeof value === 'string' ? value : '')

const truncate = (value: string, max = 80): string => (value.length > max ? `${value.slice(0, max)}…` : value)

function jobName(job: CronJob): string {
  return asText(job.name).trim()
}

function jobPrompt(job: CronJob): string {
  return asText(job.prompt)
}

function jobTitle(job: CronJob): string {
  const name = jobName(job)

  if (name) {
    return name
  }

  const prompt = jobPrompt(job)

  if (prompt) {
    return truncate(prompt, 60)
  }

  const script = asText(job.script)

  if (script) {
    return truncate(script, 60)
  }

  return job.id || t().cron.cronJob
}

function jobScheduleDisplay(job: CronJob): string {
  return asText(job.schedule_display) || asText(job.schedule?.display) || asText(job.schedule?.expr) || '—'
}

function jobScheduleExpr(job: CronJob): string {
  return asText(job.schedule?.expr) || asText(job.schedule_display) || ''
}

function jobState(job: CronJob): string {
  return asText(job.state) || (job.enabled === false ? 'disabled' : 'scheduled')
}

function jobDeliver(job: CronJob): string {
  return asText(job.deliver) || DEFAULT_DELIVER
}

function cronParts(expr: string): null | string[] {
  const parts = expr.trim().replace(/\s+/g, ' ').split(' ')

  return parts.length === 5 ? parts : null
}

function dayName(value: string): string {
  const names: Record<string, string> = {
    '0': 'Sunday',
    '1': 'Monday',
    '2': 'Tuesday',
    '3': 'Wednesday',
    '4': 'Thursday',
    '5': 'Friday',
    '6': 'Saturday',
    '7': 'Sunday'
  }

  return names[value] ?? `day ${value}`
}

function formatCronTime(minute: string, hour: string): string {
  const numericHour = Number(hour)
  const numericMinute = Number(minute)

  if (!Number.isInteger(numericHour) || !Number.isInteger(numericMinute)) {
    return `${hour}:${minute}`
  }

  return new Date(2000, 0, 1, numericHour, numericMinute).toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit'
  })
}

function isIntegerToken(value: string): boolean {
  return /^\d+$/.test(value)
}

function scheduleOptionForExpr(expr: string): ScheduleOption {
  const scheduleOptions = getScheduleOptions()
  const normalized = expr.trim().replace(/\s+/g, ' ')
  const exactMatch = scheduleOptions.find(option => option.expr === normalized)

  if (exactMatch) {
    return exactMatch
  }

  const parts = cronParts(normalized)

  if (!parts) {
    return scheduleOptions[scheduleOptions.length - 1]
  }

  const [minute, hour, dayOfMonth, month, dayOfWeek] = parts

  if (dayOfMonth === '*' && month === '*' && dayOfWeek === '*' && isIntegerToken(minute) && isIntegerToken(hour)) {
    return scheduleOptions.find(option => option.value === 'daily') ?? scheduleOptions[0]
  }

  if (dayOfMonth === '*' && month === '*' && dayOfWeek === '1-5' && isIntegerToken(minute) && isIntegerToken(hour)) {
    return scheduleOptions.find(option => option.value === 'weekdays') ?? scheduleOptions[0]
  }

  if (
    dayOfMonth === '*' &&
    month === '*' &&
    isIntegerToken(dayOfWeek) &&
    isIntegerToken(minute) &&
    isIntegerToken(hour)
  ) {
    return scheduleOptions.find(option => option.value === 'weekly') ?? scheduleOptions[0]
  }

  if (
    month === '*' &&
    dayOfWeek === '*' &&
    isIntegerToken(dayOfMonth) &&
    isIntegerToken(minute) &&
    isIntegerToken(hour)
  ) {
    return scheduleOptions.find(option => option.value === 'monthly') ?? scheduleOptions[0]
  }

  if (hour === '*' && dayOfMonth === '*' && month === '*' && dayOfWeek === '*' && isIntegerToken(minute)) {
    return scheduleOptions.find(option => option.value === 'hourly') ?? scheduleOptions[0]
  }

  if (normalized === '*/15 * * * *') {
    return scheduleOptions.find(option => option.value === 'every-15-minutes') ?? scheduleOptions[0]
  }

  return scheduleOptions[scheduleOptions.length - 1]
}

function scheduleSummary(option: ScheduleOption, expr: string): string {
  const parts = cronParts(expr)

  if (!parts) {
    return option.hint
  }

  const [minute, hour, dayOfMonth, , dayOfWeek] = parts

  if (option.value === 'daily') {
    return tp('cron.everyDay', { time: formatCronTime(minute, hour) })
  }

  if (option.value === 'weekdays') {
    return tp('cron.weekdaysAt', { time: formatCronTime(minute, hour) })
  }

  if (option.value === 'weekly') {
    return tp('cron.everyDayOfWeek', { day: dayName(dayOfWeek), time: formatCronTime(minute, hour) })
  }

  if (option.value === 'monthly') {
    return tp('cron.monthlyOnDay', { day: dayOfMonth, time: formatCronTime(minute, hour) })
  }

  if (option.value === 'hourly') {
    return minute === '0' ? t().cron.everyHour : tp('cron.everyHourAt', { min: minute.padStart(2, '0') })
  }

  return option.hint
}

function formatTime(iso?: null | string): string {
  if (!iso) {
    return '—'
  }

  const date = new Date(iso)

  if (Number.isNaN(date.valueOf())) {
    return iso
  }

  return date.toLocaleString()
}

function matchesQuery(job: CronJob, q: string): boolean {
  if (!q) {
    return true
  }

  const needle = q.toLowerCase()

  return [jobTitle(job), jobPrompt(job), jobScheduleDisplay(job), jobScheduleExpr(job), jobDeliver(job)].some(value =>
    value.toLowerCase().includes(needle)
  )
}

interface CronViewProps extends React.ComponentProps<'section'> {
  setStatusbarItemGroup?: SetStatusbarItemGroup
}

export function CronView({ setStatusbarItemGroup: _setStatusbarItemGroup, ...props }: CronViewProps) {
  const { cron: tc, common } = useTranslations()
  const [jobs, setJobs] = useState<CronJob[] | null>(null)
  const [query, setQuery] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [busyJobId, setBusyJobId] = useState<null | string>(null)

  const [editor, setEditor] = useState<EditorState>({ mode: 'closed' })
  const [pendingDelete, setPendingDelete] = useState<CronJob | null>(null)
  const [deleting, setDeleting] = useState(false)

  const refresh = useCallback(async () => {
    setRefreshing(true)

    try {
      const result = await getCronJobs()
      setJobs(result)
    } catch (err) {
      notifyError(err, tc.loadFailed)
    } finally {
      setRefreshing(false)
    }
  }, [tc])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const visibleJobs = useMemo(() => {
    if (!jobs) {
      return []
    }

    return jobs.filter(job => matchesQuery(job, query.trim())).sort((a, b) => jobTitle(a).localeCompare(jobTitle(b)))
  }, [jobs, query])

  const enabledCount = jobs?.filter(job => job.enabled).length ?? 0
  const totalCount = jobs?.length ?? 0

  async function handlePauseResume(job: CronJob) {
    setBusyJobId(job.id)

    try {
      const isPaused = jobState(job) === 'paused'
      const updated = isPaused ? await resumeCronJob(job.id) : await pauseCronJob(job.id)
      setJobs(current => (current ? current.map(row => (row.id === job.id ? updated : row)) : current))
      notify({
        kind: 'success',
        title: isPaused ? tc.resumed : tc.paused,
        message: truncate(jobTitle(job), 60)
      })
    } catch (err) {
      notifyError(err, tc.updateFailed)
    } finally {
      setBusyJobId(null)
    }
  }

  async function handleTrigger(job: CronJob) {
    setBusyJobId(job.id)

    try {
      const updated = await triggerCronJob(job.id)
      setJobs(current => (current ? current.map(row => (row.id === job.id ? updated : row)) : current))
      notify({ kind: 'success', title: tc.triggered, message: truncate(jobTitle(job), 60) })
    } catch (err) {
      notifyError(err, tc.triggerFailed)
    } finally {
      setBusyJobId(null)
    }
  }

  async function handleConfirmDelete() {
    if (!pendingDelete) {
      return
    }

    setDeleting(true)

    try {
      await deleteCronJob(pendingDelete.id)
      setJobs(current => (current ? current.filter(row => row.id !== pendingDelete.id) : current))
      notify({ kind: 'success', title: tc.deleted, message: truncate(jobTitle(pendingDelete), 60) })
      setPendingDelete(null)
    } catch (err) {
      notifyError(err, tc.deleteFailed)
    } finally {
      setDeleting(false)
    }
  }

  async function handleEditorSave(values: EditorValues) {
    if (editor.mode === 'create') {
      const created = await createCronJob({
        prompt: values.prompt,
        schedule: values.schedule,
        name: values.name || undefined,
        deliver: values.deliver || DEFAULT_DELIVER
      })

      setJobs(current => (current ? [...current, created] : [created]))
      notify({ kind: 'success', title: tc.created, message: truncate(jobTitle(created), 60) })
    } else if (editor.mode === 'edit') {
      const updated = await updateCronJob(editor.job.id, {
        prompt: values.prompt,
        schedule: values.schedule,
        name: values.name,
        deliver: values.deliver
      })

      setJobs(current => (current ? current.map(row => (row.id === updated.id ? updated : row)) : current))
      notify({ kind: 'success', title: tc.updated, message: truncate(jobTitle(updated), 60) })
    }

    setEditor({ mode: 'closed' })
  }

  return (
    <PageSearchShell
      {...props}
      filters={
        <div className="flex flex-wrap items-center justify-center gap-2">
          <Button onClick={() => setEditor({ mode: 'create' })} size="sm">
            <Codicon name="add" />
            {tc.newCron}
          </Button>
        </div>
      }
      onSearchChange={setQuery}
      searchPlaceholder={tc.searchPlaceholder}
      searchTrailingAction={
        <Button
          aria-label={refreshing ? tc.refreshingCron : tc.refreshCron}
          className="text-(--ui-text-tertiary) hover:bg-(--chrome-action-hover) hover:text-foreground"
          disabled={refreshing}
          onClick={() => void refresh()}
          size="icon-xs"
          title={refreshing ? tc.refreshingCron : tc.refreshCron}
          type="button"
          variant="ghost"
        >
          <Codicon name="refresh" size="0.875rem" spinning={refreshing} />
        </Button>
      }
      searchValue={query}
    >
      {!jobs ? (
        <PageLoader label={tc.loading} />
      ) : visibleJobs.length === 0 ? (
        <EmptyState
          actionLabel={totalCount === 0 ? tc.createFirst : undefined}
          description={
            totalCount === 0
              ? tc.createDesc
              : tc.broaderSearch
          }
          onAction={totalCount === 0 ? () => setEditor({ mode: 'create' }) : undefined}
          title={totalCount === 0 ? tc.noJobs : tc.noMatches}
        />
      ) : (
        <div className="h-full overflow-y-auto px-4 py-3">
          <div className="divide-y divide-border/40 rounded-lg border border-border/40 bg-background/70">
            {visibleJobs.map(job => (
              <CronJobRow
                busy={busyJobId === job.id}
                job={job}
                key={job.id}
                onDelete={() => setPendingDelete(job)}
                onEdit={() => setEditor({ mode: 'edit', job })}
                onPauseResume={() => void handlePauseResume(job)}
                onTrigger={() => void handleTrigger(job)}
              />
            ))}
          </div>
        </div>
      )}
      <div className="hidden">{totalCount === 0 ? tc.noJobs : `${enabledCount}/${totalCount} ${common.active}`}</div>

      <CronEditorDialog editor={editor} onClose={() => setEditor({ mode: 'closed' })} onSave={handleEditorSave} />

      <Dialog onOpenChange={open => !open && !deleting && setPendingDelete(null)} open={pendingDelete !== null}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{tc.deleteTitle}</DialogTitle>
            <DialogDescription>
              {pendingDelete ? (
                <>
                  {tc.deleteDesc.replace('{title}', truncate(jobTitle(pendingDelete), 60))}
                </>
              ) : null}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button disabled={deleting} onClick={() => setPendingDelete(null)} variant="outline">
              {common.cancel}
            </Button>
            <Button disabled={deleting} onClick={() => void handleConfirmDelete()} variant="destructive">
              {deleting ? tc.deleting : common.delete}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageSearchShell>
  )
}

function CronJobRow({
  busy,
  job,
  onDelete,
  onEdit,
  onPauseResume,
  onTrigger
}: {
  busy: boolean
  job: CronJob
  onDelete: () => void
  onEdit: () => void
  onPauseResume: () => void
  onTrigger: () => void
}) {
  const { cron: tc, common } = useTranslations()
  const state = jobState(job)
  const isPaused = state === 'paused'
  const hasName = Boolean(jobName(job))
  const prompt = jobPrompt(job)
  const deliver = jobDeliver(job)

  return (
    <div className="grid gap-3 px-3 py-2.5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
      <button
        className="min-w-0 cursor-pointer rounded-md text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
        onClick={onEdit}
        type="button"
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className="truncate text-sm font-medium">{jobTitle(job)}</span>
          <StatePill tone={STATE_TONE[state] ?? 'muted'}>{state}</StatePill>
          {deliver && deliver !== DEFAULT_DELIVER && <StatePill tone="muted">{deliver}</StatePill>}
        </div>
        {hasName && prompt && <p className="mt-1 truncate text-xs text-muted-foreground">{truncate(prompt, 120)}</p>}
        <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[0.68rem] text-muted-foreground">
          <span className="inline-flex items-center gap-1 font-mono">
            <Clock className="size-3" />
            {jobScheduleDisplay(job)}
          </span>
          <span>{tc.lastTime.replace('{time}', formatTime(job.last_run_at))}</span>
          <span>{tc.nextTime.replace('{time}', formatTime(job.next_run_at))}</span>
        </div>
        {job.last_error && (
          <p className="mt-1 inline-flex items-start gap-1 text-[0.68rem] text-destructive">
            <AlertTriangle className="mt-px size-3 shrink-0" />
            <span className="line-clamp-2">{job.last_error}</span>
          </p>
        )}
      </button>

      <div className="flex shrink-0 items-center gap-0.5">
        <IconAction
          aria-label={isPaused ? tc.resumeCron : tc.pauseCron}
          disabled={busy}
          onClick={onPauseResume}
          title={isPaused ? tc.resume : tc.pause}
        >
          {isPaused ? <Play className="size-3.5" /> : <Pause className="size-3.5" />}
        </IconAction>
        <IconAction aria-label={tc.triggerNow} disabled={busy} onClick={onTrigger} title={tc.triggerNow}>
          <Zap className="size-3.5" />
        </IconAction>
        <IconAction aria-label={common.edit} onClick={onEdit} title={common.edit}>
          <Pencil className="size-3.5" />
        </IconAction>
        <IconAction
          aria-label={common.delete}
          className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
          onClick={onDelete}
          title={common.delete}
        >
          <Trash2 className="size-3.5" />
        </IconAction>
      </div>
    </div>
  )
}

function IconAction({ children, className, ...props }: Omit<React.ComponentProps<typeof Button>, 'size' | 'variant'>) {
  return (
    <Button
      className={cn('size-7 text-muted-foreground hover:text-foreground', className)}
      size="icon"
      variant="ghost"
      {...props}
    >
      {children}
    </Button>
  )
}

function StatePill({ children, tone }: { children: string; tone: keyof typeof PILL_TONE }) {
  return (
    <span
      className={cn('inline-flex items-center rounded-full px-1.5 py-0.5 text-[0.64rem] capitalize', PILL_TONE[tone])}
    >
      {children}
    </span>
  )
}

function EmptyState({
  actionLabel,
  description,
  onAction,
  title
}: {
  actionLabel?: string
  description: string
  onAction?: () => void
  title: string
}) {
  return (
    <div className="grid h-full place-items-center px-6 py-12 text-center">
      <div className="max-w-sm space-y-2">
        <div className="text-sm font-medium">{title}</div>
        <p className="text-xs text-muted-foreground">{description}</p>
        {actionLabel && onAction && (
          <Button className="mt-2" onClick={onAction} size="sm">
            <Codicon name="add" />
            {actionLabel}
          </Button>
        )}
      </div>
    </div>
  )
}

function CronEditorDialog({
  editor,
  onClose,
  onSave
}: {
  editor: EditorState
  onClose: () => void
  onSave: (values: EditorValues) => Promise<void>
}) {
  const { cron: tc, common } = useTranslations()
  const open = editor.mode !== 'closed'
  const isEdit = editor.mode === 'edit'
  const initial = isEdit ? editor.job : null

  const [name, setName] = useState('')
  const [prompt, setPrompt] = useState('')
  const [schedule, setSchedule] = useState('')
  const [schedulePreset, setSchedulePreset] = useState('daily')
  const [deliver, setDeliver] = useState(DEFAULT_DELIVER)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<null | string>(null)

  useEffect(() => {
    if (!open) {
      return
    }

    setName(initial ? jobName(initial) : '')
    setPrompt(initial ? jobPrompt(initial) : '')
    setSchedule(initial ? jobScheduleExpr(initial) : (getScheduleOptions()[0].expr ?? ''))
    setSchedulePreset(initial ? scheduleOptionForExpr(jobScheduleExpr(initial)).value : 'daily')
    setDeliver(initial ? jobDeliver(initial) : DEFAULT_DELIVER)
    setError(null)
    setSaving(false)
  }, [initial, open])

  const selectedScheduleOption =
    getScheduleOptions().find(candidate => candidate.value === schedulePreset) ?? getScheduleOptions()[0]

  function handleSchedulePresetChange(nextPreset: string) {
    setSchedulePreset(nextPreset)
    setError(null)

    const option = getScheduleOptions().find(candidate => candidate.value === nextPreset)

    if (option?.expr) {
      setSchedule(option.expr)
    } else if (scheduleOptionForExpr(schedule).value !== 'custom') {
      setSchedule('')
    }
  }

  const scheduleHint = scheduleSummary(selectedScheduleOption, schedule)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const trimmedPrompt = prompt.trim()
    const trimmedSchedule = schedule.trim()

    if (!trimmedPrompt || !trimmedSchedule) {
      setError(tc.required)

      return
    }

    setSaving(true)
    setError(null)

    try {
      await onSave({
        deliver,
        name: name.trim(),
        prompt: trimmedPrompt,
        schedule: trimmedSchedule
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : tc.saveFailed)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog onOpenChange={value => !value && !saving && onClose()} open={open}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEdit ? tc.editTitle : tc.newTitle}</DialogTitle>
          <DialogDescription>
            {isEdit ? tc.editDesc : tc.newDesc}
          </DialogDescription>
        </DialogHeader>

        <form className="grid gap-4" onSubmit={handleSubmit}>
          <Field htmlFor="cron-name" label={tc.name} optional>
            <Input
              autoFocus
              id="cron-name"
              onChange={event => setName(event.target.value)}
              placeholder={tc.namePlaceholder}
              value={name}
            />
          </Field>

          <Field htmlFor="cron-prompt" label={tc.prompt}>
            <Textarea
              className="min-h-24 font-mono"
              id="cron-prompt"
              onChange={event => setPrompt(event.target.value)}
              placeholder={tc.promptPlaceholder}
              value={prompt}
            />
          </Field>

          <div className="grid items-start gap-4 sm:grid-cols-2">
            <Field htmlFor="cron-frequency" label={tc.frequency}>
              <Select onValueChange={handleSchedulePresetChange} value={schedulePreset}>
                <SelectTrigger className="h-9 rounded-md" id="cron-frequency">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {getScheduleOptions().map(option => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>

            <Field htmlFor="cron-deliver" label={tc.deliverTo}>
              <Select onValueChange={setDeliver} value={deliver}>
                <SelectTrigger className="h-9 rounded-md" id="cron-deliver">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {getDeliveryOptions().map(option => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          </div>

          {schedulePreset === 'custom' ? (
            <Field htmlFor="cron-schedule" label={tc.customScheduleLabel}>
              <Input
                className="font-mono"
                id="cron-schedule"
                onChange={event => setSchedule(event.target.value)}
                placeholder={tc.customPlaceholder}
                value={schedule}
              />
              <FieldHint>{tc.customHint}</FieldHint>
            </Field>
          ) : (
            <div className="rounded-md border border-border/60 bg-muted/30 px-3 py-2">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <span className="font-medium text-foreground">{scheduleHint}</span>
                <span className="font-mono text-muted-foreground">{schedule}</span>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <DialogFooter>
            <Button disabled={saving} onClick={onClose} type="button" variant="outline">
              {common.cancel}
            </Button>
            <Button disabled={saving} type="submit">
              {saving ? common.saving : isEdit ? tc.saveChanges : tc.createCron}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function Field({
  children,
  htmlFor,
  label,
  optional
}: {
  children: React.ReactNode
  htmlFor: string
  label: string
  optional?: boolean
}) {
  return (
    <div className="grid gap-1.5">
      <label className="flex items-baseline gap-2 text-xs font-medium text-foreground" htmlFor={htmlFor}>
        {label}
        {optional && <span className="text-[0.65rem] font-normal text-muted-foreground">{t().common.optional}</span>}
      </label>
      {children}
    </div>
  )
}

function FieldHint({ children }: { children: React.ReactNode }) {
  return <p className="text-[0.66rem] leading-4 text-muted-foreground">{children}</p>
}

type EditorState = { mode: 'closed' } | { mode: 'create' } | { job: CronJob; mode: 'edit' }

interface EditorValues {
  deliver: string
  name: string
  prompt: string
  schedule: string
}

interface ScheduleOption {
  expr?: string
  hint: string
  label: string
  value: string
}
