const $ = (id) => document.getElementById(id);
let token = localStorage.getItem("ikb_token") || "";
let lastAsk = null;

function apiBase() {
  return $("apiBase").value.replace(/\/$/, "");
}

function parseJsonInput(id, fallback = []) {
  try {
    const v = $(id).value?.trim();
    if (!v) return fallback;
    return JSON.parse(v);
  } catch {
    throw new Error(`Invalid JSON in ${id}`);
  }
}

async function req(path, method = "GET", body = null) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${apiBase()}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

async function reqRaw(path, method = "GET") {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${apiBase()}${path}`, { method, headers });
  const text = await res.text();
  if (!res.ok) throw new Error(text || `HTTP ${res.status}`);
  return { text, contentType: res.headers.get("content-type") || "" };
}

function setAuthState(msg, kind = "muted") {
  const el = $("authState");
  el.textContent = msg;
  el.className = kind;
}

function setSessionState(msg) {
  $("sessionState").textContent = msg;
}

function showApp(show) {
  $("appPanel").classList.toggle("hidden", !show);
}

function updateKpis(overview) {
  $("kpiQueries").textContent = overview.queries ?? 0;
  $("kpiAnswerRate").textContent = `${Math.round((overview.answer_rate ?? 0) * 100)}%`;
  $("kpiConfidence").textContent = overview.avg_confidence ?? 0;
  $("kpiHandoffs").textContent = overview.open_handoffs ?? 0;
}

async function refreshOverview() {
  const o = await req("/api/analytics/overview");
  updateKpis(o);
  $("analyticsOut").textContent = JSON.stringify(o, null, 2);
}

async function refreshUsage() {
  const usage = await req("/api/analytics/usage");
  $("usageOut").textContent = JSON.stringify(usage, null, 2);
}

function hydratePolicyForm(policy) {
  if (!policy) return;
  $("policyPack").value = policy.policy_pack || "balanced";
  $("policyMinConfidence").value = policy.min_confidence ?? "";
  $("policyMaxCitations").value = policy.max_citations ?? "";
  $("policyDailyQueryBudget").value = policy.daily_query_budget ?? "";
  $("policyDailyRunBudget").value = policy.daily_run_budget ?? "";
  $("policyDailyCostBudget").value = policy.daily_cost_budget_usd ?? "";
  $("policyMaxTopK").value = policy.max_top_k ?? "";
  $("policyMaxQuestionChars").value = policy.max_question_chars ?? "";
  $("policyKeywords").value = (policy.force_handoff_keywords || []).join(", ");
  $("policyPii").value = policy.pii_redaction_enabled ? "true" : "false";
}

async function whoami() {
  const me = await req("/api/auth/me");
  setSessionState(`${me.email} (${me.role}) • tenant ${me.tenant_id}`);
  return me;
}

async function login(email, password) {
  const data = await req("/api/auth/login", "POST", { email, password });
  token = data.access_token;
  localStorage.setItem("ikb_token", token);
  await whoami();
  showApp(true);
  setAuthState("Logged in ✅", "ok");
  await Promise.allSettled([refreshOverview(), refreshUsage(), loadPolicy()]);
}

$("registerBtn").onclick = async () => {
  try {
    const data = await req("/api/auth/register", "POST", {
      company_name: $("companyName").value,
      name: $("registerName").value,
      email: $("registerEmail").value,
      password: $("registerPassword").value,
    });
    token = data.access_token;
    localStorage.setItem("ikb_token", token);
    await whoami();
    showApp(true);
    setAuthState("Registered and logged in ✅", "ok");
    await Promise.allSettled([refreshOverview(), refreshUsage(), loadPolicy()]);
  } catch (e) {
    setAuthState(`Register failed: ${e.message}`, "danger");
  }
};

$("loginBtn").onclick = async () => {
  try {
    await login($("loginEmail").value, $("loginPassword").value);
  } catch (e) {
    setAuthState(`Login failed: ${e.message}`, "danger");
  }
};

$("logoutBtn").onclick = () => {
  token = "";
  localStorage.removeItem("ikb_token");
  showApp(false);
  setSessionState("Not logged in");
  setAuthState("Logged out", "muted");
};

$("whoamiBtn").onclick = async () => {
  try {
    const me = await whoami();
    alert(`You are ${me.email} (${me.role})`);
  } catch (e) {
    alert(`Not authenticated: ${e.message}`);
  }
};

$("createUserBtn").onclick = async () => {
  try {
    const data = await req("/api/auth/users", "POST", {
      name: $("newUserName").value,
      email: $("newUserEmail").value,
      password: $("newUserPassword").value,
      role: $("newUserRole").value,
    });
    $("createUserOut").textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    $("createUserOut").textContent = `Error: ${e.message}`;
  }
};

$("createGroupBtn").onclick = async () => {
  try {
    const data = await req("/api/groups", "POST", {
      name: $("groupName").value,
      description: $("groupDescription").value,
    });
    $("groupsOut").textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    $("groupsOut").textContent = `Error: ${e.message}`;
  }
};

$("addMemberBtn").onclick = async () => {
  try {
    const gid = Number($("memberGroupId").value);
    const data = await req(`/api/groups/${gid}/members/by-email`, "POST", {
      email: $("memberEmail").value,
    });
    $("groupsOut").textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    $("groupsOut").textContent = `Error: ${e.message}`;
  }
};

$("listGroupsBtn").onclick = async () => {
  try {
    const data = await req("/api/groups");
    $("groupsOut").textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    $("groupsOut").textContent = `Error: ${e.message}`;
  }
};

async function loadPolicy() {
  const data = await req("/api/policy");
  hydratePolicyForm(data);
  $("policyOut").textContent = JSON.stringify(data, null, 2);
  return data;
}

$("getPolicyBtn").onclick = async () => {
  try {
    await loadPolicy();
  } catch (e) {
    $("policyOut").textContent = `Error: ${e.message}`;
  }
};

$("updatePolicyBtn").onclick = async () => {
  try {
    const rawKeywords = $("policyKeywords").value
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const payload = {
      policy_pack: $("policyPack").value,
      min_confidence: Number($("policyMinConfidence").value),
      force_handoff_keywords: rawKeywords,
      pii_redaction_enabled: $("policyPii").value === "true",
      max_citations: Number($("policyMaxCitations").value),
      daily_query_budget: Number($("policyDailyQueryBudget").value),
      daily_run_budget: Number($("policyDailyRunBudget").value),
      daily_cost_budget_usd: Number($("policyDailyCostBudget").value),
      max_top_k: Number($("policyMaxTopK").value),
      max_question_chars: Number($("policyMaxQuestionChars").value),
    };

    Object.keys(payload).forEach((k) => {
      if (payload[k] === "" || Number.isNaN(payload[k])) delete payload[k];
    });

    const data = await req("/api/policy", "PUT", payload);
    hydratePolicyForm(data);
    $("policyOut").textContent = JSON.stringify(data, null, 2);
    await refreshUsage().catch(() => {});
  } catch (e) {
    $("policyOut").textContent = `Error: ${e.message}`;
  }
};

$("usageBtn").onclick = async () => {
  try {
    await refreshUsage();
  } catch (e) {
    $("usageOut").textContent = `Error: ${e.message}`;
  }
};

$("usageExportBtn").onclick = async () => {
  try {
    const usage = await req("/api/analytics/usage");
    downloadJson(`usage-${usage.day_utc || new Date().toISOString().slice(0, 10)}.json`, usage);
  } catch (e) {
    $("usageOut").textContent = `Error: ${e.message}`;
  }
};

$("ingestBtn").onclick = async () => {
  try {
    const payload = {
      title: $("docTitle").value,
      text: $("docText").value,
      roles_allowed: parseJsonInput("docRoles", ["admin", "manager", "employee", "viewer"]),
      groups_allowed: parseJsonInput("docGroups", []),
      tags: parseJsonInput("docTags", []),
      classification: $("docClassification").value || "internal",
      source_url: $("docSourceUrl").value || "",
      freshness_score: Number($("docFreshness").value || 0.5),
    };

    const data = await req("/api/documents/text", "POST", payload);
    $("docsOut").textContent = JSON.stringify(data, null, 2);
    await refreshOverview().catch(() => {});
  } catch (e) {
    $("docsOut").textContent = `Error: ${e.message}`;
  }
};

$("docsBtn").onclick = async () => {
  try {
    const data = await req("/api/documents");
    $("docsOut").textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    $("docsOut").textContent = `Error: ${e.message}`;
  }
};

$("askBtn").onclick = async () => {
  try {
    const topK = Number($("askTopK").value || 8);
    const question = $("question").value;
    const idempotency_key = $("askIdempotency").value.trim() || undefined;

    const d = await req("/api/ask", "POST", { question, top_k: topK, idempotency_key });
    lastAsk = { question, query_log_id: d.query_log_id };

    const flags = [];
    if (d.handoff_recommended) flags.push("handoff_recommended");
    if (d.abstained) flags.push("abstained");
    if (d.matched_policy_keywords?.length) flags.push(`policy_hits: ${d.matched_policy_keywords.join(", ")}`);
    if (d.budget_enforced) flags.push("budget_enforced");

    $("answerOut").textContent = [
      `Run: ${d.run_id ?? "-"} (${d.run_status ?? "unknown"})`,
      `Query Log ID: ${d.query_log_id}`,
      `Confidence: ${d.confidence}`,
      `Flags: ${flags.length ? flags.join(" | ") : "none"}`,
      "",
      d.answer,
    ].join("\n");

    $("citationsOut").innerHTML = "<h4>Citations</h4>" + (d.citations || []).map((c) =>
      `<div class='panel'><span class='tag'>${c.classification}</span><b>${c.document_title}</b><br/>`
      + `score ${c.score} • semantic ${c.semantic_score} • keyword ${c.keyword_score}<br/>${c.snippet}</div>`
    ).join("");

    $("handoffBtn").classList.toggle("hidden", !d.handoff_recommended);
    await Promise.allSettled([refreshOverview(), refreshUsage()]);
  } catch (e) {
    $("answerOut").textContent = `Error: ${e.message}`;
  }
};

$("handoffBtn").onclick = async () => {
  try {
    if (!lastAsk) throw new Error("No previous ask result.");
    const data = await req("/api/handoffs", "POST", {
      question: lastAsk.question,
      context: "Created from operator console",
      query_log_id: lastAsk.query_log_id,
    });
    alert(`Handoff created #${data.ticket_id}`);
    await refreshOverview().catch(() => {});
  } catch (e) {
    alert(`Error: ${e.message}`);
  }
};

$("handoffsBtn").onclick = async () => {
  try {
    const data = await req("/api/handoffs");
    $("handoffsOut").textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    $("handoffsOut").textContent = `Error: ${e.message}`;
  }
};

$("resolveBtn").onclick = async () => {
  try {
    const id = Number($("resolveTicketId").value);
    const resolution = $("resolveText").value;
    const data = await req(`/api/handoffs/${id}/resolve`, "POST", { resolution });
    $("handoffsOut").textContent = JSON.stringify(data, null, 2);
    await refreshOverview().catch(() => {});
  } catch (e) {
    $("handoffsOut").textContent = `Error: ${e.message}`;
  }
};

$("analyticsBtn").onclick = async () => {
  try {
    await refreshOverview();
  } catch (e) {
    $("analyticsOut").textContent = `Error: ${e.message}`;
  }
};

async function loadRuns() {
  const limit = Number($("runsLimit").value || 20);
  const rows = await req(`/api/analytics/runs?limit=${Math.max(1, Math.min(200, limit))}`);
  $("runsOut").textContent = JSON.stringify(rows, null, 2);
  return rows;
}

function downloadJson(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

$("runsBtn").onclick = async () => {
  try {
    await loadRuns();
  } catch (e) {
    $("runsOut").textContent = `Error: ${e.message}`;
  }
};

$("runsRefreshBtn").onclick = async () => {
  try {
    await Promise.all([loadRuns(), refreshUsage()]);
  } catch (e) {
    $("runsOut").textContent = `Error: ${e.message}`;
  }
};

$("runsExportBtn").onclick = async () => {
  try {
    const rows = await loadRuns();
    const ts = new Date().toISOString().replace(/[:]/g, "-");
    downloadJson(`runs-${ts}.json`, rows);
  } catch (e) {
    $("runsOut").textContent = `Error: ${e.message}`;
  }
};

$("replayBtn").onclick = async () => {
  try {
    const runId = Number($("replayRunId").value);
    if (!runId) throw new Error("Provide a valid run ID");
    const data = await req(`/api/analytics/runs/${runId}/replay`, "POST", {});
    alert(`Replay done. New run: ${data.replay_run_id}`);
    await loadRuns().catch(() => {});
  } catch (e) {
    alert(`Replay failed: ${e.message}`);
  }
};

$("auditBtn").onclick = async () => {
  try {
    const data = await req("/api/audit/events?limit=200");
    $("auditOut").textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    $("auditOut").textContent = `Error: ${e.message}`;
  }
};

$("bucketBtn").onclick = async () => {
  try {
    const data = await req("/api/analytics/confidence-buckets");
    $("bucketOut").textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    $("bucketOut").textContent = `Error: ${e.message}`;
  }
};

$("auditJsonBtn").onclick = async () => {
  try {
    const data = await reqRaw("/api/audit/events/export?format=json&limit=2000");
    $("auditOut").textContent = data.text;
  } catch (e) {
    $("auditOut").textContent = `Error: ${e.message}`;
  }
};

$("auditCsvBtn").onclick = async () => {
  try {
    const data = await reqRaw("/api/audit/events/export?format=csv&limit=2000");
    $("auditOut").textContent = data.text;
  } catch (e) {
    $("auditOut").textContent = `Error: ${e.message}`;
  }
};

(async function boot() {
  if (!token) return;
  try {
    await whoami();
    showApp(true);
    setAuthState("Session restored ✅", "ok");
    await Promise.allSettled([refreshOverview(), refreshUsage(), loadPolicy()]);
  } catch {
    token = "";
    localStorage.removeItem("ikb_token");
    setSessionState("Not logged in");
  }
})();
