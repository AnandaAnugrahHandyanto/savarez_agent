export type EventsState = "connecting" | "live" | "closed" | "error";

export const EVENTS_LABEL: Record<EventsState, string> = {
  connecting: "events",
  live: "live",
  closed: "closed",
  error: "error",
};

export const EVENTS_TONE: Record<
  EventsState,
  "secondary" | "warning" | "success" | "destructive"
> = {
  connecting: "warning",
  live: "success",
  closed: "secondary",
  error: "destructive",
};
