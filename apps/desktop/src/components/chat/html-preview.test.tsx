import type { SyntaxHighlighterProps } from '@assistant-ui/react-streamdown'
import { fireEvent, render, within } from '@testing-library/react'
import type { ComponentProps } from 'react'
import { describe, expect, it } from 'vitest'

import { HtmlPreview } from './html-preview'

// The component falls back to the shared SyntaxHighlighter, which destructures
// `components.Pre`, so every render path needs a minimal Pre supplied.
function highlighterProps(code: string): SyntaxHighlighterProps {
  return {
    code,
    language: 'html',
    components: { Pre: (props: ComponentProps<'pre'>) => <pre {...props} /> }
  } as unknown as SyntaxHighlighterProps
}

const HTML = '<div id="x">hi there</div>'

describe('HtmlPreview', () => {
  it('renders a sandboxed iframe when the fence is complete', () => {
    const { container } = render(<HtmlPreview {...highlighterProps(HTML)} />)
    const iframe = container.querySelector('iframe')

    expect(iframe).toBeTruthy()
    // SECURITY: scripts allowed, but allow-same-origin must NEVER be present —
    // an opaque origin denies untrusted LLM HTML access to app cookies/storage/DOM.
    expect(iframe?.getAttribute('sandbox')).toBe('allow-scripts')
    expect(iframe?.getAttribute('sandbox')).not.toContain('allow-same-origin')
    expect(iframe?.getAttribute('srcdoc')).toBe(HTML)
  })

  it('falls back to the code card (no iframe) while streaming', () => {
    const { container } = render(<HtmlPreview {...highlighterProps(HTML)} defer />)

    expect(container.querySelector('iframe')).toBeNull()
    expect(container.textContent).toContain('hi there')
  })

  it('falls back (no iframe) for an empty or whitespace-only fence', () => {
    const { container } = render(<HtmlPreview {...highlighterProps('   \n  ')} />)

    expect(container.querySelector('iframe')).toBeNull()
  })

  it('toggles the iframe off for the source view and back on', () => {
    const { container } = render(<HtmlPreview {...highlighterProps(HTML)} />)
    const ui = within(container)
    expect(container.querySelector('iframe')).toBeTruthy()

    // Exact name match avoids colliding with the "Copy code" button. The source
    // view is highlighted asynchronously by Shiki, so we assert on the iframe
    // presence (synchronous) rather than the rendered source text.
    fireEvent.click(ui.getByRole('button', { name: 'Code' }))
    expect(container.querySelector('iframe')).toBeNull()

    fireEvent.click(ui.getByRole('button', { name: 'PREVIEW' }))
    const iframe = container.querySelector('iframe')
    expect(iframe).toBeTruthy()
    expect(iframe?.getAttribute('srcdoc')).toBe(HTML)
  })
})
