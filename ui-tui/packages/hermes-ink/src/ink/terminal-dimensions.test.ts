import { describe, expect, it } from 'vitest'

import { safeColumns, safeRows, safeTerminalSize } from './terminal-dimensions.js'

describe('Ink terminal dimension readers', () => {
  it('passes through normal dimensions', () => {
    expect(safeColumns({ columns: 120 })).toBe(120)
    expect(safeRows({ rows: 40 })).toBe(40)
  })

  it('clamps absurd host dimensions without mutating stdout', () => {
    const stdout = { columns: 131072, rows: 99999 }

    expect(safeTerminalSize(stdout)).toEqual({ columns: 2000, rows: 1000 })
    expect(stdout).toEqual({ columns: 131072, rows: 99999 })
  })

  it('uses defaults for missing or invalid dimensions', () => {
    expect(safeColumns({ columns: 0 })).toBe(80)
    expect(safeRows({ rows: Number.NaN })).toBe(24)
    expect(safeTerminalSize(null)).toEqual({ columns: 80, rows: 24 })
  })

  it('falls back when a terminal wrapper throws while reading dimensions', () => {
    const stdout = {
      get columns() {
        throw new Error('lol terminal cursed')
      },
      get rows() {
        throw new Error('lol terminal cursed')
      }
    }

    expect(safeColumns(stdout)).toBe(80)
    expect(safeRows(stdout)).toBe(24)
  })

  it('sanitizes caller-provided fallbacks', () => {
    expect(safeColumns({ columns: undefined }, Number.NaN)).toBe(1)
    expect(safeColumns({ columns: undefined }, 999999)).toBe(2000)
    expect(safeRows({ rows: undefined }, -1)).toBe(1)
  })
})
