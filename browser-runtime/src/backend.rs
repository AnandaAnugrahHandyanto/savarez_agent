use std::{
    ffi::OsString,
    fs,
    future::Future,
    net::TcpListener,
    path::{Path, PathBuf},
    pin::Pin,
    process::{Command as StdCommand, ExitStatus, Stdio},
    time::Duration,
};

use anyhow::{Context, Result, bail};
use async_trait::async_trait;
use tokio::{
    process::{Child, Command},
    time::{Instant, sleep},
};
use tracing::{debug, info, warn};
use uuid::Uuid;

use crate::{
    cdp, display,
    models::{BrowserPersona, GpuPolicy, Viewport, WebRtcIpPolicy, extract_chrome_full_version},
};

#[derive(Debug, Clone)]
pub struct StartSessionOptions {
    pub id: Uuid,
    pub user_data_dir: PathBuf,
    pub downloads_dir: PathBuf,
    pub headless: bool,
    pub viewport: Viewport,
    pub persona: BrowserPersona,
    pub webrtc_ip_policy: WebRtcIpPolicy,
    pub gpu_policy: GpuPolicy,
    pub launch_timeout: Duration,
}

#[derive(Debug)]
pub struct LaunchedBrowser {
    pub process: Child,
    pub port: u16,
    pub http_base: String,
    pub cdp_ws_url: String,
    pub persona_guard: Option<cdp::PersonaGuard>,
}

#[async_trait]
pub trait BrowserBackend: Send + Sync + 'static {
    async fn launch(&self, options: StartSessionOptions) -> Result<LaunchedBrowser>;
    async fn close(&self, launched: &mut LaunchedBrowser) -> Result<()>;
}

#[derive(Debug, Clone)]
pub struct LocalChromeBackend {
    chrome_path: PathBuf,
}

impl LocalChromeBackend {
    pub fn new(chrome_path: Option<PathBuf>) -> Result<Self> {
        let env_override = std::env::var_os("HBR_CHROME_PATH").map(PathBuf::from);
        let autodetected = find_chrome_path();
        Self::from_candidates(chrome_path, env_override, autodetected)
    }

    fn from_candidates(
        chrome_path: Option<PathBuf>,
        env_override: Option<PathBuf>,
        autodetected: Option<PathBuf>,
    ) -> Result<Self> {
        let chrome_path = resolve_chrome_path(chrome_path, env_override, autodetected)?;
        Ok(Self { chrome_path })
    }

    pub fn chrome_path(&self) -> &Path {
        &self.chrome_path
    }
}

#[async_trait]
impl BrowserBackend for LocalChromeBackend {
    async fn launch(&self, options: StartSessionOptions) -> Result<LaunchedBrowser> {
        let chrome_path = self.chrome_path.as_path();
        let no_sandbox = std::env::var_os("HBR_CHROME_NO_SANDBOX").is_some();
        let retry_delay = Duration::from_millis(150);
        let fetch_version = fetch_browser_version;
        let open_new_page = open_blank_page;
        launch_with(
            chrome_path,
            options,
            no_sandbox,
            retry_delay,
            fetch_version,
            open_new_page,
        )
        .await
    }

    async fn close(&self, launched: &mut LaunchedBrowser) -> Result<()> {
        let timeout = Duration::from_secs(5);
        let close_browser = |browser_ws_url: String| -> AsyncResult<()> {
            Box::pin(async move { cdp::browser_close(&browser_ws_url).await })
        };
        close_with(launched, timeout, close_browser).await
    }
}

type AsyncResult<T> = Pin<Box<dyn Future<Output = Result<T>> + Send>>;

fn open_blank_page(http_base: String, url: String) -> AsyncResult<()> {
    Box::pin(async move { cdp::open_new_page(&http_base, &url).await })
}

fn fetch_browser_version(http_base: String) -> AsyncResult<cdp::VersionInfo> {
    Box::pin(async move { cdp::fetch_version(&http_base).await })
}

async fn launch_with<FV, OP>(
    chrome_path: &Path,
    options: StartSessionOptions,
    no_sandbox: bool,
    retry_delay: Duration,
    fetch_version: FV,
    open_new_page: OP,
) -> Result<LaunchedBrowser>
where
    FV: Fn(String) -> AsyncResult<cdp::VersionInfo>,
    OP: Fn(String, String) -> AsyncResult<()>,
{
    launch_with_port_allocator(
        chrome_path,
        options,
        no_sandbox,
        retry_delay,
        free_local_port,
        fetch_version,
        open_new_page,
    )
    .await
}

async fn launch_with_port_allocator<FV, OP, FP>(
    chrome_path: &Path,
    options: StartSessionOptions,
    no_sandbox: bool,
    retry_delay: Duration,
    port_allocator: FP,
    fetch_version: FV,
    open_new_page: OP,
) -> Result<LaunchedBrowser>
where
    FP: FnOnce() -> Result<u16>,
    FV: Fn(String) -> AsyncResult<cdp::VersionInfo>,
    OP: Fn(String, String) -> AsyncResult<()>,
{
    launch_with_port_allocator_and_poll(
        chrome_path,
        options,
        no_sandbox,
        retry_delay,
        port_allocator,
        fetch_version,
        open_new_page,
        poll_process_exit,
    )
    .await
}

#[allow(clippy::too_many_arguments)]
async fn launch_with_port_allocator_and_poll<FV, OP, FP, PP>(
    chrome_path: &Path,
    options: StartSessionOptions,
    no_sandbox: bool,
    retry_delay: Duration,
    port_allocator: FP,
    fetch_version: FV,
    open_new_page: OP,
    poll_process: PP,
) -> Result<LaunchedBrowser>
where
    FP: FnOnce() -> Result<u16>,
    FV: Fn(String) -> AsyncResult<cdp::VersionInfo>,
    OP: Fn(String, String) -> AsyncResult<()>,
    PP: Fn(&mut Child) -> Result<Option<ExitStatus>>,
{
    // COVERAGE-EXCEPTION: llvm-cov can charge instantiation-only misses to the
    // create_dir_all/port_allocator/spawn/poll_process calls in this generic
    // async helper even when deterministic tests cover the real source flow.
    // See browser-runtime/docs/implementation-plan.md for the approved evidence.
    fs::create_dir_all(&options.user_data_dir).context("create user data dir")?;
    fs::create_dir_all(&options.downloads_dir).context("create downloads dir")?;
    let port = port_allocator()?;
    let http_base = format!("http://127.0.0.1:{port}");
    let plan = chrome_command_plan(
        chrome_path,
        &options,
        port,
        no_sandbox,
        std::env::var_os("DISPLAY"),
        std::env::var_os("WAYLAND_DISPLAY"),
        display::find_xvfb_run_path(),
    )?;
    let mut command = command_from_plan(&plan);
    command
        .env("TZ", &options.persona.timezone_id)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    let launch_message = format!(
        "launching local chrome chrome={} port={port} display_mode={}",
        chrome_path.display(),
        plan.display_mode.label()
    );
    info!(session_id=%options.id, "{launch_message}");
    let mut process = command.spawn().context("spawn Chrome")?;
    let started = Instant::now();
    loop {
        if let Some(status) = poll_process(&mut process)? {
            bail!("Chrome exited before CDP became ready: {status}");
        }
        match fetch_version(http_base.clone()).await {
            Ok(version) => {
                debug!(session_id=%options.id, "CDP ready");
                let browser_user_agent = version.user_agent.clone();
                let _ = open_new_page(http_base.clone(), "about:blank".to_string()).await;
                let persona_guard = match cdp::start_persona_guard(
                    &http_base,
                    &options.persona,
                    browser_user_agent.as_deref(),
                )
                .await
                {
                    Ok(guard) => Some(guard),
                    Err(err) => {
                        warn!(session_id=%options.id, error=%err, "failed to start browser persona guard");
                        if let Err(err) = cdp::apply_persona(
                            &http_base,
                            &options.persona,
                            browser_user_agent.as_deref(),
                        )
                        .await
                        {
                            warn!(session_id=%options.id, error=%err, "failed to apply browser persona");
                        }
                        None
                    }
                };
                return Ok(LaunchedBrowser {
                    process,
                    port,
                    http_base,
                    cdp_ws_url: version.web_socket_debugger_url,
                    persona_guard,
                });
            }
            Err(err) if started.elapsed() < options.launch_timeout => {
                debug!(session_id=%options.id, error=%err, "waiting for CDP");
                sleep(retry_delay).await;
            }
            Err(err) => {
                let _ = process.start_kill();
                bail!(
                    "Chrome CDP did not become ready within {:?}: {err}",
                    options.launch_timeout
                );
            }
        }
    }
}

fn poll_process_exit(process: &mut Child) -> Result<Option<ExitStatus>> {
    poll_process_exit_with(process, Child::try_wait)
}

fn poll_process_exit_with<F>(process: &mut Child, try_wait: F) -> Result<Option<ExitStatus>>
where
    F: FnOnce(&mut Child) -> std::io::Result<Option<ExitStatus>>,
{
    try_wait(process).context("poll Chrome process")
}

async fn close_with<F>(
    launched: &mut LaunchedBrowser,
    wait_timeout: Duration,
    browser_close: F,
) -> Result<()>
where
    F: Fn(String) -> AsyncResult<()>,
{
    if let Some(mut guard) = launched.persona_guard.take() {
        guard.abort();
    }
    let _ = browser_close(launched.cdp_ws_url.clone()).await;
    match tokio::time::timeout(wait_timeout, launched.process.wait()).await {
        Ok(Ok(_status)) => Ok(()),
        _ => {
            let _ = launched.process.start_kill();
            let _ = launched.process.wait().await;
            Ok(())
        }
    }
}

fn free_local_port() -> Result<u16> {
    free_local_port_with(bind_ephemeral_listener)
}

fn free_local_port_with<F>(bind: F) -> Result<u16>
where
    F: FnOnce() -> Result<TcpListener>,
{
    let listener = bind()?;
    local_port(&listener)
}

fn bind_ephemeral_listener() -> Result<TcpListener> {
    bind_ephemeral_listener_with(|| TcpListener::bind(("127.0.0.1", 0)))
}

fn bind_ephemeral_listener_with<F>(bind: F) -> Result<TcpListener>
where
    F: FnOnce() -> std::io::Result<TcpListener>,
{
    bind().context("bind ephemeral port")
}

fn local_port(listener: &TcpListener) -> Result<u16> {
    local_port_with(listener, TcpListener::local_addr)
}

fn local_port_with<F>(listener: &TcpListener, local_addr: F) -> Result<u16>
where
    F: FnOnce(&TcpListener) -> std::io::Result<std::net::SocketAddr>,
{
    Ok(local_addr(listener)?.port())
}

fn resolve_chrome_path(
    explicit: Option<PathBuf>,
    env_override: Option<PathBuf>,
    autodetected: Option<PathBuf>,
) -> Result<PathBuf> {
    explicit.or(env_override).or(autodetected).ok_or_else(|| {
        anyhow::anyhow!(
            "Chrome/Chromium not found. Set HBR_CHROME_PATH or install Chrome/Chromium."
        )
    })
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum ChromeDisplayMode {
    Headless,
    LocalDisplay,
    Xvfb(PathBuf),
}

impl ChromeDisplayMode {
    fn label(&self) -> &'static str {
        match self {
            Self::Headless => "headless",
            Self::LocalDisplay => "local-display",
            Self::Xvfb(_) => "xvfb",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct ChromeCommandPlan {
    program: PathBuf,
    args: Vec<OsString>,
    display_mode: ChromeDisplayMode,
}

fn chrome_command_plan(
    chrome_path: &Path,
    options: &StartSessionOptions,
    port: u16,
    no_sandbox: bool,
    display_env: Option<OsString>,
    wayland_display_env: Option<OsString>,
    xvfb_run_path: Option<PathBuf>,
) -> Result<ChromeCommandPlan> {
    let display_mode = chrome_display_mode(
        options.headless,
        display_env,
        wayland_display_env,
        xvfb_run_path,
    )?;
    let launch_chrome_full_version = chrome_binary_full_version(chrome_path);
    let chrome_args = chrome_args_for_launch(
        options,
        port,
        no_sandbox,
        launch_chrome_full_version.as_deref(),
    );
    match display_mode.clone() {
        ChromeDisplayMode::Xvfb(xvfb_run) => {
            let mut args = vec![
                OsString::from("-a"),
                OsString::from("-s"),
                OsString::from(format!(
                    "-screen 0 {}x{}x24",
                    options.viewport.width, options.viewport.height
                )),
                chrome_path.as_os_str().to_os_string(),
            ];
            args.extend(chrome_args.into_iter().map(OsString::from));
            Ok(ChromeCommandPlan {
                program: xvfb_run,
                args,
                display_mode,
            })
        }
        ChromeDisplayMode::Headless | ChromeDisplayMode::LocalDisplay => Ok(ChromeCommandPlan {
            program: chrome_path.to_path_buf(),
            args: chrome_args.into_iter().map(OsString::from).collect(),
            display_mode,
        }),
    }
}

fn chrome_display_mode(
    headless: bool,
    display_env: Option<OsString>,
    wayland_display_env: Option<OsString>,
    xvfb_run_path: Option<PathBuf>,
) -> Result<ChromeDisplayMode> {
    if headless {
        return Ok(ChromeDisplayMode::Headless);
    }
    if display::local_display_available(display_env, wayland_display_env) {
        return Ok(ChromeDisplayMode::LocalDisplay);
    }
    if let Some(path) = xvfb_run_path {
        return Ok(ChromeDisplayMode::Xvfb(path));
    }
    bail!(
        "headed Chrome requested but no DISPLAY/WAYLAND_DISPLAY or xvfb-run is available; set HBR_HEADLESS=1, run under a display/Xvfb wrapper, or set HBR_XVFB_RUN_PATH"
    )
}

fn command_from_plan(plan: &ChromeCommandPlan) -> Command {
    let mut command = Command::new(&plan.program);
    command.args(&plan.args);
    command
}

#[cfg(test)]
fn chrome_args(options: &StartSessionOptions, port: u16, no_sandbox: bool) -> Vec<String> {
    chrome_args_with_user_agent(
        options,
        port,
        no_sandbox,
        Some(options.persona.resolved_user_agent(None)),
    )
}

fn chrome_args_for_launch(
    options: &StartSessionOptions,
    port: u16,
    no_sandbox: bool,
    chrome_full_version: Option<&str>,
) -> Vec<String> {
    chrome_args_with_user_agent(
        options,
        port,
        no_sandbox,
        options
            .persona
            .resolved_launch_user_agent(chrome_full_version),
    )
}

fn chrome_args_with_user_agent(
    options: &StartSessionOptions,
    port: u16,
    no_sandbox: bool,
    user_agent: Option<String>,
) -> Vec<String> {
    let mut args = vec![
        format!("--remote-debugging-port={port}"),
        format!("--user-data-dir={}", options.user_data_dir.display()),
        "--no-first-run".to_string(),
        "--no-default-browser-check".to_string(),
        "--disable-background-networking".to_string(),
        "--disable-sync".to_string(),
        "--disable-extensions".to_string(),
        "--disable-dev-shm-usage".to_string(),
        format!(
            "--window-size={},{}",
            options.viewport.width, options.viewport.height
        ),
        format!("--lang={}", &options.persona.locale),
        format!("--accept-lang={}", &options.persona.accept_language),
    ];
    if let Some(user_agent) = user_agent {
        args.push(format!("--user-agent={user_agent}"));
    }
    args.extend([
        "--disable-blink-features=AutomationControlled".to_string(),
        format!(
            "--force-device-scale-factor={}",
            options.persona.device_scale_factor
        ),
        format!(
            "--download-default-directory={}",
            options.downloads_dir.display()
        ),
        format!(
            "--force-webrtc-ip-handling-policy={}",
            options.webrtc_ip_policy.as_chrome_value()
        ),
    ]);
    if options.headless {
        args.push("--headless=new".to_string());
        if options.gpu_policy != GpuPolicy::SwiftshaderCompat {
            args.push("--disable-gpu".to_string());
        }
    }
    match options.gpu_policy {
        GpuPolicy::Auto => {}
        GpuPolicy::SwiftshaderCompat => {
            args.push("--use-gl=angle".to_string());
            args.push("--use-angle=swiftshader-webgl".to_string());
            args.push("--enable-unsafe-swiftshader".to_string());
        }
        GpuPolicy::Disable3d => {
            args.push("--disable-3d-apis".to_string());
        }
    }
    if no_sandbox {
        args.push("--no-sandbox".to_string());
    }
    args.push("about:blank".to_string());
    args
}

fn chrome_binary_full_version(chrome_path: &Path) -> Option<String> {
    chrome_binary_full_version_with_timeout(chrome_path, Duration::from_millis(200))
}

fn chrome_binary_full_version_with_timeout(
    chrome_path: &Path,
    timeout: Duration,
) -> Option<String> {
    let mut child = StdCommand::new(chrome_path)
        .arg("--version")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .ok()?;
    let started = std::time::Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(_status)) => {
                let output = child.wait_with_output().ok()?;
                if !output.status.success() {
                    return None;
                }
                let text = format!(
                    "{}\n{}",
                    String::from_utf8_lossy(&output.stdout),
                    String::from_utf8_lossy(&output.stderr)
                );
                return extract_chrome_full_version(&text);
            }
            Ok(None) if started.elapsed() < timeout => {
                std::thread::sleep(Duration::from_millis(10));
            }
            Ok(None) => {
                let _ = child.kill();
                let _ = child.wait();
                return None;
            }
            Err(_) => {
                let _ = child.kill();
                let _ = child.wait();
                return None;
            }
        }
    }
}

fn find_chrome_path() -> Option<PathBuf> {
    let candidates = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/opt/google/chrome/chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
        "/usr/bin/brave-browser",
        "/opt/brave.com/brave/brave-browser",
    ];
    candidates
        .iter()
        .map(PathBuf::from)
        .find(|path| path.exists())
        .or_else(find_playwright_chromium)
}

fn find_playwright_chromium() -> Option<PathBuf> {
    find_playwright_chromium_from_home(dirs::home_dir())
}

fn find_playwright_chromium_from_home(home_dir: Option<PathBuf>) -> Option<PathBuf> {
    let base = home_dir?.join(".cache/ms-playwright");
    find_playwright_chromium_in(&base)
}

fn find_playwright_chromium_in(base: &Path) -> Option<PathBuf> {
    let entries = fs::read_dir(base).ok()?;
    let mut matches: Vec<PathBuf> = entries
        .flatten()
        .flat_map(|entry| {
            let root = entry.path();
            [
                root.join("chrome-linux/chrome"),
                root.join("chrome-linux64/chrome"),
                root.join("chrome-headless-shell-linux64/chrome-headless-shell"),
            ]
        })
        .filter(|path| path.exists())
        .collect();
    matches.sort();
    matches.pop()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_support::MockCdpServer;
    use std::{
        sync::{
            Arc, OnceLock,
            atomic::{AtomicUsize, Ordering},
        },
        time::Duration,
    };
    use tokio::sync::Mutex;

    fn scripted_backend_test_lock() -> &'static Mutex<()> {
        static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
        LOCK.get_or_init(|| Mutex::new(()))
    }

    fn env_test_lock() -> &'static std::sync::Mutex<()> {
        static LOCK: OnceLock<std::sync::Mutex<()>> = OnceLock::new();
        LOCK.get_or_init(|| std::sync::Mutex::new(()))
    }

    fn init_test_tracing() {
        static TRACING: OnceLock<()> = OnceLock::new();
        TRACING.get_or_init(|| {
            let _ = tracing_subscriber::fmt()
                .with_test_writer()
                .with_max_level(tracing::Level::TRACE)
                .try_init();
        });
    }

    fn start_options() -> StartSessionOptions {
        StartSessionOptions {
            id: Uuid::nil(),
            user_data_dir: PathBuf::from("/tmp/profile"),
            downloads_dir: PathBuf::from("/tmp/downloads"),
            headless: true,
            viewport: Viewport {
                width: 1280,
                height: 720,
            },
            persona: BrowserPersona::default(),
            webrtc_ip_policy: WebRtcIpPolicy::default(),
            gpu_policy: GpuPolicy::default(),
            launch_timeout: Duration::from_secs(5),
        }
    }

    fn start_options_in(base: &Path, launch_timeout: Duration) -> StartSessionOptions {
        StartSessionOptions {
            id: Uuid::new_v4(),
            user_data_dir: base.join("profile"),
            downloads_dir: base.join("downloads"),
            launch_timeout,
            ..start_options()
        }
    }

    fn write_executable_script(dir: &Path, name: &str, body: &str) -> PathBuf {
        let path = dir.join(name);
        let temp_path = dir.join(format!("{name}.tmp"));
        fs::write(&temp_path, format!("#!/bin/sh\nset -eu\n{body}\n")).unwrap();
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;

            let mut perms = fs::metadata(&temp_path).unwrap().permissions();
            perms.set_mode(0o755);
            fs::set_permissions(&temp_path, perms).unwrap();
        }
        fs::rename(&temp_path, &path).unwrap();
        path
    }

    fn write_mock_chrome_http_server_script(dir: &Path, name: &str) -> PathBuf {
        write_executable_script(
            dir,
            name,
            r#"port=""
for arg in "$@"; do
    case "$arg" in
        --remote-debugging-port=*) port="${arg#*=}" ;;
    esac
done
test -n "$port"
exec python3 - "$port" <<'PY'
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

port = int(sys.argv[1])


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/json/version":
            body = json.dumps(
                {"webSocketDebuggerUrl": "ws://127.0.0.1:9/devtools/browser/test"}
            ).encode()
            self.send_response(200)
        elif self.path.startswith("/json/new?"):
            body = b"{}"
            self.send_response(200)
        else:
            body = b"not found"
            self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


HTTPServer(("127.0.0.1", port), Handler).serve_forever()
PY"#,
        )
    }

    #[test]
    fn finds_a_free_local_port() {
        let port = free_local_port().unwrap();
        assert!(port > 0);
    }

    #[test]
    fn bind_ephemeral_listener_adds_context_on_bind_errors() {
        let err =
            bind_ephemeral_listener_with(|| Err(std::io::Error::other("bind failed"))).unwrap_err();

        assert!(err.to_string().contains("bind ephemeral port"));
    }

    #[test]
    fn free_local_port_propagates_bind_errors() {
        let err = free_local_port_with(|| Err(anyhow::anyhow!("bind failed"))).unwrap_err();

        assert!(err.to_string().contains("bind failed"));
    }

    #[test]
    fn free_local_port_reports_local_addr_errors() {
        let listener = TcpListener::bind(("127.0.0.1", 0)).unwrap();
        let err = local_port_with(&listener, |_| {
            Err(std::io::Error::other("local addr failed"))
        })
        .unwrap_err();

        assert!(err.to_string().contains("local addr failed"));
    }

    #[test]
    fn resolves_chrome_path_from_explicit_env_or_detected_values() {
        let explicit = PathBuf::from("/tmp/explicit-chrome");
        let env_path = PathBuf::from("/tmp/env-chrome");
        let detected = PathBuf::from("/tmp/detected-chrome");

        assert_eq!(
            resolve_chrome_path(
                Some(explicit.clone()),
                Some(env_path.clone()),
                Some(detected.clone())
            )
            .unwrap(),
            explicit
        );
        assert_eq!(
            resolve_chrome_path(None, Some(env_path.clone()), Some(detected.clone())).unwrap(),
            env_path
        );
        assert_eq!(
            resolve_chrome_path(None, None, Some(detected.clone())).unwrap(),
            detected
        );
        assert!(
            resolve_chrome_path(None, None, None)
                .unwrap_err()
                .to_string()
                .contains("Chrome/Chromium not found")
        );
    }

    #[test]
    fn chrome_args_include_headless_and_optional_sandbox_flags() {
        let mut options = start_options();
        let headless_args = chrome_args(&options, 9222, true);
        assert!(headless_args.contains(&"--headless=new".to_string()));
        assert!(headless_args.contains(&"--disable-gpu".to_string()));
        assert!(headless_args.contains(&"--no-sandbox".to_string()));
        assert!(headless_args.contains(&"about:blank".to_string()));
        assert!(headless_args.contains(
            &"--force-webrtc-ip-handling-policy=default_public_interface_only".to_string()
        ));
        assert!(headless_args.contains(&"--remote-debugging-port=9222".to_string()));
        assert!(
            headless_args
                .iter()
                .any(|arg| arg.starts_with("--user-agent=") && !arg.contains("HeadlessChrome"))
        );
        assert!(
            headless_args.contains(&"--disable-blink-features=AutomationControlled".to_string())
        );

        options.headless = false;
        let headful_args = chrome_args(&options, 9333, false);
        assert!(!headful_args.contains(&"--headless=new".to_string()));
        assert!(!headful_args.contains(&"--disable-gpu".to_string()));
        assert!(!headful_args.contains(&"--no-sandbox".to_string()));
        assert!(headful_args.contains(&"--remote-debugging-port=9333".to_string()));
    }

    #[test]
    fn chrome_command_plan_uses_binary_version_for_launch_user_agent() {
        let tmp = tempfile::tempdir().unwrap();
        let chrome = write_executable_script(
            tmp.path(),
            "versioned-chrome",
            r#"if [ "${1:-}" = "--version" ]; then
    echo "Google Chrome 143.0.7499.40"
    exit 0
fi
sleep 60"#,
        );
        let options = start_options();

        let plan = chrome_command_plan(&chrome, &options, 9222, true, None, None, None).unwrap();
        let args: Vec<String> = plan
            .args
            .iter()
            .map(|arg| arg.to_string_lossy().into_owned())
            .collect();
        let user_agent_arg = args
            .iter()
            .find(|arg| arg.starts_with("--user-agent="))
            .expect("launch should include a coherent user agent when Chrome reports a version");

        assert!(user_agent_arg.contains("Chrome/143.0.7499.40"));
        assert!(!user_agent_arg.contains("Chrome/125.0.0.0"));
        assert!(!user_agent_arg.contains("HeadlessChrome"));
    }

    #[test]
    fn chrome_command_plan_omits_default_launch_user_agent_when_binary_version_unknown() {
        let tmp = tempfile::tempdir().unwrap();
        let chrome = write_executable_script(
            tmp.path(),
            "unknown-version-chrome",
            r#"if [ "${1:-}" = "--version" ]; then
    exit 1
fi
sleep 60"#,
        );
        let options = start_options();

        let plan = chrome_command_plan(&chrome, &options, 9222, true, None, None, None).unwrap();
        let args: Vec<String> = plan
            .args
            .iter()
            .map(|arg| arg.to_string_lossy().into_owned())
            .collect();

        assert!(
            args.iter().all(|arg| !arg.starts_with("--user-agent=")),
            "must not launch with stale Chrome/125 fallback when Chrome version is unknown: {args:?}"
        );
    }

    #[test]
    fn chrome_args_apply_webrtc_and_gpu_policy_flags() {
        let mut options = start_options();
        options.webrtc_ip_policy = WebRtcIpPolicy::DisableNonProxiedUdp;
        options.gpu_policy = GpuPolicy::SwiftshaderCompat;

        let args = chrome_args(&options, 9222, false);
        assert!(
            args.contains(&"--force-webrtc-ip-handling-policy=disable_non_proxied_udp".to_string())
        );
        assert!(args.contains(&"--headless=new".to_string()));
        assert!(!args.contains(&"--disable-gpu".to_string()));
        assert!(args.contains(&"--use-gl=angle".to_string()));
        assert!(args.contains(&"--use-angle=swiftshader-webgl".to_string()));
        assert!(args.contains(&"--enable-unsafe-swiftshader".to_string()));

        options.gpu_policy = GpuPolicy::Disable3d;
        let args = chrome_args(&options, 9222, false);
        assert!(args.contains(&"--disable-gpu".to_string()));
        assert!(args.contains(&"--disable-3d-apis".to_string()));
        assert!(!args.contains(&"--use-angle=swiftshader-webgl".to_string()));
    }

    #[test]
    fn chrome_command_plan_uses_xvfb_for_headed_sessions_without_display() {
        let mut options = start_options();
        options.headless = false;

        let plan = chrome_command_plan(
            Path::new("/opt/chrome/chrome"),
            &options,
            9333,
            false,
            None,
            None,
            Some(PathBuf::from("/usr/bin/xvfb-run")),
        )
        .unwrap();
        let args: Vec<String> = plan
            .args
            .iter()
            .map(|arg| arg.to_string_lossy().into_owned())
            .collect();

        assert_eq!(plan.program, PathBuf::from("/usr/bin/xvfb-run"));
        assert_eq!(
            plan.display_mode,
            ChromeDisplayMode::Xvfb(PathBuf::from("/usr/bin/xvfb-run"))
        );
        assert_eq!(args[0], "-a");
        assert_eq!(args[1], "-s");
        assert_eq!(args[2], "-screen 0 1280x720x24");
        assert_eq!(args[3], "/opt/chrome/chrome");
        assert!(args.contains(&"--remote-debugging-port=9333".to_string()));
        assert!(!args.contains(&"--headless=new".to_string()));
    }

    #[test]
    fn chrome_command_plan_prefers_local_display_and_clear_error_without_display_support() {
        let mut options = start_options();
        options.headless = false;

        let local = chrome_command_plan(
            Path::new("/opt/chrome/chrome"),
            &options,
            9333,
            false,
            Some(OsString::from(":1")),
            None,
            Some(PathBuf::from("/usr/bin/xvfb-run")),
        )
        .unwrap();
        assert_eq!(local.program, PathBuf::from("/opt/chrome/chrome"));
        assert_eq!(local.display_mode, ChromeDisplayMode::LocalDisplay);

        let err = chrome_command_plan(
            Path::new("/opt/chrome/chrome"),
            &options,
            9333,
            false,
            None,
            None,
            None,
        )
        .unwrap_err();
        assert!(err.to_string().contains("HBR_HEADLESS=1"));
    }

    #[test]
    fn chrome_command_plan_keeps_headless_direct_even_when_xvfb_exists() {
        let options = start_options();
        let plan = chrome_command_plan(
            Path::new("/opt/chrome/chrome"),
            &options,
            9222,
            false,
            None,
            None,
            Some(PathBuf::from("/usr/bin/xvfb-run")),
        )
        .unwrap();
        let args: Vec<String> = plan
            .args
            .iter()
            .map(|arg| arg.to_string_lossy().into_owned())
            .collect();

        assert_eq!(plan.program, PathBuf::from("/opt/chrome/chrome"));
        assert_eq!(plan.display_mode, ChromeDisplayMode::Headless);
        assert!(args.contains(&"--headless=new".to_string()));
    }

    #[test]
    fn backend_accepts_explicit_path_and_autodetect_helpers_are_callable() {
        let backend = LocalChromeBackend::new(Some(PathBuf::from("/tmp/chrome-bin"))).unwrap();
        assert_eq!(backend.chrome_path(), Path::new("/tmp/chrome-bin"));

        let _ = find_chrome_path();
        let _ = find_playwright_chromium();
    }

    #[test]
    fn backend_reports_missing_chrome_when_all_candidates_are_absent() {
        let err = LocalChromeBackend::from_candidates(None, None, None).unwrap_err();
        assert!(err.to_string().contains("Chrome/Chromium not found"));
    }

    #[test]
    fn find_playwright_chromium_returns_none_without_a_home_directory() {
        assert_eq!(find_playwright_chromium_from_home(None), None);
    }

    #[test]
    fn find_playwright_chromium_returns_none_when_cache_base_is_not_a_directory() {
        let tmp = tempfile::tempdir().unwrap();
        let file_path = tmp.path().join("not-a-directory");
        fs::write(&file_path, b"stub").unwrap();

        assert_eq!(find_playwright_chromium_in(&file_path), None);
    }

    #[test]
    fn backend_uses_hbr_chrome_path_env_override_when_explicit_path_is_missing() {
        let _guard = env_test_lock().lock().unwrap();
        unsafe { std::env::remove_var("HBR_CHROME_PATH") };
        unsafe { std::env::set_var("HBR_CHROME_PATH", "/tmp/env-chrome") };

        let backend = LocalChromeBackend::new(None).unwrap();

        unsafe { std::env::remove_var("HBR_CHROME_PATH") };
        assert_eq!(backend.chrome_path(), Path::new("/tmp/env-chrome"));
    }

    #[test]
    fn backend_env_override_test_covers_restore_when_previous_value_exists() {
        let _guard = env_test_lock().lock().unwrap();
        unsafe { std::env::set_var("HBR_CHROME_PATH", "/tmp/original-chrome") };
        unsafe { std::env::set_var("HBR_CHROME_PATH", "/tmp/env-chrome") };

        let backend = LocalChromeBackend::new(None).unwrap();

        unsafe { std::env::set_var("HBR_CHROME_PATH", "/tmp/original-chrome") };
        assert_eq!(backend.chrome_path(), Path::new("/tmp/env-chrome"));
        assert_eq!(
            std::env::var_os("HBR_CHROME_PATH"),
            Some("/tmp/original-chrome".into())
        );
        unsafe { std::env::remove_var("HBR_CHROME_PATH") };
    }

    #[tokio::test]
    async fn local_chrome_backend_launch_uses_real_launch_path() {
        init_test_tracing();
        let _guard = scripted_backend_test_lock().lock().await;
        let tmp = tempfile::tempdir().unwrap();
        let chrome = write_mock_chrome_http_server_script(tmp.path(), "mock-chrome");
        let backend = LocalChromeBackend::new(Some(chrome)).unwrap();
        let options = start_options_in(tmp.path(), Duration::from_secs(2));

        let mut launched = backend.launch(options.clone()).await.unwrap();

        assert!(options.user_data_dir.exists());
        assert!(options.downloads_dir.exists());
        assert!(launched.port > 0);
        assert!(launched.http_base.starts_with("http://127.0.0.1:"));
        assert_eq!(
            launched.cdp_ws_url,
            "ws://127.0.0.1:9/devtools/browser/test".to_string()
        );

        let _ = launched.process.start_kill();
        close_with(&mut launched, Duration::from_millis(10), |_| {
            Box::pin(async move { Ok(()) })
        })
        .await
        .unwrap();
    }

    #[tokio::test]
    async fn open_blank_page_hits_mock_cdp_new_endpoint() {
        let cdp = MockCdpServer::spawn().await;

        open_blank_page(cdp.base_url.clone(), "https://example.com".to_string())
            .await
            .unwrap();

        assert_eq!(cdp.new_page_calls(), 1);
        cdp.stop().await;
    }

    #[test]
    fn finds_latest_playwright_chromium_binary_in_cache_tree() {
        let tmp = tempfile::tempdir().unwrap();
        let older = tmp.path().join("chromium-1000/chrome-linux/chrome");
        let newer = tmp
            .path()
            .join("chromium-2000/chrome-headless-shell-linux64/chrome-headless-shell");
        fs::create_dir_all(older.parent().unwrap()).unwrap();
        fs::create_dir_all(newer.parent().unwrap()).unwrap();
        fs::write(&older, b"").unwrap();
        fs::write(&newer, b"").unwrap();

        assert_eq!(find_playwright_chromium_in(tmp.path()), Some(newer));
    }

    #[tokio::test]
    async fn launch_with_retries_until_cdp_ready_and_returns_browser_info() {
        init_test_tracing();
        let _guard = scripted_backend_test_lock().lock().await;
        let tmp = tempfile::tempdir().unwrap();
        let chrome = write_executable_script(tmp.path(), "fake-chrome", "sleep 60");
        let attempts = Arc::new(AtomicUsize::new(0));
        let open_calls = Arc::new(AtomicUsize::new(0));
        let options = start_options_in(tmp.path(), Duration::from_millis(50));

        let mut launched = launch_with(
            &chrome,
            options.clone(),
            true,
            Duration::from_millis(5),
            {
                let attempts = attempts.clone();
                move |_| {
                    let attempts = attempts.clone();
                    Box::pin(async move {
                        if attempts.fetch_add(1, Ordering::SeqCst) == 0 {
                            bail!("not ready yet")
                        }
                        Ok(cdp::VersionInfo {
                            web_socket_debugger_url: "ws://127.0.0.1/devtools/browser/test"
                                .to_string(),
                            user_agent: Some(
                                "Mozilla/5.0 HeadlessChrome/125.0.0.0 Safari/537.36".to_string(),
                            ),
                        })
                    })
                }
            },
            {
                let open_calls = open_calls.clone();
                move |_, _| {
                    let open_calls = open_calls.clone();
                    Box::pin(async move {
                        open_calls.fetch_add(1, Ordering::SeqCst);
                        Ok(())
                    })
                }
            },
        )
        .await
        .unwrap();

        assert!(options.user_data_dir.exists());
        assert!(options.downloads_dir.exists());
        assert!(launched.port > 0);
        assert!(launched.http_base.starts_with("http://127.0.0.1:"));
        assert_eq!(
            launched.cdp_ws_url,
            "ws://127.0.0.1/devtools/browser/test".to_string()
        );
        assert_eq!(attempts.load(Ordering::SeqCst), 2);
        assert_eq!(open_calls.load(Ordering::SeqCst), 1);

        let _ = launched.process.start_kill();
        close_with(&mut launched, Duration::from_millis(10), |_| {
            Box::pin(async move { Ok(()) })
        })
        .await
        .unwrap();
    }

    #[tokio::test]
    async fn launch_with_reports_port_allocation_error() {
        let _guard = scripted_backend_test_lock().lock().await;
        let tmp = tempfile::tempdir().unwrap();
        let chrome = tmp.path().join("unused-chrome");
        let err = launch_with_port_allocator(
            &chrome,
            start_options_in(tmp.path(), Duration::from_millis(20)),
            false,
            Duration::from_millis(1),
            || bail!("port unavailable"),
            fetch_browser_version,
            open_blank_page,
        )
        .await
        .unwrap_err();

        assert!(err.to_string().contains("port unavailable"));
    }

    #[tokio::test]
    async fn launch_with_reports_poll_error() {
        let _guard = scripted_backend_test_lock().lock().await;
        let tmp = tempfile::tempdir().unwrap();
        let chrome = write_executable_script(tmp.path(), "exits-immediately", "exit 0");
        let err = launch_with_port_allocator_and_poll(
            &chrome,
            start_options_in(tmp.path(), Duration::from_millis(20)),
            false,
            Duration::from_millis(1),
            free_local_port,
            fetch_browser_version,
            open_blank_page,
            |_process| Err(std::io::Error::other("poll failed").into()),
        )
        .await
        .unwrap_err();

        assert!(err.to_string().contains("poll failed"));
    }

    #[tokio::test]
    async fn poll_process_exit_reports_try_wait_errors() {
        let _guard = scripted_backend_test_lock().lock().await;
        let tmp = tempfile::tempdir().unwrap();
        let chrome = write_executable_script(tmp.path(), "hangs-forever", "sleep 60");
        let mut process = Command::new("sh").arg(&chrome).spawn().unwrap();

        let err = poll_process_exit_with(&mut process, |_process| {
            Err(std::io::Error::other("poll failed"))
        })
        .unwrap_err();

        let _ = process.start_kill();
        let _ = process.wait().await;
        assert!(err.to_string().contains("poll Chrome process"));
    }

    #[tokio::test]
    async fn launch_with_reports_user_data_dir_creation_error() {
        let _guard = scripted_backend_test_lock().lock().await;
        let tmp = tempfile::tempdir().unwrap();
        let options = start_options_in(tmp.path(), Duration::from_millis(20));
        let fetch_version = |_| -> AsyncResult<cdp::VersionInfo> {
            Box::pin(async move {
                Ok(cdp::VersionInfo {
                    web_socket_debugger_url: "ws://127.0.0.1/devtools/browser/test".to_string(),
                    user_agent: None,
                })
            })
        };
        let open_new_page = |_, _| -> AsyncResult<()> { Box::pin(async move { Ok(()) }) };
        fs::write(&options.user_data_dir, b"occupied").unwrap();

        fetch_version(String::new()).await.unwrap();
        open_new_page(String::new(), String::new()).await.unwrap();

        let err = launch_with(
            tmp.path().join("never-run").as_path(),
            options,
            false,
            Duration::from_millis(1),
            fetch_version,
            open_new_page,
        )
        .await
        .unwrap_err();

        assert!(err.to_string().contains("create user data dir"));
    }

    #[tokio::test]
    async fn launch_with_reports_downloads_dir_creation_error() {
        let _guard = scripted_backend_test_lock().lock().await;
        let tmp = tempfile::tempdir().unwrap();
        let options = start_options_in(tmp.path(), Duration::from_millis(20));
        let fetch_version = |_| -> AsyncResult<cdp::VersionInfo> {
            Box::pin(async move {
                Ok(cdp::VersionInfo {
                    web_socket_debugger_url: "ws://127.0.0.1/devtools/browser/test".to_string(),
                    user_agent: None,
                })
            })
        };
        let open_new_page = |_, _| -> AsyncResult<()> { Box::pin(async move { Ok(()) }) };
        fs::create_dir_all(&options.user_data_dir).unwrap();
        fs::write(&options.downloads_dir, b"occupied").unwrap();

        fetch_version(String::new()).await.unwrap();
        open_new_page(String::new(), String::new()).await.unwrap();

        let err = launch_with(
            tmp.path().join("never-run").as_path(),
            options,
            false,
            Duration::from_millis(1),
            fetch_version,
            open_new_page,
        )
        .await
        .unwrap_err();

        assert!(err.to_string().contains("create downloads dir"));
    }

    #[tokio::test]
    async fn launch_with_reports_spawn_error() {
        let _guard = scripted_backend_test_lock().lock().await;
        let tmp = tempfile::tempdir().unwrap();
        let options = start_options_in(tmp.path(), Duration::from_millis(20));
        let fetch_version = |_| -> AsyncResult<cdp::VersionInfo> {
            Box::pin(async move {
                Ok(cdp::VersionInfo {
                    web_socket_debugger_url: "ws://127.0.0.1/devtools/browser/test".to_string(),
                    user_agent: None,
                })
            })
        };
        let open_new_page = |_, _| -> AsyncResult<()> { Box::pin(async move { Ok(()) }) };

        fetch_version(String::new()).await.unwrap();
        open_new_page(String::new(), String::new()).await.unwrap();

        let err = launch_with(
            tmp.path().join("missing-chrome").as_path(),
            options,
            false,
            Duration::from_millis(1),
            fetch_version,
            open_new_page,
        )
        .await
        .unwrap_err();

        assert!(err.to_string().contains("spawn Chrome"));
    }

    #[tokio::test]
    async fn launch_with_returns_browser_even_when_open_blank_page_fails() {
        let _guard = scripted_backend_test_lock().lock().await;
        let tmp = tempfile::tempdir().unwrap();
        let chrome = write_executable_script(tmp.path(), "fake-chrome", "sleep 60");

        let mut launched = launch_with(
            &chrome,
            start_options_in(tmp.path(), Duration::from_millis(20)),
            false,
            Duration::from_millis(1),
            |_| -> AsyncResult<cdp::VersionInfo> {
                Box::pin(async move {
                    Ok(cdp::VersionInfo {
                        web_socket_debugger_url: "ws://127.0.0.1/devtools/browser/test".to_string(),
                        user_agent: None,
                    })
                })
            },
            |_, _| -> AsyncResult<()> { Box::pin(async move { bail!("new page failed") }) },
        )
        .await
        .unwrap();

        assert_eq!(
            launched.cdp_ws_url,
            "ws://127.0.0.1/devtools/browser/test".to_string()
        );

        let _ = launched.process.start_kill();
        close_with(&mut launched, Duration::from_millis(10), |_| {
            Box::pin(async move { Ok(()) })
        })
        .await
        .unwrap();
    }

    #[tokio::test]
    async fn launch_reports_child_exit_before_cdp_ready() {
        let _guard = scripted_backend_test_lock().lock().await;
        let tmp = tempfile::tempdir().unwrap();
        let chrome = write_executable_script(tmp.path(), "exits-immediately", "exit 0");
        let open_new_page =
            |_: String, _: String| -> AsyncResult<()> { Box::pin(async move { Ok(()) }) };

        open_new_page(String::new(), String::new()).await.unwrap();

        let err = launch_with(
            &chrome,
            start_options_in(tmp.path(), Duration::from_millis(100)),
            false,
            Duration::from_millis(1),
            |_| Box::pin(async move { bail!("still waiting") }),
            open_new_page,
        )
        .await
        .unwrap_err();
        let message = err.to_string();
        assert!(
            message.contains("Chrome exited before CDP became ready"),
            "unexpected launch error: {message}"
        );
    }

    #[tokio::test]
    async fn launch_with_times_out_and_kills_hanging_process() {
        let _guard = scripted_backend_test_lock().lock().await;
        let tmp = tempfile::tempdir().unwrap();
        let chrome = write_executable_script(tmp.path(), "hangs-forever", "sleep 60");
        let open_new_page =
            |_: String, _: String| -> AsyncResult<()> { Box::pin(async move { Ok(()) }) };

        open_new_page(String::new(), String::new()).await.unwrap();

        let err = launch_with(
            &chrome,
            start_options_in(tmp.path(), Duration::from_millis(20)),
            false,
            Duration::from_millis(5),
            |_| Box::pin(async move { bail!("still waiting") }),
            open_new_page,
        )
        .await
        .unwrap_err();

        let message = err.to_string();
        assert!(
            message.contains("Chrome CDP did not become ready within"),
            "unexpected launch error: {message}"
        );
    }

    #[tokio::test]
    async fn close_returns_when_process_is_already_exited() {
        let _guard = scripted_backend_test_lock().lock().await;
        let tmp = tempfile::tempdir().unwrap();
        let chrome = write_executable_script(tmp.path(), "exits-immediately", "exit 0");
        let backend = LocalChromeBackend::new(Some(chrome.clone())).unwrap();
        let process = Command::new("sh").arg(&chrome).spawn().unwrap();
        let mut launched = LaunchedBrowser {
            process,
            port: 1,
            http_base: "http://127.0.0.1:1".to_string(),
            cdp_ws_url: "ws://127.0.0.1:9/devtools/browser/missing".to_string(),
            persona_guard: None,
        };

        backend.close(&mut launched).await.unwrap();
    }

    #[tokio::test]
    async fn close_with_kills_stuck_process_after_timeout() {
        let _guard = scripted_backend_test_lock().lock().await;
        let tmp = tempfile::tempdir().unwrap();
        let chrome = write_executable_script(tmp.path(), "hangs-forever", "sleep 60");
        let process = Command::new("sh").arg(&chrome).spawn().unwrap();
        let mut launched = LaunchedBrowser {
            process,
            port: 1,
            http_base: "http://127.0.0.1:1".to_string(),
            cdp_ws_url: "ws://127.0.0.1:9/devtools/browser/missing".to_string(),
            persona_guard: None,
        };

        close_with(&mut launched, Duration::from_millis(10), |_| {
            Box::pin(async move { Ok(()) })
        })
        .await
        .unwrap();
        assert!(launched.process.try_wait().unwrap().is_some());
    }
}
