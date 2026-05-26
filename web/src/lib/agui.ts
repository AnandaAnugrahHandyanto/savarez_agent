export type AguiEvent = {
  type: string;
  [key: string]: unknown;
};

export class AguiSseDecoder {
  private buffer = "";

  push(chunk: string): AguiEvent[] {
    this.buffer += chunk;
    const events: AguiEvent[] = [];

    while (true) {
      const sep = this.findSeparator();
      if (sep.index < 0) break;
      const block = this.buffer.slice(0, sep.index);
      this.buffer = this.buffer.slice(sep.index + sep.length);
      const event = parseAguiSseBlock(block);
      if (event) events.push(event);
    }

    return events;
  }

  flush(): AguiEvent[] {
    if (!this.buffer.trim()) {
      this.buffer = "";
      return [];
    }
    const event = parseAguiSseBlock(this.buffer);
    this.buffer = "";
    return event ? [event] : [];
  }

  private findSeparator(): { index: number; length: number } {
    const lf = this.buffer.indexOf("\n\n");
    const crlf = this.buffer.indexOf("\r\n\r\n");
    if (lf < 0) return { index: crlf, length: crlf >= 0 ? 4 : 0 };
    if (crlf < 0) return { index: lf, length: 2 };
    return lf < crlf ? { index: lf, length: 2 } : { index: crlf, length: 4 };
  }
}

export function parseAguiSse(text: string): AguiEvent[] {
  const decoder = new AguiSseDecoder();
  return [...decoder.push(text), ...decoder.flush()];
}

export function parseAguiSseBlock(block: string): AguiEvent | null {
  const dataLines: string[] = [];
  for (const rawLine of block.split(/\r?\n/)) {
    const line = rawLine.trimEnd();
    if (!line || line.startsWith(":")) continue;
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (!dataLines.length) return null;
  const payload = dataLines.join("\n");
  if (payload === "[DONE]") return { type: "DONE" };
  const parsed = JSON.parse(payload) as unknown;
  if (!parsed || typeof parsed !== "object" || !("type" in parsed)) {
    return null;
  }
  return parsed as AguiEvent;
}
