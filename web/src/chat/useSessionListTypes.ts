import type { SessionActiveItem, SessionListItem } from "./sessionListCore";

export interface UseSessionListResult {
  live: SessionActiveItem[];
  history: SessionListItem[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}
