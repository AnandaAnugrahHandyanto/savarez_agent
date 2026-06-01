import { createContext } from "react";
import type { ActionStatusResponse, UpdatePreviewResponse } from "@/lib/api";

export const SystemActionsContext = createContext<SystemActionsState | null>(
  null,
);

export type SystemAction = "restart" | "update";

export interface SystemActionsState {
  actionStatus: ActionStatusResponse | null;
  activeAction: SystemAction | null;
  dismissLog: () => void;
  isBusy: boolean;
  isRunning: boolean;
  pendingAction: SystemAction | null;
  runAction: (action: SystemAction) => Promise<void>;
  /** Current update preview (changelog) or null if not fetched */
  updatePreview: UpdatePreviewResponse | null;
  /** Whether the update preview is currently being fetched */
  previewLoading: boolean;
  /** Dismiss the update preview dialog */
  dismissPreview: () => void;
  /** Confirm the update (after preview is shown) */
  confirmUpdate: () => Promise<void>;
}
