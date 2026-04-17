## Jax Control Plane stack

Source-of-truth stack definition for deploying the Jax Control Plane through the shared infra deploy tool.

### Runtime path
- Repo source: `/lab/infra/stacks/jax-control-plane/`
- Live runtime: `/lab/stacks/jax-control-plane/`

### Deploy
Manual deploy from the VPS:

```bash
bash /lab/infra/scripts/deploy-stack.sh jax-control-plane
```

GitOps deploy path:
- commit changes under `stacks/jax-control-plane/`
- push to `main` in `lab-infra`
- Woodpecker detects the changed stack and runs `deploy-stack.sh jax-control-plane`

### Build source
This stack intentionally builds from a clean mainline checkout of the app repo:
- `/lab/deploy-checkouts/jax-control-plane-main`

That checkout should track `origin/main` for `pablots99/jax-control-plane`.
This avoids building from a dirty working repository checkout.
`deploy-stack.sh` now fetches `origin/main`, hard-resets the checkout to that ref when it is clean, and refuses to continue if the checkout is dirty so the deploy never silently builds from drifted local state.

### Required runtime files
- `/lab/stacks/jax-control-plane/.env`
- `/lab/stacks/jax-control-plane/data/`

### Required runtime mounts
- `/lab:/lab:ro` — preserves the live docs/traceability mount the app already reads from inside the container
- `${HERMES_HOME:-/home/pablo/.hermes}:${HERMES_HOME:-/home/pablo/.hermes}:ro`

### Access
- Traefik route: `https://control.jaxmind.xyz`
- Protected by Traefik basic auth via `JAX_CONTROL_PLANE_AUTH`
