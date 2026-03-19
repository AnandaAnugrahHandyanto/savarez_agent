import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { KasiaBridgeCore } from "../lib/bridge_core.js";

class FakeWalletClient {
  constructor() {
    this.isConnected = true;
    this.sentTransactions = [];
    this.info = {
      address: "kaspa:qpeerwalletaddressxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      publicKeyHex: "02".padEnd(66, "1"),
      privateKeyHex: "11".repeat(32),
      network: "mainnet",
    };
  }

  async init() {
    return this.info;
  }

  async close() {}

  async sendPayloadTransaction(payload) {
    this.sentTransactions.push(payload);
    return `tx-${this.sentTransactions.length}`;
  }
}

function response(jsonPayload) {
  return {
    ok: true,
    async json() {
      return jsonPayload;
    },
    async text() {
      return JSON.stringify(jsonPayload);
    },
  };
}

test("send rejects when there is no active conversation", async () => {
  const stateDir = await mkdtemp(join(tmpdir(), "kasia-bridge-"));
  const bridge = new KasiaBridgeCore({
    stateDir,
    indexerUrl: "http://indexer.invalid",
    nodeUrl: "ws://node.invalid",
    network: "mainnet",
    seedPhrase: "seed",
    walletClient: new FakeWalletClient(),
    fetchImpl: async () => response([]),
  });

  await bridge.init();

  await assert.rejects(
    bridge.send({
      chatId: "kaspa:qcontactaddressxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      message: "hello",
    }),
    /No active Kasia conversation/
  );
});

test("state persists across restart and preserves conversation cursors", async () => {
  const stateDir = await mkdtemp(join(tmpdir(), "kasia-bridge-"));
  const bridge = new KasiaBridgeCore({
    stateDir,
    indexerUrl: "http://indexer.invalid",
    nodeUrl: "ws://node.invalid",
    network: "mainnet",
    seedPhrase: "seed",
    walletClient: new FakeWalletClient(),
    fetchImpl: async () => response([]),
  });

  await bridge.init();
  bridge.state.conversations["kaspa:qcontactaddressxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"] = {
    conversation_id: "kasia:test",
    peer_address: "kaspa:qcontactaddressxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    our_alias: "001122334455",
    their_alias: "aabbccddeeff",
    status: "active",
    updated_at: new Date().toISOString(),
    last_handshake_block_time: 100,
    last_context_block_time: 200,
    pending_handshake: null,
  };
  bridge.state.cursors.handshakes_block_time = 100;
  bridge.state.last_sync_ms = 999;
  await bridge.close();

  const restarted = new KasiaBridgeCore({
    stateDir,
    indexerUrl: "http://indexer.invalid",
    nodeUrl: "ws://node.invalid",
    network: "mainnet",
    seedPhrase: "seed",
    walletClient: new FakeWalletClient(),
    fetchImpl: async () => response([]),
  });
  await restarted.init();

  const conversation =
    restarted.state.conversations[
      "kaspa:qcontactaddressxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    ];
  assert.equal(conversation.status, "active");
  assert.equal(conversation.last_context_block_time, 200);
  assert.equal(restarted.state.cursors.handshakes_block_time, 100);
});

test("duplicate transactions are deduplicated by tx id", async () => {
  const stateDir = await mkdtemp(join(tmpdir(), "kasia-bridge-"));
  const bridge = new KasiaBridgeCore({
    stateDir,
    indexerUrl: "http://indexer.invalid",
    nodeUrl: "ws://node.invalid",
    network: "mainnet",
    seedPhrase: "seed",
    walletClient: new FakeWalletClient(),
    fetchImpl: async () => response([]),
  });

  await bridge.init();
  bridge.state.processed_tx_ids.push("tx-dup");
  await bridge.close();

  const stateJson = JSON.parse(
    await readFile(join(stateDir, "state.json"), "utf8")
  );
  assert.deepEqual(stateJson.processed_tx_ids, ["tx-dup"]);
});
