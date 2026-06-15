/**
 * Slash command execution pipeline for the web chat.
 *
 * Mirrors the Ink TUI's createSlashHandler.ts:
 *
 *   1. Parse the command into `name` + `arg`.
 *   2. Try `slash.exec` — covers every registry-backed command the terminal
 *      UI knows about (/help, /resume, /compact, /model, …). Output is
 *      rendered into the transcript.
 *   3. If `slash.exec` errors (command rejected, unknown, or needs client
 *      behaviour), fall back to `command.dispatch` which returns a typed
 *      directive: `exec` | `plugin` | `alias` | `skill` | `send`.
 *   4. Each directive is dispatched to the appropriate callback.
 *
 * Keeping the pipeline here (instead of inline in ChatPage) lets future
 * clients (SwiftUI, Android) implement the same logic by reading the same
 * contract.
 */

import type { GatewayClient } from "@/lib/gatewayClient";

export interface SlashExecResponse {
  output?: string;
  warning?: string;
}

export type CommandDispatchResponse =
  | { type: "exec" | "plugin"; output?: string }
  | { type: "alias"; target: string }
  | { type: "skill"; name: string; message?: string }
  | { type: "send"; message: string };

export interface SlashExecCallbacks {
  /** Render a transcript system message. */
  sys(text: string): void;
  /** Submit a user message to the agent (prompt.submit). */
  send(message: string): Promise<void> | void;
  /**
   * Fork the visible transcript into a new live session (`session.create`).
   * Used by `/branch` and `/fork` — avoids the slash worker, works while the
   * parent turn is still running.
   */
  branch?: (opts: { name: string }) => Promise<void>;
}

export interface SlashExecOptions {
  /** Raw command including the leading slash (e.g. "/model opus-4.6"). */
  command: string;
  /** Session id. If empty the call is still issued — some commands are session-less. */
  sessionId: string;
  gw: GatewayClient;
  callbacks: SlashExecCallbacks;
}

export type SlashExecResult = "done" | "sent" | "error";

interface ReloadMcpResponse {
  status?: "confirm_required" | "reloaded";
  message?: string;
}

/**
 * Native slash commands that bypass slash.exec / command.dispatch.
 * Mirrors ui-tui client handlers (ops.ts, session.ts).
 */
async function executeNativeSlash(
  name: string,
  arg: string,
  sessionId: string,
  gw: GatewayClient,
  callbacks: SlashExecCallbacks,
): Promise<SlashExecResult | null> {
  const { sys, branch } = callbacks;

  if (name === "branch" || name === "fork") {
    if (!branch) {
      sys("branch unavailable");
      return "error";
    }
    try {
      await branch({ name: arg });
      return "done";
    } catch (err) {
      sys(`error: ${err instanceof Error ? err.message : String(err)}`);
      return "error";
    }
  }

  if (name !== "reload-mcp" && name !== "reload_mcp") {
    return null;
  }

  const a = arg.trim().toLowerCase();
  const params: {
    session_id: string;
    confirm?: boolean;
    always?: boolean;
  } = { session_id: sessionId };
  if (a === "now" || a === "approve" || a === "once" || a === "yes") {
    params.confirm = true;
  } else if (a === "always") {
    params.confirm = true;
    params.always = true;
  }

  try {
    const r = await gw.request<ReloadMcpResponse>("reload.mcp", params);
    if (r?.status === "confirm_required") {
      sys(r.message ?? "/reload-mcp requires confirmation");
      return "done";
    }
    if (r?.status === "reloaded") {
      sys(
        params.always
          ? "MCP servers reloaded · future /reload-mcp will run without confirmation"
          : "MCP servers reloaded",
      );
      return "done";
    }
    sys("reload complete");
    return "done";
  } catch (err) {
    sys(`error: ${err instanceof Error ? err.message : String(err)}`);
    return "error";
  }
}

/**
 * Run a slash command. Returns the terminal state so callers can decide
 * whether to clear the composer, queue retries, etc.
 */
export async function executeSlash({
  command,
  sessionId,
  gw,
  callbacks,
}: SlashExecOptions): Promise<SlashExecResult> {
  const { name, arg } = parseSlash(command);
  const { sys, send } = callbacks;

  if (!name) {
    sys("empty slash command");
    return "error";
  }

  const native = await executeNativeSlash(name, arg, sessionId, gw, callbacks);
  if (native !== null) {
    return native;
  }

  // Primary dispatcher.
  try {
    const r = await gw.request<SlashExecResponse>("slash.exec", {
      command: command.replace(/^\/+/, ""),
      session_id: sessionId,
    });
    const body = r?.output || `/${name}: no output`;
    sys(r?.warning ? `warning: ${r.warning}\n${body}` : body);
    return "done";
  } catch {
    /* fall through to command.dispatch */
  }

  try {
    const d = parseCommandDispatch(
      await gw.request<unknown>("command.dispatch", {
        name,
        arg,
        session_id: sessionId,
      }),
    );

    if (!d) {
      sys("error: invalid response: command.dispatch");
      return "error";
    }

    switch (d.type) {
      case "exec":
      case "plugin":
        sys(d.output ?? "(no output)");
        return "done";

      case "alias":
        return executeSlash({
          command: `/${d.target}${arg ? ` ${arg}` : ""}`,
          sessionId,
          gw,
          callbacks,
        });

      case "skill":
      case "send": {
        const msg = d.message?.trim() ?? "";
        if (!msg) {
          sys(
            `/${name}: ${d.type === "skill" ? "skill payload missing message" : "empty message"}`,
          );
          return "error";
        }
        if (d.type === "skill") sys(`⚡ loading skill: ${d.name}`);
        await send(msg);
        return "sent";
      }
    }
  } catch (err) {
    sys(`error: ${err instanceof Error ? err.message : String(err)}`);
    return "error";
  }
}

export function parseSlash(command: string): { name: string; arg: string } {
  const m = command.replace(/^\/+/, "").match(/^(\S+)\s*(.*)$/);
  return m ? { name: m[1], arg: m[2].trim() } : { name: "", arg: "" };
}

function parseCommandDispatch(raw: unknown): CommandDispatchResponse | null {
  if (!raw || typeof raw !== "object") return null;

  const r = raw as Record<string, unknown>;
  const str = (v: unknown) => (typeof v === "string" ? v : undefined);

  switch (r.type) {
    case "exec":
    case "plugin":
      return { type: r.type, output: str(r.output) };

    case "alias":
      return typeof r.target === "string"
        ? { type: "alias", target: r.target }
        : null;

    case "skill":
      return typeof r.name === "string"
        ? { type: "skill", name: r.name, message: str(r.message) }
        : null;

    case "send":
      return typeof r.message === "string"
        ? { type: "send", message: r.message }
        : null;

    default:
      return null;
  }
}
