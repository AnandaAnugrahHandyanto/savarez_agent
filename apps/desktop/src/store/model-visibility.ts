import { atom } from 'nanostores'

import { persistString, storedString } from '@/lib/storage'
import type { ModelOptionProvider } from '@/types/hermes'

const STORAGE_KEY = 'hermes.desktop.visible-models'

/** Providers the user has already customized. A provider in this set with zero
 *  visible keys means the user deliberately hid all of its models — we must NOT
 *  resurrect its defaults. A provider absent from this set is genuinely new and
 *  still gets seeded so it shows up by default after an update adds it. */
const KNOWN_PROVIDERS_KEY = 'hermes.desktop.known-model-providers'

/** Models shown per provider in the status-bar dropdown before the user has
 *  customized the list. Backend `models` are already relevance-ordered. */
export const DEFAULT_VISIBLE_PER_PROVIDER = 50

/** Stable key for a provider/model pair (`::` avoids colliding with model ids
 *  that contain a single colon, e.g. `model:tag`). */
export const modelVisibilityKey = (provider: string, model: string): string => `${provider}::${model}`

/** A model and its optional `…-fast` sibling, collapsed into one logical row.
 *  `id` is the canonical (base) model; `fastId` is the fast variant if present. */
export interface ModelFamily {
  fastId: string | null
  id: string
}

/** Collapse a provider's model list so a base model and its `…-fast` variant
 *  become a single family (one row, one toggle). Order is preserved by the
 *  base model's position. A `…-fast` model with no base stands on its own. */
export function collapseModelFamilies(models: readonly string[]): ModelFamily[] {
  const present = new Set(models)
  const families: ModelFamily[] = []
  const consumed = new Set<string>()

  for (const model of models) {
    if (consumed.has(model)) {
      continue
    }

    if (/-fast$/i.test(model) && present.has(model.replace(/-fast$/i, ''))) {
      // Represented by its base entry — the base attaches it as `fastId`.
      continue
    }

    const fastId = `${model}-fast`
    const hasFast = present.has(fastId)
    families.push({ fastId: hasFast ? fastId : null, id: model })
    consumed.add(model)

    if (hasFast) {
      consumed.add(fastId)
    }
  }

  return families
}

function loadVisible(): Set<string> | null {
  const raw = storedString(STORAGE_KEY)

  if (!raw) {
    return null
  }

  try {
    const parsed = JSON.parse(raw)

    return Array.isArray(parsed) ? new Set(parsed.filter((x): x is string => typeof x === 'string')) : null
  } catch {
    return null
  }
}

/** Explicit set of visible `provider::model` keys, or null when the user
 *  hasn't customized — in which case the curated default applies. */
export const $visibleModels = atom<Set<string> | null>(loadVisible())

/** Provider slugs the user has customized at least once. Seeded lazily by
 *  {@link setVisibleModels}; null until the first customization. */
export const $knownProviders = atom<Set<string> | null>(loadKnownProviders())

export const $modelVisibilityOpen = atom(false)

function loadKnownProviders(): Set<string> | null {
  const raw = storedString(KNOWN_PROVIDERS_KEY)

  if (!raw) {
    return null
  }

  try {
    const parsed = JSON.parse(raw)

    return Array.isArray(parsed) ? new Set(parsed.filter((x): x is string => typeof x === 'string')) : null
  } catch {
    return null
  }
}

/** Persist the visible key set. Pass `knownProviderSlugs` (the provider slugs
 *  currently on screen) whenever the change is a user customization so a
 *  provider the user empties stays empty instead of being re-seeded. The known
 *  set is unioned so transient/partial provider lists never drop a slug. */
export function setVisibleModels(keys: Set<string>, knownProviderSlugs?: Iterable<string>): void {
  $visibleModels.set(new Set(keys))
  persistString(STORAGE_KEY, JSON.stringify([...keys]))

  if (knownProviderSlugs !== undefined) {
    const known = new Set([...($knownProviders.get() ?? []), ...knownProviderSlugs])
    $knownProviders.set(known)
    persistString(KNOWN_PROVIDERS_KEY, JSON.stringify([...known]))
  }
}

export function setModelVisibilityOpen(open: boolean): void {
  $modelVisibilityOpen.set(open)
}

/** The default-visible key set: the curated top-N per provider. Used both as
 *  the dropdown fallback and to seed the Edit Models dialog. */
export function defaultVisibleKeys(providers: readonly ModelOptionProvider[]): Set<string> {
  const keys = new Set<string>()

  for (const provider of providers) {
    const families = collapseModelFamilies(provider.models ?? [])

    for (const family of families.slice(0, DEFAULT_VISIBLE_PER_PROVIDER)) {
      keys.add(modelVisibilityKey(provider.slug, family.id))
    }
  }

  return keys
}

/** Resolve which keys are currently visible: the user's explicit set when
 *  configured, otherwise the curated default for the given providers. */
export function effectiveVisibleKeys(
  stored: Set<string> | null,
  providers: readonly ModelOptionProvider[],
  known?: Set<string> | null
): Set<string> {
  if (!stored) {
    return defaultVisibleKeys(providers)
  }

  if (stored.size === 0) {
    return new Set()
  }

  const next = new Set(stored)

  for (const provider of providers) {
    const providerPrefix = `${provider.slug}::`
    const hasStoredProvider = [...stored].some(key => key.startsWith(providerPrefix))

    if (hasStoredProvider) {
      continue
    }

    // Zero stored keys for this provider. Seed its curated defaults only when
    // the provider is genuinely new (never customized). If the user has already
    // customized it — i.e. they hid every model down to the last one — keep it
    // empty rather than resurrecting every toggle they just turned off.
    if (known?.has(provider.slug)) {
      continue
    }

    const families = collapseModelFamilies(provider.models ?? [])

    for (const family of families.slice(0, DEFAULT_VISIBLE_PER_PROVIDER)) {
      next.add(modelVisibilityKey(provider.slug, family.id))
    }
  }

  return next
}
