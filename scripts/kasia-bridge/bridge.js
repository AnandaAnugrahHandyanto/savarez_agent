#!/usr/bin/env node

import { createServer } from "node:http";
import { mkdir } from "node:fs/promises";

import {
  createBridgeHandler,
  createSyncRunner,
  getArg,
  resolveStateDir,
} from "./lib/bridge_app.js";
import { KasiaBridgeCore } from "./lib/bridge_core.js";
import { readBridgeEnv, validateBridgeEnv } from "./lib/bridge_env.js";

const args = process.argv.slice(2);
const port = Number.parseInt(getArg(args, "port", "3010"), 10);
const stateDir = resolveStateDir(getArg(args, "state-dir", ""));
const pollIntervalMs = Number.parseInt(getArg(args, "poll-interval-ms", "4000"), 10);

const bridgeConfig = readBridgeEnv(process.env);

try {
  validateBridgeEnv(bridgeConfig);
} catch (error) {
  console.error(error?.message || String(error));
  process.exit(1);
}

const {
  seedPhrase,
  indexerUrl,
  indexerUrls,
  nodeUrl,
  nodeUrls,
  network,
  knsUrl,
  feePolicy,
  maxMultipartParts,
  contextualMessageTargetExplicit,
  contextualMessageTargetChars,
  broadcastSubscriptions,
  allowedBroadcastChannels,
  allowAllBroadcastChannels,
} = bridgeConfig;

await mkdir(stateDir, { recursive: true });

const core = new KasiaBridgeCore({
  stateDir,
  indexerUrl,
  indexerUrls,
  nodeUrl,
  nodeUrls,
  network,
  seedPhrase,
  knsUrl,
  feePolicy,
  broadcastSubscriptions,
  allowedBroadcastChannels,
  allowAllBroadcastChannels,
  maxMultipartParts,
  contextualMessageTargetChars,
  respectContextualMessageTarget: contextualMessageTargetExplicit,
  logger: console,
});
await core.init({ skipInitialSync: true });

const runSync = createSyncRunner(core, console);
const server = createServer(createBridgeHandler(core));

server.listen(port, "127.0.0.1", () => {
  console.log(`[kasia-bridge] Listening on http://127.0.0.1:${port}`);
  console.log(`[kasia-bridge] State directory: ${stateDir}`);
  console.log(`[kasia-bridge] Wallet: ${core.health().walletAddress}`);
  void runSync();
});

const syncTimer = setInterval(() => {
  runSync().catch(() => {});
}, pollIntervalMs);

async function shutdown(signalName) {
  clearInterval(syncTimer);
  server.close();
  await core.close();
  console.log(`[kasia-bridge] Stopped (${signalName})`);
  process.exit(0);
}

process.on("SIGINT", () => {
  shutdown("SIGINT").catch((error) => {
    console.error(error);
    process.exit(1);
  });
});
process.on("SIGTERM", () => {
  shutdown("SIGTERM").catch((error) => {
    console.error(error);
    process.exit(1);
  });
});
