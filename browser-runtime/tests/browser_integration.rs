use std::{net::SocketAddr, process::Command, sync::Arc, time::Duration};

use hermes_browser_runtime::{
    api,
    backend::LocalChromeBackend,
    config::RuntimeConfig,
    models::{CreateSessionRequest, CreateSessionResponse},
    store::AppStore,
};
use tokio::{net::TcpListener, task::JoinHandle};

struct TestRuntime {
    _tmp: tempfile::TempDir,
    base: String,
    server: JoinHandle<()>,
}

fn playwright_available() -> bool {
    Command::new("node")
        .arg("-e")
        .arg("require('playwright-core'); console.log('ok')")
        .output()
        .map(|out| out.status.success())
        .unwrap_or(false)
}

async fn start_runtime() -> Option<TestRuntime> {
    if !playwright_available() {
        eprintln!("skipping: node/playwright-core not available");
        return None;
    }
    let Some(chrome) = std::env::var_os("HBR_CHROME_PATH") else {
        eprintln!("skipping: set HBR_CHROME_PATH to Chrome/Chromium binary");
        return None;
    };
    let tmp = tempfile::tempdir().unwrap();
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let bind: SocketAddr = listener.local_addr().unwrap();
    let config = RuntimeConfig {
        bind,
        data_dir: tmp.path().to_path_buf(),
        chrome_path: Some(chrome.clone().into()),
        bearer_token: None,
        default_headless: true,
        takeover_ttl: Duration::from_secs(60),
    };
    let store = Arc::new(
        AppStore::new(
            config,
            Arc::new(LocalChromeBackend::new(Some(chrome.into())).unwrap()),
        )
        .await
        .unwrap(),
    );
    let app = api::router(store);
    let server = tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });
    Some(TestRuntime {
        _tmp: tmp,
        base: format!("http://{}", bind),
        server,
    })
}

async fn create_session(base: &str, profile_id: &str) -> CreateSessionResponse {
    let response = reqwest::Client::new()
        .post(format!("{base}/sessions"))
        .json(&CreateSessionRequest {
            profile_id: Some(profile_id.into()),
            headless: Some(true),
            viewport: None,
            persist_profile: Some(true),
        })
        .send()
        .await
        .unwrap();
    assert!(
        response.status().is_success(),
        "{}",
        response.text().await.unwrap()
    );
    response.json::<CreateSessionResponse>().await.unwrap()
}

async fn delete_session(base: &str, id: uuid::Uuid) {
    let _ = reqwest::Client::new()
        .delete(format!("{base}/sessions/{id}"))
        .send()
        .await
        .unwrap();
}

async fn run_node(script: &'static str, envs: Vec<(&'static str, String)>) {
    tokio::task::spawn_blocking(move || {
        let mut command = Command::new("node");
        command.arg("-e").arg(script);
        for (key, value) in envs {
            command.env(key, value);
        }
        let out = command.output().unwrap();
        assert!(
            out.status.success(),
            "{}",
            String::from_utf8_lossy(&out.stderr)
        );
    })
    .await
    .unwrap();
}

#[tokio::test]
#[ignore = "requires Chrome and node package playwright-core; run manually"]
async fn create_session_connect_playwright_screenshot_close() {
    let Some(runtime) = start_runtime().await else {
        return;
    };
    let session = create_session(&runtime.base, "itest-screenshot").await;
    let script = r#"
const { chromium } = require('playwright-core');
(async () => {
  const browser = await chromium.connectOverCDP(process.env.CDP_WS_URL);
  const ctx = browser.contexts()[0];
  const page = ctx.pages()[0] || await ctx.newPage();
  await page.goto('data:text/html,<h1>Hermes Browser Runtime</h1>');
  const png = await page.screenshot();
  if (!png || png.length < 100) throw new Error('empty screenshot');
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
"#;
    run_node(script, vec![("CDP_WS_URL", session.cdp_ws_url.clone())]).await;
    delete_session(&runtime.base, session.id).await;
    runtime.server.abort();
}

#[tokio::test]
#[ignore = "requires Chrome and node package playwright-core; run manually"]
async fn persistent_profile_restores_cookie_and_local_storage() {
    let Some(runtime) = start_runtime().await else {
        return;
    };
    let first = create_session(&runtime.base, "itest-persist").await;
    let set_script = r#"
const { chromium } = require('playwright-core');
(async () => {
  const browser = await chromium.connectOverCDP(process.env.CDP_WS_URL);
  const ctx = browser.contexts()[0];
  const page = ctx.pages()[0] || await ctx.newPage();
  await page.goto(process.env.ORIGIN + '/health');
  await page.evaluate(() => localStorage.setItem('hbr_local', 'persisted'));
  await ctx.addCookies([{ name: 'hbr_cookie', value: 'persisted', url: process.env.ORIGIN }]);
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
"#;
    run_node(
        set_script,
        vec![
            ("CDP_WS_URL", first.cdp_ws_url.clone()),
            ("ORIGIN", runtime.base.clone()),
        ],
    )
    .await;
    delete_session(&runtime.base, first.id).await;

    let second = create_session(&runtime.base, "itest-persist").await;
    let check_script = r#"
const { chromium } = require('playwright-core');
(async () => {
  const browser = await chromium.connectOverCDP(process.env.CDP_WS_URL);
  const ctx = browser.contexts()[0];
  const page = ctx.pages()[0] || await ctx.newPage();
  await page.goto(process.env.ORIGIN + '/health');
  const local = await page.evaluate(() => localStorage.getItem('hbr_local'));
  const cookies = await ctx.cookies(process.env.ORIGIN);
  if (local !== 'persisted') throw new Error('localStorage did not persist: ' + local);
  if (!cookies.some(c => c.name === 'hbr_cookie' && c.value === 'persisted')) throw new Error('cookie did not persist: ' + JSON.stringify(cookies));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
"#;
    run_node(
        check_script,
        vec![
            ("CDP_WS_URL", second.cdp_ws_url.clone()),
            ("ORIGIN", runtime.base.clone()),
        ],
    )
    .await;
    delete_session(&runtime.base, second.id).await;
    runtime.server.abort();
}
