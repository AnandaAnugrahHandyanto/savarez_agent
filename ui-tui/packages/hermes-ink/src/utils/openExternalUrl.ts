import { spawn } from 'child_process'

const ALLOWED_PROTOCOLS = new Set(['http:', 'https:', 'mailto:'])

type OpenCommand = {
  args: string[]
  command: string
}

export function commandForExternalUrl(url: string, platform = process.platform): OpenCommand | undefined {
  let parsed: URL

  try {
    parsed = new URL(url)
  } catch {
    return undefined
  }

  if (!ALLOWED_PROTOCOLS.has(parsed.protocol)) {
    return undefined
  }

  if (platform === 'darwin') {
    return { command: 'open', args: [url] }
  }

  if (platform === 'win32') {
    return { command: 'cmd', args: ['/c', 'start', '', url] }
  }

  return { command: 'xdg-open', args: [url] }
}

export function openExternalUrl(url: string): void {
  const command = commandForExternalUrl(url)

  if (!command) {
    return
  }

  const child = spawn(command.command, command.args, {
    detached: true,
    stdio: 'ignore'
  })

  child.on('error', () => {})
  child.unref()
}
