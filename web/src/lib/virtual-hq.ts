export type Confidence = "verified" | "inferred" | "unknown";
export type ErrorState =
  | "none"
  | "source_missing"
  | "stale"
  | "permission_denied"
  | "parse_failed"
  | "not_connected";
export type RedactionState = "safe" | "redacted" | "sensitive_hidden";
export type TruthCategory = "fact" | "inference" | "proposal" | "decision";
export type DataMode = "mock" | "real" | "not_connected";

export type SourceRef = {
  id: string;
  label: string;
  type: "note" | "kanban" | "profile_config" | "system" | "manual" | "api";
  location: string;
  truth: TruthCategory;
  dataMode: DataMode;
  updatedAt: string;
  confidence: Confidence;
  errorState: ErrorState;
  redactionState: RedactionState;
};

export type EvidenceRef = {
  evidenceId: string;
  type: "test_log" | "screenshot" | "pr" | "ci" | "note" | "deploy_log" | "manual_check";
  title: string;
  sourcePathOrUrl: string;
  capturedAt: string;
  verifiedBy: string;
  redactionState: RedactionState;
  sourceRefs: string[];
};

export type AgentStatus = {
  agentId: string;
  displayName: string;
  role: string;
  profileName: string;
  homeTopic: string;
  allowedTopics: string[];
  state: "active" | "idle" | "waiting_approval" | "blocked" | "unknown";
  currentFocus: string;
  lastOutputSummary: string;
  sourceRefs: string[];
  updatedAt: string;
  confidence: Confidence;
  errorState: ErrorState;
  redactionState: RedactionState;
  dataMode: DataMode;
};

export type ProjectStatus = {
  projectId: string;
  name: string;
  phase: string;
  ownerAgent: string;
  state: "planned" | "active" | "review" | "waiting_approval" | "done" | "blocked";
  nextAction: string;
  evidenceRefs: string[];
  blockerReason: string | null;
  sourceRefs: string[];
  updatedAt: string;
  confidence: Confidence;
  errorState: ErrorState;
  redactionState: RedactionState;
  dataMode: DataMode;
};

export type ApprovalItem = {
  approvalId: string;
  decisionNeeded: string;
  contextSummary: string;
  recommendation: string;
  options: string[];
  riskLevel: "low" | "medium" | "high" | "critical";
  impact: string;
  evidenceRefs: string[];
  status: "candidate" | "requested" | "approved" | "rejected" | "needs_more_info";
  sourceRefs: string[];
  updatedAt: string;
  confidence: Confidence;
  errorState: ErrorState;
  redactionState: RedactionState;
  dataMode: DataMode;
};

export type ContextPack = {
  contextId: string;
  scope: "project" | "topic" | "agent" | "customer";
  summary: string;
  mustKnow: string[];
  constraints: string[];
  activeDecisions: string[];
  sourceRefs: string[];
  freshness: "fresh" | "stale" | "missing";
  staleAfter: string;
  updatedAt: string;
  confidence: Confidence;
  errorState: ErrorState;
  redactionState: RedactionState;
  dataMode: DataMode;
};

export type SystemStatus = {
  serviceId: string;
  displayName: string;
  state: "healthy" | "degraded" | "down" | "unknown";
  lastCheckAt: string;
  errorState: ErrorState;
  sourceRefs: string[];
  redactionState: RedactionState;
  confidence: Confidence;
  dataMode: DataMode;
};

export type ProductZone = {
  id: string;
  name: string;
  panel: string;
  purpose: string;
  scope: "P0" | "P1";
  sourceRefs: string[];
};

export type VirtualHqData = {
  generatedAt: string;
  sourceRegistry: SourceRef[];
  productZones: ProductZone[];
  agents: AgentStatus[];
  projects: ProjectStatus[];
  approvals: ApprovalItem[];
  evidence: EvidenceRef[];
  contextPacks: ContextPack[];
  systems: SystemStatus[];
};

export const sourceRegistry: SourceRef[] = [
  {
    id: "plan-r1",
    label: "R1 approved dev task plan",
    type: "note",
    location: "TEAM-Knowledge/02-Projects/Hermes-Virtual-HQ/Hermes-Virtual-HQ-Dev-Task-Plan-5-Rounds-2026-05-31.md",
    truth: "decision",
    dataMode: "real",
    updatedAt: "2026-05-31T22:55:00+07:00",
    confidence: "verified",
    errorState: "none",
    redactionState: "safe",
  },
  {
    id: "roadmap-draft",
    label: "Agent HQ roadmap draft and data contracts",
    type: "note",
    location: "TEAM-Knowledge/80-Meetings/Hermes-Virtual-HQ/Hermes-Virtual-HQ-Full-Development-Roadmap-Agent-HQ-Draft-2026-05-31.md",
    truth: "proposal",
    dataMode: "real",
    updatedAt: "2026-05-31T19:58:00+07:00",
    confidence: "verified",
    errorState: "none",
    redactionState: "safe",
  },
  {
    id: "kanban-r1-dev",
    label: "Kanban R1 dev card",
    type: "kanban",
    location: "t_edfb9720",
    truth: "fact",
    dataMode: "real",
    updatedAt: "2026-05-31T23:00:00+07:00",
    confidence: "verified",
    errorState: "none",
    redactionState: "safe",
  },
  {
    id: "runtime-profile-status",
    label: "Live Hermes profile runtime status adapter",
    type: "profile_config",
    location: "adapter pending read-only connection",
    truth: "fact",
    dataMode: "not_connected",
    updatedAt: "2026-05-31T23:00:00+07:00",
    confidence: "unknown",
    errorState: "not_connected",
    redactionState: "sensitive_hidden",
  },
  {
    id: "system-health-adapter",
    label: "Dashboard/gateway/system health adapter",
    type: "system",
    location: "adapter pending read-only connection",
    truth: "fact",
    dataMode: "not_connected",
    updatedAt: "2026-05-31T23:00:00+07:00",
    confidence: "unknown",
    errorState: "not_connected",
    redactionState: "sensitive_hidden",
  },
];

export const virtualHqData: VirtualHqData = {
  generatedAt: "2026-05-31T23:00:00+07:00",
  sourceRegistry,
  productZones: [
    {
      id: "agent-desks",
      name: "Agent Desks",
      panel: "Agent Status Board",
      purpose: "Show each assistant role, lane, focus, last known output, and safe unknown states.",
      scope: "P1",
      sourceRefs: ["plan-r1", "roadmap-draft"],
    },
    {
      id: "project-board",
      name: "Project Board",
      panel: "Project Status Board",
      purpose: "Separate active, review, waiting approval, blocked, and done-with-evidence work.",
      scope: "P1",
      sourceRefs: ["plan-r1", "kanban-r1-dev"],
    },
    {
      id: "approval-desk",
      name: "Approval Desk",
      panel: "Read-only Approval Queue",
      purpose: "Expose decision candidates with recommendation, alternatives, risk, impact, and evidence.",
      scope: "P1",
      sourceRefs: ["plan-r1", "roadmap-draft"],
    },
    {
      id: "evidence-panel",
      name: "Evidence Panel",
      panel: "Evidence Drawer",
      purpose: "Show redacted evidence references behind status and decision claims.",
      scope: "P1",
      sourceRefs: ["roadmap-draft"],
    },
    {
      id: "context-wall",
      name: "Context Wall",
      panel: "Context Pack Drawer",
      purpose: "Keep must-know facts, constraints, and active decisions visible without durable auto-memory writes.",
      scope: "P1",
      sourceRefs: ["roadmap-draft"],
    },
    {
      id: "command-wall",
      name: "Command Wall",
      panel: "System Status Panel",
      purpose: "Show service and integration health as read-only status with missing/not_connected labels.",
      scope: "P1",
      sourceRefs: ["roadmap-draft", "system-health-adapter"],
    },
  ],
  agents: [
    {
      agentId: "nongfah",
      displayName: "NongFah",
      role: "Coordinator, product planning, meeting moderator, final gate owner",
      profileName: "default",
      homeTopic: "Business-Fah / approval coordination",
      allowedTopics: ["General", "Business-Fah", "Approval", "Development Team"],
      state: "waiting_approval",
      currentFocus: "R1 scope approved for dev; final gate comes after Venice QA.",
      lastOutputSummary: "Created the 5-round task chain and assigned R1 dev to PaCode.",
      sourceRefs: ["plan-r1", "kanban-r1-dev"],
      updatedAt: "2026-05-31T22:59:00+07:00",
      confidence: "verified",
      errorState: "none",
      redactionState: "safe",
      dataMode: "real",
    },
    {
      agentId: "pacode",
      displayName: "PaCode",
      role: "Development and implementation owner",
      profileName: "pacode",
      homeTopic: "Development Team",
      allowedTopics: ["Development Team"],
      state: "active",
      currentFocus: "R1 P0+P1 read-only operational HQ MVP.",
      lastOutputSummary: "Implementing source registry, safe panels, and read-only data contracts.",
      sourceRefs: ["kanban-r1-dev"],
      updatedAt: "2026-05-31T23:00:00+07:00",
      confidence: "verified",
      errorState: "none",
      redactionState: "safe",
      dataMode: "real",
    },
    {
      agentId: "nonglily",
      displayName: "NongLily",
      role: "Investment perspective and memory/context input where relevant",
      profileName: "lily",
      homeTopic: "Investment-Lily",
      allowedTopics: ["Investment-Lily"],
      state: "unknown",
      currentFocus: "unknown — live profile adapter is not connected in R1.",
      lastOutputSummary: "Not connected; no fabricated activity shown.",
      sourceRefs: ["runtime-profile-status"],
      updatedAt: "2026-05-31T23:00:00+07:00",
      confidence: "unknown",
      errorState: "not_connected",
      redactionState: "sensitive_hidden",
      dataMode: "not_connected",
    },
    {
      agentId: "venice",
      displayName: "Venice",
      role: "QA, review, acceptance criteria, evidence and risk checks",
      profileName: "venice",
      homeTopic: "QA lane",
      allowedTopics: ["Development Team", "Approval"],
      state: "idle",
      currentFocus: "Waiting for PaCode R1 handoff.",
      lastOutputSummary: "QA will verify source/timestamp/error/confidence labels and no side-effect controls.",
      sourceRefs: ["plan-r1"],
      updatedAt: "2026-05-31T22:55:00+07:00",
      confidence: "inferred",
      errorState: "none",
      redactionState: "safe",
      dataMode: "real",
    },
  ],
  projects: [
    {
      projectId: "hermes-virtual-hq",
      name: "Hermes Virtual HQ",
      phase: "R1 — P0 + P1",
      ownerAgent: "PaCode",
      state: "active",
      nextAction: "Venice QA after read-only MVP verification.",
      evidenceRefs: ["ev-r1-plan", "ev-r1-qa-checklist"],
      blockerReason: null,
      sourceRefs: ["plan-r1", "kanban-r1-dev"],
      updatedAt: "2026-05-31T23:00:00+07:00",
      confidence: "verified",
      errorState: "none",
      redactionState: "safe",
      dataMode: "real",
    },
    {
      projectId: "future-rag-layer",
      name: "RAG / AI Second Brain",
      phase: "R4 proposal only",
      ownerAgent: "future",
      state: "planned",
      nextAction: "Do not start until R1-R3 gates pass and explicit approval is recorded.",
      evidenceRefs: [],
      blockerReason: null,
      sourceRefs: ["roadmap-draft"],
      updatedAt: "2026-05-31T19:58:00+07:00",
      confidence: "verified",
      errorState: "source_missing",
      redactionState: "safe",
      dataMode: "real",
    },
  ],
  approvals: [
    {
      approvalId: "r1-final-gate",
      decisionNeeded: "Fah/default final review after Venice QA PASS",
      contextSummary: "R1 dev is authorized; later rounds remain gated.",
      recommendation: "Keep R1 read-only and require QA evidence before final merge/release decision.",
      options: ["Approve R1 after QA PASS", "Request fixes", "Hold later rounds"],
      riskLevel: "medium",
      impact: "Prevents unsafe execute controls and mock data being mistaken for live system truth.",
      evidenceRefs: ["ev-r1-plan", "ev-r1-qa-checklist"],
      status: "candidate",
      sourceRefs: ["plan-r1"],
      updatedAt: "2026-05-31T22:55:00+07:00",
      confidence: "verified",
      errorState: "none",
      redactionState: "safe",
      dataMode: "real",
    },
  ],
  evidence: [
    {
      evidenceId: "ev-r1-plan",
      type: "note",
      title: "Approved R1 task plan and scope boundary",
      sourcePathOrUrl: "TEAM-Knowledge/02-Projects/Hermes-Virtual-HQ/Hermes-Virtual-HQ-Dev-Task-Plan-5-Rounds-2026-05-31.md",
      capturedAt: "2026-05-31T22:55:00+07:00",
      verifiedBy: "NongFah",
      redactionState: "safe",
      sourceRefs: ["plan-r1"],
    },
    {
      evidenceId: "ev-r1-qa-checklist",
      type: "manual_check",
      title: "R1 QA checklist: labels, unknown/not_connected, no controls, no secrets",
      sourcePathOrUrl: "Kanban child QA card t_d31db186",
      capturedAt: "2026-05-31T23:00:00+07:00",
      verifiedBy: "pending Venice QA",
      redactionState: "safe",
      sourceRefs: ["kanban-r1-dev"],
    },
  ],
  contextPacks: [
    {
      contextId: "hvhq-r1-context",
      scope: "project",
      summary: "R1 locks product zones, schemas, source registry, mock/real boundary, and read-only operations panels.",
      mustKnow: [
        "Reference image is inspiration only, not literal layout.",
        "R1 is read-only; no restart, deploy, merge, config edit, durable memory write, or external send controls.",
        "Unknown/not_connected must be shown when adapters are not connected.",
      ],
      constraints: [
        "No secrets/raw logs/local private data in UI.",
        "Later R2-R5 capabilities remain out of scope until gated approval.",
        "Done/pass states require evidence refs.",
      ],
      activeDecisions: [
        "Use real team roles: NongFah, PaCode, NongLily, Venice, plus future expansion zones.",
        "Venice QA is required before Fah/default final gate.",
      ],
      sourceRefs: ["plan-r1", "roadmap-draft"],
      freshness: "fresh",
      staleAfter: "2026-06-07T23:00:00+07:00",
      updatedAt: "2026-05-31T23:00:00+07:00",
      confidence: "verified",
      errorState: "none",
      redactionState: "safe",
      dataMode: "real",
    },
  ],
  systems: [
    {
      serviceId: "hermes-dashboard",
      displayName: "Hermes Dashboard",
      state: "unknown",
      lastCheckAt: "2026-05-31T23:00:00+07:00",
      errorState: "not_connected",
      sourceRefs: ["system-health-adapter"],
      redactionState: "sensitive_hidden",
      confidence: "unknown",
      dataMode: "not_connected",
    },
    {
      serviceId: "telegram-gateway",
      displayName: "Telegram Gateway",
      state: "unknown",
      lastCheckAt: "2026-05-31T23:00:00+07:00",
      errorState: "not_connected",
      sourceRefs: ["system-health-adapter"],
      redactionState: "sensitive_hidden",
      confidence: "unknown",
      dataMode: "not_connected",
    },
    {
      serviceId: "team-knowledge",
      displayName: "TEAM-Knowledge notes",
      state: "healthy",
      lastCheckAt: "2026-05-31T22:55:00+07:00",
      errorState: "none",
      sourceRefs: ["plan-r1", "roadmap-draft"],
      redactionState: "safe",
      confidence: "verified",
      dataMode: "real",
    },
  ],
};

export function getSourceRefs(ids: string[]): SourceRef[] {
  const byId = new Map(sourceRegistry.map((source) => [source.id, source]));
  return ids.map((id) => byId.get(id)).filter((source): source is SourceRef => Boolean(source));
}
