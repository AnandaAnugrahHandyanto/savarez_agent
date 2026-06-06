import { type ComponentProps, useEffect, useRef, useState } from 'react'

import { UrlDialog } from '@/app/chat/composer/url-dialog'
import { CreateProfileDialog } from '@/app/profiles/create-profile-dialog'
import { RenameProfileDialog } from '@/app/profiles/rename-profile-dialog'
import { ClarifyTool } from '@/components/assistant-ui/clarify-tool'
import { PendingToolApproval } from '@/components/assistant-ui/tool-approval'
import type { ToolPart } from '@/components/assistant-ui/tool-fallback-model'
import { ModelPickerDialog } from '@/components/model-picker'
import { ModelVisibilityDialog } from '@/components/model-visibility-dialog'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { completeDesktopBoot, failDesktopBoot } from '@/store/boot'
import { clearClarifyRequest, setClarifyRequest } from '@/store/clarify'
import { setModelVisibilityOpen } from '@/store/model-visibility'
import { clearNotifications, notify, notifyError } from '@/store/notifications'
import {
  clearApprovalRequest,
  clearSecretRequest,
  clearSudoRequest,
  setApprovalRequest,
  setSecretRequest,
  setSudoRequest
} from '@/store/prompts'
import { $activeSessionId } from '@/store/session'
import {
  $updateApply,
  $updateStatus,
  resetUpdateApplyState,
  setUpdateOverlayOpen,
  type UpdateApplyState
} from '@/store/updates'

/**
 * DialogGallery — DEV-ONLY visual harness for auditing every dialog/overlay.
 *
 * Mounted only when `import.meta.env.DEV` (see desktop-controller). Toggle with
 * the secret hotkey Ctrl + Shift + D (same chord on macOS — no Cmd/Option, so
 * it dodges macOS dead-key behavior). Two kinds of entries:
 *   - "overlay" scenarios flip a store atom so the REAL, app-mounted overlay
 *     renders (boot failure, updates, notifications, sudo/secret prompts). The
 *     gallery closes itself so the overlay is visible; reopen with the hotkey.
 *   - "open dialog" scenarios render the component directly with mock props
 *     (confirm, profile create/rename, url, model picker/visibility) or seed an
 *     inline tool store (clarify, approval).
 *
 * Strings are intentionally inline English and NOT i18n'd — this never ships to
 * users, so adding it to every locale would be pure noise.
 */

const CLARIFY_QUESTION = 'Which environment should I deploy to?'
const CLARIFY_CHOICES = ['Production', 'Staging', 'Preview (ephemeral)']

const SAMPLE_COMMITS = [
  { sha: 'a1b2c3d', summary: 'feat: unify dialog buttons on shared Button', author: 'bb', at: Date.now() },
  { sha: 'e4f5g6h', summary: 'fix: boot overlay retry alignment', author: 'bb', at: Date.now() },
  { sha: 'i7j8k9l', summary: 'refactor: notifications use Button variants', author: 'bb', at: Date.now() }
]

const applyState = (partial: Partial<UpdateApplyState>): UpdateApplyState => ({
  applying: false,
  command: null,
  error: null,
  log: [],
  message: '',
  percent: null,
  stage: 'idle',
  ...partial
})

type HostId =
  | 'approval'
  | 'clarifyChoices'
  | 'clarifyFreeform'
  | 'confirmDefault'
  | 'confirmDestructive'
  | 'modelPicker'
  | 'modelVisibility'
  | 'profileCreate'
  | 'profileRename'
  | 'url'

interface OverlayScenario {
  group: string
  id: string
  label: string
  run: () => void
}

interface HostedScenario {
  enter?: () => void
  group: string
  id: HostId
  label: string
}

const noop = () => {}

export function DialogGallery() {
  const [open, setOpen] = useState(false)
  const [hosted, setHosted] = useState<HostId | null>(null)
  const [url, setUrl] = useState('https://')
  const urlRef = useRef<HTMLInputElement>(null)

  const exitHosted = () => {
    clearClarifyRequest()
    clearApprovalRequest()
    setHosted(null)
  }

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const toggle = event.ctrlKey && event.shiftKey && !event.metaKey && !event.altKey && event.code === 'KeyD'

      if (toggle) {
        event.preventDefault()
        event.stopPropagation()

        if (hosted) {
          exitHosted()
        } else {
          setOpen(value => !value)
        }

        return
      }

      if (event.key === 'Escape' && (hosted || open)) {
        if (hosted) {
          exitHosted()
        } else {
          setOpen(false)
        }
      }
    }

    window.addEventListener('keydown', onKeyDown, { capture: true })

    return () => window.removeEventListener('keydown', onKeyDown, { capture: true })
  }, [hosted, open])

  const resetAll = () => {
    completeDesktopBoot()
    setUpdateOverlayOpen(false)
    resetUpdateApplyState()
    $updateStatus.set(null)
    clearNotifications()
    clearSudoRequest()
    clearSecretRequest()
    clearApprovalRequest()
    clearClarifyRequest()
    setModelVisibilityOpen(false)
    setHosted(null)
  }

  const overlays: OverlayScenario[] = [
    {
      group: 'Notifications',
      id: 'notif-info',
      label: 'Info toast',
      run: () => notify({ kind: 'info', title: 'Heads up', message: 'A background task just finished.' })
    },
    {
      group: 'Notifications',
      id: 'notif-success',
      label: 'Success toast',
      run: () => notify({ kind: 'success', title: 'Saved', message: 'Your settings were applied.' })
    },
    {
      group: 'Notifications',
      id: 'notif-warning',
      label: 'Warning toast',
      run: () => notify({ kind: 'warning', title: 'Careful', message: 'This branch is behind origin/main.' })
    },
    {
      group: 'Notifications',
      id: 'notif-error',
      label: 'Error toast (+detail)',
      run: () => notifyError(new Error('Incorrect API key provided: sk-************'), 'Request failed')
    },
    {
      group: 'Notifications',
      id: 'notif-action',
      label: 'Toast with action button',
      run: () =>
        notify({
          action: { label: 'See what’s new', onClick: noop },
          durationMs: 0,
          kind: 'info',
          message: 'A new desktop build is available.',
          title: 'Update ready'
        })
    },
    {
      group: 'Notifications',
      id: 'notif-many',
      label: 'Stack (show more / clear all)',
      run: () => {
        for (let i = 1; i <= 5; i += 1) {
          notify({ id: `dev-many-${i}`, kind: 'info', message: `Sample notification #${i}.` })
        }
      }
    },
    {
      group: 'Errors & recovery',
      id: 'boot-fail',
      label: 'Boot failure overlay',
      run: () => failDesktopBoot('Gateway exited during startup (exit code 1).')
    },
    {
      group: 'Updates',
      id: 'update-available',
      label: 'Update available',
      run: () => {
        resetUpdateApplyState()
        $updateStatus.set({
          behind: 7,
          branch: 'main',
          commits: SAMPLE_COMMITS,
          fetchedAt: Date.now(),
          supported: true,
          targetSha: 'a1b2c3d'
        })
        setUpdateOverlayOpen(true)
      }
    },
    {
      group: 'Updates',
      id: 'update-manual',
      label: 'Update — manual command',
      run: () => {
        $updateApply.set(applyState({ command: 'hermes update', message: 'hermes update', stage: 'manual' }))
        setUpdateOverlayOpen(true)
      }
    },
    {
      group: 'Updates',
      id: 'update-applying',
      label: 'Update — applying',
      run: () => {
        $updateApply.set(applyState({ applying: true, message: 'Pulling latest…', percent: 62, stage: 'pull' }))
        setUpdateOverlayOpen(true)
      }
    },
    {
      group: 'Updates',
      id: 'update-error',
      label: 'Update — error',
      run: () => {
        $updateApply.set(
          applyState({ error: 'apply-failed', message: 'git pull failed: conflict in apps/desktop', stage: 'error' })
        )
        setUpdateOverlayOpen(true)
      }
    },
    {
      group: 'Updates',
      id: 'update-check-failed',
      label: 'Update — check failed',
      run: () => {
        resetUpdateApplyState()
        $updateStatus.set({ error: 'check-failed', fetchedAt: Date.now(), message: 'network unreachable', supported: true })
        setUpdateOverlayOpen(true)
      }
    },
    {
      group: 'Prompts (chat view)',
      id: 'prompt-sudo',
      label: 'Sudo password',
      run: () => setSudoRequest({ requestId: 'dev-sudo', sessionId: $activeSessionId.get() })
    },
    {
      group: 'Prompts (chat view)',
      id: 'prompt-secret',
      label: 'Secret capture',
      run: () =>
        setSecretRequest({
          envVar: 'OPENAI_API_KEY',
          prompt: 'Paste your OpenAI API key to continue.',
          requestId: 'dev-secret',
          sessionId: $activeSessionId.get()
        })
    }
  ]

  const hostedScenarios: HostedScenario[] = [
    { group: 'Confirm', id: 'confirmDefault', label: 'Confirm dialog' },
    { group: 'Confirm', id: 'confirmDestructive', label: 'Confirm — destructive' },
    { group: 'Profiles', id: 'profileCreate', label: 'Create profile' },
    { group: 'Profiles', id: 'profileRename', label: 'Rename profile' },
    { group: 'Composer', id: 'url', label: 'Attach URL' },
    { group: 'Pickers', id: 'modelPicker', label: 'Model picker' },
    { group: 'Pickers', id: 'modelVisibility', label: 'Model visibility' },
    {
      enter: () =>
        setClarifyRequest({
          choices: CLARIFY_CHOICES,
          question: CLARIFY_QUESTION,
          requestId: 'dev-clarify',
          sessionId: $activeSessionId.get()
        }),
      group: 'Inline (tool)',
      id: 'clarifyChoices',
      label: 'Clarify — choices'
    },
    {
      enter: () =>
        setClarifyRequest({
          choices: null,
          question: CLARIFY_QUESTION,
          requestId: 'dev-clarify',
          sessionId: $activeSessionId.get()
        }),
      group: 'Inline (tool)',
      id: 'clarifyFreeform',
      label: 'Clarify — freeform'
    },
    {
      enter: () =>
        setApprovalRequest({
          command: 'rm -rf ./dist',
          description: 'delete the build output directory',
          sessionId: $activeSessionId.get()
        }),
      group: 'Inline (tool)',
      id: 'approval',
      label: 'Tool approval'
    }
  ]

  if (hosted) {
    return <HostedView hosted={hosted} onExit={exitHosted} setUrl={setUrl} url={url} urlRef={urlRef} />
  }

  if (!open) {
    return null
  }

  const overlayGroups = groupBy(overlays, scenario => scenario.group)
  const hostedGroups = groupBy(hostedScenarios, scenario => scenario.group)

  return (
    <div className="fixed inset-0 z-[3000] flex items-start justify-center overflow-y-auto bg-black/40 p-6 backdrop-blur-sm">
      <div className="w-full max-w-2xl rounded-xl border border-border bg-popover shadow-2xl">
        <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-3">
          <div>
            <h2 className="text-sm font-semibold tracking-tight">Dialog gallery</h2>
            <p className="text-[0.6875rem] text-muted-foreground">
              dev only · Ctrl + Shift + D · Esc closes
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            <Button onClick={resetAll} size="xs" variant="text">
              Reset state
            </Button>
            <Button onClick={() => setOpen(false)} size="xs" variant="ghost">
              Close
            </Button>
          </div>
        </div>

        <div className="grid max-h-[70vh] gap-5 overflow-y-auto p-5">
          <Section title="Trigger overlays (gallery closes — reopen with hotkey)">
            {overlayGroups.map(([group, items]) => (
              <ScenarioGroup key={group} title={group}>
                {items.map(scenario => (
                  <Button
                    key={scenario.id}
                    onClick={() => {
                      scenario.run()
                      setOpen(false)
                    }}
                    size="sm"
                    variant="outline"
                  >
                    {scenario.label}
                  </Button>
                ))}
              </ScenarioGroup>
            ))}
          </Section>

          <Section title="Open dialogs (rendered in place)">
            {hostedGroups.map(([group, items]) => (
              <ScenarioGroup key={group} title={group}>
                {items.map(scenario => (
                  <Button
                    key={scenario.id}
                    onClick={() => {
                      scenario.enter?.()
                      setHosted(scenario.id)
                    }}
                    size="sm"
                    variant="outline"
                  >
                    {scenario.label}
                  </Button>
                ))}
              </ScenarioGroup>
            ))}
          </Section>
        </div>
      </div>
    </div>
  )
}

function HostedView({
  hosted,
  onExit,
  setUrl,
  url,
  urlRef
}: {
  hosted: HostId
  onExit: () => void
  setUrl: (value: string) => void
  url: string
  urlRef: React.RefObject<HTMLInputElement | null>
}) {
  switch (hosted) {
    case 'approval':

    case 'clarifyChoices':

    case 'clarifyFreeform':
      return (
        <InlineHost onExit={onExit}>
          {hosted === 'approval' ? <ApprovalPreview /> : <ClarifyPreview choices={hosted === 'clarifyChoices'} />}
        </InlineHost>
      )

    case 'confirmDefault':
      return (
        <ConfirmDialog
          description="This removes the session from the sidebar. You can’t undo this."
          onClose={onExit}
          onConfirm={noop}
          open
          title="Delete session?"
        />
      )

    case 'confirmDestructive':
      return (
        <ConfirmDialog
          confirmLabel="Delete"
          description="The profile and all its local state will be permanently removed."
          destructive
          onClose={onExit}
          onConfirm={noop}
          open
          title="Delete profile?"
        />
      )

    case 'modelPicker':
      return (
        <ModelPickerDialog
          currentModel=""
          currentProvider=""
          onOpenChange={value => !value && onExit()}
          onSelect={onExit}
          open
        />
      )

    case 'modelVisibility':
      return <ModelVisibilityDialog onOpenChange={value => !value && onExit()} onOpenProviders={onExit} open />

    case 'profileCreate':
      return <CreateProfileDialog onClose={onExit} open />

    case 'profileRename':
      return <RenameProfileDialog currentName="default" onClose={onExit} open />

    case 'url':
      return (
        <UrlDialog
          inputRef={urlRef}
          onChange={setUrl}
          onOpenChange={value => !value && onExit()}
          onSubmit={onExit}
          open
          value={url}
        />
      )

    default:
      return null
  }
}

// Wrapper for inline (non-portaled) tool components so they preview centered
// over a backdrop with a "back to gallery" affordance.
function InlineHost({ children, onExit }: { children: React.ReactNode; onExit: () => void }) {
  return (
    <div className="fixed inset-0 z-[3000] flex items-center justify-center bg-black/40 p-6 backdrop-blur-sm">
      <div className="w-full max-w-xl rounded-xl border border-border bg-popover p-4 shadow-2xl">
        <div className="mb-2 flex justify-end">
          <Button onClick={onExit} size="xs" variant="text">
            ← Gallery
          </Button>
        </div>
        {children}
      </div>
    </div>
  )
}

function ClarifyPreview({ choices }: { choices: boolean }) {
  // ClarifyTool consumes assistant-ui ToolCallMessagePartProps; we only need the
  // pending branch (result === undefined), which reads `args` + the clarify
  // store. Cast through unknown to hand it a minimal mock part.
  const part = {
    args: { choices: choices ? CLARIFY_CHOICES : null, question: CLARIFY_QUESTION },
    result: undefined,
    toolCallId: 'dev-clarify',
    toolName: 'clarify',
    type: 'tool-call'
  } as unknown as ComponentProps<typeof ClarifyTool>

  return <ClarifyTool {...part} />
}

function ApprovalPreview() {
  const part: ToolPart = {
    args: {},
    result: undefined,
    toolCallId: 'dev-approval',
    toolName: 'terminal',
    type: 'tool-call'
  }

  return <PendingToolApproval part={part} />
}

function Section({ children, title }: { children: React.ReactNode; title: string }) {
  return (
    <div className="grid gap-2.5">
      <p className="text-[0.625rem] font-semibold uppercase tracking-[0.12em] text-muted-foreground">{title}</p>
      <div className="grid gap-3">{children}</div>
    </div>
  )
}

function ScenarioGroup({ children, title }: { children: React.ReactNode; title: string }) {
  return (
    <div className="grid gap-1.5">
      <p className="text-xs font-medium text-foreground/80">{title}</p>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  )
}

function groupBy<T>(items: T[], key: (item: T) => string): [string, T[]][] {
  const map = new Map<string, T[]>()

  for (const item of items) {
    const group = key(item)
    const list = map.get(group)

    if (list) {
      list.push(item)
    } else {
      map.set(group, [item])
    }
  }

  return [...map.entries()]
}
