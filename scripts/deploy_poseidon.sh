#!/usr/bin/env bash
set -Eeuo pipefail

WORKSPACE_DIR="${1:-${GITHUB_WORKSPACE:-$(pwd)}}"
DEPLOY_REF="${DEPLOY_REF:-${GITHUB_SHA:-$(git -C "$WORKSPACE_DIR" rev-parse HEAD)}}"
COMPOSE_DIR="${COMPOSE_DIR:-/home/brian/hermes-docker}"
SERVICE_NAME="${SERVICE_NAME:-hermes}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-180}"
STABLE_IMAGE="${STABLE_IMAGE:-hermes-local:latest}"
NEW_IMAGE="${NEW_IMAGE:-hermes-local:sha-${DEPLOY_REF:0:12}}"
LOCK_FILE="${LOCK_FILE:-/tmp/hermes-poseidon-deploy.lock}"

if [[ ! -f "$WORKSPACE_DIR/Dockerfile" ]]; then
  echo "Workspace missing Dockerfile: $WORKSPACE_DIR" >&2
  exit 1
fi

if [[ ! -f "$COMPOSE_DIR/docker-compose.yml" ]]; then
  echo "Compose file missing: $COMPOSE_DIR/docker-compose.yml" >&2
  exit 1
fi

if [[ ! -f "$COMPOSE_DIR/compose.env" ]]; then
  echo "Compose env missing: $COMPOSE_DIR/compose.env" >&2
  exit 1
fi

exec 9>"$LOCK_FILE"
flock 9

compose_cmd=(
  docker compose
  --project-directory "$COMPOSE_DIR"
  --env-file "$COMPOSE_DIR/compose.env"
  -f "$COMPOSE_DIR/docker-compose.yml"
)

echo "Building image $NEW_IMAGE from $WORKSPACE_DIR"
current_image_id="$(docker image inspect "$STABLE_IMAGE" --format '{{.Id}}' 2>/dev/null || true)"
rollback_image=""
if [[ -n "$current_image_id" ]]; then
  rollback_image="hermes-local:rollback-${DEPLOY_REF:0:12}"
  docker tag "$current_image_id" "$rollback_image"
fi

docker build \
  --pull \
  --label "org.opencontainers.image.revision=$DEPLOY_REF" \
  -t "$NEW_IMAGE" \
  "$WORKSPACE_DIR"

docker tag "$NEW_IMAGE" "$STABLE_IMAGE"

echo "Recreating $SERVICE_NAME with new image"
set +e
"${compose_cmd[@]}" up -d --no-deps --force-recreate --wait --wait-timeout "$WAIT_TIMEOUT" "$SERVICE_NAME"
deploy_status=$?
set -e

if [[ $deploy_status -ne 0 ]]; then
  echo "Deployment failed. Collecting diagnostics." >&2
  "${compose_cmd[@]}" ps || true
  docker logs --tail 200 "$SERVICE_NAME" || true

  if [[ -n "$rollback_image" ]]; then
    echo "Rolling back to previous image $rollback_image" >&2
    docker tag "$rollback_image" "$STABLE_IMAGE"
    "${compose_cmd[@]}" up -d --no-deps --force-recreate --wait --wait-timeout "$WAIT_TIMEOUT" "$SERVICE_NAME" || true
  fi

  exit $deploy_status
fi

running_image_id="$(docker inspect "$SERVICE_NAME" --format '{{.Image}}')"
running_revision="$(docker image inspect "$STABLE_IMAGE" --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' 2>/dev/null || true)"

echo "Deployment succeeded"
echo "  service: $SERVICE_NAME"
echo "  image:   $STABLE_IMAGE"
echo "  digest:  $running_image_id"
echo "  revision:${running_revision:-unknown}"

"${compose_cmd[@]}" ps
