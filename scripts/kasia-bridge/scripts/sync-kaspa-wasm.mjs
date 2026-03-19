import AdmZip from "adm-zip";
import { createHash } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SDK_VERSION = "1.1.0-rc.2";
const SDK_ARCHIVE_URL =
  "https://github.com/kaspanet/rusty-kaspa/releases/download/v1.1.0-rc.2/kaspa-wasm32-sdk-v1.1.0-rc.2.zip";
const SDK_ARCHIVE_SHA256 =
  "7343891dcfe0168404c1882240f0553381d35fad9568e22885f4b0bc546c9c53";
const SDK_ARCHIVE_PREFIX = "kaspa-wasm32-sdk/nodejs/kaspa/";

const bridgeDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const vendorDir = resolve(bridgeDir, "vendor");
const packageDir = resolve(vendorDir, "kaspa-wasm");
const packageJsonPath = resolve(packageDir, "package.json");
const requiredFiles = ["package.json", "kaspa.js", "kaspa.d.ts", "kaspa_bg.wasm"];

function hasExpectedVersion() {
  if (requiredFiles.some((fileName) => !existsSync(resolve(packageDir, fileName)))) {
    return false;
  }

  try {
    const pkg = JSON.parse(readFileSync(packageJsonPath, "utf8"));
    return pkg?.version === SDK_VERSION;
  } catch {
    return false;
  }
}

async function downloadArchive() {
  const response = await fetch(SDK_ARCHIVE_URL, {
    headers: {
      "user-agent": "hermes-kasia-bridge/0.1.0",
    },
  });
  if (!response.ok) {
    throw new Error(
      `Failed to download kaspa-wasm archive (${response.status} ${response.statusText})`
    );
  }

  const buffer = Buffer.from(await response.arrayBuffer());
  const digest = createHash("sha256").update(buffer).digest("hex");
  if (digest !== SDK_ARCHIVE_SHA256) {
    throw new Error(
      `kaspa-wasm archive checksum mismatch: expected ${SDK_ARCHIVE_SHA256}, got ${digest}`
    );
  }

  return buffer;
}

function extractPackage(archiveBuffer) {
  const zip = new AdmZip(archiveBuffer);
  const tempDir = resolve(vendorDir, `.kaspa-wasm-${process.pid}-${Date.now()}`);

  rmSync(tempDir, { force: true, recursive: true });
  mkdirSync(tempDir, { recursive: true });

  for (const entry of zip.getEntries()) {
    if (entry.isDirectory || !entry.entryName.startsWith(SDK_ARCHIVE_PREFIX)) {
      continue;
    }

    const relativePath = entry.entryName.slice(SDK_ARCHIVE_PREFIX.length);
    if (!relativePath) {
      continue;
    }

    const destinationPath = join(tempDir, relativePath);
    mkdirSync(dirname(destinationPath), { recursive: true });
    writeFileSync(destinationPath, entry.getData());
  }

  rmSync(packageDir, { force: true, recursive: true });
  mkdirSync(vendorDir, { recursive: true });
  renameSync(tempDir, packageDir);
}

async function main() {
  if (hasExpectedVersion()) {
    return;
  }

  mkdirSync(vendorDir, { recursive: true });
  console.log(`[kasia-bridge] Syncing kaspa-wasm ${SDK_VERSION}`);
  const archiveBuffer = await downloadArchive();
  extractPackage(archiveBuffer);
}

await main();
