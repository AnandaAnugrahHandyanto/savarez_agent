from __future__ import annotations

import argparse
from typing import Any

from . import api_service as people_api

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse
except ImportError:  # pragma: no cover
    FastAPI = None  # type: ignore[assignment]
    HTTPException = None  # type: ignore[assignment]
    HTMLResponse = None  # type: ignore[assignment]


def create_app() -> "FastAPI":
    if FastAPI is None:  # pragma: no cover
        raise RuntimeError("FastAPI is required to run the PeopleOS service")
    app = FastAPI(title="PeopleOS", version="0.1.0")

    @app.get("/healthz")
    async def healthz():
        return {"ok": True, "service": "peopleos"}

    @app.get("/readyz")
    async def readyz():
        return {"ok": True, "service": "peopleos"}

    @app.get("/")
    async def root():
        return HTMLResponse(_render_peopleos_shell())

    @app.get("/api/status")
    async def status():
        profiles = people_api.list_profiles()["profiles"]
        return {"service": "peopleos", "profile_count": len(profiles)}

    @app.get("/api/profiles")
    async def profiles(profile_type: str | None = None, q: str | None = None):
        return people_api.list_profiles(profile_type=profile_type, q=q)

    @app.post("/api/profiles")
    async def create_profile(payload: dict[str, Any]):
        return people_api.create_profile(payload)

    @app.get("/api/profiles/{slug}")
    async def profile(slug: str):
        try:
            return people_api.get_profile(slug)
        except KeyError:
            raise HTTPException(status_code=404, detail="Profile not found")

    @app.patch("/api/profiles/{slug}")
    async def patch_profile(slug: str, payload: dict[str, Any]):
        try:
            return people_api.patch_profile(slug, payload)
        except KeyError:
            raise HTTPException(status_code=404, detail="Profile not found")

    @app.get("/api/profiles/{slug}/interactions")
    async def interactions(slug: str):
        try:
            return people_api.list_interactions(slug)
        except KeyError:
            raise HTTPException(status_code=404, detail="Profile not found")

    @app.post("/api/profiles/{slug}/interactions")
    async def add_interaction(slug: str, payload: dict[str, Any]):
        try:
            return people_api.add_interaction(slug, payload)
        except KeyError:
            raise HTTPException(status_code=404, detail="Profile not found")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/profiles/{slug}/open-loops")
    async def add_open_loop(slug: str, payload: dict[str, Any]):
        try:
            return people_api.add_open_loop(slug, payload)
        except KeyError:
            raise HTTPException(status_code=404, detail="Profile not found")

    @app.patch("/api/profiles/{slug}/open-loops/{loop_id}")
    async def update_open_loop(slug: str, loop_id: str, payload: dict[str, Any]):
        try:
            return people_api.update_open_loop(slug, loop_id, payload)
        except KeyError:
            raise HTTPException(status_code=404, detail="Open loop not found")

    @app.get("/api/profiles/{slug}/prep")
    async def prep(slug: str, mode: str = "adhoc", minutes_until: int = 5):
        try:
            return people_api.get_prep(slug, mode=mode, minutes_until=minutes_until)
        except KeyError:
            raise HTTPException(status_code=404, detail="Profile not found")

    @app.get("/api/team-scan")
    async def team_scan():
        return people_api.get_team_scan()

    @app.get("/api/schedules")
    async def schedules(now: str | None = None):
        return people_api.list_schedules(now=now)

    @app.post("/api/schedules")
    async def create_schedule(payload: dict[str, Any]):
        return people_api.create_schedule(payload)

    @app.get("/api/schedules/{slug}")
    async def schedule(slug: str, now: str | None = None):
        try:
            return people_api.get_schedule(slug, now=now)
        except KeyError:
            raise HTTPException(status_code=404, detail="Schedule not found")

    @app.patch("/api/schedules/{slug}")
    async def patch_schedule(slug: str, payload: dict[str, Any]):
        try:
            return people_api.patch_schedule(slug, payload)
        except KeyError:
            raise HTTPException(status_code=404, detail="Schedule not found")

    @app.delete("/api/schedules/{slug}")
    async def delete_schedule(slug: str):
        try:
            return people_api.delete_schedule(slug)
        except KeyError:
            raise HTTPException(status_code=404, detail="Schedule not found")

    @app.post("/api/schedules/{slug}/enable")
    async def enable_schedule(slug: str):
        try:
            return people_api.set_schedule_enabled(slug, True)
        except KeyError:
            raise HTTPException(status_code=404, detail="Schedule not found")

    @app.post("/api/schedules/{slug}/disable")
    async def disable_schedule(slug: str):
        try:
            return people_api.set_schedule_enabled(slug, False)
        except KeyError:
            raise HTTPException(status_code=404, detail="Schedule not found")

    @app.post("/api/schedules/{slug}/reschedule-once")
    async def reschedule_once(slug: str, payload: dict[str, Any]):
        try:
            return people_api.reschedule_once(slug, payload)
        except KeyError:
            raise HTTPException(status_code=404, detail="Schedule not found")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/ops/due-now")
    async def due_now(now: str | None = None):
        return people_api.ops_due_now(now=now)

    @app.post("/api/ops/run-due-check")
    async def run_due_check(payload: dict[str, Any] | None = None):
        payload = payload or {}
        return people_api.ops_run_once(now=payload.get("now"))

    @app.get("/api/ops/audit")
    async def audit():
        return people_api.ops_audit()

    return app


def _render_peopleos_shell() -> str:
    return """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>PeopleOS</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif; background: #09111f; color: #e5edf8; }
    body { margin: 0; min-height: 100vh; background: radial-gradient(circle at top left, #19345f 0, transparent 30rem), #09111f; }
    .shell { max-width: 1180px; margin: 0 auto; padding: 32px 20px 56px; }
    .hero { display: flex; justify-content: space-between; gap: 20px; align-items: flex-start; margin-bottom: 24px; }
    h1 { margin: 0; font-size: clamp(32px, 5vw, 56px); letter-spacing: -0.05em; }
    .subtitle { margin: 10px 0 0; max-width: 720px; color: #a9b7cd; line-height: 1.55; }
    .status-card { min-width: 170px; border: 1px solid #29415f; border-radius: 18px; padding: 16px; background: rgba(10, 20, 36, 0.82); box-shadow: 0 20px 80px rgba(0,0,0,.25); }
    .status-card strong { display:block; font-size: 28px; }
    .toolbar { display:flex; gap: 12px; flex-wrap: wrap; margin: 20px 0; }
    .mobile-actions { display:flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
    .tabs { display:flex; gap: 8px; overflow-x:auto; padding: 4px 0 12px; margin: 8px 0 12px; }
    .tab { white-space: nowrap; border: 1px solid #2c4565; background: #0c1829; color: #bfdbfe; border-radius: 999px; padding: 10px 13px; }
    .tab.active { background: #2563eb; color: white; border-color: #60a5fa; }
    input, select, button, textarea { border: 1px solid #2c4565; background: #0c1829; color: #e5edf8; border-radius: 12px; padding: 11px 12px; font: inherit; }
    input { min-width: min(340px, 100%); flex: 1; }
    button { cursor: pointer; background: #2563eb; border-color: #3b82f6; font-weight: 650; }
    button.secondary { background: #102033; border-color: #2c4565; }
    .grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }
    .group-section { margin: 18px 0 26px; }
    .group-heading { display:flex; align-items: baseline; justify-content: space-between; gap: 12px; margin: 0 0 10px; }
    .group-heading h2 { margin: 0; font-size: 21px; }
    .profile-card { border: 1px solid #233b5a; border-radius: 18px; background: rgba(12, 24, 41, .86); padding: 18px; box-shadow: 0 12px 40px rgba(0,0,0,.18); }
    .profile-card h2 { margin: 0 0 8px; font-size: 20px; }
    .muted { color: #93a4bc; }
    .pill-row { display:flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
    .pill { color:#bfdbfe; background:#11294a; border:1px solid #264c7c; border-radius:999px; padding:5px 9px; font-size:12px; }
    .detail { margin-top: 18px; border: 1px solid #29415f; border-radius: 20px; background: rgba(10,20,36,.92); padding: 18px; display: none; }
    .detail.visible { display: block; }
    .detail pre { white-space: pre-wrap; color: #c9d7eb; background: #07101d; border-radius: 14px; padding: 14px; overflow:auto; }
    .detail-pane { display:none; }
    .detail-pane.active { display:block; }
    .quick-note { display:grid; gap: 10px; margin-top: 14px; }
    .quick-note textarea { min-height: 90px; }
    .panel { border: 1px solid #233b5a; border-radius: 18px; background: rgba(12,24,41,.72); padding: 16px; margin: 16px 0; }
    .form-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; }
    label { display:grid; gap: 6px; color: #b9c7da; font-size: 13px; }
    label span { font-weight: 650; }
    .full-span { grid-column: 1 / -1; }
    .hidden { display: none !important; }
    @media (max-width: 720px) { .hero { flex-direction: column; } .status-card { width: 100%; box-sizing: border-box; } }
  </style>
</head>
<body>
  <main class=\"shell\">
    <section class=\"hero\">
      <div>
        <h1>PeopleOS</h1>
        <p class=\"subtitle\">Standalone relationship operating system. This UI reads the canonical PeopleOS data root shared by Miya and WebUI.</p>
        <div class=\"mobile-actions\"><button onclick=\"toggleCreatePanel()\">+ Add</button><button class=\"secondary\" onclick=\"loadProfiles()\">Refresh</button></div>
      </div>
      <aside class=\"status-card\"><span class=\"muted\">Profiles loaded</span><strong id=\"profile-count\">—</strong></aside>
    </section>
    <section class=\"toolbar\">
      <input id=\"search\" placeholder=\"Search profiles, roles, relationships…\" />
      <select id=\"type-filter\"><option value=\"\">All categories</option><option value=\"Nexus\">Nexus</option><option value=\"Satellites\">Satellites</option><option value=\"External\">External</option></select>
      <select id=\"profile-sort-select\" aria-label=\"Sort profiles\">
        <option id=\"sort-rank\" value=\"rank\">Sort: rank</option>
        <option id=\"sort-updated\" value=\"updated\">Sort: last update</option>
        <option id=\"sort-next-followup\" value=\"next-followup\">Sort: next follow-up</option>
        <option id=\"sort-first-name\" value=\"first-name\">Sort: first name</option>
      </select>
      <button id=\"refresh\">Refresh</button>
    </section>
    <nav class=\"tabs\" aria-label=\"PeopleOS roster tabs\">
      <button id=\"tab-all\" class=\"tab active\" onclick=\"setRosterTab('all')\">All</button>
      <button id=\"tab-nexus\" class=\"tab\" onclick=\"setRosterTab('nexus')\">Nexus</button>
      <button id=\"tab-satellites\" class=\"tab\" onclick=\"setRosterTab('satellites')\">Satellites</button>
      <button id=\"tab-external\" class=\"tab\" onclick=\"setRosterTab('external')\">External</button>
      <button id=\"tab-due\" class=\"tab\" onclick=\"setRosterTab('due')\">Due</button>
      <button id=\"tab-open-loops\" class=\"tab\" onclick=\"setRosterTab('open-loops')\">Open Loops</button>
    </nav>
    <section id=\"create-profile-panel\" class=\"panel hidden\">
      <h2>Create profile</h2>
      <div id=\"create-profile-form\" class=\"form-grid\">
        <label><span>Name</span><input id=\"create-name\" placeholder=\"e.g. Yi Bao\" /></label>
        <label><span>Category</span><select id=\"create-category\" name=\"category\"><option value=\"Nexus\">Nexus</option><option value=\"Satellites\">Satellites</option><option value=\"External\">External</option></select></label>
        <label><span>Rank (1-101)</span><input id=\"create-rank\" type=\"number\" min=\"1\" max=\"101\" value=\"101\" /></label>
        <label><span>Trust</span><select id=\"create-trust\"><option>Rock Solid</option><option>Very High</option><option>Positive</option><option selected>Normal</option><option>Low</option></select></label>
        <label><span>Cadence</span><select id=\"create-cadence\"><option>weekly</option><option>biweekly</option><option selected>monthly</option></select></label>
        <label class=\"full-span\"><span>Role(s)</span><textarea id=\"create-roles\" rows=\"3\" placeholder=\"One role per line…\"></textarea></label>
        <label class=\"full-span\"><span>Mandate(s)</span><textarea id=\"create-mandates\" rows=\"3\" placeholder=\"One mandate per line…\"></textarea></label>
        <button onclick=\"createProfile()\">Create profile</button>
      </div>
    </section>
    <section id=\"profile-list\" class=\"grid\" aria-live=\"polite\"></section>
    <section id=\"profile-detail\" class=\"detail\"></section>
  </main>
<script>
let profiles = [];
let currentRosterTab = 'all';
let currentDetailTab = 'summary';
const categoryValues = ['Nexus', 'Satellites', 'External'];
const trustValues = ['Rock Solid', 'Very High', 'Positive', 'Normal', 'Low'];
const cadenceValues = ['weekly', 'biweekly', 'monthly'];
const performanceValues = ['exceeds expectations', 'meets expectations', 'below expectations'];
const cadenceWeekValues = ['', '1', '2', '3', '4', 'last'];
const weekParityValues = ['', 'odd', 'even'];
const weekdayValues = ['', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const hourValues = Array.from({length: 24}, (_, i) => String(i).padStart(2, '0'));
const minuteValues = ['00', '15', '30', '45'];
const listEl = document.getElementById('profile-list');
const detailEl = document.getElementById('profile-detail');
const countEl = document.getElementById('profile-count');
const searchEl = document.getElementById('search');
const typeEl = document.getElementById('type-filter');
const sortEl = document.getElementById('profile-sort-select');

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'\"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',\"'\":'&#39;','\\\"':'&quot;'}[ch] || ch));
}

function optionHtml(values, selected) {
  return values.map(value => `<option value=\"${escapeHtml(value)}\" ${value === selected ? 'selected' : ''}>${escapeHtml(value)}</option>`).join('');
}

function cadenceWeekOptionHtml(selected) {
  const labels = {'': 'No monthly week', '1': '1st week', '2': '2nd week', '3': '3rd week', '4': '4th week', 'last': 'last week'};
  return cadenceWeekValues.map(value => `<option value=\"${escapeHtml(value)}\" ${value === String(selected ?? '') ? 'selected' : ''}>${labels[value]}</option>`).join('');
}

function weekParityOptionHtml(selected) {
  const labels = {'': 'No odd/even week', 'odd': 'odd week', 'even': 'even week'};
  return weekParityValues.map(value => `<option value=\"${escapeHtml(value)}\" ${value === String(selected ?? '') ? 'selected' : ''}>${labels[value]}</option>`).join('');
}

function toggleCreatePanel() {
  document.getElementById('create-profile-panel').classList.toggle('hidden');
}

function setRosterTab(tab) {
  currentRosterTab = tab;
  ['all','nexus','satellites','external','due','open-loops'].forEach(name => {
    document.getElementById(`tab-${name}`).classList.toggle('active', name === tab);
  });
  typeEl.value = tab === 'external' ? 'External' : tab === 'nexus' ? 'Nexus' : tab === 'satellites' ? 'Satellites' : '';
  renderProfiles();
}

function setDetailTab(tab) {
  currentDetailTab = tab;
  ['summary','touch','fields','loops'].forEach(name => {
    const button = document.getElementById(`detail-tab-${name}`);
    const pane = document.getElementById(`detail-pane-${name}`);
    if (button) button.classList.toggle('active', name === tab);
    if (pane) pane.classList.toggle('active', name === tab);
  });
}

function profileGroup(profile) {
  const category = String(profile.category || '').trim();
  if (category === 'External') return 'external';
  if (category === 'Satellites') return 'satellites';
  return 'nexus';
}

function profileMatches(profile) {
  const q = searchEl.value.trim().toLowerCase();
  const category = typeEl.value;
  if (category && (profile.category || 'Nexus') !== category) return false;
  const group = profileGroup(profile);
  if (currentRosterTab === 'nexus' && group !== 'nexus') return false;
  if (currentRosterTab === 'satellites' && group !== 'satellites') return false;
  if (currentRosterTab === 'external' && group !== 'external') return false;
  if (currentRosterTab === 'open-loops' && Number(profile.open_loop_count || 0) <= 0) return false;
  if (currentRosterTab === 'due' && !profile.next_checkup_at) return false;
  if (!q) return true;
  return [profile.name, profile.slug, profile.roles, profile.mandates, profile.category, profile.trust].join(' ').toLowerCase().includes(q);
}

function firstName(profile) {
  return String(profile.name || profile.slug || '').trim().split(/\s+/)[0].toLowerCase();
}

function timestampValue(value, emptyLast = true) {
  if (!value) return emptyLast ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY;
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return emptyLast ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY;
  return parsed;
}

function numericRank(profile) {
  const rank = Number(profile.rank || 101);
  return Number.isFinite(rank) && rank >= 1 && rank <= 101 ? rank : 101;
}

function sortProfiles(items) {
  const sortMode = sortEl.value || 'rank';
  return [...items].sort((a, b) => {
    if (sortMode === 'updated') return timestampValue(b.updated_at, false) - timestampValue(a.updated_at, false) || firstName(a).localeCompare(firstName(b));
    if (sortMode === 'next-followup') return timestampValue(a.next_meeting_date || a.next_checkup_at, true) - timestampValue(b.next_meeting_date || b.next_checkup_at, true) || firstName(a).localeCompare(firstName(b));
    if (sortMode === 'first-name') return firstName(a).localeCompare(firstName(b));
    return numericRank(a) - numericRank(b) || firstName(a).localeCompare(firstName(b));
  });
}

function profileCard(p) {
  return `
    <article class=\"profile-card\">
      <h2>${escapeHtml(p.name)}</h2>
      <div class=\"muted\">${escapeHtml(p.roles || p.role_title || 'No roles yet')} · ${escapeHtml(p.slug)}</div>
      <div class=\"pill-row\">
        <span class=\"pill\">${escapeHtml(p.category || 'Nexus')}</span>
        <span class=\"pill\">Rank: ${escapeHtml(p.rank || 101)}</span>
        <span class=\"pill\">Trust: ${escapeHtml(p.trust || 'Normal')}</span>
        <span class=\"pill\">${escapeHtml(p.cadence || 'monthly')}</span>
        <span class=\"pill\">${Number(p.open_loop_count || 0)} open loops</span>
        <span class=\"pill\">${Number(p.interaction_count || 0)} notes</span>
      </div>
      <p class=\"muted profile-card-next-meeting\">Next meeting: ${escapeHtml(p.next_meeting_date || '—')}</p>
      <p class=\"muted\">Updated: ${escapeHtml(p.updated_at || '—')}</p>
      <button class=\"secondary\" onclick=\"openProfile('${escapeHtml(p.slug)}')\">Open</button>
      <button onclick=\"openProfile('${escapeHtml(p.slug)}', 'touch')\">Touch</button>
    </article>`;
}

function renderGroupSection(title, key, items) {
  if (!items.length) return '';
  return `<section class=\"group-section\" data-group=\"${key}\">
    <div class=\"group-heading\"><h2>${title}</h2><span class=\"muted\">${items.length} profiles</span></div>
    <div class=\"grid\">${sortProfiles(items).map(profileCard).join('')}</div>
  </section>`;
}

function renderProfiles() {
  const visible = profiles.filter(profileMatches);
  countEl.textContent = String(profiles.length);
  if (!visible.length) {
    listEl.innerHTML = '<p class=\"muted\">No profiles match.</p>';
    return;
  }
  const grouped = {nexus: [], satellites: [], external: []};
  visible.forEach(p => grouped[profileGroup(p)].push(p));
  if (currentRosterTab === 'nexus') listEl.innerHTML = renderGroupSection('Nexus', 'nexus', grouped.nexus) || '<p class=\"muted\">No Nexus profiles match.</p>';
  else if (currentRosterTab === 'satellites') listEl.innerHTML = renderGroupSection('Satellites', 'satellites', grouped.satellites) || '<p class=\"muted\">No Satellite profiles match.</p>';
  else if (currentRosterTab === 'external') listEl.innerHTML = renderGroupSection('External', 'external', grouped.external) || '<p class=\"muted\">No External profiles match.</p>';
  else listEl.innerHTML = [
    renderGroupSection('Nexus', 'nexus', grouped.nexus),
    renderGroupSection('Satellites', 'satellites', grouped.satellites),
    renderGroupSection('External', 'external', grouped.external),
  ].filter(Boolean).join('') || '<p class=\"muted\">No profiles match.</p>';
}

async function loadProfiles() {
  listEl.innerHTML = '<p class=\"muted\">Loading profiles…</p>';
  const response = await fetch('/api/profiles');
  const payload = await response.json();
  profiles = payload.profiles || [];
  renderProfiles();
}

async function openProfile(slug, tab = 'summary') {
  // card shortcut target: openProfile(p.slug, 'touch')
  const response = await fetch(`/api/profiles/${encodeURIComponent(slug)}`);
  const payload = await response.json();
  const p = payload.profile;
  const cadenceDetails = p.cadence_details || {};
  detailEl.className = 'detail visible';
  detailEl.innerHTML = `
    <h2>${escapeHtml(p.name)}</h2>
    <p class=\"muted\">${escapeHtml(p.roles || p.role_title || '')}</p>
    <nav class=\"tabs\" aria-label=\"Profile detail tabs\">
      <button id=\"detail-tab-summary\" class=\"tab active\" onclick=\"setDetailTab('summary')\">Summary</button>
      <button id=\"detail-tab-touch\" class=\"tab\" onclick=\"setDetailTab('touch')\">Touch</button>
      <button id=\"detail-tab-fields\" class=\"tab\" onclick=\"setDetailTab('fields')\">Fields</button>
      <button id=\"detail-tab-loops\" class=\"tab\" onclick=\"setDetailTab('loops')\">Loops</button>
    </nav>
    <section id=\"detail-pane-summary\" class=\"detail-pane active\">
      <h3>Summary</h3>
      <div class=\"pill-row\"><span class=\"pill\">${escapeHtml(p.category || 'Nexus')}</span><span class=\"pill\">Rank: ${escapeHtml(p.rank || 101)}</span><span class=\"pill\">Trust: ${escapeHtml(p.trust || 'Normal')}</span><span class=\"pill\">Cadence: ${escapeHtml(p.cadence || 'monthly')}</span><span class=\"pill\">Performance: ${escapeHtml(p.performance_rating || 'meets expectations')}</span></div>
      <p class=\"muted\">Last meeting: ${escapeHtml(p.last_meeting_date || '—')} · Next meeting: ${escapeHtml(p.next_meeting_date || '—')}</p>
    </section>
    <section id=\"detail-pane-fields\" class=\"detail-pane\">
    <h3>Editable fields</h3>
    <div class=\"form-grid\">
      <label><span>Name</span><input id=\"field-name\" value=\"${escapeHtml(p.name || '')}\" /></label>
      <label><span>Category</span><select id=\"field-category\">${optionHtml(categoryValues, p.category || 'Nexus')}</select></label>
      <label><span>Rank (1-101)</span><input id=\"field-rank\" type=\"number\" min=\"1\" max=\"101\" value=\"${escapeHtml(p.rank || 101)}\" /></label>
      <label><span>Trust</span><select id=\"field-trust\">${optionHtml(trustValues, p.trust || 'Normal')}</select></label>
      <label><span>Cadence</span><select id=\"field-cadence\" onchange=\"updateCadenceDetailsVisibility()\">${optionHtml(cadenceValues, p.cadence || 'monthly')}</select></label>
      <div id=\"cadence-details-panel\" class=\"panel full-span\">
        <strong>Cadence details</strong>
        <p class=\"muted\">Set recurring meeting timing. Use monthly week only when cadence is monthly.</p>
        <div class=\"form-grid\">
          <label id=\"cadence-week-wrap\"><span>Which week of month</span><select id=\"field-cadence-week-of-month\">${cadenceWeekOptionHtml(cadenceDetails.week_of_month)}</select></label>
          <label id=\"cadence-parity-wrap\"><span>Odd/even week</span><select id=\"field-cadence-week-parity\">${weekParityOptionHtml(cadenceDetails.week_parity)}</select></label>
          <label><span>Weekday</span><select id=\"field-cadence-weekday\">${optionHtml(weekdayValues, cadenceDetails.weekday || '')}</select></label>
          <label><span>Hour</span><select id=\"field-cadence-hour\">${optionHtml(hourValues, String(cadenceDetails.hour ?? 9).padStart(2, '0'))}</select></label>
          <label><span>Minute</span><select id=\"field-cadence-minute\">${optionHtml(minuteValues, String(cadenceDetails.minute ?? 0).padStart(2, '0'))}</select></label>
        </div>
      </div>
      <div class=\"panel full-span\">
        <strong>Meeting dates</strong>
        <p class=\"muted\">Last meeting defaults from database. Next meeting defaults from cadence calculation unless manually overridden.</p>
        <div class=\"form-grid\">
          <label><span>Last meeting date (yyyy-mm-dd) <em id=\"last-meeting-date-source\" class=\"muted\">${escapeHtml(p.last_meeting_date_source || 'database')}</em></span><input id=\"field-last-meeting-date\" data-original=\"${escapeHtml(p.last_meeting_date || '')}\" data-overridden=\"${p.last_meeting_date_overridden ? 'true' : 'false'}\" value=\"${escapeHtml(p.last_meeting_date || '')}\" disabled /></label>
          <div class=\"pill-row\"><button id=\"edit-last-meeting-date\" class=\"secondary\" onclick=\"setMeetingDateEditMode('last', true)\">Edit</button><button id=\"save-last-meeting-date\" onclick=\"confirmMeetingDateEdit('last')\">Save</button><button id=\"cancel-last-meeting-date\" class=\"secondary\" onclick=\"cancelMeetingDateEdit('last')\">Cancel</button></div>
          <label><span>Next meeting date (yyyy-mm-dd) <em id=\"next-meeting-date-source\" class=\"muted\">${escapeHtml(p.next_meeting_date_source || 'calculated')}</em></span><input id=\"field-next-meeting-date\" data-original=\"${escapeHtml(p.next_meeting_date || '')}\" data-overridden=\"${p.next_meeting_date_overridden ? 'true' : 'false'}\" value=\"${escapeHtml(p.next_meeting_date || '')}\" disabled /></label>
          <div class=\"pill-row\"><button id=\"edit-next-meeting-date\" class=\"secondary\" onclick=\"setMeetingDateEditMode('next', true)\">Edit</button><button id=\"save-next-meeting-date\" onclick=\"confirmMeetingDateEdit('next')\">Save</button><button id=\"cancel-next-meeting-date\" class=\"secondary\" onclick=\"cancelMeetingDateEdit('next')\">Cancel</button></div>
          <p id=\"next-meeting-calculated-preview\" class=\"muted full-span\">Calculated next meeting: —</p>
        </div>
      </div>
      <label><span>Performance</span><select id=\"field-performance-rating\">${optionHtml(performanceValues, p.performance_rating || 'meets expectations')}</select></label>
      <label class=\"full-span\"><span>Role(s)</span><textarea id=\"field-roles\" rows=\"3\">${escapeHtml(p.roles || '')}</textarea></label>
      <label class=\"full-span\"><span>Mandate(s)</span><textarea id=\"field-mandates\" rows=\"3\">${escapeHtml(p.mandates || '')}</textarea></label>
      <label class=\"full-span\"><span>Notes from last meeting</span><textarea id=\"field-last-meeting-notes\">${escapeHtml(p.last_meeting_notes || '')}</textarea></label>
      <label class=\"full-span\"><span>Prep notes for next meeting</span><textarea id=\"field-prep-notes\">${escapeHtml(p.prep_notes || '')}</textarea></label>
      <label class=\"full-span\"><span>Long-term notes/todos</span><textarea id=\"field-long-term-notes-todos\">${escapeHtml(p.long_term_notes_todos || '')}</textarea></label>
      <label class=\"full-span\"><span>Strengths</span><textarea id=\"field-strengths\">${escapeHtml(p.strengths || '')}</textarea></label>
      <label class=\"full-span\"><span>Weaknesses</span><textarea id=\"field-weaknesses\">${escapeHtml(p.weaknesses || '')}</textarea></label>
      <button onclick=\"saveProfileFields('${escapeHtml(p.slug)}')\">Save fields</button>
    </div>
    </section>
    <section id=\"detail-pane-touch\" class=\"detail-pane\">
    <h3>Quick add note / update</h3>
    <div class=\"quick-note\">
      <select id=\"note-kind\"><option value=\"update\">Update</option><option value=\"one_on_one\">1:1</option><option value=\"assessment\">Assessment</option><option value=\"todo_manager\">Todo for Michael</option><option value=\"todo_report\">Todo for them</option></select>
      <textarea id=\"note-body\" placeholder=\"Write a Miya/WebUI-visible note…\"></textarea>
      <button onclick=\"saveNote('${escapeHtml(p.slug)}')\">Save note</button>
    </div>
    </section>
    <section id=\"detail-pane-loops\" class=\"detail-pane\">
      <h3>Open loops</h3>
      <pre>${escapeHtml(JSON.stringify(p.open_loop_items || p.open_loops || {}, null, 2))}</pre>
    </section>`;
  setDetailTab(tab);
  updateCadenceDetailsVisibility();
  applyCadenceDetails(cadenceDetails);
  ['field-cadence','field-cadence-week-of-month','field-cadence-week-parity','field-cadence-weekday','field-cadence-hour','field-cadence-minute'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', () => { updateCadenceDetailsVisibility(); recalculateNextMeetingDate(); });
  });
  recalculateNextMeetingDate();
  detailEl.scrollIntoView({behavior: 'smooth', block: 'start'});
}

function updateCadenceDetailsVisibility() {
  const cadenceEl = document.getElementById('field-cadence');
  const weekWrap = document.getElementById('cadence-week-wrap');
  const parityWrap = document.getElementById('cadence-parity-wrap');
  if (!cadenceEl) return;
  if (weekWrap) weekWrap.classList.toggle('hidden', cadenceEl.value !== 'monthly');
  if (parityWrap) parityWrap.classList.toggle('hidden', cadenceEl.value !== 'biweekly');
}

function buildCadenceDetails() {
  const week = document.getElementById('field-cadence-week-of-month')?.value || '';
  const parity = document.getElementById('field-cadence-week-parity')?.value || '';
  const weekday = document.getElementById('field-cadence-weekday')?.value || '';
  const hour = document.getElementById('field-cadence-hour')?.value || '';
  const minute = document.getElementById('field-cadence-minute')?.value || '';
  const details = {};
  if (document.getElementById('field-cadence')?.value === 'monthly' && week) details.week_of_month = week;
  if (document.getElementById('field-cadence')?.value === 'biweekly' && parity) details.week_parity = parity;
  if (weekday) details.weekday = weekday;
  if (hour) details.hour = Number(hour);
  if (minute) details.minute = Number(minute);
  return details;
}

function applyCadenceDetails(details) {
  if (!details) return;
  const week = document.getElementById('field-cadence-week-of-month');
  const parity = document.getElementById('field-cadence-week-parity');
  const weekday = document.getElementById('field-cadence-weekday');
  const hour = document.getElementById('field-cadence-hour');
  const minute = document.getElementById('field-cadence-minute');
  if (week) week.value = String(details.week_of_month || '');
  if (parity) parity.value = String(details.week_parity || '');
  if (weekday) weekday.value = String(details.weekday || '');
  if (hour) hour.value = String(details.hour ?? 9).padStart(2, '0');
  if (minute) minute.value = String(details.minute ?? 0).padStart(2, '0');
}

function parseLocalDate(value) {
  if (!value) return null;
  const parts = String(value).slice(0, 10).split('-').map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) return null;
  return new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
}

function formatLocalDate(date) {
  return date ? date.toISOString().slice(0, 10) : '';
}

function addMonthsClamped(date) {
  const year = date.getUTCFullYear();
  const month = date.getUTCMonth();
  const day = date.getUTCDate();
  const target = new Date(Date.UTC(year, month + 2, 0));
  const maxDay = target.getUTCDate();
  return new Date(Date.UTC(year, month + 1, Math.min(day, maxDay)));
}

function nthWeekdayOfMonth(year, monthIndex, weekdayName, weekOfMonth) {
  const weekdayIndex = weekdayValues.slice(1).indexOf(weekdayName);
  if (weekdayIndex < 0 || !weekOfMonth) return null;
  if (weekOfMonth === 'last') {
    const current = new Date(Date.UTC(year, monthIndex + 1, 0));
    while (current.getUTCDay() !== (weekdayIndex + 1) % 7) current.setUTCDate(current.getUTCDate() - 1);
    return current;
  }
  const nth = Number(weekOfMonth);
  if (!Number.isFinite(nth) || nth < 1 || nth > 4) return null;
  const current = new Date(Date.UTC(year, monthIndex, 1));
  while (current.getUTCDay() !== (weekdayIndex + 1) % 7) current.setUTCDate(current.getUTCDate() + 1);
  current.setUTCDate(current.getUTCDate() + 7 * (nth - 1));
  return current.getUTCMonth() === monthIndex ? current : null;
}

function nextWeekdayOnOrAfter(reference, weekdayName) {
  const weekdayIndex = weekdayValues.slice(1).indexOf(weekdayName);
  if (weekdayIndex < 0) return reference;
  const target = (weekdayIndex + 1) % 7;
  const next = new Date(reference.getTime());
  next.setUTCDate(next.getUTCDate() + ((target - next.getUTCDay() + 7) % 7));
  return next;
}

function isoWeek(date) {
  const tmp = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  tmp.setUTCDate(tmp.getUTCDate() + 4 - (tmp.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(tmp.getUTCFullYear(), 0, 1));
  return Math.ceil((((tmp - yearStart) / 86400000) + 1) / 7);
}

function recalculateNextMeetingDate() {
  const preview = document.getElementById('next-meeting-calculated-preview');
  if (!preview) return '';
  const now = new Date();
  const reference = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
  const cadence = document.getElementById('field-cadence')?.value || 'monthly';
  const details = buildCadenceDetails();
  let next;
  if (cadence === 'weekly') next = nextWeekdayOnOrAfter(reference, details.weekday);
  else if (cadence === 'biweekly') {
    next = nextWeekdayOnOrAfter(reference, details.weekday);
    while (['odd','even'].includes(details.week_parity || '') && ((isoWeek(next) % 2 === 1) !== (details.week_parity === 'odd'))) next.setUTCDate(next.getUTCDate() + 7);
  } else {
    const clamped = addMonthsClamped(reference);
    next = nthWeekdayOfMonth(clamped.getUTCFullYear(), clamped.getUTCMonth(), details.weekday, details.week_of_month) || clamped;
  }
  const value = formatLocalDate(next);
  preview.textContent = `Calculated next meeting: ${value}`;
  const nextEl = document.getElementById('field-next-meeting-date');
  if (nextEl && nextEl.dataset.overridden !== 'true' && nextEl.disabled) nextEl.value = value;
  return value;
}

function meetingDateInput(kind) {
  return document.getElementById(kind === 'last' ? 'field-last-meeting-date' : 'field-next-meeting-date');
}

function setMeetingDateEditMode(kind, editing) {
  const input = meetingDateInput(kind);
  if (!input) return;
  input.disabled = !editing;
  if (editing) input.dataset.draft = input.value || '';
}

function confirmMeetingDateEdit(kind) {
  const input = meetingDateInput(kind);
  if (!input) return;
  input.dataset.original = input.value || '';
  input.dataset.overridden = 'true';
  input.disabled = true;
  const source = document.getElementById(kind === 'last' ? 'last-meeting-date-source' : 'next-meeting-date-source');
  if (source) source.textContent = 'manual';
}

function cancelMeetingDateEdit(kind) {
  const input = meetingDateInput(kind);
  if (!input) return;
  input.value = input.dataset.original || '';
  input.disabled = true;
}

async function createProfile() {
  const category = document.getElementById('create-category').value;
  const roles = document.getElementById('create-roles').value.trim();
  const mandates = document.getElementById('create-mandates').value.trim();
  const payload = {
    name: document.getElementById('create-name').value.trim(),
    category,
    rank: Number(document.getElementById('create-rank').value || 101),
    roles,
    role_title: roles.split('\\n').map(x => x.trim()).filter(Boolean).join('; '),
    mandates,
    mandate: mandates,
    trust: document.getElementById('create-trust').value,
    cadence: document.getElementById('create-cadence').value,
    profile_type: category === 'External' ? 'external' : 'internal',
    relationship_kind: category === 'External' ? 'other' : 'direct_report'
  };
  if (!payload.name) return alert('Name is required.');
  const response = await fetch('/api/profiles', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
  });
  if (!response.ok) return alert('Create failed.');
  const created = await response.json();
  ['create-name','create-roles','create-mandates'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('create-rank').value = '101';
  await loadProfiles();
  await openProfile(created.profile.slug);
}

async function saveProfileFields(slug) {
  const cadenceDetails = buildCadenceDetails();
  const category = document.getElementById('field-category').value;
  const roles = document.getElementById('field-roles').value.trim();
  const mandates = document.getElementById('field-mandates').value.trim();
  const payload = {
    name: document.getElementById('field-name').value.trim(),
    category,
    rank: Number(document.getElementById('field-rank').value || 101),
    roles,
    role_title: roles.split('\\n').map(x => x.trim()).filter(Boolean).join('; '),
    mandates,
    mandate: mandates,
    trust: document.getElementById('field-trust').value,
    cadence: document.getElementById('field-cadence').value,
    cadence_details: cadenceDetails,
    last_meeting_date: document.getElementById('field-last-meeting-date').value.trim() || null,
    last_meeting_date_overridden: document.getElementById('field-last-meeting-date').dataset.overridden === 'true',
    last_meeting_notes: document.getElementById('field-last-meeting-notes').value.trim(),
    next_meeting_date: document.getElementById('field-next-meeting-date').value.trim() || null,
    next_meeting_date_overridden: document.getElementById('field-next-meeting-date').dataset.overridden === 'true',
    prep_notes: document.getElementById('field-prep-notes').value.trim(),
    performance_rating: document.getElementById('field-performance-rating').value,
    long_term_notes_todos: document.getElementById('field-long-term-notes-todos').value.trim(),
    strengths: document.getElementById('field-strengths').value.trim(),
    weaknesses: document.getElementById('field-weaknesses').value.trim(),
    profile_type: category === 'External' ? 'external' : 'internal',
    relationship_kind: category === 'External' ? 'other' : 'direct_report',
    last_touch_at: document.getElementById('field-last-meeting-date').value.trim() || null,
    next_checkup_at: document.getElementById('field-next-meeting-date').value.trim() || null,
    checkup_cadence: document.getElementById('field-cadence').value
  };
  const response = await fetch(`/api/profiles/${encodeURIComponent(slug)}`, {
    method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
  });
  if (!response.ok) return alert('Save failed.');
  await loadProfiles();
  await openProfile(slug);
}

async function saveNote(slug) {
  const kind = document.getElementById('note-kind').value;
  const body = document.getElementById('note-body').value.trim();
  if (!body) return alert('Write a note first.');
  const response = await fetch(`/api/profiles/${encodeURIComponent(slug)}/interactions`, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({kind, body, lane_id: 'peopleos-webui'})
  });
  if (!response.ok) return alert('Save failed.');
  await loadProfiles();
  await openProfile(slug);
}

searchEl.addEventListener('input', renderProfiles);
typeEl.addEventListener('change', renderProfiles);
sortEl.addEventListener('change', renderProfiles);
document.getElementById('refresh').addEventListener('click', loadProfiles);
loadProfiles().catch(err => { listEl.innerHTML = `<p class=\"muted\">Failed to load profiles: ${escapeHtml(err.message)}</p>`; });
</script>
</body>
</html>"""


app = create_app()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the standalone PeopleOS web/API service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8891)
    args = parser.parse_args(argv)
    import uvicorn

    uvicorn.run(create_app(), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
