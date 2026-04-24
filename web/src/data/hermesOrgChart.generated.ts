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

export interface RoleSkillTrigger {
  skill: string;
  when: string;
}

export interface RoleSkillPolicy {
  required: string[];
  recommended?: string[];
  triggered?: RoleSkillTrigger[];
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
  skills: RoleSkillPolicy;
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
  },
  skills: {
    required: [
      "hermes-lead-workflow",
      "hermes-role-team-runtime",
      "repo-grounded-plan-review",
      "audit-change-followups",
      "manage-gitlab-work-items"
    ],
    recommended: [
      "run-required-validation",
      "pre-commit-qc",
      "update-docs-and-runbooks",
      "requesting-code-review"
    ],
    triggered: [
      {
        skill: "triage-release-pipeline",
        when: "release pipeline state is blocked, failed, skipped, or ambiguous"
      },
      {
        skill: "kinni-migration-plan-refinement",
        when: "broad Kinni/NoblePro planning or migration work is requested"
      }
    ]
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
        },
        skills: {
          required: [
            "repo-grounded-plan-review",
            "noblepro-gitlab-bug-triage",
            "audit-change-followups"
          ],
          recommended: [
            "manage-gitlab-work-items",
            "run-required-validation"
          ],
          triggered: [
            {
              skill: "change-graphql-contract",
              when: "GraphQL, API, schema, resolver, generated type, or client operation changes are involved"
            },
            {
              skill: "change-native-update-gate",
              when: "native version gate, force-update, app version compatibility, or release policy is involved"
            },
            {
              skill: "implement-ui-ux-change",
              when: "Kinni or Account user-facing UI/UX is involved"
            },
            {
              skill: "upgrade-expo-sdk",
              when: "Expo, EAS, native modules, config plugins, or SDK migration is involved"
            },
            {
              skill: "stripe-best-practices",
              when: "Stripe, payment, subscription, billing, or Connect behavior is involved"
            }
          ]
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
        },
        skills: {
          required: [
            "writing-plans",
            "plan",
            "repo-grounded-plan-review",
            "hermes-role-team-runtime"
          ],
          recommended: [
            "run-required-validation",
            "audit-change-followups",
            "update-docs-and-runbooks"
          ],
          triggered: [
            {
              skill: "implement-ui-ux-change",
              when: "planning user-facing UI work"
            },
            {
              skill: "change-graphql-contract",
              when: "planning API, schema, or contract work"
            },
            {
              skill: "change-native-update-gate",
              when: "planning native gate or force-update work"
            },
            {
              skill: "upgrade-expo-sdk",
              when: "planning Expo or native upgrade work"
            },
            {
              skill: "run-beta-ota-release",
              when: "planning a beta OTA release"
            },
            {
              skill: "run-beta-native-release",
              when: "planning a beta native release"
            },
            {
              skill: "run-production-ota-release",
              when: "planning a production OTA release"
            },
            {
              skill: "run-production-native-release",
              when: "planning a production native release"
            }
          ]
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
        },
        skills: {
          required: [
            "test-driven-development",
            "systematic-debugging"
          ],
          recommended: [
            "subagent-driven-development",
            "run-required-validation"
          ],
          triggered: [
            {
              skill: "implement-ui-ux-change",
              when: "Kinni or Account UI/user-facing behavior changes"
            },
            {
              skill: "change-graphql-contract",
              when: "GraphQL schema, resolver, codegen, or client operations change"
            },
            {
              skill: "change-native-update-gate",
              when: "native gate or force-update behavior changes"
            },
            {
              skill: "upgrade-expo-sdk",
              when: "Expo, EAS, native modules, config plugins, or SDK migration changes"
            },
            {
              skill: "stripe-best-practices",
              when: "Stripe integration, payment, subscription, billing, or Connect behavior changes"
            },
            {
              skill: "stripe-projects",
              when: "setting up Stripe Projects or provisioning stack"
            },
            {
              skill: "upgrade-stripe",
              when: "Stripe API version or SDK upgrade work is involved"
            },
            {
              skill: "kinni-linked-account-oauth-flows",
              when: "linked-account OAuth flows are involved"
            },
            {
              skill: "noblepro-wordpress-live-fix-workflow",
              when: "WordPress or SiteGround live fix workflow is involved"
            }
          ]
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
        },
        skills: {
          required: [
            "requesting-code-review",
            "pre-commit-qc",
            "run-required-validation",
            "audit-change-followups"
          ],
          recommended: [
            "systematic-debugging",
            "repo-grounded-plan-review"
          ],
          triggered: [
            {
              skill: "change-graphql-contract",
              when: "contract, schema, or generated GraphQL outputs changed"
            },
            {
              skill: "implement-ui-ux-change",
              when: "user-facing UI evidence or accessibility coverage is required"
            },
            {
              skill: "change-native-update-gate",
              when: "native gate or release compatibility behavior changed"
            },
            {
              skill: "triage-release-pipeline",
              when: "validation concerns involve release pipeline state"
            },
            {
              skill: "upgrade-expo-sdk",
              when: "Expo or native upgrade validation is required"
            }
          ]
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
        },
        skills: {
          required: [
            "implement-ui-ux-change",
            "audit-change-followups",
            "run-required-validation"
          ],
          recommended: [
            "dogfood",
            "pre-commit-qc"
          ],
          triggered: [
            {
              skill: "kinni-pixel-linked-account-verification",
              when: "linked-account behavior requires Android or Pixel evidence"
            },
            {
              skill: "kinni-website-astro-foundation",
              when: "Kinni website Astro/Starlight UX is involved"
            },
            {
              skill: "kinni-website-storyblok-marketing-seam",
              when: "Storyblok-backed marketing UX is involved"
            },
            {
              skill: "noblepro-account-hub-localized-myaccount-redirect-fix",
              when: "Account Hub redirect or login UX is involved"
            },
            {
              skill: "noblepro-wordpress-live-fix-workflow",
              when: "WordPress user-facing behavior is involved"
            }
          ]
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
        },
        skills: {
          required: [
            "triage-release-pipeline",
            "run-required-validation",
            "manage-gitlab-work-items"
          ],
          recommended: [
            "update-docs-and-runbooks",
            "pre-commit-qc"
          ],
          triggered: [
            {
              skill: "run-beta-ota-release",
              when: "executing or preparing a Kinni beta OTA release"
            },
            {
              skill: "run-beta-native-release",
              when: "executing or preparing a Kinni beta native release"
            },
            {
              skill: "run-production-ota-release",
              when: "promoting an OTA-safe beta baseline to production"
            },
            {
              skill: "run-production-native-release",
              when: "promoting a native-required beta baseline to production"
            },
            {
              skill: "change-native-update-gate",
              when: "release gate or force-update policy is involved"
            },
            {
              skill: "upgrade-expo-sdk",
              when: "release includes Expo or native SDK changes"
            }
          ]
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
        },
        skills: {
          required: [
            "change-graphql-contract",
            "run-required-validation"
          ],
          recommended: [
            "systematic-debugging",
            "audit-change-followups"
          ],
          triggered: [
            {
              skill: "change-native-update-gate",
              when: "GraphQL/API changes affect app version compatibility or force-update behavior"
            },
            {
              skill: "stripe-best-practices",
              when: "payment, billing, subscription, Connect, or Stripe integration contracts change"
            },
            {
              skill: "stripe-projects",
              when: "Stripe Projects setup or provisioning contracts are involved"
            },
            {
              skill: "upgrade-stripe",
              when: "Stripe API or SDK version changes are involved"
            },
            {
              skill: "kinni-linked-account-oauth-flows",
              when: "OAuth account-linking contracts are involved"
            }
          ]
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
        },
        skills: {
          required: [
            "change-native-update-gate",
            "upgrade-expo-sdk",
            "run-required-validation"
          ],
          recommended: [
            "kinni-pixel-linked-account-verification",
            "systematic-debugging"
          ],
          triggered: [
            {
              skill: "run-beta-native-release",
              when: "beta native release behavior or EAS build/submission evidence is involved"
            },
            {
              skill: "run-production-native-release",
              when: "production native release behavior or store submission evidence is involved"
            },
            {
              skill: "kinni-linked-account-oauth-flows",
              when: "native OAuth or account-linking flows are involved"
            },
            {
              skill: "implement-ui-ux-change",
              when: "native/mobile UI behavior is user-facing"
            }
          ]
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
        },
        skills: {
          required: [
            "systematic-debugging",
            "run-required-validation",
            "audit-change-followups"
          ],
          recommended: [
            "pre-commit-qc"
          ],
          triggered: [
            {
              skill: "change-graphql-contract",
              when: "API, resolver, query, or generated-client performance is involved"
            },
            {
              skill: "implement-ui-ux-change",
              when: "UI rendering, responsiveness, or interaction performance is involved"
            },
            {
              skill: "upgrade-expo-sdk",
              when: "native or Expo upgrade could affect runtime performance"
            },
            {
              skill: "kinni-website-astro-foundation",
              when: "website build or render performance is involved"
            }
          ]
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
        },
        skills: {
          required: [
            "kinni-pixel-linked-account-verification",
            "run-required-validation",
            "dogfood"
          ],
          recommended: [
            "change-native-update-gate",
            "upgrade-expo-sdk"
          ],
          triggered: [
            {
              skill: "run-beta-native-release",
              when: "beta native release requires physical-device proof"
            },
            {
              skill: "run-production-native-release",
              when: "production native release requires physical-device proof"
            },
            {
              skill: "kinni-linked-account-oauth-flows",
              when: "OAuth or linking needs real-device proof"
            },
            {
              skill: "implement-ui-ux-change",
              when: "user-facing mobile behavior needs V4 evidence"
            }
          ]
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
        },
        skills: {
          required: [
            "manage-gitlab-work-items",
            "noblepro-gitlab-bug-triage",
            "audit-change-followups",
            "pre-commit-qc",
            "update-docs-and-runbooks"
          ],
          recommended: [
            "run-required-validation"
          ],
          triggered: [
            {
              skill: "run-beta-ota-release",
              when: "beta OTA release artifacts or MRs are involved"
            },
            {
              skill: "run-beta-native-release",
              when: "beta native release artifacts or MRs are involved"
            },
            {
              skill: "run-production-ota-release",
              when: "production OTA release artifacts or MRs are involved"
            },
            {
              skill: "run-production-native-release",
              when: "production native release artifacts or MRs are involved"
            },
            {
              skill: "triage-release-pipeline",
              when: "release pipeline evidence must be captured"
            },
            {
              skill: "noblepro-plan-cleanup-and-verification",
              when: "in-repo plan cleanup or MR packaging is involved"
            }
          ]
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
