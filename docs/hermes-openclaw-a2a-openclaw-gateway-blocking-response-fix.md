# OpenClaw A2A gateway blocking response patch note

## Context

During Hermes ↔ OpenClaw A2A v2.6 live validation, Hermes could deliver tasks to OpenClaw and OpenClaw executed them, but the blocking `message/send` HTTP call timed out before receiving the final JSON-RPC result.

Layered status before the fix:

- Hermes → OpenClaw task delivery: passed
- OpenClaw task execution: passed
- OpenClaw log/audit marker: passed
- OpenClaw → Hermes blocking JSON-RPC response: failed / timed out
- two-worker live acceptance: blocked

## Root cause

OpenClaw gateway returned the initial `agent` RPC as `accepted`, while the final agent output arrived later as a WebSocket `event=agent` frame without the original request id.

The existing `GatewayRpcConnection.handleMessage()` path ignored event frames after `connect.challenge`, so the pending `expectFinal` agent request was never resolved. Hermes therefore waited until the blocking HTTP client timed out.

## Runtime fix applied on OpenClaw 247

Runtime repo:

```text
/root/.openclaw/extensions/a2a-gateway
```

Changed file:

```text
src/executor.ts
```

Patch class:

- preserve `connect.challenge` behavior;
- for `event=agent`, inspect `payload.result.payloads`;
- only resolve when the event contains real agent text/media payload content;
- if exactly one pending `expectFinal` `agent` request exists, resolve it with the event payload;
- ignore non-content agent events to avoid resolving too early.

Current uncommitted runtime diff:

```diff
diff --git a/src/executor.ts b/src/executor.ts
index d5ab86c..05334c4 100644
--- a/src/executor.ts
+++ b/src/executor.ts
@@ -921,6 +921,24 @@ export class GatewayRpcConnection {
         if (nonce && this.connectChallengeResolver) {
           this.connectChallengeResolver(nonce);
         }
+        return;
+      }
+
+      if (frame.event === "agent") {
+        const eventPayload = asObject(frame.payload);
+        const eventResult = asObject(eventPayload?.result);
+        const eventPayloads = Array.isArray(eventResult?.payloads) ? eventResult.payloads : [];
+        const hasAgentContent = eventPayloads.some((entry) => Boolean(extractAgentPayloadText(entry)) || extractMediaUrlsFromPayload(entry).length > 0);
+        if (hasAgentContent) {
+          const pendingEntries = Array.from(this.pending.entries())
+            .filter(([, entry]) => entry.expectFinal && entry.method === "agent");
+          if (pendingEntries.length === 1) {
+            const [pendingId, pending] = pendingEntries[0];
+            this.pending.delete(pendingId);
+            clearTimeout(pending.timer);
+            pending.resolve(frame.payload);
+          }
+        }
       }
       return;
     }
```

## Verification

TypeScript check on OpenClaw 247:

```text
cd /root/.openclaw/extensions/a2a-gateway
npx tsc --noEmit --pretty false
# passed
```

Gateway service:

```text
systemctl is-active openclaw-gateway.service
active
```

Latest live Hermes evidence:

```text
examples/v2.6.0/live-final-fix2-20260530T135309Z
```

Runner result:

```json
{
  "ok": true,
  "run_id": "a2a-v260-two-worker-20260530T135309Z",
  "dry_run": false,
  "receipt_count": 2,
  "accepted_count": 2,
  "overall": "accepted_with_boundary",
  "secret_scan_ok": true
}
```

Evidence validator:

```text
ok: true
receipt_count: 2
accepted_count: 2
overall: accepted_with_boundary
```

Secret scan:

```text
FINAL_SECRET_HIT_COUNT 0
FINAL_SECRET_HITS []
```

## Side effects

- OpenClaw gateway was restarted during diagnosis and after the fix.
- No Hermes config was changed.
- No cron, daemon, webhook, reverse loop, or platform send was enabled.
- The runtime OpenClaw patch is currently local to `192.168.31.247`; it still needs to be committed/upstreamed in the OpenClaw A2A gateway project if long-term persistence across plugin updates is required.
