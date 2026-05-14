use chrono::{DateTime, Utc};
use serde::Serialize;
use serde_json::Value;
use uuid::Uuid;

use crate::{
    models::{
        ArtifactInfo, ArtifactsResponse, DownloadInfo, DownloadsResponse, LiveLinkSummary,
        SessionInfo, SessionStatus,
    },
    security::redact_text,
    store::AppStore,
};

#[derive(Debug, Clone, Serialize)]
pub struct InspectorSessionsResponse {
    pub sessions: Vec<InspectorSessionSummary>,
}

#[derive(Debug, Clone, Serialize)]
pub struct InspectorSessionDetail {
    #[serde(flatten)]
    pub summary: InspectorSessionSummary,
    pub artifacts: Vec<InspectorArtifact>,
    pub downloads: Vec<InspectorDownload>,
    pub timeline: Vec<InspectorTimelineEvent>,
}

#[derive(Debug, Clone, Serialize)]
pub struct InspectorSessionSummary {
    pub id: Uuid,
    pub short_id: String,
    pub status: String,
    pub bucket: String,
    pub profile_id: String,
    pub persist_profile: bool,
    pub headless: bool,
    pub pause_reason: Option<String>,
    pub captcha_status: String,
    pub captcha_challenge_type: Option<String>,
    pub credential_fill_status: String,
    pub credential_privacy_guard: bool,
    pub latest_screenshot: Option<InspectorArtifact>,
    pub artifact_count: usize,
    pub download_count: usize,
    pub recent_downloads: Vec<InspectorDownload>,
    pub live_links: Vec<LiveLinkSummary>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize)]
pub struct InspectorArtifact {
    pub name: String,
    pub kind: String,
    pub size_bytes: u64,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize)]
pub struct InspectorDownload {
    pub name: String,
    pub size_bytes: u64,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize)]
pub struct InspectorTimelineEvent {
    pub timestamp: Option<DateTime<Utc>>,
    pub kind: String,
}

pub fn inspector_html() -> String {
    inspector_html_for(None)
}

pub fn inspector_session_html(session_id: Uuid) -> String {
    inspector_html_for(Some(session_id))
}

pub async fn inspector_sessions(store: &AppStore) -> InspectorSessionsResponse {
    let mut sessions = Vec::new();
    for session in store.list_sessions().await {
        sessions.push(build_summary(store, session).await);
    }
    sessions.sort_by_key(|session| std::cmp::Reverse(session.updated_at));
    InspectorSessionsResponse { sessions }
}

pub async fn inspector_session_detail(
    store: &AppStore,
    id: Uuid,
) -> anyhow::Result<InspectorSessionDetail> {
    let session = store
        .get_session(id)
        .await
        .ok_or_else(|| anyhow::anyhow!("session not found"))?;
    let artifacts_response = store.artifacts(id).await.ok();
    let downloads_response = store.list_downloads(id).await.ok();
    let summary = build_summary_from_parts(
        store,
        session,
        artifacts_response.as_ref(),
        downloads_response.as_ref(),
    )
    .await;
    let artifacts = artifacts_response
        .map(|response| sanitized_artifacts(&response))
        .unwrap_or_default();
    let downloads = downloads_response
        .map(|response| sanitized_downloads(&response))
        .unwrap_or_default();
    let timeline = timeline_from_artifacts(&artifacts);
    Ok(InspectorSessionDetail {
        summary,
        artifacts,
        downloads,
        timeline,
    })
}

async fn build_summary(store: &AppStore, session: SessionInfo) -> InspectorSessionSummary {
    let artifacts_response = store.artifacts(session.id).await.ok();
    let downloads_response = store.list_downloads(session.id).await.ok();
    build_summary_from_parts(
        store,
        session,
        artifacts_response.as_ref(),
        downloads_response.as_ref(),
    )
    .await
}

async fn build_summary_from_parts(
    store: &AppStore,
    session: SessionInfo,
    artifacts_response: Option<&ArtifactsResponse>,
    downloads_response: Option<&DownloadsResponse>,
) -> InspectorSessionSummary {
    let artifacts = artifacts_response
        .map(sanitized_artifacts)
        .unwrap_or_default();
    let recent_downloads = downloads_response
        .map(sanitized_downloads)
        .unwrap_or_default();
    let latest_screenshot = artifacts
        .iter()
        .filter(|artifact| artifact.kind == "screenshot")
        .max_by(|left, right| left.created_at.cmp(&right.created_at))
        .cloned();
    let live_links = store
        .live_link_summaries(session.id)
        .await
        .unwrap_or_default();
    let (credential_records, credential_privacy_guard) = store
        .credential_fill_snapshot(session.id)
        .await
        .unwrap_or_default();
    let credential_fill_status = credential_records
        .first()
        .map(|record| serde_name(&record.status))
        .unwrap_or_else(|| "not_requested".to_string());

    InspectorSessionSummary {
        id: session.id,
        short_id: short_id(session.id),
        status: serde_name(&session.status),
        bucket: status_bucket(&session.status).to_string(),
        profile_id: redact_text(&session.profile_id),
        persist_profile: session.persist_profile,
        headless: session.headless,
        pause_reason: session.pause_reason.as_deref().map(redact_text),
        captcha_status: serde_name(&session.captcha_status),
        captcha_challenge_type: session.captcha_challenge_type.as_deref().map(redact_text),
        credential_fill_status,
        credential_privacy_guard,
        latest_screenshot,
        artifact_count: artifacts.len(),
        download_count: recent_downloads.len(),
        recent_downloads,
        live_links,
        created_at: session.created_at,
        updated_at: session.updated_at,
    }
}

fn inspector_html_for(selected: Option<Uuid>) -> String {
    let selected_json = selected
        .map(|id| format!("\"{id}\""))
        .unwrap_or_else(|| "null".to_string());
    format!(
        r#"<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hermes Browser Runtime inspector</title>
  <style>
    :root {{ color-scheme: light dark; --bg:#0b1020; --card:#111a2e; --line:#283856; --fg:#f2f6ff; --muted:#a7b4c9; --accent:#79b8ff; --danger:#ff7b72; }}
    body {{ margin:0; font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif; background:var(--bg); color:var(--fg); }}
    header {{ position:sticky; top:0; z-index:3; padding:14px 18px; background:rgba(11,16,32,.94); border-bottom:1px solid var(--line); }}
    h1 {{ margin:0; font-size:20px; }}
    main {{ display:grid; grid-template-columns:minmax(280px,380px) 1fr; gap:16px; padding:16px; }}
    @media (max-width: 820px) {{ main {{ grid-template-columns:1fr; padding:10px; }} .row {{ flex-direction:column; align-items:flex-start; }} }}
    .card {{ border:1px solid var(--line); background:var(--card); border-radius:14px; padding:14px; margin-bottom:12px; }}
    .session {{ cursor:pointer; }} .session:hover {{ border-color:var(--accent); }}
    .muted {{ color:var(--muted); }} .badge {{ display:inline-block; padding:2px 7px; border-radius:999px; border:1px solid var(--line); margin-right:6px; }}
    .needs_human {{ border-color:#d29922; }} .active {{ border-color:#3fb950; }} .done {{ opacity:.76; }} .error {{ border-color:var(--danger); }}
    .row {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-top:10px; }}
    button {{ border:1px solid var(--line); border-radius:10px; padding:9px 11px; background:#1f2a44; color:var(--fg); }} button.danger {{ border-color:var(--danger); }}
    code {{ word-break:break-all; }} pre {{ white-space:pre-wrap; overflow:auto; }}
  </style>
</head>
<body>
<header>
  <h1>Hermes Browser Runtime inspector</h1>
  <div class="muted">Live human browser sessions, copy-once links, Release browser back to agent / Cancel / deny checkpoint controls, Credential fill status, CAPTCHA / checkpoint state, latest screenshot, artifacts and downloads. Authorization token stays in memory for this tab only; links are not persisted by this page.</div>
</header>
<main>
  <section><h2>Sessions</h2><div id="sessions" class="muted">Loading…</div></section>
  <section><h2>Details</h2><div id="detail" class="muted">Select a session.</div></section>
</main>
<script>
const selectedAtLoad = {selected_json};
let selected = selectedAtLoad;
let inspectorBearerToken = null;
if (location.search) history.replaceState(null, '', location.pathname + location.hash);
const $ = (id) => document.getElementById(id);
function promptForInspectorToken() {{
  const token = window.prompt('Enter HBR_BEARER_TOKEN for this inspector session. Authorization token stays in memory only.');
  if (!token || !token.trim()) throw new Error('Authorization token required');
  inspectorBearerToken = token.trim();
  return inspectorBearerToken;
}}
function apiHeaders(options={{}}) {{
  const headers = {{'content-type':'application/json', ...(options.headers || {{}})}};
  if (inspectorBearerToken && !headers.Authorization && !headers.authorization) {{
    headers.Authorization = `Bearer ${{inspectorBearerToken}}`;
  }}
  return headers;
}}
async function fetchApi(path, options={{}}) {{
  return await fetch(path, {{...options, headers: apiHeaders(options)}});
}}
async function api(path, options={{}}) {{
  let response = await fetchApi(path, options);
  if (response.status === 401 || response.status === 403) {{
    inspectorBearerToken = null;
    promptForInspectorToken();
    response = await fetchApi(path, options);
  }}
  if (!response.ok) throw new Error(await response.text());
  return response.status === 204 ? null : await response.json();
}}
function confirmRiskyInspectorAction(message, id) {{
  return window.confirm(`${{message}}\n\nThis changes browser-runtime session ${{id}}.`);
}}
function esc(value) {{ return String(value ?? '').replace(/[&<>\"]/g, (c) => ({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}}[c])); }}
function renderSession(s) {{
  return `<article class="card session ${{esc(s.bucket)}}" data-id="${{esc(s.id)}}"><strong>${{esc(s.short_id)}}</strong> <span class="badge">${{esc(s.status)}}</span><div class="muted">profile ${{esc(s.profile_id)}} · ${{esc(s.pause_reason || 'no pause reason')}}</div><div class="row"><span>CAPTCHA / checkpoint: ${{esc(s.captcha_status)}}</span><span>Credential fill: ${{esc(s.credential_fill_status)}}</span><span>artifacts ${{s.artifact_count}}</span><span>downloads ${{s.download_count}}</span></div></article>`;
}}
function renderLiveLinks(links, sessionId) {{
  if (!links.length) return '<p class="muted">none</p>';
  return links.map(l => `<div class="row"><code>${{esc(l.id)}}</code><span class="badge">${{esc(l.mode)}}</span><span>revoked=${{l.revoked}}</span><span>expired=${{l.expired}}</span>${{(!l.revoked && !l.expired) ? `<button class="danger" onclick="revokeLiveLink('${{esc(sessionId)}}','${{esc(l.id)}}')">Revoke live link</button>` : ''}}</div>`).join('');
}}
function renderDetail(d) {{
  return `<article class="card"><h3>${{esc(d.short_id)}} <span class="badge">${{esc(d.bucket)}}</span></h3><p>${{esc(d.pause_reason || 'No human pause reason')}}</p><div class="row"><button onclick="releaseSession('${{esc(d.id)}}')">Release</button><button class="danger" onclick="cancelSession('${{esc(d.id)}}')">Cancel</button><button onclick="copyLiveLink('${{esc(d.id)}}','read_only')">Copy read-only live link</button><button onclick="copyLiveLink('${{esc(d.id)}}','interactive')">Copy interactive live link</button></div><h4>Latest screenshot</h4><p>${{d.latest_screenshot ? esc(d.latest_screenshot.name) : 'No screenshot yet'}}</p><h4>CAPTCHA / checkpoint</h4><p>${{esc(d.captcha_status)}} ${{esc(d.captcha_challenge_type || '')}}</p><h4>Credential fill</h4><p>${{esc(d.credential_fill_status)}} · privacy guard ${{d.credential_privacy_guard ? 'active' : 'inactive'}}</p><h4>Artifacts</h4><pre>${{esc(d.artifacts.map(a => `${{a.kind}} ${{a.name}} ${{a.size_bytes}}B`).join('\n') || 'none')}}</pre><h4>Downloads</h4><pre>${{esc(d.downloads.map(f => `${{f.name}} ${{f.size_bytes}}B`).join('\n') || 'none')}}</pre><h4>Live links</h4>${{renderLiveLinks(d.live_links, d.id)}}</article>`;
}}
async function load() {{
  try {{
    const data = await api('/inspector/api/sessions');
    $('sessions').innerHTML = data.sessions.map(renderSession).join('') || '<p>No sessions.</p>';
    document.querySelectorAll('.session').forEach(el => el.onclick = () => show(el.dataset.id));
    if (selected || data.sessions[0]) await show(selected || data.sessions[0].id);
  }} catch (err) {{ $('sessions').textContent = err.message; }}
}}
async function show(id) {{ selected = id; const detail = await api(`/inspector/api/sessions/${{id}}`); $('detail').innerHTML = renderDetail(detail); }}
async function releaseSession(id) {{ if (!confirmRiskyInspectorAction('Release browser back to agent?', id)) return; await api(`/inspector/api/sessions/${{id}}/release`, {{method:'POST'}}); await show(id); }}
async function cancelSession(id) {{ if (!confirmRiskyInspectorAction('Cancel browser session?', id)) return; await api(`/inspector/api/sessions/${{id}}/cancel`, {{method:'POST'}}); selected = null; await load(); }}
async function copyLiveLink(id, mode) {{ const link = await api(`/inspector/api/sessions/${{id}}/live-links`, {{method:'POST', body: JSON.stringify({{mode}})}}); await navigator.clipboard.writeText(link.url); await show(id); }}
async function revokeLiveLink(id, tokenId) {{ if (!confirmRiskyInspectorAction('Revoke live link?', id)) return; await api(`/inspector/api/sessions/${{id}}/live-links/${{tokenId}}`, {{method:'DELETE'}}); await show(id); }}
load();
</script>
</body>
</html>"#,
    )
}

fn sanitized_artifacts(response: &ArtifactsResponse) -> Vec<InspectorArtifact> {
    response.artifacts.iter().map(sanitize_artifact).collect()
}

fn sanitize_artifact(artifact: &ArtifactInfo) -> InspectorArtifact {
    InspectorArtifact {
        name: redact_text(&file_name(&artifact.path)),
        kind: redact_text(&artifact.kind),
        size_bytes: artifact.size_bytes,
        created_at: artifact.created_at,
    }
}

fn sanitized_downloads(response: &DownloadsResponse) -> Vec<InspectorDownload> {
    response.downloads.iter().map(sanitize_download).collect()
}

fn sanitize_download(download: &DownloadInfo) -> InspectorDownload {
    InspectorDownload {
        name: redact_text(&download.name),
        size_bytes: download.size_bytes,
        created_at: download.created_at,
    }
}

fn timeline_from_artifacts(artifacts: &[InspectorArtifact]) -> Vec<InspectorTimelineEvent> {
    artifacts
        .iter()
        .rev()
        .take(10)
        .map(|artifact| InspectorTimelineEvent {
            timestamp: Some(artifact.created_at),
            kind: artifact.kind.clone(),
        })
        .collect()
}

fn status_bucket(status: &SessionStatus) -> &'static str {
    match status {
        SessionStatus::Starting | SessionStatus::Running => "active",
        SessionStatus::PausedForHuman => "needs_human",
        SessionStatus::Closing => "closing",
        SessionStatus::Closed => "done",
        SessionStatus::Failed => "error",
    }
}

fn short_id(id: Uuid) -> String {
    id.to_string().chars().take(8).collect()
}

fn serde_name<T: Serialize>(value: &T) -> String {
    match serde_json::to_value(value).unwrap_or(Value::Null) {
        Value::String(value) => value,
        Value::Null => "null".to_string(),
        other => other.to_string(),
    }
}

fn file_name(path: &str) -> String {
    std::path::Path::new(path)
        .file_name()
        .map(|value| value.to_string_lossy().to_string())
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| "artifact".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::credentials::{CredentialBrokerMode, CredentialFillStatus};
    use crate::models::{
        ArtifactInfo, ArtifactsResponse, CaptchaPolicy, CaptchaStatus, CredentialFillStatusRecord,
        CredentialPrivacyGuardResponse, DownloadInfo, DownloadsResponse, GpuPolicy, LiveLinkMode,
        Viewport, WebRtcIpPolicy,
    };

    fn cdp_browser_ws_fixture() -> String {
        ["ws://127.0.0.1:9", "/devtools/", "browser/", "main"].concat()
    }

    fn artifact(path: &str, kind: &str, created_at: DateTime<Utc>) -> ArtifactInfo {
        ArtifactInfo {
            kind: kind.to_string(),
            path: path.to_string(),
            created_at,
            size_bytes: 12,
        }
    }

    #[test]
    fn html_embeds_selected_session_without_query_tokens() {
        let id = Uuid::new_v4();
        let html = inspector_session_html(id);
        assert!(html.contains(&format!("const selectedAtLoad = \"{id}\";")));
        assert!(html.contains("history.replaceState"));
        assert!(html.contains("revokeLiveLink"));
        assert!(html.contains("Revoke live link"));
        assert!(!html.contains("?token="));
        assert!(inspector_html().contains("const selectedAtLoad = null;"));
    }

    #[test]
    fn sanitizers_redact_names_and_keep_recent_timeline_order() {
        let now = Utc::now();
        let response = ArtifactsResponse {
            session_id: Uuid::new_v4(),
            artifacts: vec![
                artifact("/tmp/screenshot-password-123456.png", "screenshot", now),
                artifact(
                    "/tmp/events.jsonl",
                    "event_log",
                    now + chrono::Duration::seconds(1),
                ),
                artifact("/", "secret-kind", now + chrono::Duration::seconds(2)),
            ],
            downloads_dir: "/tmp/downloads".to_string(),
        };

        let sanitized = sanitized_artifacts(&response);
        assert_eq!(sanitized.len(), 3);
        assert!(sanitized[0].name.contains("[REDACTED]"));
        assert_eq!(sanitized[1].name, "events.jsonl");
        assert_eq!(sanitized[2].name, "artifact");

        let downloads = sanitized_downloads(&DownloadsResponse {
            session_id: response.session_id,
            downloads: vec![DownloadInfo {
                name: "card-token-4111111111111111.txt".to_string(),
                created_at: now,
                size_bytes: 3,
            }],
        });
        assert!(downloads[0].name.contains("[REDACTED]"));

        let timeline = timeline_from_artifacts(&sanitized);
        assert_eq!(timeline[0].kind, sanitized[2].kind);
        assert_eq!(timeline.len(), 3);
    }

    #[test]
    fn status_buckets_and_serde_names_cover_all_terminal_shapes() {
        assert_eq!(status_bucket(&SessionStatus::Starting), "active");
        assert_eq!(status_bucket(&SessionStatus::Running), "active");
        assert_eq!(status_bucket(&SessionStatus::PausedForHuman), "needs_human");
        assert_eq!(status_bucket(&SessionStatus::Closing), "closing");
        assert_eq!(status_bucket(&SessionStatus::Closed), "done");
        assert_eq!(status_bucket(&SessionStatus::Failed), "error");
        assert_eq!(serde_name(&Value::Null), "null");
        assert_eq!(
            serde_name(&serde_json::json!({"kind":"object"})),
            "{\"kind\":\"object\"}"
        );
    }

    #[tokio::test]
    async fn summary_builder_redacts_sensitive_session_metadata() {
        let now = Utc::now();
        let id = Uuid::new_v4();
        let cdp_ws_url = cdp_browser_ws_fixture();
        let session = SessionInfo {
            id,
            status: SessionStatus::PausedForHuman,
            cdp_ws_url: Some(cdp_ws_url.clone()),
            takeover_url: None,
            profile_id: "profile-password-123456".to_string(),
            headless: false,
            persist_profile: true,
            viewport: Viewport::default(),
            webrtc_ip_policy: WebRtcIpPolicy::default(),
            gpu_policy: GpuPolicy::default(),
            captcha_policy: CaptchaPolicy::HumanOnly,
            captcha_status: CaptchaStatus::HumanRequired,
            captcha_challenge_type: Some("otp-123456".to_string()),
            captcha_solver_status: None,
            pause_reason: Some("manual login with password 123456".to_string()),
            created_at: now,
            updated_at: now,
        };
        let artifacts = ArtifactsResponse {
            session_id: id,
            artifacts: vec![artifact("/tmp/latest.png", "screenshot", now)],
            downloads_dir: "/tmp/downloads".to_string(),
        };
        let downloads = DownloadsResponse {
            session_id: id,
            downloads: Vec::new(),
        };
        let tmp = tempfile::tempdir().unwrap();
        let store = crate::store::AppStore::new(
            crate::test_support::test_config(tmp.path().to_path_buf(), None),
            std::sync::Arc::new(crate::test_support::MockBackend::new(
                "http://127.0.0.1:9".to_string(),
                cdp_ws_url.clone(),
            )),
        )
        .await
        .unwrap();
        let summary =
            build_summary_from_parts(&store, session, Some(&artifacts), Some(&downloads)).await;

        let summary_json = serde_json::to_string(&summary).unwrap();
        assert!(!summary_json.contains(&cdp_ws_url));

        assert_eq!(summary.id, id);
        assert_eq!(summary.bucket, "needs_human");
        assert!(summary.profile_id.contains("[REDACTED]"));
        assert!(summary.pause_reason.unwrap().contains("[REDACTED]"));
        assert_eq!(summary.credential_fill_status, "not_requested");
        assert!(!summary.credential_privacy_guard);
        assert_eq!(summary.latest_screenshot.unwrap().name, "latest.png");
    }

    #[test]
    fn credential_status_record_terminal_helper_is_serialized_for_inspector() {
        let record = CredentialFillStatusRecord {
            request_id: Uuid::new_v4(),
            session_id: Uuid::new_v4(),
            alias: "demo".to_string(),
            observed_origin: "https://example.test".to_string(),
            status: CredentialFillStatus::PrivacyGuardActive,
            broker: CredentialBrokerMode::Disabled,
            audit_id: Uuid::new_v4(),
            privacy_guard_active: true,
            created_at: Utc::now(),
            updated_at: Utc::now(),
            redacted_message: None,
        };
        let guard = CredentialPrivacyGuardResponse {
            session_id: record.session_id,
            privacy_guard_active: true,
        };
        let link = LiveLinkSummary {
            id: Uuid::new_v4(),
            mode: LiveLinkMode::Interactive,
            created_at: Utc::now(),
            expires_at: Utc::now() + chrono::Duration::seconds(30),
            revoked: false,
            expired: false,
        };
        assert!(!record.is_terminal());
        assert_eq!(serde_name(&record.status), "privacy_guard_active");
        assert_eq!(serde_name(&guard.privacy_guard_active), "true");
        assert_eq!(serde_name(&link.mode), "interactive");
    }
}
