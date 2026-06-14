import type { GatewayClient } from "@/lib/gatewayClient";
import { Button } from "@nous-research/ui/ui/components/button";
import { Input } from "@nous-research/ui/ui/components/input";
import { useState } from "react";

import type { PromptOverlay } from "./chatMessages";

interface Props {
  overlay: PromptOverlay;
  gw: GatewayClient | null;
  sessionId: string | null;
  onClear(): void;
}

export function PromptOverlays({
  overlay,
  gw,
  sessionId,
  onClear,
}: Props) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);

  const respond = async (
    method: string,
    params: Record<string, unknown>,
  ) => {
    if (!gw) return;
    setBusy(true);
    try {
      await gw.request(method, params);
      setValue("");
      onClear();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="shrink-0 border-t border-warning/30 bg-warning/5 px-3 py-3 sm:px-4">
      <div className="mx-auto max-w-3xl rounded-lg border border-warning/40 bg-background-base p-3 text-sm">
        {overlay.kind === "approval" && (
          <>
            <p className="font-medium text-warning">Approval required</p>
            {overlay.description && (
              <p className="mt-1 text-text-secondary">{overlay.description}</p>
            )}
            {overlay.command && (
              <pre className="mt-2 overflow-x-auto rounded bg-muted/30 p-2 font-mono text-xs">
                {overlay.command}
              </pre>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                size="sm"
                disabled={busy || !sessionId}
                onClick={() =>
                  void respond("approval.respond", {
                    choice: "once",
                    session_id: sessionId,
                  })
                }
              >
                Allow once
              </Button>
              <Button
                size="sm"
                outlined
                disabled={busy || !sessionId}
                onClick={() =>
                  void respond("approval.respond", {
                    choice: "session",
                    session_id: sessionId,
                  })
                }
              >
                Allow session
              </Button>
              {overlay.allowPermanent !== false && (
                <Button
                  size="sm"
                  outlined
                  disabled={busy || !sessionId}
                  onClick={() =>
                    void respond("approval.respond", {
                      choice: "always",
                      session_id: sessionId,
                    })
                  }
                >
                  Always allow
                </Button>
              )}
              <Button
                size="sm"
                destructive
                disabled={busy || !sessionId}
                onClick={() =>
                  void respond("approval.respond", {
                    choice: "deny",
                    session_id: sessionId,
                  })
                }
              >
                Deny
              </Button>
            </div>
          </>
        )}

        {overlay.kind === "clarify" && (
          <>
            <p className="font-medium">{overlay.question}</p>
            {overlay.choices?.length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {overlay.choices.map((choice) => (
                  <Button
                    key={choice}
                    size="sm"
                    disabled={busy}
                    onClick={() =>
                      void respond("clarify.respond", {
                        request_id: overlay.requestId,
                        answer: choice,
                      })
                    }
                  >
                    {choice}
                  </Button>
                ))}
              </div>
            ) : (
              <div className="mt-3 flex gap-2">
                <Input
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  placeholder="Your answer…"
                  className="flex-1"
                />
                <Button
                  size="sm"
                  disabled={busy || !value.trim()}
                  onClick={() =>
                    void respond("clarify.respond", {
                      request_id: overlay.requestId,
                      answer: value.trim(),
                    })
                  }
                >
                  Submit
                </Button>
              </div>
            )}
          </>
        )}

        {overlay.kind === "sudo" && (
          <>
            <p className="font-medium">Sudo password required</p>
            {overlay.command && (
              <pre className="mt-1 font-mono text-xs text-text-secondary">
                {overlay.command}
              </pre>
            )}
            <div className="mt-3 flex gap-2">
              <Input
                type="password"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="Password"
                className="flex-1"
              />
              <Button
                size="sm"
                disabled={busy || !value}
                onClick={() =>
                  void respond("sudo.respond", {
                    request_id: overlay.requestId,
                    password: value,
                  })
                }
              >
                Submit
              </Button>
            </div>
          </>
        )}

        {overlay.kind === "secret" && (
          <>
            <p className="font-medium">
              {overlay.prompt ||
                `Enter value for ${overlay.envVar ?? "credential"}`}
            </p>
            <div className="mt-3 flex gap-2">
              <Input
                type="password"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder={overlay.envVar ?? "Value"}
                className="flex-1"
              />
              <Button
                size="sm"
                disabled={busy || !value}
                onClick={() =>
                  void respond("secret.respond", {
                    request_id: overlay.requestId,
                    value,
                  })
                }
              >
                Submit
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
