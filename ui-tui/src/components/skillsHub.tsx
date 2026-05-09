import { Box, Text, useInput, useStdout } from '@hermes/ink'
import { useEffect, useMemo, useState } from 'react'

import type { GatewayClient } from '../gatewayClient.js'
import { rpcErrorMessage } from '../lib/rpc.js'
import { handleSearchInput, useIndexedFuzzyList } from '../lib/searchableList.js'
import type { Theme } from '../theme.js'

import { OverlayHint, useOverlayKeys, windowItems, windowOffset } from './overlayControls.js'

const VISIBLE = 12
const MIN_WIDTH = 40
const MAX_WIDTH = 90
const LABEL_SEARCH_KEYS = ['label'] as const

interface IndexedLabel {
  index: number
  label: string
}

export function SkillsHub({ gw, onClose, t }: SkillsHubProps) {
  const [skillsByCat, setSkillsByCat] = useState<Record<string, string[]>>({})
  const [selectedCat, setSelectedCat] = useState('')
  const [catIdx, setCatIdx] = useState(0)
  const [skillIdx, setSkillIdx] = useState(0)
  const [stage, setStage] = useState<'actions' | 'category' | 'skill'>('category')
  const [info, setInfo] = useState<null | SkillInfo>(null)
  const [installing, setInstalling] = useState(false)
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(true)
  const [catQuery, setCatQuery] = useState('')
  const [skillQuery, setSkillQuery] = useState('')
  const [searchStage, setSearchStage] = useState<null | 'category' | 'skill'>(null)

  const { stdout } = useStdout()
  const width = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, (stdout?.columns ?? 80) - 6))

  useEffect(() => {
    gw.request<{ skills?: Record<string, string[]> }>('skills.manage', { action: 'list' })
      .then(r => {
        setSkillsByCat(r?.skills ?? {})
        setErr('')
        setLoading(false)
      })
      .catch((e: unknown) => {
        setErr(rpcErrorMessage(e))
        setLoading(false)
      })
  }, [gw])

  const cats = useMemo(() => Object.keys(skillsByCat).sort(), [skillsByCat])
  const skills = useMemo(() => (selectedCat ? (skillsByCat[selectedCat] ?? []) : []), [selectedCat, skillsByCat])
  const skillName = skills[skillIdx] ?? ''

  const catEntries = useMemo<IndexedLabel[]>(
    () => cats.map((label, index) => ({ index, label: `${label} · ${skillsByCat[label]?.length ?? 0} skills` })),
    [cats, skillsByCat]
  )

  const skillEntries = useMemo<IndexedLabel[]>(
    () => skills.map((label, index) => ({ index, label })),
    [skills]
  )

  const searchActive = searchStage === stage

  const { filtered: filteredCats, selectedPosition: catPos } = useIndexedFuzzyList(
    catEntries,
    catQuery,
    LABEL_SEARCH_KEYS,
    catIdx,
    setCatIdx,
    stage === 'category'
  )

  const { filtered: filteredSkills, selectedPosition: skillPos } = useIndexedFuzzyList(
    skillEntries,
    skillQuery,
    LABEL_SEARCH_KEYS,
    skillIdx,
    setSkillIdx,
    stage === 'skill'
  )

  const back = () => {
    if (stage === 'actions') {
      setStage('skill')
      setInfo(null)
      setErr('')

      return
    }

    if (stage === 'skill') {
      setStage('category')
      setSkillIdx(0)
      setSkillQuery('')
      setSearchStage(null)

      return
    }

    onClose()
  }

  useOverlayKeys({ disabled: installing || searchActive, onBack: back, onClose })

  const inspect = (name: string) => {
    setInfo(null)
    setErr('')

    gw.request<{ info?: SkillInfo }>('skills.manage', { action: 'inspect', query: name })
      .then(r => setInfo(r?.info ?? { name }))
      .catch((e: unknown) => setErr(rpcErrorMessage(e)))
  }

  const install = (name: string) => {
    setInstalling(true)
    setErr('')

    gw.request<{ installed?: boolean; name?: string }>('skills.manage', { action: 'install', query: name })
      .then(() => onClose())
      .catch((e: unknown) => setErr(rpcErrorMessage(e)))
      .finally(() => setInstalling(false))
  }

  useInput((ch, key) => {
    if (installing) {
      return
    }

    if (stage === 'actions') {
      if (key.return) {
        setStage('skill')
        setInfo(null)
        setErr('')

        return
      }

      if (ch?.toLowerCase() === 'x' && skillName) {
        install(skillName)

        return
      }

      if (ch?.toLowerCase() === 'i' && skillName) {
        inspect(skillName)
      }

      return
    }

    if (stage === 'category' || stage === 'skill') {
      const setQuery = stage === 'category' ? setCatQuery : setSkillQuery

      if (handleSearchInput(ch, key, {
        active: searchActive,
        setActive: active => setSearchStage(active ? stage : null),
        setQuery
      })) {
        return
      }
    }

    const entries = stage === 'category' ? filteredCats : filteredSkills
    const count = entries.length
    const sel = stage === 'category' ? catPos : skillPos
    const setSel = stage === 'category' ? setCatIdx : setSkillIdx

    if (key.upArrow && sel > 0) {
      setSel(entries[sel - 1]!.index)

      return
    }

    if (key.downArrow && sel < count - 1) {
      setSel(entries[sel + 1]!.index)

      return
    }

    if (key.return) {
      if (stage === 'category') {
        const cat = cats[catIdx]

        if (!cat || !filteredCats.length) {
          return
        }

        setSelectedCat(cat)
        setSkillIdx(0)
        setSkillQuery('')
        setSearchStage(null)
        setStage('skill')

        return
      }

      const name = skills[skillIdx]

      if (name && filteredSkills.length) {
        setStage('actions')
        inspect(name)
      }

      return
    }

    const n = ch === '0' ? 10 : parseInt(ch, 10)

    if (!Number.isNaN(n) && n >= 1 && n <= Math.min(10, count)) {
      const next = windowOffset(count, sel, VISIBLE) + n - 1
      const entry = entries[next]

      if (!entry) {
        return
      }

      if (stage === 'category') {
        const cat = cats[entry.index]

        if (cat) {
          setSelectedCat(cat)
          setCatIdx(entry.index)
          setSkillIdx(0)
          setSkillQuery('')
          setSearchStage(null)
          setStage('skill')
        }

        return
      }

      const name = skills[entry.index]

      if (name) {
        setSkillIdx(entry.index)
        setStage('actions')
        inspect(name)
      }
    }
  })

  if (loading) {
    return <Text color={t.color.muted}>loading skills…</Text>
  }

  if (err && stage === 'category') {
    return (
      <Box flexDirection="column" width={width}>
        <Text color={t.color.label}>error: {err}</Text>
        <OverlayHint t={t}>Esc/q cancel</OverlayHint>
      </Box>
    )
  }

  if (!cats.length) {
    return (
      <Box flexDirection="column" width={width}>
        <Text color={t.color.muted}>no skills available</Text>
        <OverlayHint t={t}>Esc/q cancel</OverlayHint>
      </Box>
    )
  }

  if (stage === 'category') {
    const { items, offset } = windowItems(filteredCats, catPos, VISIBLE)

    const searchLabel = catQuery || searchActive
      ? `Search: ${catQuery}${searchActive ? '▎' : ''} (${filteredCats.length}/${cats.length})`
      : 'Search: / to filter categories'

    return (
      <Box flexDirection="column" width={width}>
        <Text bold color={t.color.accent}>
          Skills Hub
        </Text>

        <Text color={t.color.muted}>select a category</Text>
        <Text color={searchActive ? t.color.accent : t.color.muted}>{searchLabel}</Text>
        {offset > 0 && <Text color={t.color.muted}> ↑ {offset} more</Text>}
        {!filteredCats.length && catQuery ? <Text color={t.color.muted}>no categories match "{catQuery}"</Text> : null}

        {items.map((entry, i) => {
          const idx = entry.index

          return (
            <Text
              bold={catIdx === idx}
              color={catIdx === idx ? t.color.accent : t.color.muted}
              inverse={catIdx === idx}
              key={entry.label}
              wrap="truncate-end"
            >
              {catIdx === idx ? '▸ ' : '  '}
              {offset + i + 1}. {entry.label}
            </Text>
          )
        })}

        {offset + VISIBLE < filteredCats.length && (
          <Text color={t.color.muted}> ↓ {filteredCats.length - offset - VISIBLE} more</Text>
        )}
        <OverlayHint t={t}>↑/↓ select · Enter open · / search · 1-9,0 quick · Esc/q cancel</OverlayHint>
      </Box>
    )
  }

  if (stage === 'skill') {
    const { items, offset } = windowItems(filteredSkills, skillPos, VISIBLE)

    const searchLabel = skillQuery || searchActive
      ? `Search: ${skillQuery}${searchActive ? '▎' : ''} (${filteredSkills.length}/${skills.length})`
      : 'Search: / to filter skills'

    return (
      <Box flexDirection="column" width={width}>
        <Text bold color={t.color.accent}>
          {selectedCat}
        </Text>

        <Text color={t.color.muted}>{skills.length} skill(s)</Text>
        <Text color={searchActive ? t.color.accent : t.color.muted}>{searchLabel}</Text>
        {!skills.length ? <Text color={t.color.muted}>no skills in this category</Text> : null}
        {skills.length && !filteredSkills.length && skillQuery ? (
          <Text color={t.color.muted}>no skills match "{skillQuery}"</Text>
        ) : null}
        {offset > 0 && <Text color={t.color.muted}> ↑ {offset} more</Text>}

        {items.map((entry, i) => {
          const idx = entry.index

          return (
            <Text
              bold={skillIdx === idx}
              color={skillIdx === idx ? t.color.accent : t.color.muted}
              inverse={skillIdx === idx}
              key={entry.label}
              wrap="truncate-end"
            >
              {skillIdx === idx ? '▸ ' : '  '}
              {offset + i + 1}. {entry.label}
            </Text>
          )
        })}

        {offset + VISIBLE < filteredSkills.length && (
          <Text color={t.color.muted}> ↓ {filteredSkills.length - offset - VISIBLE} more</Text>
        )}
        <OverlayHint t={t}>
          {skills.length ? '↑/↓ select · Enter open · / search · 1-9,0 quick · Esc back · q close' : 'Esc back · q close'}
        </OverlayHint>
      </Box>
    )
  }

  return (
    <Box flexDirection="column" width={width}>
      <Text bold color={t.color.accent}>
        {info?.name ?? skillName}
      </Text>

      <Text color={t.color.muted}>{info?.category ?? selectedCat}</Text>
      {info?.description ? <Text color={t.color.text}>{info.description}</Text> : null}
      {info?.path ? <Text color={t.color.muted}>path: {info.path}</Text> : null}
      {!info && !err ? <Text color={t.color.muted}>loading…</Text> : null}
      {err ? <Text color={t.color.label}>error: {err}</Text> : null}
      {installing ? <Text color={t.color.accent}>installing…</Text> : null}

      <OverlayHint t={t}>i reinspect · x reinstall · Enter/Esc back · q close</OverlayHint>
    </Box>
  )
}

interface SkillInfo {
  category?: string
  description?: string
  name?: string
  path?: string
}

interface SkillsHubProps {
  gw: GatewayClient
  onClose: () => void
  t: Theme
}
