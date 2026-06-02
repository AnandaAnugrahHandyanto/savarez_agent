import { type CSSProperties, useState } from 'react'

import { useTranslations } from '@/locales'

import introCopyJsonl from './intro-copy.jsonl?raw'

type IntroCopy = {
  headline: string
  body: string
}

type IntroCopyRecord = IntroCopy & {
  personality: string
}

export type IntroProps = {
  personality?: string
  seed?: number
}

const NEUTRAL_PERSONALITIES = new Set(['', 'default', 'none', 'neutral'])

function normalizeKey(value?: string): string {
  return (value || '').trim().toLowerCase()
}

function titleize(value: string): string {
  return value
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function isIntroCopyRecord(value: unknown): value is IntroCopyRecord {
  if (!value || typeof value !== 'object') {
    return false
  }

  const record = value as Record<string, unknown>

  return (
    typeof record.personality === 'string' &&
    typeof record.headline === 'string' &&
    typeof record.body === 'string' &&
    Boolean(record.personality.trim()) &&
    Boolean(record.headline.trim()) &&
    Boolean(record.body.trim())
  )
}

function parseIntroCopy(raw: string): Record<string, IntroCopy[]> {
  const byPersonality: Record<string, IntroCopy[]> = {}

  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim()

    if (!trimmed) {
      continue
    }

    try {
      const parsed: unknown = JSON.parse(trimmed)

      if (!isIntroCopyRecord(parsed)) {
        continue
      }

      const key = normalizeKey(parsed.personality)
      byPersonality[key] ??= []
      byPersonality[key].push({
        headline: parsed.headline.trim(),
        body: parsed.body.trim()
      })
    } catch {
      // Bad generated copy should not break the whole desktop app.
    }
  }

  return byPersonality
}

const INTRO_COPY_BY_PERSONALITY = parseIntroCopy(introCopyJsonl)

function getFallbackCopy(t: ReturnType<typeof useTranslations>): IntroCopy[] {
  const intro = t.intro
  return [
    { headline: intro.headline1, body: intro.body1 },
    { headline: intro.headline2, body: intro.body2 },
    { headline: intro.headline3, body: intro.body3 },
    { headline: intro.headline4, body: intro.body4 },
    { headline: intro.headline5, body: intro.body5 }
  ]
}

function neutralCopy(t: ReturnType<typeof useTranslations>): IntroCopy[] {
  return INTRO_COPY_BY_PERSONALITY.none || INTRO_COPY_BY_PERSONALITY.default || getFallbackCopy(t)
}

function fallbackCopyForPersonality(personalityKey: string, t: ReturnType<typeof useTranslations>): IntroCopy[] {
  if (NEUTRAL_PERSONALITIES.has(personalityKey)) {
    return neutralCopy(t)
  }

  const label = titleize(personalityKey)
  const intro = t.intro

  return [
    { headline: intro.personalityHeadline1.replace('{label}', label), body: intro.personalityBody1 },
    { headline: intro.personalityHeadline2.replace('{label}', label), body: intro.personalityBody2 },
    { headline: intro.personalityHeadline3.replace('{label}', label), body: intro.personalityBody3 },
    { headline: intro.personalityHeadline4.replace('{label}', label), body: intro.personalityBody4 },
    { headline: intro.personalityHeadline5.replace('{label}', label), body: intro.personalityBody5 }
  ]
}

function pickCopy(copies: IntroCopy[], seed = 0): IntroCopy {
  return copies[Math.abs(seed) % copies.length] || getFallbackCopy(useTranslations())[0]
}

function resolveCopy(personality: string | undefined, seed: number, t: ReturnType<typeof useTranslations>): IntroCopy {
  const personalityKey = normalizeKey(personality)

  const copies = NEUTRAL_PERSONALITIES.has(personalityKey)
    ? INTRO_COPY_BY_PERSONALITY[personalityKey] || neutralCopy(t)
    : INTRO_COPY_BY_PERSONALITY[personalityKey] || fallbackCopyForPersonality(personalityKey, t)

  return pickCopy(copies, seed)
}

export function Intro({ personality, seed }: IntroProps) {
  const [mountSeed] = useState(() => Math.floor(Math.random() * 100000))
  const t = useTranslations()
  const copy = resolveCopy(personality, mountSeed + (seed ?? 0), t)

  return (
    <div
      className="pointer-events-none flex w-full min-w-0 flex-col items-center justify-center px-3 py-6 text-center text-muted-foreground sm:px-6 lg:px-8"
      data-slot="aui_intro"
    >
      <div className="w-full min-w-0">
        <p
          className="fit-text mx-auto mb-3 w-4/5 font-['Collapse'] font-bold uppercase leading-[0.9] tracking-[0.08em] text-midground mix-blend-plus-lighter dark:text-foreground/90"
          style={
            { '--fit-text-line-height': '0.9', '--fit-text-max': '8rem', '--fit-text-min': '2.75rem' } as CSSProperties
          }
        >
          <span>
            <span>HERMES AGENT</span>
          </span>
          <span aria-hidden="true">HERMES AGENT</span>
        </p>

        <p className="m-0 text-center leading-normal tracking-tight">{copy.body}</p>
      </div>
    </div>
  )
}
