#!/usr/bin/env python3
"""
Deploy script - Deploy MVP to Kubernetes or servers.
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd, cwd=None, capture=True, check=True, timeout=300):
    """Run a shell command."""
    print(f"🔄 {' '.join(cmd)[:80]}...")

    retries = 3 if cmd and cmd[0] == 'kubectl' else 1
    backoff_seconds = 2

    for attempt in range(1, retries + 1):
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=capture,
                text=True,
                check=check,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            print(f"❌ Error: Command timed out after {timeout}s")
            result = None
        except subprocess.CalledProcessError as e:
            print(f"❌ Error: {e.stderr or e}")
            result = None

        if result and result.returncode == 0:
            return result.stdout if capture else ""

        if attempt < retries:
            wait = backoff_seconds ** attempt
            print(f"⚠️ kubectl command failed (attempt {attempt}/{retries}), retrying in {wait}s...")
            time.sleep(wait)

    return None


def deploy_to_k8s(project_dir, namespace):
    """Deploy to Kubernetes cluster."""
    print(f"\n☸️  Deploying to Kubernetes (namespace: {namespace})...")

    k8s_dir = Path(project_dir) / 'src' / 'infrastructure' / 'k8s'

    if not k8s_dir.exists():
        print("❌ K8s manifests not found!")
        return False

    # Create namespace if doesn't exist (ignore already exists)
    ns_check = run_command(['kubectl', 'get', 'namespace', namespace])
    if ns_check is None:
        if run_command(['kubectl', 'create', 'namespace', namespace]) is None:
            return False

    # Apply manifests
    if run_command(['kubectl', 'apply', '-f', str(k8s_dir), '-n', namespace]) is None:
        return False

    # Wait for deployment
    print("\n⏳ Waiting for deployment to be ready...")
    if run_command([
        'kubectl', 'wait', '--for=condition=available',
        'deployment', '-l', 'app', '-n', namespace,
        '--timeout=300s'
    ]) is None:
        return False

    # Get status
    print("\n📊 Deployment status:")
    run_command(['kubectl', 'get', 'pods', '-n', namespace], capture=False, check=False)
    run_command(['kubectl', 'get', 'svc', '-n', namespace], capture=False, check=False)
    run_command(['kubectl', 'get', 'ingress', '-n', namespace], capture=False, check=False)

    return True


def deploy_to_server(project_dir, server):
    """Deploy to a remote server via SSH."""
    print(f"\n🖥️  Deploying to server: {server}...")

    # Build Docker image
    src_dir = Path(project_dir) / 'src'
    dockerfile = src_dir / 'Dockerfile'

    if not dockerfile.exists():
        print("❌ Dockerfile not found!")
        return False

    print("📦 Building Docker image...")
    project_name_raw = Path(project_dir).name
    project_name = re.sub(r'[^a-z0-9._-]', '-', project_name_raw.lower()).strip('._-') or 'project'
    image_tag = f"mvp/{project_name}:latest"

    if run_command(['docker', 'build', '-t', image_tag, str(src_dir)]) is None:
        return False

    # Make sure remote server has the locally built image
    print("📤 Transferring Docker image to remote server (docker save | ssh docker load)...")
    transfer_cmd = f"docker save {image_tag} | ssh {server} 'docker load'"
    if run_command(['bash', '-lc', transfer_cmd], capture=False) is None:
        return False

    # Deploy via SSH
    print(f"🚀 Deploying to {server}...")
    if run_command(['ssh', server, 'docker-compose up -d']) is None:
        return False

    return True


def update_dns(domain, target_ip=None):
    """Update Cloudflare DNS to point to the deployment."""
    print(f"\n🌐 Updating DNS for {domain}...")
    
    cf_script = str(Path(os.getenv('MVP_LAUNCHER_CLOUDFLARE_SCRIPT', '~/.hermes/skills/software-development/domain-launch-operations/scripts/cloudflare.py')).expanduser())
    
    # If we have a target IP, create/update A record
    if target_ip:
        run_command([
            'python3', cf_script,
            'dns-create', domain, 'A', target_ip,
            '--name', '@', '--proxied', '--ttl', '300'
        ], check=False)
    
    # Purge cache
    run_command(['python3', cf_script, 'purge-cache', domain], check=False)
    
    print(f"✅ DNS updated for {domain}")
    return True


def main():
    parser = argparse.ArgumentParser(description='Deploy MVP project')
    parser.add_argument('--project-dir', required=True, help='Project directory')
    parser.add_argument('--target', required=True, choices=['k8s', 'server'])
    parser.add_argument('--namespace', default='default', help='K8s namespace')
    parser.add_argument('--server', help='Target server (for server deployment)')
    parser.add_argument('--domain', help='Domain to update in DNS')
    
    args = parser.parse_args()
    
    # Load project info
    project_json = Path(args.project_dir) / 'project.json'
    if project_json.exists():
        project = json.loads(project_json.read_text())
        domain = args.domain or project.get('domain')
    else:
        domain = args.domain
    
    # Deploy
    success = False
    if args.target == 'k8s':
        success = deploy_to_k8s(args.project_dir, args.namespace)
    elif args.target == 'server':
        if not args.server:
            print("❌ --server required for server deployment")
            sys.exit(1)
        success = deploy_to_server(args.project_dir, args.server)
    
    if success and domain:
        update_dns(domain)
    
    print("\n" + "=" * 60)
    if success:
        print("🚀 DEPLOYMENT COMPLETE")
        if domain:
            print(f"   Website: https://{domain}")
    else:
        print("❌ DEPLOYMENT FAILED")
    print("=" * 60)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
