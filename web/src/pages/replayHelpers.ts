import type { SessionInfo, SessionMessage } from "@/lib/api";

export type ReplayStatus = "success" | "failed" | "interrupted" | "running";

export function getSessionStatus(session: SessionInfo): ReplayStatus {
  const text = `${session.title ?? ""} ${session.preview ?? ""}`.toLowerCase();
  if (session.is_active) return "running";
  if (!session.ended_at) return "interrupted";
  if (
    /\b(fail|failed|failure|error|exception|traceback|crash|missing env)\b/.test(
      text,
    )
  ) {
    return "failed";
  }
  return "success";
}

export function statusTone(status: ReplayStatus) {
  if (status === "success") return "success" as const;
  if (status === "failed") return "destructive" as const;
  if (status === "running") return "warning" as const;
  return "outline" as const;
}

export function formatDuration(session: SessionInfo): string {
  const end = session.ended_at ?? session.last_active;
  const seconds = Math.max(0, Math.round(end - session.started_at));
  if (!Number.isFinite(seconds) || seconds <= 0) return "—";
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) return `${minutes}m ${remainingSeconds}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

export function formatTokens(session: SessionInfo): string {
  const total = (session.input_tokens ?? 0) + (session.output_tokens ?? 0);
  if (total <= 0) return "—";
  return new Intl.NumberFormat().format(total);
}

export function compactId(id: string): string {
  if (id.length <= 14) return id;
  return `${id.slice(0, 8)}…${id.slice(-4)}`;
}

export function formatDateTime(value: number): string {
  if (!value) return "—";
  return new Date(value * 1000).toLocaleString();
}

export function messageText(message: SessionMessage): string {
  if (message.content) return message.content;
  if (message.tool_calls?.length) {
    return message.tool_calls
      .map((call) => `${call.function.name}(${call.function.arguments})`)
      .join("\n");
  }
  return "";
}

export function isErrorText(text: string): boolean {
  return /\b(error|failed|failure|traceback|exception|exit_code[^0-9-]*[-:]?\s*[1-9]|missing|crash)\b/i.test(
    text,
  );
}

export function deriveIncidentSummary(
  session: SessionInfo | null,
  messages: SessionMessage[],
) {
  const status = session ? getSessionStatus(session) : "interrupted";
  const toolMessages = messages.filter(
    (message) => message.role === "tool" || message.tool_calls?.length,
  );
  const errorIndex = messages.findIndex((message) =>
    isErrorText(messageText(message)),
  );
  const errorMessage = errorIndex >= 0 ? messages[errorIndex] : null;
  const lastSuccessful =
    errorIndex > 0
      ? messages
          .slice(0, errorIndex)
          .reverse()
          .find((message) => !isErrorText(messageText(message)))
      : toolMessages.at(-1) ?? messages.at(-1);

  const failurePoint = errorMessage?.tool_name
    ? errorMessage.tool_name
    : errorMessage?.tool_calls?.[0]?.function.name
      ? errorMessage.tool_calls[0].function.name
      : status === "failed"
        ? "session execution"
        : status === "interrupted"
          ? "session interrupted"
          : "none detected";

  const rawError = errorMessage ? messageText(errorMessage).trim() : "";
  const error = rawError ? rawError.slice(0, 220) : "No blocking error detected.";
  const lastSuccessfulStep = lastSuccessful
    ? (lastSuccessful.tool_name ??
      lastSuccessful.tool_calls?.[0]?.function.name ??
      lastSuccessful.role)
    : "—";
  const suggestedNextStep =
    status === "failed"
      ? "Inspect the failing tool/terminal output, fix the root cause, then replay or resume from the last successful step."
      : status === "interrupted"
        ? "Resume the session or compare it with a successful run to find the missing step."
        : "Share, export, or compare this run if you need to hand off the result.";

  return {
    outcome: status,
    failurePoint,
    lastSuccessfulStep,
    error,
    suggestedNextStep,
  };
}

export function countToolCalls(messages: SessionMessage[]): number {
  return messages.reduce(
    (total, message) => total + (message.tool_calls?.length ?? 0),
    0,
  );
}

export function terminalCommands(messages: SessionMessage[]): string[] {
  return messages.flatMap((message) =>
    (message.tool_calls ?? [])
      .filter((call) => call.function.name === "terminal")
      .map((call) => call.function.arguments),
  );
}

export function fileChangeCalls(messages: SessionMessage[]): string[] {
  return messages.flatMap((message) =>
    (message.tool_calls ?? [])
      .filter((call) => /write_file|patch|edit|remove_file/.test(call.function.name))
      .map((call) => `${call.function.name}: ${call.function.arguments}`),
  );
}
