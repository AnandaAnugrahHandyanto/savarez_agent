'use client'

import type { SyntaxHighlighterProps } from '@assistant-ui/react-streamdown'
import { mermaid as mermaidPlugin } from '@streamdown/mermaid'
import { type FC, useEffect, useState } from 'react'

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
import { useTheme } from '@/themes/context'

/**
 * Renders ```mermaid fences as diagrams. Registered per-language via
 * `componentsByLanguage` on StreamdownTextPrimitive — the global
 * `SyntaxHighlighter` override replaces streamdown's built-in code dispatcher
 * (the only place its mermaid plugin is consulted), so a plugins-only setup
 * never renders diagrams; this component is the supported escape hatch.
 *
 * While streaming (`defer`) or when the source fails to parse we fall back to
 * the regular code card, so the user always at least sees the source.
 */
interface MermaidDiagramProps extends SyntaxHighlighterProps {
  defer?: boolean
}

// mermaid.render() requires a document-unique element id per call.
let renderSeq = 0

export const MermaidDiagram: FC<MermaidDiagramProps> = props => {
  const { code, defer = false } = props
  const { t } = useI18n()
  const { renderedMode } = useTheme()
  const [svg, setSvg] = useState('')
  const [failed, setFailed] = useState(false)
  const source = (code ?? '').trim()

  useEffect(() => {
    if (defer || !source) {
      return
    }

    let cancelled = false

    setFailed(false)
    const instance = mermaidPlugin.getMermaid({ theme: renderedMode === 'dark' ? 'dark' : 'default' })

    instance
      .render(`hermes-mermaid-${++renderSeq}`, source)
      .then(({ svg: rendered }) => {
        if (!cancelled) {
          setSvg(rendered)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSvg('')
          setFailed(true)
        }
      })

    return () => {
      cancelled = true
    }
  }, [source, defer, renderedMode])

  if (defer || failed || !source) {
    return <SyntaxHighlighter {...props} defer={defer} />
  }

  // Async render pending: keep showing the source, swap in the diagram when ready.
  if (!svg) {
    return <SyntaxHighlighter {...props} defer />
  }

  return (
    <CodeCard>
      <CodeCardHeader>
        <CodeCardTitle>
          <CodeCardIcon name="graph" />
          {t.assistant.tool.code}
          <CodeCardSubtitle> · mermaid</CodeCardSubtitle>
        </CodeCardTitle>
        <CopyButton
          appearance="inline"
          className="-my-1 -mr-1 h-5 px-1 opacity-55 hover:opacity-100"
          iconClassName="size-2.5"
          label={t.assistant.tool.copyCode}
          showLabel={false}
          text={source}
        />
      </CodeCardHeader>
      <CodeCardBody>
        {/* Mermaid output is sanitized by the library (securityLevel: strict). */}
        <div
          className="flex justify-center overflow-x-auto bg-background p-3 [&_svg]:h-auto [&_svg]:max-w-full"
          dangerouslySetInnerHTML={{ __html: svg }}
          role="img"
        />
      </CodeCardBody>
    </CodeCard>
  )
}
