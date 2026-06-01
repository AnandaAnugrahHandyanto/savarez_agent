import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ActionStatusResponse, UpdatePreviewResponse } from "@/lib/api";
import { Toast } from "@nous-research/ui/ui/components/toast";
import { useI18n } from "@/i18n";
import {
  SystemActionsContext,
  type SystemAction,
} from "./system-actions-context";

const ACTION_NAMES: Record<SystemAction, string> = {
  restart: "gateway-restart",
  update: "hermes-update",
};

export function SystemActionsProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [pendingAction, setPendingAction] = useState<SystemAction | null>(null);
  const [activeAction, setActiveAction] = useState<SystemAction | null>(null);
  const [actionStatus, setActionStatus] = useState<ActionStatusResponse | null>(
    null,
  );
  const [toast, setToast] = useState<ToastState | null>(null);
  const [updatePreview, setUpdatePreview] =
    useState<UpdatePreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const { t } = useI18n();

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  // Poll action status while an action is active
  useEffect(() => {
    if (!activeAction) return;
    const name = ACTION_NAMES[activeAction];
    let cancelled = false;

    const poll = async () => {
      try {
        const resp = await api.getActionStatus(name);
        if (cancelled) return;
        setActionStatus(resp);
        if (!resp.running) {
          const ok = resp.exit_code === 0;
          setToast({
            type: ok ? "success" : "error",
            message: ok
              ? t.status.actionFinished
              : `${t.status.actionFailed} (exit ${resp.exit_code ?? "?"})`,
          });

          // If update completed successfully, restart the dashboard
          if (activeAction === "update" && ok) {
            setTimeout(() => {
              api.restartDashboard().catch(() => {});
            }, 500);
          }
          return;
        }
      } catch {
        // transient fetch error; keep polling
      }
      if (!cancelled) setTimeout(poll, 1500);
    };

    poll();
    return () => {
      cancelled = true;
    };
  }, [activeAction, t.status.actionFinished, t.status.actionFailed]);

  const runAction = useCallback(
    async (action: SystemAction) => {
      // For update: show preview first, don't start immediately
      if (action === "update") {
        setPreviewLoading(true);
        try {
          const preview = await api.previewUpdate();
          setUpdatePreview(preview);
          if (preview.up_to_date) {
            setToast({
              type: "success",
              message: t.status.upToDate ?? "Hermes is already up to date",
            });
            setUpdatePreview(null); // dismiss preview if up to date
          }
        } catch (err) {
          const detail = err instanceof Error ? err.message : String(err);
          setToast({
            type: "error",
            message: `${t.status.actionFailed}: ${detail}`,
          });
        } finally {
          setPreviewLoading(false);
        }
        return;
      }

      // Restart: execute immediately (no preview needed)
      setPendingAction(action);
      setActionStatus(null);
      try {
        await api.restartGateway();
        setActiveAction(action);
      } catch (err) {
        const detail = err instanceof Error ? err.message : String(err);
        setToast({
          type: "error",
          message: `${t.status.actionFailed}: ${detail}`,
        });
      } finally {
        setPendingAction(null);
      }
    },
    [t.status.actionFailed, t.status.upToDate],
  );

  const confirmUpdate = useCallback(async () => {
    setUpdatePreview(null);
    setPendingAction("update");
    setActionStatus(null);
    try {
      await api.updateHermes();
      setActiveAction("update");
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      setToast({
        type: "error",
        message: `${t.status.actionFailed}: ${detail}`,
      });
    } finally {
      setPendingAction(null);
    }
  }, [t.status.actionFailed]);

  const dismissLog = useCallback(() => {
    setActiveAction(null);
    setActionStatus(null);
  }, []);

  const dismissPreview = useCallback(() => {
    setUpdatePreview(null);
  }, []);

  const isRunning =
    activeAction !== null && actionStatus?.running !== false;
  const isBusy = pendingAction !== null || isRunning || previewLoading;

  return (
    <SystemActionsContext.Provider
      value={{
        actionStatus,
        activeAction,
        dismissLog,
        isBusy,
        isRunning,
        pendingAction,
        runAction,
        updatePreview,
        previewLoading,
        dismissPreview,
        confirmUpdate,
      }}
    >
      {children}
      <Toast toast={toast} />
    </SystemActionsContext.Provider>
  );
}

interface ToastState {
  message: string;
  type: "success" | "error";
}
