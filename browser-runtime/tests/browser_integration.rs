use std::{collections::HashMap, path::PathBuf, sync::Arc, time::Duration};

use anyhow::{Context, Result, bail, ensure};
use axum::{
    Router,
    extract::{Query, State},
    http::{HeaderMap, header},
    response::{Html, IntoResponse},
    routing::get,
};
use hermes_browser_runtime::{
    api,
    backend::{BrowserBackend, LocalChromeBackend, StartSessionOptions},
    cdp,
    client::BrowserRuntimeClient,
    config::RuntimeConfig,
    display,
    models::{
        BrowserPersona, CaptchaPolicy, CreateSessionRequest, PauseForHumanRequest, SessionStatus,
        Viewport,
    },
    store::AppStore,
};
use reqwest::StatusCode;
use serde_json::{Value, json};
use tokio::{
    net::TcpListener,
    sync::{Mutex, oneshot},
    task::JoinHandle,
};
use uuid::Uuid;

const INDEX_HTML: &str = r#"<!doctype html>
<html><head><meta charset="utf-8"><title>HBR coherence probe</title></head>
<body><iframe id="frame" src="/frame"></iframe></body></html>"#;

const FRAME_HTML: &str = r#"<!doctype html><html><body>frame probe</body></html>"#;

const TAKEOVER_FORM_HTML: &str = r#"<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Takeover form probe</title>
  <style>
    body { margin: 0; font-family: sans-serif; }
    label { display: block; margin: 18px 0 0 40px; }
    input, textarea, [contenteditable] { display: block; width: 320px; min-height: 32px; font-size: 16px; padding: 6px; margin-top: 4px; }
    textarea { height: 80px; }
    [contenteditable] { border: 1px solid #767676; background: white; }
  </style>
</head>
<body>
  <label>Text<input id="name" type="text" autocomplete="off"></label>
  <label>Email<input id="email" type="email" autocomplete="off"></label>
  <label>Password<input id="password" type="password" autocomplete="off"></label>
  <label>Notes<textarea id="notes" autocomplete="off"></textarea></label>
  <label>Editable<div id="editable" contenteditable="true"></div></label>
</body>
</html>"#;

const WORKER_JS: &str = r#"
self.onmessage = async () => {
  await fetch('/headers?realm=worker_fetch');
  const uaData = navigator.userAgentData
    ? await navigator.userAgentData.getHighEntropyValues(['brands', 'fullVersionList', 'platform', 'platformVersion', 'architecture', 'bitness', 'mobile'])
    : null;
  self.postMessage({
    language: navigator.language,
    languages: Array.from(navigator.languages || []),
    userAgent: navigator.userAgent,
    platform: navigator.platform,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    uaData,
    automation: {
      webdriverType: typeof navigator.webdriver,
      webdriverInNavigator: 'webdriver' in navigator,
      ownHasWebdriver: Object.prototype.hasOwnProperty.call(navigator, 'webdriver'),
      protoHasWebdriver: !!Object.getOwnPropertyDescriptor(Object.getPrototypeOf(navigator), 'webdriver'),
    },
  });
};
"#;

const PROBE_EXPRESSION: &str = r#"
(async () => {
  const automationProbe = (win) => {
    const nav = win.navigator;
    const proto = win.Object.getPrototypeOf(nav);
    const protoDescriptor = win.Object.getOwnPropertyDescriptor(proto, 'webdriver');
    const ownDescriptor = win.Object.getOwnPropertyDescriptor(nav, 'webdriver');
    return {
      webdriverType: typeof nav.webdriver,
      webdriverInNavigator: 'webdriver' in nav,
      ownHasWebdriver: !!ownDescriptor,
      protoHasWebdriver: !!protoDescriptor,
      protoGetterText: protoDescriptor && protoDescriptor.get ? win.Function.prototype.toString.call(protoDescriptor.get) : null,
    };
  };
  const probe = (win) => ({
    language: win.navigator.language,
    languages: Array.from(win.navigator.languages || []),
    userAgent: win.navigator.userAgent,
    platform: win.navigator.platform,
    timezone: win.Intl.DateTimeFormat().resolvedOptions().timeZone,
    viewport: { innerWidth: win.innerWidth, innerHeight: win.innerHeight },
    screen: { width: win.screen.width, height: win.screen.height, availWidth: win.screen.availWidth, availHeight: win.screen.availHeight },
    devicePixelRatio: win.devicePixelRatio,
    automation: automationProbe(win),
  });
  const deadline = Date.now() + 5000;
  let iframe = document.getElementById('frame');
  while (!iframe && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 50));
    iframe = document.getElementById('frame');
  }
  if (!iframe) { throw new Error('iframe probe element missing after navigation'); }
  if (!iframe.contentWindow || iframe.contentDocument.readyState !== 'complete') {
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('iframe probe load timeout')), 5000);
      iframe.addEventListener('load', () => { clearTimeout(timer); resolve(); }, { once: true });
    });
  }
  const popup = window.open('about:blank', '_blank', 'width=320,height=240');
  let popupResult = null;
  if (popup) {
    popup.document.open();
    popup.document.write('<!doctype html><html><body>popup probe</body></html>');
    popup.document.close();
    await new Promise((resolve) => setTimeout(resolve, 500));
    popupResult = probe(popup);
    popup.close();
  }
  const worker = new Worker('/worker.js');
  const workerResult = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('worker probe timeout')), 5000);
    worker.onmessage = (event) => { clearTimeout(timer); resolve(event.data); };
    worker.onerror = (event) => { clearTimeout(timer); reject(new Error(event.message || 'worker probe failed')); };
    worker.postMessage('probe');
  });
  worker.terminate();
  const uaData = navigator.userAgentData
    ? await navigator.userAgentData.getHighEntropyValues(['brands', 'fullVersionList', 'platform', 'platformVersion', 'architecture', 'bitness', 'mobile'])
    : null;
  return { top: probe(window), frame: probe(iframe.contentWindow), popup: popupResult, worker: workerResult, uaData };
})()
"#;

#[derive(Clone, Default)]
struct HeaderCapture {
    seen: Arc<Mutex<HashMap<String, String>>>,
}

impl HeaderCapture {
    async fn record(&self, realm: &str, headers: &HeaderMap) {
        let value = headers
            .get(header::ACCEPT_LANGUAGE)
            .and_then(|value| value.to_str().ok())
            .unwrap_or_default()
            .to_string();
        self.seen.lock().await.insert(realm.to_string(), value);
    }

    async fn snapshot(&self) -> HashMap<String, String> {
        self.seen.lock().await.clone()
    }
}

struct EchoServer {
    base_url: String,
    capture: HeaderCapture,
    task: tokio::task::JoinHandle<()>,
}

impl EchoServer {
    async fn spawn() -> Self {
        let capture = HeaderCapture::default();
        let app = Router::new()
            .route("/", get(index_handler))
            .route("/frame", get(frame_handler))
            .route("/takeover-form", get(takeover_form_handler))
            .route("/worker.js", get(worker_handler))
            .route("/headers", get(headers_handler))
            .with_state(capture.clone());
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let base_url = format!("http://{}", listener.local_addr().unwrap());
        let task = tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });
        Self {
            base_url,
            capture,
            task,
        }
    }

    async fn stop(self) {
        self.task.abort();
        let _ = self.task.await;
    }
}

async fn index_handler(
    State(capture): State<HeaderCapture>,
    headers: HeaderMap,
) -> Html<&'static str> {
    capture.record("top_request", &headers).await;
    Html(INDEX_HTML)
}

async fn frame_handler(
    State(capture): State<HeaderCapture>,
    headers: HeaderMap,
) -> Html<&'static str> {
    capture.record("frame_request", &headers).await;
    Html(FRAME_HTML)
}

async fn takeover_form_handler(
    State(capture): State<HeaderCapture>,
    headers: HeaderMap,
) -> Html<&'static str> {
    capture.record("takeover_form_request", &headers).await;
    Html(TAKEOVER_FORM_HTML)
}

async fn worker_handler(
    State(capture): State<HeaderCapture>,
    headers: HeaderMap,
) -> impl IntoResponse {
    capture.record("worker_script", &headers).await;
    (
        [(header::CONTENT_TYPE, "application/javascript")],
        WORKER_JS,
    )
}

async fn headers_handler(
    State(capture): State<HeaderCapture>,
    Query(query): Query<HashMap<String, String>>,
    headers: HeaderMap,
) -> impl IntoResponse {
    let realm = query
        .get("realm")
        .map(String::as_str)
        .unwrap_or("unknown_request");
    capture.record(realm, &headers).await;
    "ok"
}

fn chrome_path_from_env_or_known_locations() -> Option<PathBuf> {
    let mut candidates = vec![
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/opt/google/chrome/chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
        "/usr/bin/brave-browser",
        "/opt/brave.com/brave/brave-browser",
    ]
    .into_iter()
    .map(PathBuf::from)
    .collect::<Vec<_>>();
    if let Some(home) = dirs::home_dir() {
        candidates.push(home.join(".cache/ms-playwright/chromium-1217/chrome-linux64/chrome"));
    }
    std::env::var_os("HBR_CHROME_PATH")
        .map(PathBuf::from)
        .or_else(|| candidates.into_iter().find(|path| path.exists()))
}

fn headed_display_available() -> bool {
    display::headed_mode_supported(
        std::env::var_os("DISPLAY"),
        std::env::var_os("WAYLAND_DISPLAY"),
        display::find_xvfb_run_path(),
    )
}

fn integration_headless_override() -> bool {
    std::env::var_os("HBR_BROWSER_INTEGRATION_HEADLESS").is_some_and(|value| {
        value == "1" || value == "true" || value == "TRUE" || value == "yes" || value == "YES"
    })
}

fn persona() -> BrowserPersona {
    BrowserPersona {
        locale: "en-US".into(),
        accept_language: "en-US,en;q=0.9".into(),
        timezone_id: "America/New_York".into(),
        platform: "Linux x86_64".into(),
        user_agent: None,
        viewport: Viewport {
            width: 1280,
            height: 800,
        },
        screen: Viewport {
            width: 1280,
            height: 800,
        },
        device_scale_factor: 1.0,
        hardware_concurrency: 8,
        device_memory_gb: 8,
        max_touch_points: 0,
    }
}

fn assert_ua_data_has_no_headless_marker(ua_data: &Value) {
    if ua_data.is_null() {
        return;
    }
    assert_eq!(ua_data["platform"], "Linux");
    assert_eq!(ua_data["mobile"], false);
    for key in ["brands", "fullVersionList"] {
        if let Some(brands) = ua_data[key].as_array() {
            for brand in brands {
                assert_ne!(brand["brand"], "HeadlessChrome");
            }
        }
    }
}

fn assert_webdriver_hygiene(observed: &Value, realm: &str) {
    assert_eq!(
        observed["automation"]["webdriverType"], "undefined",
        "{realm} navigator.webdriver should be undefined"
    );
    assert_eq!(
        observed["automation"]["webdriverInNavigator"], false,
        "{realm} should not expose webdriver via the in-operator"
    );
    assert_eq!(
        observed["automation"]["ownHasWebdriver"], false,
        "{realm} navigator should not have an own webdriver descriptor"
    );
    assert_eq!(
        observed["automation"]["protoHasWebdriver"], false,
        "{realm} Navigator prototype should not retain a webdriver descriptor"
    );
    assert!(
        observed["automation"]["protoGetterText"].is_null(),
        "{realm} should not expose native webdriver getter text"
    );
}

fn assert_coherent_persona_probe(
    observed: &Value,
    headers: &HashMap<String, String>,
    persona: &BrowserPersona,
) {
    for realm in [
        "top_request",
        "frame_request",
        "worker_script",
        "worker_fetch",
    ] {
        let value = headers
            .get(realm)
            .unwrap_or_else(|| panic!("missing header capture for {realm}"));
        assert!(
            value.starts_with(&persona.accept_language),
            "{realm} accept-language mismatch: {value:?}"
        );
    }

    for realm in ["top", "frame", "worker"] {
        assert_webdriver_hygiene(&observed[realm], realm);
        assert_eq!(
            observed[realm]["language"], persona.locale,
            "{realm} language"
        );
        assert_eq!(
            observed[realm]["languages"][0], persona.locale,
            "{realm} languages[0]"
        );
        assert_eq!(
            observed[realm]["timezone"], persona.timezone_id,
            "{realm} timezone"
        );
        assert_eq!(
            observed[realm]["platform"], persona.platform,
            "{realm} platform"
        );
        let user_agent = observed[realm]["userAgent"].as_str().unwrap_or_default();
        assert!(
            user_agent.contains("Chrome/") && !user_agent.contains("HeadlessChrome"),
            "{realm} leaked incoherent/headless UA: {user_agent}"
        );
    }

    for realm in ["top", "frame"] {
        assert_eq!(
            observed[realm]["viewport"]["innerWidth"],
            persona.viewport.width
        );
        assert_eq!(
            observed[realm]["viewport"]["innerHeight"],
            persona.viewport.height
        );
        assert_eq!(observed[realm]["screen"]["width"], persona.screen.width);
        assert_eq!(observed[realm]["screen"]["height"], persona.screen.height);
        assert_eq!(
            observed[realm]["devicePixelRatio"],
            persona.device_scale_factor
        );
    }

    assert!(
        observed["popup"].is_object(),
        "popup probe was blocked or missing"
    );
    assert_webdriver_hygiene(&observed["popup"], "popup");
    assert_eq!(
        observed["popup"]["language"], persona.locale,
        "popup language"
    );
    assert_eq!(
        observed["popup"]["timezone"], persona.timezone_id,
        "popup timezone"
    );
    assert_eq!(
        observed["popup"]["platform"], persona.platform,
        "popup platform"
    );

    assert_ua_data_has_no_headless_marker(&observed["uaData"]);
    assert_ua_data_has_no_headless_marker(&observed["worker"]["uaData"]);
}

#[test]
fn deterministic_persona_probe_fixture_covers_top_iframe_popup_worker_headers() {
    let persona = persona();
    let realm_probe = json!({
        "language": persona.locale.clone(),
        "languages": [persona.locale.clone(), "en"],
        "userAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "platform": persona.platform.clone(),
        "timezone": persona.timezone_id.clone(),
        "viewport": {"innerWidth": persona.viewport.width, "innerHeight": persona.viewport.height},
        "screen": {"width": persona.screen.width, "height": persona.screen.height, "availWidth": persona.screen.width, "availHeight": persona.screen.height},
        "devicePixelRatio": persona.device_scale_factor,
        "automation": {
            "webdriverType": "undefined",
            "webdriverInNavigator": false,
            "ownHasWebdriver": false,
            "protoHasWebdriver": false,
            "protoGetterText": null,
        },
    });
    let ua_data = json!({
        "brands": [{"brand": "Chromium", "version": "125"}],
        "fullVersionList": [{"brand": "Chromium", "version": "125.0.0.0"}],
        "platform": "Linux",
        "platformVersion": "6.0.0",
        "architecture": "x86",
        "bitness": "64",
        "mobile": false,
    });
    let mut worker = realm_probe.clone();
    worker["uaData"] = ua_data.clone();
    let observed = json!({
        "top": realm_probe,
        "frame": realm_probe,
        "popup": realm_probe,
        "worker": worker,
        "uaData": ua_data,
    });
    let headers = HashMap::from([
        ("top_request".to_string(), persona.accept_language.clone()),
        ("frame_request".to_string(), persona.accept_language.clone()),
        ("worker_script".to_string(), persona.accept_language.clone()),
        ("worker_fetch".to_string(), persona.accept_language.clone()),
    ]);

    assert_coherent_persona_probe(&observed, &headers, &persona);
}

#[tokio::test]
#[ignore = "requires local Chrome plus DISPLAY/WAYLAND_DISPLAY or xvfb-run; set HBR_CHROME_PATH if autodetect misses it"]
async fn headed_persona_coherence_echo_page_covers_top_iframe_popup_worker_and_headers()
-> Result<()> {
    let Some(chrome_path) = chrome_path_from_env_or_known_locations() else {
        eprintln!("skipping: no Chrome/Chromium path found; set HBR_CHROME_PATH");
        return Ok(());
    };
    let headless = integration_headless_override();
    if !headless && !headed_display_available() {
        eprintln!(
            "skipping: no DISPLAY, WAYLAND_DISPLAY, or xvfb-run for headed Chrome; set HBR_BROWSER_INTEGRATION_HEADLESS=1 to run the coherence gate headlessly"
        );
        return Ok(());
    }

    let echo = EchoServer::spawn().await;
    let tempdir = tempfile::tempdir().context("create browser tempdir")?;
    let persona = persona();
    let backend = LocalChromeBackend::new(Some(chrome_path))?;
    let mut launched = backend
        .launch(StartSessionOptions {
            id: Uuid::new_v4(),
            user_data_dir: tempdir.path().join("profile"),
            downloads_dir: tempdir.path().join("downloads"),
            headless,
            viewport: persona.viewport.clone(),
            persona: persona.clone(),
            launch_timeout: Duration::from_secs(15),
            webrtc_ip_policy: Default::default(),
            gpu_policy: Default::default(),
        })
        .await?;

    cdp::navigate(&launched.http_base, &echo.base_url).await?;
    let observed = cdp::evaluate_json(&launched.http_base, PROBE_EXPRESSION).await?;
    let headers = echo.capture.snapshot().await;

    assert_coherent_persona_probe(&observed, &headers, &persona);

    backend.close(&mut launched).await?;
    echo.stop().await;
    Ok(())
}

struct RuntimeApiServer {
    base_url: String,
    store: Arc<AppStore>,
    shutdown_tx: oneshot::Sender<()>,
    task: JoinHandle<()>,
    _tempdir: tempfile::TempDir,
}

impl RuntimeApiServer {
    async fn spawn(chrome_path: PathBuf) -> Result<Self> {
        let tempdir = tempfile::tempdir().context("create runtime tempdir")?;
        let data_dir = tempdir.path().join("runtime-data");
        let listener = TcpListener::bind("127.0.0.1:0")
            .await
            .context("bind runtime API test server")?;
        let bind = listener
            .local_addr()
            .context("read runtime API bind addr")?;
        let config = RuntimeConfig {
            bind,
            data_dir,
            chrome_path: Some(chrome_path.clone()),
            default_headless: true,
            artifact_retention: Duration::from_secs(3600),
            takeover_ttl: Duration::from_secs(60),
            launch_timeout: Duration::from_secs(20),
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
            bearer_token: Some("integration-smoke-bearer".to_string()),
            operator_token: None,
            default_webrtc_ip_policy: Default::default(),
            default_gpu_policy: Default::default(),
            default_persona: BrowserPersona::default(),
        };
        let backend: Arc<dyn BrowserBackend> =
            Arc::new(LocalChromeBackend::new(Some(chrome_path))?);
        let store = Arc::new(
            AppStore::new(config, backend)
                .await
                .context("create runtime API store")?,
        );
        let (shutdown_tx, shutdown_rx) = oneshot::channel();
        let server_store = store.clone();
        let task = tokio::spawn(async move {
            axum::serve(listener, api::router(server_store))
                .with_graceful_shutdown(async {
                    let _ = shutdown_rx.await;
                })
                .await
                .unwrap();
        });
        let base_url = format!("http://{bind}");
        let health_url = format!("{base_url}/health");
        let client = reqwest::Client::new();
        let mut last_error = None;
        for _ in 0..50 {
            match client.get(&health_url).send().await {
                Ok(response) if response.status().is_success() => {
                    return Ok(Self {
                        base_url,
                        store,
                        shutdown_tx,
                        task,
                        _tempdir: tempdir,
                    });
                }
                Ok(response) => {
                    last_error = Some(anyhow::anyhow!("health returned {}", response.status()));
                }
                Err(err) => {
                    last_error = Some(err.into());
                }
            }
            tokio::time::sleep(Duration::from_millis(20)).await;
        }
        bail!(
            "runtime API test server did not become healthy: {}",
            last_error
                .map(|err| err.to_string())
                .unwrap_or_else(|| "no health attempt was made".to_string())
        )
    }

    async fn stop(self) -> Result<()> {
        let shutdown_result = self.store.shutdown_all().await;
        let _ = self.shutdown_tx.send(());
        let _ = self.task.await;
        shutdown_result
    }
}

fn cdp_http_base_from_browser_ws_url(ws_url: &str) -> Result<String> {
    let (scheme, rest) = if let Some(rest) = ws_url.strip_prefix("ws://") {
        ("http", rest)
    } else if let Some(rest) = ws_url.strip_prefix("wss://") {
        ("https", rest)
    } else {
        bail!("CDP websocket URL did not use ws/wss scheme")
    };
    let authority = rest
        .split('/')
        .next()
        .filter(|value| !value.is_empty())
        .context("CDP websocket URL missing authority")?;
    Ok(format!("{scheme}://{authority}"))
}

fn takeover_token_from_url(url: &str) -> Result<String> {
    let token = url
        .split("token=")
        .nth(1)
        .and_then(|value| value.split('&').next())
        .filter(|value| !value.is_empty())
        .context("takeover URL missing token query parameter")?;
    Ok(token.to_string())
}

fn ensure_png(bytes: &[u8], label: &str) -> Result<()> {
    ensure!(bytes.len() > 8, "{label} too small to be a PNG");
    ensure!(
        bytes.starts_with(b"\x89PNG\r\n\x1a\n"),
        "{label} did not have a PNG signature"
    );
    Ok(())
}

async fn ensure_forbidden_without_secret_echo(
    response: reqwest::Response,
    secret: &str,
    label: &str,
) -> Result<()> {
    let status = response.status();
    let body = response
        .text()
        .await
        .with_context(|| format!("read {label} response body"))?;
    ensure!(status == StatusCode::FORBIDDEN, "{label} returned {status}");
    ensure!(
        body.contains("invalid or expired takeover token"),
        "{label} did not return the generic takeover-token error"
    );
    ensure!(!body.contains(secret), "{label} echoed the rejected token");
    Ok(())
}

async fn remote_element_center(cdp_http_base: &str, selector: &str) -> Result<(f64, f64)> {
    let selector_json = serde_json::to_string(selector)?;
    let expression = format!(
        r#"
(async () => {{
  const selector = {selector_json};
  for (let i = 0; i < 50; i += 1) {{
    const el = document.querySelector(selector);
    if (el) {{
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {{
        return {{ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, id: el.id }};
      }}
    }}
    await new Promise((resolve) => setTimeout(resolve, 100));
  }}
  throw new Error(`selector not visible: ${{selector}}`);
}})()
"#,
        selector_json = selector_json
    );
    let point = cdp::evaluate_json(cdp_http_base, &expression)
        .await
        .with_context(|| format!("find remote element center for {selector}"))?;
    let x = point["x"]
        .as_f64()
        .with_context(|| format!("remote element {selector} missing x center"))?;
    let y = point["y"]
        .as_f64()
        .with_context(|| format!("remote element {selector} missing y center"))?;
    Ok((x, y))
}

async fn wait_operator_keyboard_proxy_focused(operator_http_base: &str) -> Result<()> {
    let observed = cdp::evaluate_json(
        operator_http_base,
        r#"
(async () => {
  for (let i = 0; i < 50; i += 1) {
    const activeElement = document.activeElement ? document.activeElement.id : null;
    if (activeElement === 'keyboard-proxy') {
      return { activeElement };
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return { activeElement: document.activeElement ? document.activeElement.id : null };
})()
"#,
    )
    .await
    .context("wait for takeover keyboard proxy focus")?;
    ensure!(
        observed["activeElement"] == "keyboard-proxy",
        "takeover page did not focus the keyboard proxy after screenshot click"
    );
    Ok(())
}

async fn click_takeover_screenshot_at_remote_point(
    operator_http_base: &str,
    remote_x: f64,
    remote_y: f64,
) -> Result<()> {
    let expression = format!(
        r#"
(async () => {{
  const remoteX = {remote_x};
  const remoteY = {remote_y};
  const img = document.getElementById('shot');
  if (!img) {{ throw new Error('takeover screenshot image missing'); }}
  for (let i = 0; i < 50; i += 1) {{
    if (img.complete && img.naturalWidth > 0 && img.naturalHeight > 0) {{
      const rect = img.getBoundingClientRect();
      return {{
        x: rect.left + (remoteX * rect.width / img.naturalWidth),
        y: rect.top + (remoteY * rect.height / img.naturalHeight),
        naturalWidth: img.naturalWidth,
        naturalHeight: img.naturalHeight,
      }};
    }}
    await new Promise((resolve) => setTimeout(resolve, 100));
  }}
  throw new Error('takeover screenshot image did not load');
}})()
"#,
        remote_x = remote_x,
        remote_y = remote_y,
    );
    let point = cdp::evaluate_json(operator_http_base, &expression)
        .await
        .context("map remote point to takeover screenshot coordinates")?;
    let x = point["x"].as_f64().context("mapped click x missing")?;
    let y = point["y"].as_f64().context("mapped click y missing")?;
    cdp::click(operator_http_base, x, y)
        .await
        .context("click takeover screenshot in operator browser")?;
    wait_operator_keyboard_proxy_focused(operator_http_base).await?;
    Ok(())
}

async fn wait_remote_active_id(cdp_http_base: &str, expected_id: &str) -> Result<()> {
    let expected_json = serde_json::to_string(expected_id)?;
    let expression = format!(
        r#"
(async () => {{
  const expected = {expected_json};
  for (let i = 0; i < 50; i += 1) {{
    const activeElement = document.activeElement ? document.activeElement.id : null;
    if (activeElement === expected) {{
      return {{ activeElement }};
    }}
    await new Promise((resolve) => setTimeout(resolve, 100));
  }}
  return {{ activeElement: document.activeElement ? document.activeElement.id : null }};
}})()
"#,
        expected_json = expected_json,
    );
    let observed = cdp::evaluate_json(cdp_http_base, &expression)
        .await
        .with_context(|| format!("wait for remote focus on {expected_id}"))?;
    ensure!(
        observed["activeElement"] == expected_id,
        "remote page did not focus expected form field"
    );
    Ok(())
}

async fn wait_remote_field_text(cdp_http_base: &str, selector: &str, expected: &str) -> Result<()> {
    let selector_json = serde_json::to_string(selector)?;
    let expected_json = serde_json::to_string(expected)?;
    let expression = format!(
        r#"
(async () => {{
  const selector = {selector_json};
  const expected = {expected_json};
  for (let i = 0; i < 50; i += 1) {{
    const el = document.querySelector(selector);
    const value = el ? (el.isContentEditable ? el.textContent : el.value) : null;
    if (value === expected) {{
      return {{ matched: true }};
    }}
    await new Promise((resolve) => setTimeout(resolve, 100));
  }}
  return {{ matched: false }};
}})()
"#,
        selector_json = selector_json,
        expected_json = expected_json,
    );
    let observed = cdp::evaluate_json(cdp_http_base, &expression)
        .await
        .with_context(|| format!("wait for remote field text in {selector}"))?;
    ensure!(
        observed["matched"].as_bool().unwrap_or(false),
        "remote field did not receive expected synthetic text"
    );
    Ok(())
}

async fn ensure_operator_page_did_not_keep_text(
    operator_http_base: &str,
    text: &str,
) -> Result<()> {
    let text_json = serde_json::to_string(text)?;
    let expression = format!(
        r#"
(() => {{
  const text = {text_json};
  const proxy = document.getElementById('keyboard-proxy');
  const helper = document.getElementById('text');
  return {{
    proxyEmpty: proxy ? proxy.value === '' : false,
    helperContainsText: helper ? helper.value.includes(text) : false,
    bodyContainsText: document.body.innerText.includes(text),
  }};
}})()
"#,
        text_json = text_json,
    );
    let observed = cdp::evaluate_json(operator_http_base, &expression)
        .await
        .context("verify takeover page did not retain typed text")?;
    ensure!(
        observed["proxyEmpty"].as_bool().unwrap_or(false),
        "takeover keyboard proxy retained typed text"
    );
    ensure!(
        !observed["helperContainsText"].as_bool().unwrap_or(true),
        "takeover helper textarea retained typed text"
    );
    ensure!(
        !observed["bodyContainsText"].as_bool().unwrap_or(true),
        "takeover page body exposed typed text"
    );
    Ok(())
}

#[tokio::test]
#[ignore = "requires local Chrome; exercises takeover UI screenshot-click keyboard proxy against common form fields"]
async fn takeover_page_click_then_operator_typing_fills_common_form_fields() -> Result<()> {
    let Some(chrome_path) = chrome_path_from_env_or_known_locations() else {
        eprintln!("skipping: no Chrome/Chromium path found; set HBR_CHROME_PATH");
        return Ok(());
    };

    let echo = EchoServer::spawn().await;
    let runtime = RuntimeApiServer::spawn(chrome_path.clone()).await?;
    let result =
        run_takeover_form_field_keyboard_proxy_regression(&runtime, &echo, chrome_path).await;
    let shutdown = runtime.stop().await;
    echo.stop().await;
    result?;
    shutdown?;
    Ok(())
}

async fn run_takeover_form_field_keyboard_proxy_regression(
    runtime: &RuntimeApiServer,
    echo: &EchoServer,
    chrome_path: PathBuf,
) -> Result<()> {
    let http = reqwest::Client::new();
    let client = BrowserRuntimeClient::new(
        &runtime.base_url,
        Some("integration-smoke-bearer".to_string()),
    )?;
    let persona = persona();
    let create_response = http
        .post(format!("{}/sessions", runtime.base_url))
        .bearer_auth("integration-smoke-bearer")
        .json(&CreateSessionRequest {
            profile_id: Some(format!("takeover-keyboard-{}", Uuid::new_v4())),
            headless: Some(true),
            viewport: Some(persona.viewport.clone()),
            persist_profile: Some(false),
            launch_timeout_secs: Some(20),
            persona: Some(persona.clone()),
            ..Default::default()
        })
        .send()
        .await
        .context("create browser runtime session for takeover keyboard regression")?;
    ensure!(
        create_response.status().is_success(),
        "create browser runtime session for takeover keyboard regression failed"
    );
    let created: Value = create_response
        .json()
        .await
        .context("parse takeover keyboard regression create response")?;
    let session_id = Uuid::parse_str(
        created["id"]
            .as_str()
            .context("create response missing session id")?,
    )?;
    let cdp_ws_url = created["cdp_ws_url"]
        .as_str()
        .context("create response missing CDP websocket URL")?;
    let cdp_http_base = cdp_http_base_from_browser_ws_url(cdp_ws_url)?;

    let form_url = format!("{}/takeover-form", echo.base_url);
    cdp::navigate(&cdp_http_base, &form_url)
        .await
        .context("navigate remote browser to takeover form probe")?;
    let ready = cdp::evaluate_json(
        &cdp_http_base,
        r#"
(async () => {
  for (let i = 0; i < 50; i += 1) {
    if (document.title === 'Takeover form probe' && document.getElementById('editable')) {
      return { title: document.title, fieldsReady: true };
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return { title: document.title, fieldsReady: false };
})()
"#,
    )
    .await
    .context("wait for takeover form probe")?;
    ensure!(
        ready["fieldsReady"] == true,
        "takeover form probe did not finish loading"
    );

    let paused = client
        .pause_session(
            session_id,
            &PauseForHumanRequest {
                reason: Some("takeover keyboard proxy regression".to_string()),
            },
        )
        .await
        .context("pause session for takeover keyboard regression")?;
    let takeover_url = paused["takeover_url"]
        .as_str()
        .context("pause response missing takeover_url")?
        .to_string();

    let operator_tempdir = tempfile::tempdir().context("create operator browser tempdir")?;
    let backend = LocalChromeBackend::new(Some(chrome_path))?;
    let mut operator = backend
        .launch(StartSessionOptions {
            id: Uuid::new_v4(),
            user_data_dir: operator_tempdir.path().join("operator-profile"),
            downloads_dir: operator_tempdir.path().join("operator-downloads"),
            headless: true,
            viewport: persona.viewport.clone(),
            persona,
            launch_timeout: Duration::from_secs(20),
            webrtc_ip_policy: Default::default(),
            gpu_policy: Default::default(),
        })
        .await
        .context("launch operator browser for takeover keyboard regression")?;

    let operator_result = async {
        cdp::navigate(&operator.http_base, &takeover_url)
            .await
            .context("navigate operator browser to takeover page")?;
        let takeover_ready = cdp::evaluate_json(
            &operator.http_base,
            r#"
(async () => {
  for (let i = 0; i < 50; i += 1) {
    const proxy = document.getElementById('keyboard-proxy');
    const img = document.getElementById('shot');
    if (proxy && img && img.complete && img.naturalWidth > 0) {
      return { proxy: true, naturalWidth: img.naturalWidth };
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return { proxy: !!document.getElementById('keyboard-proxy'), naturalWidth: 0 };
})()
"#,
        )
        .await
        .context("wait for takeover page screenshot and keyboard proxy")?;
        ensure!(
            takeover_ready["proxy"] == true
                && takeover_ready["naturalWidth"].as_u64().unwrap_or(0) > 0,
            "takeover page did not expose loaded screenshot and keyboard proxy"
        );

        for (selector, field_id, typed_text) in [
            ("#name", "name", "Synthetic Name"),
            ("#email", "email", "synthetic@example.test"),
            ("#password", "password", "synthetic-password-fixture"),
            ("#notes", "notes", "Synthetic textarea note"),
            ("#editable", "editable", "Synthetic editable text"),
        ] {
            let (x, y) = remote_element_center(&cdp_http_base, selector).await?;
            click_takeover_screenshot_at_remote_point(&operator.http_base, x, y)
                .await
                .with_context(|| format!("click takeover screenshot for {field_id}"))?;
            wait_remote_active_id(&cdp_http_base, field_id).await?;
            cdp::insert_text(&operator.http_base, typed_text)
                .await
                .with_context(|| format!("type through takeover keyboard proxy for {field_id}"))?;
            wait_remote_field_text(&cdp_http_base, selector, typed_text).await?;
            ensure_operator_page_did_not_keep_text(&operator.http_base, typed_text).await?;
        }

        client
            .delete_session(session_id)
            .await
            .context("delete takeover keyboard regression session")?;
        Ok::<(), anyhow::Error>(())
    }
    .await;
    let close_result = backend.close(&mut operator).await;
    operator_result?;
    close_result?;
    Ok(())
}

#[tokio::test]
#[ignore = "requires local Chrome; set HBR_CHROME_NO_SANDBOX=1 on AppArmor/userns hosts; runs real API create/CDP attach/screenshot/takeover/release smoke"]
async fn create_session_connect_playwright_screenshot_close() -> Result<()> {
    let Some(chrome_path) = chrome_path_from_env_or_known_locations() else {
        eprintln!("skipping: no Chrome/Chromium path found; set HBR_CHROME_PATH");
        return Ok(());
    };

    let runtime = RuntimeApiServer::spawn(chrome_path).await?;
    let result = run_create_attach_takeover_smoke(&runtime).await;
    let shutdown = runtime.stop().await;
    result?;
    shutdown?;
    Ok(())
}

async fn run_create_attach_takeover_smoke(runtime: &RuntimeApiServer) -> Result<()> {
    let http = reqwest::Client::new();
    let client = BrowserRuntimeClient::new(
        &runtime.base_url,
        Some("integration-smoke-bearer".to_string()),
    )?;
    let unauthenticated_response = http
        .get(format!("{}/sessions", runtime.base_url))
        .send()
        .await
        .context("send unauthenticated list request")?;
    ensure!(
        unauthenticated_response.status() == StatusCode::UNAUTHORIZED,
        "unauthenticated API request did not fail with 401"
    );
    let unauthenticated_body = unauthenticated_response
        .text()
        .await
        .context("read unauthenticated list response")?;
    ensure!(
        unauthenticated_body.contains("unauthorized"),
        "unauthenticated API response body was not generic unauthorized JSON"
    );

    let persona = persona();
    let create_response = http
        .post(format!("{}/sessions", runtime.base_url))
        .bearer_auth("integration-smoke-bearer")
        .json(&CreateSessionRequest {
            profile_id: Some(format!("attach-smoke-{}", Uuid::new_v4())),
            headless: Some(true),
            viewport: Some(persona.viewport.clone()),
            persist_profile: Some(false),
            launch_timeout_secs: Some(20),
            persona: Some(persona.clone()),
            ..Default::default()
        })
        .send()
        .await
        .context("send browser runtime session create request")?;
    let create_status = create_response.status();
    let create_body = create_response
        .text()
        .await
        .context("read browser runtime session create response")?;
    ensure!(
        create_status.is_success(),
        "create browser runtime session returned {create_status}: {create_body}"
    );
    let created: Value =
        serde_json::from_str(&create_body).context("parse create-session response")?;
    ensure!(
        created["status"] == "running",
        "created session was not running"
    );
    ensure!(
        created["takeover_url"].is_null(),
        "fresh session exposed a takeover URL before pause"
    );
    let created_text = serde_json::to_string(&created)?;
    ensure!(
        !created_text.contains("/takeover/") && !created_text.contains("token="),
        "create-session response leaked takeover material before pause"
    );
    let session_id = Uuid::parse_str(
        created["id"]
            .as_str()
            .context("create-session response missing id")?,
    )
    .context("parse created session id")?;
    let cdp_ws_url = created["cdp_ws_url"]
        .as_str()
        .filter(|value| value.starts_with("ws://") || value.starts_with("wss://"))
        .context("create-session response missing CDP websocket URL")?;
    let cdp_http_base = cdp_http_base_from_browser_ws_url(cdp_ws_url)?;

    let pre_pause_forbidden = http
        .get(format!(
            "{}/takeover/{session_id}?token=pre-pause-probe",
            runtime.base_url
        ))
        .send()
        .await
        .context("probe pre-pause takeover URL")?;
    ensure_forbidden_without_secret_echo(
        pre_pause_forbidden,
        "pre-pause-probe",
        "pre-pause takeover page",
    )
    .await?;

    let echo = EchoServer::spawn().await;
    let smoke_result = async {
        cdp::navigate(&cdp_http_base, &echo.base_url)
            .await
            .context("navigate attached CDP page to echo server")?;
        let observed = cdp::evaluate_json(
            &cdp_http_base,
            r#"
(async () => {
  for (let i = 0; i < 50; i += 1) {
    if (document.title === 'HBR coherence probe' && document.readyState !== 'loading') {
      let input = document.getElementById('smoke-input');
      if (!input) {
        input = document.createElement('input');
        input.id = 'smoke-input';
        input.autocomplete = 'off';
        document.body.appendChild(input);
      }
      input.focus();
      return { title: document.title, href: location.href, activeElement: document.activeElement.id };
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`echo page did not finish loading; title=${document.title} ready=${document.readyState}`);
})()
"#,
        )
        .await
        .context("evaluate attached CDP page")?;
        ensure!(observed["title"] == "HBR coherence probe", "CDP attach saw wrong page");
        ensure!(
            observed["activeElement"] == "smoke-input",
            "CDP setup did not focus smoke input"
        );

        let session_screenshot = client
            .screenshot(session_id)
            .await
            .context("capture screenshot through authenticated session API")?;
        ensure_png(&session_screenshot, "session screenshot")?;

        let paused = client
            .pause_session(
                session_id,
                &PauseForHumanRequest {
                    reason: Some("manual attach takeover smoke".to_string()),
                },
            )
            .await
            .context("pause session for human takeover")?;
        ensure!(
            paused["status"] == "paused_for_human",
            "pause response did not enter paused_for_human"
        );
        let takeover_url = paused["takeover_url"]
            .as_str()
            .context("pause response missing takeover_url")?
            .to_string();
        ensure!(
            takeover_url.starts_with(&format!("{}/takeover/{session_id}?token=", runtime.base_url)),
            "takeover URL did not target the local runtime API server"
        );
        let takeover_token = takeover_token_from_url(&takeover_url)?;
        let persisted_record = tokio::fs::read_to_string(
            runtime
                .store
                .config
                .data_dir
                .join("sessions")
                .join(session_id.to_string())
                .join("session.json"),
        )
        .await
        .context("read persisted paused session record")?;
        ensure!(
            !persisted_record.contains(&takeover_token) && !persisted_record.contains("token="),
            "persisted paused session record leaked takeover token material"
        );

        let wrong_token_response = http
            .get(format!(
                "{}/takeover/{session_id}?token=wrong-takeover-token",
                runtime.base_url
            ))
            .send()
            .await
            .context("probe wrong takeover token")?;
        ensure_forbidden_without_secret_echo(
            wrong_token_response,
            "wrong-takeover-token",
            "wrong-token takeover page",
        )
        .await?;

        let takeover_page_response = http
            .get(&takeover_url)
            .send()
            .await
            .context("load takeover page")?;
        ensure!(
            takeover_page_response.status().is_success(),
            "valid takeover page did not return 2xx"
        );
        let takeover_page = takeover_page_response
            .text()
            .await
            .context("read takeover page")?;
        for marker in [
            "Release browser back to agent",
            "Keyboard helpers",
            "mapScreenshotCoordinates",
            "id=\"keyboard-proxy\"",
            "enqueueRemoteInput('key'",
            "textarea id=\"text\"",
            "never stored in runtime logs",
        ] {
            ensure!(
                takeover_page.contains(marker),
                "takeover page missing marker {marker:?}"
            );
        }

        let takeover_screenshot_response = http
            .get(format!(
                "{}/takeover/{session_id}/screenshot?token={takeover_token}",
                runtime.base_url
            ))
            .send()
            .await
            .context("capture screenshot through takeover token API")?;
        ensure!(
            takeover_screenshot_response.status().is_success(),
            "valid takeover screenshot did not return 2xx"
        );
        let takeover_screenshot = takeover_screenshot_response
            .bytes()
            .await
            .context("read takeover screenshot bytes")?
            .to_vec();
        ensure_png(&takeover_screenshot, "takeover screenshot")?;

        let typed_text = "typed through takeover API";
        let type_response = http
            .post(format!(
                "{}/takeover/{session_id}/type?token={takeover_token}",
                runtime.base_url
            ))
            .json(&json!({"text": typed_text}))
            .send()
            .await
            .context("send takeover type request")?;
        ensure!(
            type_response.status().is_success(),
            "valid takeover type request did not return 2xx"
        );
        let type_json: Value = type_response
            .json()
            .await
            .context("parse takeover type response")?;
        ensure!(type_json["ok"] == true, "takeover type response was not ok");
        let typed_observed = cdp::evaluate_json(
            &cdp_http_base,
            "(() => ({ value: document.getElementById('smoke-input').value }))()",
        )
        .await
        .context("verify typed text through attached CDP page")?;
        ensure!(
            typed_observed["value"] == typed_text,
            "takeover type request did not reach the focused page"
        );

        let wait_client = client.clone();
        let wait_task = tokio::spawn(async move {
            wait_client
                .wait_session(session_id, Duration::from_secs(3))
                .await
        });
        let release_response = http
            .post(format!(
                "{}/takeover/{session_id}/release?token={takeover_token}",
                runtime.base_url
            ))
            .send()
            .await
            .context("release via takeover token API")?;
        ensure!(
            release_response.status().is_success(),
            "valid takeover release did not return 2xx"
        );
        let released: Value = release_response
            .json()
            .await
            .context("parse takeover release response")?;
        ensure!(released["status"] == "running", "release response was not running");
        ensure!(
            released["takeover_url"].is_null(),
            "release response retained takeover_url"
        );
        let wait = wait_task.await.context("join wait-session task")??;
        ensure!(!wait.timed_out, "wait endpoint timed out after takeover release");
        ensure!(
            wait.session.status == SessionStatus::Running,
            "wait endpoint did not observe running session after release"
        );

        let stale_page_response = http
            .get(&takeover_url)
            .send()
            .await
            .context("probe stale takeover page after release")?;
        ensure_forbidden_without_secret_echo(
            stale_page_response,
            &takeover_token,
            "released takeover page",
        )
        .await?;
        let stale_release_response = http
            .post(format!(
                "{}/takeover/{session_id}/release?token={takeover_token}",
                runtime.base_url
            ))
            .send()
            .await
            .context("probe stale takeover release after release")?;
        ensure_forbidden_without_secret_echo(
            stale_release_response,
            &takeover_token,
            "released takeover release",
        )
        .await?;

        let fetched_after_release = client
            .get_session(session_id)
            .await
            .context("fetch session after release")?;
        ensure!(
            fetched_after_release["takeover_url"].is_null(),
            "get-session after release retained takeover_url"
        );
        let fetched_after_release_text = serde_json::to_string(&fetched_after_release)?;
        ensure!(
            !fetched_after_release_text.contains(&takeover_token),
            "get-session after release leaked stale takeover token"
        );

        let artifacts = client
            .list_artifacts(session_id)
            .await
            .context("list artifacts after screenshots")?;
        let artifacts_text = serde_json::to_string(&artifacts)?;
        ensure!(
            !artifacts_text.contains(&takeover_token),
            "artifact listing leaked takeover token"
        );
        let screenshot_count = artifacts["artifacts"]
            .as_array()
            .context("artifact listing missing artifacts array")?
            .iter()
            .filter(|artifact| {
                artifact["kind"] == "screenshot"
                    && artifact["size_bytes"].as_u64().unwrap_or_default() > 8
            })
            .count();
        ensure!(
            screenshot_count >= 2,
            "expected both session and takeover screenshots to be recorded as artifacts"
        );

        let deleted = client
            .delete_session(session_id)
            .await
            .context("delete smoked browser session")?;
        ensure!(deleted["status"] == "closed", "delete response did not close session");
        Ok::<(), anyhow::Error>(())
    }
    .await;
    echo.stop().await;
    smoke_result
}

#[tokio::test]
#[ignore = "requires local Chrome; run manually with HBR_CHROME_PATH if autodetect misses it"]
async fn persistent_profile_restores_cookie_and_local_storage_across_two_runs() -> Result<()> {
    let Some(chrome_path) = chrome_path_from_env_or_known_locations() else {
        eprintln!("skipping: no Chrome/Chromium path found; set HBR_CHROME_PATH");
        return Ok(());
    };
    let echo = EchoServer::spawn().await;
    let tempdir = tempfile::tempdir().context("create browser tempdir")?;
    let profile_dir = tempdir.path().join("profile");
    let backend = LocalChromeBackend::new(Some(chrome_path))?;
    let headless = true;

    let mut first = backend
        .launch(StartSessionOptions {
            id: Uuid::new_v4(),
            user_data_dir: profile_dir.clone(),
            downloads_dir: tempdir.path().join("downloads-1"),
            headless,
            viewport: persona().viewport,
            persona: persona(),
            launch_timeout: Duration::from_secs(15),
            webrtc_ip_policy: Default::default(),
            gpu_policy: Default::default(),
        })
        .await?;
    cdp::navigate(&first.http_base, &echo.base_url).await?;
    cdp::evaluate_json(
        &first.http_base,
        r#"
(async () => {
  document.cookie = 'hbr_cookie=first-run; max-age=3600; path=/; SameSite=Lax';
  localStorage.setItem('hbr_local_storage', 'first-run');
  return { cookie: document.cookie, localStorage: localStorage.getItem('hbr_local_storage') };
})()
"#,
    )
    .await?;
    backend.close(&mut first).await?;

    let mut second = backend
        .launch(StartSessionOptions {
            id: Uuid::new_v4(),
            user_data_dir: profile_dir,
            downloads_dir: tempdir.path().join("downloads-2"),
            headless,
            viewport: persona().viewport,
            persona: persona(),
            launch_timeout: Duration::from_secs(15),
            webrtc_ip_policy: Default::default(),
            gpu_policy: Default::default(),
        })
        .await?;
    cdp::navigate(&second.http_base, &echo.base_url).await?;
    let restored = cdp::evaluate_json(
        &second.http_base,
        r#"
(async () => ({
  cookie: document.cookie,
  localStorage: localStorage.getItem('hbr_local_storage')
}))()
"#,
    )
    .await?;
    assert!(
        restored["cookie"]
            .as_str()
            .unwrap_or_default()
            .contains("hbr_cookie=first-run"),
        "cookie was not restored from persistent profile: {restored:?}"
    );
    assert_eq!(restored["localStorage"], "first-run");

    backend.close(&mut second).await?;
    echo.stop().await;
    Ok(())
}
