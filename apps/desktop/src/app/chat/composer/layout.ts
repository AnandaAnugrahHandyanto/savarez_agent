export function draftRequestsStackedComposer(draft: string): boolean {
  return draft.includes('\n')
}

export function composerUsesStackedLayout({
  draft,
  narrow,
  tight
}: {
  draft: string
  narrow: boolean
  tight: boolean
}): boolean {
  return draftRequestsStackedComposer(draft) || narrow || tight
}
