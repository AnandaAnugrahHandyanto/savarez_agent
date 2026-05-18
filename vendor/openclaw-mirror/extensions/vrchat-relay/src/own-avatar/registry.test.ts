import { promises as fs } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { DEFAULT_OWN_AVATAR_REQUIRED_PARAMS } from "./config.js";
import { parseAvatarOscConfig, VRChatAvatarRegistry } from "./registry.js";

const cleanupPaths: string[] = [];

async function makeOscRoot(): Promise<string> {
  const root = await fs.mkdtemp(join(tmpdir(), "openclaw-vrchat-osc-"));
  cleanupPaths.push(root);
  return root;
}

function buildConfig(parameterNames: readonly string[]): string {
  return JSON.stringify(
    {
      id: "avtr_test",
      name: "OpenClaw Test Avatar",
      parameters: parameterNames.map((name) => ({
        name,
        input: {
          address: `/avatar/parameters/${name}`,
          type:
            name.endsWith("Enabled") ||
            name.endsWith("Pulse") ||
            name.endsWith("Reset") ||
            name.endsWith("Lock")
              ? "Bool"
              : "Int",
        },
        output: {
          address: `/avatar/parameters/${name}`,
          type:
            name.endsWith("Enabled") ||
            name.endsWith("Pulse") ||
            name.endsWith("Reset") ||
            name.endsWith("Lock")
              ? "Bool"
              : "Int",
        },
      })),
    },
    null,
    2,
  );
}

afterEach(async () => {
  await Promise.all(
    cleanupPaths.splice(0).map((path) => fs.rm(path, { recursive: true, force: true })),
  );
});

describe("VRChatAvatarRegistry", () => {
  it("parses VRChat OSC JSON input endpoints as writable parameters", () => {
    const parsed = parseAvatarOscConfig(buildConfig(DEFAULT_OWN_AVATAR_REQUIRED_PARAMS));

    expect(parsed.supported).toBe(true);
    expect(parsed.parameters).toContainEqual(
      expect.objectContaining({
        name: "OC_State",
        inputAddress: "/avatar/parameters/OC_State",
        writable: true,
      }),
    );
  });

  it("discovers the current avatar config below the VRChat OSC root", async () => {
    const root = await makeOscRoot();
    const avatarDir = join(root, "usr_00000000-0000-0000-0000-000000000000", "Avatars");
    await fs.mkdir(avatarDir, { recursive: true });
    await fs.writeFile(
      join(avatarDir, "avtr_ready.json"),
      buildConfig(DEFAULT_OWN_AVATAR_REQUIRED_PARAMS),
      "utf8",
    );

    const registry = new VRChatAvatarRegistry({ oscJsonRoot: root });
    const snapshot = await registry.loadAvatar("avtr_ready");

    expect(snapshot.supported).toBe(true);
    expect(snapshot.avatarId).toBe("avtr_ready");
    expect(registry.hasWritableParameter("OC_ActionPulse")).toBe(true);
  });

  it("reports unsupported avatars when required OC parameters are missing", async () => {
    const registry = new VRChatAvatarRegistry({ oscJsonRoot: await makeOscRoot() });
    const snapshot = await registry.loadAvatar("avtr_missing");

    expect(snapshot.supported).toBe(false);
    expect(snapshot.missingRequiredParameters).toContain("OC_State");
    expect(registry.hasWritableParameter("OC_State")).toBe(false);
  });
});
