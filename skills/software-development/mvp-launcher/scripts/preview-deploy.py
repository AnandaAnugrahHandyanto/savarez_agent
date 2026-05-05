#!/usr/bin/env python3
"""
Preview Deploy - Deploy MVP to batumi.org preview subdomain via Tailscale.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_command(cmd, cwd=None, capture=True, timeout=300):
    """Run a shell command."""
    print(f"🔄 {' '.join(cmd)[:80]}...")
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=capture, text=True, check=False, timeout=timeout
        )
        if result.returncode != 0:
            print(f"❌ Error: {result.stderr[:200]}")
            return None
        return result.stdout if capture else ""
    except subprocess.TimeoutExpired:
        print(f"❌ Command timed out after {timeout}s")
        return None


def deploy_to_preview(project_dir, subdomain):
    """Deploy to batumi.org preview subdomain."""
    preview_domain = f"{subdomain}.preview.batumi.org"
    print(f"\n🔮 Deploying to preview: {preview_domain}")
    
    # Build Docker image
    src_dir = Path(project_dir) / 'src'
    dockerfile = src_dir / 'Dockerfile'
    
    if not dockerfile.exists():
        print("❌ Dockerfile not found! Creating minimal Dockerfile...")
        dockerfile.write_text('''FROM nginx:alpine
COPY . /usr/share/nginx/html
EXPOSE 80
''')
    
    project_name = Path(project_dir).name
    image_tag = f"preview/{project_name}:latest"
    
    # Build image
    print("📦 Building Docker image...")
    if run_command(['docker', 'build', '-t', image_tag, str(src_dir)]) is None:
        return False, None
    
    # Deploy to preview server via Tailscale
    # Assumes preview server is accessible via Tailscale at 100.x.x.x
    preview_server = "100.110.104.77"  # Kai's Mac Studio or your preview server
    
    print(f"📤 Transferring image to preview server...")
    transfer_cmd = f"docker save {image_tag} | ssh root@{preview_server} 'docker load'"
    if run_command(['bash', '-lc', transfer_cmd]) is None:
        return False, None
    
    # Deploy with unique container name for this project
    container_name = f"preview-{project_name}"
    deploy_cmd = f"docker stop {container_name} 2>/dev/null; docker rm {container_name} 2>/dev/null; docker run -d --name {container_name} --label traefik.enable=true --label 'traefik.http.routers.{container_name}.rule=Host(`{preview_domain}`)' --label traefik.http.routers.{container_name}.tls=true --label traefik.http.routers.{container_name}.tls.certresolver=letsencrypt --network traefik-public {image_tag}"
    
    print(f"🚀 Starting preview container...")
    if run_command(['ssh', f'root@{preview_server}', deploy_cmd]) is None:
        return False, None
    
    print(f"✅ Preview deployed: https://{preview_domain}")
    print(f"   Access via Tailscale: {preview_domain}")
    
    return True, preview_domain


def update_preview_dns(subdomain, target_ip="100.110.104.77"):
    """Update Cloudflare DNS for preview subdomain."""
    preview_domain = f"{subdomain}.preview.batumi.org"
    print(f"\n🌐 Updating DNS for {preview_domain}...")
    
    # Use cloudflare.py to create/update A record
    cf_script = str(Path(os.getenv('MVP_LAUNCHER_CLOUDFLARE_SCRIPT', '~/.hermes/skills/software-development/domain-launch-operations/scripts/cloudflare.py')).expanduser())
    
    # Check if record exists
    result = run_command([
        'python3', cf_script,
        'dns-list', 'batumi.org',
        '--type', 'A',
        '--name', f"{subdomain}.preview"
    ])
    
    # Create or update
    if result and f"{subdomain}.preview" in result:
        print(f"   Updating existing DNS record...")
        run_command([
            'python3', cf_script,
            'dns-edit', 'batumi.org', 'A', target_ip,
            '--name', f"{subdomain}.preview"
        ])
    else:
        print(f"   Creating new DNS record...")
        run_command([
            'python3', cf_script,
            'dns-create', 'batumi.org', 'A', target_ip,
            '--name', f"{subdomain}.preview",
            '--proxied', '--ttl', '300'
        ])
    
    print(f"✅ DNS updated for {preview_domain}")
    return True


def main():
    parser = argparse.ArgumentParser(description='Deploy MVP to preview subdomain')
    parser.add_argument('--project-dir', required=True, help='Project directory')
    parser.add_argument('--subdomain', required=True, help='Preview subdomain (e.g., myapp)')
    parser.add_argument('--skip-dns', action='store_true', help='Skip DNS update')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔮 Preview Deployment")
    print("=" * 60)
    
    # Deploy to preview
    success, preview_domain = deploy_to_preview(args.project_dir, args.subdomain)
    
    if not success:
        print("❌ Preview deployment failed")
        sys.exit(1)
    
    # Update DNS
    if not args.skip_dns:
        update_preview_dns(args.subdomain)
    
    print("\n" + "=" * 60)
    print("✅ PREVIEW DEPLOYED")
    print("=" * 60)
    print(f"   URL: https://{preview_domain}")
    print(f"   Access: Only via Tailscale (private)")
    print(f"   Project: {args.project_dir}")


if __name__ == '__main__':
    main()
