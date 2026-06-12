import type * as React from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

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
import { Textarea } from '@/components/ui/textarea'
import {
  createProfile,
  deleteProfile,
  getFleetProfiles,
  getProfileSetupCommand,
  getProfileSoul,
  type FleetProfile,
  renameProfile,
  updateProfileSoul
} from '@/hermes'
import { useI18n } from '@/i18n'
import { AlertTriangle, Pencil, Save, Terminal, Trash2, Users } from '@/lib/icons'
import { cn } from '@/lib/utils'
import { notify, notifyError } from '@/store/notifications'

import { useRefreshHotkey } from '../hooks/use-refresh-hotkey'
import { OverlayView } from '../overlays/overlay-view'
import type { SetStatusbarItemGroup } from '../shell/statusbar-controls'
import { titlebarHeaderBaseClass } from '../shell/titlebar'
import type { SetTitlebarToolGroup } from '../shell/titlebar-controls'

const PROFILE_NAME_RE = /^[a-z0-9][a-z0-9_-]{0,63}$/

function isValidProfileName(name: string): boolean {
  return PROFILE_NAME_RE.test(name.trim())
}

/** Color for a fleet layer badge. */
function layerColor(layer: FleetProfile['layer']): string {
  switch (layer) {
    case 'orchestrator':
      return 'bg-blue-500/15 text-blue-500 border-blue-500/25'
    case 'executor':
      return 'bg-emerald-500/15 text-emerald-500 border-emerald-500/25'
    case 'specialist':
      return 'bg-amber-500/15 text-amber-500 border-amber-500/25'
    default:
      return 'bg-muted text-muted-foreground border-border/40'
  }
}

function layerBadge(layer: FleetProfile['layer']): string | null {
  if (!layer) return null
  return layer
}

function purposeSnippet(purpose: null | string, max = 48): string {
  if (!purpose) return ''
  const trimmed = purpose.trim()
  if (trimmed.length <= max) return trimmed
  return trimmed.slice(0, max) + '…'
}

interface ProfilesViewProps extends React.ComponentProps<'section'> {
  onClose: () => void
  setStatusbarItemGroup?: SetStatusbarItemGroup
  setTitlebarToolGroup?: SetTitlebarToolGroup
}

export function ProfilesView({
  onClose,
  setStatusbarItemGroup: _setStatusbarItemGroup,
  setTitlebarToolGroup,
  ...props
}: ProfilesViewProps) {
  const { t } = useI18n()
  const p = t.profiles
  const [profiles, setFleetProfiles] = useState<null | FleetProfile[]>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [selectedName, setSelectedName] = useState<null | string>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<null | FleetProfile>(null)
  const [deleting, setDeleting] = useState(false)
  const [registryError, setRegistryError] = useState<null | string>(null)

  const refresh = useCallback(async () => {
    setRefreshing(true)

    try {
      const { profiles: list, registry_error } = await getFleetProfiles()
      setFleetProfiles(list)
      setRegistryError(registry_error ?? null)
      setSelectedName(current => {
        if (current && list.some(p => p.name === current)) {
          return current
        }

        return list.find(p => p.is_default)?.name ?? list[0]?.name ?? null
      })
    } catch (err) {
      notifyError(err, p.failedLoad)
    } finally {
      setRefreshing(false)
    }
  }, [p])

  useRefreshHotkey(refresh)

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    if (!setTitlebarToolGroup) {
      return
    }

    setTitlebarToolGroup('profiles', [
      {
        disabled: refreshing,
        icon: <Codicon name="refresh" spinning={refreshing} />,
        id: 'refresh-profiles',
        label: refreshing ? p.refreshing : p.refresh,
        onSelect: () => void refresh()
      }
    ])

    return () => setTitlebarToolGroup('profiles', [])
  }, [p, refresh, refreshing, setTitlebarToolGroup])

  const selected = useMemo(() => {
    if (!profiles) {
      return null
    }

    return profiles.find(p => p.name === selectedName) ?? profiles[0] ?? null
  }, [profiles, selectedName])

  const handleCreate = useCallback(
    async (name: string, cloneFromDefault: boolean) => {
      const trimmed = name.trim()

      if (!isValidProfileName(trimmed)) {
        throw new Error(p.nameHint)
      }

      await createProfile({ name: trimmed, clone_from_default: cloneFromDefault })
      notify({ kind: 'success', title: p.created, message: trimmed })
      setSelectedName(trimmed)
      await refresh()
    },
    [p, refresh]
  )

  const handleRename = useCallback(
    async (from: string, to: string): Promise<void> => {
      const target = to.trim()

      if (target === from) {
        return
      }

      if (!isValidProfileName(target)) {
        throw new Error(p.nameHint)
      }

      await renameProfile(from, target)
      notify({ kind: 'success', title: p.renamed, message: `${from} → ${target}` })
      setSelectedName(target)
      await refresh()
    },
    [p, refresh]
  )

  const handleConfirmDelete = useCallback(async () => {
    if (!pendingDelete) {
      return
    }

    setDeleting(true)

    try {
      await deleteProfile(pendingDelete.name)
      notify({ kind: 'success', title: p.deleted, message: pendingDelete.name })
      setPendingDelete(null)
      setSelectedName(null)
      await refresh()
    } catch (err) {
      notifyError(err, p.failedDelete)
    } finally {
      setDeleting(false)
    }
  }, [p, pendingDelete, refresh])

  return (
    <OverlayView closeLabel={p.close} onClose={onClose}>
      <section {...props} className="flex h-full min-w-0 flex-col overflow-hidden rounded-b-[0.9375rem] bg-background">
        <header className={titlebarHeaderBaseClass}>
          <h2 className="pointer-events-auto text-base font-semibold leading-none tracking-tight">{p.title}</h2>
          <span className="pointer-events-auto text-xs text-muted-foreground">
            {profiles ? p.count(profiles.length) : ''}
          </span>
        </header>

        {registryError && (
          <div className="mx-2 mt-1 flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-600 dark:text-amber-400">
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
            <span>
              Registry error: {registryError} — showing disk-only profiles.
            </span>
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-hidden rounded-b-[1.0625rem] border border-border/50 bg-background/85">
          {!profiles ? (
            <PageLoader label={p.loading} />
          ) : (
            <div className="grid h-full min-h-0 grid-cols-1 lg:grid-cols-[16rem_minmax(0,1fr)]">
              <aside className="flex min-h-0 flex-col overflow-hidden border-b border-border/50 lg:border-b-0 lg:border-r">
                <div className="border-b border-border/40 p-2">
                  <Button className="w-full" onClick={() => setCreateOpen(true)} size="sm">
                    <Codicon name="add" />
                    {p.newProfile}
                  </Button>
                </div>
                <ul className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2">
                  {profiles.map(profile => (
                    <li key={profile.name}>
                      <ProfileRow
                        active={selected?.name === profile.name}
                        onSelect={() => setSelectedName(profile.name)}
                        profile={profile}
                      />
                    </li>
                  ))}
                  {profiles.length === 0 && (
                    <li className="px-2 py-4 text-center text-xs text-muted-foreground">{p.noProfiles}</li>
                  )}
                </ul>
              </aside>

              <main className="min-h-0 overflow-hidden">
                {selected ? (
                  <ProfileDetail
                    key={selected.name}
                    onDelete={() => setPendingDelete(selected)}
                    onRename={newName => handleRename(selected.name, newName)}
                    profile={selected}
                  />
                ) : (
                  <div className="grid h-full place-items-center px-6 py-12 text-center text-sm text-muted-foreground">
                    <div>
                      <Users className="mx-auto size-6 text-muted-foreground/60" />
                      <p className="mt-3">{p.selectPrompt}</p>
                    </div>
                  </div>
                )}
              </main>
            </div>
          )}
        </div>

        <CreateProfileDialog
          onClose={() => setCreateOpen(false)}
          onCreate={async (name, cloneFromDefault) => handleCreate(name, cloneFromDefault)}
          open={createOpen}
        />

        <Dialog onOpenChange={open => !open && !deleting && setPendingDelete(null)} open={pendingDelete !== null}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>{p.deleteTitle}</DialogTitle>
              <DialogDescription>
                {pendingDelete ? (
                  <>
                    {p.deleteDescPrefix}
                    <span className="font-medium text-foreground">{pendingDelete.name}</span>
                    {p.deleteDescMid}
                    <span className="font-mono text-xs">{pendingDelete.path}</span>
                    {p.deleteDescSuffix}
                  </>
                ) : null}
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button disabled={deleting} onClick={() => setPendingDelete(null)} variant="outline">
                {t.common.cancel}
              </Button>
              <Button disabled={deleting} onClick={() => void handleConfirmDelete()} variant="destructive">
                {deleting ? p.deleting : t.common.delete}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </section>
    </OverlayView>
  )
}

function ProfileRow({ active, onSelect, profile }: { active: boolean; onSelect: () => void; profile: FleetProfile }) {
  const { t } = useI18n()
  const p = t.profiles

  return (
    <button
      className={cn(
        'flex w-full flex-col items-start gap-1 rounded-lg px-2.5 py-2 text-left transition-colors',
        active ? 'bg-accent text-foreground' : 'text-foreground/85 hover:bg-accent/60'
      )}
      onClick={onSelect}
      type="button"
    >
      <span className="flex w-full items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 truncate text-sm font-medium">
          {profile.name}
          {profile.provenance === 'orphan' && (
            <span
              className="text-[0.7rem] text-muted-foreground/60"
              title="Not in registry — run fleet_reconcile.py --verify to investigate."
            >
              ↻
            </span>
          )}
        </span>
        <div className="flex shrink-0 items-center gap-1">
          {profile.is_default && <span className="text-[0.6rem] text-primary">{p.default}</span>}
          {profile.layer && (
            <span
              className={cn(
                'rounded-full border px-1.5 py-0.5 text-[0.58rem] font-medium uppercase leading-none tracking-wider',
                layerColor(profile.layer)
              )}
            >
              {layerBadge(profile.layer)}
            </span>
          )}
        </div>
      </span>
      {profile.purpose && (
        <span className="truncate text-[0.63rem] text-muted-foreground/70">
          {purposeSnippet(profile.purpose)}
        </span>
      )}
      <span className="text-[0.66rem] text-muted-foreground">
        {p.skills(profile.skill_count)}
        {profile.has_env ? ` · ${p.env}` : ''}
      </span>
    </button>
  )
}

function ProfileDetail({
  onDelete,
  onRename,
  profile
}: {
  onDelete: () => void
  onRename: (newName: string) => Promise<void>
  profile: FleetProfile
}) {
  const { t } = useI18n()
  const p = t.profiles
  const [renameOpen, setRenameOpen] = useState(false)
  const [copying, setCopying] = useState(false)

  const handleCopySetup = useCallback(async () => {
    setCopying(true)

    try {
      const { command } = await getProfileSetupCommand(profile.name)
      await navigator.clipboard.writeText(command)
      notify({ kind: 'success', title: p.setupCopied, message: command })
    } catch (err) {
      notifyError(err, p.failedCopy)
    } finally {
      setCopying(false)
    }
  }, [p, profile.name])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl space-y-6 px-6 py-6">
          <header className="space-y-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-xl font-semibold tracking-tight">{profile.name}</h3>
                  {profile.is_default && (
                    <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[0.65rem] font-medium text-primary">
                      {p.defaultBadge}
                    </span>
                  )}
                  {profile.has_env && (
                    <span className="rounded-full bg-muted px-2 py-0.5 text-[0.65rem] font-medium text-muted-foreground">
                      .env
                    </span>
                  )}
                  {profile.layer && (
                    <span
                      className={cn(
                        'rounded-full border px-2 py-0.5 text-[0.65rem] font-medium leading-none',
                        layerColor(profile.layer)
                      )}
                    >
                      {profile.layer}
                    </span>
                  )}
                  {profile.provenance === 'orphan' && (
                    <span
                      className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[0.65rem] font-medium text-amber-600 dark:text-amber-400"
                      title="Not in registry — run fleet_reconcile.py --verify to investigate."
                    >
                      ↻ orphan
                    </span>
                  )}
                </div>
                <p className="mt-1 font-mono text-[0.7rem] text-muted-foreground" title={profile.path ?? undefined}>
                  {profile.path ?? '(registry only — not materialized on disk)'}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                {!profile.is_default && (
                  <Button onClick={() => setRenameOpen(true)} size="sm" variant="outline">
                    <Pencil />
                    {p.rename}
                  </Button>
                )}
                <Button disabled={copying} onClick={() => void handleCopySetup()} size="sm" variant="outline">
                  <Terminal />
                  {copying ? p.copying : p.copySetup}
                </Button>
                {!profile.is_default && (
                  <Button
                    className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                    onClick={onDelete}
                    size="sm"
                    variant="ghost"
                  >
                    <Trash2 />
                    {t.common.delete}
                  </Button>
                )}
              </div>
            </div>

            <dl className="grid gap-2 rounded-lg border border-border/40 bg-background/70 px-3 py-3 text-xs sm:grid-cols-2">
              <DetailRow label={p.modelLabel}>
                {profile.model ? (
                  <>
                    <span className="font-mono">{profile.model}</span>
                    {profile.provider && <span className="text-muted-foreground"> · {profile.provider}</span>}
                  </>
                ) : (
                  <span className="text-muted-foreground">{p.notSet}</span>
                )}
              </DetailRow>
              <DetailRow label={p.skillsLabel}>{profile.skill_count}</DetailRow>
            </dl>
          </header>

          {/* Fleet section — only when registry data is available */}
          {profile.provenance !== 'orphan' && (
            <section className="space-y-3">
              <h4 className="text-[0.7rem] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                Fleet
              </h4>
              <dl className="grid gap-2 rounded-lg border border-border/40 bg-background/70 px-3 py-3 text-xs sm:grid-cols-2">
                <DetailRow label="Layer">{profile.layer ?? '—'}</DetailRow>
                <DetailRow label="Domain">{profile.domain ?? '—'}</DetailRow>
                <DetailRow label="Parent">{profile.parent ?? '—'}</DetailRow>
                <DetailRow label="Schedule">
                  {profile.schedule ? (
                    <span className="font-mono">{profile.schedule}</span>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </DetailRow>
                <DetailRow label="Daemon">
                  {profile.daemon === true ? 'Yes' : profile.daemon === false ? 'No' : '—'}
                </DetailRow>
                <DetailRow label="Spawn">{profile.spawn ?? '—'}</DetailRow>
              </dl>

              {profile.boundaries && profile.boundaries.length > 0 && (
                <details className="group rounded-lg border border-border/40 bg-background/70 px-3 py-2">
                  <summary className="cursor-pointer text-[0.65rem] font-semibold uppercase tracking-[0.12em] text-muted-foreground group-open:mb-2">
                    Boundaries ({profile.boundaries.length})
                  </summary>
                  <ul className="space-y-1">
                    {profile.boundaries.map((b, i) => (
                      <li key={i} className="text-xs text-foreground/80">
                        • {b}
                      </li>
                    ))}
                  </ul>
                </details>
              )}

              {profile.escalation && profile.escalation.length > 0 && (
                <details className="group rounded-lg border border-border/40 bg-background/70 px-3 py-2">
                  <summary className="cursor-pointer text-[0.65rem] font-semibold uppercase tracking-[0.12em] text-muted-foreground group-open:mb-2">
                    Escalation ({profile.escalation.length})
                  </summary>
                  <ul className="space-y-1">
                    {profile.escalation.map((e, i) => (
                      <li key={i} className="text-xs text-foreground/80">
                        • {e}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </section>
          )}

          <SoulEditor profileName={profile.name} />
        </div>
      </div>

      <RenameProfileDialog
        currentName={profile.name}
        onClose={() => setRenameOpen(false)}
        onRename={async newName => {
          await onRename(newName)
          setRenameOpen(false)
        }}
        open={renameOpen}
      />
    </div>
  )
}

function DetailRow({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <div className="flex flex-wrap items-baseline gap-2">
      <dt className="text-[0.65rem] font-semibold uppercase tracking-[0.12em] text-muted-foreground">{label}</dt>
      <dd className="text-sm text-foreground">{children}</dd>
    </div>
  )
}

function SoulEditor({ profileName }: { profileName: string }) {
  const { t } = useI18n()
  const p = t.profiles
  const [content, setContent] = useState('')
  const [original, setOriginal] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<null | string>(null)
  const requestRef = useRef<string>(profileName)

  useEffect(() => {
    requestRef.current = profileName
    setLoading(true)
    setError(null)
    setContent('')
    setOriginal('')

    void (async () => {
      try {
        const soul = await getProfileSoul(profileName)

        if (requestRef.current === profileName) {
          setContent(soul.content)
          setOriginal(soul.content)
        }
      } catch (err) {
        if (requestRef.current === profileName) {
          setError(err instanceof Error ? err.message : p.failedLoadSoul)
        }
      } finally {
        if (requestRef.current === profileName) {
          setLoading(false)
        }
      }
    })()
  }, [p, profileName])

  const dirty = content !== original
  const isEmpty = !content.trim()

  async function handleSave() {
    setSaving(true)
    setError(null)

    try {
      await updateProfileSoul(profileName, content)
      setOriginal(content)
      notify({ kind: 'success', title: p.soulSaved, message: profileName })
    } catch (err) {
      setError(err instanceof Error ? err.message : p.failedSaveSoul)
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h4 className="text-[0.7rem] font-semibold uppercase tracking-[0.14em] text-muted-foreground">SOUL.md</h4>
          <p className="text-xs text-muted-foreground">{p.soulDesc}</p>
        </div>
        {dirty && <span className="text-[0.65rem] text-muted-foreground">{p.unsavedChanges}</span>}
      </div>

      {loading ? (
        <div className="grid h-44 place-items-center rounded-md border border-border/40 bg-background/60 text-xs text-muted-foreground">
          {p.loadingSoul}
        </div>
      ) : (
        <Textarea
          className="min-h-72 font-mono text-xs leading-5"
          onChange={event => setContent(event.target.value)}
          placeholder={isEmpty ? p.emptySoul : undefined}
          value={content}
        />
      )}

      {error && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="flex justify-end">
        <Button disabled={!dirty || saving || loading} onClick={() => void handleSave()} size="sm">
          <Save />
          {saving ? p.saving : p.saveSoul}
        </Button>
      </div>
    </section>
  )
}

function CreateProfileDialog({
  onClose,
  onCreate,
  open
}: {
  onClose: () => void
  onCreate: (name: string, cloneFromDefault: boolean) => Promise<void>
  open: boolean
}) {
  const { t } = useI18n()
  const p = t.profiles
  const [name, setName] = useState('')
  const [cloneFromDefault, setCloneFromDefault] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<null | string>(null)

  useEffect(() => {
    if (!open) {
      return
    }

    setName('')
    setCloneFromDefault(true)
    setError(null)
    setSaving(false)
  }, [open])

  const trimmed = name.trim()
  const invalid = trimmed !== '' && !isValidProfileName(trimmed)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()

    if (!trimmed || invalid) {
      setError(invalid ? p.invalidName(p.nameHint) : p.nameRequired)

      return
    }

    setSaving(true)
    setError(null)

    try {
      await onCreate(trimmed, cloneFromDefault)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : p.failedCreate)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog onOpenChange={value => !value && !saving && onClose()} open={open}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{p.newProfile}</DialogTitle>
          <DialogDescription>{p.createDesc}</DialogDescription>
        </DialogHeader>

        <form className="grid gap-4" onSubmit={handleSubmit}>
          <div className="grid gap-1.5">
            <label className="text-xs font-medium" htmlFor="new-profile-name">
              {p.nameLabel}
            </label>
            <Input
              aria-invalid={invalid}
              autoFocus
              id="new-profile-name"
              onChange={event => setName(event.target.value)}
              placeholder="my-profile"
              value={name}
            />
            <p className={cn('text-[0.66rem] leading-4', invalid ? 'text-destructive' : 'text-muted-foreground')}>
              {p.nameHint}
            </p>
          </div>

          <label className="flex cursor-pointer items-center gap-2 rounded-md border border-border/40 bg-background/50 px-3 py-2 text-sm">
            <input
              checked={cloneFromDefault}
              className="size-4 accent-primary"
              onChange={event => setCloneFromDefault(event.target.checked)}
              type="checkbox"
            />
            <span>
              <span className="font-medium">{p.cloneFromDefault}</span>
              <span className="ml-2 text-xs text-muted-foreground">{p.cloneFromDefaultDesc}</span>
            </span>
          </label>

          {error && (
            <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <DialogFooter>
            <Button disabled={saving} onClick={onClose} type="button" variant="outline">
              {t.common.cancel}
            </Button>
            <Button disabled={saving || !trimmed || invalid} type="submit">
              {saving ? p.creating : p.createAction}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function RenameProfileDialog({
  currentName,
  onClose,
  onRename,
  open
}: {
  currentName: string
  onClose: () => void
  onRename: (newName: string) => Promise<void>
  open: boolean
}) {
  const { t } = useI18n()
  const p = t.profiles
  const [name, setName] = useState(currentName)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<null | string>(null)

  useEffect(() => {
    if (!open) {
      return
    }

    setName(currentName)
    setError(null)
    setSaving(false)
  }, [currentName, open])

  const trimmed = name.trim()
  const unchanged = trimmed === currentName
  const invalid = trimmed !== '' && !unchanged && !isValidProfileName(trimmed)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()

    if (unchanged) {
      onClose()

      return
    }

    if (!trimmed || invalid) {
      setError(invalid ? p.invalidName(p.nameHint) : p.nameRequired)

      return
    }

    setSaving(true)
    setError(null)

    try {
      await onRename(trimmed)
    } catch (err) {
      setError(err instanceof Error ? err.message : p.failedRename)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog onOpenChange={value => !value && !saving && onClose()} open={open}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{p.renameTitle}</DialogTitle>
          <DialogDescription>
            {p.renameDescPrefix}
            <span className="font-mono">~/.local/bin</span>
            {p.renameDescSuffix}
          </DialogDescription>
        </DialogHeader>

        <form className="grid gap-3" onSubmit={handleSubmit}>
          <div className="grid gap-1.5">
            <label className="text-xs font-medium" htmlFor="rename-profile-name">
              {p.newNameLabel}
            </label>
            <Input
              aria-invalid={invalid}
              autoFocus
              id="rename-profile-name"
              onChange={event => setName(event.target.value)}
              value={name}
            />
            <p className={cn('text-[0.66rem] leading-4', invalid ? 'text-destructive' : 'text-muted-foreground')}>
              {p.nameHint}
            </p>
          </div>

          {error && (
            <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <DialogFooter>
            <Button disabled={saving} onClick={onClose} type="button" variant="outline">
              {t.common.cancel}
            </Button>
            <Button disabled={saving || invalid || unchanged} type="submit">
              {saving ? p.renaming : p.rename}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
