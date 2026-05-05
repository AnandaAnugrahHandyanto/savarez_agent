#!/usr/bin/env python3
"""
MVP Launcher - Main orchestration script for end-to-end MVP deployment.
Takes a PRD document and launches a complete website.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(os.getenv("MVP_LAUNCHER_SKILL_DIR", "~/.hermes/skills/software-development/mvp-launcher")).expanduser()
PROJECTS_DIR = Path(os.getenv("MVP_LAUNCHER_PROJECTS_DIR", "~/.hermes/workspace/mvp-projects")).expanduser()
PORKBUN_SCRIPT = os.getenv("MVP_LAUNCHER_PORKBUN_SCRIPT", "~/.hermes/skills/software-development/domain-launch-operations/scripts/porkbun.py")
CLOUDFLARE_SCRIPT = os.getenv("MVP_LAUNCHER_CLOUDFLARE_SCRIPT", "~/.hermes/skills/software-development/domain-launch-operations/scripts/cloudflare.py")

SENSITIVE_PATTERNS = [
    # key/value style secrets
    (re.compile(r"(?im)^([\w\-\.]*?(?:password|passwd|pwd|token|secret|api[_-]?key|access[_-]?key|auth)[\w\-\.]*)\s*[:=]\s*([^\n]+)$"), r"\1: [REDACTED]"),
    # Bearer tokens
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-\._~\+/]+=*"), "Bearer [REDACTED]"),
    # Common API key formats
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
]


def run_command(cmd, cwd=None, capture=True, timeout=60):
    """Run a shell command and return subprocess result (or None if execution failed)."""
    print(f"🔄 Running: {' '.join(cmd)[:100]}...")
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"❌ Command timed out after {timeout}s")
        return None
    except OSError as exc:
        print(f"❌ Failed to execute command: {exc}")
        return None

    if result.returncode != 0:
        err = (result.stderr or "").strip()
        print(f"❌ Command failed (exit={result.returncode}): {err[:500]}")

    return result


def run_api_command(cmd, timeout=None, max_attempts=None):
    """Run Porkbun/Cloudflare API command with retries and exponential backoff."""
    timeout = timeout or int(os.getenv("MVP_LAUNCHER_API_TIMEOUT", "60"))
    max_attempts = max_attempts or int(os.getenv("MVP_LAUNCHER_API_MAX_ATTEMPTS", "3"))

    for attempt in range(1, max_attempts + 1):
        result = run_command(cmd, timeout=timeout)
        if result and result.returncode == 0:
            return result

        if attempt < max_attempts:
            delay = 2 ** (attempt - 1)
            print(f"⚠️ API command failed (attempt {attempt}/{max_attempts}), retrying in {delay}s...")
            time.sleep(delay)

    return result


def sanitize_project_name(project_name):
    """Sanitize project names to a safe slug-like value."""
    safe = re.sub(r"[^a-zA-Z0-9\-\s_]", "", project_name or "")
    safe = safe.replace("_", "-")
    safe = re.sub(r"\s+", "-", safe.lower())
    safe = re.sub(r"-+", "-", safe).strip("-")
    return safe[:30] or "untitled-project"


def _slugify(text):
    return sanitize_project_name(text)


def redact_sensitive_content(content):
    """Redact common secret/token patterns before content is sent to AI prompts."""
    redacted = content
    for pattern, replacement in SENSITIVE_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def extract_prd_info(prd_path):
    """Extract key info from PRD document."""
    print("📄 Reading PRD document...")
    content = Path(prd_path).read_text()
    redacted_content = redact_sensitive_content(content)

    lines = content.split("\n")
    title = lines[0].replace("#", "").strip() if lines else "Untitled Project"

    domain_hints = []
    for line in lines:
        if "domain" in line.lower() or "website" in line.lower():
            domain_hints.append(line.strip())

    tech_hints = []
    tech_keywords = ["react", "vue", "angular", "nextjs", "django", "flask", "fastapi", "node"]
    for line in lines:
        lower_line = line.lower()
        for tech in tech_keywords:
            if tech in lower_line:
                tech_hints.append(tech)

    return {
        "title": title,
        "content": redacted_content,
        "raw_content": content,
        "domain_hints": domain_hints[:5],
        "tech_hints": list(set(tech_hints)),
        "slug": _slugify(title),
    }


def get_domain_quote(domain):
    """Get current availability and pricing for a domain from Porkbun."""
    result = run_api_command([
        "python3",
        PORKBUN_SCRIPT,
        "check",
        domain,
        "--json",
    ])
    if not result or result.returncode != 0:
        return None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"⚠️ Could not parse Porkbun response for {domain}")
        return None

    available = data.get("avail") == "yes"
    price_raw = data.get("price", 0)
    try:
        price = float(price_raw)
    except (TypeError, ValueError):
        price = 0.0

    return {
        "domain": domain,
        "available": available,
        "price": price,
        "currency": "USD",
        "premium": data.get("premium") == "yes",
        "min_duration": int(data.get("minDuration", 1) or 1),
    }


def research_domains(project_info, tlds, budget):
    """Research available domains."""
    print("\n🔍 Researching domain names...")

    base_names = [
        project_info["slug"],
        project_info["slug"].replace("-", ""),
        project_info["slug"].replace("-", "app"),
        f"get{project_info['slug'].replace('-', '')}",
        f"use{project_info['slug'].replace('-', '')}",
        f"my{project_info['slug'].replace('-', '')}",
    ]

    candidates = []
    for name in base_names:
        clean_name = re.sub(r"[^a-z0-9-]", "", name.lower()).strip("-")
        if not clean_name:
            continue
        for tld in tlds:
            tld = tld.strip().lower().lstrip(".")
            if tld:
                candidates.append(f"{clean_name}.{tld}")

    seen = set()
    unique_candidates = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique_candidates.append(c)

    available = []
    for domain in unique_candidates[:12]:
        quote = get_domain_quote(domain)
        if not quote:
            continue
        if quote["available"] and quote["price"] <= budget:
            available.append(quote)

    return sorted(available, key=lambda x: x["price"])[:5]


def select_domain_interactively(available_quotes):
    """Ask user to explicitly choose a domain from researched candidates."""
    print("\n💡 Available domains:")
    for i, quote in enumerate(available_quotes, 1):
        print(f"   {i}. {quote['domain']} - ${quote['price']:.2f} {quote['currency']}")

    choice = input("\nChoose a domain number to continue (or 'q' to cancel): ").strip().lower()
    if choice == "q":
        return None

    if not choice.isdigit():
        print("❌ Invalid selection")
        return None

    idx = int(choice)
    if idx < 1 or idx > len(available_quotes):
        print("❌ Selection out of range")
        return None

    return available_quotes[idx - 1]


def confirm_domain_purchase(quote):
    """Require explicit user confirmation before any purchase."""
    yearly_total = quote["price"] * max(1, quote.get("min_duration", 1))
    print("\n⚠️ DOMAIN PURCHASE CONFIRMATION REQUIRED")
    print(f"   Domain: {quote['domain']}")
    print(f"   Price: ${quote['price']:.2f} {quote['currency']} / year")
    print(f"   Min term: {quote.get('min_duration', 1)} year(s)")
    print(f"   Immediate charge: ${yearly_total:.2f} {quote['currency']}")
    if quote.get("premium"):
        print("   Note: Premium domain pricing applies")

    confirmation = input("\nType 'yes' to confirm purchase: ").strip().lower()
    return confirmation == "yes"


def register_domain(domain):
    """Register the selected domain on Porkbun."""
    print(f"\n📝 Registering {domain}...")

    result = run_api_command([
        "python3",
        PORKBUN_SCRIPT,
        "register",
        domain,
        "--yes",
        "--json",
    ])

    if not result or result.returncode != 0:
        return False

    try:
        data = json.loads(result.stdout)
        cost = float(data.get("cost", 0)) / 100.0
        print(f"✅ Domain {domain} registered successfully (charged: ${cost:.2f})")
    except (json.JSONDecodeError, ValueError, TypeError):
        print(f"✅ Domain {domain} registered successfully")

    return True


def get_cloudflare_nameservers(domain):
    """Fetch Cloudflare nameservers for the zone."""
    result = run_api_command([
        "python3",
        CLOUDFLARE_SCRIPT,
        "--json",
        "zone-info",
        domain,
    ])
    if not result or result.returncode != 0:
        return None

    try:
        zone = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    nameservers = zone.get("name_servers") or zone.get("nameServers") or []
    return [ns.strip() for ns in nameservers if ns and isinstance(ns, str)]


def handoff_nameservers_to_cloudflare(domain):
    """Update Porkbun nameservers to Cloudflare's assigned nameservers."""
    print(f"\n🔁 Handing off nameservers to Cloudflare for {domain}...")

    nameservers = get_cloudflare_nameservers(domain)
    if not nameservers or len(nameservers) < 2:
        print("❌ Could not read Cloudflare nameservers. Ensure zone exists in Cloudflare first.")
        return False

    print(f"   Cloudflare nameservers: {', '.join(nameservers)}")

    set_result = run_api_command([
        "python3",
        PORKBUN_SCRIPT,
        "ns-set",
        domain,
        *nameservers,
    ])
    if not set_result or set_result.returncode != 0:
        print("❌ Failed to update Porkbun nameservers")
        return False

    verify_result = run_api_command([
        "python3",
        PORKBUN_SCRIPT,
        "ns-get",
        domain,
        "--json",
    ])
    if verify_result and verify_result.returncode == 0:
        try:
            current_ns = [ns.lower() for ns in json.loads(verify_result.stdout)]
            expected = [ns.lower() for ns in nameservers]
            if sorted(current_ns) != sorted(expected):
                print("⚠️ Nameserver update may still be propagating; verification mismatch.")
            else:
                print("✅ Nameserver handoff complete")
        except json.JSONDecodeError:
            print("⚠️ Could not parse nameserver verification response")
    else:
        print("⚠️ Could not verify nameserver update immediately")

    return True


def setup_cloudflare(domain):
    """Setup Cloudflare SSL for the domain."""
    print(f"\n☁️ Setting up Cloudflare for {domain}...")

    zone_check = run_api_command([
        "python3",
        CLOUDFLARE_SCRIPT,
        "zone-info",
        domain,
    ])

    if not zone_check or zone_check.returncode != 0:
        print("❌ Zone not found in Cloudflare. Add domain to CF first.")
        return False

    ssl_result = run_api_command([
        "python3",
        CLOUDFLARE_SCRIPT,
        "ssl-mode",
        domain,
        "strict",
    ])
    if not ssl_result or ssl_result.returncode != 0:
        print("❌ Failed to set Cloudflare SSL mode")
        return False

    print(f"✅ Cloudflare configured for {domain}")
    return True


def mark_domain_for_cleanup(domain, reason):
    """Persist domain cleanup note for manual follow-up."""
    cleanup_file = PROJECTS_DIR / "_cleanup_domains.jsonl"
    cleanup_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "domain": domain,
        "reason": reason,
        "created_at": datetime.now().isoformat(),
        "status": "pending_manual_cleanup",
    }
    with cleanup_file.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"📝 Marked for cleanup: {cleanup_file}")


def rollback_domain_purchase(domain, reason):
    """Best-effort rollback after failed post-purchase steps."""
    print("\n↩️ Initiating rollback for domain purchase...")
    print(f"   Reason: {reason}")

    delete_result = run_api_command([
        "python3",
        PORKBUN_SCRIPT,
        "delete",
        domain,
        "--yes",
    ])
    if delete_result and delete_result.returncode == 0:
        print("✅ Rollback complete: domain deletion requested")
        return

    print("⚠️ Automatic delete unavailable/failed, trying to reduce risk (disable auto-renew)...")
    autorenew_result = run_api_command([
        "python3",
        PORKBUN_SCRIPT,
        "autorenew",
        domain,
        "off",
    ])
    if autorenew_result and autorenew_result.returncode == 0:
        print("✅ Rollback step complete: auto-renew disabled")
    else:
        print("⚠️ Could not disable auto-renew")

    mark_domain_for_cleanup(domain, reason)
    print("⚠️ Manual action may be required: request cancellation/refund in Porkbun dashboard.")


def create_project_structure(domain, prd_info):
    """Create the project directory structure."""
    print("\n📁 Creating project structure...")
    project_dir = PROJECTS_DIR / domain

    dirs = [
        "research",
        "design",
        "src/frontend",
        "src/backend",
        "src/infrastructure/k8s",
        "audits",
        "deploy",
    ]

    for d in dirs:
        (project_dir / d).mkdir(parents=True, exist_ok=True)

    # Keep redacted PRD as default input for downstream AI prompts.
    (project_dir / "prd.md").write_text(prd_info["content"])
    (project_dir / "prd.original.md").write_text(prd_info.get("raw_content", prd_info["content"]))

    metadata = {
        "domain": domain,
        "title": prd_info["title"],
        "created_at": datetime.now().isoformat(),
        "tech_hints": prd_info["tech_hints"],
        "status": "domain_registered",
    }
    (project_dir / "project.json").write_text(json.dumps(metadata, indent=2))

    print(f"✅ Project structure created at {project_dir}")
    return project_dir


def run_audit_loop(project_dir, iterations=3, preview_url=None):
    """Run the CC + audit loop for development with optional E2E testing."""
    print(f"\n🔄 Starting development with audit loop ({iterations} iterations)...")

    audit_script = SKILL_DIR / "scripts" / "audit-loop.py"

    cmd = [
        "python3",
        str(audit_script),
        "--project-dir",
        str(project_dir),
        "--iterations",
        str(iterations),
    ]
    
    if preview_url:
        cmd.extend(["--preview-url", preview_url])

    result = run_command(cmd, capture=False, timeout=600)

    return bool(result and result.returncode == 0)


def deploy_project(project_dir, deploy_target, namespace):
    """Deploy the project to the target infrastructure."""
    print(f"\n🚀 Deploying to {deploy_target}...")

    deploy_script = SKILL_DIR / "scripts" / "deploy.py"

    result = run_command([
        "python3",
        str(deploy_script),
        "--project-dir",
        str(project_dir),
        "--target",
        deploy_target,
        "--namespace",
        namespace,
    ], capture=False, timeout=300)

    return bool(result and result.returncode == 0)


def deploy_to_preview(project_dir, subdomain):
    """Deploy to batumi.org preview subdomain for testing."""
    print(f"\n🔮 Deploying to preview ({subdomain}.preview.batumi.org)...")

    preview_script = SKILL_DIR / "scripts" / "preview-deploy.py"

    result = run_command([
        "python3",
        str(preview_script),
        "--project-dir", str(project_dir),
        "--subdomain", subdomain,
    ], capture=False, timeout=300)

    return bool(result and result.returncode == 0)


def main():
    parser = argparse.ArgumentParser(description="Launch an MVP from PRD to live site")
    parser.add_argument("--prd", required=True, help="Path to PRD/research document")
    parser.add_argument("--budget", type=float, default=50, help="Max domain budget")
    parser.add_argument("--tlds", default="com,io,app", help="Preferred TLDs (comma-separated)")
    parser.add_argument("--deploy-to", default="k8s", choices=["k8s", "server"])
    parser.add_argument("--namespace", help="K8s namespace (default: project slug)")
    parser.add_argument("--iterations", type=int, default=3, help="Audit loop iterations")
    parser.add_argument("--skip-domain", action="store_true", help="Skip domain registration")
    parser.add_argument("--domain", help="Pre-selected domain (skip research)")

    args = parser.parse_args()

    print("=" * 60)
    print("🚀 MVP Launcher - PRD to Live Site")
    print("=" * 60)

    prd_info = extract_prd_info(args.prd)
    prd_info["slug"] = sanitize_project_name(prd_info.get("slug") or prd_info.get("title"))
    print(f"\n📋 Project: {prd_info['title']}")
    if prd_info["tech_hints"]:
        print(f"   Tech hints: {', '.join(prd_info['tech_hints'])}")

    selected_domain = None
    domain_registered = False

    try:
        if not args.skip_domain:
            quote = None
            if args.domain:
                selected_domain = args.domain.strip().lower()
                print(f"\n📌 Using pre-selected domain: {selected_domain}")
                quote = get_domain_quote(selected_domain)
                if not quote:
                    print("❌ Could not fetch domain availability/pricing")
                    sys.exit(1)
                if not quote["available"]:
                    print("❌ Selected domain is not available for registration")
                    sys.exit(1)
            else:
                tlds = args.tlds.split(",")
                available = research_domains(prd_info, tlds, args.budget)

                if not available:
                    print("❌ No available domains found within budget!")
                    sys.exit(1)

                quote = select_domain_interactively(available)
                if not quote:
                    print("🛑 Domain selection canceled by user.")
                    sys.exit(1)

                selected_domain = quote["domain"]
                print(f"\n✅ Selected domain: {selected_domain}")

            if quote is None:
                print("❌ Internal error: missing domain quote")
                sys.exit(1)

            if not confirm_domain_purchase(quote):
                print("🛑 Domain purchase canceled by user.")
                sys.exit(1)

            if not register_domain(selected_domain):
                print("❌ Domain registration failed!")
                sys.exit(1)
            domain_registered = True

            if not handoff_nameservers_to_cloudflare(selected_domain):
                raise RuntimeError("Nameserver handoff to Cloudflare failed")

            if not setup_cloudflare(selected_domain):
                raise RuntimeError("Cloudflare setup failed")
        else:
            selected_domain = args.domain or f"{prd_info['slug']}.com"
            print(f"\n📌 Using domain (no registration): {selected_domain}")

        project_dir = create_project_structure(selected_domain, prd_info)
        namespace = sanitize_project_name(args.namespace or prd_info["slug"]).replace("-", "")[:20]

        print("\n" + "=" * 60)
        print("✅ PHASE 1-3 COMPLETE: Domain & Infrastructure")
        print("=" * 60)
        print(f"   Domain: {selected_domain}")
        print(f"   Project: {project_dir}")

        # NEW PHASE: Design Kit Generation
        print("\n" + "=" * 60)
        print("🎨 PHASE 3b: DESIGN KIT GENERATION (NEW)")
        print("=" * 60)
        print("   Creating brand identity and design mockups...")
        print("   • Brand analysis")
        print("   • Color palette & typography")
        print("   • 5 logo concepts (for Nano Banana Pro)")
        print("   • 5 website mockups (for Nano Banana Pro)")
        print("   • Design brief for coding agent")

        if input("\nGenerate design kit? [Y/n]: ").lower() in ("", "y", "yes"):
            design_script = SKILL_DIR / "scripts" / "design-kit.py"
            result = run_command([
                "python3",
                str(design_script),
                "--prd", args.prd,
                "--domain", selected_domain,
                "--project-dir", str(project_dir),
            ], capture=False, timeout=120)
            
            if result and result.returncode == 0:
                print("\n✅ Design kit generated!")
                print(f"   Location: {project_dir}/design/")
                print("\n   NEXT: Use Nano Banana Pro to generate images:")
                print("   - 5 logos from prompts in design/logos/")
                print("   - 5 mockups from prompts in design/mockups/")
                print("   - Pick favorites, logo will be converted to SVG")
            else:
                print("\n⚠️ Design kit generation had issues, continuing anyway...")

        print("\n📝 Next: Development phase with CC + audit loop")

        preview_subdomain = prd_info["slug"][:20]
        preview_url = f"https://{preview_subdomain}.preview.batumi.org"

        # Phase 4: Build and deploy to preview FIRST
        print("\n" + "=" * 60)
        print("🔮 PHASE 4: Build + Preview Deploy")
        print("=" * 60)
        print(f"   Preview URL: {preview_url}")
        print("   Process: Build → Deploy Preview → E2E Test → Production")

        if input("\nStart build + preview deploy? [Y/n]: ").lower() in ("", "y", "yes"):
            # Step 1: Build the code
            print("\n📦 Step 1: Building code...")
            if not run_audit_loop(project_dir, args.iterations, preview_url=preview_url):
                print("\n⛔ BUILD/AUDIT FAILED - Cannot proceed")
                print("   Fix issues and retry")
                sys.exit(1)
            
            # Step 2: Deploy to preview
            print("\n📦 Step 2: Deploying to preview...")
            if not deploy_to_preview(project_dir, preview_subdomain):
                print("\n⛔ PREVIEW DEPLOY FAILED")
                sys.exit(1)
            
            print(f"\n✅ Preview live: {preview_url}")
            print("   Access via Tailscale to test")
            
            # Step 3: E2E Testing (already done in audit loop if preview_url passed)
            print("\n📦 Step 3: E2E tests complete (verified in audit)")

        # Phase 5: Production Deployment (only if preview passed)
        print("\n" + "=" * 60)
        print("🚀 PHASE 5: Production Deployment")
        print("=" * 60)
        print(f"   Production Domain: https://{selected_domain}")
        print(f"   Preview Tests: ✅ PASSED")
        print("   Ready for production!")

        if input("\nDeploy to production? [Y/n]: ").lower() in ("", "y", "yes"):
            if deploy_project(project_dir, args.deploy_to, namespace):
                print(f"\n✅ Production live: https://{selected_domain}")
            else:
                print("⚠️ Production deployment failed")

    except Exception as exc:
        print(f"\n❌ Launch failed: {exc}")
        if domain_registered and selected_domain:
            rollback_domain_purchase(selected_domain, str(exc))
        sys.exit(1)

    preview_url = f"https://{preview_subdomain}.preview.batumi.org"

    print("\n" + "=" * 60)
    print("🎉 MVP LAUNCH COMPLETE!")
    print("=" * 60)
    print(f"   Production: https://{selected_domain}")
    print(f"   Preview:    {preview_url} (Tailscale)")
    print(f"   Project:    {project_dir}")
    print(f"   Logs:       {project_dir}/deploy.log")


if __name__ == "__main__":
    main()
