/**
 * Hypura Python harness — HTTP proxy tools for the FastAPI daemon (extensions/hypura-harness/scripts/harness_daemon.py).
 * Default base URL matches harness.config.json (port 18794; avoids OpenClaw Bridge on 18790).
 */
import { stringEnum } from "openclaw/plugin-sdk/core";
import { definePluginEntry, type OpenClawPluginApi } from "openclaw/plugin-sdk/plugin-entry";
import { Type } from "typebox";

const DEFAULT_BASE_URL = "http://127.0.0.1:18794";
const COMPANION_CONTROL_ACTIONS = [
  "status",
  "speak",
  "emotion",
  "motion",
  "expression",
  "look_at",
  "load_model",
  "mic",
  "input_snapshot",
  "window_capture",
  "permission",
] as const;
const COMPANION_TTS_PROVIDERS = ["voicevox", "web-speech"] as const;
const COMPANION_PERMISSION_CAPABILITIES = ["mic", "camera", "screen", "tab-follow"] as const;
const COMPANION_PERMISSION_DECISIONS = ["granted", "denied"] as const;
const COMPANION3D_EVENT_TYPES = [
  "state",
  "emotion",
  "speak_start",
  "speak_end",
  "gesture",
  "look_at",
  "idle",
  "load_model",
] as const;

type HarnessPluginConfig = {
  baseUrl?: string;
};

function resolveBaseUrl(api: OpenClawPluginApi): string {
  const cfg = (api.pluginConfig ?? {}) as HarnessPluginConfig;
  const raw = typeof cfg.baseUrl === "string" ? cfg.baseUrl.trim() : "";
  return raw || DEFAULT_BASE_URL;
}

function okText(text: string, details: Record<string, unknown> = {}) {
  return {
    content: [{ type: "text" as const, text }],
    details,
  };
}

function addStringParam(
  body: Record<string, unknown>,
  params: Record<string, unknown>,
  key: string,
): void {
  if (typeof params[key] === "string") {
    body[key] = params[key];
  }
}

function addFiniteNumberParam(
  body: Record<string, unknown>,
  params: Record<string, unknown>,
  key: string,
): void {
  const value = params[key];
  if (typeof value === "number" && Number.isFinite(value)) {
    body[key] = value;
  }
}

function addFiniteNumberArrayParam(
  body: Record<string, unknown>,
  params: Record<string, unknown>,
  key: string,
): void {
  const value = params[key];
  if (Array.isArray(value)) {
    const values = value.filter(
      (item): item is number => typeof item === "number" && Number.isFinite(item),
    );
    if (values.length > 0) {
      body[key] = values;
    }
  }
}

function addBooleanParam(
  body: Record<string, unknown>,
  params: Record<string, unknown>,
  key: string,
): void {
  if (typeof params[key] === "boolean") {
    body[key] = params[key];
  }
}

async function harnessJson(
  api: OpenClawPluginApi,
  path: string,
  init?: RequestInit,
  timeoutMs = 120_000,
): Promise<unknown> {
  const base = resolveBaseUrl(api);
  const url = `${base.replace(/\/$/, "")}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    throw new Error(
      `Hypura harness unreachable at ${base}. Start: cd extensions/hypura-harness/scripts && uv run harness_daemon.py (Windows: scripts/launchers/Start-Hypura-Harness.ps1). (${msg})`,
    );
  }
  const text = await res.text();
  let body: unknown;
  try {
    body = text ? JSON.parse(text) : {};
  } catch {
    body = { raw: text };
  }
  if (!res.ok) {
    const errObj = body as { detail?: string };
    const detail = typeof errObj?.detail === "string" ? errObj.detail : text;
    throw new Error(`Hypura harness HTTP ${res.status}: ${detail}`);
  }
  return body;
}

export default definePluginEntry({
  id: "hypura-harness",
  name: "Hypura Harness",
  description:
    "Call the Hypura Python harness HTTP API (OSC, VOICEVOX, code run, skills, evolve, LoRA jobs).",
  register(api: OpenClawPluginApi) {
    api.registerTool({
      name: "hypura_harness_companion",
      label: "Hypura Harness Companion",
      description:
        "POST /companion/control - drive Desktop Companion speech, avatar, mic, permission, input snapshot, and window capture state through the Hypura harness bridge.",
      parameters: Type.Object({
        action: stringEnum(COMPANION_CONTROL_ACTIONS, {
          description: "Companion action to perform.",
        }),
        value: Type.Optional(
          Type.String({ description: "Text, emotion, motion, or expression value." }),
        ),
        emotion: Type.Optional(
          Type.String({ description: "Optional emotion to cue when action=speak." }),
        ),
        tts_provider: Type.Optional(
          stringEnum(COMPANION_TTS_PROVIDERS, {
            description: "Optional action=speak local TTS backend override.",
          }),
        ),
        motion_index: Type.Optional(Type.Number({ description: "Motion index (default 0)." })),
        x: Type.Optional(Type.Number({ description: "Normalized look-at x coordinate." })),
        y: Type.Optional(Type.Number({ description: "Normalized look-at y coordinate." })),
        model_path: Type.Optional(
          Type.String({ description: "Absolute or workspace-relative avatar model path." }),
        ),
        enabled: Type.Optional(
          Type.Boolean({ description: "For action=mic, enable or disable local STT capture." }),
        ),
        include_camera: Type.Optional(
          Type.Boolean({
            description: "For action=input_snapshot, include existing camera frame.",
          }),
        ),
        capture_camera: Type.Optional(
          Type.Boolean({
            description: "For action=input_snapshot, request a fresh camera capture.",
          }),
        ),
        capability: Type.Optional(
          stringEnum(COMPANION_PERMISSION_CAPABILITIES, {
            description: "For action=permission, local capture capability.",
          }),
        ),
        decision: Type.Optional(
          stringEnum(COMPANION_PERMISSION_DECISIONS, {
            description: "For action=permission, permission decision.",
          }),
        ),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const body: Record<string, unknown> = {
          action: params.action,
        };
        addStringParam(body, params, "value");
        addStringParam(body, params, "emotion");
        addStringParam(body, params, "tts_provider");
        addFiniteNumberParam(body, params, "motion_index");
        addFiniteNumberParam(body, params, "x");
        addFiniteNumberParam(body, params, "y");
        if (typeof params.model_path === "string") {
          body.model_path = params.model_path;
        }
        addBooleanParam(body, params, "enabled");
        addBooleanParam(body, params, "include_camera");
        addBooleanParam(body, params, "capture_camera");
        addStringParam(body, params, "capability");
        addStringParam(body, params, "decision");
        const data = (await harnessJson(api, "/companion/control", {
          method: "POST",
          body: JSON.stringify(body),
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_submodule",
      label: "Hypura Harness Submodule",
      description:
        "POST /submodule/run - run a registry-backed vendor submodule preset through the gateway tool surface.",
      parameters: Type.Object({
        repoId: Type.String({
          description: "Registered repo id from vendor/submodules/registry.json.",
        }),
        preset: Type.String({ description: "Registered preset name for the target repo." }),
        extraArgs: Type.Optional(
          Type.Array(
            Type.String({
              description: "Additional arguments appended after the preset template.",
            }),
          ),
        ),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const body: Record<string, unknown> = {
          repoId: typeof params.repoId === "string" ? params.repoId : "",
          preset: typeof params.preset === "string" ? params.preset : "",
        };
        if (Array.isArray(params.extraArgs)) {
          body.extraArgs = params.extraArgs.filter((value) => typeof value === "string");
        }
        const data = (await harnessJson(api, "/submodule/run", {
          method: "POST",
          body: JSON.stringify(body),
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_status",
      label: "Hypura Harness Status",
      description: "GET /status — voicevox, ollama, LoRA summary and daemon health.",
      parameters: Type.Object({}),
      async execute() {
        const data = (await harnessJson(api, "/status", undefined, 10_000)) as Record<
          string,
          unknown
        >;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_channel_readiness",
      label: "Hypura Harness Channel Readiness",
      description:
        "GET /channels/readiness - inspect redacted LINE/Telegram credential and live-roundtrip readiness without printing tokens or raw routing ids.",
      parameters: Type.Object({}),
      async execute() {
        const data = (await harnessJson(api, "/channels/readiness", undefined, 10_000)) as Record<
          string,
          unknown
        >;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_osc",
      label: "Hypura Harness OSC",
      description:
        "POST /osc — VRChat OSC: chatbox, emotion, param, move/jump/move_forward/turn_* (see Hypura harness docs).",
      parameters: Type.Object({
        action: Type.String({ description: "e.g. chatbox, emotion, param, jump, move_forward" }),
        payload: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const action = typeof params.action === "string" ? params.action : "";
        const payload =
          params.payload && typeof params.payload === "object" && params.payload !== null
            ? (params.payload as Record<string, unknown>)
            : {};
        const data = (await harnessJson(api, "/osc", {
          method: "POST",
          body: JSON.stringify({ action, payload }),
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_speak",
      label: "Hypura Harness Speak",
      description: "POST /speak — VOICEVOX speech (text or scene array).",
      parameters: Type.Object({
        text: Type.Optional(Type.String()),
        emotion: Type.Optional(Type.String()),
        speaker: Type.Optional(Type.Number()),
        scene: Type.Optional(Type.Array(Type.Unknown())),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const body: Record<string, unknown> = {};
        if (typeof params.text === "string") {
          body.text = params.text;
        }
        if (typeof params.emotion === "string") {
          body.emotion = params.emotion;
        }
        if (typeof params.speaker === "number" && Number.isFinite(params.speaker)) {
          body.speaker = params.speaker;
        }
        if (Array.isArray(params.scene)) {
          body.scene = params.scene;
        }
        const data = (await harnessJson(api, "/speak", {
          method: "POST",
          body: JSON.stringify(body),
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_voice_devices",
      label: "Hypura Harness Voice Devices",
      description:
        "GET /voice/devices - list local sounddevice input/output devices and defaults for voice I/O routing.",
      parameters: Type.Object({}),
      async execute() {
        const data = (await harnessJson(api, "/voice/devices", undefined, 10_000)) as Record<
          string,
          unknown
        >;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_voice_test_say",
      label: "Hypura Harness Voice Test Say",
      description:
        "POST /voice/test-say - synthesize VOICEVOX text and play it through selected local output device ids.",
      parameters: Type.Object({
        text: Type.Optional(Type.String({ description: "Text to synthesize." })),
        emotion: Type.Optional(Type.String({ description: "Voice emotion preset." })),
        speaker: Type.Optional(Type.Number({ description: "VOICEVOX speaker id." })),
        output_device: Type.Optional(Type.Number({ description: "Single sounddevice output id." })),
        output_devices: Type.Optional(
          Type.Array(Type.Number({ description: "Sounddevice output id." })),
        ),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const body: Record<string, unknown> = {};
        addStringParam(body, params, "text");
        addStringParam(body, params, "emotion");
        addFiniteNumberParam(body, params, "speaker");
        addFiniteNumberParam(body, params, "output_device");
        addFiniteNumberArrayParam(body, params, "output_devices");
        const data = (await harnessJson(api, "/voice/test-say", {
          method: "POST",
          body: JSON.stringify(body),
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_voice_transcribe",
      label: "Hypura Harness Voice Transcribe",
      description:
        "POST /voice/transcribe - transcribe an existing WAV file with the configured or supplied whisper.cpp runtime.",
      parameters: Type.Object({
        wav_path: Type.String({ description: "WAV file path visible to the harness daemon." }),
        whisper_exe: Type.Optional(
          Type.String({ description: "Optional whisper-cli executable path." }),
        ),
        whisper_model: Type.Optional(
          Type.String({ description: "Optional whisper.cpp model path." }),
        ),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const body: Record<string, unknown> = {
          wav_path: typeof params.wav_path === "string" ? params.wav_path : "",
        };
        addStringParam(body, params, "whisper_exe");
        addStringParam(body, params, "whisper_model");
        const data = (await harnessJson(api, "/voice/transcribe", {
          method: "POST",
          body: JSON.stringify(body),
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_voice_turn",
      label: "Hypura Harness Voice Turn",
      description:
        "POST /voice/turn - record local mic audio, transcribe it, run the OpenClaw agent command, and speak the reply.",
      parameters: Type.Object({
        record_seconds: Type.Optional(
          Type.Number({ description: "Recording duration in seconds." }),
        ),
        samplerate: Type.Optional(Type.Number({ description: "Recording sample rate." })),
        input_device: Type.Optional(Type.Number({ description: "Sounddevice input id." })),
        output_device: Type.Optional(Type.Number({ description: "Single sounddevice output id." })),
        output_devices: Type.Optional(
          Type.Array(Type.Number({ description: "Sounddevice output id." })),
        ),
        speaker: Type.Optional(Type.Number({ description: "VOICEVOX speaker id." })),
        emotion: Type.Optional(Type.String({ description: "Voice emotion preset for the reply." })),
        whisper_exe: Type.Optional(
          Type.String({ description: "Optional whisper-cli executable path." }),
        ),
        whisper_model: Type.Optional(
          Type.String({ description: "Optional whisper.cpp model path." }),
        ),
        openclaw_timeout: Type.Optional(
          Type.Number({ description: "Agent command timeout in seconds." }),
        ),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const body: Record<string, unknown> = {};
        addFiniteNumberParam(body, params, "record_seconds");
        addFiniteNumberParam(body, params, "samplerate");
        addFiniteNumberParam(body, params, "input_device");
        addFiniteNumberParam(body, params, "output_device");
        addFiniteNumberArrayParam(body, params, "output_devices");
        addFiniteNumberParam(body, params, "speaker");
        addStringParam(body, params, "emotion");
        addStringParam(body, params, "whisper_exe");
        addStringParam(body, params, "whisper_model");
        addFiniteNumberParam(body, params, "openclaw_timeout");
        const data = (await harnessJson(
          api,
          "/voice/turn",
          {
            method: "POST",
            body: JSON.stringify(body),
          },
          600_000,
        )) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_companion_voice_turn",
      label: "Hypura Harness Companion Voice Turn",
      description:
        "POST /voice/companion-turn - use a Desktop Companion transcript as an OpenClaw agent turn and optionally speak/animate the reply.",
      parameters: Type.Object({
        transcript: Type.Optional(
          Type.String({ description: "Transcript text. If omitted, read latest companion state." }),
        ),
        transcript_timestamp: Type.Optional(
          Type.Number({ description: "Transcript timestamp from companion state." }),
        ),
        last_seen_timestamp: Type.Optional(
          Type.Number({ description: "Skip transcript if timestamp is not newer." }),
        ),
        openclaw_timeout: Type.Optional(
          Type.Number({ description: "Agent command timeout in seconds." }),
        ),
        speak: Type.Optional(
          Type.Boolean({ description: "Speak the reply through the Desktop Companion." }),
        ),
        animate: Type.Optional(
          Type.Boolean({ description: "Forward inferred emotion to the Desktop Companion." }),
        ),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const body: Record<string, unknown> = {};
        addStringParam(body, params, "transcript");
        addFiniteNumberParam(body, params, "transcript_timestamp");
        addFiniteNumberParam(body, params, "last_seen_timestamp");
        addFiniteNumberParam(body, params, "openclaw_timeout");
        addBooleanParam(body, params, "speak");
        addBooleanParam(body, params, "animate");
        const data = (await harnessJson(
          api,
          "/voice/companion-turn",
          {
            method: "POST",
            body: JSON.stringify(body),
          },
          600_000,
        )) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_companion_mic",
      label: "Hypura Harness Companion Mic",
      description:
        "POST /voice/companion-mic - enable or disable Desktop Companion microphone capture through the harness bridge.",
      parameters: Type.Object({
        enabled: Type.Optional(
          Type.Boolean({ description: "Whether companion microphone capture should be enabled." }),
        ),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const body: Record<string, unknown> = {};
        addBooleanParam(body, params, "enabled");
        const data = (await harnessJson(api, "/voice/companion-mic", {
          method: "POST",
          body: JSON.stringify(body),
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_vrc_status",
      label: "Hypura Harness VRC Status",
      description:
        "GET /vrc/status - inspect VRChat OSC bridge, current avatar id, catalog/profile readiness, and emergency-stop state.",
      parameters: Type.Object({}),
      async execute() {
        const data = (await harnessJson(api, "/vrc/status", undefined, 10_000)) as Record<
          string,
          unknown
        >;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_vrc_current_avatar",
      label: "Hypura Harness VRC Current Avatar",
      description:
        "GET /vrc/avatar/current - show the current VRChat avatar id and loaded OSC parameter catalog.",
      parameters: Type.Object({}),
      async execute() {
        const data = (await harnessJson(api, "/vrc/avatar/current", undefined, 10_000)) as Record<
          string,
          unknown
        >;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_vrc_parameters",
      label: "Hypura Harness VRC Parameters",
      description:
        "GET /vrc/avatar/parameters - list writable/readable parameters discovered from the current avatar's VRChat OSC JSON.",
      parameters: Type.Object({}),
      async execute() {
        const data = (await harnessJson(
          api,
          "/vrc/avatar/parameters",
          undefined,
          10_000,
        )) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_vrc_profile",
      label: "Hypura Harness VRC Profile",
      description:
        "GET /vrc/avatar/profile - inspect approved and suggested action profiles for the current VRChat avatar.",
      parameters: Type.Object({}),
      async execute() {
        const data = (await harnessJson(api, "/vrc/avatar/profile", undefined, 10_000)) as Record<
          string,
          unknown
        >;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_vrc_suggest_profile",
      label: "Hypura Harness VRC Suggest Profile",
      description:
        "POST /vrc/avatar/profile/suggest - generate an unapproved per-avatar action profile suggestion from the OSC JSON catalog.",
      parameters: Type.Object({
        avatar_id: Type.Optional(
          Type.String({ description: "Optional avatar id; defaults to the current avatar." }),
        ),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const body: Record<string, unknown> = {};
        addStringParam(body, params, "avatar_id");
        const data = (await harnessJson(api, "/vrc/avatar/profile/suggest", {
          method: "POST",
          body: JSON.stringify(body),
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_vrc_approve_profile",
      label: "Hypura Harness VRC Approve Profile",
      description:
        "POST /vrc/avatar/profile/approve - operator-only approval for a reviewed avatar action profile. Use only after explicit user approval.",
      parameters: Type.Object({
        avatar_id: Type.Optional(
          Type.String({ description: "Optional avatar id; defaults to the current avatar." }),
        ),
        confirm: Type.String({
          description:
            'Required explicit confirmation text containing "approve" or "承認"; agents must not invent this.',
        }),
        notes: Type.Optional(Type.String({ description: "Optional operator approval notes." })),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const body: Record<string, unknown> = {
          confirm: typeof params.confirm === "string" ? params.confirm : "",
        };
        addStringParam(body, params, "avatar_id");
        addStringParam(body, params, "notes");
        const data = (await harnessJson(api, "/vrc/avatar/profile/approve", {
          method: "POST",
          body: JSON.stringify(body),
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_vrc_action",
      label: "Hypura Harness VRC Action",
      description:
        "POST /vrc/action - send only approved profile actions to the current VRChat avatar through the safety gate.",
      parameters: Type.Object({
        action: Type.String({ description: "Approved action name from the avatar profile." }),
        reason: Type.Optional(Type.String({ description: "Short reason for audit/debug output." })),
        intensity: Type.Optional(Type.Number({ description: "Optional action intensity hint." })),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const body: Record<string, unknown> = {
          action: typeof params.action === "string" ? params.action : "",
        };
        addStringParam(body, params, "reason");
        addFiniteNumberParam(body, params, "intensity");
        const data = (await harnessJson(api, "/vrc/action", {
          method: "POST",
          body: JSON.stringify(body),
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_vrc_chatbox",
      label: "Hypura Harness VRC ChatBox",
      description:
        "POST /vrc/chatbox - send a rate-limited VRChat ChatBox message only when ChatBox is explicitly enabled.",
      parameters: Type.Object({
        text: Type.String({ description: "ChatBox text; daemon truncates to configured limits." }),
        send_immediately: Type.Optional(Type.Boolean()),
        notify: Type.Optional(Type.Boolean()),
        public_instance: Type.Optional(
          Type.Boolean({ description: "Set true when operating in a Public instance." }),
        ),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const body: Record<string, unknown> = {
          text: typeof params.text === "string" ? params.text : "",
        };
        addBooleanParam(body, params, "send_immediately");
        addBooleanParam(body, params, "notify");
        addBooleanParam(body, params, "public_instance");
        const data = (await harnessJson(api, "/vrc/chatbox", {
          method: "POST",
          body: JSON.stringify(body),
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_vrc_emergency_stop",
      label: "Hypura Harness VRC Emergency Stop",
      description:
        "POST /vrc/emergency-stop - cancel VRChat movement/typing and block further avatar actions until safety is reset.",
      parameters: Type.Object({}),
      async execute() {
        const data = (await harnessJson(api, "/vrc/emergency-stop", {
          method: "POST",
          body: "{}",
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_companion3d_status",
      label: "Hypura Harness Companion3D Status",
      description:
        "GET /companion3d/status - inspect browser/Electron 3D companion policy, events, and last state.",
      parameters: Type.Object({}),
      async execute() {
        const data = (await harnessJson(api, "/companion3d/status", undefined, 10_000)) as Record<
          string,
          unknown
        >;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_companion3d_load_model",
      label: "Hypura Harness Companion3D Load Model",
      description:
        "POST /companion3d/load-model - load a user-approved local VRM/GLB/GLTF/FBX asset from the configured companion3d assetRoot.",
      parameters: Type.Object({
        model_path: Type.String({
          description:
            "Local model path under state/companion3d/assets; remote URLs and traversal are rejected.",
        }),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const data = (await harnessJson(api, "/companion3d/load-model", {
          method: "POST",
          body: JSON.stringify({
            model_path: typeof params.model_path === "string" ? params.model_path : "",
          }),
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_companion3d_event",
      label: "Hypura Harness Companion3D Event",
      description:
        "POST /companion3d/event - send a structured emotion/speech/gesture/look/idle event to the local 3D companion event bus.",
      parameters: Type.Object({
        type: stringEnum(COMPANION3D_EVENT_TYPES, {
          description: "Companion3D event type.",
        }),
        payload: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const payload =
          params.payload && typeof params.payload === "object" && params.payload !== null
            ? (params.payload as Record<string, unknown>)
            : {};
        const data = (await harnessJson(api, "/companion3d/event", {
          method: "POST",
          body: JSON.stringify({ type: params.type, payload }),
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_companion3d_set_state",
      label: "Hypura Harness Companion3D Set State",
      description:
        "POST /companion3d/state - record companion state such as AI emotion, speaking, idle, or VRChat sync fallback.",
      parameters: Type.Object({
        state: Type.Record(Type.String(), Type.Unknown()),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const state =
          params.state && typeof params.state === "object" && params.state !== null
            ? (params.state as Record<string, unknown>)
            : {};
        const data = (await harnessJson(api, "/companion3d/state", {
          method: "POST",
          body: JSON.stringify({ state }),
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_run",
      label: "Hypura Harness Run",
      description:
        "POST /run — generate and execute Python via harness code_runner (PEP 723 + uv).",
      parameters: Type.Object({
        task: Type.String({ description: "Natural language task for code generation." }),
        model: Type.Optional(Type.String()),
        max_retries: Type.Optional(Type.Number()),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const task = typeof params.task === "string" ? params.task : "";
        const body: Record<string, unknown> = { task };
        if (typeof params.model === "string") {
          body.model = params.model;
        }
        if (typeof params.max_retries === "number" && Number.isFinite(params.max_retries)) {
          body.max_retries = params.max_retries;
        }
        const data = (await harnessJson(api, "/run", {
          method: "POST",
          body: JSON.stringify(body),
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_skill",
      label: "Hypura Harness Skill",
      description: "POST /skill — generate a new workspace skill (SKILL.md) via harness.",
      parameters: Type.Object({
        name: Type.String(),
        description: Type.String(),
        examples: Type.Optional(Type.Array(Type.String())),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const body = {
          name: typeof params.name === "string" ? params.name : "",
          description: typeof params.description === "string" ? params.description : "",
          examples: Array.isArray(params.examples)
            ? params.examples.filter((x) => typeof x === "string")
            : [],
        };
        const data = (await harnessJson(api, "/skill", {
          method: "POST",
          body: JSON.stringify(body),
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_evolve",
      label: "Hypura Harness Evolve",
      description: "POST /evolve — ShinkaEvolve loop for code or skill targets.",
      parameters: Type.Object({
        target: stringEnum(["code", "skill"] as const, { description: "Evolution target" }),
        seed: Type.String({ description: "Starting code or skill text." }),
        fitness_hint: Type.Optional(Type.String()),
        generations: Type.Optional(Type.Number()),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const body: Record<string, unknown> = {
          target: params.target,
          seed: typeof params.seed === "string" ? params.seed : "",
        };
        if (typeof params.fitness_hint === "string") {
          body.fitness_hint = params.fitness_hint;
        }
        if (typeof params.generations === "number" && Number.isFinite(params.generations)) {
          body.generations = params.generations;
        }
        const data = (await harnessJson(api, "/evolve", {
          method: "POST",
          body: JSON.stringify(body),
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_lora_status",
      label: "Hypura Harness LoRA Status",
      description: "GET /lora/status — LoRA paths and environment resolution summary.",
      parameters: Type.Object({}),
      async execute() {
        const data = (await harnessJson(api, "/lora/status", undefined, 15_000)) as Record<
          string,
          unknown
        >;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_lora_curriculum_build",
      label: "Hypura Harness LoRA Curriculum Build",
      description: "POST /lora/curriculum/build — enqueue curriculum JSONL build job.",
      parameters: Type.Object({
        arxiv_ids: Type.Optional(Type.Array(Type.String())),
        include_soul: Type.Optional(Type.Boolean()),
        extra_jsonl: Type.Optional(Type.Array(Type.String())),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const body: Record<string, unknown> = {};
        if (Array.isArray(params.arxiv_ids)) {
          body.arxiv_ids = params.arxiv_ids.filter((x) => typeof x === "string");
        }
        if (typeof params.include_soul === "boolean") {
          body.include_soul = params.include_soul;
        }
        if (Array.isArray(params.extra_jsonl)) {
          body.extra_jsonl = params.extra_jsonl.filter((x) => typeof x === "string");
        }
        const data = (await harnessJson(api, "/lora/curriculum/build", {
          method: "POST",
          body: JSON.stringify(body),
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_lora_train",
      label: "Hypura Harness LoRA Train",
      description: "POST /lora/train — enqueue LoRA SFT train job (dry_run recommended first).",
      parameters: Type.Object({
        dry_run: Type.Optional(Type.Boolean()),
        dataset_path: Type.Optional(Type.String()),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const body: Record<string, unknown> = {};
        if (typeof params.dry_run === "boolean") {
          body.dry_run = params.dry_run;
        }
        if (typeof params.dataset_path === "string") {
          body.dataset_path = params.dataset_path;
        }
        const data = (await harnessJson(api, "/lora/train", {
          method: "POST",
          body: JSON.stringify(body),
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_lora_grpo",
      label: "Hypura Harness LoRA GRPO",
      description: "POST /lora/grpo — GRPO placeholder or train job (mode placeholder|train).",
      parameters: Type.Object({
        mode: Type.Optional(
          stringEnum(["placeholder", "train"] as const, { description: "GRPO mode" }),
        ),
        dataset_path: Type.Optional(Type.String()),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const body: Record<string, unknown> = {};
        if (params.mode === "placeholder" || params.mode === "train") {
          body.mode = params.mode;
        }
        if (typeof params.dataset_path === "string") {
          body.dataset_path = params.dataset_path;
        }
        const data = (await harnessJson(api, "/lora/grpo", {
          method: "POST",
          body: JSON.stringify(body),
        })) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_harness_lora_job",
      label: "Hypura Harness LoRA Job",
      description: "GET /lora/jobs/{job_id} — poll async LoRA job status.",
      parameters: Type.Object({
        job_id: Type.String(),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const jobId = typeof params.job_id === "string" ? encodeURIComponent(params.job_id) : "";
        const data = (await harnessJson(api, `/lora/jobs/${jobId}`, undefined, 15_000)) as Record<
          string,
          unknown
        >;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    // ── 継続改善ループ ────────────────────────────────────────────────────────

    api.registerTool({
      name: "hypura_loop_status",
      label: "Hypura Loop Status",
      description:
        "GET /status — Redis ループ状態を確認する。training:examples / atlas:failures / TinyLoRA adapter 状況を返す。",
      parameters: Type.Object({}),
      async execute() {
        const data = (await harnessJson(api, "/status", undefined, 10_000)) as Record<
          string,
          unknown
        >;
        const loop = (data.loop ?? {}) as Record<string, unknown>;
        const summary = [
          `Redis: ${loop.redis ?? "unknown"}`,
          `training:examples = ${loop.training_examples ?? "?"}`,
          `atlas:failures = ${loop.failures ?? "?"}`,
          `shinka:fitness_hints = ${loop.fitness_hints ?? "?"}`,
          `TinyLoRA adapter ready: ${loop.tinylora_adapter_ready ?? false}`,
          `Training in progress: ${loop.training_in_progress ?? false}`,
          loop.last_trained ? `Last trained: ${loop.last_trained}` : "Never trained",
        ].join("\n");
        return okText(summary, { loop });
      },
    });

    api.registerTool({
      name: "hypura_tinylora_train",
      label: "Hypura TinyLoRA Train",
      description:
        "POST /lora/train — TinyLoRA (arXiv:2602.04118) で qwen-hakua-core2 を学習する。" +
        "13 パラメータで秒〜分単位の高速学習。mode=tinylora|sft|auto を選択できる。",
      parameters: Type.Object({
        mode: Type.Optional(stringEnum(["auto", "tinylora", "sft"] as const, { default: "auto" })),
        dry_run: Type.Optional(Type.Boolean()),
        dataset_path: Type.Optional(Type.String()),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const body: Record<string, unknown> = {
          mode: params.mode ?? "auto",
          dry_run: params.dry_run ?? true,
        };
        if (typeof params.dataset_path === "string") {
          body.dataset_path = params.dataset_path;
        }
        const data = (await harnessJson(
          api,
          "/lora/train",
          {
            method: "POST",
            body: JSON.stringify(body),
          },
          600_000,
        )) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    // ── AI Scientist ──────────────────────────────────────────────────────

    api.registerTool({
      name: "hypura_scientist_run",
      label: "Hypura AI Scientist Run",
      description:
        "POST /scientist/run — AI-Scientist (SakanaAI, Ollama モード) でリサーチアイデアを生成して Redis に保存する。" +
        "topic が空なら atlas:failures から自動設定。run_experiment=true で実験実行まで行う。",
      parameters: Type.Object({
        topic: Type.Optional(
          Type.String({ description: "研究テーマ (空=atlas:failuresから自動設定)" }),
        ),
        num_ideas: Type.Optional(Type.Number({ default: 3, description: "生成するアイデア数" })),
        run_experiment: Type.Optional(
          Type.Boolean({ default: false, description: "実験実行も行う" }),
        ),
        model: Type.Optional(Type.String({ default: "ollama/qwen-Hakua-core2" })),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const body: Record<string, unknown> = {
          topic: params.topic ?? "",
          num_ideas: params.num_ideas ?? 3,
          run_experiment: params.run_experiment ?? false,
          model: params.model ?? "ollama/qwen-Hakua-core2",
        };
        const data = (await harnessJson(
          api,
          "/scientist/run",
          {
            method: "POST",
            body: JSON.stringify(body),
          },
          300_000,
        )) as Record<string, unknown>;
        return okText(JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_scientist_ideas",
      label: "Hypura AI Scientist Ideas",
      description:
        "POST /scientist/ideas — AI-Scientist でアイデア一覧のみ生成して返す (Redis 保存なし)。" +
        "Ollama の qwen-Hakua-core2 を使用。",
      parameters: Type.Object({
        topic: Type.Optional(Type.String({ description: "研究テーマ" })),
        num_ideas: Type.Optional(Type.Number({ default: 3 })),
        model: Type.Optional(Type.String({ default: "ollama/qwen-Hakua-core2" })),
      }),
      async execute(_id: string, params: Record<string, unknown>) {
        const body: Record<string, unknown> = {
          topic: params.topic ?? "",
          num_ideas: params.num_ideas ?? 3,
          model: params.model ?? "ollama/qwen-Hakua-core2",
        };
        const data = (await harnessJson(
          api,
          "/scientist/ideas",
          {
            method: "POST",
            body: JSON.stringify(body),
          },
          120_000,
        )) as Record<string, unknown>;
        const ideas = (data.ideas as unknown[]) ?? [];
        const summary = ideas
          .map((idea: unknown, i: number) => {
            const obj = idea as Record<string, unknown>;
            return `[${i + 1}] ${obj.Name ?? obj.Title ?? "idea"}: ${obj.fitness_hint ?? ""}`;
          })
          .join("\n");
        return okText(summary || JSON.stringify(data, null, 2), data);
      },
    });

    api.registerTool({
      name: "hypura_scientist_status",
      label: "Hypura AI Scientist Status",
      description:
        "GET /scientist/status — ai_scientist:findings / ai_scientist:tasks のキュー状態を確認する。",
      parameters: Type.Object({}),
      async execute() {
        const data = (await harnessJson(api, "/scientist/status", undefined, 10_000)) as Record<
          string,
          unknown
        >;
        const summary = [
          `Findings stored: ${data.findings ?? "?"}`,
          `Tasks queued:    ${data.tasks ?? "?"}`,
          `Redis:           ${data.redis ?? "unknown"}`,
        ].join("\n");
        return okText(summary, data);
      },
    });

    api.on("before_prompt_build", () => ({
      appendSystemContext: [
        "## Hypura Python harness (hypura-harness plugin)",
        "",
        "- Prefer **`hypura_harness_status`** before other harness tools.",
        "- Channel readiness: use **`hypura_harness_channel_readiness`** to separate LINE/Telegram credential readiness from live roundtrip readiness without printing tokens or raw routing ids.",
        "- VRChat / VOICEVOX legacy tools: **`hypura_harness_osc`**, **`hypura_harness_speak`**.",
        "- VRChat existing avatar tools: call **`hypura_harness_vrc_status`** first, inspect **`hypura_harness_vrc_current_avatar`** and **`hypura_harness_vrc_profile`**, generate only unapproved suggestions with **`hypura_harness_vrc_suggest_profile`**, and send avatar changes only through **`hypura_harness_vrc_action`** after an approved profile exists.",
        "- Do not approve VRChat avatar profiles unless the user explicitly provides approval; if no approved action is available, use **`hypura_harness_companion3d_event`** or **`hypura_harness_companion3d_set_state`** instead of writing VRChat parameters.",
        "- VRChat ChatBox stays disabled by default; use **`hypura_harness_vrc_chatbox`** only after status/config show it is enabled, and use **`hypura_harness_vrc_emergency_stop`** immediately if avatar behavior is surprising.",
        "- Voice I/O: use **`hypura_harness_voice_devices`** first, **`hypura_harness_voice_test_say`** for output routing, **`hypura_harness_voice_transcribe`** for WAV input, and **`hypura_harness_voice_turn`** for mic -> OpenClaw -> VOICEVOX turns.",
        "- Desktop Companion voice: **`hypura_harness_companion`** mirrors `control_companion` for status/speech/avatar/mic/permissions/snapshots/window captures; **`hypura_harness_companion_mic`** toggles mic capture and **`hypura_harness_companion_voice_turn`** handles transcript -> OpenClaw -> companion speech/animation.",
        "- Desktop Companion 3D: **`hypura_harness_companion3d_status`**, **`hypura_harness_companion3d_load_model`**, **`hypura_harness_companion3d_event`**, and **`hypura_harness_companion3d_set_state`** only use local approved assets under the configured asset root.",
        "- Sanctioned external repos: **`hypura_harness_submodule`** for registry-backed vendor submodule presets.",
        "- Code execution: **`hypura_harness_run`** (→ 成功時に training:examples へ保存、失敗時に ShinkaEvolve → atlas:failures へ記録).",
        "- Skills / evolution / LoRA: **`hypura_harness_skill`**, **`hypura_harness_evolve`**, `hypura_harness_lora_*`.",
        "- Loop monitoring: **`hypura_loop_status`** で training:examples / failures / TinyLoRA adapter 状況を確認.",
        "- TinyLoRA training: **`hypura_tinylora_train`** (qwen-hakua-core2 を 13 params で学習; mode=auto/tinylora/sft).",
        "- AI Scientist: **`hypura_scientist_run`** (SakanaAI/AI-Scientist, Ollama モード; アイデア生成→Redis保存), **`hypura_scientist_ideas`** (アイデアのみ取得), **`hypura_scientist_status`** (findings/tasks キュー確認).",
        `- Default URL: ${DEFAULT_BASE_URL} (override via plugins.entries["hypura-harness"].config.baseUrl).`,
        "- If tools fail to connect: `cd extensions/hypura-harness/scripts && uv run harness_daemon.py` (or `scripts/launchers/Start-Hypura-Harness.ps1` on Windows).",
      ].join("\n"),
    }));
  },
});
