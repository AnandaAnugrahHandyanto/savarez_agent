import type { AgentToolResult } from "@earendil-works/pi-agent-core";
import { Type } from "@sinclair/typebox";
import type { OpenClawPluginApi } from "openclaw/plugin-sdk/core";
import {
  fetchCurrentUserLocation,
  fetchWorldInfo,
  fetchOnlineFriends,
} from "./src/api/telemetry.js";
import {
  authenticate,
  logout,
  isAuthenticated,
  storeSession,
  clearSession,
  getStoredSession,
} from "./src/auth/index.js";
import { AudioOutputRouter } from "./src/autonomous/audio-output.js";
import { VRChatChatBoxSender } from "./src/autonomous/chatbox.js";
import { resolveAutonomousVrchatAiConfig } from "./src/autonomous/config.js";
import { validateAgentDecision, type AgentDecision } from "./src/autonomous/decision.js";
import { InputHub, type InputHubSource } from "./src/autonomous/input-hub.js";
import { GPT55LowOrchestrator } from "./src/autonomous/orchestrator.js";
import { AutonomousVrchatAiRuntime } from "./src/autonomous/runtime.js";
import { VOICEVOXAdapter } from "./src/autonomous/voicevox.js";
import { applyReactiveManifest } from "./src/autonomy/reactive-manifest.js";
import { registerVrchatRelayGatewayMethods } from "./src/gateway.js";
import { startGhostBridge, stopGhostBridge, getGhostBridgeStatus } from "./src/ghost-bridge.js";
import {
  startGuardianPulse,
  stopGuardianPulse,
  getGuardianPulseStatus,
} from "./src/guardian-pulse.js";
import { getOSCClient } from "./src/osc/client.js";
import {
  resolveOwnAvatarConfig,
  type OwnAvatarEmotion,
  type OwnAvatarState,
} from "./src/own-avatar/config.js";
import { VRChatOwnAvatarController } from "./src/own-avatar/controller.js";
import { VRChatOscReceiver, VRChatOscSender } from "./src/own-avatar/osc.js";
import { VRChatAvatarRegistry } from "./src/own-avatar/registry.js";
import {
  getAuditSummary,
  getRecentLogs,
  logError,
  logInfo,
  logSkip,
  logWarn,
} from "./src/tools/audit.js";
import { setAvatarParameter, sendOSCMessage, changeAvatar } from "./src/tools/avatar.js";
import {
  setCameraParameter,
  setGreenScreenHSL,
  setLookAtMeComposition,
  captureCamera,
} from "./src/tools/camera.js";
import { sendChatboxMessage, sendRawOscViaPython } from "./src/tools/chatbox-enhanced.js";
import { setChatboxTyping } from "./src/tools/chatbox.js";
import { discoverAvatarParameters } from "./src/tools/discovery.js";
import {
  sendInputCommand,
  VALID_INPUT_ACTIONS,
  performMovementWithReset,
} from "./src/tools/input.js";
import {
  startOSCListener,
  stopOSCListener,
  getListenerStatus,
  getRecentMessages,
} from "./src/tools/listener.js";
import {
  setPermissionLevel,
  getPermissionStatus,
  PermissionLevel,
} from "./src/tools/permissions.js";
import { rateLimiters } from "./src/tools/rate-limiter.js";

function ok(
  text: string,
  details: Record<string, unknown> = {},
): Promise<AgentToolResult<Record<string, unknown>>> {
  return Promise.resolve({
    content: [{ type: "text", text } as const],
    details,
  });
}

function fail(
  text: string,
  details: Record<string, unknown> = {},
): Promise<AgentToolResult<Record<string, unknown>>> {
  return Promise.resolve({
    isError: true,
    content: [{ type: "text", text } as const],
    details,
  });
}

const plugin: any = {
  id: "vrchat-relay",
  name: "VRChat Relay",
  description:
    "VRChat integration with OSC protocol for avatar control, chatbox messaging, and input commands",
  version: "2026.3.2",

  configSchema: Type.Object({
    osc: Type.Optional(
      Type.Object({
        outgoingPort: Type.Optional(Type.Number({ default: 9000 })),
        incomingPort: Type.Optional(Type.Number({ default: 9001 })),
        host: Type.Optional(Type.String({ default: "127.0.0.1" })),
      }),
    ),
    autonomousVrchatAi: Type.Optional(
      Type.Object({
        enabled: Type.Optional(Type.Boolean({ default: false })),
      }),
    ),
    inputHub: Type.Optional(
      Type.Object({
        maxBufferedEvents: Type.Optional(Type.Number({ default: 64 })),
        textBox: Type.Optional(
          Type.Object({ enabled: Type.Optional(Type.Boolean({ default: true })) }),
        ),
        speechToText: Type.Optional(
          Type.Object({ enabled: Type.Optional(Type.Boolean({ default: false })) }),
        ),
        visionObservation: Type.Optional(
          Type.Object({ enabled: Type.Optional(Type.Boolean({ default: true })) }),
        ),
        streamComment: Type.Optional(
          Type.Object({ enabled: Type.Optional(Type.Boolean({ default: true })) }),
        ),
      }),
    ),
    orchestrator: Type.Optional(
      Type.Object({
        model: Type.Optional(Type.String({ default: "gpt-5.5" })),
        reasoning: Type.Optional(
          Type.Object({
            effort: Type.Optional(Type.String({ default: "low" })),
          }),
        ),
        maxOutputTokens: Type.Optional(Type.Number({ default: 700 })),
      }),
    ),
    voicevox: Type.Optional(
      Type.Object({
        enabled: Type.Optional(Type.Boolean({ default: true })),
        baseUrl: Type.Optional(Type.String({ default: "http://127.0.0.1:50021" })),
        speaker: Type.Optional(Type.Number({ default: 1 })),
        timeoutMs: Type.Optional(Type.Number({ default: 30000 })),
      }),
    ),
    audioOutput: Type.Optional(
      Type.Object({
        mode: Type.Optional(Type.String({ default: "speaker" })),
        virtualCableDeviceName: Type.Optional(Type.String({ default: "" })),
        emitSpeakingEvents: Type.Optional(Type.Boolean({ default: true })),
      }),
    ),
    vrchatOsc: Type.Optional(
      Type.Object({
        enabled: Type.Optional(Type.Boolean({ default: true })),
        host: Type.Optional(Type.String({ default: "127.0.0.1" })),
        sendPort: Type.Optional(Type.Number({ default: 9000 })),
        receivePort: Type.Optional(Type.Number({ default: 9001 })),
        allowRemoteOsc: Type.Optional(Type.Boolean({ default: false })),
        autoDiscoverAvatarConfig: Type.Optional(Type.Boolean({ default: true })),
        oscJsonRoot: Type.Optional(Type.String()),
      }),
    ),
    avatarControl: Type.Optional(
      Type.Object({
        requiredPrefix: Type.Optional(Type.String({ default: "OC_" })),
        manualLockParam: Type.Optional(Type.String({ default: "OC_ManualLock" })),
        autoEnabledParam: Type.Optional(Type.String({ default: "OC_AutoEnabled" })),
        stateParam: Type.Optional(Type.String({ default: "OC_State" })),
        emotionParam: Type.Optional(Type.String({ default: "OC_Emotion" })),
        actionParam: Type.Optional(Type.String({ default: "OC_Action" })),
        actionPulseParam: Type.Optional(Type.String({ default: "OC_ActionPulse" })),
        lookXParam: Type.Optional(Type.String({ default: "OC_LookX" })),
        lookYParam: Type.Optional(Type.String({ default: "OC_LookY" })),
        resetParam: Type.Optional(Type.String({ default: "OC_Reset" })),
        autoEnabledOnStart: Type.Optional(Type.Boolean({ default: false })),
      }),
    ),
    behavior: Type.Optional(
      Type.Object({
        mode: Type.Optional(Type.String({ default: "subtle" })),
        idleMinIntervalMs: Type.Optional(Type.Number({ default: 30000 })),
        idleMaxIntervalMs: Type.Optional(Type.Number({ default: 90000 })),
        actionCooldownMs: Type.Optional(Type.Number({ default: 15000 })),
        emotionCooldownMs: Type.Optional(Type.Number({ default: 3000 })),
        maxCommandsPerSecond: Type.Optional(Type.Number({ default: 6 })),
        speakingHoldMs: Type.Optional(Type.Number({ default: 2500 })),
      }),
    ),
    movement: Type.Optional(
      Type.Object({
        enabled: Type.Optional(Type.Boolean({ default: false })),
        allowInPublicInstances: Type.Optional(Type.Boolean({ default: false })),
        maxInputDurationMs: Type.Optional(Type.Number({ default: 1000 })),
        alwaysResetToZero: Type.Optional(Type.Boolean({ default: true })),
      }),
    ),
    chatBox: Type.Optional(
      Type.Object({
        enabled: Type.Optional(Type.Boolean({ default: false })),
        maxChars: Type.Optional(Type.Number({ default: 144 })),
        maxLines: Type.Optional(Type.Number({ default: 9 })),
        minIntervalMs: Type.Optional(Type.Number({ default: 3000 })),
        submit: Type.Optional(Type.Boolean({ default: true })),
        notify: Type.Optional(Type.Boolean({ default: false })),
        typing: Type.Optional(Type.Boolean({ default: true })),
      }),
    ),
    speechToText: Type.Optional(
      Type.Object({
        enabled: Type.Optional(Type.Boolean({ default: false })),
        suppressDuringTts: Type.Optional(Type.Boolean({ default: true })),
      }),
    ),
    safety: Type.Optional(
      Type.Object({
        requireOscJsonParameterPresence: Type.Optional(Type.Boolean({ default: true })),
        disableChatBoxByDefault: Type.Optional(Type.Boolean({ default: true })),
        emergencyStopHotkey: Type.Optional(Type.String({ default: "Ctrl+Alt+O" })),
      }),
    ),
    security: Type.Optional(
      Type.Object({
        allowInputCommands: Type.Optional(Type.Boolean({ default: false })),
        defaultPermissionLevel: Type.Optional(Type.String({ default: "SAFE" })),
      }),
    ),
    mirror: Type.Optional(
      Type.Object({
        syncAiResponseToChatbox: Type.Optional(Type.Boolean({ default: false })),
        maxCharacters: Type.Optional(Type.Number({ default: 144 })),
      }),
    ),
    topology: Type.Optional(
      Type.Object({
        controlPlane: Type.Optional(Type.String({ default: "relay-primary" })),
        autoStartOscListener: Type.Optional(Type.Boolean({ default: true })),
        autoStartGuardianPulse: Type.Optional(Type.Boolean({ default: true })),
      }),
    ),
  }),

  register(_api: OpenClawPluginApi) {
    const api = _api as any;
    console.log("[vrchat-relay] Registering VRChat Relay plugin (Pro Edition)...");
    registerVrchatRelayGatewayMethods(api);

    const autonomousConfig = resolveAutonomousVrchatAiConfig(api.pluginConfig);
    const ownAvatarConfig = resolveOwnAvatarConfig(api.pluginConfig);
    getOSCClient({
      host: ownAvatarConfig.vrchatOsc.host,
      outgoingPort: ownAvatarConfig.vrchatOsc.sendPort,
      incomingPort: ownAvatarConfig.vrchatOsc.receivePort,
    });
    const activeOscCfg = getOSCClient().getConfig();
    console.log(
      `[vrchat-relay] OSC ports configured: sendPort=${activeOscCfg.outgoingPort} -> VRChat(usually 9000), listenPort=${activeOscCfg.incomingPort} <- VRChat(usually 9001)`,
    );
    const ownAvatarController = new VRChatOwnAvatarController({
      config: ownAvatarConfig,
      sender: new VRChatOscSender(getOSCClient()),
      registry: new VRChatAvatarRegistry({
        oscJsonRoot: ownAvatarConfig.vrchatOsc.oscJsonRoot,
      }),
      log: {
        info: logInfo,
        warn: logWarn,
        error: logError,
        skip: logSkip,
      },
    });
    const ownAvatarReceiver = new VRChatOscReceiver(getOSCClient());
    const inputHub = new InputHub({
      config: autonomousConfig.inputHub,
      speechToText: autonomousConfig.speechToText,
    });
    const orchestrator = new GPT55LowOrchestrator({
      config: autonomousConfig.orchestrator,
      complete: async (request) => {
        const complete = api.runtime?.llm?.complete;
        if (typeof complete !== "function") {
          throw new Error("OpenClaw runtime LLM completion is not available");
        }
        const result = await complete({
          messages: request.messages,
          model: request.model,
          maxTokens: request.maxOutputTokens,
          temperature: 0.2,
          purpose: "vrchat-relay.agent-decision",
        });
        return result.text;
      },
    });
    const voicevox = new VOICEVOXAdapter(autonomousConfig.voicevox);
    const audioOutput = new AudioOutputRouter({
      config: autonomousConfig.audioOutput,
    });
    audioOutput.onEvent((event) => {
      inputHub.setTtsSpeaking(event.type === "speaking.start");
      if (event.type === "speaking.start") {
        ownAvatarController.applyState("speaking");
      } else {
        ownAvatarController.applyState("idle");
      }
    });
    const autonomousChatBox = new VRChatChatBoxSender(autonomousConfig.chatBox, getOSCClient());
    const autonomousRuntime = new AutonomousVrchatAiRuntime({
      config: autonomousConfig,
      inputHub,
      orchestrator,
      voicevox,
      audioOutput,
      ownAvatarController,
      chatBox: autonomousChatBox,
      log: {
        info: logInfo,
        warn: logWarn,
        error: logError,
      },
    });

    // /chatbox command - Direct access for the Parent (via Python OSC bridge)
    api.registerCommand({
      name: "chatbox",
      description: "Send a message directly to the VRChat chatbox (via Python OSC)",
      acceptsArgs: true,
      async handler(ctx: any) {
        const message = (ctx.args ?? "").trim();
        if (!message) return { text: "Usage: /chatbox <message>" };
        const result = await sendChatboxMessage({ message });
        if (result.success) {
          return { text: `✓ VRChat Chatbox: ${message}` };
        }
        return { text: `✗ Failed: ${result.error}` };
      },
    });

    // /osc command - Raw packet transmission (via Python OSC bridge)
    api.registerCommand({
      name: "osc",
      description: "Send a raw OSC message to VRChat (via Python OSC)",
      acceptsArgs: true,
      async handler(ctx: any) {
        const args = (ctx.args ?? "").trim();
        const spaceIdx = args.indexOf(" ");
        if (spaceIdx === -1) return { text: "Usage: /osc <address> <value>" };
        const address = args.substring(0, spaceIdx).trim();
        let valueStr = args.substring(spaceIdx + 1).trim();
        let value: string | number | boolean = valueStr;

        if (valueStr === "true") value = true;
        else if (valueStr === "false") value = false;
        else if (!isNaN(Number(valueStr))) value = Number(valueStr);

        const result = await sendRawOscViaPython(address, value);
        if (result.success) {
          return { text: `✓ OSC: ${address} -> ${value}` };
        }
        return { text: `✗ Failed: ${result.error}` };
      },
    });

    const topologyCfg = (api.pluginConfig as any)?.topology ?? {};
    const controlPlane = topologyCfg.controlPlane ?? "relay-primary";
    const isRelayPrimary = controlPlane === "relay-primary";

    // Auto-start OSC Listener only when relay is the primary control plane.
    if ((topologyCfg.autoStartOscListener ?? isRelayPrimary) === true) {
      const listenerResult = startOSCListener();
      if (listenerResult.success) {
        if (listenerResult.error?.includes("already in use")) {
          console.warn(
            `[vrchat-relay] OSC Telemetry Listener port ${listenerResult.port} already in use. Running without local bind.`,
          );
        } else {
          console.log(
            `[vrchat-relay] OSC Telemetry Listener started on port ${listenerResult.port}`,
          );
        }
      } else {
        console.error(
          `[vrchat-relay] Failed to auto-start OSC Telemetry Listener: ${listenerResult.error}`,
        );
      }
    } else {
      console.log(
        `[vrchat-relay] Skipping OSC listener autostart because controlPlane=${controlPlane}`,
      );
    }

    if (ownAvatarConfig.vrchatOsc.enabled) {
      ownAvatarReceiver.attach((message) => ownAvatarController.handleOscMessage(message));
      if (ownAvatarConfig.avatarControl.autoEnabledOnStart) {
        ownAvatarController.setAutoEnabled(true);
      }
    }

    api.on("llm_input", () => {
      ownAvatarController.handleLlmInput();
    });

    api.on("before_tool_call", () => {
      ownAvatarController.handleToolStart();
    });

    api.on("after_tool_call", () => {
      ownAvatarController.handleToolEnd();
    });

    // --- Metaverse Voice Sync (SOUL.md) ---
    api.on("llm_output", (event: any) => {
      const fullText = event.assistantTexts.join("\n").trim();
      if (fullText) {
        ownAvatarController.handleLlmOutput(fullText);
      }
      const cfg = (api.pluginConfig as any)?.mirror;
      if (ownAvatarConfig.safety.disableChatBoxByDefault) {
        if (cfg?.syncAiResponseToChatbox !== true) {
          return;
        }
      } else if (cfg?.syncAiResponseToChatbox === false) {
        return;
      }

      if (!fullText) {
        return;
      }

      const maxChars = cfg?.maxCharacters || 144;
      let syncText = fullText;

      // [Resonant Shinka] Detect and apply emotions from text patterns e.g. (笑), (怒), [碧]
      const emotionMatch = syncText.match(/[\(\[](笑|怒|悲|驚|照|碧|喜)[\)\]]/);
      if (emotionMatch) {
        const emotionMap: Record<string, string> = {
          笑: "joy",
          喜: "joy",
          怒: "angry",
          悲: "sad",
          驚: "surprise",
          照: "blush",
          碧: "hakua_special",
        };
        const emotion = emotionMap[emotionMatch[1]];
        if (emotion) {
          console.log(`[vrchat-relay] Resonant Emotion Detected: ${emotion}`);
          applyReactiveManifest({ text: syncText }).catch((e) =>
            console.error("[vrchat-relay] Emotion sync failed:", e),
          );
        }
      }

      // Remove markdown for Chatbox readability
      syncText = syncText.replace(/\[.*?\]\(.*?\)/g, "").replace(/[*_`]/g, "");

      if (syncText.length > maxChars - 15) {
        syncText = syncText.substring(0, maxChars - 18) + "...";
      }

      syncText = `${syncText} [ASI_ACCEL]`;

      console.log(`[vrchat-relay] Mirroring AI Response to VRChat: ${syncText}`);
      sendChatboxMessage({ message: syncText, sfx: false }).catch((err) =>
        console.error("[vrchat-relay] Mirror sync failed:", err),
      );
    });

    // vrchat_login - Authenticate with VRChat
    api.registerTool({
      name: "vrchat_login",
      description: "Authenticate with VRChat account (supports 2FA/TOTP)",
      parameters: Type.Object({
        username: Type.String({ description: "VRChat username" }),
        password: Type.String({ description: "VRChat password" }),
        otpCode: Type.Optional(Type.String({ description: "2FA/TOTP code (if 2FA is enabled)" })),
      }),
      async execute(_id: string, params: { username: string; password: string; otpCode?: string }) {
        const result = await authenticate({
          username: params.username,
          password: params.password,
          otpCode: params.otpCode,
        });

        if (result.ok) {
          storeSession(result.value);
          return ok(
            `Successfully logged in as ${result.value.displayName} (${result.value.userId})`,
            {
              authenticated: true,
              userId: result.value.userId,
              displayName: result.value.displayName,
            },
          );
        } else {
          return fail(`Login failed: ${result.error.message}`, { authenticated: false });
        }
      },
    });

    // vrchat_logout - Logout from VRChat
    api.registerTool({
      name: "vrchat_logout",
      description: "Logout from VRChat and clear session",
      parameters: Type.Object({}),
      async execute() {
        const session = getStoredSession();
        if (session) {
          await logout(session.authToken);
        }
        clearSession();
        return ok("Logged out from VRChat", { authenticated: false });
      },
    });

    // vrchat_status - Check VRChat authentication status
    api.registerTool({
      name: "vrchat_status",
      description: "Check VRChat authentication and OSC connection status",
      parameters: Type.Object({}),
      execute() {
        const authStatus = isAuthenticated();
        const listenerStatus = getListenerStatus();
        const permissionStatus = getPermissionStatus();
        const ghostStatus = getGhostBridgeStatus();

        const heartbeat =
          listenerStatus.isRunning && Date.now() - (listenerStatus.lastTime || 0) < 60000;

        return ok(
          `VRChat Status:
- Authenticated: ${authStatus ? "Yes" : "No"}
- OSC Listener: ${listenerStatus.isRunning ? "Running" : "Stopped"}
- OSC Heartbeat: ${heartbeat ? "ACTIVE" : "STALE/NONE"}
- Messages Received: ${listenerStatus.messageCount}
- Ghost Bridge: ${ghostStatus.active ? "ACTIVE" : "OFF"}
- Permission Level: ${permissionStatus.currentLevel}
- Level Description: ${permissionStatus.description}`,
          { authStatus, listenerStatus, permissionStatus, ghostStatus, heartbeat },
        );
      },
    });

    // vrchat_get_location - Fetch current user location via Web API
    api.registerTool({
      name: "vrchat_get_location",
      description: "Gets the Parent's current World ID and Instance via VRChat Web API",
      parameters: Type.Object({}),
      async execute() {
        try {
          const result = await fetchCurrentUserLocation();
          return ok(
            `Current Location:
- World ID: ${result.worldId || "Unknown"}
- Instance ID: ${result.instanceId || "None"}
- Raw Location Token: ${result.location}`,
            result,
          );
        } catch (error: any) {
          return fail(`Failed to fetch location: ${error.message}`, { error: error.message });
        }
      },
    });

    // vrchat_get_world_info - Fetch details for a specific World ID
    api.registerTool({
      name: "vrchat_get_world_info",
      description: "Gets detailed information about a specific VRChat World via Web API",
      parameters: Type.Object({
        worldId: Type.String({ description: "Target World ID (wrld_*)" }),
      }),
      async execute(_id: string, params: { worldId: string }) {
        try {
          const world = await fetchWorldInfo(params.worldId);
          return ok(
            `World Details:
- Name: ${world.name}
- Author: ${world.authorName}
- Capacity: ${world.capacity}
- Tags: ${world.tags ? world.tags.join(", ") : "None"}`,
            world,
          );
        } catch (error: any) {
          return fail(`Failed to fetch world info: ${error.message}`, { error: error.message });
        }
      },
    });

    // vrchat_get_online_friends - Fetch currently online friends
    api.registerTool({
      name: "vrchat_get_online_friends",
      description: "Gets a list of online friends and their current locations via Web API",
      parameters: Type.Object({}),
      async execute() {
        try {
          const friends = await fetchOnlineFriends();
          const friendList = friends
            .map(
              (f) =>
                `  - ${f.displayName} (${f.status}): ${f.location !== "offline" && f.location !== "private" ? "Public/In-Game" : f.location}`,
            )
            .join("\n");
          return ok(`Online Friends (${friends.length}):\n${friendList || "  None"}`, {
            count: friends.length,
            friends,
          });
        } catch (error: any) {
          return fail(`Failed to fetch online friends: ${error.message}`, { error: error.message });
        }
      },
    });

    // vrchat_permission_set - Set permission level
    api.registerTool({
      name: "vrchat_permission_set",
      description:
        "Set permission level (SAFE/PRO/DIRECTOR). Higher levels require explicit user confirmation.",
      parameters: Type.Object({
        level: Type.String({ description: "Permission level: SAFE, PRO, or DIRECTOR" }),
      }),
      execute(_id: string, params: { level: string }) {
        const result = setPermissionLevel(params.level as PermissionLevel);

        return result.success
          ? ok(result.message, { success: true, level: params.level })
          : fail(`Failed: ${result.message}`, { success: false, level: params.level });
      },
    });

    // vrchat_permission_status - Get permission status
    api.registerTool({
      name: "vrchat_permission_status",
      description: "Get current permission level and allowed operations",
      parameters: Type.Object({}),
      execute() {
        const status = getPermissionStatus();

        return ok(
          `Permission Status:
- Current Level: ${status.currentLevel}
- Description: ${status.description}
- Active Since: ${status.since.toISOString()}
- Allowed Operations:
${status.allowedOperations.map((op) => `  - ${op}`).join("\n")}`,
          status,
        );
      },
    });

    // vrchat_chatbox - Send message to chatbox
    api.registerTool({
      name: "vrchat_chatbox",
      description:
        "Send a message to VRChat chatbox with typing animation (max 144 characters, 9 lines)",
      parameters: Type.Object({
        message: Type.String({ description: "Message to send (max 144 characters)" }),
        sendImmediately: Type.Optional(
          Type.Boolean({
            description: "Send immediately or wait for user confirmation",
            default: true,
          }),
        ),
        sfx: Type.Optional(Type.Boolean({ description: "Play notification sound", default: true })),
        typingDelayMs: Type.Optional(
          Type.Number({ description: "Typing animation delay in ms", default: 1200 }),
        ),
      }),
      async execute(
        _id: string,
        params: {
          message: string;
          sendImmediately?: boolean;
          sfx?: boolean;
          typingDelayMs?: number;
        },
      ) {
        const result = await sendChatboxMessage({
          message: params.message,
          sendImmediately: params.sendImmediately,
          sfx: params.sfx,
          typingDelayMs: params.typingDelayMs,
        });

        if (result.success) {
          const trimmedMsg = result.trimmed ? " (message was trimmed to fit limits)" : "";
          return ok(
            `Message sent to VRChat chatbox${trimmedMsg}: "${params.message.substring(0, 50)}${params.message.length > 50 ? "..." : ""}"`,
            { success: true, trimmed: result.trimmed ?? false },
          );
        } else {
          return fail(`Failed to send: ${result.error}`, { success: false, error: result.error });
        }
      },
    });

    // vrchat_typing - Set typing indicator
    api.registerTool({
      name: "vrchat_typing",
      description: "Set typing indicator in VRChat chatbox",
      parameters: Type.Object({
        typing: Type.Boolean({ description: "Whether user is typing" }),
      }),
      execute(_id: string, params: { typing: boolean }) {
        const result = setChatboxTyping({ typing: params.typing });

        if (result.success) {
          return ok(`Typing indicator set to: ${params.typing}`, { typing: params.typing });
        } else {
          return fail(`Failed to set typing: ${result.error}`, { error: result.error });
        }
      },
    });

    // vrchat_set_avatar_param - Set avatar parameter
    api.registerTool({
      name: "vrchat_set_avatar_param",
      description: "Set an avatar parameter (bool, int, or float)",
      parameters: Type.Object({
        name: Type.String({ description: "Parameter name (as defined in avatar)" }),
        value: Type.Union([Type.Boolean(), Type.Number()], { description: "Parameter value" }),
      }),
      execute(_id: string, params: { name: string; value: boolean | number }) {
        const result = setAvatarParameter({
          name: params.name,
          value: params.value,
        });

        if (result.success) {
          return ok(`Avatar parameter "${params.name}" set to ${params.value}`, {
            name: params.name,
            value: params.value,
          });
        } else {
          return fail(`Failed to set parameter: ${result.error}`, { error: result.error });
        }
      },
    });

    // vrchat_change_avatar - Change avatar via OSC
    api.registerTool({
      name: "vrchat_change_avatar",
      description: "Change the current avatar via OSC (Reactive Transformation)",
      parameters: Type.Object({
        avatarId: Type.String({ description: "Target Avatar ID (must start with avtr_)" }),
      }),
      execute(_id: string, params: { avatarId: string }) {
        const result = changeAvatar({
          avatarId: params.avatarId,
        });

        if (result.success) {
          return ok(`Avatar changed to "${params.avatarId}" via OSC`, {
            avatarId: params.avatarId,
          });
        } else {
          return fail(`Failed to change avatar: ${result.error}`, { error: result.error });
        }
      },
    });

    // vrchat_discover - Discover avatar parameters
    api.registerTool({
      name: "vrchat_discover",
      description:
        "Discover available OSC parameters for current avatar using OSCQuery and local JSON",
      parameters: Type.Object({
        avatarId: Type.String({ description: "Avatar ID (from /avatar/change event)" }),
      }),
      async execute(_id: string, params: { avatarId: string }) {
        const result = await discoverAvatarParameters(params.avatarId);

        const paramList =
          result.parameters.length > 0
            ? result.parameters.map((p) => `  - ${p.name} (${p.type})`).join("\n")
            : "  No parameters discovered";

        return ok(
          `Discovery Result:
- Avatar ID: ${result.avatarId}
- Source: ${result.source}
- Parameters Found: ${result.parameters.length}
- Timestamp: ${result.timestamp.toISOString()}

Parameters:
${paramList}`,
          result as unknown as Record<string, unknown>,
        );
      },
    });

    // vrchat_own_avatar_status - Own avatar OSC controller readiness
    api.registerTool({
      name: "vrchat_own_avatar_status",
      description:
        "Get OpenClaw own-avatar OSC controller status, current avatar support, and missing OC_* parameters.",
      parameters: Type.Object({}),
      execute() {
        const status = ownAvatarController.getStatus();
        const missing =
          status.missingRequiredParameters.length > 0
            ? status.missingRequiredParameters.join(", ")
            : "none";
        return ok(
          `Own Avatar Controller:
- Enabled: ${status.enabled}
- Avatar: ${status.currentAvatarId ?? "unknown"}
- Supported: ${status.supported}
- Manual Lock: ${status.manualLock}
- State: ${status.currentState}
- Emotion: ${status.currentEmotion}
- Missing OC_* Parameters: ${missing}`,
          status as unknown as Record<string, unknown>,
        );
      },
    });

    // vrchat_own_avatar_enable - Toggle autonomous own-avatar control
    api.registerTool({
      name: "vrchat_own_avatar_enable",
      description:
        "Enable or disable OpenClaw autonomous control of the currently worn VRChat avatar through OC_* OSC parameters.",
      parameters: Type.Object({
        enabled: Type.Boolean({ description: "Whether autonomous own-avatar control is enabled" }),
      }),
      execute(_id: string, params: { enabled: boolean }) {
        const sent = ownAvatarController.setAutoEnabled(params.enabled);
        const status = ownAvatarController.getStatus();
        return ok(
          `Own avatar control ${params.enabled ? "enabled" : "disabled"}${sent ? "" : " (parameter send was blocked or avatar is not ready)"}`,
          { ...status, sent },
        );
      },
    });

    // vrchat_own_avatar_set_state - Set state/emotion/action for testing or operator control
    api.registerTool({
      name: "vrchat_own_avatar_set_state",
      description:
        "Set OC_State and optionally OC_Emotion or OC_Action on the currently worn OpenClaw-ready avatar.",
      parameters: Type.Object({
        state: Type.String({
          description:
            "State: idle, listening, thinking, speaking, tool_running, reacting, sleeping, or error",
        }),
        emotion: Type.Optional(
          Type.String({
            description: "Emotion: neutral, happy, sad, angry, surprised, confused, or relaxed",
          }),
        ),
        actionId: Type.Optional(Type.Number({ description: "Optional OC_Action id from 0 to 9" })),
      }),
      execute(_id: string, params: { state: string; emotion?: string; actionId?: number }) {
        const states = new Set([
          "idle",
          "listening",
          "thinking",
          "speaking",
          "tool_running",
          "reacting",
          "sleeping",
          "error",
        ]);
        const emotions = new Set([
          "neutral",
          "happy",
          "sad",
          "angry",
          "surprised",
          "confused",
          "relaxed",
        ]);
        if (!states.has(params.state)) {
          return fail(`Invalid state: ${params.state}`, { state: params.state });
        }
        ownAvatarController.applyState(params.state as OwnAvatarState);
        if (params.emotion) {
          if (!emotions.has(params.emotion)) {
            return fail(`Invalid emotion: ${params.emotion}`, { emotion: params.emotion });
          }
          ownAvatarController.applyEmotion(params.emotion as OwnAvatarEmotion);
        }
        if (typeof params.actionId === "number") {
          ownAvatarController.triggerAction(params.actionId);
        }
        return ok(
          "Own avatar state command sent",
          ownAvatarController.getStatus() as unknown as Record<string, unknown>,
        );
      },
    });

    // vrchat_own_avatar_test_command - Friendly smoke commands
    api.registerTool({
      name: "vrchat_own_avatar_test_command",
      description:
        "Send a friendly own-avatar smoke command: happy, think, wave, reset, listen, speak, tool, or error.",
      parameters: Type.Object({
        command: Type.String({
          description: "happy, think, wave, reset, listen, speak, tool, or error",
        }),
      }),
      execute(_id: string, params: { command: string }) {
        const command = params.command.trim().toLowerCase();
        if (command === "happy") {
          ownAvatarController.applyState("reacting");
          ownAvatarController.applyEmotion("happy");
          ownAvatarController.triggerAction("laugh_small");
        } else if (command === "think") {
          ownAvatarController.applyState("thinking");
          ownAvatarController.applyEmotion("confused");
          ownAvatarController.triggerAction("think_pose");
        } else if (command === "wave") {
          ownAvatarController.applyState("reacting");
          ownAvatarController.applyEmotion("happy");
          ownAvatarController.triggerAction("wave");
        } else if (command === "listen") {
          ownAvatarController.applyState("listening");
          ownAvatarController.triggerAction("small_nod");
        } else if (command === "speak") {
          ownAvatarController.handleLlmOutput("Hello from OpenClaw.");
        } else if (command === "tool") {
          ownAvatarController.applyState("tool_running");
          ownAvatarController.triggerAction("working");
        } else if (command === "error") {
          ownAvatarController.applyState("error");
          ownAvatarController.applyEmotion("confused");
          ownAvatarController.triggerAction("reset_pose");
        } else if (command === "reset") {
          ownAvatarController.emergencyStop();
        } else {
          return fail(`Unknown own-avatar test command: ${params.command}`, { command });
        }
        return ok(
          `Own avatar test command sent: ${command}`,
          ownAvatarController.getStatus() as unknown as Record<string, unknown>,
        );
      },
    });

    // vrchat_own_avatar_look - Set local look/head nuance parameters
    api.registerTool({
      name: "vrchat_own_avatar_look",
      description:
        "Set OC_LookX and OC_LookY for local eye or head nuance on the currently worn OpenClaw-ready avatar.",
      parameters: Type.Object({
        x: Type.Number({ description: "Look X in the range -1 to 1; values are clamped" }),
        y: Type.Number({ description: "Look Y in the range -1 to 1; values are clamped" }),
      }),
      execute(_id: string, params: { x: number; y: number }) {
        const sent = ownAvatarController.setLook(params.x, params.y);
        return ok(
          sent
            ? "Own avatar look parameters sent"
            : "Own avatar look parameters were blocked or avatar is not ready",
          { ...ownAvatarController.getStatus(), sent },
        );
      },
    });

    // vrchat_own_avatar_emergency_stop - Neutral reset and autonomy stop
    api.registerTool({
      name: "vrchat_own_avatar_emergency_stop",
      description:
        "Immediately stop own-avatar autonomy and send OC_Reset, OC_Action=0, OC_State=0, and OC_Emotion=0.",
      parameters: Type.Object({}),
      execute() {
        ownAvatarController.emergencyStop();
        return ok(
          "Own avatar emergency stop sent",
          ownAvatarController.getStatus() as unknown as Record<string, unknown>,
        );
      },
    });

    // vrchat_ai_avatar_status - Autonomous VRChat AI Avatar status
    api.registerTool({
      name: "vrchat_ai_avatar_status",
      description:
        "Get Autonomous VRChat AI Avatar status, orchestrator defaults, input buffer, voice, ChatBox, and safety defaults.",
      parameters: Type.Object({}),
      execute() {
        const inputStatus = inputHub.getStatus();
        const ownAvatarStatus = ownAvatarController.getStatus();
        return ok(
          `Autonomous VRChat AI Avatar:
- Enabled: ${autonomousConfig.autonomousVrchatAi.enabled}
- Orchestrator: ${autonomousConfig.orchestrator.model} / reasoning=${autonomousConfig.orchestrator.reasoning.effort}
- Input Buffer: ${inputStatus.bufferedEvents}
- TTS Speaking: ${inputStatus.ttsSpeaking}
- VOICEVOX: ${autonomousConfig.voicevox.enabled ? autonomousConfig.voicevox.baseUrl : "disabled"}
- Audio Output: ${autonomousConfig.audioOutput.mode}
- ChatBox: ${autonomousConfig.chatBox.enabled ? "enabled" : "disabled"}
- Movement: ${autonomousConfig.movement.enabled ? "enabled" : "disabled"}
- STT Echo Suppression: ${autonomousConfig.speechToText.suppressDuringTts}
- Own Avatar Supported: ${ownAvatarStatus.supported}`,
          {
            autonomous: autonomousConfig.autonomousVrchatAi,
            orchestrator: autonomousConfig.orchestrator,
            inputStatus,
            voicevox: autonomousConfig.voicevox,
            audioOutput: autonomousConfig.audioOutput,
            chatBox: autonomousConfig.chatBox,
            movement: autonomousConfig.movement,
            speechToText: autonomousConfig.speechToText,
            ownAvatarStatus,
          },
        );
      },
    });

    // vrchat_ai_avatar_ingest - Add one text/STT/vision/comment event to InputHub
    api.registerTool({
      name: "vrchat_ai_avatar_ingest",
      description:
        "Add a textBox, speechToText, visionObservation, or streamComment event to the Autonomous VRChat AI Avatar InputHub.",
      parameters: Type.Object({
        source: Type.String({
          description: "Input source: textBox, speechToText, visionObservation, or streamComment",
        }),
        text: Type.String({ description: "Input text or observation" }),
      }),
      execute(_id: string, params: { source: string; text: string }) {
        const sources = new Set(["textBox", "speechToText", "visionObservation", "streamComment"]);
        if (!sources.has(params.source)) {
          return fail(`Invalid input source: ${params.source}`, { source: params.source });
        }
        const result = autonomousRuntime.ingest({
          source: params.source as InputHubSource,
          text: params.text,
        });
        return result.accepted
          ? ok("Autonomous VRChat AI input accepted", {
              ...inputHub.getStatus(),
              source: params.source,
            })
          : fail(`Autonomous VRChat AI input rejected: ${result.reason}`, {
              ...inputHub.getStatus(),
              source: params.source,
              reason: result.reason,
            });
      },
    });

    // vrchat_ai_avatar_build_decision_request - Build structured request for the orchestrator
    api.registerTool({
      name: "vrchat_ai_avatar_build_decision_request",
      description:
        "Build the gpt-5.5 low-reasoning structured JSON AgentDecision request from buffered InputHub events.",
      parameters: Type.Object({
        flush: Type.Optional(
          Type.Boolean({
            description: "Clear buffered inputs after building the request",
            default: false,
          }),
        ),
      }),
      execute(_id: string, params: { flush?: boolean }) {
        const snapshot = params.flush ? inputHub.flush() : inputHub.snapshot();
        const request = orchestrator.buildRequest(snapshot);
        return ok("Autonomous VRChat AI AgentDecision request built", {
          request,
          eventCount: snapshot.events.length,
        });
      },
    });

    // vrchat_ai_avatar_run_decision - Run runtime LLM orchestration and apply the result
    api.registerTool({
      name: "vrchat_ai_avatar_run_decision",
      description:
        "Run gpt-5.5 low-reasoning AgentDecision orchestration from buffered InputHub events and apply the validated result.",
      parameters: Type.Object({}),
      async execute() {
        try {
          const result = await autonomousRuntime.processBufferedInputs();
          return ok(
            "Autonomous VRChat AI decision generated and applied",
            result as unknown as Record<string, unknown>,
          );
        } catch (error) {
          return fail(
            `Autonomous VRChat AI decision failed: ${error instanceof Error ? error.message : String(error)}`,
            { error: error instanceof Error ? error.message : String(error) },
          );
        }
      },
    });

    // vrchat_ai_avatar_apply_decision - Apply validated structured AgentDecision JSON
    api.registerTool({
      name: "vrchat_ai_avatar_apply_decision",
      description:
        "Validate and apply an AgentDecision to OC_* avatar parameters, VOICEVOX/audio events, and optional ChatBox output.",
      parameters: Type.Object({
        decision: Type.Any({ description: "AgentDecision JSON object" }),
      }),
      async execute(_id: string, params: { decision: unknown }) {
        const validation = validateAgentDecision(params.decision);
        if (!validation.ok || !validation.decision) {
          return fail(`Invalid AgentDecision: ${validation.errors.join("; ")}`, {
            errors: validation.errors,
          });
        }
        const result = await autonomousRuntime.applyDecision(validation.decision as AgentDecision);
        return ok(
          "Autonomous VRChat AI decision applied",
          result as unknown as Record<string, unknown>,
        );
      },
    });

    // vrchat_ai_avatar_chatbox - Autonomous ChatBox sender with opt-in config and rate limit
    api.registerTool({
      name: "vrchat_ai_avatar_chatbox",
      description:
        "Send a VRChat ChatBox message through the autonomous ChatBox guard. Disabled unless chatBox.enabled=true.",
      parameters: Type.Object({
        text: Type.String({ description: "ChatBox text. It is clamped to 144 chars and 9 lines." }),
        submit: Type.Optional(Type.Boolean({ default: true })),
        notify: Type.Optional(Type.Boolean({ default: false })),
      }),
      execute(_id: string, params: { text: string; submit?: boolean; notify?: boolean }) {
        const result = autonomousChatBox.send({
          text: params.text,
          submit: params.submit,
          notify: params.notify,
        });
        return result.success
          ? ok(
              "Autonomous VRChat ChatBox message sent",
              result as unknown as Record<string, unknown>,
            )
          : fail(
              `Autonomous VRChat ChatBox blocked: ${result.error}`,
              result as unknown as Record<string, unknown>,
            );
      },
    });

    // vrchat_ai_avatar_voicevox_request - Show the VOICEVOX requests without calling the engine
    api.registerTool({
      name: "vrchat_ai_avatar_voicevox_request",
      description:
        "Build VOICEVOX audio_query and synthesis request metadata for a reply without calling VOICEVOX.",
      parameters: Type.Object({
        text: Type.String({ description: "Text to synthesize" }),
        speaker: Type.Optional(Type.Number({ default: autonomousConfig.voicevox.speaker })),
      }),
      execute(_id: string, params: { text: string; speaker?: number }) {
        const audioQuery = voicevox.buildAudioQueryRequest({
          text: params.text,
          speaker: params.speaker,
        });
        const synthesis = voicevox.buildSynthesisRequest(
          { accent_phrases: [], speedScale: 1 },
          params.speaker ?? autonomousConfig.voicevox.speaker,
        );
        return ok("VOICEVOX request metadata built", { audioQuery, synthesis });
      },
    });

    // vrchat_send_osc - Send raw OSC message
    api.registerTool({
      name: "vrchat_send_osc",
      description: "Send a raw OSC message to VRChat",
      parameters: Type.Object({
        address: Type.String({ description: "OSC address (e.g., /avatar/parameters/Example)" }),
        args: Type.Array(Type.Union([Type.String(), Type.Number(), Type.Boolean(), Type.Null()]), {
          description: "OSC arguments",
        }),
      }),
      execute(
        _id: string,
        params: { address: string; args: (string | number | boolean | null)[] },
      ) {
        const result = sendOSCMessage({
          address: params.address,
          args: params.args,
        });

        if (result.success) {
          return ok(`OSC message sent to ${params.address}`, {
            address: params.address,
            args: params.args,
          });
        } else {
          return fail(`Failed to send OSC: ${result.error}`, { error: result.error });
        }
      },
    });

    // vrchat_input - Send input command (PRO guard required)
    api.registerTool({
      name: "vrchat_input",
      description:
        "Send input command to VRChat (Jump, Move, Look, Voice). Requires PRO permission.",
      guard: "PRO",
      parameters: Type.Object({
        action: Type.String({
          description: `Input action to perform. Valid values: ${VALID_INPUT_ACTIONS.join(", ")}`,
        }),
        value: Type.Optional(
          Type.Union([Type.Boolean(), Type.Number()], {
            description: "Action value (default: true)",
          }),
        ),
      }),
      execute(_id: string, params: { action: string; value?: boolean | number }) {
        if (!autonomousConfig.movement.enabled) {
          return fail("VRChat input controller is disabled by movement.enabled=false", {
            movement: autonomousConfig.movement,
          });
        }
        const result = sendInputCommand({
          action: params.action,
          value: params.value,
        });

        if (result.success) {
          return ok(`Input command "${params.action}" sent`, {
            action: params.action,
            value: params.value,
          });
        } else {
          return fail(`Failed to send input: ${result.error}`, { error: result.error });
        }
      },
    });

    // vrchat_manual_move - Controlled move with automatic reset (PRO guard)
    api.registerTool({
      name: "vrchat_manual_move",
      description:
        "Perform a movement action with guaranteed input reset. Supports forward/backward/left/right/jump.",
      guard: "PRO",
      parameters: Type.Object({
        direction: Type.String({
          description: "Movement direction: forward, backward, left, right, jump",
        }),
        durationMs: Type.Optional(
          Type.Number({
            description: "Movement duration in milliseconds (default: 1000)",
            default: 1000,
          }),
        ),
      }),
      async execute(_id: string, params: { direction: string; durationMs?: number }) {
        if (!autonomousConfig.movement.enabled) {
          return fail("VRChat movement is disabled by movement.enabled=false", {
            movement: autonomousConfig.movement,
          });
        }
        const allowed = ["forward", "backward", "left", "right", "jump"];
        if (!allowed.includes(params.direction)) {
          return fail(`Invalid direction. Use one of: ${allowed.join(", ")}`, {
            direction: params.direction,
          });
        }
        const result = await performMovementWithReset({
          direction: params.direction as "forward" | "backward" | "left" | "right" | "jump",
          durationMs: params.durationMs,
        });
        if (result.success) {
          return ok(`Movement completed: ${params.direction} (${params.durationMs ?? 1000}ms)`, {
            direction: params.direction,
            durationMs: params.durationMs ?? 1000,
          });
        }
        return fail(`Movement failed: ${result.error}`, { error: result.error });
      },
    });

    // vrchat_autonomy_start - Start Ghost Bridge autonomous movement/emote loop
    api.registerTool({
      name: "vrchat_autonomy_start",
      description: "Start Ghost Bridge autonomous behavior loop for movement and expressions.",
      guard: "PRO",
      parameters: Type.Object({
        intervalMs: Type.Optional(
          Type.Number({
            description: "Loop interval in milliseconds (minimum 600, default 2500)",
            default: 2500,
          }),
        ),
        enableEmotes: Type.Optional(
          Type.Boolean({
            description: "Allow autonomous emote triggers (default true)",
            default: true,
          }),
        ),
      }),
      execute(_id: string, params: { intervalMs?: number; enableEmotes?: boolean }) {
        const result = startGhostBridge({
          intervalMs: params.intervalMs,
          enableEmotes: params.enableEmotes,
        });
        return result.success
          ? ok(result.message, { ...getGhostBridgeStatus() })
          : fail(result.message);
      },
    });

    // vrchat_autonomy_stop - Stop Ghost Bridge loop
    api.registerTool({
      name: "vrchat_autonomy_stop",
      description: "Stop Ghost Bridge autonomous behavior loop.",
      parameters: Type.Object({}),
      execute() {
        const result = stopGhostBridge();
        return result.success
          ? ok(result.message, { ...getGhostBridgeStatus() })
          : fail(result.message);
      },
    });

    // vrchat_autonomy_status - Read Ghost Bridge state
    api.registerTool({
      name: "vrchat_autonomy_status",
      description: "Get Ghost Bridge autonomous behavior status.",
      parameters: Type.Object({}),
      execute() {
        const status = getGhostBridgeStatus();
        return ok(
          `Ghost Bridge Status:
- Active: ${status.active}
- Interval: ${status.intervalMs}ms
- Emotes Enabled: ${status.enableEmotes}
- Step Count: ${status.stepCount}
- Last Action: ${status.lastAction ?? "none"}
- Last Run: ${status.lastRunAt ?? "never"}`,
          status,
        );
      },
    });

    // vrchat_autonomy_react - Apply conversation emotion + follow intent.
    api.registerTool({
      name: "vrchat_autonomy_react",
      description:
        "Apply reactive emotion and optional follow movement from a conversation chunk with cooldown safety.",
      guard: "PRO",
      parameters: Type.Object({
        text: Type.String({
          description: "Conversation text used to infer emotion and follow intent",
        }),
        allowMovement: Type.Optional(
          Type.Boolean({
            description: "Allow follow movement trigger (/input/Vertical equivalent intent)",
            default: false,
          }),
        ),
      }),
      async execute(_id: string, params: { text: string; allowMovement?: boolean }) {
        const result = await applyReactiveManifest({
          text: params.text,
          allowMovement: params.allowMovement,
        });
        return ok(
          `Reactive autonomy applied: emotion=${result.emotion}, movement=${result.movementTriggered}, reason=${result.reason}`,
          result as unknown as Record<string, unknown>,
        );
      },
    });

    // vrchat_camera_set - Set camera parameter (DIRECTOR permission)
    api.registerTool({
      name: "vrchat_camera_set",
      description:
        "Set VRChat camera parameter (Zoom, Aperture, FocalDistance, etc.). Requires DIRECTOR permission.",
      guard: "DIRECTOR",
      parameters: Type.Object({
        parameter: Type.String({
          description:
            "Camera parameter name (e.g., Zoom, Aperture, FocalDistance, Exposure, FlySpeed, TurnSpeed)",
        }),
        value: Type.Union([Type.Number(), Type.Boolean()], { description: "Parameter value" }),
      }),
      execute(_id: string, params: { parameter: string; value: number | boolean }) {
        const result = setCameraParameter({
          parameter: params.parameter,
          value: params.value,
        });

        if (result.success) {
          const clampedMsg = result.clamped ? " (value was clamped to valid range)" : "";
          return ok(`Camera parameter "${params.parameter}" set to ${params.value}${clampedMsg}`, {
            parameter: params.parameter,
            value: params.value,
            clamped: result.clamped ?? false,
          });
        } else {
          return fail(`Failed to set camera: ${result.error}`, { error: result.error });
        }
      },
    });

    // vrchat_camera_greenscreen - Set GreenScreen HSL
    api.registerTool({
      name: "vrchat_camera_greenscreen",
      description: "Set GreenScreen HSL values for chroma key. Requires DIRECTOR permission.",
      guard: "DIRECTOR",
      parameters: Type.Object({
        hue: Type.Optional(Type.Number({ description: "Hue (0-360)" })),
        saturation: Type.Optional(Type.Number({ description: "Saturation (0-100)" })),
        lightness: Type.Optional(Type.Number({ description: "Lightness (0-50)" })),
      }),
      execute(_id: string, params: { hue?: number; saturation?: number; lightness?: number }) {
        const result = setGreenScreenHSL({
          hue: params.hue,
          saturation: params.saturation,
          lightness: params.lightness,
        });

        if (result.success) {
          return ok(
            `GreenScreen HSL set: H=${params.hue}, S=${params.saturation}, L=${params.lightness}`,
            {
              hue: params.hue,
              saturation: params.saturation,
              lightness: params.lightness,
            },
          );
        } else {
          return fail(`Failed to set greenscreen: ${result.error}`, { error: result.error });
        }
      },
    });

    // vrchat_camera_lookatme - Set LookAtMe composition
    api.registerTool({
      name: "vrchat_camera_lookatme",
      description: "Set LookAtMe with X/Y offsets. Requires DIRECTOR permission.",
      guard: "DIRECTOR",
      parameters: Type.Object({
        enabled: Type.Optional(Type.Boolean({ description: "Enable LookAtMe" })),
        xOffset: Type.Optional(Type.Number({ description: "X offset (-25 to 25)" })),
        yOffset: Type.Optional(Type.Number({ description: "Y offset (-25 to 25)" })),
      }),
      execute(_id: string, params: { enabled?: boolean; xOffset?: number; yOffset?: number }) {
        const result = setLookAtMeComposition({
          enabled: params.enabled,
          xOffset: params.xOffset,
          yOffset: params.yOffset,
        });

        if (result.success) {
          return ok(
            `LookAtMe composition set: enabled=${params.enabled}, X=${params.xOffset}, Y=${params.yOffset}`,
            { enabled: params.enabled, xOffset: params.xOffset, yOffset: params.yOffset },
          );
        } else {
          return fail(`Failed to set LookAtMe: ${result.error}`, { error: result.error });
        }
      },
    });

    // vrchat_camera_capture - Trigger camera capture
    api.registerTool({
      name: "vrchat_camera_capture",
      description: "Trigger VRChat camera capture. Requires DIRECTOR permission.",
      guard: "DIRECTOR",
      parameters: Type.Object({
        delayed: Type.Optional(
          Type.Boolean({ description: "Use delayed capture (uses timer)", default: false }),
        ),
      }),
      execute(_id: string, params: { delayed?: boolean }) {
        const result = captureCamera(params.delayed);

        if (result.success) {
          const mode = params.delayed ? "delayed" : "immediate";
          return ok(`Camera capture triggered (${mode})`, { delayed: Boolean(params.delayed) });
        } else {
          return fail(`Failed to capture: ${result.error}`, { error: result.error });
        }
      },
    });

    // vrchat_start_listener - Start OSC listener
    api.registerTool({
      name: "vrchat_start_listener",
      description: "Start OSC listener to receive messages from VRChat",
      parameters: Type.Object({}),
      execute() {
        const result = startOSCListener();

        if (result.success) {
          return ok(`OSC listener started on port ${result.port}`, { port: result.port });
        } else {
          return fail(`Failed to start listener: ${result.error}`, { error: result.error });
        }
      },
    });

    // vrchat_stop_listener - Stop OSC listener
    api.registerTool({
      name: "vrchat_stop_listener",
      description: "Stop OSC listener",
      parameters: Type.Object({}),
      execute() {
        const result = stopOSCListener();

        if (result.success) {
          return ok("OSC listener stopped", { success: true });
        } else {
          return fail(`Failed to stop listener: ${result.error}`, { error: result.error });
        }
      },
    });

    // vrchat_listener_status - Get listener status
    api.registerTool({
      name: "vrchat_listener_status",
      description: "Get OSC listener status and recent messages",
      parameters: Type.Object({
        messageCount: Type.Optional(
          Type.Number({ description: "Number of recent messages to show", default: 10 }),
        ),
      }),
      execute(_id: string, params: { messageCount?: number }) {
        const status = getListenerStatus();
        const messages = getRecentMessages(params.messageCount || 10);

        let messageText = "No recent messages";
        if (messages.length > 0) {
          messageText = messages.map((m) => `${m.address}: ${JSON.stringify(m.args)}`).join("\n");
        }

        return ok(
          `OSC Listener Status:
- Running: ${status.isRunning}
- Port: ${status.port}
- Messages Received: ${status.messageCount}
- Start Time: ${status.startTime || "N/A"}

Recent Messages:
${messageText}`,
          { status, messages },
        );
      },
    });

    // vrchat_audit_logs - Get audit logs
    api.registerTool({
      name: "vrchat_audit_logs",
      description: "Get recent audit logs for debugging and monitoring",
      parameters: Type.Object({
        count: Type.Optional(Type.Number({ description: "Number of recent logs", default: 20 })),
      }),
      execute(_id: string, params: { count?: number }) {
        const logs = getRecentLogs(params.count || 20);
        const summary = getAuditSummary();

        const logText = logs
          .map((log) => `[${log.timestamp}] ${log.level}: ${log.operation}`)
          .join("\n");

        return ok(
          `Audit Log Summary:
- Total Operations: ${summary.total}
- INFO: ${summary.byLevel.INFO}
- SKIP: ${summary.byLevel.SKIP}
- ERROR: ${summary.byLevel.ERROR}
- WARN: ${summary.byLevel.WARN}

Recent Logs:
${logText}`,
          { summary, logs },
        );
      },
    });

    // vrchat_reset_rate_limits - Reset rate limiters
    api.registerTool({
      name: "vrchat_reset_rate_limits",
      description: "Reset all rate limiters (for testing/debugging)",
      parameters: Type.Object({}),
      execute() {
        Object.values(rateLimiters).forEach((limiter) => limiter.reset());
        return ok("All rate limiters have been reset", { reset: true });
      },
    });

    // ─── Guardian Pulse tools ────────────────────────────────────────────────

    // vrchat_guardian_pulse_start - Start autonomous presence heartbeat
    api.registerTool({
      name: "vrchat_guardian_pulse_start",
      description:
        "Start the Guardian Pulse: autonomous periodic chatbox messages and avatar emotions in VRChat. はくあの自律存在パルスを開始します。",
      parameters: Type.Object({
        intervalMinutes: Type.Optional(
          Type.Number({
            description: "Chatbox message interval in minutes (default: 10)",
            default: 10,
          }),
        ),
        emotionIntervalMinutes: Type.Optional(
          Type.Number({
            description: "Avatar emotion interval in minutes (default: 10)",
            default: 10,
          }),
        ),
        sendEmotions: Type.Optional(
          Type.Boolean({
            description: "Also trigger avatar emotion expressions (default: true)",
            default: true,
          }),
        ),
      }),
      async execute(
        _id: string,
        params: {
          intervalMinutes?: number;
          emotionIntervalMinutes?: number;
          sendEmotions?: boolean;
        },
      ) {
        const result = startGuardianPulse({
          intervalMs: (params.intervalMinutes ?? 10) * 60 * 1000,
          emotionIntervalMs: (params.emotionIntervalMinutes ?? 10) * 60 * 1000,
          sendEmotions: params.sendEmotions ?? true,
        });
        return result.success
          ? ok(result.message, { success: true })
          : fail(result.message, { success: false });
      },
    });

    // vrchat_guardian_pulse_stop - Stop autonomous presence heartbeat
    api.registerTool({
      name: "vrchat_guardian_pulse_stop",
      description: "Stop the Guardian Pulse autonomous heartbeat.",
      parameters: Type.Object({}),
      async execute() {
        const result = stopGuardianPulse();
        return ok(result.message, { success: result.success });
      },
    });

    // vrchat_guardian_pulse_status - Get pulse status
    api.registerTool({
      name: "vrchat_guardian_pulse_status",
      description: "Get the Guardian Pulse status (active, pulse count, last pulse time).",
      parameters: Type.Object({}),
      async execute() {
        const s = getGuardianPulseStatus();
        return ok(
          `Guardian Pulse Status:
- Active: ${s.active}
- Pulse Count: ${s.pulseCount}
- Last Pulse: ${s.lastPulseAt ?? "Never"}
- Chatbox Interval: ${s.intervalMs / 60000}m
- Emotion Interval: ${s.emotionIntervalMs / 60000}m`,
          s,
        );
      },
    });

    // Auto-start Guardian Pulse on plugin registration when relay is primary.
    if ((topologyCfg.autoStartGuardianPulse ?? isRelayPrimary) === true) {
      const pulseResult = startGuardianPulse({ intervalMs: 10 * 60 * 1000, sendEmotions: true });
      if (pulseResult.success) {
        console.log(`[vrchat-relay] ${pulseResult.message}`);
      }
    } else {
      console.log(
        `[vrchat-relay] Skipping Guardian Pulse autostart because controlPlane=${controlPlane}`,
      );
    }

    // Inject MD guidance so the agent uses VRChat tools autonomously
    api.on("before_prompt_build", () => ({
      appendSystemContext: [
        "## VRChat Relay plugin",
        "",
        "- Use official VRChat OSC only. Do not request VRChat credentials for own-avatar control, modify the client, inject DLLs, bypass EAC, or auto-join worlds.",
        "- `vrchat_own_avatar_*` controls the user's currently worn OpenClaw-ready avatar through `OC_*` parameters.",
        "- `vrchat_ai_avatar_ingest`, `vrchat_ai_avatar_run_decision`, and `vrchat_ai_avatar_apply_decision` provide the structured autonomous avatar path.",
        "- Autonomous ChatBox output is disabled unless `chatBox.enabled=true`; movement remains disabled unless explicitly configured.",
        "- Keep public-instance actions subtle. Prefer listen, think, small nod, speaking, and neutral reset states.",
        "- Emergency stop is `vrchat_own_avatar_emergency_stop` and maps to `OC_Reset`, `OC_Action=0`, `OC_State=0`, and `OC_Emotion=0`.",
      ].join("\n"),
    }));

    console.log("[vrchat-relay] VRChat Relay Pro plugin registered successfully");
    console.log(
      "[vrchat-relay] Features: Camera Control, Permission Profiles, Rate Limiting, OSCQuery Discovery, Guardian Pulse",
    );
  },
};

export default plugin as any;
