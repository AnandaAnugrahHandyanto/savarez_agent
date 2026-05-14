use std::{
    collections::HashMap,
    fs,
    net::TcpListener as StdTcpListener,
    process::{Command, Stdio},
    sync::Arc,
    time::Duration,
};

use anyhow::{Result, bail};
use async_trait::async_trait;
use axum::{
    Json, Router,
    extract::{Path, Query, State},
    http::{HeaderMap, header},
    response::IntoResponse,
    routing::{get, post},
};
use chrono::Utc;
use hermes_browser_runtime::{
    api,
    backend::{BrowserBackend, LaunchedBrowser, StartSessionOptions},
    config::RuntimeConfig,
    credentials::{CredentialBrokerMode, CredentialFillStatus},
    models::{
        BrowserPersona, CaptchaPolicy, CaptchaStatus, CredentialFillStatusRecord,
        CredentialPrivacyGuardResponse, SessionInfo, SessionStatus, Viewport, WaitSessionResponse,
    },
    store::AppStore,
};
use tokio::{net::TcpListener, sync::Mutex};
use uuid::Uuid;

struct UnusedBackend;

#[async_trait]
impl BrowserBackend for UnusedBackend {
    async fn launch(&self, _options: StartSessionOptions) -> Result<LaunchedBrowser> {
        bail!("launch should not be called in this binary smoke test")
    }

    async fn close(&self, _launched: &mut LaunchedBrowser) -> Result<()> {
        Ok(())
    }
}

struct RunningApiServer {
    _tempdir: tempfile::TempDir,
    task: tokio::task::JoinHandle<()>,
    base_url: String,
}

impl RunningApiServer {
    async fn spawn(bearer_token: Option<&str>) -> Self {
        let tempdir = tempfile::tempdir().unwrap();
        let store = Arc::new(
            AppStore::new(
                RuntimeConfig {
                    bind: "127.0.0.1:7788".parse().unwrap(),
                    data_dir: tempdir.path().to_path_buf(),
                    chrome_path: Some(tempdir.path().join("unused-chrome")),
                    bearer_token: bearer_token.map(str::to_owned),
                    operator_token: None,
                    default_headless: true,
                    artifact_retention: Duration::from_secs(60),
                    takeover_ttl: Duration::from_secs(60),
                    launch_timeout: Duration::from_secs(15),
                    captcha_solver_enabled: false,
                    default_captcha_policy: CaptchaPolicy::HumanOnly,
                    captcha_solver_policy_path: None,
                    captcha_solver_provider_order: "capsolver".to_string(),
                    captcha_solver_timeout: Duration::from_secs(120),
                    captcha_solver_poll_interval: Duration::from_millis(3000),
                    captcha_solver_verify_timeout: Duration::from_secs(20),
                    captcha_solver_max_attempts: 2,
                    captcha_solver_max_cost_usd_per_session: 0.25,
                    captcha_solver_provider_key_available: false,
                    credential_provider: Default::default(),
                    credential_policy_path: None,
                    op_path: None,
                    op_timeout: Duration::from_secs(5),
                    credential_approval_ttl: Duration::from_secs(300),
                    credential_privacy_guard: true,
                    default_webrtc_ip_policy: Default::default(),
                    default_gpu_policy: Default::default(),
                    default_persona: BrowserPersona::default(),
                },
                Arc::new(UnusedBackend),
            )
            .await
            .unwrap(),
        );

        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let base_url = format!("http://{}", listener.local_addr().unwrap());
        let task = tokio::spawn(async move {
            axum::serve(listener, api::router(store)).await.unwrap();
        });

        Self {
            _tempdir: tempdir,
            task,
            base_url,
        }
    }

    async fn stop(self) {
        self.task.abort();
        let _ = self.task.await;
    }
}

struct RunningRouter {
    task: tokio::task::JoinHandle<()>,
    base_url: String,
}

impl RunningRouter {
    async fn spawn(router: Router) -> Self {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let base_url = format!("http://{}", listener.local_addr().unwrap());
        let task = tokio::spawn(async move {
            axum::serve(listener, router).await.unwrap();
        });
        Self { task, base_url }
    }

    async fn stop(self) {
        self.task.abort();
        let _ = self.task.await;
    }
}

async fn run_binary(args: &[&str], envs: &[(&str, &str)]) -> std::process::Output {
    let bin = std::env::var("CARGO_BIN_EXE_hermes-browser-runtime").unwrap();
    let args = args.iter().map(|arg| (*arg).to_owned()).collect::<Vec<_>>();
    let envs = envs
        .iter()
        .map(|(key, value)| ((*key).to_owned(), (*value).to_owned()))
        .collect::<Vec<_>>();

    tokio::task::spawn_blocking(move || {
        let mut command = Command::new(bin);
        command.args(&args);
        for (key, value) in envs {
            command.env(key, value);
        }
        command.output().unwrap()
    })
    .await
    .unwrap()
}

async fn wait_for_http_ready(url: &str) -> bool {
    for _ in 0..80 {
        if let Ok(response) = reqwest::get(url).await
            && response.status().is_success()
        {
            return true;
        }
        tokio::time::sleep(Duration::from_millis(25)).await;
    }

    false
}

#[cfg(unix)]
async fn wait_for_child_exit(child: &mut std::process::Child) -> Option<std::process::ExitStatus> {
    for _ in 0..80 {
        if let Ok(Some(status)) = child.try_wait() {
            return Some(status);
        }
        tokio::time::sleep(Duration::from_millis(25)).await;
    }

    None
}

fn authorization_header(headers: &HeaderMap) -> Option<String> {
    headers
        .get(header::AUTHORIZATION)
        .and_then(|value| value.to_str().ok())
        .map(str::to_owned)
}

fn session_info_with_captcha(
    session_id: Uuid,
    status: SessionStatus,
    captcha_status: CaptchaStatus,
) -> SessionInfo {
    SessionInfo {
        id: session_id,
        status,
        cdp_ws_url: None,
        takeover_url: None,
        profile_id: "p1".into(),
        persist_profile: true,
        headless: true,
        viewport: Viewport::default(),
        created_at: Utc::now(),
        updated_at: Utc::now(),
        pause_reason: None,
        webrtc_ip_policy: Default::default(),
        gpu_policy: Default::default(),
        captcha_policy: Default::default(),
        captcha_status,
        captcha_challenge_type: None,
        captcha_solver_status: None,
    }
}

#[derive(Clone, Default)]
struct CommandCapture {
    wait_auth: Arc<Mutex<Option<String>>>,
    wait_timeout_ms: Arc<Mutex<Option<String>>>,
    screenshot_auth: Arc<Mutex<Option<String>>>,
    credential_request_auth: Arc<Mutex<Option<String>>>,
    credential_request_body: Arc<Mutex<Option<serde_json::Value>>>,
    credential_status_auth: Arc<Mutex<Option<String>>>,
    credential_approve_auth: Arc<Mutex<Option<String>>>,
    credential_approve_body: Arc<Mutex<Option<serde_json::Value>>>,
    credential_deny_auth: Arc<Mutex<Option<String>>>,
    credential_deny_body: Arc<Mutex<Option<serde_json::Value>>>,
    credential_clear_auth: Arc<Mutex<Option<String>>>,
    captcha_report_auth: Arc<Mutex<Option<String>>>,
    captcha_report_body: Arc<Mutex<Option<serde_json::Value>>>,
    captcha_resolve_auth: Arc<Mutex<Option<String>>>,
    captcha_resolve_body: Arc<Mutex<Option<serde_json::Value>>>,
}

async fn wait_handler(
    State(capture): State<CommandCapture>,
    Path(session_id): Path<Uuid>,
    Query(params): Query<HashMap<String, String>>,
    headers: HeaderMap,
) -> Json<WaitSessionResponse> {
    *capture.wait_auth.lock().await = authorization_header(&headers);
    *capture.wait_timeout_ms.lock().await = params.get("timeout_ms").cloned();

    Json(WaitSessionResponse {
        timed_out: true,
        session: SessionInfo {
            id: session_id,
            status: SessionStatus::PausedForHuman,
            cdp_ws_url: None,
            takeover_url: Some(format!(
                "http://127.0.0.1:7788/takeover/{session_id}?token=***"
            )),
            profile_id: "p1".into(),
            persist_profile: true,
            headless: true,
            viewport: Viewport::default(),
            created_at: Utc::now(),
            updated_at: Utc::now(),
            pause_reason: Some("manual oauth approval".into()),
            webrtc_ip_policy: Default::default(),
            gpu_policy: Default::default(),
            captcha_policy: Default::default(),
            captcha_status: Default::default(),
            captcha_challenge_type: None,
            captcha_solver_status: None,
        },
    })
}

async fn screenshot_handler(
    State(capture): State<CommandCapture>,
    Path(_session_id): Path<Uuid>,
    headers: HeaderMap,
) -> impl IntoResponse {
    *capture.screenshot_auth.lock().await = authorization_header(&headers);
    ([(header::CONTENT_TYPE, "image/png")], b"png".to_vec())
}

fn credential_record(
    session_id: Uuid,
    request_id: Uuid,
    status: CredentialFillStatus,
) -> CredentialFillStatusRecord {
    CredentialFillStatusRecord {
        request_id,
        session_id,
        alias: "demo-login".into(),
        observed_origin: "https://example.test".into(),
        status,
        broker: CredentialBrokerMode::Mock,
        audit_id: Uuid::new_v4(),
        privacy_guard_active: false,
        created_at: Utc::now(),
        updated_at: Utc::now(),
        redacted_message: None,
    }
}

async fn credential_request_handler(
    State(capture): State<CommandCapture>,
    Path(session_id): Path<Uuid>,
    headers: HeaderMap,
    Json(body): Json<serde_json::Value>,
) -> Json<CredentialFillStatusRecord> {
    *capture.credential_request_auth.lock().await = authorization_header(&headers);
    *capture.credential_request_body.lock().await = Some(body);

    Json(credential_record(
        session_id,
        Uuid::new_v4(),
        CredentialFillStatus::RequiresUserApproval,
    ))
}

async fn credential_status_handler(
    State(capture): State<CommandCapture>,
    Path((session_id, request_id)): Path<(Uuid, Uuid)>,
    headers: HeaderMap,
) -> Json<CredentialFillStatusRecord> {
    *capture.credential_status_auth.lock().await = authorization_header(&headers);
    Json(credential_record(
        session_id,
        request_id,
        CredentialFillStatus::RequiresUserApproval,
    ))
}

async fn credential_approve_handler(
    State(capture): State<CommandCapture>,
    Path((session_id, request_id)): Path<(Uuid, Uuid)>,
    headers: HeaderMap,
    Json(body): Json<serde_json::Value>,
) -> Json<CredentialFillStatusRecord> {
    *capture.credential_approve_auth.lock().await = authorization_header(&headers);
    *capture.credential_approve_body.lock().await = Some(body);
    Json(credential_record(
        session_id,
        request_id,
        CredentialFillStatus::Approved,
    ))
}

async fn credential_deny_handler(
    State(capture): State<CommandCapture>,
    Path((session_id, request_id)): Path<(Uuid, Uuid)>,
    headers: HeaderMap,
    Json(body): Json<serde_json::Value>,
) -> Json<CredentialFillStatusRecord> {
    *capture.credential_deny_auth.lock().await = authorization_header(&headers);
    *capture.credential_deny_body.lock().await = Some(body);
    Json(credential_record(
        session_id,
        request_id,
        CredentialFillStatus::Denied,
    ))
}

async fn credential_clear_handler(
    State(capture): State<CommandCapture>,
    Path(session_id): Path<Uuid>,
    headers: HeaderMap,
) -> Json<CredentialPrivacyGuardResponse> {
    *capture.credential_clear_auth.lock().await = authorization_header(&headers);
    Json(CredentialPrivacyGuardResponse {
        session_id,
        privacy_guard_active: false,
    })
}

async fn captcha_report_handler(
    State(capture): State<CommandCapture>,
    Path(session_id): Path<Uuid>,
    headers: HeaderMap,
    Json(body): Json<serde_json::Value>,
) -> Json<SessionInfo> {
    *capture.captcha_report_auth.lock().await = authorization_header(&headers);
    *capture.captcha_report_body.lock().await = Some(body);
    Json(session_info_with_captcha(
        session_id,
        SessionStatus::PausedForHuman,
        CaptchaStatus::HumanRequired,
    ))
}

async fn captcha_resolve_handler(
    State(capture): State<CommandCapture>,
    Path(session_id): Path<Uuid>,
    headers: HeaderMap,
    Json(body): Json<serde_json::Value>,
) -> Json<SessionInfo> {
    *capture.captcha_resolve_auth.lock().await = authorization_header(&headers);
    *capture.captcha_resolve_body.lock().await = Some(body);
    let mut session = session_info_with_captcha(
        session_id,
        SessionStatus::PausedForHuman,
        CaptchaStatus::Resolved,
    );
    session.takeover_url = Some("http://127.0.0.1/takeover/redacted".into());
    session.pause_reason = Some("human checkpoint remains paused after CAPTCHA resolution".into());
    Json(session)
}

#[tokio::test]
async fn binary_profiles_list_executes_main_and_cli_run() {
    let server = RunningApiServer::spawn(None).await;
    let base_url = server.base_url.clone();

    let output = run_binary(
        &["profiles", "list", "--server", base_url.as_str()],
        &[("HBR_SERVER", "http://127.0.0.1:1")],
    )
    .await;

    assert!(
        output.status.success(),
        "stderr={}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "[]");

    server.stop().await;
}

#[tokio::test]
async fn binary_profiles_list_honors_env_server_and_token() {
    let server = RunningApiServer::spawn(Some("secret-token")).await;
    let base_url = server.base_url.clone();

    let output = run_binary(
        &["profiles", "list"],
        &[
            ("HBR_SERVER", base_url.as_str()),
            ("HBR_BEARER_TOKEN", "secret-token"),
        ],
    )
    .await;

    assert!(
        output.status.success(),
        "stderr={}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "[]");

    server.stop().await;
}

#[tokio::test]
async fn binary_profiles_list_surfaces_auth_error_without_token() {
    let server = RunningApiServer::spawn(Some("secret-token")).await;
    let base_url = server.base_url.clone();

    let output = run_binary(&["profiles", "list", "--server", base_url.as_str()], &[]).await;
    let stderr = String::from_utf8_lossy(&output.stderr);
    let stderr_lower = stderr.to_ascii_lowercase();

    assert!(
        !output.status.success(),
        "stdout={}",
        String::from_utf8_lossy(&output.stdout)
    );
    assert!(stderr.contains("401"));
    assert!(!stderr.contains("secret-token"));
    assert!(!stderr_lower.contains("authorization"));

    server.stop().await;
}

#[tokio::test]
async fn binary_wait_and_screenshot_commands_preserve_auth_query_and_output_shape() {
    let capture = CommandCapture::default();
    let server = RunningRouter::spawn(
        Router::new()
            .route("/sessions/:id/wait", get(wait_handler))
            .route("/sessions/:id/screenshot", get(screenshot_handler))
            .with_state(capture.clone()),
    )
    .await;
    let base_url = server.base_url.clone();
    let session_id = Uuid::new_v4();
    let session_id_string = session_id.to_string();

    let wait_output = run_binary(
        &[
            "sessions",
            "wait",
            session_id_string.as_str(),
            "--server",
            base_url.as_str(),
            "--bearer-token",
            "secret-token",
            "--timeout-secs",
            "2",
        ],
        &[],
    )
    .await;

    assert!(
        wait_output.status.success(),
        "stderr={}",
        String::from_utf8_lossy(&wait_output.stderr)
    );
    let wait_json: serde_json::Value = serde_json::from_slice(&wait_output.stdout).unwrap();
    assert_eq!(wait_json["timed_out"], true);
    assert_eq!(wait_json["session"]["id"], session_id_string);
    assert_eq!(
        capture.wait_timeout_ms.lock().await.clone().as_deref(),
        Some("2000")
    );
    assert_eq!(
        capture.wait_auth.lock().await.clone().as_deref(),
        Some("Bearer secret-token")
    );

    let shot_dir = tempfile::tempdir().unwrap();
    let shot_path = shot_dir.path().join("cli-shot.png");
    let shot_path_string = shot_path.display().to_string();
    let screenshot_output = run_binary(
        &[
            "sessions",
            "screenshot",
            session_id_string.as_str(),
            "--server",
            base_url.as_str(),
            "--bearer-token",
            "secret-token",
            "--output",
            shot_path_string.as_str(),
        ],
        &[],
    )
    .await;

    assert!(
        screenshot_output.status.success(),
        "stderr={}",
        String::from_utf8_lossy(&screenshot_output.stderr)
    );
    assert_eq!(
        String::from_utf8_lossy(&screenshot_output.stdout).trim(),
        shot_path_string
    );
    assert_eq!(fs::read(&shot_path).unwrap(), b"png");
    assert_eq!(
        capture.screenshot_auth.lock().await.clone().as_deref(),
        Some("Bearer secret-token")
    );

    server.stop().await;
}

#[tokio::test]
async fn binary_sessions_credentials_commands_preserve_auth_and_json_shape() {
    let capture = CommandCapture::default();
    let server = RunningRouter::spawn(
        Router::new()
            .route(
                "/sessions/:id/credentials/fill",
                post(credential_request_handler),
            )
            .route(
                "/sessions/:id/credentials/fill/:request_id",
                get(credential_status_handler),
            )
            .route(
                "/sessions/:id/credentials/fill/:request_id/approve",
                post(credential_approve_handler),
            )
            .route(
                "/sessions/:id/credentials/fill/:request_id/deny",
                post(credential_deny_handler),
            )
            .route(
                "/sessions/:id/credentials/privacy-guard/clear",
                post(credential_clear_handler),
            )
            .with_state(capture.clone()),
    )
    .await;
    let base_url = server.base_url.clone();
    let session_id = Uuid::new_v4();
    let request_id = Uuid::new_v4();
    let session_id_string = session_id.to_string();
    let request_id_string = request_id.to_string();

    let request_output = run_binary(
        &[
            "sessions",
            "credentials",
            "request",
            session_id_string.as_str(),
            "--alias",
            "demo-login",
            "--username-selector",
            "#user",
            "--password-selector",
            "#pass",
            "--server",
            base_url.as_str(),
            "--bearer-token",
            "secret-token",
        ],
        &[],
    )
    .await;
    assert!(
        request_output.status.success(),
        "stderr={}",
        String::from_utf8_lossy(&request_output.stderr)
    );
    let request_json: serde_json::Value = serde_json::from_slice(&request_output.stdout).unwrap();
    assert_eq!(request_json["session_id"], session_id_string);
    assert_eq!(request_json["alias"], "demo-login");
    assert_eq!(request_json["status"], "requires_user_approval");
    assert_eq!(
        capture
            .credential_request_auth
            .lock()
            .await
            .clone()
            .as_deref(),
        Some("Bearer secret-token")
    );
    let request_body = capture
        .credential_request_body
        .lock()
        .await
        .clone()
        .unwrap();
    assert_eq!(request_body["alias"], "demo-login");
    assert_eq!(request_body["username_selector"], "#user");
    assert_eq!(request_body["password_selector"], "#pass");

    let status_output = run_binary(
        &[
            "sessions",
            "credentials",
            "status",
            session_id_string.as_str(),
            request_id_string.as_str(),
            "--server",
            base_url.as_str(),
            "--bearer-token",
            "secret-token",
        ],
        &[],
    )
    .await;
    assert!(
        status_output.status.success(),
        "stderr={}",
        String::from_utf8_lossy(&status_output.stderr)
    );
    let status_json: serde_json::Value = serde_json::from_slice(&status_output.stdout).unwrap();
    assert_eq!(status_json["request_id"], request_id_string);
    assert_eq!(
        capture
            .credential_status_auth
            .lock()
            .await
            .clone()
            .as_deref(),
        Some("Bearer secret-token")
    );

    let approve_output = run_binary(
        &[
            "sessions",
            "credentials",
            "approve",
            session_id_string.as_str(),
            request_id_string.as_str(),
            "--server",
            base_url.as_str(),
            "--operator-token",
            "operator-token",
            "--note",
            "operator approved",
        ],
        &[],
    )
    .await;
    assert!(
        approve_output.status.success(),
        "stderr={}",
        String::from_utf8_lossy(&approve_output.stderr)
    );
    let approve_json: serde_json::Value = serde_json::from_slice(&approve_output.stdout).unwrap();
    assert_eq!(approve_json["status"], "approved");
    assert_eq!(
        capture
            .credential_approve_auth
            .lock()
            .await
            .clone()
            .as_deref(),
        Some("Bearer operator-token")
    );
    let approve_body = capture
        .credential_approve_body
        .lock()
        .await
        .clone()
        .unwrap();
    assert_eq!(approve_body["note"], "operator approved");

    let deny_output = run_binary(
        &[
            "sessions",
            "credentials",
            "deny",
            session_id_string.as_str(),
            request_id_string.as_str(),
            "--server",
            base_url.as_str(),
            "--operator-token",
            "operator-token",
            "--reason",
            "operator denied",
        ],
        &[],
    )
    .await;
    assert!(
        deny_output.status.success(),
        "stderr={}",
        String::from_utf8_lossy(&deny_output.stderr)
    );
    let deny_json: serde_json::Value = serde_json::from_slice(&deny_output.stdout).unwrap();
    assert_eq!(deny_json["status"], "denied");
    assert_eq!(
        capture.credential_deny_auth.lock().await.clone().as_deref(),
        Some("Bearer operator-token")
    );
    let deny_body = capture.credential_deny_body.lock().await.clone().unwrap();
    assert_eq!(deny_body["reason"], "operator denied");
    assert!(deny_body.get("note").is_none());

    let clear_output = run_binary(
        &[
            "sessions",
            "credentials",
            "clear-privacy-guard",
            session_id_string.as_str(),
            "--server",
            base_url.as_str(),
            "--operator-token",
            "operator-token",
        ],
        &[],
    )
    .await;
    assert!(
        clear_output.status.success(),
        "stderr={}",
        String::from_utf8_lossy(&clear_output.stderr)
    );
    let clear_json: serde_json::Value = serde_json::from_slice(&clear_output.stdout).unwrap();
    assert_eq!(clear_json["session_id"], session_id_string);
    assert_eq!(clear_json["privacy_guard_active"], false);
    assert_eq!(
        capture
            .credential_clear_auth
            .lock()
            .await
            .clone()
            .as_deref(),
        Some("Bearer operator-token")
    );

    server.stop().await;
}

#[tokio::test]
async fn binary_sessions_captcha_report_and_resolve_preserve_auth_and_json_shape() {
    let session_id = Uuid::new_v4();
    let session_id_string = session_id.to_string();
    let capture = CommandCapture::default();
    let router = Router::new()
        .route(
            "/sessions/:session_id/captcha/report",
            post(captcha_report_handler),
        )
        .route(
            "/sessions/:session_id/captcha/resolve",
            post(captcha_resolve_handler),
        )
        .with_state(capture.clone());
    let server = RunningRouter::spawn(router).await;
    let base_url = server.base_url.clone();

    let report_output = run_binary(
        &[
            "sessions",
            "captcha",
            "report",
            session_id_string.as_str(),
            "--server",
            base_url.as_str(),
            "--bearer-token",
            "secret-token",
            "--state",
            "human-required",
            "--challenge-type",
            "hcaptcha",
            "--reason",
            "checkpoint detected",
        ],
        &[],
    )
    .await;
    assert!(
        report_output.status.success(),
        "stderr={}",
        String::from_utf8_lossy(&report_output.stderr)
    );
    let report_json: serde_json::Value = serde_json::from_slice(&report_output.stdout).unwrap();
    assert_eq!(report_json["status"], "paused_for_human");
    assert_eq!(report_json["captcha_status"], "human_required");
    assert_eq!(
        capture.captcha_report_auth.lock().await.clone().as_deref(),
        Some("Bearer secret-token")
    );
    let report_body = capture.captcha_report_body.lock().await.clone().unwrap();
    assert_eq!(report_body["state"], "human_required");
    assert_eq!(report_body["challenge_type"], "hcaptcha");
    assert_eq!(report_body["reason"], "checkpoint detected");

    let resolve_output = run_binary(
        &[
            "sessions",
            "captcha",
            "resolve",
            session_id_string.as_str(),
            "--server",
            base_url.as_str(),
            "--bearer-token",
            "secret-token",
            "--outcome",
            "resolved",
            "--note",
            "operator solved",
        ],
        &[],
    )
    .await;
    assert!(
        resolve_output.status.success(),
        "stderr={}",
        String::from_utf8_lossy(&resolve_output.stderr)
    );
    let resolve_json: serde_json::Value = serde_json::from_slice(&resolve_output.stdout).unwrap();
    assert_eq!(resolve_json["status"], "paused_for_human");
    assert_eq!(resolve_json["captcha_status"], "resolved");
    assert!(resolve_json["takeover_url"].as_str().is_some());
    assert!(resolve_json["pause_reason"].as_str().is_some());
    assert_eq!(
        capture.captcha_resolve_auth.lock().await.clone().as_deref(),
        Some("Bearer secret-token")
    );
    let resolve_body = capture.captcha_resolve_body.lock().await.clone().unwrap();
    assert_eq!(resolve_body["outcome"], "resolved");
    assert_eq!(resolve_body["note"], "operator solved");

    server.stop().await;
}

#[cfg(unix)]
#[tokio::test]
async fn binary_serve_exits_when_sent_sigterm() {
    let reserved = StdTcpListener::bind("127.0.0.1:0").unwrap();
    let port = reserved.local_addr().unwrap().port();
    drop(reserved);

    let tempdir = tempfile::tempdir().unwrap();
    let data_dir = tempdir.path().join("data");
    let chrome_path = tempdir.path().join("unused-chrome");
    let bind = format!("127.0.0.1:{port}");
    let bin = std::env::var("CARGO_BIN_EXE_hermes-browser-runtime").unwrap();
    let mut child = Command::new(bin)
        .args([
            "server",
            "--bind",
            bind.as_str(),
            "--data-dir",
            data_dir.to_str().unwrap(),
            "--chrome-path",
            chrome_path.to_str().unwrap(),
        ])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .unwrap();

    let health_url = format!("http://{bind}/health");
    assert!(
        wait_for_http_ready(&health_url).await,
        "health endpoint never became ready"
    );

    let status = Command::new("kill")
        .args(["-TERM", &child.id().to_string()])
        .status()
        .unwrap();
    assert!(status.success());

    let exit_status = wait_for_child_exit(&mut child).await;
    assert!(exit_status.is_some(), "server did not exit after SIGTERM");
    assert!(exit_status.unwrap().success());
}
