use std::{
    collections::VecDeque,
    net::SocketAddr,
    path::PathBuf,
    sync::{
        Arc,
        atomic::{AtomicUsize, Ordering},
    },
    time::Duration,
};

use anyhow::{Context, Result};
use axum::{
    Json, Router,
    extract::{
        State,
        ws::{Message, WebSocket, WebSocketUpgrade},
    },
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::get,
};
use base64::{Engine as _, engine::general_purpose};
use futures_util::{SinkExt, StreamExt};
use serde_json::{Value, json};
use tokio::sync::oneshot;
use tokio::{net::TcpListener, task::JoinHandle};

use crate::{
    api,
    backend::{BrowserBackend, LaunchedBrowser, StartSessionOptions},
    cdp,
    config::RuntimeConfig,
    models::{BrowserPersona, CaptchaPolicy, CreateSessionRequest},
    store::AppStore,
};

#[derive(Debug, Clone)]
pub(crate) struct RecordedCommand {
    pub websocket: &'static str,
    pub method: String,
    pub params: Value,
    pub session_id: Option<String>,
}

#[derive(Debug, Clone)]
pub(crate) enum MockEndpointResponse {
    Json(StatusCode, Value),
    Text(StatusCode, String),
    Empty(StatusCode),
}

impl MockEndpointResponse {
    fn into_response(self) -> Response {
        match self {
            Self::Json(status, value) => (status, Json(value)).into_response(),
            Self::Text(status, body) => (status, body).into_response(),
            Self::Empty(status) => status.into_response(),
        }
    }
}

#[derive(Debug, Clone)]
pub(crate) enum WsReply {
    Success(Value),
    Error(Value),
    CloseBeforeResponse,
    InvalidJson,
    EventThenSuccess(Value),
    CustomEventThenSuccess { event: Value, result: Value },
    BinaryThenSuccess(Value),
    ForceSendError,
}

struct MockCdpState {
    ws_base_url: tokio::sync::Mutex<String>,
    version_override: tokio::sync::Mutex<Option<MockEndpointResponse>>,
    list_override: tokio::sync::Mutex<Option<MockEndpointResponse>>,
    new_override: tokio::sync::Mutex<Option<MockEndpointResponse>>,
    screenshot_base64: tokio::sync::Mutex<String>,
    page_replies: tokio::sync::Mutex<VecDeque<WsReply>>,
    browser_replies: tokio::sync::Mutex<VecDeque<WsReply>>,
    recorded_commands: tokio::sync::Mutex<Vec<RecordedCommand>>,
    new_page_calls: AtomicUsize,
}

impl MockCdpState {
    fn new() -> Self {
        Self {
            ws_base_url: tokio::sync::Mutex::new(String::new()),
            version_override: tokio::sync::Mutex::new(None),
            list_override: tokio::sync::Mutex::new(None),
            new_override: tokio::sync::Mutex::new(None),
            screenshot_base64: tokio::sync::Mutex::new(general_purpose::STANDARD.encode(b"png")),
            page_replies: tokio::sync::Mutex::new(VecDeque::new()),
            browser_replies: tokio::sync::Mutex::new(VecDeque::new()),
            recorded_commands: tokio::sync::Mutex::new(Vec::new()),
            new_page_calls: AtomicUsize::new(0),
        }
    }
}

pub(crate) struct MockCdpServer {
    pub base_url: String,
    pub browser_ws_url: String,
    pub page_ws_url: String,
    state: Arc<MockCdpState>,
    shutdown_tx: oneshot::Sender<()>,
    task: JoinHandle<()>,
}

impl MockCdpServer {
    pub(crate) async fn spawn() -> Self {
        let state = Arc::new(MockCdpState::new());
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let (shutdown_tx, shutdown_rx) = oneshot::channel();
        let addr = listener.local_addr().unwrap();
        let base_url = format!("http://{addr}");
        let ws_base_url = format!("ws://{addr}");
        let page_ws_url = format!("{ws_base_url}/devtools/page/main");
        let browser_ws_url = format!("{ws_base_url}/devtools/browser/main");
        *state.ws_base_url.lock().await = ws_base_url.clone();
        let app = Router::new()
            .route("/json/version", get(version_handler))
            .route("/json/list", get(list_handler))
            .route("/json/new", get(new_handler))
            .route("/devtools/page/main", get(page_ws_handler))
            .route("/devtools/browser/main", get(browser_ws_handler))
            .with_state(state.clone());
        let task = tokio::spawn(async move {
            axum::serve(listener, app)
                .with_graceful_shutdown(async {
                    let _ = shutdown_rx.await;
                })
                .await
                .unwrap();
        });
        Self {
            base_url,
            browser_ws_url,
            page_ws_url,
            state,
            shutdown_tx,
            task,
        }
    }

    pub(crate) async fn stop(self) {
        let Self {
            shutdown_tx, task, ..
        } = self;
        let _ = shutdown_tx.send(());
        let _ = task.await;
    }

    pub(crate) async fn set_version_response(&self, response: MockEndpointResponse) {
        *self.state.version_override.lock().await = Some(response);
    }

    pub(crate) async fn set_list_response(&self, response: MockEndpointResponse) {
        *self.state.list_override.lock().await = Some(response);
    }

    pub(crate) async fn set_new_response(&self, response: MockEndpointResponse) {
        *self.state.new_override.lock().await = Some(response);
    }

    pub(crate) async fn set_screenshot_bytes(&self, bytes: &[u8]) {
        *self.state.screenshot_base64.lock().await = general_purpose::STANDARD.encode(bytes);
    }

    pub(crate) async fn enqueue_page_reply(&self, reply: WsReply) {
        self.state.page_replies.lock().await.push_back(reply);
    }

    pub(crate) async fn enqueue_browser_reply(&self, reply: WsReply) {
        self.state.browser_replies.lock().await.push_back(reply);
    }

    pub(crate) async fn recorded_commands(&self) -> Vec<RecordedCommand> {
        self.state.recorded_commands.lock().await.clone()
    }

    pub(crate) async fn clear_recorded_commands(&self) {
        self.state.recorded_commands.lock().await.clear();
    }

    pub(crate) fn new_page_calls(&self) -> usize {
        self.state.new_page_calls.load(Ordering::SeqCst)
    }
}

async fn version_handler(State(state): State<Arc<MockCdpState>>) -> Response {
    if let Some(response) = state.version_override.lock().await.clone() {
        return response.into_response();
    }
    let ws_base_url = state.ws_base_url.lock().await.clone();
    Json(json!({
        "webSocketDebuggerUrl": format!("{ws_base_url}/devtools/browser/main"),
    }))
    .into_response()
}

async fn list_handler(State(state): State<Arc<MockCdpState>>) -> Response {
    if let Some(response) = state.list_override.lock().await.clone() {
        return response.into_response();
    }
    let ws_base_url = state.ws_base_url.lock().await.clone();
    Json(json!([
        {
            "type": "page",
            "webSocketDebuggerUrl": format!("{ws_base_url}/devtools/page/main"),
        }
    ]))
    .into_response()
}

async fn new_handler(State(state): State<Arc<MockCdpState>>) -> Response {
    state.new_page_calls.fetch_add(1, Ordering::SeqCst);
    state
        .new_override
        .lock()
        .await
        .clone()
        .unwrap_or(MockEndpointResponse::Empty(StatusCode::OK))
        .into_response()
}

async fn page_ws_handler(
    ws: WebSocketUpgrade,
    State(state): State<Arc<MockCdpState>>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| websocket_handler(socket, state, "page"))
}

async fn browser_ws_handler(
    ws: WebSocketUpgrade,
    State(state): State<Arc<MockCdpState>>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| websocket_handler(socket, state, "browser"))
}

async fn websocket_handler(
    mut socket: WebSocket,
    state: Arc<MockCdpState>,
    websocket: &'static str,
) {
    while let Some(Ok(frame)) = socket.next().await {
        let Message::Text(text) = frame else {
            continue;
        };
        let value: Value = match serde_json::from_str(&text) {
            Ok(value) => value,
            Err(_) => break,
        };
        let method = value
            .get("method")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string();
        let params = value.get("params").cloned().unwrap_or(Value::Null);
        let session_id = value
            .get("sessionId")
            .and_then(Value::as_str)
            .map(str::to_owned);
        state.recorded_commands.lock().await.push(RecordedCommand {
            websocket,
            method: method.clone(),
            params,
            session_id,
        });
        let reply = next_ws_reply(&state, websocket, &method).await;
        if send_ws_reply(&mut socket, reply).await.is_err() {
            break;
        }
    }
}

async fn next_ws_reply(
    state: &Arc<MockCdpState>,
    websocket: &'static str,
    method: &str,
) -> WsReply {
    let queued = if websocket == "page" {
        state.page_replies.lock().await.pop_front()
    } else {
        state.browser_replies.lock().await.pop_front()
    };
    if let Some(reply) = queued {
        return reply;
    }
    match method {
        "Page.captureScreenshot" => WsReply::Success(json!({
            "data": state.screenshot_base64.lock().await.clone(),
        })),
        _ => WsReply::Success(json!({})),
    }
}

async fn send_ws_reply(socket: &mut WebSocket, reply: WsReply) -> Result<()> {
    match reply {
        WsReply::Success(result) => {
            let payload = json!({"id": 1, "result": result}).to_string();
            socket.send(Message::Text(payload)).await?;
        }
        WsReply::Error(error) => {
            let payload = json!({"id": 1, "error": error}).to_string();
            socket.send(Message::Text(payload)).await?;
        }
        WsReply::CloseBeforeResponse => {
            socket.close().await?;
        }
        WsReply::InvalidJson => {
            socket.send(Message::Text("not-json".to_string())).await?;
        }
        WsReply::EventThenSuccess(result) => {
            let event = json!({
                "method": "Page.lifecycleEvent",
                "params": {"name": "networkAlmostIdle"}
            })
            .to_string();
            socket.send(Message::Text(event)).await?;
            let payload = json!({"id": 1, "result": result}).to_string();
            socket.send(Message::Text(payload)).await?;
        }
        WsReply::CustomEventThenSuccess { event, result } => {
            socket.send(Message::Text(event.to_string())).await?;
            let payload = json!({"id": 1, "result": result}).to_string();
            socket.send(Message::Text(payload)).await?;
        }
        WsReply::BinaryThenSuccess(result) => {
            socket.send(Message::Binary(vec![1, 2, 3])).await?;
            let payload = json!({"id": 1, "result": result}).to_string();
            socket.send(Message::Text(payload)).await?;
        }
        WsReply::ForceSendError => {
            return Err(anyhow::anyhow!("forced websocket send error"));
        }
    }
    Ok(())
}

#[derive(Clone)]
pub(crate) struct MockBackend {
    http_base: String,
    browser_ws_url: String,
}

impl MockBackend {
    pub(crate) fn new(http_base: String, browser_ws_url: String) -> Self {
        Self {
            http_base,
            browser_ws_url,
        }
    }
}

#[async_trait::async_trait]
impl BrowserBackend for MockBackend {
    async fn launch(&self, _options: StartSessionOptions) -> Result<LaunchedBrowser> {
        let process = tokio::process::Command::new("sleep")
            .arg("60")
            .spawn()
            .context("spawn fake browser process")?;
        Ok(LaunchedBrowser {
            process,
            port: 1,
            http_base: self.http_base.clone(),
            cdp_ws_url: self.browser_ws_url.clone(),
            persona_guard: None,
        })
    }

    async fn close(&self, launched: &mut LaunchedBrowser) -> Result<()> {
        let _ = cdp::browser_close(&launched.cdp_ws_url).await;
        let _ = launched.process.start_kill();
        let _ = launched.process.wait().await;
        Ok(())
    }
}

pub(crate) fn test_config(data_dir: PathBuf, bearer_token: Option<String>) -> RuntimeConfig {
    RuntimeConfig {
        bind: "127.0.0.1:7788".parse::<SocketAddr>().unwrap(),
        data_dir,
        chrome_path: None,
        bearer_token,
        operator_token: None,
        default_headless: true,
        artifact_retention: Duration::from_secs(604800),
        takeover_ttl: Duration::from_secs(60),
        launch_timeout: Duration::from_secs(15),
        captcha_solver_enabled: false,
        default_captcha_policy: CaptchaPolicy::HumanOnly,
        captcha_solver_policy_path: None,
        captcha_solver_provider_order: "capsolver".into(),
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
    }
}

pub(crate) fn persistent_req(profile_id: &str) -> CreateSessionRequest {
    CreateSessionRequest {
        profile_id: Some(profile_id.into()),
        headless: Some(true),
        viewport: None,
        persist_profile: Some(true),
        launch_timeout_secs: None,
        persona: None,
        ..Default::default()
    }
}

pub(crate) fn token_from_url(url: &str) -> &str {
    url.split("token=").nth(1).unwrap()
}

pub(crate) struct TestApiServer {
    pub base_url: String,
    pub store: Arc<AppStore>,
    pub cdp: MockCdpServer,
    _tempdir: tempfile::TempDir,
    shutdown_tx: oneshot::Sender<()>,
    task: JoinHandle<()>,
}

impl TestApiServer {
    pub(crate) async fn stop(self) {
        let Self {
            cdp,
            shutdown_tx,
            task,
            ..
        } = self;
        let _ = shutdown_tx.send(());
        let _ = task.await;
        cdp.stop().await;
    }
}

pub(crate) async fn spawn_api_server(bearer_token: Option<&str>) -> TestApiServer {
    let tempdir = tempfile::tempdir().unwrap();
    let cdp = MockCdpServer::spawn().await;
    let store = Arc::new(
        AppStore::new(
            test_config(
                tempdir.path().to_path_buf(),
                bearer_token.map(std::string::ToString::to_string),
            ),
            Arc::new(MockBackend::new(
                cdp.base_url.clone(),
                cdp.browser_ws_url.clone(),
            )),
        )
        .await
        .unwrap(),
    );
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let (shutdown_tx, shutdown_rx) = oneshot::channel();
    let base_url = format!("http://{}", listener.local_addr().unwrap());
    let server_store = store.clone();
    let task = tokio::spawn(async move {
        axum::serve(listener, api::router(server_store))
            .with_graceful_shutdown(async {
                let _ = shutdown_rx.await;
            })
            .await
            .unwrap();
    });
    TestApiServer {
        base_url,
        store,
        cdp,
        _tempdir: tempdir,
        shutdown_tx,
        task,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use futures_util::{SinkExt, StreamExt};
    use serde_json::json;
    use tokio::time::{sleep, timeout};
    use tokio_tungstenite::{connect_async, tungstenite::Message};

    #[tokio::test]
    async fn websocket_handler_breaks_on_invalid_client_json() {
        let server = MockCdpServer::spawn().await;
        let (mut ws, _) = connect_async(&server.page_ws_url).await.unwrap();

        ws.send(Message::Text("not-json".to_string()))
            .await
            .unwrap();
        let _ = timeout(Duration::from_millis(100), ws.next()).await;

        assert!(server.recorded_commands().await.is_empty());

        drop(ws);
        server.stop().await;
    }

    #[tokio::test]
    async fn websocket_handler_breaks_when_reply_send_fails() {
        let server = MockCdpServer::spawn().await;
        server.enqueue_page_reply(WsReply::ForceSendError).await;
        let (mut ws, _) = connect_async(&server.page_ws_url).await.unwrap();

        ws.send(Message::Text(
            json!({"id": 1, "method": "Input.insertText", "params": {"text": "hello"}}).to_string(),
        ))
        .await
        .unwrap();

        let _ = timeout(Duration::from_millis(100), ws.next()).await;
        sleep(Duration::from_millis(25)).await;

        let commands = server.recorded_commands().await;
        assert_eq!(commands.len(), 1);
        assert_eq!(commands[0].method, "Input.insertText");

        drop(ws);
        server.stop().await;
    }
}
