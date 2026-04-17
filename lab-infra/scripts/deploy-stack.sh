#!/bin/bash
# deploy-stack.sh — manually deploy or update a stack
# Usage: bash scripts/deploy-stack.sh <stack-name>
# Example: bash scripts/deploy-stack.sh monitoring
#
# SOPS decryption:
#   If SOPS_AGE_KEY_FILE is set and stacks/<name>/.env.enc exists,
#   the .env is decrypted automatically before docker compose runs.
#   In Woodpecker CI, the AGE_PRIVATE_KEY secret is injected and
#   written to a temp file — SOPS_AGE_KEY_FILE points to that file.

set -e

STACK="$1"
STACKS_PATH="/lab/stacks"
INFRA_PATH="/lab/infra"
JAX_CONTROL_PLANE_DEPLOY_CHECKOUT="/lab/deploy-checkouts/jax-control-plane-main"

refresh_jax_control_plane_checkout() {
  if ! git -C "$JAX_CONTROL_PLANE_DEPLOY_CHECKOUT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "❌ Expected git worktree at $JAX_CONTROL_PLANE_DEPLOY_CHECKOUT"
    exit 1
  fi

  echo "🔍 Verifying clean deploy checkout: $JAX_CONTROL_PLANE_DEPLOY_CHECKOUT"
  git -C "$JAX_CONTROL_PLANE_DEPLOY_CHECKOUT" fetch origin main

  if [ -n "$(git -C "$JAX_CONTROL_PLANE_DEPLOY_CHECKOUT" status --porcelain)" ]; then
    echo "❌ Deploy checkout is dirty; refusing to reset to origin/main"
    git -C "$JAX_CONTROL_PLANE_DEPLOY_CHECKOUT" status --short
    echo "   Clean or recreate $JAX_CONTROL_PLANE_DEPLOY_CHECKOUT before retrying"
    exit 1
  fi

  git -C "$JAX_CONTROL_PLANE_DEPLOY_CHECKOUT" reset --hard origin/main
  TARGET_SHA=$(git -C "$JAX_CONTROL_PLANE_DEPLOY_CHECKOUT" rev-parse --short origin/main)
  echo "✅ Deploy checkout refreshed to origin/main ($TARGET_SHA)"
}

if [ -z "$STACK" ]; then
  echo "Usage: bash deploy-stack.sh <stack-name>"
  echo "Available stacks:"
  ls "$INFRA_PATH/stacks/"
  exit 1
fi

STACK_DIR="$STACKS_PATH/$STACK"
SRC_DIR="$INFRA_PATH/stacks/$STACK"

if [ ! -d "$SRC_DIR" ]; then
  echo "❌ Stack '$STACK' not found in $INFRA_PATH/stacks/"
  exit 1
fi

echo "🚀 Deploying stack: $STACK"
echo "──────────────────────────"

if [ "$STACK" = "jax-control-plane" ]; then
  refresh_jax_control_plane_checkout
fi

# Sync config files (preserve .env)
rsync -av --exclude='.env' "$SRC_DIR/" "$STACK_DIR/"

# Decrypt .env from .env.enc if the encrypted file exists
ENV_ENC="$STACK_DIR/.env.enc"
ENV_FILE="$STACK_DIR/.env"

if [ -f "$ENV_ENC" ]; then
  if [ -z "$SOPS_AGE_KEY_FILE" ]; then
    echo "⚠️  WARNING: $ENV_ENC exists but SOPS_AGE_KEY_FILE is not set — skipping decryption"
    echo "   Set SOPS_AGE_KEY_FILE to the age private key file path to enable auto-decrypt"
    if [ ! -f "$ENV_FILE" ]; then
      echo "❌ No .env file found and cannot decrypt — stack will fail to start!"
      exit 1
    fi
  else
    echo "🔓 Decrypting $ENV_ENC → $ENV_FILE"
    SOPS_AGE_KEY_FILE="$SOPS_AGE_KEY_FILE" sops decrypt --input-type dotenv --output-type dotenv "$ENV_ENC" > "$ENV_FILE"
    echo "✅ .env decrypted successfully"
  fi
else
  echo "ℹ️  No .env.enc found for $STACK — using existing .env (if present)"
fi

# Deploy
cd "$STACK_DIR"
docker compose pull
docker compose up -d --build --remove-orphans
docker image prune -f

echo ""
echo "✅ Stack '$STACK' deployed"
docker compose ps
