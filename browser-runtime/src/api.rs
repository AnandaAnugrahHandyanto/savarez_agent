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
        CaptchaReportRequest, CaptchaResolveRequest, CaptchaScanRequest, CaptchaSolveRequest,
        CaptchaSolveResponse, CleanupArtifactsRequest, ClickRequest, CreateLiveLinkRequest,
        CreateProfileRequest, CreateSessionRequest, CredentialDecisionRequest,
        CredentialFillStartRequest, ErrorResponse, KeyRequest, LiveLinkMode, PauseForHumanRequest,
        ScrollRequest, TypeRequest,
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
        .route("/sessions/:id/captcha/report", post(report_captcha))
        .route("/sessions/:id/captcha/resolve", post(resolve_captcha))
        .route("/sessions/:id/captcha/scan", post(scan_captcha))
        .route("/sessions/:id/captcha/solve", post(solve_captcha))
        .route("/sessions/:id/captcha/status", get(captcha_status))
        .route("/sessions/:id/wait", get(wait_session))
        .route(
            "/sessions/:id/credentials/fill",
            post(request_credential_fill),
        )
        .route(
            "/sessions/:id/credentials/fill/:request_id",
            get(credential_fill_status),
        )
        .route(
            "/sessions/:id/credentials/fill/:request_id/approve",
            post(approve_credential_fill),
        )
        .route(
            "/sessions/:id/credentials/fill/:request_id/deny",
            post(deny_credential_fill),
        )
        .route(
            "/sessions/:id/credentials/privacy-guard/clear",
            post(clear_credential_privacy_guard),
        )
        .route(
            "/sessions/:id/credentials/privacy_guard/clear",
            post(clear_credential_privacy_guard),
        )
        .route("/sessions/:id/screenshot", get(session_screenshot))
        .route("/sessions/:id/artifacts", get(session_artifacts))
        .route("/sessions/:id/downloads", get(session_downloads))
        .route("/sessions/:id/download", get(session_download))
        .route("/artifacts/cleanup", post(cleanup_artifacts))
        .route("/profiles", post(create_profile).get(list_profiles))
        .route("/profiles/:id", delete(delete_profile))
        .route("/inspector", get(inspector_index))
        .route("/inspector/:id", get(inspector_detail_page))
        .route("/inspector/api/sessions", get(inspector_sessions_api))
        .route(
            "/inspector/api/sessions/:id",
            get(inspector_session_detail_api),
        )
        .route(
            "/inspector/api/sessions/:id/live-links",
            post(inspector_create_live_link),
        )
        .route(
            "/inspector/api/sessions/:id/live-links/:link_id",
            delete(inspector_revoke_live_link),
        )
        .route(
            "/inspector/api/sessions/:id/release",
            post(inspector_release),
        )
        .route("/inspector/api/sessions/:id/cancel", post(inspector_cancel))
        .route("/takeover/:id", get(takeover_page))
        .route("/takeover/:id/screenshot", get(takeover_screenshot))
        .route("/takeover/:id/release", post(takeover_release))
        .route("/takeover/:id/click", post(takeover_click))
        .route("/takeover/:id/type", post(takeover_type))
        .route("/takeover/:id/key", post(takeover_key))
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
            takeover_url: info.takeover_url,
            profile_id: info.profile_id,
            webrtc_ip_policy: info.webrtc_ip_policy,
            gpu_policy: info.gpu_policy,
            captcha_policy: info.captcha_policy,
            captcha_status: info.captcha_status,
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

async fn report_captcha(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
    Json(req): Json<CaptchaReportRequest>,
) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    match store
        .report_captcha(id, req.state, req.challenge_type, req.reason)
        .await
    {
        Ok(info) => Json(info).into_response(),
        Err(err) => api_error(err),
    }
}

async fn resolve_captcha(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
    Json(req): Json<CaptchaResolveRequest>,
) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    match store.resolve_captcha(id, req.outcome, req.note).await {
        Ok(info) => Json(info).into_response(),
        Err(err) => api_error(err),
    }
}

async fn scan_captcha(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
    body: Option<Json<CaptchaScanRequest>>,
) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    let req = body.map(|Json(payload)| payload).unwrap_or_default();
    match store.scan_captcha(id, req).await {
        Ok(response) => Json(response).into_response(),
        Err(err) => api_error(err),
    }
}

async fn solve_captcha(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
    body: Option<Json<CaptchaSolveRequest>>,
) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    let req = body.map(|Json(payload)| payload).unwrap_or_default();
    let result = if req.dry_run {
        store
            .captcha_status(id)
            .await
            .map(|status| CaptchaSolveResponse::from_status(status, false))
    } else {
        store
            .request_captcha_solve(
                id,
                req.challenge_type,
                req.reason,
                req.site_key,
                req.page_url,
            )
            .await
            .map(|result| {
                CaptchaSolveResponse::from_session(result.info, result.provider_call_performed)
            })
    };
    match result {
        Ok(response) => Json(response).into_response(),
        Err(err) => api_error(err),
    }
}

async fn captcha_status(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    match store.captcha_status(id).await {
        Ok(response) => Json(response).into_response(),
        Err(err) => api_error(err),
    }
}

#[derive(Deserialize)]
struct WaitSessionQuery {
    timeout_ms: Option<u64>,
}

async fn wait_session(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
    Query(query): Query<WaitSessionQuery>,
) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    match store
        .wait_session(
            id,
            std::time::Duration::from_millis(query.timeout_ms.unwrap_or(30_000)),
        )
        .await
    {
        Ok(wait) => Json(wait).into_response(),
        Err(err) => api_error(err),
    }
}

async fn request_credential_fill(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
    Json(req): Json<CredentialFillStartRequest>,
) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    match store.request_credential_fill(id, req).await {
        Ok(record) => Json(record).into_response(),
        Err(err) => api_error(err),
    }
}

async fn credential_fill_status(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path((id, request_id)): Path<(Uuid, Uuid)>,
) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    match store.credential_fill_status(id, request_id).await {
        Ok(record) => Json(record).into_response(),
        Err(err) => api_error(err),
    }
}

async fn approve_credential_fill(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path((id, request_id)): Path<(Uuid, Uuid)>,
    body: Option<Json<CredentialDecisionRequest>>,
) -> Response {
    if let Some(response) = operator_auth_response(&store, &headers) {
        return response;
    }
    let note = body.and_then(|Json(payload)| payload.operator_note());
    match store.approve_credential_fill(id, request_id, note).await {
        Ok(record) => Json(record).into_response(),
        Err(err) => api_error(err),
    }
}

async fn deny_credential_fill(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path((id, request_id)): Path<(Uuid, Uuid)>,
    body: Option<Json<CredentialDecisionRequest>>,
) -> Response {
    if let Some(response) = operator_auth_response(&store, &headers) {
        return response;
    }
    let note = body.and_then(|Json(payload)| payload.operator_note());
    match store.deny_credential_fill(id, request_id, note).await {
        Ok(record) => Json(record).into_response(),
        Err(err) => api_error(err),
    }
}

async fn clear_credential_privacy_guard(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
) -> Response {
    if let Some(response) = operator_auth_response(&store, &headers) {
        return response;
    }
    match store.clear_credential_privacy_guard(id).await {
        Ok(response) => Json(response).into_response(),
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

#[derive(Deserialize)]
struct DownloadQuery {
    name: String,
}

async fn session_downloads(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    match store.list_downloads(id).await {
        Ok(downloads) => Json(downloads).into_response(),
        Err(err) => api_error(err),
    }
}

async fn session_download(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
    Query(query): Query<DownloadQuery>,
) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    match store.read_download(id, &query.name).await {
        Ok((name, bytes)) => {
            let content_disposition = format!("attachment; filename=\"{name}\"");
            Response::builder()
                .header(header::CONTENT_TYPE, "application/octet-stream")
                .header(header::CONTENT_DISPOSITION, content_disposition)
                .body(bytes.into())
                .expect("download response should build")
        }
        Err(err) => api_error(err),
    }
}

async fn cleanup_artifacts(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Json(req): Json<CleanupArtifactsRequest>,
) -> Response {
    if let Some(response) = auth_response(&store, &headers) {
        return response;
    }
    let older_than = req.older_than_secs.map(std::time::Duration::from_secs);
    match store.cleanup_artifacts(older_than, req.dry_run).await {
        Ok(result) => Json(result).into_response(),
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

async fn inspector_index(State(store): State<Arc<AppStore>>, headers: HeaderMap) -> Response {
    if let Some(response) = inspector_auth_response(&store, &headers) {
        return response;
    }
    Html(crate::inspector::inspector_html()).into_response()
}

async fn inspector_detail_page(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
) -> Response {
    if let Some(response) = inspector_auth_response(&store, &headers) {
        return response;
    }
    Html(crate::inspector::inspector_session_html(id)).into_response()
}

async fn inspector_sessions_api(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
) -> Response {
    if let Some(response) = inspector_auth_response(&store, &headers) {
        return response;
    }
    Json(crate::inspector::inspector_sessions(&store).await).into_response()
}

async fn inspector_session_detail_api(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
) -> Response {
    if let Some(response) = inspector_auth_response(&store, &headers) {
        return response;
    }
    match crate::inspector::inspector_session_detail(&store, id).await {
        Ok(detail) => Json(detail).into_response(),
        Err(err) if err.to_string().contains("not found") => not_found("session not found"),
        Err(err) => api_error(err),
    }
}

async fn inspector_create_live_link(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
    Json(req): Json<CreateLiveLinkRequest>,
) -> Response {
    if let Some(response) = inspector_auth_response(&store, &headers) {
        return response;
    }
    match store.create_live_link(id, req.mode).await {
        Ok(link) => Json(link).into_response(),
        Err(err) => api_error(err),
    }
}

async fn inspector_revoke_live_link(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path((id, link_id)): Path<(Uuid, Uuid)>,
) -> Response {
    if let Some(response) = inspector_auth_response(&store, &headers) {
        return response;
    }
    match store.revoke_live_link(id, link_id).await {
        Ok(summary) => Json(summary).into_response(),
        Err(err) => api_error(err),
    }
}

async fn inspector_release(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
) -> Response {
    if let Some(response) = inspector_auth_response(&store, &headers) {
        return response;
    }
    match store.release(id).await {
        Ok(info) => Json(info).into_response(),
        Err(err) => api_error(err),
    }
}

async fn inspector_cancel(
    State(store): State<Arc<AppStore>>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
) -> Response {
    if let Some(response) = inspector_auth_response(&store, &headers) {
        return response;
    }
    match store.delete_session(id).await {
        Ok(info) => Json(info).into_response(),
        Err(err) => api_error(err),
    }
}

async fn takeover_page(
    State(store): State<Arc<AppStore>>,
    Path(id): Path<Uuid>,
    Query(query): Query<TakeoverQuery>,
) -> Response {
    if store.takeover_access_mode(id, &query.token).await.is_none() {
        return forbidden();
    }
    Html(takeover_html(id, &query.token)).into_response()
}

async fn takeover_screenshot(
    State(store): State<Arc<AppStore>>,
    Path(id): Path<Uuid>,
    Query(query): Query<TakeoverQuery>,
) -> Response {
    if store.takeover_access_mode(id, &query.token).await.is_none() {
        return forbidden();
    }
    screenshot_response(&store, id).await
}

async fn takeover_release(
    State(store): State<Arc<AppStore>>,
    Path(id): Path<Uuid>,
    Query(query): Query<TakeoverQuery>,
) -> Response {
    if let Some(response) = require_interactive_takeover(&store, id, &query.token).await {
        return response;
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
    if let Some(response) = require_interactive_takeover(&store, id, &query.token).await {
        return response;
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
    if let Some(response) = require_interactive_takeover(&store, id, &query.token).await {
        return response;
    }
    match store.input_type(id, &req.text).await {
        Ok(()) => Json(serde_json::json!({"ok": true})).into_response(),
        Err(err) => api_error(err),
    }
}

async fn takeover_key(
    State(store): State<Arc<AppStore>>,
    Path(id): Path<Uuid>,
    Query(query): Query<TakeoverQuery>,
    Json(req): Json<KeyRequest>,
) -> Response {
    if let Some(response) = require_interactive_takeover(&store, id, &query.token).await {
        return response;
    }
    match store.input_key(id, &req.key).await {
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
    if let Some(response) = require_interactive_takeover(&store, id, &query.token).await {
        return response;
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
        Err(err) if err.to_string().contains("credential privacy guard active") => {
            credential_privacy_guard_image()
        }
        Err(err) => api_error(err),
    }
}

fn credential_privacy_guard_image() -> Response {
    const SVG: &str = r##"<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540" role="img" aria-label="Credential privacy guard active">
  <rect width="960" height="540" fill="#0f172a"/>
  <rect x="110" y="150" width="740" height="240" rx="24" fill="#111827" stroke="#f59e0b" stroke-width="4"/>
  <text x="480" y="235" fill="#fbbf24" font-family="system-ui, sans-serif" font-size="34" font-weight="700" text-anchor="middle">Credential privacy guard active</text>
  <text x="480" y="295" fill="#e5e7eb" font-family="system-ui, sans-serif" font-size="22" text-anchor="middle">Screenshot/live view is hidden while sensitive credential fields are protected.</text>
  <text x="480" y="335" fill="#cbd5e1" font-family="system-ui, sans-serif" font-size="18" text-anchor="middle">Clear the guard after human review to resume visual access.</text>
</svg>"##;
    Response::builder()
        .status(StatusCode::OK)
        .header(header::CONTENT_TYPE, "image/svg+xml; charset=utf-8")
        .header(header::CACHE_CONTROL, "no-store")
        .body(Body::from(SVG))
        .unwrap()
}

async fn require_interactive_takeover(store: &AppStore, id: Uuid, token: &str) -> Option<Response> {
    match store.takeover_access_mode(id, token).await {
        Some(LiveLinkMode::Interactive) => None,
        Some(LiveLinkMode::ReadOnly) => Some(
            (
                StatusCode::FORBIDDEN,
                Json(ErrorResponse {
                    error: "read-only live link cannot mutate the browser session".to_string(),
                }),
            )
                .into_response(),
        ),
        None => Some(forbidden()),
    }
}

fn inspector_auth_response(store: &AppStore, headers: &HeaderMap) -> Option<Response> {
    if let Some(response) = auth_response(store, headers) {
        return Some(response);
    }
    inspector_loopback_guard_response(store)
}

fn inspector_loopback_guard_response(store: &AppStore) -> Option<Response> {
    if !store.config.bind.ip().is_loopback() && !nonlocal_inspector_approved() {
        return Some(
            (
                StatusCode::FORBIDDEN,
                Json(ErrorResponse {
                    error:
                        "inspector requires loopback bind or HBR_ALLOW_NONLOCAL_INSPECTOR=true approval"
                            .to_string(),
                }),
            )
                .into_response(),
        );
    }
    None
}

fn nonlocal_inspector_approved() -> bool {
    std::env::var("HBR_ALLOW_NONLOCAL_INSPECTOR")
        .ok()
        .is_some_and(|value| nonlocal_inspector_approval_value(&value))
}

fn nonlocal_inspector_approval_value(value: &str) -> bool {
    matches!(
        value.trim().to_ascii_lowercase().as_str(),
        "1" | "true" | "yes" | "on"
    )
}

fn auth_response(store: &AppStore, headers: &HeaderMap) -> Option<Response> {
    auth(store, headers).err().map(auth_error_response)
}

fn operator_auth_response(store: &AppStore, headers: &HeaderMap) -> Option<Response> {
    operator_auth(store, headers).err().map(auth_error_response)
}

fn auth_error_response(status: StatusCode) -> Response {
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
}

fn auth(store: &AppStore, headers: &HeaderMap) -> Result<(), StatusCode> {
    let Some(expected) = &store.config.bearer_token else {
        return Ok(());
    };
    require_bearer_token(expected, headers)
}

fn operator_auth(store: &AppStore, headers: &HeaderMap) -> Result<(), StatusCode> {
    let Some(expected) = &store.config.operator_token else {
        return Err(StatusCode::UNAUTHORIZED);
    };
    if store.config.bearer_token.as_deref() == Some(expected.as_str()) {
        return Err(StatusCode::FORBIDDEN);
    }
    require_bearer_token(expected, headers)
}

fn require_bearer_token(expected: &str, headers: &HeaderMap) -> Result<(), StatusCode> {
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
    } else if message == "invalid download name" {
        StatusCode::BAD_REQUEST
    } else if message.contains("locked")
        || message.contains("invalid")
        || message.contains("credential privacy guard active")
        || message.contains("credential fill not approved")
        || message.contains("captcha policy disabled")
        || message.contains("cannot downgrade active human CAPTCHA checkpoint")
        || message.contains("captcha resolution requires")
        || message.contains("credential fill pending")
        || message.contains("paused human takeover")
    {
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
    let id = id.to_string();
    format!(
        r#"<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Hermes takeover {id}</title>
<style>
:root{{color-scheme:dark}}
*{{box-sizing:border-box}}
body{{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0b0f19;color:#e5e7eb;margin:0;line-height:1.5}}
button,textarea{{font-size:16px;padding:10px 12px;margin:4px;border-radius:10px;border:1px solid #374151;background:#111827;color:#e5e7eb}}
button{{min-height:42px;touch-action:manipulation}}
textarea{{width:min(100%,560px);min-height:100px;display:block}}
.header{{position:sticky;top:0;z-index:10;background:rgba(11,15,25,.96);backdrop-filter:blur(8px);border-bottom:1px solid #1f2937;padding:10px 12px}}
.title-row{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between}}
.toolbar{{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:8px}}
#status{{display:inline-block;color:#93c5fd;min-height:1.4em}}
#zoom-label{{color:#cbd5e1;font-size:14px;min-width:44px}}
#viewer{{height:min(72vh,820px);overflow:auto;overscroll-behavior:contain;-webkit-overflow-scrolling:touch;background:#030712;border-top:1px solid #1f2937;border-bottom:1px solid #1f2937;padding:8px;touch-action:pan-x pan-y}}
#shot{{width:100%;max-width:none;border:1px solid #374151;background:#111827;border-radius:12px;display:block;transform-origin:top left;cursor:crosshair}}
#keyboard-proxy{{position:fixed;left:0;bottom:0;width:1px;height:1px;opacity:.01;border:0;padding:0;margin:0;background:transparent;color:transparent;caret-color:transparent;resize:none;pointer-events:none;outline:none}}
.panel{{background:#111827;border:1px solid #1f2937;border-radius:12px;padding:12px;margin:12px}}
.helper-grid{{display:flex;flex-wrap:wrap;gap:8px}}
.note{{color:#cbd5e1;font-size:14px}}
.mobile-hint{{display:none}}
@media (max-width: 700px) {{
  button,textarea{{font-size:17px}}
  .header{{padding:8px}}
  #viewer{{height:68vh;padding:6px}}
  .panel{{margin:10px 8px}}
  .mobile-hint{{display:block}}
}}
</style>
</head>
<body>
<div class="header">
  <div class="title-row">
    <b>Hermes Browser Runtime takeover</b>
    <button id="release">Release browser back to agent</button>
  </div>
  <div class="toolbar" aria-label="Screenshot zoom controls">
    <button id="refresh">Refresh screenshot</button>
    <button data-zoom="fit">Fit</button>
    <button data-zoom="1.5">1.5×</button>
    <button data-zoom="2">2×</button>
    <button data-zoom="3">3×</button>
    <button id="top-left">Top-left form/captcha</button>
    <span id="zoom-label">fit</span>
    <span id="status"></span>
  </div>
</div>

<div id="viewer" aria-label="Scrollable live screenshot viewer">
  <img id="shot" alt="live screenshot">
</div>
<textarea id="keyboard-proxy" aria-label="Remote keyboard input proxy" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" tabindex="-1"></textarea>

<div class="panel">
  <p>Click/tap the screenshot for CDP mouse fallback. Use Fit for overview, zoom in and pan for phone-readable form/captcha areas, or press Top-left form/captcha to jump to the common challenge location.</p>
  <p class="mobile-hint note">Phone mode starts zoomed into the top-left once the first screenshot loads; use Fit if you need the full page overview.</p>
  <p class="note">Typed text is sent directly to CDP and never stored in runtime logs. Keep takeover URLs private and release control when done.</p>
</div>

<div class="panel">
  <label for="text"><b>Type fallback</b></label>
  <textarea id="text" placeholder="Paste text for the currently focused field"></textarea>
  <button id="typebtn">Send typed text</button>
  <button id="scroll">Scroll down</button>
</div>

<div class="panel">
  <b>Keyboard helpers</b>
  <div class="helper-grid">
    <button data-key="Tab">Tab</button>
    <button data-key="Enter">Enter</button>
    <button data-key="Escape">Escape</button>
    <button data-key="Backspace">Backspace</button>
    <button data-key="ArrowUp">↑</button>
    <button data-key="ArrowDown">↓</button>
    <button data-key="ArrowLeft">←</button>
    <button data-key="ArrowRight">→</button>
    <button data-key="PageUp">Page Up</button>
    <button data-key="PageDown">Page Down</button>
    <button data-key="Home">Home</button>
    <button data-key="End">End</button>
    <button data-key="Delete">Delete</button>
    <button data-key="Space">Space</button>
  </div>
</div>

<script>
const token = {token:?};
const id = {id:?};
const status = document.getElementById('status');
const img = document.getElementById('shot');
const viewer = document.getElementById('viewer');
const textArea = document.getElementById('text');
const keyboardProxy = document.getElementById('keyboard-proxy');
const zoomLabel = document.getElementById('zoom-label');
const forwardedKeys = new Set(['Backspace', 'Tab', 'Enter', 'Escape', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'PageUp', 'PageDown', 'Home', 'End', 'Delete']);
let currentZoom = 'fit';
let didInitialMobileFocus = false;
let keyboardForwardingArmed = false;
let lastRemoteClick = Promise.resolve();
let inputQueue = Promise.resolve();
const takeoverPath = window.location.pathname.replace(/\/+$/, '');

if (window.history && window.history.replaceState && window.location.search.includes('token=')) {{
  window.history.replaceState(null, document.title, takeoverPath);
}}

function setStatus(message) {{
  status.textContent = message;
}}

function actionUrl(action, params = {{}}) {{
  const query = new URLSearchParams();
  query.set('token', token);
  for (const [key, value] of Object.entries(params)) {{
    query.set(key, String(value));
  }}
  return `${{takeoverPath}}/${{action}}?${{query.toString()}}`;
}}

async function refresh() {{
  img.src = actionUrl('screenshot', {{ t: Date.now() }});
}}

function setZoom(value) {{
  currentZoom = value;
  if (value === 'fit') {{
    img.style.width = '100%';
    zoomLabel.textContent = 'fit';
    return;
  }}
  const scale = Number(value);
  img.style.width = `${{Math.round(scale * 100)}}%`;
  zoomLabel.textContent = `${{scale}}×`;
}}

function focusTopLeft() {{
  if (currentZoom === 'fit') {{
    setZoom(window.matchMedia('(max-width: 700px)').matches ? '2' : '1.5');
  }}
  viewer.scrollTo({{ left: 0, top: 0, behavior: 'smooth' }});
}}

function mapScreenshotCoordinates(event) {{
  const rect = img.getBoundingClientRect();
  const x = (event.clientX - rect.left) * (img.naturalWidth / rect.width);
  const y = (event.clientY - rect.top) * (img.naturalHeight / rect.height);
  return {{
    x: Math.max(0, Math.min(img.naturalWidth, x)),
    y: Math.max(0, Math.min(img.naturalHeight, y)),
  }};
}}

async function postJson(url, payload) {{
  const response = await fetch(url, {{
    method: 'POST',
    headers: {{ 'content-type': 'application/json' }},
    body: JSON.stringify(payload),
  }});
  setStatus(response.ok ? 'ok' : `request failed ${{response.status}}`);
  return response;
}}

function isOperatorControl(element) {{
  if (!element || element === keyboardProxy) {{
    return false;
  }}
  return Boolean(element.closest('textarea,input,select,button,[contenteditable="true"]'));
}}

function focusKeyboardProxy() {{
  keyboardForwardingArmed = true;
  if (!keyboardProxy) {{
    return;
  }}
  keyboardProxy.value = '';
  try {{
    keyboardProxy.focus({{ preventScroll: true }});
  }} catch (_) {{
    keyboardProxy.focus();
  }}
  setStatus('keyboard forwarding ready');
}}

function enqueueRemoteInput(action, payload, refreshAfter = false) {{
  inputQueue = inputQueue
    .catch(() => {{}})
    .then(() => lastRemoteClick.catch(() => {{}}))
    .then(async () => {{
      const response = await postJson(actionUrl(action), payload);
      if (response.ok && refreshAfter) {{
        await refresh();
      }}
      return response;
    }})
    .catch(() => {{
      setStatus('remote input failed');
    }});
  return inputQueue;
}}

function forwardText(text) {{
  if (!text) {{
    return Promise.resolve();
  }}
  return enqueueRemoteInput('type', {{ text }});
}}

function postKey(key) {{
  return enqueueRemoteInput('key', {{ key }}, true);
}}

img.addEventListener('load', () => {{
  setStatus(`${{img.naturalWidth}}×${{img.naturalHeight}} screenshot`);
  if (!didInitialMobileFocus && window.matchMedia('(max-width: 700px)').matches) {{
    didInitialMobileFocus = true;
    setZoom('2');
    requestAnimationFrame(() => viewer.scrollTo({{ left: 0, top: 0 }}));
  }}
}});

img.addEventListener('click', (event) => {{
  const point = mapScreenshotCoordinates(event);
  focusKeyboardProxy();
  lastRemoteClick = (async () => {{
    const response = await postJson(actionUrl('click'), point);
    if (response.ok) {{
      await refresh();
    }}
    return response;
  }})().catch(() => {{
    setStatus('click request failed');
  }});
}});

document.getElementById('refresh').onclick = refresh;
document.getElementById('top-left').onclick = focusTopLeft;
document.querySelectorAll('[data-zoom]').forEach((button) => {{
  button.addEventListener('click', () => {{
    setZoom(button.dataset.zoom);
  }});
}});

document.getElementById('typebtn').onclick = async () => {{
  await forwardText(textArea.value);
  await refresh();
}};

document.getElementById('scroll').onclick = async () => {{
  await postJson(actionUrl('scroll'), {{ delta_y: 500 }});
  await refresh();
}};

document.querySelectorAll('[data-key]').forEach((button) => {{
  button.addEventListener('click', async () => {{
    focusKeyboardProxy();
    await postKey(button.dataset.key);
  }});
}});

if (keyboardProxy) {{
  keyboardProxy.addEventListener('beforeinput', (event) => {{
    if (!keyboardForwardingArmed) {{
      return;
    }}
    if (event.inputType === 'insertLineBreak') {{
      event.preventDefault();
      postKey('Enter');
      return;
    }}
    if (typeof event.data === 'string' && event.data.length > 0) {{
      event.preventDefault();
      forwardText(event.data);
    }}
  }});

  keyboardProxy.addEventListener('input', () => {{
    const text = keyboardProxy.value;
    keyboardProxy.value = '';
    if (keyboardForwardingArmed && text) {{
      forwardText(text);
    }}
  }});

  keyboardProxy.addEventListener('paste', (event) => {{
    if (!keyboardForwardingArmed) {{
      return;
    }}
    const pasted = event.clipboardData ? event.clipboardData.getData('text') : '';
    if (pasted) {{
      event.preventDefault();
      forwardText(pasted);
    }}
  }});

  keyboardProxy.addEventListener('blur', () => {{
    if (!keyboardForwardingArmed) {{
      return;
    }}
    setTimeout(() => {{
      if (keyboardForwardingArmed && document.activeElement === document.body) {{
        focusKeyboardProxy();
      }}
    }}, 0);
  }});
}}

document.addEventListener('keydown', (event) => {{
  if (!keyboardForwardingArmed || isOperatorControl(event.target)) {{
    return;
  }}
  if (event.ctrlKey || event.metaKey || event.altKey) {{
    return;
  }}
  const key = event.key;
  if (!key) {{
    return;
  }}
  if (key.length === 1) {{
    if (event.target !== keyboardProxy) {{
      event.preventDefault();
      forwardText(key);
    }}
    return;
  }}
  if (forwardedKeys.has(key)) {{
    event.preventDefault();
    postKey(key);
  }}
}}, true);

document.getElementById('release').onclick = async () => {{
  const response = await fetch(actionUrl('release'), {{ method: 'POST' }});
  setStatus(response.ok ? 'released' : `release failed ${{response.status}}`);
}};

setInterval(refresh, 1200);
refresh();
</script>
</body>
</html>"#
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        backend::{BrowserBackend, LaunchedBrowser, StartSessionOptions},
        models::{
            CaptchaReportState, CreateProfileRequest, CredentialFillStartRequest,
            PauseForHumanRequest, SessionStatus,
        },
        store::AppStore,
        test_support::{
            MockBackend, MockCdpServer, MockEndpointResponse, persistent_req, spawn_api_server,
            test_config, token_from_url,
        },
    };
    use anyhow::{Context, Result};
    use reqwest::{StatusCode as HttpStatus, header};
    use serde_json::json;
    use std::{fs, sync::Arc, time::Duration};
    use tokio::{net::TcpListener, sync::oneshot, task::JoinHandle, time::sleep};
    use uuid::Uuid;

    fn fake_cdp_ws_url(browser_id: &str) -> String {
        let prefix = "ws://127.0.0.1:1/devtools";
        format!("{prefix}/browser/{browser_id}")
    }

    struct FakeBackend;

    #[async_trait::async_trait]
    impl BrowserBackend for FakeBackend {
        async fn launch(&self, _options: StartSessionOptions) -> Result<LaunchedBrowser> {
            let process = tokio::process::Command::new("sleep")
                .arg("60")
                .spawn()
                .context("spawn fake browser process")?;
            Ok(LaunchedBrowser {
                process,
                port: 1,
                http_base: "http://127.0.0.1:1".to_string(),
                cdp_ws_url: fake_cdp_ws_url("fake"),
                persona_guard: None,
            })
        }

        async fn close(&self, launched: &mut LaunchedBrowser) -> Result<()> {
            let _ = launched.process.start_kill();
            let _ = launched.process.wait().await;
            Ok(())
        }
    }

    struct ShortLivedBackend {
        cdp_http_base: String,
        cdp_ws_url: String,
        run_for: Duration,
    }

    #[async_trait::async_trait]
    impl BrowserBackend for ShortLivedBackend {
        async fn launch(&self, options: StartSessionOptions) -> Result<LaunchedBrowser> {
            let marker = options.user_data_dir.join("browser-exit-marker.txt");
            let script = format!(
                "sleep {delay}; printf browser-crashed > {marker}",
                delay = self.run_for.as_secs_f32(),
                marker = marker.display(),
            );
            let process = tokio::process::Command::new("sh")
                .arg("-c")
                .arg(script)
                .spawn()
                .context("spawn short-lived browser process")?;
            Ok(LaunchedBrowser {
                process,
                port: 9222,
                http_base: self.cdp_http_base.clone(),
                cdp_ws_url: self.cdp_ws_url.clone(),
                persona_guard: None,
            })
        }

        async fn close(&self, launched: &mut LaunchedBrowser) -> Result<()> {
            let _ = launched.process.start_kill();
            let _ = launched.process.wait().await;
            Ok(())
        }
    }

    struct TestServer {
        base_url: String,
        store: Arc<AppStore>,
        shutdown_tx: oneshot::Sender<()>,
        task: JoinHandle<()>,
        _tempdir: tempfile::TempDir,
    }

    impl TestServer {
        async fn stop(self) {
            let Self {
                shutdown_tx, task, ..
            } = self;
            let _ = shutdown_tx.send(());
            let _ = task.await;
        }
    }

    async fn spawn_fake_server(bearer_token: Option<&str>) -> TestServer {
        spawn_fake_server_with_operator_token(bearer_token, None).await
    }

    async fn spawn_fake_server_with_operator_token(
        bearer_token: Option<&str>,
        operator_token: Option<&str>,
    ) -> TestServer {
        let tempdir = tempfile::tempdir().unwrap();
        let mut config = test_config(
            tempdir.path().to_path_buf(),
            bearer_token.map(std::string::ToString::to_string),
        );
        config.operator_token = operator_token.map(std::string::ToString::to_string);
        let store = Arc::new(AppStore::new(config, Arc::new(FakeBackend)).await.unwrap());
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let base_url = format!("http://{}", listener.local_addr().unwrap());
        let (shutdown_tx, shutdown_rx) = oneshot::channel();
        let server_store = store.clone();
        let task = tokio::spawn(async move {
            axum::serve(listener, router(server_store))
                .with_graceful_shutdown(async {
                    let _ = shutdown_rx.await;
                })
                .await
                .unwrap();
        });
        TestServer {
            base_url,
            store,
            shutdown_tx,
            task,
            _tempdir: tempdir,
        }
    }

    struct RuntimeTestServer {
        base_url: String,
        store: Arc<AppStore>,
        shutdown_tx: oneshot::Sender<()>,
        task: JoinHandle<()>,
        cdp: MockCdpServer,
        _tempdir: tempfile::TempDir,
    }

    impl RuntimeTestServer {
        async fn stop(self) {
            let Self {
                shutdown_tx,
                task,
                cdp,
                ..
            } = self;
            let _ = shutdown_tx.send(());
            let _ = task.await;
            cdp.stop().await;
        }
    }

    async fn serve_runtime_store(
        tempdir: tempfile::TempDir,
        cdp: MockCdpServer,
        store: Arc<AppStore>,
    ) -> RuntimeTestServer {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let base_url = format!("http://{}", listener.local_addr().unwrap());
        let (shutdown_tx, shutdown_rx) = oneshot::channel();
        let server_store = store.clone();
        let task = tokio::spawn(async move {
            axum::serve(listener, router(server_store))
                .with_graceful_shutdown(async {
                    let _ = shutdown_rx.await;
                })
                .await
                .unwrap();
        });
        RuntimeTestServer {
            base_url,
            store,
            shutdown_tx,
            task,
            cdp,
            _tempdir: tempdir,
        }
    }

    async fn spawn_short_lived_server(takeover_ttl: Duration) -> RuntimeTestServer {
        let tempdir = tempfile::tempdir().unwrap();
        let cdp = MockCdpServer::spawn().await;
        let mut config = test_config(tempdir.path().to_path_buf(), None);
        config.takeover_ttl = takeover_ttl;
        let store = Arc::new(
            AppStore::new(
                config,
                Arc::new(ShortLivedBackend {
                    cdp_http_base: cdp.base_url.clone(),
                    cdp_ws_url: cdp.browser_ws_url.clone(),
                    run_for: Duration::from_millis(50),
                }),
            )
            .await
            .unwrap(),
        );

        serve_runtime_store(tempdir, cdp, store).await
    }

    async fn spawn_zero_ttl_server() -> RuntimeTestServer {
        let tempdir = tempfile::tempdir().unwrap();
        let cdp = MockCdpServer::spawn().await;
        let mut config = test_config(tempdir.path().to_path_buf(), None);
        config.takeover_ttl = Duration::ZERO;
        let store = Arc::new(
            AppStore::new(
                config,
                Arc::new(MockBackend::new(
                    cdp.base_url.clone(),
                    cdp.browser_ws_url.clone(),
                )),
            )
            .await
            .unwrap(),
        );

        serve_runtime_store(tempdir, cdp, store).await
    }

    #[test]
    fn constant_time_auth_checks_value() {
        assert!(constant_time_eq(b"Bearer abc", b"Bearer abc"));
        assert!(!constant_time_eq(b"Bearer abc", b"Bearer xyz"));
        assert!(!constant_time_eq(b"Bearer abc", b"Bearer abcd"));
    }

    #[test]
    fn takeover_html_contains_release_keyboard_and_type_safety_helpers() {
        let html = takeover_html(Uuid::nil(), "secret-token");

        assert!(html.contains("<meta name=\"viewport\""));
        assert!(html.contains("Release browser back to agent"));
        assert!(html.contains("Keyboard helpers"));
        assert!(html.contains("mapScreenshotCoordinates"));
        assert!(html.contains("id=\"viewer\""));
        assert!(html.contains("id=\"top-left\""));
        assert!(html.contains("data-zoom=\"2\""));
        assert!(html.contains("const takeoverPath = window.location.pathname.replace"));
        assert!(html.contains("function actionUrl(action"));
        assert!(html.contains("enqueueRemoteInput('key'"));
        assert!(!html.contains("`/takeover/${id}/key?token=${token}`"));
        assert!(html.contains("history.replaceState"));
        assert!(!html.contains("localStorage"));
        assert!(!html.contains("sessionStorage"));
        assert!(!html.contains("document.cookie"));
        assert!(html.contains("img.naturalWidth / rect.width"));
        assert!(html.contains("img.naturalHeight / rect.height"));
        assert!(html.contains("const id = \"00000000-0000-0000-0000-000000000000\";"));
        assert!(!html.contains("const id = 00000000-0000-0000-0000-000000000000;"));
        assert!(html.contains("textarea id=\"text\""));
        assert!(html.contains("id=\"keyboard-proxy\""));
        assert!(html.contains("focusKeyboardProxy"));
        assert!(html.contains("addEventListener('beforeinput'"));
        assert!(html.contains("document.addEventListener('keydown'"));
        assert!(html.contains("enqueueRemoteInput('type'"));
        assert!(html.contains("never stored in runtime logs"));
        assert!(!html.contains("console.log"));

        let screenshot_index = html.find("id=\"viewer\"").unwrap();
        let type_index = html.find("textarea id=\"text\"").unwrap();
        let keyboard_index = html.find("Keyboard helpers").unwrap();
        assert!(screenshot_index < type_index);
        assert!(screenshot_index < keyboard_index);
    }

    #[test]
    fn nonlocal_inspector_env_requires_explicit_truthy_value() {
        for value in ["", "0", "false", "False", "no", "off", "anything"] {
            assert!(!nonlocal_inspector_approval_value(value));
        }
        for value in ["1", "true", "TRUE", " yes ", "on"] {
            assert!(nonlocal_inspector_approval_value(value));
        }
    }

    #[tokio::test]
    async fn credential_privacy_guard_image_returns_svg_card_not_json() {
        let response = credential_privacy_guard_image();
        assert_eq!(response.status(), StatusCode::OK);
        assert!(
            response
                .headers()
                .get(header::CONTENT_TYPE)
                .unwrap()
                .to_str()
                .unwrap()
                .starts_with("image/svg+xml")
        );
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let body = String::from_utf8(body.to_vec()).unwrap();
        assert!(body.contains("Credential privacy guard active"));
        assert!(!body.contains("application/json"));
    }

    #[tokio::test]
    async fn auth_required_routes_return_unauthorized_and_forbidden() {
        let server = spawn_fake_server(Some("secret-token")).await;
        let created = server
            .store
            .create_session(persistent_req("p1"))
            .await
            .unwrap();
        let client = reqwest::Client::new();
        let requests = vec![
            client
                .post(format!("{}/sessions", server.base_url))
                .json(&persistent_req("p2"))
                .build()
                .unwrap(),
            client
                .get(format!("{}/sessions", server.base_url))
                .build()
                .unwrap(),
            client
                .get(format!("{}/sessions/{}", server.base_url, created.id))
                .build()
                .unwrap(),
            client
                .delete(format!("{}/sessions/{}", server.base_url, created.id))
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/sessions/{}/pause_for_human",
                    server.base_url, created.id
                ))
                .json(&PauseForHumanRequest {
                    reason: Some("manual oauth approval".into()),
                })
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/sessions/{}/release",
                    server.base_url, created.id
                ))
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/sessions/{}/captcha/report",
                    server.base_url, created.id
                ))
                .json(&json!({
                    "state": "human_required",
                    "challenge_type": "hcaptcha",
                    "reason": "manual checkpoint"
                }))
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/sessions/{}/captcha/resolve",
                    server.base_url, created.id
                ))
                .json(&json!({"outcome": "resolved", "note": "solved"}))
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/sessions/{}/captcha/scan",
                    server.base_url, created.id
                ))
                .json(&json!({"dry_run": true}))
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/sessions/{}/captcha/solve",
                    server.base_url, created.id
                ))
                .json(&json!({"dry_run": true}))
                .build()
                .unwrap(),
            client
                .get(format!(
                    "{}/sessions/{}/captcha/status",
                    server.base_url, created.id
                ))
                .build()
                .unwrap(),
            client
                .get(format!(
                    "{}/sessions/{}/wait?timeout_ms=1",
                    server.base_url, created.id
                ))
                .build()
                .unwrap(),
            client
                .get(format!(
                    "{}/sessions/{}/screenshot",
                    server.base_url, created.id
                ))
                .build()
                .unwrap(),
            client
                .get(format!(
                    "{}/sessions/{}/artifacts",
                    server.base_url, created.id
                ))
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/sessions/{}/credentials/fill",
                    server.base_url, created.id
                ))
                .json(&CredentialFillStartRequest {
                    alias: "demo-login".into(),
                    username_selector: Some("#user".into()),
                    password_selector: Some("#pass".into()),
                    purpose: None,
                    expected_origin: Some("https://example.test".into()),
                })
                .build()
                .unwrap(),
            client
                .get(format!(
                    "{}/sessions/{}/credentials/fill/{}",
                    server.base_url,
                    created.id,
                    Uuid::new_v4()
                ))
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/sessions/{}/credentials/fill/{}/approve",
                    server.base_url,
                    created.id,
                    Uuid::new_v4()
                ))
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/sessions/{}/credentials/fill/{}/deny",
                    server.base_url,
                    created.id,
                    Uuid::new_v4()
                ))
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/sessions/{}/credentials/privacy-guard/clear",
                    server.base_url, created.id
                ))
                .build()
                .unwrap(),
            client
                .post(format!("{}/profiles", server.base_url))
                .json(&CreateProfileRequest {
                    id: Some("p2".into()),
                })
                .build()
                .unwrap(),
            client
                .get(format!("{}/profiles", server.base_url))
                .build()
                .unwrap(),
            client
                .delete(format!("{}/profiles/p1", server.base_url))
                .build()
                .unwrap(),
        ];

        for request in requests {
            let response = client.execute(request).await.unwrap();
            assert_eq!(response.status(), HttpStatus::UNAUTHORIZED);
            let body = response.json::<serde_json::Value>().await.unwrap();
            assert_eq!(body["error"], "unauthorized");
        }

        let forbidden = client
            .get(format!("{}/sessions", server.base_url))
            .header(header::AUTHORIZATION, "Bearer wrong-token")
            .send()
            .await
            .unwrap();
        assert_eq!(forbidden.status(), HttpStatus::FORBIDDEN);
        let body = forbidden.json::<serde_json::Value>().await.unwrap();
        assert_eq!(body["error"], "forbidden");

        let authorized = client
            .get(format!("{}/sessions", server.base_url))
            .header(header::AUTHORIZATION, "Bearer secret-token")
            .send()
            .await
            .unwrap();
        assert_eq!(authorized.status(), HttpStatus::OK);
        let body = authorized.json::<serde_json::Value>().await.unwrap();
        assert_eq!(body.as_array().unwrap().len(), 1);

        server.store.delete_session(created.id).await.unwrap();
        server.stop().await;
    }

    #[tokio::test]
    async fn credential_operator_routes_require_distinct_operator_token() {
        let server =
            spawn_fake_server_with_operator_token(Some("agent-token"), Some("operator-token"))
                .await;
        let created = server
            .store
            .create_session(persistent_req("operator-auth"))
            .await
            .unwrap();
        let client = reqwest::Client::new();
        let request_id = Uuid::new_v4();
        let approve_url = format!(
            "{}/sessions/{}/credentials/fill/{}/approve",
            server.base_url, created.id, request_id
        );
        let deny_url = format!(
            "{}/sessions/{}/credentials/fill/{}/deny",
            server.base_url, created.id, request_id
        );
        let clear_url = format!(
            "{}/sessions/{}/credentials/privacy-guard/clear",
            server.base_url, created.id
        );

        for url in [&approve_url, &deny_url, &clear_url] {
            let agent_only = client
                .post(url)
                .header(header::AUTHORIZATION, "Bearer agent-token")
                .send()
                .await
                .unwrap();
            assert_eq!(agent_only.status(), HttpStatus::FORBIDDEN);
            let body = agent_only.json::<serde_json::Value>().await.unwrap();
            assert_eq!(body["error"], "forbidden");

            let operator_authorized = client
                .post(url)
                .header(header::AUTHORIZATION, "Bearer operator-token")
                .send()
                .await
                .unwrap();
            assert_ne!(operator_authorized.status(), HttpStatus::UNAUTHORIZED);
            assert_ne!(operator_authorized.status(), HttpStatus::FORBIDDEN);
        }

        server.store.delete_session(created.id).await.unwrap();
        server.stop().await;
    }

    #[tokio::test]
    async fn credential_operator_routes_reject_reused_agent_token_configuration() {
        let server =
            spawn_fake_server_with_operator_token(Some("same-token"), Some("same-token")).await;
        let created = server
            .store
            .create_session(persistent_req("operator-auth-same"))
            .await
            .unwrap();
        let client = reqwest::Client::new();
        let response = client
            .post(format!(
                "{}/sessions/{}/credentials/privacy-guard/clear",
                server.base_url, created.id
            ))
            .header(header::AUTHORIZATION, "Bearer same-token")
            .send()
            .await
            .unwrap();
        assert_eq!(response.status(), HttpStatus::FORBIDDEN);
        let body = response.json::<serde_json::Value>().await.unwrap();
        assert_eq!(body["error"], "forbidden");

        server.store.delete_session(created.id).await.unwrap();
        server.stop().await;
    }

    #[tokio::test]
    async fn inspector_routes_use_in_memory_bearer_prompt_without_browser_storage() {
        let server = spawn_fake_server(Some("inspector-bearer")).await;
        let client = reqwest::Client::new();

        let page_without_auth = client
            .get(format!("{}/inspector", server.base_url))
            .send()
            .await
            .unwrap();
        assert_eq!(page_without_auth.status(), HttpStatus::UNAUTHORIZED);

        let page = client
            .get(format!("{}/inspector", server.base_url))
            .header(header::AUTHORIZATION, "Bearer inspector-bearer")
            .send()
            .await
            .unwrap();
        assert_eq!(page.status(), HttpStatus::OK);
        assert!(
            page.headers()
                .get(header::CONTENT_TYPE)
                .unwrap()
                .to_str()
                .unwrap()
                .starts_with("text/html")
        );
        let html = page.text().await.unwrap();
        assert!(html.contains("<meta name=\"viewport\""));
        assert!(html.contains("Hermes Browser Runtime inspector"));
        assert!(html.contains("Release browser back to agent"));
        assert!(html.contains("Cancel / deny checkpoint"));
        assert!(html.contains("Credential fill"));
        assert!(html.contains("CAPTCHA / checkpoint"));
        assert!(html.contains("latest screenshot"));
        assert!(html.contains("history.replaceState"));
        assert!(html.contains("promptForInspectorToken"));
        assert!(html.contains("window.prompt"));
        assert!(html.contains("inspectorBearerToken"));
        assert!(html.contains("Authorization"));
        assert!(html.contains("Bearer $"));
        assert!(html.contains("Authorization token stays in memory"));
        assert!(html.contains("confirmRiskyInspectorAction"));
        assert!(html.contains("window.confirm"));
        assert!(html.contains("Release browser back to agent?"));
        assert!(html.contains("Cancel browser session?"));
        assert!(!html.contains("inspector-bearer"));
        assert!(!html.contains("localStorage"));
        assert!(!html.contains("sessionStorage"));
        assert!(!html.contains("document.cookie"));

        let missing_auth = client
            .get(format!("{}/inspector/api/sessions", server.base_url))
            .send()
            .await
            .unwrap();
        assert_eq!(missing_auth.status(), HttpStatus::UNAUTHORIZED);

        let missing_page_detail = client
            .get(format!("{}/inspector/{}", server.base_url, Uuid::new_v4()))
            .send()
            .await
            .unwrap();
        assert_eq!(missing_page_detail.status(), HttpStatus::UNAUTHORIZED);

        let wrong_auth = client
            .get(format!("{}/inspector/api/sessions", server.base_url))
            .header(header::AUTHORIZATION, "Bearer wrong-inspector-bearer")
            .send()
            .await
            .unwrap();
        assert_eq!(wrong_auth.status(), HttpStatus::FORBIDDEN);
        let wrong_body = wrong_auth.text().await.unwrap();
        assert!(!wrong_body.contains("wrong-inspector-bearer"));

        let authorized = client
            .get(format!("{}/inspector/api/sessions", server.base_url))
            .header(header::AUTHORIZATION, "Bearer inspector-bearer")
            .send()
            .await
            .unwrap();
        assert_eq!(authorized.status(), HttpStatus::OK);

        server.stop().await;
    }

    #[tokio::test]
    async fn inspector_detail_page_missing_detail_and_loopback_guard_are_safe() {
        let server = spawn_fake_server(Some("inspector-bearer")).await;
        let client = reqwest::Client::new();
        let created = server
            .store
            .create_session(persistent_req("p1"))
            .await
            .unwrap();

        let page = client
            .get(format!("{}/inspector/{}", server.base_url, created.id))
            .send()
            .await
            .unwrap();
        assert_eq!(page.status(), HttpStatus::UNAUTHORIZED);

        let page = client
            .get(format!("{}/inspector/{}", server.base_url, created.id))
            .header(header::AUTHORIZATION, "Bearer inspector-bearer")
            .send()
            .await
            .unwrap();
        assert_eq!(page.status(), HttpStatus::OK);
        let html = page.text().await.unwrap();
        assert!(html.contains(&created.id.to_string()));
        assert!(!html.contains("inspector-bearer"));

        let missing = client
            .get(format!(
                "{}/inspector/api/sessions/{}",
                server.base_url,
                Uuid::new_v4()
            ))
            .header(header::AUTHORIZATION, "Bearer inspector-bearer")
            .send()
            .await
            .unwrap();
        assert_eq!(missing.status(), HttpStatus::NOT_FOUND);
        let missing_body = missing.text().await.unwrap();
        assert!(!missing_body.contains("inspector-bearer"));

        let tempdir = tempfile::tempdir().unwrap();
        let cdp = MockCdpServer::spawn().await;
        let mut config = test_config(tempdir.path().to_path_buf(), None);
        config.bind = "0.0.0.0:7788".parse().unwrap();
        let guarded_store = AppStore::new(
            config,
            Arc::new(MockBackend::new(
                cdp.base_url.clone(),
                cdp.browser_ws_url.clone(),
            )),
        )
        .await
        .unwrap();
        let guarded = inspector_loopback_guard_response(&guarded_store).unwrap();
        assert_eq!(guarded.status(), HttpStatus::FORBIDDEN);

        cdp.stop().await;
        server.store.delete_session(created.id).await.unwrap();
        server.stop().await;
    }

    #[tokio::test]
    async fn inspector_api_redacts_state_and_read_only_live_links_cannot_mutate() {
        let server = spawn_api_server(Some("api-bearer")).await;
        let client = reqwest::Client::new();
        let created = server
            .store
            .create_session(persistent_req("p1"))
            .await
            .unwrap();
        server
            .store
            .report_captcha(
                created.id,
                CaptchaReportState::HumanRequired,
                Some("turnstile".into()),
                Some("request_body=fixture-value".into()),
            )
            .await
            .unwrap();
        let paused = server
            .store
            .pause_for_human(created.id, Some("request_body=fixture-value".into()))
            .await
            .unwrap();
        let takeover_token = token_from_url(paused.takeover_url.as_ref().unwrap()).to_string();

        let artifacts_dir = server
            .store
            .config
            .data_dir
            .join("sessions")
            .join(created.id.to_string())
            .join("artifacts");
        fs::write(artifacts_dir.join("screenshot.png"), b"png").unwrap();
        fs::write(
            artifacts_dir.join("auth-body-provider-fixture.txt"),
            b"sensitive filename canary",
        )
        .unwrap();
        let downloads_dir = server
            .store
            .config
            .data_dir
            .join("sessions")
            .join(created.id.to_string())
            .join("downloads");
        fs::write(downloads_dir.join("report.csv"), b"a,b\n1,2\n").unwrap();

        let create_link = client
            .post(format!(
                "{}/inspector/api/sessions/{}/live-links",
                server.base_url, created.id
            ))
            .header(header::AUTHORIZATION, "Bearer api-bearer")
            .json(&json!({"mode": "read_only"}))
            .send()
            .await
            .unwrap();
        assert_eq!(create_link.status(), HttpStatus::OK);
        let link_json = create_link.json::<serde_json::Value>().await.unwrap();
        assert_eq!(link_json["mode"], "read_only");
        let readonly_url = link_json["url"].as_str().unwrap().to_string();
        let readonly_token = token_from_url(&readonly_url).to_string();
        assert_ne!(readonly_token, takeover_token);

        let page = client
            .get(format!(
                "{}/takeover/{}?token={readonly_token}",
                server.base_url, created.id
            ))
            .send()
            .await
            .unwrap();
        assert_eq!(page.status(), HttpStatus::OK);

        let blocked_type = client
            .post(format!(
                "{}/takeover/{}/type?token={readonly_token}",
                server.base_url, created.id
            ))
            .json(&json!({"text": "request_body=typed-fixture"}))
            .send()
            .await
            .unwrap();
        assert_eq!(blocked_type.status(), HttpStatus::FORBIDDEN);
        let blocked_body = blocked_type.text().await.unwrap();
        assert!(blocked_body.contains("read-only live link"));
        assert!(!blocked_body.contains(&readonly_token));
        assert!(!blocked_body.contains("typed-fixture"));

        let list = client
            .get(format!("{}/inspector/api/sessions", server.base_url))
            .header(header::AUTHORIZATION, "Bearer api-bearer")
            .send()
            .await
            .unwrap();
        assert_eq!(list.status(), HttpStatus::OK);
        let list_body = list.text().await.unwrap();
        assert!(list_body.contains("paused_for_human"));
        assert!(list_body.contains("human_required"));
        assert!(list_body.contains("screenshot.png"));
        assert!(list_body.contains("report.csv"));
        assert!(list_body.contains("[REDACTED]"));
        assert!(!list_body.contains("auth-body-provider-fixture.txt"));
        assert!(!list_body.contains("fixture-value"));
        assert!(!list_body.contains(&takeover_token));
        assert!(!list_body.contains(&readonly_token));
        assert!(!list_body.contains("devtools/browser"));
        assert!(!list_body.contains(&server.store.config.data_dir.to_string_lossy().to_string()));

        let detail = client
            .get(format!(
                "{}/inspector/api/sessions/{}",
                server.base_url, created.id
            ))
            .header(header::AUTHORIZATION, "Bearer api-bearer")
            .send()
            .await
            .unwrap();
        assert_eq!(detail.status(), HttpStatus::OK);
        let detail_body = detail.text().await.unwrap();
        assert!(detail_body.contains("screenshot.png"));
        assert!(detail_body.contains("report.csv"));
        assert!(detail_body.contains("[REDACTED]"));
        assert!(!detail_body.contains("auth-body-provider-fixture.txt"));
        assert!(!detail_body.contains(&server.store.config.data_dir.to_string_lossy().to_string()));

        let revoke = client
            .delete(format!(
                "{}/inspector/api/sessions/{}/live-links/{}",
                server.base_url,
                created.id,
                link_json["id"].as_str().unwrap()
            ))
            .header(header::AUTHORIZATION, "Bearer api-bearer")
            .send()
            .await
            .unwrap();
        assert_eq!(revoke.status(), HttpStatus::OK);

        let revoked_page = client
            .get(format!(
                "{}/takeover/{}?token={readonly_token}",
                server.base_url, created.id
            ))
            .send()
            .await
            .unwrap();
        assert_eq!(revoked_page.status(), HttpStatus::FORBIDDEN);
        let revoked_body = revoked_page.text().await.unwrap();
        assert!(!revoked_body.contains(&readonly_token));

        server.store.delete_session(created.id).await.unwrap();
        server.stop().await;
    }

    #[tokio::test]
    async fn session_and_profile_error_routes_map_status_codes() {
        let server = spawn_fake_server(None).await;
        let client = reqwest::Client::new();
        let created = client
            .post(format!("{}/sessions", server.base_url))
            .json(&persistent_req("p1"))
            .send()
            .await
            .unwrap();
        assert_eq!(created.status(), HttpStatus::OK);
        let created_id = created.json::<serde_json::Value>().await.unwrap()["id"]
            .as_str()
            .unwrap()
            .parse::<Uuid>()
            .unwrap();

        let conflict = client
            .post(format!("{}/sessions", server.base_url))
            .json(&persistent_req("p1"))
            .send()
            .await
            .unwrap();
        assert_eq!(conflict.status(), HttpStatus::CONFLICT);
        let body = conflict.json::<serde_json::Value>().await.unwrap();
        assert!(body["error"].as_str().unwrap().contains("locked"));

        let missing = Uuid::new_v4();
        let routes = vec![
            client
                .get(format!("{}/sessions/{}", server.base_url, missing))
                .build()
                .unwrap(),
            client
                .delete(format!("{}/sessions/{}", server.base_url, missing))
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/sessions/{}/pause_for_human",
                    server.base_url, missing
                ))
                .header(header::CONTENT_TYPE, "application/json")
                .body("{\"reason\":\"waiting\"}")
                .build()
                .unwrap(),
            client
                .post(format!("{}/sessions/{}/release", server.base_url, missing))
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/sessions/{}/captcha/report",
                    server.base_url, missing
                ))
                .header(header::CONTENT_TYPE, "application/json")
                .body("{\"state\":\"suspected\"}")
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/sessions/{}/captcha/resolve",
                    server.base_url, missing
                ))
                .header(header::CONTENT_TYPE, "application/json")
                .body("{\"outcome\":\"resolved\"}")
                .build()
                .unwrap(),
            client
                .get(format!(
                    "{}/sessions/{}/wait?timeout_ms=1",
                    server.base_url, missing
                ))
                .build()
                .unwrap(),
            client
                .get(format!(
                    "{}/sessions/{}/artifacts",
                    server.base_url, missing
                ))
                .build()
                .unwrap(),
        ];
        for request in routes {
            let response = client.execute(request).await.unwrap();
            assert_eq!(response.status(), HttpStatus::NOT_FOUND);
            let body = response.json::<serde_json::Value>().await.unwrap();
            assert!(
                body["error"]
                    .as_str()
                    .unwrap()
                    .contains("session not found")
            );
        }

        let screenshot = client
            .get(format!(
                "{}/sessions/{created_id}/screenshot",
                server.base_url
            ))
            .send()
            .await
            .unwrap();
        assert_eq!(screenshot.status(), HttpStatus::INTERNAL_SERVER_ERROR);
        let body = screenshot.json::<serde_json::Value>().await.unwrap();
        assert!(!body["error"].as_str().unwrap().is_empty());

        let locked_profile = client
            .delete(format!("{}/profiles/p1", server.base_url))
            .send()
            .await
            .unwrap();
        assert_eq!(locked_profile.status(), HttpStatus::CONFLICT);
        let body = locked_profile.json::<serde_json::Value>().await.unwrap();
        assert!(body["error"].as_str().unwrap().contains("locked"));

        let missing_download = client
            .get(format!(
                "{}/sessions/{created_id}/download?name=missing.txt",
                server.base_url
            ))
            .send()
            .await
            .unwrap();
        assert_eq!(missing_download.status(), HttpStatus::NOT_FOUND);
        let body = missing_download.json::<serde_json::Value>().await.unwrap();
        assert!(
            body["error"]
                .as_str()
                .unwrap()
                .contains("download not found")
        );

        let invalid_profile = client
            .delete(format!("{}/profiles/bad%20path", server.base_url))
            .send()
            .await
            .unwrap();
        assert_eq!(invalid_profile.status(), HttpStatus::CONFLICT);
        let body = invalid_profile.json::<serde_json::Value>().await.unwrap();
        assert!(body["error"].as_str().unwrap().contains("invalid"));

        server.store.delete_session(created_id).await.unwrap();
        server.stop().await;
    }

    #[tokio::test]
    async fn captcha_report_and_resolve_routes_enforce_state_machine_and_wake_waiters() {
        let server = spawn_fake_server(None).await;
        let client = reqwest::Client::new();
        let created = client
            .post(format!("{}/sessions", server.base_url))
            .json(&persistent_req("p-captcha"))
            .send()
            .await
            .unwrap();
        assert_eq!(created.status(), HttpStatus::OK);
        let session_id = created.json::<serde_json::Value>().await.unwrap()["id"]
            .as_str()
            .unwrap()
            .parse::<Uuid>()
            .unwrap();

        let reported = client
            .post(format!(
                "{}/sessions/{session_id}/captcha/report",
                server.base_url
            ))
            .json(&json!({
                "state": "human_required",
                "challenge_type": "hcaptcha",
                "reason": "checkpoint includes raw password 123456"
            }))
            .send()
            .await
            .unwrap();
        assert_eq!(reported.status(), HttpStatus::OK);
        let reported_json = reported.json::<serde_json::Value>().await.unwrap();
        assert_eq!(reported_json["status"], "paused_for_human");
        assert_eq!(reported_json["captcha_status"], "human_required");
        assert_eq!(reported_json["captcha_challenge_type"], "hcaptcha");
        let takeover_url = reported_json["takeover_url"]
            .as_str()
            .expect("human-required CAPTCHA report should expose takeover_url")
            .to_string();
        assert!(takeover_url.contains("/takeover/"));
        let pause_reason = reported_json["pause_reason"].as_str().unwrap().to_string();
        assert!(!pause_reason.contains("raw password"));
        assert!(!pause_reason.contains("123456"));

        let downgrade = client
            .post(format!(
                "{}/sessions/{session_id}/captcha/report",
                server.base_url
            ))
            .json(&json!({"state": "suspected"}))
            .send()
            .await
            .unwrap();
        assert_eq!(downgrade.status(), HttpStatus::CONFLICT);

        let resolved = client
            .post(format!(
                "{}/sessions/{session_id}/captcha/resolve",
                server.base_url
            ))
            .json(&json!({"outcome": "resolved", "note": "manual code 123456"}))
            .send()
            .await
            .unwrap();
        assert_eq!(resolved.status(), HttpStatus::OK);
        let resolved_json = resolved.json::<serde_json::Value>().await.unwrap();
        assert_eq!(resolved_json["status"], "paused_for_human");
        assert_eq!(resolved_json["captcha_status"], "resolved");
        assert_eq!(
            resolved_json["takeover_url"].as_str(),
            Some(takeover_url.as_str())
        );
        assert_eq!(
            resolved_json["pause_reason"].as_str(),
            Some(pause_reason.as_str())
        );

        let wait_after_resolve = client
            .get(format!(
                "{}/sessions/{session_id}/wait?timeout_ms=25",
                server.base_url
            ))
            .send()
            .await
            .unwrap();
        assert_eq!(wait_after_resolve.status(), HttpStatus::OK);
        let wait_after_resolve_json = wait_after_resolve
            .json::<serde_json::Value>()
            .await
            .unwrap();
        assert_eq!(wait_after_resolve_json["timed_out"], true);
        assert_eq!(
            wait_after_resolve_json["session"]["status"],
            "paused_for_human"
        );
        assert_eq!(
            wait_after_resolve_json["session"]["captcha_status"],
            "resolved"
        );

        let wait_url = format!(
            "{}/sessions/{session_id}/wait?timeout_ms=1000",
            server.base_url
        );
        let wait_client = client.clone();
        let wait_task = tokio::spawn(async move {
            wait_client
                .get(wait_url)
                .send()
                .await
                .unwrap()
                .json::<serde_json::Value>()
                .await
                .unwrap()
        });
        sleep(Duration::from_millis(25)).await;

        let released = client
            .post(format!("{}/sessions/{session_id}/release", server.base_url))
            .send()
            .await
            .unwrap();
        assert_eq!(released.status(), HttpStatus::OK);
        let released_json = released.json::<serde_json::Value>().await.unwrap();
        assert_eq!(released_json["status"], "running");
        assert_eq!(released_json["captcha_status"], "resolved");
        assert!(released_json["takeover_url"].is_null());
        assert!(released_json["pause_reason"].is_null());

        let waited_json = wait_task.await.unwrap();
        assert_eq!(waited_json["timed_out"], false);
        assert_eq!(waited_json["session"]["status"], "running");
        assert_eq!(waited_json["session"]["captcha_status"], "resolved");

        let double_resolve = client
            .post(format!(
                "{}/sessions/{session_id}/captcha/resolve",
                server.base_url
            ))
            .json(&json!({"outcome": "dismissed"}))
            .send()
            .await
            .unwrap();
        assert_eq!(double_resolve.status(), HttpStatus::CONFLICT);

        let mut progress_req = persistent_req("p-captcha-progress");
        progress_req.captcha_policy = Some(crate::models::CaptchaPolicy::ObserveOnly);
        let progress = client
            .post(format!("{}/sessions", server.base_url))
            .json(&progress_req)
            .send()
            .await
            .unwrap();
        assert_eq!(progress.status(), HttpStatus::OK);
        let progress_id = progress.json::<serde_json::Value>().await.unwrap()["id"]
            .as_str()
            .unwrap()
            .parse::<Uuid>()
            .unwrap();
        let in_progress = client
            .post(format!(
                "{}/sessions/{progress_id}/captcha/report",
                server.base_url
            ))
            .json(&json!({"state": "in_progress", "challenge_type": "turnstile"}))
            .send()
            .await
            .unwrap();
        assert_eq!(in_progress.status(), HttpStatus::OK);
        assert_eq!(
            in_progress.json::<serde_json::Value>().await.unwrap()["captcha_status"],
            "in_progress"
        );
        let failed = client
            .post(format!(
                "{}/sessions/{progress_id}/captcha/resolve",
                server.base_url
            ))
            .json(&json!({"outcome": "failed", "note": "operator timed out"}))
            .send()
            .await
            .unwrap();
        assert_eq!(failed.status(), HttpStatus::OK);
        assert_eq!(
            failed.json::<serde_json::Value>().await.unwrap()["captcha_status"],
            "failed"
        );

        let mut disabled_req = persistent_req("p-captcha-disabled");
        disabled_req.captcha_policy = Some(crate::models::CaptchaPolicy::Disabled);
        let disabled = client
            .post(format!("{}/sessions", server.base_url))
            .json(&disabled_req)
            .send()
            .await
            .unwrap();
        assert_eq!(disabled.status(), HttpStatus::OK);
        let disabled_id = disabled.json::<serde_json::Value>().await.unwrap()["id"]
            .as_str()
            .unwrap()
            .parse::<Uuid>()
            .unwrap();
        let disabled_report = client
            .post(format!(
                "{}/sessions/{disabled_id}/captcha/report",
                server.base_url
            ))
            .json(&json!({"state": "suspected", "reason": "should be blocked"}))
            .send()
            .await
            .unwrap();
        assert_eq!(disabled_report.status(), HttpStatus::CONFLICT);
        let disabled_body = disabled_report.json::<serde_json::Value>().await.unwrap();
        assert!(
            disabled_body["error"]
                .as_str()
                .unwrap()
                .contains("disabled")
        );

        server.store.delete_session(session_id).await.unwrap();
        server.store.delete_session(progress_id).await.unwrap();
        server.store.delete_session(disabled_id).await.unwrap();
        server.stop().await;
    }

    #[tokio::test]
    async fn captcha_scan_solve_and_status_routes_stay_local_and_redacted() {
        let server = spawn_fake_server(None).await;
        let client = reqwest::Client::new();
        let mut req = persistent_req("p-captcha-solver");
        req.captcha_policy = Some(crate::models::CaptchaPolicy::AutoSolve);
        let created = client
            .post(format!("{}/sessions", server.base_url))
            .json(&req)
            .send()
            .await
            .unwrap();
        assert_eq!(created.status(), HttpStatus::OK);
        let session_id = created.json::<serde_json::Value>().await.unwrap()["id"]
            .as_str()
            .unwrap()
            .parse::<Uuid>()
            .unwrap();

        let status = client
            .get(format!(
                "{}/sessions/{session_id}/captcha/status",
                server.base_url
            ))
            .send()
            .await
            .unwrap();
        assert_eq!(status.status(), HttpStatus::OK);
        let status_json = status.json::<serde_json::Value>().await.unwrap();
        assert_eq!(status_json["captcha_policy"], "auto_solve");
        assert_eq!(status_json["captcha_status"], "none");
        assert_eq!(status_json["solver"]["status"], "not_requested");
        assert_eq!(status_json["solver"]["enabled"], false);

        let scan = client
            .post(format!(
                "{}/sessions/{session_id}/captcha/scan",
                server.base_url
            ))
            .json(&json!({"dry_run": true}))
            .send()
            .await
            .unwrap();
        assert_eq!(scan.status(), HttpStatus::OK);
        let scan_json = scan.json::<serde_json::Value>().await.unwrap();
        assert_eq!(scan_json["detected"], false);
        assert_eq!(scan_json["provider_call_performed"], false);
        assert_eq!(
            scan_json["policy_decision"],
            "auto_solve_waiting_for_detection"
        );

        let dry_run_solve = client
            .post(format!(
                "{}/sessions/{session_id}/captcha/solve",
                server.base_url
            ))
            .json(&json!({"dry_run": true}))
            .send()
            .await
            .unwrap();
        assert_eq!(dry_run_solve.status(), HttpStatus::OK);
        let dry_run_json = dry_run_solve.json::<serde_json::Value>().await.unwrap();
        assert_eq!(dry_run_json["captcha_status"], "none");
        assert_eq!(dry_run_json["provider_call_performed"], false);

        let solved = client
            .post(format!(
                "{}/sessions/{session_id}/captcha/solve",
                server.base_url
            ))
            .json(&json!({
                "challenge_type": "turnstile",
                "reason": "password=solver-secret-123"
            }))
            .send()
            .await
            .unwrap();
        assert_eq!(solved.status(), HttpStatus::OK);
        let solved_body = solved.text().await.unwrap();
        assert!(!solved_body.contains("solver-secret-123"));
        let solved_json = serde_json::from_str::<serde_json::Value>(&solved_body).unwrap();
        assert_eq!(solved_json["captcha_status"], "human_required");
        assert_eq!(solved_json["challenge_type"], "turnstile");
        assert_eq!(solved_json["solver"]["status"], "disabled");
        assert_eq!(solved_json["solver"]["normalized_error"], "solver_disabled");
        assert_eq!(solved_json["solver"]["human_takeover_required"], true);
        assert_eq!(solved_json["provider_call_performed"], false);

        let after_solve = client
            .get(format!(
                "{}/sessions/{session_id}/captcha/status",
                server.base_url
            ))
            .send()
            .await
            .unwrap();
        assert_eq!(after_solve.status(), HttpStatus::OK);
        let after_solve_json = after_solve.json::<serde_json::Value>().await.unwrap();
        assert_eq!(after_solve_json["captcha_status"], "human_required");
        assert_eq!(
            after_solve_json["solver"]["normalized_error"],
            "solver_disabled"
        );

        let detected_scan = client
            .post(format!(
                "{}/sessions/{session_id}/captcha/scan",
                server.base_url
            ))
            .send()
            .await
            .unwrap();
        assert_eq!(detected_scan.status(), HttpStatus::OK);
        let detected_scan_json = detected_scan.json::<serde_json::Value>().await.unwrap();
        assert_eq!(detected_scan_json["detected"], true);
        assert_eq!(
            detected_scan_json["policy_decision"],
            "local_checkpoint_detected"
        );
        assert_eq!(detected_scan_json["provider_call_performed"], false);

        let missing_id = Uuid::new_v4();
        for response in [
            client
                .get(format!(
                    "{}/sessions/{missing_id}/captcha/status",
                    server.base_url
                ))
                .send()
                .await
                .unwrap(),
            client
                .post(format!(
                    "{}/sessions/{missing_id}/captcha/scan",
                    server.base_url
                ))
                .json(&json!({"dry_run": true}))
                .send()
                .await
                .unwrap(),
            client
                .post(format!(
                    "{}/sessions/{missing_id}/captcha/solve",
                    server.base_url
                ))
                .json(&json!({"dry_run": true}))
                .send()
                .await
                .unwrap(),
        ] {
            assert_eq!(response.status(), HttpStatus::NOT_FOUND);
            let body = response.json::<serde_json::Value>().await.unwrap();
            assert_eq!(body["error"], "session not found");
        }

        server.store.delete_session(session_id).await.unwrap();
        server.stop().await;
    }

    #[tokio::test]
    async fn running_sessions_do_not_expose_takeover_urls_or_accept_takeover_requests_before_pause()
    {
        let server = spawn_api_server(None).await;
        let client = reqwest::Client::new();
        let created = client
            .post(format!("{}/sessions", server.base_url))
            .json(&persistent_req("p1"))
            .send()
            .await
            .unwrap();
        assert_eq!(created.status(), HttpStatus::OK);
        let created_body = created.text().await.unwrap();
        assert!(!created_body.contains("/takeover/"));
        assert!(!created_body.contains("token="));
        let created_json = serde_json::from_str::<serde_json::Value>(&created_body).unwrap();
        let session_id = created_json["id"]
            .as_str()
            .unwrap()
            .parse::<Uuid>()
            .unwrap();
        assert!(created_json["takeover_url"].is_null());

        let fetched = client
            .get(format!("{}/sessions/{session_id}", server.base_url))
            .send()
            .await
            .unwrap();
        assert_eq!(fetched.status(), HttpStatus::OK);
        let fetched_body = fetched.text().await.unwrap();
        assert!(!fetched_body.contains("/takeover/"));
        assert!(!fetched_body.contains("token="));
        let fetched_json = serde_json::from_str::<serde_json::Value>(&fetched_body).unwrap();
        assert_eq!(fetched_json["status"], "running");
        assert!(fetched_json["takeover_url"].is_null());

        let pre_pause_token = "pre-pause-token";
        let sensitive_text = "card 4111 1111 1111 1111";
        let routes = vec![
            client
                .get(format!(
                    "{}/takeover/{session_id}?token={pre_pause_token}",
                    server.base_url
                ))
                .build()
                .unwrap(),
            client
                .get(format!(
                    "{}/takeover/{session_id}/screenshot?token={pre_pause_token}",
                    server.base_url
                ))
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/takeover/{session_id}/release?token={pre_pause_token}",
                    server.base_url
                ))
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/takeover/{session_id}/click?token={pre_pause_token}",
                    server.base_url
                ))
                .header(reqwest::header::CONTENT_TYPE, "application/json")
                .body("{\"x\":10,\"y\":20}")
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/takeover/{session_id}/type?token={pre_pause_token}",
                    server.base_url
                ))
                .header(reqwest::header::CONTENT_TYPE, "application/json")
                .body(format!("{{\"text\":{sensitive_text:?}}}"))
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/takeover/{session_id}/scroll?token={pre_pause_token}",
                    server.base_url
                ))
                .header(reqwest::header::CONTENT_TYPE, "application/json")
                .body("{\"delta_y\":500}")
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/takeover/{session_id}/key?token={pre_pause_token}",
                    server.base_url
                ))
                .header(reqwest::header::CONTENT_TYPE, "application/json")
                .body("{\"key\":\"Tab\"}")
                .build()
                .unwrap(),
        ];

        for request in routes {
            let response = client.execute(request).await.unwrap();
            let status = response.status();
            let body = response.text().await.unwrap();
            assert_eq!(status, reqwest::StatusCode::FORBIDDEN, "body={body}");
            assert!(body.contains("invalid or expired takeover token"));
            assert!(!body.contains(pre_pause_token));
            assert!(!body.contains(sensitive_text));
        }

        server.store.delete_session(session_id).await.unwrap();
        server.stop().await;
    }

    #[tokio::test]
    async fn crashed_sessions_surface_failed_status_and_release_profile_locks() {
        let server = spawn_short_lived_server(Duration::from_secs(60)).await;
        let client = reqwest::Client::new();
        let created = server
            .store
            .create_session(persistent_req("p1"))
            .await
            .unwrap();

        sleep(Duration::from_millis(150)).await;

        let fetched = client
            .get(format!("{}/sessions/{}", server.base_url, created.id))
            .send()
            .await
            .unwrap();
        assert_eq!(fetched.status(), HttpStatus::OK);
        let fetched_json = fetched.json::<serde_json::Value>().await.unwrap();
        assert_eq!(fetched_json["status"], "failed");
        assert!(fetched_json["cdp_ws_url"].is_null());
        assert!(fetched_json["takeover_url"].is_null());

        let wait = client
            .get(format!(
                "{}/sessions/{}/wait?timeout_ms=1",
                server.base_url, created.id
            ))
            .send()
            .await
            .unwrap();
        assert_eq!(wait.status(), HttpStatus::OK);
        let wait_json = wait.json::<serde_json::Value>().await.unwrap();
        assert_eq!(wait_json["timed_out"], false);
        assert_eq!(wait_json["session"]["status"], "failed");
        assert!(wait_json["session"]["cdp_ws_url"].is_null());

        let profile_delete = client
            .delete(format!("{}/profiles/p1", server.base_url))
            .send()
            .await
            .unwrap();
        assert_eq!(profile_delete.status(), HttpStatus::NO_CONTENT);

        let events_path = server
            .store
            .config
            .data_dir
            .join("sessions")
            .join(created.id.to_string())
            .join("artifacts/events.jsonl");
        let events = fs::read_to_string(events_path).unwrap();
        assert!(events.contains("browser_process_exited"), "{events}");

        server.stop().await;
    }

    #[tokio::test]
    async fn expired_takeover_tokens_are_rejected_without_echoing_secrets() {
        let server = spawn_zero_ttl_server().await;
        let client = reqwest::Client::new();
        let created = server
            .store
            .create_session(persistent_req("p1"))
            .await
            .unwrap();
        let paused = server
            .store
            .pause_for_human(created.id, Some("manual oauth approval".into()))
            .await
            .unwrap();
        let token = token_from_url(paused.takeover_url.as_ref().unwrap()).to_string();

        let page = client
            .get(format!(
                "{}/takeover/{}?token={token}",
                server.base_url, created.id
            ))
            .send()
            .await
            .unwrap();
        assert_eq!(page.status(), HttpStatus::FORBIDDEN);
        let body = page.text().await.unwrap();
        assert!(body.contains("invalid or expired takeover token"));
        assert!(!body.contains(&token));

        let release = client
            .post(format!(
                "{}/takeover/{}/release?token={token}",
                server.base_url, created.id
            ))
            .send()
            .await
            .unwrap();
        assert_eq!(release.status(), HttpStatus::FORBIDDEN);
        let body = release.text().await.unwrap();
        assert!(body.contains("invalid or expired takeover token"));
        assert!(!body.contains(&token));

        server.stop().await;
    }

    #[tokio::test]
    async fn profile_routes_surface_internal_errors_from_filesystem() {
        let server = spawn_fake_server(None).await;
        let client = reqwest::Client::new();
        let profiles_dir = server.store.config.data_dir.join("profiles");

        fs::write(profiles_dir.join("conflict-file"), b"not a dir").unwrap();
        let create = client
            .post(format!("{}/profiles", server.base_url))
            .json(&CreateProfileRequest {
                id: Some("conflict-file".into()),
            })
            .send()
            .await
            .unwrap();
        assert_eq!(create.status(), HttpStatus::INTERNAL_SERVER_ERROR);

        fs::remove_dir_all(&profiles_dir).unwrap();
        fs::write(&profiles_dir, b"not a dir").unwrap();
        let list = client
            .get(format!("{}/profiles", server.base_url))
            .send()
            .await
            .unwrap();
        assert_eq!(list.status(), HttpStatus::INTERNAL_SERVER_ERROR);

        server.stop().await;
    }

    #[tokio::test]
    async fn takeover_routes_accept_valid_tokens_and_drive_cdp_fallbacks() {
        let server = spawn_api_server(None).await;
        let created = server
            .store
            .create_session(persistent_req("p1"))
            .await
            .unwrap();
        let client = reqwest::Client::new();

        let session_screenshot = client
            .get(format!(
                "{}/sessions/{}/screenshot",
                server.base_url, created.id
            ))
            .send()
            .await
            .unwrap();
        assert_eq!(session_screenshot.status(), HttpStatus::OK);
        assert_eq!(
            session_screenshot
                .headers()
                .get(header::CONTENT_TYPE)
                .unwrap(),
            "image/png"
        );
        assert_eq!(session_screenshot.bytes().await.unwrap().as_ref(), b"png");

        let paused = server
            .store
            .pause_for_human(created.id, Some("manual oauth approval".into()))
            .await
            .unwrap();
        let token = token_from_url(paused.takeover_url.as_ref().unwrap()).to_string();

        let page = client
            .get(format!(
                "{}/takeover/{}?token={token}",
                server.base_url, created.id
            ))
            .send()
            .await
            .unwrap();
        assert_eq!(page.status(), HttpStatus::OK);
        assert!(
            page.text()
                .await
                .unwrap()
                .contains("Hermes Browser Runtime takeover")
        );

        let takeover_screenshot = client
            .get(format!(
                "{}/takeover/{}/screenshot?token={token}",
                server.base_url, created.id
            ))
            .send()
            .await
            .unwrap();
        assert_eq!(takeover_screenshot.status(), HttpStatus::OK);
        assert_eq!(
            takeover_screenshot
                .headers()
                .get(header::CONTENT_TYPE)
                .unwrap(),
            "image/png"
        );

        for (path, body) in [
            (
                format!(
                    "{}/takeover/{}/click?token={token}",
                    server.base_url, created.id
                ),
                json!({"x": 10.0, "y": 20.0}),
            ),
            (
                format!(
                    "{}/takeover/{}/type?token={token}",
                    server.base_url, created.id
                ),
                json!({"text": "hello world"}),
            ),
            (
                format!(
                    "{}/takeover/{}/key?token={token}",
                    server.base_url, created.id
                ),
                json!({"key": "Tab"}),
            ),
            (
                format!(
                    "{}/takeover/{}/scroll?token={token}",
                    server.base_url, created.id
                ),
                json!({}),
            ),
        ] {
            let response = client.post(path).json(&body).send().await.unwrap();
            assert_eq!(response.status(), HttpStatus::OK);
            let json = response.json::<serde_json::Value>().await.unwrap();
            assert_eq!(json["ok"], serde_json::Value::Bool(true));
        }

        let release = client
            .post(format!(
                "{}/takeover/{}/release?token={token}",
                server.base_url, created.id
            ))
            .send()
            .await
            .unwrap();
        assert_eq!(release.status(), HttpStatus::OK);
        let body = release.json::<serde_json::Value>().await.unwrap();
        assert_eq!(body["status"], "running");
        assert!(body["takeover_url"].is_null());

        let post_release = client
            .get(format!(
                "{}/takeover/{}?token={token}",
                server.base_url, created.id
            ))
            .send()
            .await
            .unwrap();
        assert_eq!(post_release.status(), HttpStatus::FORBIDDEN);
        let post_release_body = post_release.text().await.unwrap();
        assert!(post_release_body.contains("invalid or expired takeover token"));
        assert!(!post_release_body.contains(&token));

        let commands = server.cdp.recorded_commands().await;
        assert!(
            commands
                .iter()
                .filter(|command| command.method == "Page.captureScreenshot")
                .count()
                >= 2
        );
        assert!(
            commands
                .iter()
                .any(|command| command.method == "Input.insertText")
        );
        assert!(
            commands
                .iter()
                .any(|command| command.method == "Input.dispatchKeyEvent")
        );
        assert!(commands.iter().any(|command| {
            command.method == "Input.dispatchMouseEvent"
                && command.params["deltaY"] == 500.0
                && command.params["deltaX"] == 0.0
        }));

        server.store.delete_session(created.id).await.unwrap();
        server.stop().await;
    }

    #[tokio::test]
    async fn takeover_input_routes_surface_cdp_errors_after_token_validation() {
        let server = spawn_api_server(None).await;
        let created = server
            .store
            .create_session(persistent_req("p1"))
            .await
            .unwrap();
        let paused = server
            .store
            .pause_for_human(created.id, Some("manual oauth approval".into()))
            .await
            .unwrap();
        let token = token_from_url(paused.takeover_url.as_ref().unwrap()).to_string();
        server
            .cdp
            .set_list_response(MockEndpointResponse::Text(
                HttpStatus::INTERNAL_SERVER_ERROR,
                "cdp list failed".into(),
            ))
            .await;

        let client = reqwest::Client::new();
        for (path, body) in [
            (
                format!(
                    "{}/takeover/{}/click?token={token}",
                    server.base_url, created.id
                ),
                json!({"x": 10.0, "y": 20.0}),
            ),
            (
                format!(
                    "{}/takeover/{}/type?token={token}",
                    server.base_url, created.id
                ),
                json!({"text": "hello world"}),
            ),
            (
                format!(
                    "{}/takeover/{}/key?token={token}",
                    server.base_url, created.id
                ),
                json!({"key": "Tab"}),
            ),
            (
                format!(
                    "{}/takeover/{}/scroll?token={token}",
                    server.base_url, created.id
                ),
                json!({}),
            ),
        ] {
            let response = client.post(path).json(&body).send().await.unwrap();
            assert_eq!(response.status(), HttpStatus::INTERNAL_SERVER_ERROR);
            assert!(
                !response.json::<serde_json::Value>().await.unwrap()["error"]
                    .as_str()
                    .unwrap()
                    .is_empty()
            );
        }

        server.store.delete_session(created.id).await.unwrap();
        server.stop().await;
    }

    #[tokio::test]
    async fn takeover_release_surfaces_store_errors_after_token_validation() {
        let server = spawn_api_server(None).await;
        let created = server
            .store
            .create_session(persistent_req("p1"))
            .await
            .unwrap();
        let paused = server
            .store
            .pause_for_human(created.id, Some("manual oauth approval".into()))
            .await
            .unwrap();
        let token = token_from_url(paused.takeover_url.as_ref().unwrap()).to_string();
        let artifacts_dir = server
            .store
            .config
            .data_dir
            .join("sessions")
            .join(created.id.to_string())
            .join("artifacts");
        fs::remove_dir_all(&artifacts_dir).unwrap();
        fs::write(&artifacts_dir, b"not a directory").unwrap();

        let response = reqwest::Client::new()
            .post(format!(
                "{}/takeover/{}/release?token={token}",
                server.base_url, created.id
            ))
            .send()
            .await
            .unwrap();
        assert_eq!(response.status(), HttpStatus::INTERNAL_SERVER_ERROR);
        assert!(
            !response.json::<serde_json::Value>().await.unwrap()["error"]
                .as_str()
                .unwrap()
                .is_empty()
        );

        fs::remove_file(&artifacts_dir).unwrap();
        fs::create_dir_all(&artifacts_dir).unwrap();
        server.store.delete_session(created.id).await.unwrap();
        server.stop().await;
    }

    #[tokio::test]
    async fn takeover_routes_reject_invalid_tokens_without_echoing_secrets() {
        let server = spawn_api_server(None).await;
        let created = server
            .store
            .create_session(persistent_req("p1"))
            .await
            .unwrap();
        server
            .store
            .pause_for_human(created.id, Some("manual oauth approval".into()))
            .await
            .unwrap();

        let wrong_token = "wrong-token";
        let sensitive_text = "card 4111 1111 1111 1111";
        let client = reqwest::Client::new();
        let routes = vec![
            client
                .get(format!(
                    "{}/takeover/{}?token={wrong_token}",
                    server.base_url, created.id
                ))
                .build()
                .unwrap(),
            client
                .get(format!(
                    "{}/takeover/{}/screenshot?token={wrong_token}",
                    server.base_url, created.id
                ))
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/takeover/{}/release?token={wrong_token}",
                    server.base_url, created.id
                ))
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/takeover/{}/click?token={wrong_token}",
                    server.base_url, created.id
                ))
                .header(reqwest::header::CONTENT_TYPE, "application/json")
                .body("{\"x\":10,\"y\":20}")
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/takeover/{}/type?token={wrong_token}",
                    server.base_url, created.id
                ))
                .header(reqwest::header::CONTENT_TYPE, "application/json")
                .body(format!("{{\"text\":{sensitive_text:?}}}"))
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/takeover/{}/scroll?token={wrong_token}",
                    server.base_url, created.id
                ))
                .header(reqwest::header::CONTENT_TYPE, "application/json")
                .body("{\"delta_y\":500}")
                .build()
                .unwrap(),
            client
                .post(format!(
                    "{}/takeover/{}/key?token={wrong_token}",
                    server.base_url, created.id
                ))
                .header(reqwest::header::CONTENT_TYPE, "application/json")
                .body("{\"key\":\"Tab\"}")
                .build()
                .unwrap(),
        ];

        for request in routes {
            let response = client.execute(request).await.unwrap();
            let status = response.status();
            let body = response.text().await.unwrap();
            assert_eq!(status, reqwest::StatusCode::FORBIDDEN, "body={body}");
            assert!(body.contains("invalid or expired takeover token"));
            assert!(!body.contains(wrong_token));
            assert!(!body.contains(sensitive_text));
        }

        server.store.delete_session(created.id).await.unwrap();
        server.stop().await;
    }

    #[tokio::test]
    async fn wait_endpoint_returns_running_after_release() {
        let server = spawn_api_server(None).await;
        let created = server
            .store
            .create_session(persistent_req("p1"))
            .await
            .unwrap();
        let paused = server
            .store
            .pause_for_human(created.id, Some("manual oauth approval".into()))
            .await
            .unwrap();
        assert_eq!(paused.status, SessionStatus::PausedForHuman);

        let store = server.store.clone();
        let session_id = created.id;
        let releaser = tokio::spawn(async move {
            sleep(Duration::from_millis(25)).await;
            store.release(session_id).await.unwrap();
        });

        let response = reqwest::Client::new()
            .get(format!(
                "{}/sessions/{session_id}/wait?timeout_ms=500",
                server.base_url
            ))
            .send()
            .await
            .unwrap();

        assert_eq!(response.status(), reqwest::StatusCode::OK);
        let body = response.json::<serde_json::Value>().await.unwrap();
        assert_eq!(body["timed_out"], serde_json::Value::Bool(false));
        assert_eq!(body["session"]["id"], created.id.to_string());
        assert_eq!(body["session"]["status"], "running");

        releaser.await.unwrap();
        server.store.delete_session(created.id).await.unwrap();
        server.stop().await;
    }

    #[tokio::test]
    async fn wait_endpoint_reports_timeout_when_session_stays_paused() {
        let server = spawn_api_server(None).await;
        let created = server
            .store
            .create_session(persistent_req("p1"))
            .await
            .unwrap();
        let paused = server
            .store
            .pause_for_human(created.id, Some("manual oauth approval".into()))
            .await
            .unwrap();
        assert_eq!(paused.status, SessionStatus::PausedForHuman);

        let response = reqwest::Client::new()
            .get(format!(
                "{}/sessions/{}/wait?timeout_ms=10",
                server.base_url, created.id
            ))
            .send()
            .await
            .unwrap();

        assert_eq!(response.status(), reqwest::StatusCode::OK);
        let body = response.json::<serde_json::Value>().await.unwrap();
        assert_eq!(body["timed_out"], serde_json::Value::Bool(true));
        assert_eq!(body["session"]["status"], "paused_for_human");
        assert!(body["session"]["takeover_url"].as_str().is_some());

        server.store.delete_session(created.id).await.unwrap();
        server.stop().await;
    }

    #[tokio::test]
    async fn wait_endpoint_requires_auth() {
        let server = spawn_api_server(Some("secret-token")).await;
        let created = server
            .store
            .create_session(persistent_req("p1"))
            .await
            .unwrap();

        let response = reqwest::Client::new()
            .get(format!(
                "{}/sessions/{}/wait?timeout_ms=1",
                server.base_url, created.id
            ))
            .send()
            .await
            .unwrap();

        assert_eq!(response.status(), reqwest::StatusCode::UNAUTHORIZED);
        let body = response.json::<serde_json::Value>().await.unwrap();
        assert_eq!(body["error"], "unauthorized");

        server.store.delete_session(created.id).await.unwrap();
        server.stop().await;
    }

    #[tokio::test]
    async fn download_routes_list_files_and_reject_path_traversal() {
        let server = spawn_api_server(None).await;
        let client = reqwest::Client::new();
        let created = server
            .store
            .create_session(persistent_req("p1"))
            .await
            .unwrap();
        let downloads_dir = server.store.downloads_dir(created.id).await.unwrap();
        fs::write(downloads_dir.join("report.txt"), b"hello").unwrap();

        let listed = client
            .get(format!(
                "{}/sessions/{}/downloads",
                server.base_url, created.id
            ))
            .send()
            .await
            .unwrap();
        assert_eq!(listed.status(), reqwest::StatusCode::OK);
        let body: serde_json::Value = listed.json().await.unwrap();
        assert_eq!(body["downloads"][0]["name"], "report.txt");
        assert_eq!(body["downloads"][0]["size_bytes"], 5);

        let fetched = client
            .get(format!(
                "{}/sessions/{}/download",
                server.base_url, created.id
            ))
            .query(&[("name", "report.txt")])
            .send()
            .await
            .unwrap();
        assert_eq!(fetched.status(), reqwest::StatusCode::OK);
        assert_eq!(fetched.bytes().await.unwrap(), b"hello".as_slice());

        let bad = client
            .get(format!(
                "{}/sessions/{}/download",
                server.base_url, created.id
            ))
            .query(&[("name", "../secrets.txt")])
            .send()
            .await
            .unwrap();
        assert_eq!(bad.status(), reqwest::StatusCode::BAD_REQUEST);
        let error: serde_json::Value = bad.json().await.unwrap();
        assert_eq!(error["error"], "invalid download name");
        assert!(!error.to_string().contains("../secrets.txt"));

        server.store.delete_session(created.id).await.unwrap();
        server.stop().await;
    }
}
