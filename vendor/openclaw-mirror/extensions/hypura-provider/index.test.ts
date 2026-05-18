import { readFile, stat } from "node:fs/promises";
import type { ProviderDiscoveryContext } from "openclaw/plugin-sdk/core";
import { createTestPluginApi } from "openclaw/plugin-sdk/plugin-test-api";
import { afterEach, describe, expect, it, vi } from "vitest";
import plugin, { resolveHypuraOllamaApiBase } from "./index.js";

type RegisteredProvider = {
  catalog?: {
    run: (ctx: ProviderDiscoveryContext) => Promise<unknown>;
  };
};

function registerHypuraProvider(): RegisteredProvider {
  const registerProvider = vi.fn();
  plugin.register(
    createTestPluginApi({
      id: "hypura",
      name: "Hypura Provider",
      source: "test",
      config: {},
      pluginConfig: {},
      runtime: {} as never,
      registerProvider,
    }),
  );
  const provider = registerProvider.mock.calls[0]?.[0] as RegisteredProvider | undefined;
  if (!provider) {
    throw new Error("hypura provider registration missing");
  }
  return provider;
}

describe("hypura provider", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("declares a resolvable OpenClaw extension entrypoint", async () => {
    const packageUrl = new URL("./package.json", import.meta.url);
    const manifest = JSON.parse(await readFile(packageUrl, "utf8")) as {
      openclaw?: {
        extensions?: unknown;
      };
    };
    const extensions = manifest.openclaw?.extensions;

    expect(extensions).toEqual(["./index.ts"]);

    const [extensionPath] = extensions as [string];
    const stats = await stat(new URL(extensionPath, packageUrl));
    expect(stats.isFile()).toBe(true);
  });

  it("normalizes Ollama-compatible base URLs locally", () => {
    expect(resolveHypuraOllamaApiBase()).toBe("http://127.0.0.1:8080");
    expect(resolveHypuraOllamaApiBase("http://127.0.0.1:8080/v1/")).toBe("http://127.0.0.1:8080");
  });

  it("uses the normalized explicit model config without probing the server", async () => {
    const provider = registerHypuraProvider();
    const fetchStub = vi.fn();
    vi.stubGlobal("fetch", fetchStub);

    const result = await provider.catalog?.run({
      config: {
        models: {
          providers: {
            hypura: {
              id: "hypura",
              baseUrl: "http://127.0.0.1:8080/v1/",
              models: [{ id: "local-model" }],
            },
          },
        },
      },
      resolveProviderApiKey: () => ({ apiKey: "test-key", source: "test" }),
    } as ProviderDiscoveryContext);

    expect(result).toEqual({
      provider: {
        id: "hypura",
        baseUrl: "http://127.0.0.1:8080",
        models: [{ id: "local-model" }],
        api: "ollama",
        apiKey: "test-key",
      },
    });
    expect(fetchStub).not.toHaveBeenCalled();
  });
});
