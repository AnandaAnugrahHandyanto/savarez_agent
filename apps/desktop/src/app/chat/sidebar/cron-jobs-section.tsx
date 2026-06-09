import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { DisclosureCaret } from '@/components/ui/disclosure-caret'
import { SidebarGroup, SidebarGroupContent } from '@/components/ui/sidebar'
import { useI18n } from '@/i18n'
import { cn } from '@/lib/utils'
import type { CronJob } from '@/types/hermes'

import { SidebarPanelLabel } from '../../shell/sidebar-label'

interface SidebarCronJobsSectionProps {
  jobs: CronJob[]
  label: string
  onManageJob: (jobId: string) => void
  /** Open a run session for a job — reserved until jobs carry run session ids. */
  onOpenRun?: (sessionId: string) => void
  onToggle: () => void
  onTriggerJob: (jobId: string) => void
  open: boolean
}

function cronJobTitle(job: CronJob): string {
  return job.name?.trim() || job.prompt?.trim().slice(0, 60) || job.id
}

export function SidebarCronJobsSection({
  jobs,
  label,
  onManageJob,
  onToggle,
  onTriggerJob,
  open
}: SidebarCronJobsSectionProps) {
  const { t } = useI18n()
  const c = t.cron

  return (
    <SidebarGroup className="shrink-0 p-0">
      <div className="group/section flex shrink-0 items-center justify-between pb-1 pt-1.5">
        <button
          className="group/section-label flex w-fit items-center gap-1 bg-transparent text-left leading-none"
          onClick={onToggle}
          type="button"
        >
          <SidebarPanelLabel>{label}</SidebarPanelLabel>
          <span className="text-[0.625rem] leading-none text-(--ui-text-quaternary)">{jobs.length}</span>
          <DisclosureCaret
            className="text-(--ui-text-tertiary) opacity-0 transition group-hover/section-label:opacity-100"
            open={open}
          />
        </button>
      </div>
      {open && (
        <SidebarGroupContent>
          <div className="grid gap-px">
            {jobs.map(job => (
              <div
                className="group relative grid min-h-7 cursor-pointer grid-cols-[minmax(0,1fr)_auto] items-center rounded-md transition-colors duration-100 ease-out hover:bg-(--ui-row-hover-background) hover:transition-none"
                key={job.id}
              >
                <button
                  className="flex min-w-0 items-center gap-1.5 bg-transparent py-1 pl-2 pr-2 text-left"
                  onClick={() => onManageJob(job.id)}
                  title={job.schedule_display || job.schedule?.display || undefined}
                  type="button"
                >
                  <Codicon
                    className={cn('shrink-0', job.enabled ? 'text-(--ui-text-tertiary)' : 'text-(--ui-text-quaternary) opacity-60')}
                    name="clock"
                    size="0.75rem"
                  />
                  <span
                    className={cn(
                      'block truncate text-[0.8125rem] font-normal text-(--ui-text-secondary) group-hover:text-foreground',
                      !job.enabled && 'opacity-60'
                    )}
                  >
                    {cronJobTitle(job)}
                  </span>
                </button>
                <div className="flex items-center justify-end gap-0.5 px-1">
                  <Button
                    aria-label={c.triggerNow}
                    className="size-5 rounded-[4px] bg-transparent text-transparent transition-colors duration-100 hover:bg-(--ui-control-active-background) hover:text-foreground focus-visible:bg-(--ui-control-active-background) focus-visible:text-foreground focus-visible:ring-0 group-hover:text-(--ui-text-tertiary) [&_svg]:size-3!"
                    onClick={() => onTriggerJob(job.id)}
                    size="icon"
                    title={c.triggerNow}
                    variant="ghost"
                  >
                    <Codicon name="play" size="0.75rem" />
                  </Button>
                  <Button
                    aria-label={c.manage}
                    className="size-5 rounded-[4px] bg-transparent text-transparent transition-colors duration-100 hover:bg-(--ui-control-active-background) hover:text-foreground focus-visible:bg-(--ui-control-active-background) focus-visible:text-foreground focus-visible:ring-0 group-hover:text-(--ui-text-tertiary) [&_svg]:size-3!"
                    onClick={() => onManageJob(job.id)}
                    size="icon"
                    title={c.manage}
                    variant="ghost"
                  >
                    <Codicon name="gear" size="0.75rem" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </SidebarGroupContent>
      )}
    </SidebarGroup>
  )
}
