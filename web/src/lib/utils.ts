import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export interface TimeAgoLabels {
  justNow: string;
  minutesAgo: string;
  hoursAgo: string;
  yesterday: string;
  daysAgo: string;
  unknown: string;
}

const DEFAULT_TIME_AGO_LABELS: TimeAgoLabels = {
  justNow: "just now",
  minutesAgo: "{count}m ago",
  hoursAgo: "{count}h ago",
  yesterday: "yesterday",
  daysAgo: "{count}d ago",
  unknown: "unknown",
};

function formatRelativeTime(template: string, count: number): string {
  return template.replace("{count}", String(count));
}

/** Relative time from a Unix epoch timestamp (seconds). */
export function timeAgo(
  ts: number,
  labels: TimeAgoLabels = DEFAULT_TIME_AGO_LABELS,
): string {
  const delta = Date.now() / 1000 - ts;
  if (delta < 60) return labels.justNow;
  if (delta < 3600) {
    return formatRelativeTime(labels.minutesAgo, Math.floor(delta / 60));
  }
  if (delta < 86400) {
    return formatRelativeTime(labels.hoursAgo, Math.floor(delta / 3600));
  }
  if (delta < 172800) return labels.yesterday;
  return formatRelativeTime(labels.daysAgo, Math.floor(delta / 86400));
}

/** Relative time from an ISO-8601 timestamp string. */
export function isoTimeAgo(
  iso: string,
  labels: TimeAgoLabels = DEFAULT_TIME_AGO_LABELS,
): string {
  const ts = new Date(iso).getTime() / 1000;
  if (Number.isNaN(ts) || ts > Date.now() / 1000) return labels.unknown;
  return timeAgo(ts, labels);
}
