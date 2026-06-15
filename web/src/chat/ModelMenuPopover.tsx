import type { GatewayClient } from "@/lib/gatewayClient";
import { Button } from "@nous-research/ui/ui/components/button";
import { Checkbox } from "@nous-research/ui/ui/components/checkbox";
import { Input } from "@nous-research/ui/ui/components/input";
import { Label } from "@nous-research/ui/ui/components/label";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { fuzzyRank } from "@/lib/fuzzy";
import { cn } from "@/lib/utils";
import { Search, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import {
  applyModelSelection,
  type ModelOptionProvider,
  type ModelOptionsResponse,
} from "./modelPickerCore";

interface Props {
  gw: GatewayClient;
  sessionId: string;
  onClose(): void;
}

export function ModelMenuPopover({ gw, sessionId, onClose }: Props) {
  const [providers, setProviders] = useState<ModelOptionProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSlug, setSelectedSlug] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [query, setQuery] = useState("");
  const [persistGlobal, setPersistGlobal] = useState(false);
  const [applying, setApplying] = useState(false);
  const [confirmMessage, setConfirmMessage] = useState<string | null>(null);
  const closedRef = useRef(false);

  useEffect(() => {
    closedRef.current = false;
    gw
      .request<ModelOptionsResponse>("model.options", { session_id: sessionId })
      .then((r) => {
        if (closedRef.current) return;
        const next = r?.providers ?? [];
        setProviders(next);
        setSelectedSlug((next.find((p) => p.is_current) ?? next[0])?.slug ?? "");
        setLoading(false);
      })
      .catch((e) => {
        if (closedRef.current) return;
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      });

    return () => {
      closedRef.current = true;
    };
  }, [gw, sessionId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const selectedProvider = useMemo(
    () => providers.find((p) => p.slug === selectedSlug) ?? null,
    [providers, selectedSlug],
  );

  const models = selectedProvider?.models ?? [];
  const trimmedQuery = query.trim();

  const filteredProviders = useMemo(
    () =>
      fuzzyRank(
        providers,
        trimmedQuery,
        (p) => `${p.name} ${p.slug} ${(p.models ?? []).join(" ")}`,
      ).map((r) => r.item),
    [providers, trimmedQuery],
  );

  const filteredModels = useMemo(
    () =>
      fuzzyRank(models, trimmedQuery, (m) => m).map((r) => ({
        model: r.item,
        positions: r.positions,
      })),
    [models, trimmedQuery],
  );

  const runApply = async (confirmExpensive = false) => {
    if (!selectedProvider || !selectedModel || applying) return;
    setApplying(true);
    setError(null);
    try {
      const result = await applyModelSelection({
        gw,
        sessionId,
        providerSlug: selectedProvider.slug,
        model: selectedModel,
        persistGlobal,
        confirmExpensiveModel: confirmExpensive,
      });
      if (result?.confirm_required) {
        setConfirmMessage(
          result.confirm_message ||
            result.warning ||
            "This model has unusually high known pricing.",
        );
        return;
      }
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setApplying(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-[70] flex items-end justify-center sm:items-center">
      <button
        type="button"
        aria-label="Close model picker"
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
      />

      <div
        className={cn(
          "relative z-10 flex max-h-[min(70dvh,28rem)] w-full max-w-md flex-col",
          "rounded-t-lg border border-border bg-popover shadow-xl sm:rounded-lg",
        )}
      >
        <div className="flex items-center justify-between border-b border-border/40 px-3 py-2">
          <span className="text-sm font-medium">Switch model</span>
          <Button ghost size="icon" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </div>

        {confirmMessage ? (
          <div className="flex flex-col gap-3 p-4 text-sm">
            <p>{confirmMessage}</p>
            <div className="flex justify-end gap-2">
              <Button ghost onClick={() => setConfirmMessage(null)}>
                Cancel
              </Button>
              <Button onClick={() => void runApply(true)} disabled={applying}>
                Confirm
              </Button>
            </div>
          </div>
        ) : loading ? (
          <div className="flex items-center justify-center p-8">
            <Spinner />
          </div>
        ) : error ? (
          <p className="p-4 text-sm text-destructive">{error}</p>
        ) : (
          <>
            <div className="border-b border-border/30 px-3 py-2">
              <div className="relative">
                <Search className="absolute left-2 top-2 h-4 w-4 text-text-tertiary" />
                <Input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search providers or models…"
                  className="pl-8"
                />
              </div>
            </div>

            <div className="flex min-h-0 flex-1 divide-x divide-border/30">
              <div className="w-2/5 overflow-y-auto p-1">
                {filteredProviders.map((p) => (
                  <button
                    key={p.slug}
                    type="button"
                    onClick={() => {
                      setSelectedSlug(p.slug);
                      setSelectedModel("");
                    }}
                    className={cn(
                      "w-full rounded px-2 py-1.5 text-left text-xs",
                      selectedSlug === p.slug
                        ? "bg-primary/15 text-primary"
                        : "hover:bg-muted/40",
                    )}
                  >
                    {p.name}
                  </button>
                ))}
              </div>

              <div className="min-w-0 flex-1 overflow-y-auto p-1">
                {filteredModels.map(({ model }) => (
                  <button
                    key={model}
                    type="button"
                    onClick={() => setSelectedModel(model)}
                    className={cn(
                      "w-full rounded px-2 py-1.5 text-left font-mono text-xs",
                      selectedModel === model
                        ? "bg-primary/15 text-primary"
                        : "hover:bg-muted/40",
                    )}
                  >
                    {model}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center justify-between gap-2 border-t border-border/30 px-3 py-2">
              <Label className="flex items-center gap-2 text-xs">
                <Checkbox
                  checked={persistGlobal}
                  onCheckedChange={(v) => setPersistGlobal(v === true)}
                />
                Persist globally
              </Label>
              <Button
                onClick={() => void runApply()}
                disabled={!selectedModel || applying}
                size="sm"
              >
                Apply
              </Button>
            </div>
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}
