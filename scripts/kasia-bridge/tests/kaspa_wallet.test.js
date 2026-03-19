import test from "node:test";
import assert from "node:assert/strict";

import {
  KaspaWalletClient,
  buildCandidateUtxoPlans,
  makeOutpointKey,
  normalizeSendState,
  reconcileSendState,
  shouldCompactSend,
} from "../lib/kaspa_wallet.js";

function utxo({ txId, index, amount, blockDaaScore = 1, isCoinbase = false }) {
  return {
    outpoint: {
      transactionId: txId,
      index,
    },
    amount: BigInt(amount),
    blockDaaScore: BigInt(blockDaaScore),
    isCoinbase,
  };
}

test("buildCandidateUtxoPlans prefers tracked pending self-change before confirmed prefixes", () => {
  const pending = utxo({
    txId: "pending-a",
    index: 0,
    amount: 6000,
    blockDaaScore: 0,
  });
  const matureLarge = utxo({ txId: "confirmed-b", index: 0, amount: 4000 });
  const matureSmall = utxo({ txId: "confirmed-c", index: 1, amount: 2000 });

  const plans = buildCandidateUtxoPlans({
    trackedPendingUtxos: [pending],
    matureUtxos: [matureSmall, matureLarge],
    maxConfirmedPlans: 3,
  });

  assert.equal(plans[0].name, "pending-single");
  assert.equal(makeOutpointKey(plans[0].entries[0]), "pending-a:0");
  assert.equal(plans[1].name, "confirmed-1");
  assert.equal(makeOutpointKey(plans[1].entries[0]), "confirmed-b:0");
  assert.equal(plans[2].name, "confirmed-2");
});

test("reconcileSendState keeps recent invisible pending outputs but drops stale reservations", () => {
  const nowMs = 5_000;
  const state = normalizeSendState({
    reserved_outpoints: [
      { key: "old:0", reserved_at_ms: nowMs - 200_000 },
      { key: "live:1", reserved_at_ms: nowMs - 100 },
    ],
    pending_outputs: [
      {
        key: "pending-visible:0",
        tx_id: "pending-visible",
        index: 0,
        amount: "1000",
        created_ms: nowMs - 100,
      },
      {
        key: "pending-invisible:0",
        tx_id: "pending-invisible",
        index: 0,
        amount: "1000",
        created_ms: nowMs - 100,
      },
    ],
    last_compaction_ms: 99,
  });

  const reconciled = reconcileSendState(
    state,
    [
      utxo({ txId: "live", index: 1, amount: 1200 }),
      utxo({
        txId: "pending-visible",
        index: 0,
        amount: 1000,
        blockDaaScore: 0,
      }),
    ],
    { nowMs }
  );

  assert.deepEqual(
    reconciled.reserved_outpoints.map((entry) => entry.key),
    ["live:1"]
  );
  assert.deepEqual(
    reconciled.pending_outputs.map((entry) => entry.key).sort(),
    ["pending-invisible:0", "pending-visible:0"]
  );
});

test("reconcileSendState removes tracked pending outputs once they mature", () => {
  const state = normalizeSendState({
    pending_outputs: [
      {
        key: "ready:0",
        tx_id: "ready",
        index: 0,
        amount: "1000",
        created_ms: 10,
      },
    ],
  });

  const reconciled = reconcileSendState(state, [
    utxo({
      txId: "ready",
      index: 0,
      amount: 1000,
      blockDaaScore: 25,
    }),
  ]);

  assert.equal(reconciled.pending_outputs.length, 0);
});

test("shouldCompactSend matches KaChat-style no-pending multi-utxo condition", () => {
  assert.equal(
    shouldCompactSend({
      matureUtxos: [utxo({ txId: "a", index: 0, amount: 1 }), utxo({ txId: "b", index: 0, amount: 1 })],
      trackedPendingUtxos: [],
      lastCompactionMs: 0,
      nowMs: 20_000,
      threshold: 3,
      cooldownMs: 1_000,
    }),
    false
  );

  assert.equal(
    shouldCompactSend({
      matureUtxos: [
        utxo({ txId: "a", index: 0, amount: 1 }),
        utxo({ txId: "b", index: 0, amount: 1 }),
        utxo({ txId: "c", index: 0, amount: 1 }),
      ],
      trackedPendingUtxos: [],
      lastCompactionMs: 0,
      nowMs: 20_000,
      threshold: 3,
      cooldownMs: 1_000,
    }),
    true
  );

  assert.equal(
    shouldCompactSend({
      matureUtxos: [
        utxo({ txId: "a", index: 0, amount: 1 }),
        utxo({ txId: "b", index: 0, amount: 1 }),
        utxo({ txId: "c", index: 0, amount: 1 }),
      ],
      trackedPendingUtxos: [utxo({ txId: "pending", index: 0, amount: 2, blockDaaScore: 0 })],
      lastCompactionMs: 0,
      nowMs: 20_000,
      threshold: 3,
      cooldownMs: 1_000,
    }),
    false
  );
});

test("wallet planner passes plain address strings into transaction attempts", async () => {
  class ProbeWalletClient extends KaspaWalletClient {
    constructor() {
      super({
        seedPhrase:
          "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about",
        nodeUrl: "ws://node.invalid",
        network: "mainnet",
      });
      this.identity = { address: "kaspa:qselfaddressxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" };
      this.utxoContext = {};
      this.rpc = {};
      this.planCalls = [];
    }

    _loadSendContext() {
      return {
        trackedPendingUtxos: [],
        availableMatureUtxos: [utxo({ txId: "mature-1", index: 0, amount: 1_000_000 })],
      };
    }

    async _tryPlans(_plans, txOptions) {
      this.planCalls.push({ ...txOptions });
      return {
        success: true,
        transactions: [{ txId: "tx-ok", inputCount: 1, usesPendingInputs: false }],
      };
    }
  }

  const wallet = new ProbeWalletClient();
  const result = await wallet._sendPayloadTransaction({
    destinationAddress: "kaspa:qpeeraddressxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    amountSompi: 1000n,
    payloadBytes: new Uint8Array(),
    strategy: "direct",
  });

  assert.equal(result.txId, "tx-ok");
  assert.equal(wallet.planCalls.length, 1);
  assert.equal(typeof wallet.planCalls[0].destination, "string");
  assert.equal(typeof wallet.planCalls[0].receiveAddress, "string");
});

test("wallet planner can compact before retrying a fragmented direct send", async () => {
  class ProbeWalletClient extends KaspaWalletClient {
    constructor() {
      super({
        seedPhrase:
          "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about",
        nodeUrl: "ws://node.invalid",
        network: "mainnet",
      });
      this.identity = { address: "kaspa:qselfaddressxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" };
      this.utxoContext = {};
      this.rpc = {};
      this.didCompact = false;
      this.compactionCount = 0;
    }

    _loadSendContext() {
      return {
        trackedPendingUtxos: [],
        availableMatureUtxos: [
          utxo({ txId: "m1", index: 0, amount: 1000 }),
          utxo({ txId: "m2", index: 0, amount: 1000 }),
          utxo({ txId: "m3", index: 0, amount: 1000 }),
        ],
      };
    }

    async _tryPlans(_plans, txOptions) {
      if (!this.didCompact && txOptions.destination !== txOptions.receiveAddress) {
        return { success: false, error: new Error("insufficient funds") };
      }
      return {
        success: true,
        transactions: [{ txId: "tx-after-compact", inputCount: 1, usesPendingInputs: true }],
      };
    }

    async _compactMatureUtxos() {
      this.didCompact = true;
      this.compactionCount += 1;
    }
  }

  const wallet = new ProbeWalletClient();
  const result = await wallet._sendPayloadTransaction({
    destinationAddress: "kaspa:qpeeraddressxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    amountSompi: 1000n,
    payloadBytes: new Uint8Array(),
    strategy: "direct",
  });

  assert.equal(wallet.compactionCount, 1);
  assert.equal(result.txId, "tx-after-compact");
  assert.equal(result.usedPendingInput, true);
});
