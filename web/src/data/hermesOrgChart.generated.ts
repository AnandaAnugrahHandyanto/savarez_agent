/* AUTO-GENERATED FILE. DO NOT EDIT DIRECTLY. */
/* Source: hermesOrgChart.registry.yaml */
import type { LucideIcon } from "lucide-react";
import {
  Crown,
  Compass,
  LayoutTemplate,
  Wrench,
  ShieldCheck,
  ClipboardCheck,
  Briefcase,
  Cpu,
  Smartphone,
  Gauge,
  GitPullRequest
} from "lucide-react";

export type ExecutionMode = "persistent_role_instance" | "delegated_subagent" | "scheduled_role_run" | "inline_lead_exception";
export type WorktreeStrategy = "shared" | "isolated_if_coding" | "isolated_required";

export interface RuntimePolicy {
  default_execution_mode: ExecutionMode;
  allowed_execution_modes: ExecutionMode[];
  requires_independent_session: boolean;
  requires_artifact_handoff: boolean;
  lead_coordinates_feedback: boolean;
  lead_review_required_before_next_handoff: boolean;
  requires_revalidation_after_fix: boolean;
  worktree_strategy: WorktreeStrategy;
}

export interface OrgRole {
  title: string;
  position: string;
  mission: string;
  responsibilities: string[];
  activation: string;
  reportsTo: string;
  model: string;
  toolFocus: string[];
  invokeFor: string[];
  icon: LucideIcon;
  tone?: "default" | "success" | "warning";
  runtimePolicy: RuntimePolicy;
}

export interface OrgSection {
  id: string;
  title: string;
  description: string;
  lane: string;
  roles: OrgRole[];
}

export interface InvokeRow {
  trigger: string;
  primary: string;
  supporting: string[];
  verification: string;
}

export interface VerificationLevel {
  id: string;
  label: string;
  detail: string;
}

export const LEAD_ROLE: OrgRole = {
  title: "Lead / PM",
  position: "Executive lead",
  mission: "Own the workflow end to end: routing, planning, user communication, specialist orchestration, validation gates, verification gates, and final completion authority.",
  responsibilities: [
    "Translate user requests into the working plan and communicate only the essential phase changes.",
    "Choose specialists, enforce plan approval, and keep work moving autonomously.",
    "Prevent premature completion when validation, verification, or evidence is still missing."
  ],
  activation: "Always active. Every workflow reports through this role.",
  reportsTo: "User",
  model: "Latest GPT (auto)",
  toolFocus: [
    "planning",
    "delegation",
    "verification gating"
  ],
  invokeFor: [
    "all work orchestration",
    "user communication",
    "final completion decisions"
  ],
  icon: Crown,
  tone: "success",
  runtimePolicy: {
    default_execution_mode: "persistent_role_instance",
    allowed_execution_modes: [
      "persistent_role_instance"
    ],
    requires_independent_session: true,
    requires_artifact_handoff: true,
    lead_coordinates_feedback: true,
    lead_review_required_before_next_handoff: true,
    requires_revalidation_after_fix: true,
    worktree_strategy: "shared"
  }
};

export const ROLE_ALIASES: Record<string, string[]> = {
  Planner: [
    "Discovery / Content Inventory Specialist",
    "Website Information Architecture Specialist",
    "Voice / Content Strategy Specialist"
  ],
  Developer: [
    "Website Platform Developer",
    "Phase 1 Finisher Developer"
  ]
};

export const ORG_SECTIONS: OrgSection[] = [
  {
    id: "planning",
    title: "Planning & intake",
    lane: "Staff line",
    description: "Front-door roles that classify work, shape the plan, and prepare approval-ready execution.",
    roles: [
      {
        title: "Intake / Routing",
        position: "Operations intake",
        mission: "Classify each request and identify the correct execution lane before any implementation starts.",
        responsibilities: [
          "Classify work as feature, bug, UI/UX, contract, native, performance, release, or incident.",
          "Identify impacted product surfaces such as Kinni, API, Account, or cross-surface.",
          "Decide what validation and verification level is required."
        ],
        activation: "Used at the start of every task before planning begins.",
        reportsTo: "Lead / PM",
        model: "Latest GPT (auto)",
        toolFocus: [
          "repo docs",
          "issue context",
          "routing rules"
        ],
        invokeFor: [
          "issue triage",
          "initial scope",
          "verification level choice"
        ],
        icon: Compass,
        runtimePolicy: {
          default_execution_mode: "persistent_role_instance",
          allowed_execution_modes: [
            "persistent_role_instance",
            "delegated_subagent",
            "scheduled_role_run"
          ],
          requires_independent_session: true,
          requires_artifact_handoff: true,
          lead_coordinates_feedback: true,
          lead_review_required_before_next_handoff: true,
          requires_revalidation_after_fix: false,
          worktree_strategy: "shared"
        }
      },
      {
        title: "Planner",
        position: "Planning lead",
        mission: "Turn routed work into an approval-ready plan with clear scope, validation, and verification gates.",
        responsibilities: [
          "Define scope boundaries, acceptance criteria, and task decomposition.",
          "List commands, manual checks, risks, evidence, and rollback notes.",
          "Prepare the explicit plan approval checkpoint before implementation begins."
        ],
        activation: "Used whenever work needs an explicit approved plan before execution.",
        reportsTo: "Lead / PM",
        model: "Latest GPT (auto)",
        toolFocus: [
          "plans",
          "acceptance criteria",
          "validation gates"
        ],
        invokeFor: [
          "plan drafting",
          "acceptance criteria",
          "execution sequencing"
        ],
        icon: LayoutTemplate,
        runtimePolicy: {
          default_execution_mode: "persistent_role_instance",
          allowed_execution_modes: [
            "persistent_role_instance",
            "delegated_subagent",
            "scheduled_role_run"
          ],
          requires_independent_session: true,
          requires_artifact_handoff: true,
          lead_coordinates_feedback: true,
          lead_review_required_before_next_handoff: true,
          requires_revalidation_after_fix: true,
          worktree_strategy: "shared"
        }
      }
    ]
  },
  {
    id: "delivery",
    title: "Delivery & quality",
    lane: "Core execution",
    description: "Roles that implement the approved work, prove it technically, and collect user-facing evidence.",
    roles: [
      {
        title: "Developer",
        position: "Implementation specialist",
        mission: "Build the approved change without drifting from the agreed scope.",
        responsibilities: [
          "Edit code and configuration on the approved branch or worktree.",
          "Follow repo conventions, file ownership, and plan boundaries.",
          "Produce concrete artifacts for validation and audit."
        ],
        activation: "Used after plan approval for implementation tasks.",
        reportsTo: "Lead / PM",
        model: "Latest GPT (auto)",
        toolFocus: [
          "code changes",
          "tests",
          "local verification"
        ],
        invokeFor: [
          "feature work",
          "bug fixes",
          "refactors within scope"
        ],
        icon: Wrench,
        runtimePolicy: {
          default_execution_mode: "persistent_role_instance",
          allowed_execution_modes: [
            "persistent_role_instance",
            "delegated_subagent",
            "scheduled_role_run"
          ],
          requires_independent_session: true,
          requires_artifact_handoff: true,
          lead_coordinates_feedback: true,
          lead_review_required_before_next_handoff: true,
          requires_revalidation_after_fix: true,
          worktree_strategy: "isolated_required"
        }
      },
      {
        title: "Technical Validator",
        position: "Quality gate",
        mission: "Prove the change passes required automated and technical checks.",
        responsibilities: [
          "Run tests, lint, type-checks, smoke scripts, and other technical gates.",
          "Separate true regressions from pre-existing baseline failures.",
          "Block sign-off if validation is incomplete or red."
        ],
        activation: "Used whenever behavior, code, or configuration changes.",
        reportsTo: "Lead / PM",
        model: "Latest GPT (auto)",
        toolFocus: [
          "tests",
          "lint",
          "type-check",
          "smoke scripts"
        ],
        invokeFor: [
          "pre-merge validation",
          "regression checks",
          "quality gates"
        ],
        icon: ShieldCheck,
        tone: "success",
        runtimePolicy: {
          default_execution_mode: "persistent_role_instance",
          allowed_execution_modes: [
            "persistent_role_instance",
            "delegated_subagent",
            "scheduled_role_run"
          ],
          requires_independent_session: true,
          requires_artifact_handoff: true,
          lead_coordinates_feedback: true,
          lead_review_required_before_next_handoff: true,
          requires_revalidation_after_fix: true,
          worktree_strategy: "isolated_if_coding"
        }
      },
      {
        title: "UX / Evidence Auditor",
        position: "Verification and evidence",
        mission: "Confirm the user-facing result and assemble the proof needed for completion.",
        responsibilities: [
          "Audit screenshots, recordings, and manual QA evidence.",
          "Check reuse, state coverage, accessibility notes, and UX expectations.",
          "Ensure required issue/MR evidence blocks are complete before sign-off."
        ],
        activation: "Used for user-facing work and whenever evidence must be collected.",
        reportsTo: "Lead / PM",
        model: "Latest GPT (auto)",
        toolFocus: [
          "screenshots",
          "manual QA",
          "artifacts"
        ],
        invokeFor: [
          "UI changes",
          "manual verification",
          "handoff proof"
        ],
        icon: ClipboardCheck,
        runtimePolicy: {
          default_execution_mode: "persistent_role_instance",
          allowed_execution_modes: [
            "persistent_role_instance",
            "delegated_subagent",
            "scheduled_role_run"
          ],
          requires_independent_session: true,
          requires_artifact_handoff: true,
          lead_coordinates_feedback: true,
          lead_review_required_before_next_handoff: true,
          requires_revalidation_after_fix: true,
          worktree_strategy: "isolated_if_coding"
        }
      }
    ]
  },
  {
    id: "specialists",
    title: "Specialist bench",
    lane: "On-demand experts",
    description: "Specialists the Lead activates when the task carries release, contract, device, or performance risk.",
    roles: [
      {
        title: "Release Manager",
        position: "Release specialist",
        mission: "Handle release readiness, sequencing, and release-specific obligations.",
        responsibilities: [
          "Review release playbooks, checklists, and gating criteria.",
          "Track merge state and release-specific evidence."
        ],
        activation: "Used for release, deployment, and merge-sensitive work.",
        reportsTo: "Lead / PM",
        model: "Latest GPT (auto)",
        toolFocus: [
          "release docs",
          "merge state",
          "handoff artifacts"
        ],
        invokeFor: [
          "release prep",
          "merge readiness",
          "deployment coordination"
        ],
        icon: Briefcase,
        runtimePolicy: {
          default_execution_mode: "persistent_role_instance",
          allowed_execution_modes: [
            "persistent_role_instance",
            "delegated_subagent",
            "scheduled_role_run"
          ],
          requires_independent_session: true,
          requires_artifact_handoff: true,
          lead_coordinates_feedback: true,
          lead_review_required_before_next_handoff: true,
          requires_revalidation_after_fix: true,
          worktree_strategy: "isolated_if_coding"
        }
      },
      {
        title: "Contract Specialist",
        position: "API / schema specialist",
        mission: "Protect interface and schema correctness across product surfaces.",
        responsibilities: [
          "Review API contracts, codegen requirements, and schema compatibility.",
          "Catch breaking changes before merge."
        ],
        activation: "Used for GraphQL, API, schema, or shared contract changes.",
        reportsTo: "Lead / PM",
        model: "Latest GPT (auto)",
        toolFocus: [
          "contracts",
          "schema",
          "codegen"
        ],
        invokeFor: [
          "API changes",
          "schema work",
          "cross-surface contract checks"
        ],
        icon: Cpu,
        runtimePolicy: {
          default_execution_mode: "persistent_role_instance",
          allowed_execution_modes: [
            "persistent_role_instance",
            "delegated_subagent",
            "scheduled_role_run"
          ],
          requires_independent_session: true,
          requires_artifact_handoff: true,
          lead_coordinates_feedback: true,
          lead_review_required_before_next_handoff: true,
          requires_revalidation_after_fix: true,
          worktree_strategy: "isolated_if_coding"
        }
      },
      {
        title: "Native / Device Validation Specialist",
        position: "Platform specialist",
        mission: "Verify mobile or native behavior in the correct environment and target platform.",
        responsibilities: [
          "Run environment-specific checks for Android, iOS, watch, treadmill, or peripheral flows.",
          "Confirm the correct device target and environment are in use."
        ],
        activation: "Used for native, platform, peripheral, and device-sensitive work.",
        reportsTo: "Lead / PM",
        model: "Latest GPT (auto)",
        toolFocus: [
          "adb",
          "devices",
          "platform smoke tests"
        ],
        invokeFor: [
          "mobile flows",
          "device-sensitive changes",
          "platform-specific issues"
        ],
        icon: Smartphone,
        runtimePolicy: {
          default_execution_mode: "persistent_role_instance",
          allowed_execution_modes: [
            "persistent_role_instance",
            "delegated_subagent",
            "scheduled_role_run"
          ],
          requires_independent_session: true,
          requires_artifact_handoff: true,
          lead_coordinates_feedback: true,
          lead_review_required_before_next_handoff: true,
          requires_revalidation_after_fix: true,
          worktree_strategy: "isolated_if_coding"
        }
      },
      {
        title: "Performance Specialist",
        position: "Performance specialist",
        mission: "Investigate latency, throughput, rendering, and resource regressions.",
        responsibilities: [
          "Profile slow paths, bottlenecks, and regressions.",
          "Validate performance-specific fixes and proof."
        ],
        activation: "Used when speed, stability, or efficiency is part of scope.",
        reportsTo: "Lead / PM",
        model: "Latest GPT (auto)",
        toolFocus: [
          "profiling",
          "metrics",
          "regression analysis"
        ],
        invokeFor: [
          "slow UI",
          "latency problems",
          "performance regressions"
        ],
        icon: Gauge,
        runtimePolicy: {
          default_execution_mode: "persistent_role_instance",
          allowed_execution_modes: [
            "persistent_role_instance",
            "delegated_subagent",
            "scheduled_role_run"
          ],
          requires_independent_session: true,
          requires_artifact_handoff: true,
          lead_coordinates_feedback: true,
          lead_review_required_before_next_handoff: true,
          requires_revalidation_after_fix: true,
          worktree_strategy: "isolated_if_coding"
        }
      },
      {
        title: "Physical Device Verification Specialist",
        position: "Real-world verifier",
        mission: "Provide the highest-confidence proof on actual target hardware.",
        responsibilities: [
          "Run required V4 checks on the real device instead of stopping at emulators or reasoning.",
          "Report coverage honestly when only a smoke pass was performed."
        ],
        activation: "Used when the verification level requires physical-device proof.",
        reportsTo: "Lead / PM",
        model: "Latest GPT (auto)",
        toolFocus: [
          "physical devices",
          "real-world verification",
          "coverage"
        ],
        invokeFor: [
          "V4 verification",
          "hardware proof",
          "final device sign-off"
        ],
        icon: Smartphone,
        tone: "warning",
        runtimePolicy: {
          default_execution_mode: "persistent_role_instance",
          allowed_execution_modes: [
            "persistent_role_instance",
            "delegated_subagent",
            "scheduled_role_run"
          ],
          requires_independent_session: true,
          requires_artifact_handoff: true,
          lead_coordinates_feedback: true,
          lead_review_required_before_next_handoff: true,
          requires_revalidation_after_fix: true,
          worktree_strategy: "isolated_if_coding"
        }
      },
      {
        title: "GitLab / Artifact Steward",
        position: "Delivery operations",
        mission: "Keep GitLab issues, MRs, and delivery artifacts complete and accurate.",
        responsibilities: [
          "Check issue/MR formatting, required sections, and supporting evidence blocks.",
          "Track merge-pending state until GitLab confirms merged."
        ],
        activation: "Used for issue triage, merge requests, release notes, and final handoff packaging.",
        reportsTo: "Lead / PM",
        model: "Latest GPT (auto)",
        toolFocus: [
          "GitLab",
          "MRs",
          "delivery evidence"
        ],
        invokeFor: [
          "MR packaging",
          "artifact completeness",
          "merge state tracking"
        ],
        icon: GitPullRequest,
        runtimePolicy: {
          default_execution_mode: "persistent_role_instance",
          allowed_execution_modes: [
            "persistent_role_instance",
            "delegated_subagent",
            "scheduled_role_run"
          ],
          requires_independent_session: true,
          requires_artifact_handoff: true,
          lead_coordinates_feedback: true,
          lead_review_required_before_next_handoff: true,
          requires_revalidation_after_fix: true,
          worktree_strategy: "isolated_if_coding"
        }
      }
    ]
  }
];

export const WORKFLOW_STEPS = [
  "Route the request",
  "Draft and review the plan",
  "Get approval before implementation",
  "Implement via specialists",
  "Validate technically",
  "Verify and collect evidence",
  "Close only when fully complete"
];

export const VERIFICATION_LEVELS: VerificationLevel[] = [
  {
    id: "V1",
    label: "Logical verification",
    detail: "Reasoning and implementation logic checks."
  },
  {
    id: "V2",
    label: "Workflow verification",
    detail: "End-to-end flow proof in the intended workflow."
  },
  {
    id: "V3",
    label: "Platform / environment",
    detail: "Correct behavior in the required runtime environment."
  },
  {
    id: "V4",
    label: "Physical device",
    detail: "Real hardware proof on the actual target device."
  }
];

export const INVOKE_MATRIX: InvokeRow[] = [
  {
    trigger: "New GitLab issue or vague request",
    primary: "Intake / Routing",
    supporting: [
      "Planner",
      "Lead / PM"
    ],
    verification: "Choose V1–V4 up front"
  },
  {
    trigger: "Need an approval-ready execution plan",
    primary: "Planner",
    supporting: [
      "Intake / Routing",
      "Lead / PM"
    ],
    verification: "Define validation + verification gates"
  },
  {
    trigger: "Feature or bug implementation",
    primary: "Developer",
    supporting: [
      "Technical Validator",
      "Lead / PM"
    ],
    verification: "V1/V2 minimum unless scope raises it"
  },
  {
    trigger: "UI changes needing screenshots or manual QA",
    primary: "UX / Evidence Auditor",
    supporting: [
      "Developer",
      "Technical Validator"
    ],
    verification: "Usually V2 or V3"
  },
  {
    trigger: "API/schema/contract changes",
    primary: "Contract Specialist",
    supporting: [
      "Developer",
      "Technical Validator"
    ],
    verification: "V2/V3 depending on affected consumers"
  },
  {
    trigger: "Android/iOS/device-sensitive work",
    primary: "Native / Device Validation Specialist",
    supporting: [
      "Physical Device Verification Specialist",
      "Developer"
    ],
    verification: "V3 or V4"
  },
  {
    trigger: "Release, MR readiness, merge tracking",
    primary: "Release Manager",
    supporting: [
      "GitLab / Artifact Steward",
      "Lead / PM"
    ],
    verification: "Artifact + merge-state proof"
  },
  {
    trigger: "Slowdowns, performance regressions",
    primary: "Performance Specialist",
    supporting: [
      "Developer",
      "Technical Validator"
    ],
    verification: "Metrics-backed V2/V3"
  }
];

export const DEFAULT_OPEN_SECTIONS: Record<string, boolean> = Object.fromEntries(
  ORG_SECTIONS.map((section) => [section.id, true]),
);
