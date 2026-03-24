export const DEFAULT_CONTEXTUAL_MESSAGE_TARGET_CHARS = 4096;
export const DEFAULT_CONTEXTUAL_MESSAGE_MIN_CHARS = 40;
export const DEFAULT_CONTEXTUAL_MESSAGE_MAX_PARTS = 8;
export const DEFAULT_MAX_SEND_JOBS = 100;
const DEFAULT_SEND_JOB_PREVIEW_CHARS = 120;
export const DEFAULT_SEND_JOB_INDEXER_LOOKBACK_MS = 60_000;
export const DEFAULT_IDENTITY_REFRESH_MS = 15 * 60 * 1000;
export const DEFAULT_LIVE_LOOKBACK_MS = 10 * 60 * 1000;
export const DEFAULT_NODE_STARTUP_TIMEOUT_MS = 12_000;

export function joinUrl(baseUrl, relativePath, params = {}) {
  const normalizedBase = String(baseUrl || "").replace(/\/+$/, "");
  const normalizedPath = String(relativePath || "").replace(/^\/+/, "");
  const url = new URL(`${normalizedBase}/${normalizedPath}`);
  Object.entries(params).forEach(([key, value]) => {
    if (value != null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });
  return url;
}

export function encodeIndexerAlias(alias) {
  return Buffer.from(String(alias || ""), "utf8").toString("hex");
}

export function parseEndpointList(value) {
  if (Array.isArray(value)) {
    return [...new Set(value.map((item) => String(item || "").trim()).filter(Boolean))];
  }
  return [...new Set(
    String(value || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean)
  )];
}

export function isRetryableNodeError(error) {
  const text = String(error?.message || error || "").toLowerCase();
  return (
    text.includes("timeout") ||
    text.includes("connection") ||
    text.includes("socket") ||
    text.includes("rpc") ||
    text.includes("offline") ||
    text.includes("econn") ||
    text.includes("failed to connect") ||
    text.includes("websocket") ||
    text.includes("network")
  );
}

export async function withTimeout(promise, timeoutMs, label) {
  let timeout = null;
  try {
    return await Promise.race([
      promise,
      new Promise((_, reject) => {
        timeout = setTimeout(() => {
          reject(new Error(`${label} timed out after ${timeoutMs}ms`));
        }, timeoutMs);
      }),
    ]);
  } finally {
    clearTimeout(timeout);
  }
}

export function mempoolEntriesForAddress(mempoolResponse, address) {
  const entries = Array.isArray(mempoolResponse?.entries)
    ? mempoolResponse.entries
    : [];
  return entries.find((entry) => String(entry?.address || "").trim() === address) || null;
}

export function senderTransactionsFromAddressEntry(addressEntry) {
  return Array.isArray(addressEntry?.sending)
    ? addressEntry.sending
        .map((entry) => entry?.transaction || null)
        .filter(Boolean)
    : [];
}

export function txIdFromTransaction(transaction) {
  return (
    String(transaction?.verboseData?.transactionId || "").trim() ||
    String(transaction?.transactionId || "").trim() ||
    String(transaction?.id || "").trim() ||
    null
  );
}

export function txPayloadFromTransaction(transaction) {
  return transaction?.payload || transaction?.verboseData?.payload || null;
}

export function txBlockTimeFromRecord(record) {
  return Number(record?.block_time || record?.blockTime || 0);
}

export function publicDelivery(raw, updates = {}) {
  return {
    ...(raw?.delivery || {}),
    ...updates,
  };
}

export function isTerminalSendJobStatus(status) {
  return (
    status === "processed" ||
    status === "sent" ||
    status === "failed" ||
    status === "rejected"
  );
}

export function isBlockingSendJobStatus(status) {
  return status === "queued" || status === "submitting";
}

export function isIndexerTrackedSendJobStatus(status) {
  return status === "submitted" || status === "waiting_for_indexer";
}

export function buildSendJobPreview(message, maxChars = DEFAULT_SEND_JOB_PREVIEW_CHARS) {
  const normalized = String(message || "").trim().replace(/\s+/g, " ");
  if (!normalized) {
    return null;
  }
  if (normalized.length <= maxChars) {
    return normalized;
  }
  return `${normalized.slice(0, Math.max(1, maxChars - 1)).trimEnd()}…`;
}

export function buildSendJobStatusMessage(job) {
  const totalParts = Math.max(0, Number(job?.total_parts || 0));
  const completedParts = Math.max(0, Number(job?.completed_parts || 0));
  const indexedParts = Math.max(0, Number(job?.indexed_parts || 0));
  const plural = totalParts === 1 ? "" : "s";

  switch (job?.status) {
    case "queued":
      return "Queued for Kasia delivery.";
    case "submitting":
      return totalParts > 1
        ? `Submitting ${completedParts}/${totalParts} Kasia parts to the node.`
        : "Submitting the Kasia transaction to the node.";
    case "submitted":
      return totalParts > 1
        ? `Submitted ${completedParts}/${totalParts} Kasia parts to the node. Waiting for indexer visibility.`
        : "Submitted to the Kaspa node. Waiting for indexer visibility.";
    case "waiting_for_indexer":
      return job?.observed_live_ms && indexedParts === 0
        ? "Visible through the live Kaspa path. Waiting for indexer visibility."
        : indexedParts > 0 && totalParts > 0
        ? `${indexedParts}/${totalParts} Kasia part${plural} visible through the indexer.`
        : "Submitted to the Kaspa node. Waiting for indexer visibility.";
    case "processed":
      return totalParts > 1
        ? `All ${totalParts} Kasia parts are visible through the indexer.`
        : "Visible through the Kasia indexer.";
    case "failed":
      return job?.error || "Kasia delivery failed.";
    case "rejected":
      return job?.error || "Kasia delivery was rejected.";
    case "sent":
      return "Sent under the previous Kasia bridge format.";
    default:
      return null;
  }
}

export function toPublicSendJob(job) {
  if (!job) {
    return null;
  }
  return {
    jobId: job.job_id,
    chatId: job.chat_id,
    status: job.status,
    createdMs: job.created_ms,
    updatedMs: job.updated_ms,
    startedMs: job.started_ms,
    finishedMs: job.finished_ms,
    submittedMs: job.submitted_ms,
    observedLiveMs: job.observed_live_ms,
    indexedMs: job.indexed_ms,
    indexedBlockTimeMs: job.indexed_block_time_ms,
    partCount: job.total_parts,
    completedParts: job.completed_parts,
    indexedParts: job.indexed_parts,
    txId: job.last_tx_id,
    txIds: [...(job.tx_ids || [])],
    indexedTxIds: [...(job.indexed_tx_ids || [])],
    error: job.error,
    messagePreview: job.message_preview,
    jobKind: job.job_kind,
    statusMessage: buildSendJobStatusMessage(job),
  };
}

export function isPayloadTooLargeError(error) {
  const text = String(error?.message || error || "").toLowerCase();
  return (
    text.includes("storage mass") ||
    text.includes("larger than max allowed size") ||
    text.includes("transaction is not standard")
  );
}

export function isRetryableHandshakeProcessingError(error) {
  const text = String(error?.message || error || "").toLowerCase();
  return text.includes("missing sender address");
}

export function truncateMessage(
  content,
  maxLength = DEFAULT_CONTEXTUAL_MESSAGE_TARGET_CHARS,
  { annotateParts = true } = {}
) {
  const text = String(content || "");
  if (text.length <= maxLength) {
    return [text];
  }

  const indicatorReserve = 10;
  const fenceClose = "\n```";
  const chunks = [];
  let remaining = text;
  let carryLang = null;

  while (remaining) {
    const prefix = carryLang != null ? `\`\`\`${carryLang}\n` : "";
    let headroom =
      maxLength - indicatorReserve - prefix.length - fenceClose.length;
    if (headroom < 1) {
      headroom = Math.max(1, Math.floor(maxLength / 2));
    }

    if (prefix.length + remaining.length <= maxLength - indicatorReserve) {
      chunks.push(prefix + remaining);
      break;
    }

    const region = remaining.slice(0, headroom);
    let splitAt = region.lastIndexOf("\n");
    if (splitAt < Math.floor(headroom / 2)) {
      splitAt = region.lastIndexOf(" ");
    }
    if (splitAt < 1) {
      splitAt = headroom;
    }

    const candidate = remaining.slice(0, splitAt);
    const backtickCount =
      (candidate.match(/`/g) || []).length -
      (candidate.match(/\\`/g) || []).length;
    if (backtickCount % 2 === 1) {
      let lastBacktick = candidate.lastIndexOf("`");
      while (lastBacktick > 0 && candidate[lastBacktick - 1] === "\\") {
        lastBacktick = candidate.lastIndexOf("`", lastBacktick - 1);
      }
      if (lastBacktick > 0) {
        const safeSpace = candidate.lastIndexOf(" ", lastBacktick);
        const safeNewline = candidate.lastIndexOf("\n", lastBacktick);
        const safeSplit = Math.max(safeSpace, safeNewline);
        if (safeSplit > Math.floor(headroom / 4)) {
          splitAt = safeSplit;
        }
      }
    }

    const chunkBody = remaining.slice(0, splitAt);
    remaining = remaining.slice(splitAt).trimStart();

    let fullChunk = prefix + chunkBody;
    let inCode = carryLang != null;
    let lang = carryLang || "";
    for (const line of chunkBody.split("\n")) {
      const stripped = line.trim();
      if (stripped.startsWith("```")) {
        if (inCode) {
          inCode = false;
          lang = "";
        } else {
          inCode = true;
          const tag = stripped.slice(3).trim();
          lang = tag ? tag.split(/\s+/, 1)[0] : "";
        }
      }
    }

    if (inCode) {
      fullChunk += fenceClose;
      carryLang = lang;
    } else {
      carryLang = null;
    }

    chunks.push(fullChunk);
  }

  if (annotateParts && chunks.length > 1) {
    const total = chunks.length;
    return chunks.map((chunk, index) => `${chunk} (${index + 1}/${total})`);
  }
  return chunks;
}
