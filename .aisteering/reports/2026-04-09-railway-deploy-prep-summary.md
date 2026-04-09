# Railway Deploy Prep Summary

- What changed: pulled `origin/main`, added a dedicated `api-server` extra, added `scripts/railway-start.sh`, and added `Dockerfile`, `railway.toml`, `.dockerignore`, `.railwayignore`, and a regression test for the Railway startup wrapper.
- Why: make Hermes deployable as an internal Railway service in the existing `laudable-trust` project without adding a code-level `PORT` fallback that would violate repo policy.
- How to validate:
  - `pytest -o addopts='' tests/test_railway_start.py -q`
  - `uv lock`
  - `docker build -t hermes-agent-railway:test .`
  - `docker run -d --rm -e PORT=18789 -e API_SERVER_KEY=test-key -p 18789:18789 --name hermes-agent-railway-smoke hermes-agent-railway:test`
  - `curl http://127.0.0.1:18789/health`
  - `docker stop hermes-agent-railway-smoke`
- Notes/risks: Railway service `Hermes Agent` now exists in project `laudable-trust` with a `/data` volume and an `API_SERVER_KEY` set, but I did not push a live deployment because the runtime model provider for Hermes has not been chosen/configured yet.
- Next steps: set the provider env vars for Hermes on Railway, then run `railway up` against the `Hermes Agent` service.
