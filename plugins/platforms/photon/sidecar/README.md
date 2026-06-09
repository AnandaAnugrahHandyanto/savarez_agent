# Photon sidecar

Small Node helper that bridges Hermes Agent to Photon's Spectrum SDK
(`spectrum-ts`).  Hermes is Python; Photon has no public HTTP
send-message endpoint today; replies therefore go through this sidecar.

The sidecar:

- runs `Spectrum({ projectId, projectSecret, providers: [imessage.config()] })`
- exposes a loopback-only HTTP control channel for the Python adapter
  to push send/typing requests (auth via `X-Hermes-Sidecar-Token`)
- streams inbound `app.messages` events to the Python adapter over
  loopback `GET /inbound` (NDJSON); there is no Photon webhook in this
  installed path
- polyfills `globalThis.File` on Node 18 before importing `spectrum-ts`

## Install

```bash
cd plugins/platforms/photon/sidecar
npm install
```

The Hermes plugin's `hermes photon setup` and `hermes photon install-sidecar`
commands run `npm install` here, then verify that `index.mjs` and the
`spectrum-ts` imports load under the active Node runtime.

## Run standalone

For debugging:

```bash
PHOTON_PROJECT_ID=... PHOTON_PROJECT_SECRET=... \
PHOTON_SIDECAR_PORT=8789 PHOTON_SIDECAR_TOKEN=$(openssl rand -hex 16) \
node index.mjs
```

In normal use, the Python adapter supervises this process — start,
restart on crash, kill on shutdown — and never asks the user to run
it by hand.

## Why a sidecar at all?

Photon's `spectrum-ts` SDK is TypeScript-only and exposes the long-lived
`app.messages` stream plus `space.send(...)` APIs Hermes needs. The Python
gateway therefore supervises this sidecar and uses loopback HTTP for both
directions instead of exposing a public webhook or direct HTTP send endpoint.
