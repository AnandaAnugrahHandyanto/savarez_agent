'use client'

import type { SyntaxHighlighterProps } from '@assistant-ui/react-streamdown'
import { type FC, useState } from 'react'
import ShikiHighlighter from 'react-shiki'

import {
  CodeCard,
  CodeCardBody,
  CodeCardHeader,
  CodeCardIcon,
  CodeCardSubtitle,
  CodeCardTitle
} from '@/components/chat/code-card'
import { SyntaxHighlighter } from '@/components/chat/shiki-highlighter'
import { CopyButton } from '@/components/ui/copy-button'
import { useI18n } from '@/i18n'
import { cn } from '@/lib/utils'

/**
 * Renders ```html fences as a live, Claude-artifacts-style preview. Registered
 * per-language via `componentsByLanguage` on StreamdownTextPrimitive — the
 * global `SyntaxHighlighter` override replaces streamdown's built-in code
 * dispatcher (the only place its plugins are consulted), so a plugins-only
 * setup never runs; this component is the supported escape hatch (same wiring
 * as MermaidDiagram).
 *
 * While streaming (`defer`) or when the fence is empty we fall back to the
 * regular code card, so the user always at least sees the source build up.
 */
interface HtmlPreviewProps extends SyntaxHighlighterProps {
  defer?: boolean
}

// Mirror shiki-highlighter.tsx so the inline "Code" view matches the rest of
// the app (full react-shiki bundle, light-dark() theme follows color-scheme).
const SHIKI_THEME = { dark: 'github-dark-default', light: 'github-light-default' } as const
const SHIKI_COLOR_REPLACEMENTS: Record<string, Record<string, string>> = {
  'github-light-default': { '#6e7781': '#57606a' }
}

export const HtmlPreview: FC<HtmlPreviewProps> = props => {
  const { code, defer = false } = props
  const { t } = useI18n()
  const [showCode, setShowCode] = useState(false)
  const source = (code ?? '').trim()

  // Streaming or empty fence: keep the plain code card so the user watches the
  // markup arrive. We never preview a half-written document.
  if (defer || !source) {
    return <SyntaxHighlighter {...props} defer={defer} />
  }

  return (
    <CodeCard>
      <CodeCardHeader>
        <CodeCardTitle>
          <CodeCardIcon name="code" />
          {t.assistant.tool.code}
          <CodeCardSubtitle> · html</CodeCardSubtitle>
        </CodeCardTitle>
        <div className="flex items-center gap-1">
          <div className="flex items-center rounded-md border border-border p-0.5">
            <button
              aria-pressed={!showCode}
              className={cn(
                'rounded-[0.25rem] px-1.5 py-0.5 text-[0.65rem] font-medium leading-none transition-colors',
                showCode ? 'text-muted-foreground hover:text-foreground' : 'bg-muted text-foreground'
              )}
              onClick={() => setShowCode(false)}
              type="button"
            >
              {t.preview.renderedPreview}
            </button>
            <button
              aria-pressed={showCode}
              className={cn(
                'rounded-[0.25rem] px-1.5 py-0.5 text-[0.65rem] font-medium leading-none transition-colors',
                showCode ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground'
              )}
              onClick={() => setShowCode(true)}
              type="button"
            >
              {t.assistant.tool.code}
            </button>
          </div>
          <CopyButton
            appearance="inline"
            className="-my-1 -mr-1 h-5 px-1 opacity-55 hover:opacity-100"
            iconClassName="size-2.5"
            label={t.assistant.tool.copyCode}
            showLabel={false}
            text={source}
          />
        </div>
      </CodeCardHeader>
      {showCode ? (
        <CodeCardBody>
          <pre className="aui-shiki m-0 overflow-hidden bg-transparent p-0">
            <ShikiHighlighter
              addDefaultStyles={false}
              as="div"
              colorReplacements={SHIKI_COLOR_REPLACEMENTS}
              defaultColor="light-dark()"
              delay={120}
              language="html"
              showLanguage={false}
              theme={SHIKI_THEME}
            >
              {source}
            </ShikiHighlighter>
          </pre>
        </CodeCardBody>
      ) : (
        // SECURITY: `allow-scripts` only — never `allow-same-origin`. The HTML
        // is untrusted LLM output running inside an Electron renderer; keeping
        // the frame in an opaque origin denies it access to app cookies,
        // storage, and the parent DOM. White background since HTML pages
        // assume a white canvas.
        <iframe
          className="block h-[22.5rem] w-full border-0 bg-white"
          sandbox="allow-scripts"
          srcDoc={source}
          title="html-preview"
        />
      )}
    </CodeCard>
  )
}
