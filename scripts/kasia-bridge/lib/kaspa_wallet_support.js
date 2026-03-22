import {
  Address,
  Mnemonic,
  NetworkId,
  PrivateKeyGenerator,
  UtxoEntries,
  XPrv,
  addressFromScriptPublicKey,
  payToAddressScript,
} from "./kaspa_sdk.js";

export const DEFAULT_SEND_STATE = Object.freeze({
  reserved_outpoints: [],
  pending_outputs: [],
  last_compaction_ms: 0,
});
export const DEFAULT_SEND_VISIBILITY_RETRIES = 10;
export const DEFAULT_SEND_VISIBILITY_DELAY_MS = 1000;
export const DEFAULT_MAX_CONFIRMED_INPUT_PLANS = 6;
export const DEFAULT_COMPACTION_INPUT_THRESHOLD = 3;
export const DEFAULT_COMPACTION_MAX_INPUTS = 12;
export const DEFAULT_COMPACTION_COOLDOWN_MS = 60_000;
export const DEFAULT_RESERVED_OUTPOINT_TTL_MS = 120_000;
export const DEFAULT_PENDING_OUTPUT_TTL_MS = 600_000;
export const DUST_THRESHOLD_SOMPI = 10_000n;
export const DEFAULT_LOCAL_PENDING_RETENTION_MS = 30_000;
export const SYNTHETIC_PREVIEW_INPUT_AMOUNT_SOMPI = 10_000_000_000n;
export const DEFAULT_FEE_POLICY = "auto";
export const DEFAULT_FEE_ESTIMATE_TTL_MS = 15_000;
const DEFAULT_AUTO_FEE_TARGET_SECONDS = 8;
export const DEFAULT_LOW_FEE_RATE_SOMPI_PER_GRAM = 1;
export const DEFAULT_NORMAL_FEE_RATE_SOMPI_PER_GRAM = 2;
export const DEFAULT_PRIORITY_FEE_RATE_SOMPI_PER_GRAM = 6;

export function toBigInt(value, fallback = 0n) {
  if (typeof value === "bigint") {
    return value;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return BigInt(Math.trunc(value));
  }
  if (typeof value === "string" && value.trim()) {
    try {
      return BigInt(value.trim());
    } catch {}
  }
  return fallback;
}

export function toNumber(value, fallback = 0) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

function toPositiveNumber(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric > 0 ? numeric : null;
}

export function normalizeFeePolicy(value, fallback = DEFAULT_FEE_POLICY) {
  const normalized = String(value || "").trim().toLowerCase();
  if (
    normalized === "low" ||
    normalized === "normal" ||
    normalized === "priority" ||
    normalized === "auto"
  ) {
    return normalized;
  }
  return normalizeFeePolicy(
    fallback === value ? DEFAULT_FEE_POLICY : fallback,
    DEFAULT_FEE_POLICY
  );
}

export function getFallbackFeeRate(policy = DEFAULT_FEE_POLICY) {
  switch (normalizeFeePolicy(policy)) {
    case "low":
      return DEFAULT_LOW_FEE_RATE_SOMPI_PER_GRAM;
    case "normal":
    case "auto":
      return DEFAULT_NORMAL_FEE_RATE_SOMPI_PER_GRAM;
    case "priority":
    default:
      return DEFAULT_PRIORITY_FEE_RATE_SOMPI_PER_GRAM;
  }
}

function getFirstPositiveBucket(buckets = []) {
  if (!Array.isArray(buckets)) {
    return null;
  }
  return buckets.find((bucket) => toPositiveNumber(bucket?.feerate) != null) || null;
}

function getLastPositiveBucket(buckets = []) {
  if (!Array.isArray(buckets)) {
    return null;
  }
  for (let index = buckets.length - 1; index >= 0; index -= 1) {
    if (toPositiveNumber(buckets[index]?.feerate) != null) {
      return buckets[index];
    }
  }
  return null;
}

export function selectFeeRateFromEstimate(
  feeEstimate,
  policy = DEFAULT_FEE_POLICY,
  { autoTargetSeconds = DEFAULT_AUTO_FEE_TARGET_SECONDS } = {}
) {
  const estimate =
    feeEstimate && typeof feeEstimate.estimate === "object"
      ? feeEstimate.estimate
      : feeEstimate || {};
  const priorityRate = toPositiveNumber(estimate?.priorityBucket?.feerate);
  const firstNormalBucket = getFirstPositiveBucket(estimate?.normalBuckets);
  const lastNormalBucket = getLastPositiveBucket(estimate?.normalBuckets);
  const lowBucket =
    getFirstPositiveBucket(estimate?.lowBuckets) || lastNormalBucket;
  const normalRate = toPositiveNumber(firstNormalBucket?.feerate);
  const lowRate = toPositiveNumber(lowBucket?.feerate);

  switch (normalizeFeePolicy(policy)) {
    case "low":
      return lowRate || normalRate || priorityRate || null;
    case "normal":
      return normalRate || priorityRate || lowRate || null;
    case "auto": {
      const normalSeconds = toPositiveNumber(firstNormalBucket?.estimatedSeconds);
      if (normalRate && (normalSeconds == null || normalSeconds <= autoTargetSeconds)) {
        return normalRate;
      }
      return priorityRate || normalRate || lowRate || null;
    }
    case "priority":
    default:
      return priorityRate || normalRate || lowRate || null;
  }
}

function normalizeOutpoint(outpoint = {}) {
  const transactionId =
    outpoint.transactionId ||
    outpoint.transaction_id ||
    outpoint.txId ||
    outpoint.tx_id ||
    null;
  const index = toNumber(outpoint.index, -1);
  return {
    transactionId,
    index,
  };
}

export function makeOutpointKey(inputOrTransactionId, index) {
  if (
    inputOrTransactionId &&
    typeof inputOrTransactionId === "object" &&
    inputOrTransactionId.outpoint
  ) {
    const normalized = normalizeOutpoint(inputOrTransactionId.outpoint);
    return makeOutpointKey(normalized.transactionId, normalized.index);
  }

  const txId = String(inputOrTransactionId || "").trim();
  const outputIndex = toNumber(index, -1);
  if (!txId || outputIndex < 0) {
    return null;
  }
  return `${txId}:${outputIndex}`;
}

function normalizeReservedOutpoint(entry = {}) {
  const key = String(entry.key || entry.outpoint_key || "").trim();
  if (!key) {
    return null;
  }
  return {
    key,
    reserved_at_ms: toNumber(entry.reserved_at_ms, 0),
  };
}

function normalizePendingOutput(entry = {}) {
  const key =
    String(entry.key || "").trim() ||
    makeOutpointKey(entry.tx_id || entry.transaction_id, entry.index);
  if (!key) {
    return null;
  }
  return {
    key,
    tx_id: String(entry.tx_id || entry.transaction_id || "").trim(),
    index: toNumber(entry.index, 0),
    amount: String(toBigInt(entry.amount, 0n)),
    created_ms: toNumber(entry.created_ms, 0),
    observed_in_mempool: Boolean(
      entry.observed_in_mempool ?? entry.observedInMempool
    ),
  };
}

function outputAddress(output, networkId) {
  try {
    return normalizeAddressValue(
      addressFromScriptPublicKey(output?.scriptPublicKey, networkId)
    );
  } catch {
    return output?.verboseData?.scriptPublicKeyAddress || null;
  }
}

export function mempoolEntriesForAddress(mempoolResponse, address) {
  const entries = Array.isArray(mempoolResponse?.entries)
    ? mempoolResponse.entries
    : [];
  return entries.find((entry) => entry?.address === address) || null;
}

export function pendingOutputsFromMempoolEntry(mempoolEntry, address, networkId, nowMs) {
  const transaction = mempoolEntry?.transaction;
  if (!transaction || !Array.isArray(transaction.outputs)) {
    return [];
  }

  return transaction.outputs
    .map((output, index) => {
      if (outputAddress(output, networkId) !== address) {
        return null;
      }
      const txId = normalizeAddressValue(transaction?.verboseData?.transactionId);
      const key = makeOutpointKey(txId, index);
      if (!key) {
        return null;
      }
      return {
        key,
        tx_id: txId,
        index,
        amount: String(toBigInt(output?.value, 0n)),
        created_ms: nowMs,
        observed_in_mempool: true,
      };
    })
    .filter(Boolean);
}

export function normalizeSendState(sendState = {}) {
  const reserved = Array.isArray(sendState.reserved_outpoints)
    ? sendState.reserved_outpoints
        .map((entry) => normalizeReservedOutpoint(entry))
        .filter(Boolean)
    : [];
  const pending = Array.isArray(sendState.pending_outputs)
    ? sendState.pending_outputs
        .map((entry) => normalizePendingOutput(entry))
        .filter(Boolean)
    : [];

  return {
    reserved_outpoints: reserved,
    pending_outputs: pending,
    last_compaction_ms: toNumber(sendState.last_compaction_ms, 0),
  };
}

export function normalizeUtxoList(entries) {
  if (!entries) {
    return [];
  }
  if (Array.isArray(entries)) {
    return entries.filter(Boolean);
  }
  if (Array.isArray(entries.items)) {
    return entries.items.filter(Boolean);
  }
  if (typeof entries[Symbol.iterator] === "function") {
    return Array.from(entries).filter(Boolean);
  }
  return [];
}

export function isPendingUtxo(entry) {
  return toBigInt(entry?.blockDaaScore, 0n) === 0n;
}

export function isSpendableUtxo(entry) {
  return Boolean(entry) && entry.isCoinbase !== true;
}

export function sortByAmountDescending(entries) {
  return [...entries].sort((left, right) => {
    const diff = toBigInt(right?.amount, 0n) - toBigInt(left?.amount, 0n);
    if (diff === 0n) {
      return 0;
    }
    return diff > 0n ? 1 : -1;
  });
}

export function getTrackedPendingKeys(sendState) {
  return new Set(sendState.pending_outputs.map((entry) => entry.key));
}

export function reconcileSendState(
  sendState,
  liveUtxos,
  {
    nowMs = Date.now(),
    reservedOutpointTtlMs = DEFAULT_RESERVED_OUTPOINT_TTL_MS,
    pendingOutputTtlMs = DEFAULT_PENDING_OUTPUT_TTL_MS,
  } = {}
) {
  const normalized = normalizeSendState(sendState);
  const liveEntries = normalizeUtxoList(liveUtxos);
  const liveByKey = new Map();

  for (const entry of liveEntries) {
    const key = makeOutpointKey(entry);
    if (key) {
      liveByKey.set(key, entry);
    }
  }

  normalized.reserved_outpoints = normalized.reserved_outpoints.filter(
    (entry) => entry.key && entry.reserved_at_ms + reservedOutpointTtlMs > nowMs
  );
  const reservedKeys = new Set(
    normalized.reserved_outpoints.map((entry) => entry.key)
  );

  normalized.pending_outputs = normalized.pending_outputs.filter((entry) => {
    if (!entry.key) {
      return false;
    }
    if (reservedKeys.has(entry.key)) {
      return false;
    }
    const live = liveByKey.get(entry.key);
    if (!live) {
      return entry.created_ms + pendingOutputTtlMs > nowMs;
    }
    return isPendingUtxo(live);
  });

  return normalized;
}

export function buildCandidateUtxoPlans({
  trackedPendingUtxos = [],
  matureUtxos = [],
  maxConfirmedPlans = DEFAULT_MAX_CONFIRMED_INPUT_PLANS,
}) {
  const plans = [];
  const seen = new Set();

  for (const utxo of sortByAmountDescending(trackedPendingUtxos)) {
    const key = makeOutpointKey(utxo);
    if (!key || seen.has(key)) {
      continue;
    }
    seen.add(key);
    plans.push({
      name: "pending-single",
      entries: [utxo],
      usesPendingInputs: true,
    });
  }

  const confirmed = sortByAmountDescending(matureUtxos);
  const planCount = Math.min(confirmed.length, Math.max(1, maxConfirmedPlans));
  for (let count = 1; count <= planCount; count += 1) {
    plans.push({
      name: `confirmed-${count}`,
      entries: confirmed.slice(0, count),
      usesPendingInputs: false,
    });
  }

  if (confirmed.length > planCount) {
    plans.push({
      name: "confirmed-all",
      entries: confirmed,
      usesPendingInputs: false,
    });
  }

  return plans;
}

export function shouldCompactSend({
  matureUtxos = [],
  trackedPendingUtxos = [],
  lastCompactionMs = 0,
  nowMs = Date.now(),
  cooldownMs = DEFAULT_COMPACTION_COOLDOWN_MS,
  threshold = DEFAULT_COMPACTION_INPUT_THRESHOLD,
}) {
  if (trackedPendingUtxos.length > 0) {
    return false;
  }
  if (matureUtxos.length < threshold) {
    return false;
  }
  return nowMs - toNumber(lastCompactionMs, 0) >= cooldownMs;
}

export function createGeneratorEntries(entries) {
  const normalized = normalizeUtxoList(entries);
  if (normalized.length === 0) {
    return new UtxoEntries([]);
  }
  return new UtxoEntries(normalized);
}

export function normalizeAddressValue(value) {
  if (!value) {
    return null;
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value.toString === "function") {
    return value.toString();
  }
  return null;
}

export function isLikelyInsufficientFundsError(error) {
  const text = String(error?.message || error || "").toLowerCase();
  return (
    text.includes("insufficient funds") ||
    text.includes("not enough funds") ||
    text.includes("not enough mature") ||
    text.includes("no transaction was produced") ||
    text.includes("not enough balance") ||
    text.includes("storage mass") ||
    text.includes("larger than max allowed size")
  );
}

export function deriveWalletIdentity(seedPhrase, network) {
  const mnemonic = new Mnemonic(String(seedPhrase || "").trim());
  const seed = mnemonic.toSeed("");
  const xprv = new XPrv(seed);
  const privateKeyGenerator = new PrivateKeyGenerator(xprv, false, BigInt(0));
  const privateKey = privateKeyGenerator.receiveKey(0);
  const publicKey = privateKey.toPublicKey();
  const networkId = new NetworkId(network);
  const address = publicKey.toAddress(networkId).toString();
  const scriptPublicKey = payToAddressScript(new Address(address));
  return {
    address,
    privateKey,
    privateKeyHex: privateKey.toString(),
    publicKeyHex: publicKey.toString(),
    scriptPublicKey,
    network,
    networkId,
  };
}
