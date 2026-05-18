import path from "node:path";
import process from "node:process";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../../..");

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", reject);
  });
}

async function loadCompanionSdk() {
  try {
    return await import("openclaw/plugin-sdk/live2d-companion");
  } catch {
    return await import(
      pathToFileURL(path.join(repoRoot, "extensions/live2d-companion/runtime-api.js")).href
    );
  }
}

function resolveStateDir(rawStateDir) {
  const stateDir =
    typeof rawStateDir === "string" && rawStateDir.trim() ? rawStateDir : ".openclaw-desktop";
  return path.resolve(repoRoot, stateDir);
}

async function main() {
  const sdk = await loadCompanionSdk();
  const raw = await readStdin();
  const request = raw ? JSON.parse(raw) : {};
  const stateDir = resolveStateDir(request.stateDir);

  const avatarCommand =
    request.avatarCommand && typeof request.avatarCommand === "object"
      ? request.avatarCommand
      : null;

  if (avatarCommand) {
    await sdk.setCompanionAvatarCommand({
      stateDir,
      avatarCommand,
    });
  }

  let permissionState = null;
  if (request.permission && typeof request.permission === "object") {
    permissionState = await sdk.setCompanionPermission({
      stateDir,
      capability: request.permission.capability,
      decision: request.permission.decision,
    });
  }

  let micResult = null;
  if (typeof request.micEnabled === "boolean") {
    micResult = await sdk.setCompanionMicEnabled({
      stateDir,
      enabled: request.micEnabled,
    });
  }

  let speechState = null;
  if (typeof request.text === "string" && request.text.trim()) {
    const emotion =
      typeof request.emotion === "string" && request.emotion.trim()
        ? request.emotion.trim()
        : typeof avatarCommand?.expression === "string" && avatarCommand.expression.trim()
          ? avatarCommand.expression.trim()
          : "";
    speechState = await sdk.speakWithCompanion({
      stateDir,
      text: request.text.trim(),
      ...(emotion ? { emotion } : {}),
      ...(typeof request.ttsProvider === "string" ? { ttsProvider: request.ttsProvider } : {}),
    });
  }

  const inputSnapshot =
    request.inputSnapshot && typeof request.inputSnapshot === "object"
      ? await sdk.getCompanionInputSnapshot({
          stateDir,
          payload: {
            includeCamera: request.inputSnapshot.includeCamera === true,
            captureCamera: request.inputSnapshot.captureCamera === true,
          },
        })
      : null;

  const windowCapture =
    request.windowCapture === true ? await sdk.requestCompanionWindowCapture({ stateDir }) : null;

  const state = request.getState === true ? await sdk.getCompanionState({ stateDir }) : null;

  process.stdout.write(
    JSON.stringify({
      ok: true,
      stateDir,
      permissionState,
      micResult,
      speechState,
      inputSnapshot,
      windowCapture,
      state,
    }),
  );
}

void main().catch((error) => {
  process.stderr.write(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
