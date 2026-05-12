import { describe, expect, it, vi } from 'vitest'

import { handleMouseEvent } from './App.js'

const createApp = () => {
  const props = {
    getHyperlinkAt: vi.fn(),
    onClickAt: vi.fn(),
    onHoverAt: vi.fn(),
    onHyperlinkHover: vi.fn(),
    onMouseDownAt: vi.fn(),
    onMouseDragAt: vi.fn(),
    onMouseUpAt: vi.fn(),
    onMultiClick: vi.fn(),
    onOpenHyperlink: vi.fn(),
    onSelectionChange: vi.fn(),
    onSelectionDrag: vi.fn(),
    selection: { anchor: undefined, focus: undefined, isDragging: false }
  }

  return {
    app: {
      clickCount: 0,
      lastClickCol: 0,
      lastClickRow: 0,
      lastClickTime: 0,
      props
    } as any,
    props
  }
}

describe('handleMouseEvent', () => {
  it('does not dispatch right-button motion as a right-click paste trigger', () => {
    const { app, props } = createApp()

    handleMouseEvent(app, {
      action: 'press',
      button: 34,
      col: 10,
      kind: 'mouse',
      row: 5,
      sequence: '\x1b[<34;10;5M'
    })

    expect(props.onMouseDownAt).not.toHaveBeenCalled()
    expect(props.onSelectionDrag).not.toHaveBeenCalled()
  })

  it('still dispatches actual right-click presses', () => {
    const { app, props } = createApp()

    handleMouseEvent(app, {
      action: 'press',
      button: 2,
      col: 10,
      kind: 'mouse',
      row: 5,
      sequence: '\x1b[<2;10;5M'
    })

    expect(props.onMouseDownAt).toHaveBeenCalledWith(9, 4, 2)
  })

  it('opens links for modified left-click releases encoded as SGR button 3', () => {
    vi.useFakeTimers()
    const { app, props } = createApp()

    props.getHyperlinkAt.mockReturnValue('https://example.com')

    handleMouseEvent(app, {
      action: 'press',
      button: 8,
      col: 10,
      kind: 'mouse',
      row: 5,
      sequence: '\x1b[<8;10;5M'
    })
    handleMouseEvent(app, {
      action: 'release',
      button: 11,
      col: 10,
      kind: 'mouse',
      row: 5,
      sequence: '\x1b[<11;10;5m'
    })

    expect(props.getHyperlinkAt).toHaveBeenCalledWith(9, 4)
    vi.runOnlyPendingTimers()
    expect(props.onOpenHyperlink).toHaveBeenCalledWith('https://example.com')
    vi.useRealTimers()
  })

  it('updates hyperlink hover state on no-button mouse motion', () => {
    const { app, props } = createApp()

    props.getHyperlinkAt.mockReturnValueOnce('https://example.com').mockReturnValueOnce(undefined)

    handleMouseEvent(app, {
      action: 'press',
      button: 35,
      col: 10,
      kind: 'mouse',
      row: 5,
      sequence: '\x1b[<35;10;5M'
    })
    handleMouseEvent(app, {
      action: 'press',
      button: 35,
      col: 11,
      kind: 'mouse',
      row: 5,
      sequence: '\x1b[<35;11;5M'
    })

    expect(props.onHoverAt).toHaveBeenCalledWith(9, 4)
    expect(props.getHyperlinkAt).toHaveBeenNthCalledWith(1, 9, 4)
    expect(props.onHyperlinkHover).toHaveBeenNthCalledWith(1, 'https://example.com')
    expect(props.onHyperlinkHover).toHaveBeenNthCalledWith(2, undefined)
  })
})
