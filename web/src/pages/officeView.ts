import type { OfficeState } from "@/lib/api";

export type AttentionItem = {
  id: string;
  label: string;
  detail: string;
};

export type OfficeMapNode = {
  id: "sessions" | "work" | "automation" | "routing";
  label: string;
  detail: string;
  zone: "entry" | "workbench" | "machine" | "routing";
  count: number;
  health: "ok" | "partial" | "missing" | "error";
  x: number;
  y: number;
};

export type OfficeMapFlow = {
  from: OfficeMapNode["id"];
  to: OfficeMapNode["id"];
  label: string;
  health: OfficeMapNode["health"];
};

export type OfficeSceneObject = {
  id: string;
  roomId: OfficeMapNode["id"];
  kind: "avatar" | "desk" | "machine" | "mail" | "alert";
  label: string;
  detail: string;
  health: OfficeMapNode["health"];
  x: number;
  y: number;
};

export function textField(row: Record<string, unknown>, key: string): string {
  const value = row[key];
  return typeof value === "string" && value.length > 0 ? value : "—";
}

export function numberField(row: Record<string, unknown>, key: string): number | null {
  const value = row[key];
  return typeof value === "number" ? value : null;
}

export function groupByText(rows: Array<Record<string, unknown>>, key: string, fallback = "unknown") {
  return rows.reduce<Record<string, Array<Record<string, unknown>>>>((acc, row) => {
    const value = textField(row, key);
    const group = value === "—" ? fallback : value;
    acc[group] = acc[group] ?? [];
    acc[group].push(row);
    return acc;
  }, {});
}

export function visibleRows<T>(rows: T[], limit: number, expanded: boolean): T[] {
  return expanded ? rows : rows.slice(0, limit);
}

export function buildOfficeMapNodes(state: OfficeState): OfficeMapNode[] {
  const sourceStatus = (id: string): OfficeMapNode["health"] => {
    const status = state.data_sources.find((source) => source.id === id)?.status;
    if (status === "error") return "error";
    if (status === "partial" || status === "unavailable") return "partial";
    if (status === "ok") return "ok";
    return "missing";
  };

  const routingHealth: OfficeMapNode["health"] = state.topics.length > 0 || state.provenance.length > 0 ? "ok" : sourceStatus("topics");

  return [
    {
      id: "sessions",
      label: "Sessions",
      detail: "recent safe session metadata",
      zone: "entry",
      count: state.agents.length,
      health: sourceStatus("sessions"),
      x: 24,
      y: 30,
    },
    {
      id: "work",
      label: "Work",
      detail: "Kanban/task cards without bodies",
      zone: "workbench",
      count: state.work_items.length,
      health: sourceStatus("kanban"),
      x: 70,
      y: 30,
    },
    {
      id: "automation",
      label: "Automation",
      detail: "cron jobs as read-only machines",
      zone: "machine",
      count: state.automations.length,
      health: sourceStatus("cron"),
      x: 24,
      y: 72,
    },
    {
      id: "routing",
      label: "Routing",
      detail: "topic/provenance projection",
      zone: "routing",
      count: state.topics.length + state.provenance.length,
      health: routingHealth,
      x: 70,
      y: 72,
    },
  ];
}

export function buildOfficeMapFlows(nodes: OfficeMapNode[]): OfficeMapFlow[] {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const flowDefs: Array<Omit<OfficeMapFlow, "health">> = [
    { from: "sessions", to: "work", label: "intake to work" },
    { from: "work", to: "automation", label: "work to automation" },
    { from: "automation", to: "routing", label: "automation to routing" },
  ];
  const severity: Record<OfficeMapNode["health"], number> = { ok: 0, missing: 1, partial: 2, error: 3 };
  const healthBySeverity: OfficeMapNode["health"][] = ["ok", "missing", "partial", "error"];

  return flowDefs.map((flow) => {
    const from = byId.get(flow.from);
    const to = byId.get(flow.to);
    const score = Math.max(severity[from?.health ?? "missing"], severity[to?.health ?? "missing"]);
    return { ...flow, health: healthBySeverity[score] };
  });
}

const SCENE_OBJECT_LIMIT = 6;

const SCENE_SLOTS: Record<OfficeMapNode["id"], Array<[number, number]>> = {
  sessions: [[17, 22], [24, 22], [31, 22], [17, 34], [24, 34], [31, 34]],
  work: [[63, 21], [70, 21], [77, 21], [63, 34], [70, 34], [77, 34]],
  automation: [[17, 64], [24, 64], [31, 64], [17, 77], [24, 77], [31, 77]],
  routing: [[63, 64], [70, 64], [77, 64], [63, 77], [70, 77], [77, 77]],
};

const SCENE_ROOM_CONFIG: Record<OfficeMapNode["id"], { kind: OfficeSceneObject["kind"]; singular: string; plural: string; emptyLabel?: string; emptyDetail?: string }> = {
  sessions: { kind: "avatar", singular: "session avatar", plural: "sessions" },
  work: { kind: "desk", singular: "work desk", plural: "work" },
  automation: { kind: "machine", singular: "automation machine", plural: "automations" },
  routing: { kind: "mail", singular: "routing mail", plural: "routes", emptyLabel: "unrouted bucket", emptyDetail: "topic/provenance gap remains explicit" },
};

function roomRows(state: OfficeState, roomId: OfficeMapNode["id"]): Array<Record<string, unknown>> {
  if (roomId === "sessions") return state.agents;
  if (roomId === "work") return state.work_items;
  if (roomId === "automation") return state.automations;
  return [...state.topics, ...state.provenance];
}

export function buildOfficeSceneObjects(state: OfficeState, nodes: OfficeMapNode[]): OfficeSceneObject[] {
  return nodes.flatMap((node) => {
    const config = SCENE_ROOM_CONFIG[node.id];
    const rows = roomRows(state, node.id);
    const slots = SCENE_SLOTS[node.id];
    const visibleRows = rows.slice(0, SCENE_OBJECT_LIMIT);
    const objects = visibleRows.map<OfficeSceneObject>((_, index) => {
      const [x, y] = slots[index];
      return {
        id: `${node.id}-${config.kind}-${index + 1}`,
        roomId: node.id,
        kind: config.kind,
        label: `${config.singular} ${index + 1}`,
        detail: `${node.zone} safe marker`,
        health: node.health,
        x,
        y,
      };
    });

    if (rows.length === 0 && config.emptyLabel) {
      const [x, y] = slots[0];
      objects.push({
        id: `${node.id}-empty`,
        roomId: node.id,
        kind: config.kind,
        label: config.emptyLabel,
        detail: config.emptyDetail ?? `${node.zone} empty marker`,
        health: node.health,
        x,
        y,
      });
    }

    if (rows.length > SCENE_OBJECT_LIMIT) {
      objects.push({
        id: `${node.id}-overflow`,
        roomId: node.id,
        kind: "alert",
        label: `+${rows.length - SCENE_OBJECT_LIMIT} ${config.plural}`,
        detail: "additional safe count hidden from map density",
        health: node.health,
        x: Math.min(node.x + 12, 90),
        y: Math.min(node.y + 11, 88),
      });
    }

    return objects;
  });
}

export function buildOfficeAttentionItems(state: OfficeState): AttentionItem[] {
  const blocked = state.work_items
    .map((item) => ({
      id: `work:${String(item.id)}`,
      label: textField(item, "title"),
      detail: `work item · ${textField(item, "status")}`,
    }))
    .filter((item) => item.detail.includes("blocked"));
  const failedAutomations = state.automations
    .filter(
      (job) => job.last_status === "error" || job.state === "error" || (Array.isArray(job.badges) && job.badges.includes("needs_attention")),
    )
    .map((job) => ({
      id: `automation:${String(job.id)}`,
      label: textField(job, "name"),
      detail: `automation · ${textField(job, "last_status")}`,
    }));
  const sourceWarnings = state.data_sources
    .filter((source) => source.status === "partial" || source.status === "error" || (source.warning_count ?? 0) > 0)
    .map((source) => ({
      id: `source:${source.id}`,
      label: source.id,
      detail: `source · ${source.status}${source.warning_count ? ` · ${source.warning_count} warning(s)` : ""}`,
    }));
  return [...blocked, ...failedAutomations, ...sourceWarnings];
}
