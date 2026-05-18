import type { OpenClawPluginApi } from "openclaw/plugin-sdk/core";
import { sendChatboxMessage, sendRawOscViaPython } from "./tools/chatbox-enhanced.js";
import { sendInputCommand } from "./tools/input.js";
import { getListenerStatus } from "./tools/listener.js";

type GatewayMethodContext = Parameters<
  Parameters<OpenClawPluginApi["registerGatewayMethod"]>[1]
>[0];
type GatewayRespond = GatewayMethodContext["respond"];

function respondError(
  respond: GatewayRespond,
  code: "invalid_request" | "internal_error" | "unavailable",
  message: string,
) {
  respond(false, undefined, { code, message });
}

export function registerVrchatRelayGatewayMethods(api: OpenClawPluginApi): void {
  api.registerGatewayMethod(
    "vrchat.chatbox",
    async ({ params, respond }) => {
      const message = typeof params.message === "string" ? params.message.trim() : "";
      const sendImmediately = params.sendImmediately !== false;
      if (!message) {
        respondError(respond, "invalid_request", "message required");
        return;
      }

      const result = await sendChatboxMessage({ message, sendImmediately });
      if (result.success) {
        respond(true, { ok: true });
      } else {
        respondError(respond, "unavailable", result.error ?? "VRChat call failed");
      }
    },
    { scope: "operator.write" },
  );

  api.registerGatewayMethod(
    "vrchat.input",
    ({ params, respond }) => {
      const action = typeof params.action === "string" ? params.action.trim() : "";
      const value =
        typeof params.value === "boolean" || typeof params.value === "number" ? params.value : true;
      if (!action) {
        respondError(respond, "invalid_request", "action required");
        return;
      }

      const result = sendInputCommand({ action, value });
      if (result.success) {
        respond(true, { ok: true });
      } else {
        respondError(respond, "unavailable", result.error ?? "VRChat call failed");
      }
    },
    { scope: "operator.write" },
  );

  api.registerGatewayMethod(
    "vrchat.status",
    ({ respond }) => {
      respond(true, {
        ok: true,
        substrate: "plugin-owned-osc",
        listener: getListenerStatus(),
      });
    },
    { scope: "operator.read" },
  );

  api.registerGatewayMethod(
    "vrchat.raw",
    async ({ params, respond }) => {
      const address = typeof params.address === "string" ? params.address.trim() : "";
      const args = Array.isArray(params.args)
        ? params.args.filter(
            (value): value is string | number | boolean | null =>
              value === null ||
              typeof value === "string" ||
              typeof value === "number" ||
              typeof value === "boolean",
          )
        : [];
      if (!address) {
        respondError(respond, "invalid_request", "address required");
        return;
      }

      const result = await sendRawOscViaPython(address, args);
      if (result.success) {
        respond(true, { ok: true });
      } else {
        respondError(respond, "unavailable", result.error ?? "VRChat call failed");
      }
    },
    { scope: "operator.write" },
  );
}
