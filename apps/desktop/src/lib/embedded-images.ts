const DATA_IMAGE_URL_PREFIX_RE = /data:image\/[\w.+-]+;base64,/iy
const DATA_URL_RE = /^data:([\w./+-]+);base64,(.*)$/i
const BASE64_CHAR_RE = /[A-Za-z0-9+/=]/

export const DATA_IMAGE_URL_RE = /^data:image\/[\w.+-]+;base64,/i

export interface EmbeddedImageExtraction {
  cleanedText: string
  images: string[]
}

export function dataUrlToBlob(dataUrl: string): Blob | null {
  const match = DATA_URL_RE.exec(dataUrl.trim())

  if (!match) {
    return null
  }

  try {
    const bytes = atob(match[2])
    const buffer = new Uint8Array(bytes.length)

    for (let i = 0; i < bytes.length; i += 1) {
      buffer[i] = bytes.charCodeAt(i)
    }

    return new Blob([buffer], { type: match[1] })
  } catch {
    return null
  }
}

function dataImageUrlEnd(text: string, start: number): number | null {
  DATA_IMAGE_URL_PREFIX_RE.lastIndex = start
  const prefix = DATA_IMAGE_URL_PREFIX_RE.exec(text)

  if (!prefix || prefix.index !== start) {
    return null
  }

  let end = DATA_IMAGE_URL_PREFIX_RE.lastIndex

  while (end < text.length && BASE64_CHAR_RE.test(text[end])) {
    end += 1
  }

  // Ignore tiny/partial strings so normal prose is preserved. The old regex used
  // the same 64-character floor; keep that contract while avoiding a huge
  // backtracking match over multi-megabyte data URLs.
  return end - DATA_IMAGE_URL_PREFIX_RE.lastIndex >= 64 ? end : null
}

export function extractEmbeddedImages(text: string): EmbeddedImageExtraction {
  if (!text || !text.includes('data:image/')) {
    return { cleanedText: text, images: [] }
  }

  const images: string[] = []
  const chunks: string[] = []
  let cursor = 0

  while (cursor < text.length) {
    const start = text.indexOf('data:image/', cursor)

    if (start < 0) {
      chunks.push(text.slice(cursor))

      break
    }

    const end = dataImageUrlEnd(text, start)

    if (!end) {
      chunks.push(text.slice(cursor, start + 'data:image/'.length))
      cursor = start + 'data:image/'.length

      continue
    }

    let removeStart = start
    let removeEnd = end

    const jsonPrefix = '{"type":"image_url","image_url":{"url":"'
    const jsonSuffix = '"}}'

    if (text.slice(start - jsonPrefix.length, start) === jsonPrefix && text.slice(end, end + jsonSuffix.length) === jsonSuffix) {
      removeStart = start - jsonPrefix.length
      removeEnd = end + jsonSuffix.length
    }

    chunks.push(text.slice(cursor, removeStart))
    images.push(text.slice(start, end))
    cursor = removeEnd
  }

  const cleanedText = chunks
    .join('')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()

  return { cleanedText, images }
}

export function embeddedImageUrls(text: string): string[] {
  return extractEmbeddedImages(text).images
}

export function textWithoutEmbeddedImages(text: string): string {
  return extractEmbeddedImages(text).cleanedText
}
