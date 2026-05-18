import { promises as fs } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { DEFAULT_OWN_AVATAR_REQUIRED_PARAMS } from "./config.js";

export type OwnAvatarParameterType = "bool" | "int" | "float";

export interface VRChatAvatarParameterDefinition {
  name: string;
  type: OwnAvatarParameterType;
  inputAddress?: string;
  outputAddress?: string;
  writable: boolean;
}

export interface VRChatAvatarRegistrySnapshot {
  avatarId: string;
  avatarName?: string;
  sourcePath?: string;
  parameters: VRChatAvatarParameterDefinition[];
  supported: boolean;
  missingRequiredParameters: string[];
}

export interface VRChatAvatarRegistryOptions {
  oscJsonRoot?: string;
  requiredParameters?: readonly string[];
}

interface RawOscParameterEndpoint {
  address?: unknown;
  type?: unknown;
}

interface RawOscParameter {
  name?: unknown;
  type?: unknown;
  input?: unknown;
  output?: unknown;
}

interface RawOscAvatarConfig {
  id?: unknown;
  name?: unknown;
  parameters?: unknown;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeParameterType(value: unknown): OwnAvatarParameterType | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim().toLowerCase();
  if (normalized === "bool" || normalized === "boolean") {
    return "bool";
  }
  if (normalized === "int" || normalized === "integer") {
    return "int";
  }
  if (normalized === "float" || normalized === "number") {
    return "float";
  }
  return null;
}

function readEndpoint(value: unknown): RawOscParameterEndpoint | null {
  return isRecord(value) ? value : null;
}

function readAddress(value: unknown): string | undefined {
  return typeof value === "string" && value.startsWith("/") ? value : undefined;
}

export function parseAvatarOscConfig(
  content: string,
  sourcePath?: string,
): VRChatAvatarRegistrySnapshot {
  const raw = JSON.parse(content) as RawOscAvatarConfig;
  const avatarId = typeof raw.id === "string" && raw.id.trim() ? raw.id.trim() : "unknown";
  const avatarName = typeof raw.name === "string" && raw.name.trim() ? raw.name.trim() : undefined;
  const rawParameters = Array.isArray(raw.parameters) ? raw.parameters : [];
  const parameters: VRChatAvatarParameterDefinition[] = [];

  for (const entry of rawParameters) {
    if (!isRecord(entry)) {
      continue;
    }
    const rawParam = entry as RawOscParameter;
    const name =
      typeof rawParam.name === "string" && rawParam.name.trim() ? rawParam.name.trim() : "";
    if (!name) {
      continue;
    }
    const input = readEndpoint(rawParam.input);
    const output = readEndpoint(rawParam.output);
    const type =
      normalizeParameterType(rawParam.type) ??
      normalizeParameterType(input?.type) ??
      normalizeParameterType(output?.type);
    if (!type) {
      continue;
    }
    const inputAddress = readAddress(input?.address);
    const outputAddress = readAddress(output?.address);
    parameters.push({
      name,
      type,
      inputAddress,
      outputAddress,
      writable: Boolean(inputAddress),
    });
  }

  const requiredParameters = [...DEFAULT_OWN_AVATAR_REQUIRED_PARAMS];
  const missingRequiredParameters = requiredParameters.filter(
    (param) => !parameters.some((candidate) => candidate.name === param && candidate.writable),
  );

  return {
    avatarId,
    avatarName,
    sourcePath,
    parameters,
    supported: missingRequiredParameters.length === 0,
    missingRequiredParameters,
  };
}

export function getDefaultOscJsonRoot(): string {
  return join(homedir(), "AppData", "LocalLow", "VRChat", "VRChat", "OSC");
}

async function listUserDirectories(oscJsonRoot: string): Promise<string[]> {
  try {
    const entries = await fs.readdir(oscJsonRoot, { withFileTypes: true });
    return entries
      .filter((entry) => entry.isDirectory() && entry.name.startsWith("usr_"))
      .map((entry) => join(oscJsonRoot, entry.name))
      .toSorted((left, right) => left.localeCompare(right));
  } catch {
    return [];
  }
}

export class VRChatAvatarRegistry {
  private readonly oscJsonRoot: string;
  private readonly requiredParameters: readonly string[];
  private current: VRChatAvatarRegistrySnapshot | null = null;

  constructor(options: VRChatAvatarRegistryOptions = {}) {
    this.oscJsonRoot = options.oscJsonRoot ?? getDefaultOscJsonRoot();
    this.requiredParameters = options.requiredParameters ?? DEFAULT_OWN_AVATAR_REQUIRED_PARAMS;
  }

  getCurrent(): VRChatAvatarRegistrySnapshot | null {
    return this.current;
  }

  hasWritableParameter(name: string): boolean {
    return (
      this.current?.parameters.some((parameter) => parameter.name === name && parameter.writable) ??
      false
    );
  }

  async loadAvatar(avatarId: string): Promise<VRChatAvatarRegistrySnapshot> {
    const sourcePath = await this.findAvatarConfigPath(avatarId);
    if (!sourcePath) {
      const snapshot = this.emptySnapshot(avatarId);
      this.current = snapshot;
      return snapshot;
    }

    const content = await fs.readFile(sourcePath, "utf8");
    const parsed = parseAvatarOscConfig(content, sourcePath);
    const snapshot: VRChatAvatarRegistrySnapshot = {
      ...parsed,
      avatarId,
      missingRequiredParameters: this.requiredParameters.filter(
        (param) =>
          !parsed.parameters.some((candidate) => candidate.name === param && candidate.writable),
      ),
    };
    snapshot.supported = snapshot.missingRequiredParameters.length === 0;
    this.current = snapshot;
    return snapshot;
  }

  private emptySnapshot(avatarId: string): VRChatAvatarRegistrySnapshot {
    return {
      avatarId,
      parameters: [],
      supported: false,
      missingRequiredParameters: [...this.requiredParameters],
    };
  }

  private async findAvatarConfigPath(avatarId: string): Promise<string | null> {
    const userDirs = await listUserDirectories(this.oscJsonRoot);
    for (const userDir of userDirs) {
      const avatarPath = join(userDir, "Avatars", `${avatarId}.json`);
      try {
        const stat = await fs.stat(avatarPath);
        if (stat.isFile()) {
          return avatarPath;
        }
      } catch {
        continue;
      }
    }
    return null;
  }
}
