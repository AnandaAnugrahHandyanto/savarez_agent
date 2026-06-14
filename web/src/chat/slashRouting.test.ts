import { describe, expect, it, vi } from "vitest";

import type { GatewayClient } from "@/lib/gatewayClient";
import { executeSlash, parseSlash } from "@/lib/slashExec";

describe("slash composer routing", () => {
  it("parseSlash splits name and arg", () => {
    expect(parseSlash("/help")).toEqual({ name: "help", arg: "" });
    expect(parseSlash("/model opus")).toEqual({
      name: "model",
      arg: "opus",
    });
  });

  it("complete slash without args is a bare command", () => {
    const { name, arg } = parseSlash("/help");
    expect(name).toBe("help");
    expect(arg).toBe("");
    expect(`/help`.startsWith("/") && !`/help`.includes(" ")).toBe(true);
  });

  it("/reload-mcp calls reload.mcp RPC (not command.dispatch)", async () => {
    const request = vi.fn().mockResolvedValue({
      status: "confirm_required",
      message: "confirm please",
    });
    const gw = { request } as unknown as GatewayClient;
    const sys = vi.fn();

    const result = await executeSlash({
      command: "/reload-mcp",
      sessionId: "sid-1",
      gw,
      callbacks: { sys, send: vi.fn() },
    });

    expect(result).toBe("done");
    expect(request).toHaveBeenCalledWith("reload.mcp", {
      session_id: "sid-1",
    });
    expect(sys).toHaveBeenCalledWith("confirm please");
  });

  it("/reload-mcp now passes confirm=true", async () => {
    const request = vi.fn().mockResolvedValue({ status: "reloaded" });
    const gw = { request } as unknown as GatewayClient;
    const sys = vi.fn();

    await executeSlash({
      command: "/reload-mcp now",
      sessionId: "sid-2",
      gw,
      callbacks: { sys, send: vi.fn() },
    });

    expect(request).toHaveBeenCalledWith("reload.mcp", {
      session_id: "sid-2",
      confirm: true,
    });
    expect(sys).toHaveBeenCalledWith("MCP servers reloaded");
  });

  it("/branch uses client branch callback (not slash.exec)", async () => {
    const request = vi.fn();
    const gw = { request } as unknown as GatewayClient;
    const branch = vi.fn().mockResolvedValue(undefined);

    const result = await executeSlash({
      command: "/branch my fork",
      sessionId: "sid-3",
      gw,
      callbacks: { sys: vi.fn(), send: vi.fn(), branch },
    });

    expect(result).toBe("done");
    expect(branch).toHaveBeenCalledWith({ name: "my fork" });
    expect(request).not.toHaveBeenCalled();
  });
});
