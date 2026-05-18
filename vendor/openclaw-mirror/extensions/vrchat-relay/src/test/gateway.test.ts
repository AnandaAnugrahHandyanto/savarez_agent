import type { OpenClawPluginApi } from "openclaw/plugin-sdk/core";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { registerVrchatRelayGatewayMethods } from "../gateway.js";

const { sendChatboxMessage, sendRawOscViaPython, sendInputCommand, getListenerStatus } = vi.hoisted(
  () => ({
    sendChatboxMessage: vi.fn(),
    sendRawOscViaPython: vi.fn(),
    sendInputCommand: vi.fn(),
    getListenerStatus: vi.fn(),
  }),
);

vi.mock("../tools/chatbox-enhanced.js", () => ({
  sendChatboxMessage,
  sendRawOscViaPython,
}));

vi.mock("../tools/input.js", () => ({
  sendInputCommand,
}));

vi.mock("../tools/listener.js", () => ({
  getListenerStatus,
}));

type GatewayHandler = Parameters<OpenClawPluginApi["registerGatewayMethod"]>[1];

function createApi() {
  const registerGatewayMethod = vi.fn();
  return {
    api: {
      registerGatewayMethod,
    } as Pick<OpenClawPluginApi, "registerGatewayMethod"> as OpenClawPluginApi,
    registerGatewayMethod,
  };
}

function findHandler(
  registerGatewayMethod: ReturnType<typeof vi.fn>,
  method: string,
): GatewayHandler {
  const match = registerGatewayMethod.mock.calls.find((call) => call[0] === method);
  if (!match) {
    throw new Error(`Gateway method not registered: ${method}`);
  }
  return match[1] as GatewayHandler;
}

describe("registerVrchatRelayGatewayMethods", () => {
  beforeEach(() => {
    sendChatboxMessage.mockReset();
    sendRawOscViaPython.mockReset();
    sendInputCommand.mockReset();
    getListenerStatus.mockReset();
  });

  it("registers VRChat gateway methods through the plugin API", () => {
    const { api, registerGatewayMethod } = createApi();

    registerVrchatRelayGatewayMethods(api);

    expect(registerGatewayMethod.mock.calls.map((call) => call[0])).toEqual([
      "vrchat.chatbox",
      "vrchat.input",
      "vrchat.status",
      "vrchat.raw",
    ]);
  });

  it("routes gateway calls to plugin-owned helpers", async () => {
    const { api, registerGatewayMethod } = createApi();
    registerVrchatRelayGatewayMethods(api);

    sendChatboxMessage.mockResolvedValue({ success: true });
    sendInputCommand.mockReturnValue({ success: true });
    sendRawOscViaPython.mockResolvedValue({ success: true });
    getListenerStatus.mockReturnValue({
      isRunning: true,
      port: 9001,
      messageCount: 2,
      lastTime: 123,
    });

    const respond = vi.fn();

    await findHandler(
      registerGatewayMethod,
      "vrchat.chatbox",
    )({
      params: { message: "hello", sendImmediately: false },
      respond,
    } as never);
    expect(sendChatboxMessage).toHaveBeenCalledWith({
      message: "hello",
      sendImmediately: false,
    });

    await findHandler(
      registerGatewayMethod,
      "vrchat.input",
    )({
      params: { action: "Jump", value: 1 },
      respond,
    } as never);
    expect(sendInputCommand).toHaveBeenCalledWith({ action: "Jump", value: 1 });

    await findHandler(
      registerGatewayMethod,
      "vrchat.raw",
    )({
      params: { address: "/avatar/parameters/Test", args: [true] },
      respond,
    } as never);
    expect(sendRawOscViaPython).toHaveBeenCalledWith("/avatar/parameters/Test", [true]);

    await findHandler(
      registerGatewayMethod,
      "vrchat.status",
    )({
      params: {},
      respond,
    } as never);

    expect(respond).toHaveBeenCalledWith(
      true,
      expect.objectContaining({
        ok: true,
        listener: expect.objectContaining({ isRunning: true, port: 9001 }),
      }),
    );
  });
});
