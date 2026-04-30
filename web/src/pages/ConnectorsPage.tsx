import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import {
  Plug,
  RefreshCw,
  Save,
  Settings2,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import type { ConnectorInfo, ConnectorPatch } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectOption } from "@/components/ui/select";
import { useToast } from "@/hooks/useToast";
import { Toast } from "@/components/Toast";
import { useI18n } from "@/i18n";
import { usePageHeader } from "@/contexts/usePageHeader";
import { PluginSlot } from "@/plugins";

type Filter = "all" | "enabled" | "disabled";

function runtimeBadge(runtime: ConnectorInfo["runtime"]) {
  const state = runtime?.state ?? "unknown";
  const variant =
    state === "connected" || state === "running"
      ? "success"
      : state === "retrying" || state === "starting"
        ? "warning"
        : state === "fatal" || state === "disconnected"
          ? "destructive"
          : "outline";
  return (
    <Badge variant={variant} className="text-[10px]">
      {state}
    </Badge>
  );
}

function ConnectorConfigModal({
  connector,
  open,
  onClose,
  onSave,
}: {
  connector: ConnectorInfo | null;
  open: boolean;
  onClose: () => void;
  onSave: (patch: ConnectorPatch) => void;
}) {
  const { t } = useI18n();
  const [enabled, setEnabled] = useState(false);
  const [token, setToken] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [replyToMode, setReplyToMode] = useState<"off" | "first" | "all">("first");
  const [homeChatId, setHomeChatId] = useState("");
  const [homeName, setHomeName] = useState("");
  const [extraText, setExtraText] = useState("");

  useEffect(() => {
    if (!connector) return;
    setEnabled(connector.enabled);
    setToken("");
    setApiKey("");
    setReplyToMode((connector.reply_to_mode as "off" | "first" | "all") ?? "first");
    const hc = connector.home_channel as { chat_id?: string | number; name?: string } | null;
    setHomeChatId(hc?.chat_id !== undefined && hc?.chat_id !== null ? String(hc.chat_id) : "");
    setHomeName(hc?.name ?? "");
    setExtraText(JSON.stringify(connector.extra ?? {}, null, 2));
  }, [connector]);

  if (!open || !connector) return null;

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    >
      <div className="w-full max-w-2xl mx-4 border border-border bg-card shadow-lg">
        <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
          <div className="min-w-0">
            <h2 className="text-sm font-bold tracking-[0.08em] uppercase">
              {connector.label}
            </h2>
            <p className="text-xs text-muted-foreground">
              {connector.id}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="opacity-70 hover:opacity-100"
            aria-label={t.common.close}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-4 grid gap-4">
          <div className="flex items-center justify-between">
            <div className="grid gap-0.5">
              <Label>{t.common.enabled}</Label>
              <span className="text-xs text-muted-foreground">
                {connector.runtime?.state ? `${t.status.gateway}: ${connector.runtime.state}` : ""}
              </span>
            </div>
            <Switch checked={enabled} onCheckedChange={setEnabled} />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="connector-token">Token</Label>
            <Input
              id="connector-token"
              placeholder={connector.token_redacted ?? ""}
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
            <div className="flex items-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => onSave({ token: null })}
                className="h-7 text-xs"
              >
                {t.common.clear}
              </Button>
              <span className="text-xs text-muted-foreground">
                {connector.token_redacted ? connector.token_redacted : ""}
              </span>
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="connector-api-key">API Key</Label>
            <Input
              id="connector-api-key"
              placeholder={connector.api_key_redacted ?? ""}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
            <div className="flex items-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => onSave({ api_key: null })}
                className="h-7 text-xs"
              >
                {t.common.clear}
              </Button>
              <span className="text-xs text-muted-foreground">
                {connector.api_key_redacted ? connector.api_key_redacted : ""}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="grid gap-2">
              <Label htmlFor="connector-reply-mode">Reply mode</Label>
              <Select
                id="connector-reply-mode"
                value={replyToMode}
                onValueChange={(v) => setReplyToMode(v as "off" | "first" | "all")}
              >
                <SelectOption value="off">{t.common.off}</SelectOption>
                <SelectOption value="first">first</SelectOption>
                <SelectOption value="all">all</SelectOption>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="connector-home-chat">Home chat_id</Label>
              <Input
                id="connector-home-chat"
                value={homeChatId}
                onChange={(e) => setHomeChatId(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="connector-home-name">Home name</Label>
              <Input
                id="connector-home-name"
                value={homeName}
                onChange={(e) => setHomeName(e.target.value)}
              />
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="connector-extra">Extra (JSON)</Label>
            <textarea
              id="connector-extra"
              className="min-h-[160px] w-full border border-input bg-transparent px-3 py-2 text-sm font-mono leading-relaxed focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              value={extraText}
              onChange={(e) => setExtraText(e.target.value)}
              spellCheck={false}
            />
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border p-3">
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={() => {
              let extra: Record<string, unknown> | null = null;
              try {
                extra = extraText.trim() ? (JSON.parse(extraText) as Record<string, unknown>) : {};
              } catch {
                extra = null;
              }
              const patch: ConnectorPatch = {
                enabled,
                reply_to_mode: replyToMode,
                home_channel: homeChatId || homeName ? { chat_id: homeChatId || null, name: homeName || null } : null,
              };
              if (token.trim()) patch.token = token.trim();
              if (apiKey.trim()) patch.api_key = apiKey.trim();
              if (extra === null) {
                onSave({ ...patch, extra: undefined });
                return;
              }
              patch.extra = extra;
              onSave(patch);
            }}
            className="gap-1.5"
          >
            <Save className="h-3.5 w-3.5" />
            {t.common.save}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

export default function ConnectorsPage() {
  const [connectors, setConnectors] = useState<ConnectorInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [selected, setSelected] = useState<ConnectorInfo | null>(null);
  const [saving, setSaving] = useState(false);
  const { toast, showToast } = useToast();
  const { t } = useI18n();
  const { setEnd } = usePageHeader();

  const load = useCallback(() => {
    api
      .getConnectors()
      .then((r) => setConnectors(r.connectors))
      .catch((e) => showToast(String(e), "error"))
      .finally(() => setLoading(false));
  }, [showToast]);

  useLayoutEffect(() => {
    setEnd(
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={load}
        disabled={loading}
        className="h-7 text-xs"
      >
        <RefreshCw className="mr-1 h-3 w-3" />
        {t.common.refresh}
      </Button>,
    );
    return () => setEnd(null);
  }, [load, loading, setEnd, t.common.refresh]);

  useEffect(() => {
    load();
    const id = window.setInterval(load, 5000);
    return () => window.clearInterval(id);
  }, [load]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return connectors.filter((c) => {
      if (filter === "enabled" && !c.enabled) return false;
      if (filter === "disabled" && c.enabled) return false;
      if (!q) return true;
      return (
        c.id.toLowerCase().includes(q) ||
        c.label.toLowerCase().includes(q) ||
        (c.runtime?.state ?? "").toLowerCase().includes(q)
      );
    });
  }, [connectors, filter, search]);

  const applyPatch = async (id: string, patch: ConnectorPatch) => {
    setSaving(true);
    try {
      await api.updateConnector(id, patch);
      showToast(t.config.configSaved, "success");
      load();
    } catch (e) {
      showToast(String(e), "error");
    } finally {
      setSaving(false);
    }
  };

  if (loading && connectors.length === 0) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <PluginSlot name="connectors:top" />
      <Toast toast={toast} />

      <ConnectorConfigModal
        connector={selected}
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        onSave={(patch) => {
          if (!selected) return;
          if (patch.extra === undefined && selected) {
            showToast("Invalid JSON in extra", "error");
            return;
          }
          void applyPatch(selected.id, patch);
          if (!("token" in patch) && !("api_key" in patch)) setSelected(null);
        }}
      />

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full min-w-0 sm:max-w-xs">
          <Input
            placeholder={t.common.search}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-8 text-xs"
          />
        </div>

        <Select value={filter} onValueChange={(v) => setFilter(v as Filter)}>
          <SelectOption value="all">{t.common.all}</SelectOption>
          <SelectOption value="enabled">{t.common.active}</SelectOption>
          <SelectOption value="disabled">{t.common.inactive}</SelectOption>
        </Select>
      </div>

      {filtered.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            {t.common.noResults}
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((c) => (
            <Card key={c.id}>
              <CardHeader className="py-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Plug className="h-4 w-4 text-muted-foreground" />
                      <span className="truncate">{c.label}</span>
                    </CardTitle>
                    <p className="text-xs text-muted-foreground mt-1">{c.id}</p>
                  </div>
                  <Switch
                    checked={c.enabled}
                    onCheckedChange={(v) => void applyPatch(c.id, { enabled: v })}
                    disabled={saving}
                  />
                </div>
              </CardHeader>
              <CardContent className="grid gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  {runtimeBadge(c.runtime)}
                  <Badge variant={c.configured ? "secondary" : "outline"} className="text-[10px]">
                    {c.configured ? t.common.configured : t.common.none}
                  </Badge>
                </div>

                {c.runtime?.error_message && (
                  <p className="text-xs text-destructive line-clamp-3">
                    {c.runtime.error_message}
                  </p>
                )}

                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setSelected(c)}
                  className="h-8 text-xs w-full gap-1.5"
                >
                  <Settings2 className="h-3.5 w-3.5" />
                  {t.connectors.configure}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <PluginSlot name="connectors:bottom" />
    </div>
  );
}
