# WordPress Skills Expansion Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add a first-class WordPress skill cluster to Hermes Agent so users can reliably delegate WordPress development, site operations, store operations, and content/admin workflows.

**Architecture:** Hermes currently has no bundled WordPress skills. The fastest path is not a new top-level category, but a prefixed cross-category bundle using existing buckets: `software-development/wordpress-*` for build workflows, `devops/wordpress-*` for operational workflows, and `productivity/wordpress-*` / `productivity/woocommerce-*` for editor/store workflows. We should start with a router + triage pair, then add the highest-demand workflows, then wire the bundle into generated docs/catalog pages via the existing `website/scripts/generate-skill-docs.py` pipeline.

**Tech Stack:** SKILL.md authoring, Markdown references, small deterministic helper scripts, existing bundled-skills docs generator, git, pytest/docs checks where applicable.

---

## Research Summary

### What exists online already

1. **`WordPress/agent-skills`** is the clearest benchmark repository.
   - Public repo with ~17 WordPress-focused skills.
   - Covers: router, project triage, block development, block themes, plugin development, REST API, Interactivity API, Abilities API, WP-CLI/ops, performance, PHPStan, Playground, plugin directory guidelines, and WPDS.
   - Structure is strong: `SKILL.md` + `references/` + optional `scripts/`.
   - It is already indexed by `VoltAgent/awesome-agent-skills`, which matters for discovery.

2. **WordPress MCP infrastructure is growing faster than reusable skill libraries.**
   - `WordPress/mcp-adapter` exposes WordPress abilities as MCP tools/resources/prompts.
   - `msrbuilds/elementor-mcp` exposes a large Elementor tool surface.
   - `use-novamira/novamira` exposes broad WordPress access through PHP/filesystem operations.

3. **WP-CLI and deployment tooling remain foundational, but are not packaged as agent-friendly skill bundles.**
   - `wp-cli/wp-cli` remains the core automation surface.
   - `welaika/wordmove` represents deploy/mirroring workflows that skills could teach well.

### What appears missing or under-served

The public WordPress skill landscape is still thin beyond the official WordPress repo. I did **not** find broad, mature, reusable skill bundles for these high-value areas:

- **WooCommerce operations** — product/catalog, orders, coupons, taxes, shipping, store diagnostics.
- **WordPress admin/editor workflows** — Site Editor, menus/navigation, reusable patterns, publishing ops.
- **SEO and content operations** — metadata, schema, redirects, internal links, content refresh workflows.
- **Migrations and deploys** — local/staging/prod sync, safe search-replace, media/database move checklists.
- **Security and hardening** — plugin/theme review, capability audits beyond API-specific flows, backup/restore hygiene.
- **Testing and QA** — plugin/theme smoke tests, Playground-driven checks, visual/content regression.
- **Popular plugin ecosystems** — ACF, Elementor, Gravity Forms, Contact Form 7, multilingual plugins.
- **Multisite fleet operations** — network-safe plugin activation, per-site config changes, bulk inspection.

### Practical conclusion

There is already a solid external benchmark for *core WordPress development* skills, but there is still whitespace around:
- WooCommerce
- migrations/deploys
- SEO/content ops
- admin/editor workflows
- plugin-ecosystem-specific workflows
- QA/security playbooks

That makes the best Hermes strategy: **copy the good repo shape, avoid duplicating the official WordPress core coverage 1:1 at first, and win on the missing operator-heavy workflows.**

---

## Target Repo Shape

Do **not** create a new top-level `wordpress/` category yet.

Use these existing categories:

- `skills/software-development/wordpress-*/`
- `skills/devops/wordpress-*/`
- `skills/productivity/wordpress-*/`
- `skills/productivity/woocommerce-*/`

This keeps the bundle aligned with Hermes conventions while making WordPress skills easy to search by prefix.

---

## Proposed Skill Roadmap

### Phase 1 — foundation

1. `skills/software-development/wordpress-project-router/SKILL.md`
   - Detect whether the repo/site is plugin, theme, block/theme, headless, WooCommerce, or ops-heavy.
   - Route to the correct follow-on skill.

2. `skills/software-development/wordpress-project-triage/SKILL.md`
   - Inspect repo structure, WordPress version assumptions, theme/plugin markers, Composer/npm use, build tools, test tools, and WP-CLI presence.

3. `skills/devops/wordpress-wpcli-ops/SKILL.md`
   - Core operational baseline: plugin/theme management, user ops, cache/transient cleanup, cron checks, search-replace safety, multisite caveats.

### Phase 2 — high-leverage whitespace

4. `skills/devops/wordpress-migrations-and-deploys/SKILL.md`
   - Safe database/media/code moves across local/staging/prod.
   - Include search-replace, serialized data caveats, rollback checklist, and verification.

5. `skills/productivity/woocommerce-store-ops/SKILL.md`
   - Store triage, product/catalog updates, order inspection, coupon/shipping/tax checks, Woo-related troubleshooting.

6. `skills/productivity/wordpress-seo-content-ops/SKILL.md`
   - Title/meta/schema checks, redirects, internal links, sitemap/robots basics, publishing refresh workflow.

7. `skills/productivity/wordpress-admin-site-editor/SKILL.md`
   - Site Editor, patterns, templates, template parts, navigation/menu updates, content-safe editing workflow.

### Phase 3 — ecosystem depth

8. `skills/software-development/wordpress-plugin-development/SKILL.md`
   - Hermes-tailored plugin workflow with modern best practices.
   - Avoid cloning the official WordPress skill verbatim; focus on Hermes workflow, verification, and common mistakes.

9. `skills/software-development/wordpress-theme-and-block-development/SKILL.md`
   - Block themes, `theme.json`, patterns, rendering, style variations, and when to choose theme vs plugin vs block.

10. `skills/software-development/wordpress-rest-api-integration/SKILL.md`
    - Endpoint shape, auth options, schema discipline, permissions, and client/server verification.

### Phase 4 — specialization

11. `skills/software-development/wordpress-acf-workflows/SKILL.md`
12. `skills/productivity/wordpress-elementor-workflows/SKILL.md`
13. `skills/productivity/wordpress-forms-workflows/SKILL.md`
14. `skills/devops/wordpress-security-hardening/SKILL.md`
15. `skills/devops/wordpress-playground-qa/SKILL.md`

Only do Phase 4 after Phase 2 usage data proves demand.

---

## Implementation Tasks

### Task 1: Create the strategy note in-repo

**Objective:** Preserve the research and expansion direction in a durable repo artifact.

**Files:**
- Create: `docs/plans/2026-06-02-wordpress-skills-expansion.md`

**Verification:**
- File exists and includes benchmark repo, gaps, phases, and exact target skill paths.

### Task 2: Scaffold the Phase 1 directories

**Objective:** Create the minimal repo structure for the initial WordPress bundle.

**Files:**
- Create: `skills/software-development/wordpress-project-router/SKILL.md`
- Create: `skills/software-development/wordpress-project-triage/SKILL.md`
- Create: `skills/devops/wordpress-wpcli-ops/SKILL.md`

**Notes:**
- Follow bundled skill conventions: frontmatter, Overview, When to Use, actionable body, Common Pitfalls, Verification Checklist.
- Add `references/` and `scripts/` only when they materially help.

### Task 3: Author `wordpress-project-router`

**Objective:** Ensure WordPress requests load the right specialized skill instead of treating every site the same.

**Files:**
- Modify/create: `skills/software-development/wordpress-project-router/SKILL.md`
- Optional: `skills/software-development/wordpress-project-router/references/repo-signals.md`

**Must cover:**
- plugin vs theme vs block theme vs WooCommerce vs headless vs ops-only
- when to switch to wpcli, deploy, SEO, admin, or store skills
- quick repo/site signals to inspect first

### Task 4: Author `wordpress-project-triage`

**Objective:** Teach Hermes how to inspect an unfamiliar WordPress repo/site before making changes.

**Files:**
- Modify/create: `skills/software-development/wordpress-project-triage/SKILL.md`
- Optional: `skills/software-development/wordpress-project-triage/scripts/detect_wordpress_project.py`

**Must cover:**
- marker files and directories
- Composer/npm/build chain detection
- WordPress version assumptions
- plugin/theme boundaries
- test and validation surfaces

### Task 5: Author `wordpress-wpcli-ops`

**Objective:** Ship the first practical operator skill that users can apply immediately.

**Files:**
- Modify/create: `skills/devops/wordpress-wpcli-ops/SKILL.md`
- Optional: `skills/devops/wordpress-wpcli-ops/references/common-commands.md`
- Optional: `skills/devops/wordpress-wpcli-ops/references/multisite-caveats.md`

**Must cover:**
- safe `wp` command discovery
- plugin/theme/user/content ops
- search-replace safety
- transient/cache cleanup
- cron inspection
- multisite caveats
- verification before/after changes

### Task 6: Scaffold the Phase 2 whitespace skills

**Objective:** Prepare the highest-value missing areas next.

**Files:**
- Create: `skills/devops/wordpress-migrations-and-deploys/SKILL.md`
- Create: `skills/productivity/woocommerce-store-ops/SKILL.md`
- Create: `skills/productivity/wordpress-seo-content-ops/SKILL.md`
- Create: `skills/productivity/wordpress-admin-site-editor/SKILL.md`

### Task 7: Author `wordpress-migrations-and-deploys`

**Objective:** Cover a major gap not well represented in public WordPress skill repos.

**Files:**
- Modify/create: `skills/devops/wordpress-migrations-and-deploys/SKILL.md`
- Optional: `skills/devops/wordpress-migrations-and-deploys/references/rollback-checklist.md`

**Must cover:**
- code/db/uploads separation
- staging-to-prod and prod-to-local flows
- search-replace with serialized data safety
- backup checkpoints
- rollback plan
- post-move verification

### Task 8: Author `woocommerce-store-ops`

**Objective:** Establish Hermes coverage in the biggest obvious whitespace area.

**Files:**
- Modify/create: `skills/productivity/woocommerce-store-ops/SKILL.md`
- Optional: `skills/productivity/woocommerce-store-ops/references/store-triage-checklist.md`

**Must cover:**
- product/catalog updates
- order inspection
- coupon/shipping/tax sanity checks
- extensions/plugin interaction risks
- what to verify after each change

### Task 9: Author `wordpress-seo-content-ops`

**Objective:** Add non-developer WordPress workflows that broad users will actually ask for.

**Files:**
- Modify/create: `skills/productivity/wordpress-seo-content-ops/SKILL.md`
- Optional: `skills/productivity/wordpress-seo-content-ops/references/seo-audit-checklist.md`

**Must cover:**
- titles/meta/schema basics
- redirects/canonicals/internal linking
- sitemap/robots checks
- content refresh workflow
- plugin-agnostic guidance first; plugin-specific notes second

### Task 10: Author `wordpress-admin-site-editor`

**Objective:** Cover admin/editor changes that are common, risky, and poorly handled by generic coding agents.

**Files:**
- Modify/create: `skills/productivity/wordpress-admin-site-editor/SKILL.md`
- Optional: `skills/productivity/wordpress-admin-site-editor/references/editor-safety-checklist.md`

**Must cover:**
- Site Editor vs classic admin distinctions
- patterns/templates/template parts
- navigation/menu changes
- safe content-edit workflow
- verification in browser after edits

### Task 11: Add the Phase 3 dev skills only after the operator baseline is in place

**Objective:** Fill in core code workflows without spending the first release only on overlap with the WordPress benchmark repo.

**Files:**
- Create: `skills/software-development/wordpress-plugin-development/SKILL.md`
- Create: `skills/software-development/wordpress-theme-and-block-development/SKILL.md`
- Create: `skills/software-development/wordpress-rest-api-integration/SKILL.md`

**Priority rule:**
- If time is limited, ship Phase 2 before these.

### Task 12: Generate docs pages and catalog entries

**Objective:** Make the new skills discoverable in Hermes docs immediately.

**Files:**
- Generated/updated by script: `website/docs/user-guide/skills/bundled/**`
- Generated/updated by script: `website/docs/reference/skills-catalog.md`

**Run:**
```bash
cd /home/jorgerosal/hermes-agent
python website/scripts/generate-skill-docs.py
```

**Expected:**
- New bundled skill pages appear under the correct category paths.
- `website/docs/reference/skills-catalog.md` includes the new entries.

### Task 13: Add top-level repo discoverability for the WordPress bundle

**Objective:** Make WordPress support visible in the main repo narrative.

**Files:**
- Modify: `README.md`

**Suggested additions:**
- a short bullet in the skills/value section mentioning bundled WordPress skills
- one concrete example prompt or workflow
- optionally link to generated docs/catalog page

### Task 14: Validate the bundle end-to-end

**Objective:** Ensure the skills are shippable, not just written.

**Files:**
- Validate generated docs and skill pages
- Inspect a few generated pages under `website/docs/user-guide/skills/bundled/`

**Run:**
```bash
cd /home/jorgerosal/hermes-agent
python website/scripts/generate-skill-docs.py
```

**Manual checks:**
- frontmatter loads correctly
- descriptions are concise and trigger-based
- related skills resolve sensibly
- no category/path naming mistakes
- docs pages render under bundled skills

---

## Prioritization Rules

If we only ship **five** WordPress skills in the first PR, ship these:

1. `wordpress-project-router`
2. `wordpress-project-triage`
3. `wordpress-wpcli-ops`
4. `wordpress-migrations-and-deploys`
5. `woocommerce-store-ops`

Why: this gives Hermes a differentiated operator story instead of only duplicating the official WordPress development bundle.

---

## Suggested Naming Conventions

- Use `wordpress-` prefix for WordPress-specific skills.
- Use `woocommerce-` prefix only when the skill is store-specific.
- Keep names action/domain-oriented rather than tool-oriented.
- Start descriptions with `Use when ...`

Examples:
- `wordpress-project-router`
- `wordpress-migrations-and-deploys`
- `wordpress-seo-content-ops`
- `woocommerce-store-ops`

---

## Risks and Avoidance

1. **Risk: cloning the official WordPress repo too literally**
   - Avoidance: use it as a benchmark, but prioritize Hermes-specific workflows and whitespace.

2. **Risk: inventing a new top-level category too early**
   - Avoidance: stay inside `software-development`, `devops`, and `productivity` for v1.

3. **Risk: writing generic advice with no deterministic verification**
   - Avoidance: every skill needs concrete checks, commands, and "done means" criteria.

4. **Risk: over-indexing on Gutenberg/core dev and missing operator demand**
   - Avoidance: ship migrations, WooCommerce, WP-CLI, and SEO/admin skills first.

5. **Risk: docs/catalog drift**
   - Avoidance: always run `python website/scripts/generate-skill-docs.py` in the same PR.

---

## Success Criteria

- Hermes repo contains at least 5 bundled WordPress-prefixed skills.
- At least 2 of those skills cover whitespace not strongly served by `WordPress/agent-skills`.
- Generated docs/catalog pages include all new skills.
- README makes WordPress support discoverable.
- The first bundle gives a user enough coverage to handle: repo triage, WP-CLI ops, migration/deploy, and WooCommerce basics.

---

## Recommended First PR Scope

Keep PR 1 tight:

- `wordpress-project-router`
- `wordpress-project-triage`
- `wordpress-wpcli-ops`
- `wordpress-migrations-and-deploys`
- `woocommerce-store-ops`
- generated docs/catalog updates
- small README mention

Leave SEO/admin/editor and plugin/theme/dev skills for PR 2.

This creates a differentiated WordPress bundle quickly without turning the first PR into a huge documentation dump.
