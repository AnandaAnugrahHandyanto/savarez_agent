#!/bin/sh
set -eu

if [ -z "${PORT:-}" ]; then
  echo "PORT must be set by Railway before starting Hermes." >&2
  exit 1
fi

if [ -z "${API_SERVER_KEY:-}" ]; then
  echo "API_SERVER_KEY must be set for Railway API server deployments." >&2
  exit 1
fi

export HERMES_HOME="${HERMES_HOME:-/data/hermes}"
mkdir -p "${HERMES_HOME}"

export API_SERVER_ENABLED=true
export API_SERVER_HOST=0.0.0.0
export API_SERVER_PORT="${PORT}"

exec hermes gateway run --replace
