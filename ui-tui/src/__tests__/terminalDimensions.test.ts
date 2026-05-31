import { describe, expect, it } from 'vitest'

import {
  DEFAULT_COLUMNS,
  DEFAULT_ROWS,
  MAX_COLUMNS,
  MAX_ROWS,
  safeColumns,
  safeRows,
  safeTerminalSize,
  sanitizeDimension,
  sanitizeTerminalSize
} from '../lib/terminalDimensions.js'

describe('sanitizeDimension', () => {
  it('passes through an in-range value', () => {
    expect(sanitizeDimension(120, 1, MAX_COLUMNS, DEFAULT_COLUMNS)).toBe(120)
  })

  it('floors fractional values', () => {
    expect(sanitizeDimension(80.9, 1, MAX_COLUMNS, DEFAULT_COLUMNS)).toBe(80)
  })

  it('clamps an absurd width to the max, not the fallback', () => {
    expect(sanitizeDimension(131072, 1, MAX_COLUMNS, DEFAULT_COLUMNS)).toBe(MAX_COLUMNS)
  })

  it('falls back when value is zero', () => {
    expect(sanitizeDimension(0, 1, MAX_COLUMNS, DEFAULT_COLUMNS)).toBe(DEFAULT_COLUMNS)
  })

  it('falls back when value is negative', () => {
    expect(sanitizeDimension(-5, 1, MAX_COLUMNS, DEFAULT_COLUMNS)).toBe(DEFAULT_COLUMNS)
  })

  it('falls back on NaN / undefined / non-number', () => {
    expect(sanitizeDimension(NaN, 1, MAX_COLUMNS, DEFAULT_COLUMNS)).toBe(DEFAULT_COLUMNS)
    expect(sanitizeDimension(undefined, 1, MAX_COLUMNS, DEFAULT_COLUMNS)).toBe(DEFAULT_COLUMNS)
    expect(sanitizeDimension('80', 1, MAX_COLUMNS, DEFAULT_COLUMNS)).toBe(DEFAULT_COLUMNS)
    expect(sanitizeDimension(Infinity, 1, MAX_COLUMNS, DEFAULT_COLUMNS)).toBe(DEFAULT_COLUMNS)
  })
})

describe('sanitizeTerminalSize', () => {
  it('sanitizes the WSL 131072x1 report', () => {
    // 131072 cols is absurd → clamp to max; 1 row is a valid (degenerate) TTY → keep.
    expect(sanitizeTerminalSize(131072, 1)).toEqual({ columns: MAX_COLUMNS, rows: 1 })
  })

  it('passes a normal terminal through unchanged', () => {
    expect(sanitizeTerminalSize(120, 40)).toEqual({ columns: 120, rows: 40 })
  })

  it('falls back when both dimensions are missing', () => {
    expect(sanitizeTerminalSize(undefined, undefined)).toEqual({
      columns: DEFAULT_COLUMNS,
      rows: DEFAULT_ROWS
    })
  })

  it('clamps an oversized height', () => {
    expect(sanitizeTerminalSize(80, 99999)).toEqual({ columns: 80, rows: MAX_ROWS })
  })
})

describe('safe terminal dimension readers', () => {
  it('passes through normal dimensions', () => {
    expect(safeColumns({ columns: 120 })).toBe(120)
    expect(safeRows({ rows: 40 })).toBe(40)
  })

  it('uses defaults for missing streams and properties', () => {
    expect(safeColumns(null)).toBe(DEFAULT_COLUMNS)
    expect(safeRows(null)).toBe(DEFAULT_ROWS)
    expect(safeRows({})).toBe(DEFAULT_ROWS)
  })

  it('sanitizes invalid and fractional values', () => {
    expect(safeColumns({ columns: NaN })).toBe(DEFAULT_COLUMNS)
    expect(safeRows({ rows: Infinity })).toBe(DEFAULT_ROWS)
    expect(safeColumns({ columns: -1 })).toBe(DEFAULT_COLUMNS)
    expect(safeColumns({ columns: 90.9 })).toBe(90)
  })

  it('clamps a bogus columns getter on a live stream without patching it', () => {
    let raw = 131072
    const stream: { columns?: number; rows?: number } = {}
    Object.defineProperty(stream, 'columns', { configurable: true, get: () => raw })
    Object.defineProperty(stream, 'rows', { configurable: true, get: () => 1 })
    const descriptor = Object.getOwnPropertyDescriptor(stream, 'columns')

    expect(safeColumns(stream)).toBe(MAX_COLUMNS)
    expect(safeRows(stream)).toBe(1)
    expect(Object.getOwnPropertyDescriptor(stream, 'columns')).toStrictEqual(descriptor)

    // Live resize still propagates through the original getter, clamped.
    raw = 100
    expect(safeColumns(stream)).toBe(100)

    raw = 0
    expect(safeColumns(stream)).toBe(DEFAULT_COLUMNS)
  })

  it('clamps bogus plain-value properties without mutating them', () => {
    const stream: { columns?: number; rows?: number } = { columns: 131072, rows: 99999 }

    expect(safeColumns(stream)).toBe(MAX_COLUMNS)
    expect(safeRows(stream)).toBe(MAX_ROWS)
    expect(stream.columns).toBe(131072)
    expect(stream.rows).toBe(99999)
  })

  it('sanitizes a stream as a dimension pair', () => {
    expect(safeTerminalSize({ columns: 131072, rows: 99999 })).toEqual({
      columns: MAX_COLUMNS,
      rows: MAX_ROWS
    })
  })

  it('does not crash on a non-configurable property', () => {
    const stream: { columns?: number; rows?: number } = {}
    Object.defineProperty(stream, 'columns', { configurable: false, value: 131072 })

    expect(() => safeColumns(stream)).not.toThrow()
    expect(safeColumns(stream)).toBe(MAX_COLUMNS)
  })

  it('falls back when a terminal wrapper throws while reading dimensions', () => {
    const stream = {
      get columns() {
        throw new Error('lol terminal cursed')
      },
      get rows() {
        throw new Error('lol terminal cursed')
      }
    }

    expect(safeColumns(stream)).toBe(DEFAULT_COLUMNS)
    expect(safeRows(stream)).toBe(DEFAULT_ROWS)
  })

  it('sanitizes caller-provided fallbacks', () => {
    expect(safeColumns({ columns: undefined }, NaN)).toBe(1)
    expect(safeColumns({ columns: undefined }, 999999)).toBe(MAX_COLUMNS)
    expect(safeRows({ rows: undefined }, -1)).toBe(1)
  })
})
