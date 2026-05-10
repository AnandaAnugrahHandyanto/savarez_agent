use std::sync::Arc;

use axum::{
    Json, Router,
    body::Body,
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode, header},
    response::{Html, IntoResponse, Response},
    routing::{delete, get, post},
};
use serde::Deserialize;
use uuid::Uuid;

use crate::{
    models::{
        ClickRequest, CreateProfileRequest, CreateSessionRequest, ErrorResponse,
        PauseForHumanRequest, ScrollRequest, TypeRequest,
    },
    store::AppStore,
};

pub fn router(store: Arc<AppStore>) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/sessions", post(create_session).get(list_sessions))
        .route("/sessions/:id", get(get_session).delete(delete_session))
        .route("/sessions/:id/pause_for_human", post(pause_for_human))
        .route("/sessions/:id/release", post(release_session))
        .route("/sessions/:id/screenshot", get(session_screenshot))
        .route("/sessions/:id/artifacts", get(session_artifacts))
        .route("/profiles", post(create_profile).get(list_profiles))
        .route("/profiles/:id", delete(delete_profile))
        .route("/takeover/:id", get(takeover_page))
        .route("/takeover/:id/screenshot", get(takeover_screenshot))
        .route("/takeover/:id/release", post(takeover_release))
        .route("/takeover/:id/click", post(takeover_click))
        .route("/takeover/:id/type", post(takeover_type))
        .route("/takeover/:id/scroll", post(takeover_scroll))
        .with_state(store)
}

async fn health() -> Json<serde_json::Value> {
    Json(serde_json::json!({"ok": true}))
}

async fn create_session(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Json(req): Json<CreateSessionRequest>,
) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    match store.create_session(req).await {
        Ok(info) => Json(crate::models::CreateSessionResponse {
            id: info.id,
            status: info.status,
            cdp_ws_url: info.cdp_ws_url.unwrap_or_default(),
            takeover_url: info.takeover_url.unwrap_or_default(),
            profile_id: info.profile_id,
        })
        .into_response(),
        Err(err) => api_error(err),
    }
}

async fn list_sessions(State(store): State<Arc<AppStore>>, headers: HeaderMap) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    Json(store.list_sessions().await).into_response()
}

async fn get_session(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    match store.get_session(id).await {
        Some(info) => Json(info).into_response(),
        None => not_found("session not found"),
    }
}

async fn delete_session(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    match store.delete_session(id).await {
        Ok(info) => Json(info).into_response(),
        Err(err) => api_error(err),
    }
}

async fn pause_for_human(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
    Json(req): Json<PauseForHumanRequest>,
) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    match store.pause_for_human(id, req.reason).await {
        Ok(info) => Json(info).into_response(),
        Err(err) => api_error(err),
    }
}

async fn release_session(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    match store.release(id).await {
        Ok(info) => Json(info).into_response(),
        Err(err) => api_error(err),
    }
}

async fn session_screenshot(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    screenshot_response(&store, id).await
}

async fn session_artifacts(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    match store.artifacts(id).await {
        Ok(artifacts) => Json(artifacts).into_response(),
        Err(err) => api_error(err),
    }
}

async fn create_profile(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Json(req): Json<CreateProfileRequest>,
) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    match store.create_profile(req.id).await {
        Ok(profile) => Json(profile).into_response(),
        Err(err) => api_error(err),
    }
}

async fn list_profiles(State(store): State<Arc<AppStore>>, headers: HeaderMap) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    match store.list_profiles().await {
        Ok(profiles) => Json(profiles).into_response(),
        Err(err) => api_error(err),
    }
}

async fn delete_profile(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<String>,
) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    match store.delete_profile(&id).await {
        Ok(()) => StatusCode::NO_CONTENT.into_response(),
        Err(err) => api_error(err),
    }
}

#[derive(Deserialize)]
struct TakeoverQuery {
    token: String,
}

async fn takeover_page(
    State(store): State<Arc<AppStore>>,
    Path(id): Path<Uuid>,
    Query(query): Query<TakeoverQuery>,
) -> Response {
    if !store.validate_takeover_token(id, &query.token).await {
        return forbidden();
    }
    Html(takeover_html(id, &query.token)).into_response()
}

async fn takeover_screenshot(
    State(store): State<Arc<AppStore>>,
    Path(id): Path<Uuid>,
    Query(query): Query<TakeoverQuery>,
) -> Response {
    if !store.validate_takeover_token(id, &query.token).await {
        return forbidden();
    }
    screenshot_response(&store, id).await
}

async fn takeover_release(
    State(store): State<Arc<AppStore>>,
    Path(id): Path<Uuid>,
    Query(query): Query<TakeoverQuery>,
) -> Response {
    if !store.validate_takeover_token(id, &query.token).await {
        return forbidden();
    }
    match store.release(id).await {
        Ok(info) => Json(info).into_response(),
        Err(err) => api_error(err),
    }
}

async fn takeover_click(
    State(store): State<Arc<AppStore>>,
    Path(id): Path<Uuid>,
    Query(query): Query<TakeoverQuery>,
    Json(req): Json<ClickRequest>,
) -> Response {
    if !store.validate_takeover_token(id, &query.token).await {
        return forbidden();
    }
    match store.input_click(id, req.x, req.y).await {
        Ok(()) => Json(serde_json::json!({"ok": true})).into_response(),
        Err(err) => api_error(err),
    }
}

async fn takeover_type(
    State(store): State<Arc<AppStore>>,
    Path(id): Path<Uuid>,
    Query(query): Query<TakeoverQuery>,
    Json(req): Json<TypeRequest>,
) -> Response {
    if !store.validate_takeover_token(id, &query.token).await {
        return forbidden();
    }
    match store.input_type(id, &req.text).await {
        Ok(()) => Json(serde_json::json!({"ok": true})).into_response(),
        Err(err) => api_error(err),
    }
}

async fn takeover_scroll(
    State(store): State<Arc<AppStore>>,
    Path(id): Path<Uuid>,
    Query(query): Query<TakeoverQuery>,
    Json(req): Json<ScrollRequest>,
) -> Response {
    if !store.validate_takeover_token(id, &query.token).await {
        return forbidden();
    }
    match store
        .input_scroll(id, req.delta_x.unwrap_or(0.0), req.delta_y.unwrap_or(500.0))
        .await
    {
        Ok(()) => Json(serde_json::json!({"ok": true})).into_response(),
        Err(err) => api_error(err),
    }
}

async fn screenshot_response(store: &AppStore, id: Uuid) -> Response {
    match store.screenshot(id).await {
        Ok(png) => Response::builder()
            .status(StatusCode::OK)
            .header(header::CONTENT_TYPE, "image/png")
            .body(Body::from(png))
            .unwrap(),
        Err(err) => api_error(err),
    }
}

fn auth_response(store: &AppStore, headers: &HeaderMap) -> Option<Response> {
    auth(store, headers).err().map(|status| {
        let msg = if status == StatusCode::UNAUTHORIZED {
            "unauthorized"
        } else {
            "forbidden"
        };
        (
            status,
            Json(ErrorResponse {
                error: msg.to_string(),
            }),
        )
            .into_response()
    })
}

fn auth(store: &AppStore, headers: &HeaderMap) -> Result<(), StatusCode> {
    let Some(expected) = &store.config.bearer_token else {
        return Ok(());
    };
    let Some(header_value) = headers
        .get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
    else {
        return Err(StatusCode::UNAUTHORIZED);
    };
    let expected_header = format!("Bearer {expected}");
    if constant_time_eq(header_value.as_bytes(), expected_header.as_bytes()) {
        Ok(())
    } else {
        Err(StatusCode::FORBIDDEN)
    }
}

fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    a.iter()
        .zip(b.iter())
        .fold(0u8, |acc, (x, y)| acc | (x ^ y))
        == 0
}

fn api_error(err: anyhow::Error) -> Response {
    let message = err.to_string();
    let status = if message.contains("not found") {
        StatusCode::NOT_FOUND
    } else if message.contains("locked") || message.contains("invalid") {
        StatusCode::CONFLICT
    } else {
        StatusCode::INTERNAL_SERVER_ERROR
    };
    (status, Json(ErrorResponse { error: message })).into_response()
}

fn not_found(message: &str) -> Response {
    (
        StatusCode::NOT_FOUND,
        Json(ErrorResponse {
            error: message.to_string(),
        }),
    )
        .into_response()
}

fn forbidden() -> Response {
    (
        StatusCode::FORBIDDEN,
        Json(ErrorResponse {
            error: "invalid or expired takeover token".to_string(),
        }),
    )
        .into_response()
}

fn takeover_html(id: Uuid, token: &str) -> String {
    format!(
        r#"<!doctype html>
<html><head><meta charset="utf-8"><title>Hermes takeover {id}</title>
<style>body{{font-family:system-ui;background:#0b0f19;color:#e5e7eb;margin:24px}}button,input{{font-size:16px;padding:8px;margin:4px}}#shot{{max-width:100%;border:1px solid #374151;background:#111827}}.bar{{position:sticky;top:0;background:#0b0f19;padding:8px}}</style></head>
<body><div class="bar"><b>Hermes Browser Runtime takeover</b> <button id="release">Release to agent</button><input id="text" placeholder="type fallback"><button id="typebtn">Type</button><button id="scroll">Scroll</button><span id="status"></span></div>
<p>Click the screenshot for CDP Input mouse fallback. Use local headful Chrome window if available for complex steps.</p><img id="shot" alt="live screenshot">
<script>
const token = {token:?}; const id = {id:?}; const status = document.getElementById('status'); const img = document.getElementById('shot');
async function refresh() {{ img.src = `/takeover/${{id}}/screenshot?token=${{token}}&t=${{Date.now()}}`; }}
img.addEventListener('click', async (e) => {{ const r = img.getBoundingClientRect(); const x = (e.clientX-r.left) * (img.naturalWidth/r.width); const y = (e.clientY-r.top) * (img.naturalHeight/r.height); await fetch(`/takeover/${{id}}/click?token=${{token}}`, {{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{x,y}})}}); }});
document.getElementById('typebtn').onclick = async () => {{ await fetch(`/takeover/${{id}}/type?token=${{token}}`, {{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{text:document.getElementById('text').value}})}}); }};
document.getElementById('scroll').onclick = async () => {{ await fetch(`/takeover/${{id}}/scroll?token=${{token}}`, {{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{delta_y:500}})}}); }};
document.getElementById('release').onclick = async () => {{ const r = await fetch(`/takeover/${{id}}/release?token=${{token}}`, {{method:'POST'}}); status.textContent = r.ok ? 'released' : 'release failed'; }};
setInterval(refresh, 1200); refresh();
</script></body></html>"#
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn constant_time_auth_checks_value() {
        assert!(constant_time_eq(b"Bearer abc", b"Bearer abc"));
        assert!(!constant_time_eq(b"Bearer abc", b"Bearer xyz"));
        assert!(!constant_time_eq(b"Bearer abc", b"Bearer abcd"));
    }
}
