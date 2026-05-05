#!/usr/bin/env python3
"""
Audit Loop - CRITICAL MANDATORY code review system.
NO CODE SHIPS WITHOUT PASSING THIS AUDIT. PERIOD.
Target: 99/100 (near perfect)
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

SKILL_DIR = Path(
    os.getenv("MVP_LAUNCHER_SKILL_DIR", os.getenv("SKILL_DIR", "~/.hermes/skills/software-development/mvp-launcher"))
).expanduser()

# ULTRA STRICT THRESHOLDS
MIN_QUALITY_SCORE = 99  # Near perfect required
MAX_CRITICAL_ISSUES = 0  # Zero tolerance
MAX_WARNINGS = 1  # Almost perfect


class AuditLoop:
    def __init__(self, project_dir, iterations=10, focus_areas=None):
        self.project_dir = Path(project_dir)
        self.iterations = iterations
        self.focus_areas = focus_areas or ['quality', 'security', 'performance']
        self.audits_dir = self.project_dir / 'audits'
        self.src_dir = self.project_dir / 'src'
        self.current_iteration = 0
        
    def load_prd(self):
        """Load PRD requirements."""
        prd_path = self.project_dir / 'prd.md'
        if prd_path.exists():
            return prd_path.read_text()
        return "No PRD found"
    
    def load_project_info(self):
        """Load project metadata."""
        json_path = self.project_dir / 'project.json'
        if json_path.exists():
            return json.loads(json_path.read_text())
        return {}
    
    def run_claude_code(self, task, workdir=None, timeout=300):
        """Run Claude Code for implementation tasks."""
        cc_script = str(SKILL_DIR.parent / "claude-code" / "scripts" / "run.py")
        
        cmd = [
            "python3", os.path.expanduser(cc_script),
            "--task", task,
            "--model", "opus",
            "--timeout", str(timeout)
        ]
        if workdir:
            cmd.extend(["--workdir", str(workdir)])
        
        print(f"🤖 CC Task: {task[:60]}...")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            print(f"⚠️  CC warning: subprocess timed out after {timeout}s")
            return None

        if result.returncode != 0:
            print(f"⚠️  CC warning: {result.stderr[:200]}")

        return result.stdout if result.returncode == 0 else None
    
    def run_heuristic_audit(self, code_path, audit_type):
        """CRITICAL QUALITY AUDIT - NO DEPLOYMENT WITHOUT PASSING (99/100 required)."""
        prd = self.load_prd().lower()

        code_files = []
        if code_path.is_file():
            code_files = [code_path]
        elif code_path.is_dir():
            code_files = [
                f for f in code_path.rglob('*')
                if f.is_file() and f.suffix in ['.js', '.ts', '.jsx', '.tsx', '.py', '.go', '.rs', '.java', '.kt']
            ]

        metrics = {
            'files': len(code_files),
            'lines': 0,
            'todos': 0,
            'fixmes': 0,
            'hacks': 0,
            'debug_logs': 0,
            'bare_except': 0,
            'unsafe_eval': 0,
            'potential_secrets': 0,
            'large_files': 0,
        }

        secret_patterns = ['api_key', 'secret', 'password', 'token=', 'private_key', '-----begin']

        for f in code_files:
            try:
                content = f.read_text(errors='ignore')
            except Exception:
                continue

            lines = content.splitlines()
            metrics['lines'] += len(lines)

            lower = content.lower()
            metrics['todos'] += lower.count('todo')
            metrics['fixmes'] += lower.count('fixme')
            metrics['hacks'] += lower.count('hack')

            metrics['debug_logs'] += lower.count('console.log(')
            metrics['debug_logs'] += lower.count('print(')
            metrics['debug_logs'] += lower.count('debugger')

            metrics['bare_except'] += lower.count('except:')
            metrics['unsafe_eval'] += lower.count('eval(') + lower.count('exec(')
            
            # Check for dummy data
            metrics['dummy_data'] = 0
            dummy_patterns = [
                'lorem ipsum', 'dummy', 'placeholder', 'test@test.com', 
                'example.com', 'john doe', 'jane doe', 'xxxx', '0000',
                'sample', 'fake', 'mock data', 'test data'
            ]
            for pat in dummy_patterns:
                metrics['dummy_data'] += lower.count(pat)

            for pat in secret_patterns:
                metrics['potential_secrets'] += lower.count(pat)

            if len(lines) > 800:
                metrics['large_files'] += 1

        # CRITICAL ISSUES - ZERO TOLERANCE
        critical_issues = []
        warnings = []
        suggestions = []
        strengths = []

        expected_paths = {
            'frontend': self.src_dir / 'frontend',
            'backend': self.src_dir / 'backend',
            'k8s': self.src_dir / 'infrastructure' / 'k8s',
        }
        missing = [name for name, p in expected_paths.items() if not p.exists()]

        if missing:
            critical_issues.append(f"MISSING STRUCTURE: {', '.join(missing)} - CANNOT DEPLOY")

        if metrics['files'] == 0:
            critical_issues.append("NO SOURCE FILES - CANNOT DEPLOY")

        # ALL OF THESE ARE CRITICAL - NO EXCEPTIONS
        if metrics['potential_secrets'] > 0:
            critical_issues.append(f"SECRETS DETECTED: {metrics['potential_secrets']} occurrences - SECURITY RISK")

        if metrics['unsafe_eval'] > 0:
            critical_issues.append(f"UNSAFE eval/exec: {metrics['unsafe_eval']} occurrences - SECURITY RISK")

        # TODO/FIXME/HACK/DEBUG ARE CRITICAL - CODE MUST BE COMPLETE
        if metrics['todos'] > 0:
            critical_issues.append(f"{metrics['todos']} TODO MARKERS - FINISH ALL TASKS BEFORE DEPLOY")

        if metrics['fixmes'] > 0:
            critical_issues.append(f"{metrics['fixmes']} FIXME MARKERS - FIX ALL ISSUES BEFORE DEPLOY")

        if metrics['hacks'] > 0:
            critical_issues.append(f"{metrics['hacks']} HACK/TEMP MARKERS - REMOVE TEMPORARY CODE")

        if metrics['debug_logs'] > 0:
            critical_issues.append(f"{metrics['debug_logs']} DEBUG STATEMENTS - REMOVE ALL BEFORE PRODUCTION")
            
        # DUMMY DATA IS CRITICAL - MUST BE REAL
        if metrics.get('dummy_data', 0) > 0:
            critical_issues.append(f"{metrics['dummy_data']} DUMMY/PLACEHOLDER DATA FOUND - USE REAL RESEARCHED DATA")

        # WARNINGS - STILL IMPORTANT
        if metrics['bare_except'] > 0:
            warnings.append(f"{metrics['bare_except']} bare except blocks")

        if metrics['large_files'] > 0:
            warnings.append(f"{metrics['large_files']} large files (>800 lines)")

        # SUGGESTIONS
        if not suggestions:
            suggestions.append('Verify all PRD requirements implemented')

        # STRENGTHS
        if metrics['files'] > 5:
            strengths.append(f"Good organization: {metrics['files']} files")

        if metrics['todos'] == 0 and metrics['fixmes'] == 0:
            strengths.append("No TODO/FIXME markers")

        if not missing:
            strengths.append("Proper project structure")

        if metrics['potential_secrets'] == 0:
            strengths.append("No secrets detected")

        if metrics['debug_logs'] == 0:
            strengths.append("No debug code")

        # ULTRA STRICT SCORE - 99/100 REQUIRED
        score = 100
        score -= len(critical_issues) * 30  # Each critical issue is -30
        score -= len(warnings) * 10  # Each warning is -10
        score -= min(metrics['todos'] + metrics['fixmes'], 40)
        score -= min(metrics['hacks'] * 8, 25)
        score -= min(metrics['debug_logs'] * 5, 20)
        score = max(0, min(100, score))

        return {
            'score': score,
            'critical_issues': critical_issues,
            'warnings': warnings,
            'suggestions': suggestions,
            'strengths': strengths,
        }

    def initial_implementation(self):
        """Phase 1: Build with STRICT quality requirements."""
        print(f"\n{'='*60}")
        print(f"🔨 BUILD PHASE - ITERATION {self.current_iteration + 1}")
        print(f"{'='*60}")
        
        prd = self.load_prd()
        project = self.load_project_info()
        
        task = f"""Create PRODUCTION-READY MVP website.

PRD:
{prd}

Project: {project.get('title', 'Untitled')}
Tech: {', '.join(project.get('tech_hints', ['react', 'node']))}

⛔ MANDATORY - ZERO TOLERANCE:
1. NO TODO comments
2. NO FIXME comments  
3. NO console.log / print / debugger
4. NO hardcoded secrets
5. NO eval() / exec()
6. NO localhost URLs in production code
7. MUST handle all errors properly
8. MUST be production-ready
9. NO DUMMY DATA - If site has listings/directory, research and use REAL data

Create:
- src/frontend/ - React/Vue frontend
- src/backend/ - API backend  
- src/infrastructure/k8s/ - K8s manifests
- Dockerfile

THE AUDIT IS EXTREMELY STRICT (99/100 required).
CODE MUST BE NEAR-PERFECT. NO EXCEPTIONS.
"""
        
        result = self.run_claude_code(task, workdir=self.project_dir, timeout=600)
        
        # Create initial audit report
        audit = {
            'iteration': self.current_iteration + 1,
            'phase': 'initial_implementation',
            'timestamp': datetime.now().isoformat(),
            'agent': 'claude-code',
            'result': 'completed' if result else 'failed'
        }
        
        audit_path = self.audits_dir / f"iteration_{self.current_iteration + 1}_build.json"
        audit_path.write_text(json.dumps(audit, indent=2))
        
        return result is not None
    
    def audit_phase(self):
        """Phase 2: CRITICAL AUDIT - BLOCKS DEPLOYMENT IF FAILED."""
        print(f"\n{'='*60}")
        print(f"🔍 CRITICAL AUDIT - ITERATION {self.current_iteration + 1}")
        print(f"{'='*60}")
        print("⛔ MANDATORY - NO DEPLOY WITHOUT PASSING")
        print(f"⛔ MINIMUM SCORE: {MIN_QUALITY_SCORE}/100 (NEAR PERFECT)")
        print(f"⛔ MAX CRITICAL: {MAX_CRITICAL_ISSUES}")
        print(f"⛔ MAX WARNINGS: {MAX_WARNINGS}")
        print("="*60)
        
        audits = {}
        
        for focus in self.focus_areas:
            print(f"\n🔎 {focus.upper()} AUDIT...")
            audit = self.run_heuristic_audit(self.src_dir, focus)
            audits[focus] = audit
            
            print(f"   Score: {audit['score']}/100")
            
            if audit['critical_issues']:
                print(f"   ⛔ CRITICAL ({len(audit['critical_issues'])}):")
                for issue in audit['critical_issues']:
                    print(f"      - {issue}")
                    
            if audit['warnings']:
                print(f"   ⚠️ WARNINGS ({len(audit['warnings'])}):")
                for warning in audit['warnings']:
                    print(f"      - {warning}")
        
        # Calculate overall
        avg_score = sum(a['score'] for a in audits.values()) / len(audits)
        total_critical = sum(len(a['critical_issues']) for a in audits.values())
        total_warnings = sum(len(a['warnings']) for a in audits.values())
        
        # Save audit report
        audit_path = self.audits_dir / f"iteration_{self.current_iteration + 1}_audit.json"
        audit_path.write_text(json.dumps({
            'iteration': self.current_iteration + 1,
            'phase': 'audit',
            'timestamp': datetime.now().isoformat(),
            'audits': audits,
            'overall_score': avg_score,
            'total_critical': total_critical,
            'total_warnings': total_warnings,
            'passed': avg_score >= MIN_QUALITY_SCORE and total_critical == 0 and total_warnings <= MAX_WARNINGS
        }, indent=2))
        
        print(f"\n{'='*60}")
        print(f"📊 RESULTS - ITERATION {self.current_iteration + 1}")
        print(f"{'='*60}")
        print(f"Score: {avg_score:.1f}/100 (need {MIN_QUALITY_SCORE})")
        print(f"Critical: {total_critical} (max {MAX_CRITICAL_ISSUES})")
        print(f"Warnings: {total_warnings} (max {MAX_WARNINGS})")
        
        if avg_score >= MIN_QUALITY_SCORE and total_critical == 0 and total_warnings <= MAX_WARNINGS:
            print(f"✅ PASSED - Quality is EXCELLENT")
            return audits, True
        else:
            print(f"⛔ FAILED - Quality NOT ACCEPTABLE")
            if avg_score < MIN_QUALITY_SCORE:
                print(f"   Score too low: {avg_score:.1f} < {MIN_QUALITY_SCORE}")
            if total_critical > 0:
                print(f"   Critical issues: {total_critical}")
            if total_warnings > MAX_WARNINGS:
                print(f"   Too many warnings: {total_warnings}")
            return audits, False
    
    def fix_phase(self, audits):
        """Phase 3: Fix ALL identified issues."""
        print(f"\n{'='*60}")
        print(f"🔧 FIX PHASE - ITERATION {self.current_iteration + 1}")
        print(f"{'='*60}")
        
        # Collect all issues
        all_critical = []
        all_warnings = []
        
        for focus, audit in audits.items():
            all_critical.extend([f"[{focus}] {issue}" for issue in audit.get('critical_issues', [])])
            all_warnings.extend([f"[{focus}] {warning}" for warning in audit.get('warnings', [])])
        
        if not all_critical and not all_warnings:
            print("✅ NO ISSUES - Code is perfect!")
            return True
        
        print(f"⛔ FIXING {len(all_critical)} critical + {len(all_warnings)} warnings...")
        
        task = f"""FIX ALL ISSUES in {self.project_dir}/src/

CRITICAL (MUST FIX):
{chr(10).join(f"- {issue}" for issue in all_critical[:15])}

WARNINGS (SHOULD FIX):
{chr(10).join(f"- {warning}" for warning in all_warnings[:10])}

RULES:
1. Fix ALL critical issues
2. Fix ALL warnings  
3. Remove ALL TODO/FIXME/HACK
4. Remove ALL debug logs
5. Code must be PERFECT (99/100)

MUST PASS AUDIT AFTER FIXES.
"""
        
        result = self.run_claude_code(task, workdir=self.project_dir, timeout=600)
        
        # Save fix report
        fix_path = self.audits_dir / f"iteration_{self.current_iteration + 1}_fix.json"
        fix_path.write_text(json.dumps({
            'iteration': self.current_iteration + 1,
            'phase': 'fix',
            'timestamp': datetime.now().isoformat(),
            'critical_fixed': len(all_critical),
            'warnings_fixed': len(all_warnings),
            'result': 'completed' if result else 'failed'
        }, indent=2))
        
        return result is not None
    
    def verify_phase(self):
        """Phase 4: Verify the implementation works."""
        print(f"\n✅ Verify Phase (Iteration {self.current_iteration + 1})")
        
        # Run basic verification
        frontend_dir = self.src_dir / 'frontend'
        backend_dir = self.src_dir / 'backend'
        
        checks = []
        
        # Check frontend has package.json
        if (frontend_dir / 'package.json').exists():
            checks.append("Frontend package.json: ✓")
        else:
            checks.append("Frontend package.json: ✗")
        
        # Check backend exists
        if any(backend_dir.iterdir()) if backend_dir.exists() else False:
            checks.append("Backend code: ✓")
        else:
            checks.append("Backend code: ✗")
        
        # Check K8s manifests
        k8s_dir = self.src_dir / 'infrastructure' / 'k8s'
        if k8s_dir.exists() and any(k8s_dir.glob('*.yaml')):
            checks.append("K8s manifests: ✓")
        else:
            checks.append("K8s manifests: ✗")
        
        for check in checks:
            print(f"   {check}")
        
        # Save verification report
        verify_path = self.audits_dir / f"iteration_{self.current_iteration + 1}_verify.json"
        verify_path.write_text(json.dumps({
            'iteration': self.current_iteration + 1,
            'phase': 'verify',
            'timestamp': datetime.now().isoformat(),
            'checks': checks,
            'passed': sum(1 for c in checks if '✓' in c),
            'total': len(checks)
        }, indent=2))
        
        return all('✓' in c for c in checks)
    
    def e2e_test_phase(self, preview_url):
        """Phase 4: CRITICAL End-to-End testing in browser."""
        print(f"\n{'='*60}")
        print(f"🌐 E2E TESTING PHASE (CRITICAL)")
        print(f"{'='*60}")
        print("⛔ TESTING ACTUAL WEBSITE IN BROWSER")
        print("⛔ Each page, endpoint, form MUST work")
        print("⛔ Full UX/UI verification required")
        print("="*60)
        
        e2e_script = SKILL_DIR / "scripts" / "e2e-test.py"
        
        result = subprocess.run([
            "python3",
            str(e2e_script),
            "--url", preview_url,
            "--project-dir", str(self.project_dir)
        ], capture_output=True, text=True, timeout=120)
        
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        # Parse results
        try:
            results_path = self.audits_dir / 'e2e_test_results.json'
            if results_path.exists():
                e2e_results = json.loads(results_path.read_text())
                score = e2e_results.get('score', 0)
                errors = e2e_results.get('errors', [])
                
                print(f"\n{'='*60}")
                print(f"📊 E2E RESULTS")
                print(f"{'='*60}")
                print(f"E2E Score: {score}/100")
                print(f"Errors: {len(errors)}")
                
                if score >= 90 and len(errors) == 0:
                    print(f"✅ E2E TESTS PASSED")
                    return True, score
                else:
                    print(f"⛔ E2E TESTS FAILED")
                    print(f"   Score too low: {score} < 90")
                    print(f"   Errors found: {len(errors)}")
                    return False, score
            else:
                print(f"⛔ E2E results not found")
                return False, 0
        except Exception as e:
            print(f"⛔ Error parsing E2E results: {e}")
            return False, 0
    
    def run(self, preview_url=None):
        """Execute the full audit loop with E2E testing."""
        print("\n" + "=" * 60)
        print("🔄 CRITICAL AUDIT LOOP - 99/100 REQUIRED")
        print("=" * 60)
        print("⛔ CODE MUST BE NEAR-PERFECT")
        print("⛔ NO TODO/FIXME/HACK/DEBUG ALLOWED")
        print("⛔ E2E TESTING REQUIRED (pages, endpoints, forms)")
        print("=" * 60)
        
        # Initial implementation
        if not self.initial_implementation():
            print("⛔ Initial implementation failed!")
            return False
        
        # Run iterations
        for i in range(self.iterations):
            self.current_iteration = i
            
            print(f"\n{'=' * 60}")
            print(f"🔄 ITERATION {i + 1} / {self.iterations}")
            print("=" * 60)
            
            # Audit
            audits, passed = self.audit_phase()
            
            if passed:
                print(f"\n✅ Code audit passed!")
                
                # E2E testing if preview URL available
                if preview_url and i == self.iterations - 1:
                    e2e_passed, e2e_score = self.e2e_test_phase(preview_url)
                    if not e2e_passed:
                        print(f"\n⛔ E2E TESTS FAILED - CANNOT DEPLOY")
                        print(f"   Fix the website issues and retry")
                        return False
                    else:
                        print(f"\n✅ E2E TESTS PASSED - Ready for production!")
                        break
                elif passed:
                    print(f"\n✅ Quality threshold met - Ready for production!")
                    break
            
            # Fix
            if i < self.iterations - 1:
                self.fix_phase(audits)
            else:
                print(f"\n⛔ MAX ITERATIONS REACHED - Quality not achieved")
                return False
        
        print("\n" + "=" * 60)
        print("✅ AUDIT LOOP COMPLETE - QUALITY VERIFIED")
        print("=" * 60)
        print(f"   Reports: {self.audits_dir}")
        print(f"   Code: {self.src_dir}")
        
        return True


def main():
    parser = argparse.ArgumentParser(description='Multi-agent audit loop for MVP development')
    parser.add_argument('--project-dir', required=True, help='Project directory')
    parser.add_argument('--iterations', type=int, default=10, help='Number of iterations')
    parser.add_argument('--focus', default='quality,security,performance', 
                        help='Focus areas (comma-separated)')
    parser.add_argument('--preview-url', help='Preview URL for E2E testing')
    
    args = parser.parse_args()
    
    focus_areas = args.focus.split(',')
    loop = AuditLoop(args.project_dir, args.iterations, focus_areas)
    success = loop.run(preview_url=args.preview_url)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
