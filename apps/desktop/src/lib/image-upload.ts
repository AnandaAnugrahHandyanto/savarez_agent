export interface ImageUploadPayload {
  data_base64: string
  filename: string
  mime_type: string
}

const DATA_URL_RE = /^data:([^;,]+)?(?:;[^,]*)?;base64,(.*)$/s
const CHUNK_SIZE = 0x8000

function basename(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).pop() || 'image'
}

export function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''

  for (let offset = 0; offset < bytes.length; offset += CHUNK_SIZE) {
    const chunk = bytes.subarray(offset, offset + CHUNK_SIZE)
    binary += String.fromCharCode(...chunk)
  }

  return btoa(binary)
}

export async function imageUploadPayloadFromFile(file: File): Promise<ImageUploadPayload> {
  return {
    data_base64: arrayBufferToBase64(await file.arrayBuffer()),
    filename: basename(file.name || 'image'),
    mime_type: file.type || 'application/octet-stream'
  }
}

export function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.addEventListener('load', () => resolve(String(reader.result || '')))
    reader.addEventListener('error', () => reject(reader.error || new Error('Failed to read image')))
    reader.readAsDataURL(file)
  })
}

export function imageUploadPayloadFromPath(filePath: string, dataUrl: string): ImageUploadPayload {
  const match = dataUrl.match(DATA_URL_RE)

  if (!match) {
    throw new Error('Expected image data URL')
  }

  return {
    data_base64: match[2] || '',
    filename: basename(filePath),
    mime_type: match[1] || 'application/octet-stream'
  }
}
