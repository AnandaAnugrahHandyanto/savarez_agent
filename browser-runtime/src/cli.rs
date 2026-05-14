use std::{
    fs,
    future::{Future, pending},
    io::{self, Write},
    net::SocketAddr,
    path::{Path, PathBuf},
    pin::Pin,
    sync::Arc,
    time::Duration,
};

use anyhow::{Context, Result};
use axum::serve;
use base64::{Engine as _, engine::general_purpose::STANDARD as BASE64};
use clap::Parser;
use http::Request;
use tokio::net::TcpListener;
use tower_http::trace::TraceLayer;
use tracing::{info, warn};

#[cfg(test)]
use crate::models::CaptchaPolicy;

use crate::{
    api,
    backend::LocalChromeBackend,
    client::BrowserRuntimeClient,
    config::{
        ArtifactsArgs, ArtifactsCommand, CaptchaArgs, CaptchaCommand, Cli, ClientArgs, Command,
        CredentialPrivacyGuardCommand, CredentialsArgs, CredentialsCommand, OperatorClientArgs,
        ProfilesArgs, ProfilesCommand, RuntimeConfig, SessionsArgs, SessionsCommand,
    },
    models::{
        ArtifactsResponse, CaptchaReportRequest, CaptchaResolveRequest, CleanupArtifactsRequest,
        CreateProfileRequest, CreateSessionRequest, CredentialFillStartRequest,
        PauseForHumanRequest,
    },
    store::AppStore,
};

pub async fn run() -> Result<()> {
    run_cli(Cli::parse()).await
}

async fn run_cli(cli: Cli) -> Result<()> {
    match cli.command {
        Command::Server(args) => run_server(RuntimeConfig::from_server_args(args)).await,
        Command::Sessions(args) => run_sessions(args).await,
        Command::Credentials(args) => run_credentials(args).await,
        Command::Captcha(args) => run_captcha(args).await,
        Command::Profiles(args) => run_profiles(args).await,
        Command::Artifacts(args) => run_artifacts(args).await,
    }
}

pub async fn run_server(config: RuntimeConfig) -> Result<()> {
    run_server_with_shutdown(config, shutdown_signal()).await
}

async fn run_server_with_shutdown(config: RuntimeConfig, shutdown: ShutdownFuture) -> Result<()> {
    let backend = LocalChromeBackend::new(config.chrome_path.clone())?;
    info!(chrome=%backend.chrome_path().display(), bind=%config.bind, data_dir=%config.data_dir.display(), "starting Hermes Browser Runtime");
    let store = Arc::new(AppStore::new(config.clone(), Arc::new(backend)).await?);
    serve_store_with_shutdown(config.bind, store, shutdown).await
}

fn runtime_app(store: Arc<AppStore>) -> axum::Router {
    api::router(store).layer(
        TraceLayer::new_for_http().make_span_with(|request: &Request<_>| {
            tracing::debug_span!(
                "request",
                method = %request.method(),
                uri = %request.uri().path(),
                version = ?request.version(),
            )
        }),
    )
}

type ShutdownFuture = Pin<Box<dyn Future<Output = ()> + Send + 'static>>;

fn shutdown_signal() -> ShutdownFuture {
    Box::pin(async {
        #[cfg(unix)]
        {
            let ctrl_c = async {
                if let Err(err) = tokio::signal::ctrl_c().await {
                    warn!(error=%err, "failed to install Ctrl-C handler");
                    pending::<()>().await;
                }
            };
            let sigterm = async {
                match tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate()) {
                    Ok(mut signal) => {
                        let _ = signal.recv().await;
                    }
                    Err(err) => {
                        warn!(error=%err, "failed to install SIGTERM handler");
                        pending::<()>().await;
                    }
                }
            };
            shutdown_signal_with(ctrl_c, sigterm).await;
            info!("shutdown signal received");
        }

        #[cfg(not(unix))]
        {
            if let Err(err) = tokio::signal::ctrl_c().await {
                warn!(error=%err, "failed to install Ctrl-C handler");
                pending::<()>().await;
            }
            info!("shutdown signal received");
        }
    })
}

async fn shutdown_signal_with<C, S>(ctrl_c: C, sigterm: S)
where
    C: Future<Output = ()>,
    S: Future<Output = ()>,
{
    tokio::select! {
        _ = ctrl_c => {}
        _ = sigterm => {}
    }
}

#[inline(never)]
async fn serve_store_with_shutdown(
    bind: SocketAddr,
    store: Arc<AppStore>,
    shutdown: ShutdownFuture,
) -> Result<()> {
    let app = runtime_app(store.clone());
    let listener = TcpListener::bind(bind)
        .await
        .with_context(|| format!("bind {}", bind))?;
    let shutdown_error = Arc::new(std::sync::Mutex::new(None::<String>));
    let shutdown_error_slot = shutdown_error.clone();
    serve_app(
        listener,
        app,
        Box::pin(async move {
            shutdown.await;
            if let Err(err) = store.shutdown_all().await {
                *shutdown_error_slot.lock().unwrap() = Some(err.to_string());
            }
        }),
    )
    .await?;
    if let Some(err) = shutdown_error.lock().unwrap().take() {
        return Err(anyhow::anyhow!(err));
    }
    Ok(())
}

#[inline(never)]
async fn serve_app(
    listener: TcpListener,
    app: axum::Router,
    shutdown: ShutdownFuture,
) -> Result<()> {
    let result = serve(listener, app).with_graceful_shutdown(shutdown).await;
    finalize_serve_result(result)
}

#[inline(never)]
fn finalize_serve_result(result: io::Result<()>) -> Result<()> {
    result.context("serve HTTP")?;
    Ok(())
}

async fn run_sessions(args: SessionsArgs) -> Result<()> {
    match args.command {
        SessionsCommand::Create(args) => {
            let headless = if args.headless {
                Some(true)
            } else if args.headful {
                Some(false)
            } else {
                None
            };
            let value = client_from_args(&args.client)?
                .create_session(&CreateSessionRequest {
                    profile_id: args.profile_id,
                    headless,
                    viewport: None,
                    persist_profile: Some(args.persist_profile),
                    captcha_policy: args.captcha_policy,
                    launch_timeout_secs: args.launch_timeout_secs,
                    persona: None,
                    webrtc_ip_policy: args.webrtc_ip_policy,
                    gpu_policy: args.gpu_policy,
                })
                .await?;
            print_json(value)
        }
        SessionsCommand::List(args) => print_json(client_from_args(&args)?.list_sessions().await?),
        SessionsCommand::Get(args) => print_json(
            client_from_args(&args.client)?
                .get_session(args.session_id)
                .await?,
        ),
        SessionsCommand::Delete(args) => print_json(
            client_from_args(&args.client)?
                .delete_session(args.session_id)
                .await?,
        ),
        SessionsCommand::Pause(args) => {
            let value = client_from_args(&args.client)?
                .pause_session(
                    args.session_id,
                    &PauseForHumanRequest {
                        reason: args.reason,
                    },
                )
                .await?;
            print_json(value)
        }
        SessionsCommand::Release(args) => print_json(
            client_from_args(&args.client)?
                .release_session(args.session_id)
                .await?,
        ),
        SessionsCommand::Wait(args) => {
            let value = client_from_args(&args.client)?
                .wait_session(args.session_id, Duration::from_secs(args.timeout_secs))
                .await?;
            print_json(serde_json::to_value(value)?)
        }
        SessionsCommand::Screenshot(args) => {
            let png = client_from_args(&args.client)?
                .screenshot(args.session_id)
                .await?;
            write_screenshot(&png, args.output)
        }
        SessionsCommand::Credentials(args) => run_credentials(args).await,
        SessionsCommand::Captcha(args) => run_captcha(args).await,
    }
}

async fn run_captcha(args: CaptchaArgs) -> Result<()> {
    match args.command {
        CaptchaCommand::Report(args) => {
            let value = client_from_args(&args.client)?
                .captcha_report(
                    args.session_id,
                    &CaptchaReportRequest {
                        state: args.state,
                        challenge_type: args.challenge_type,
                        reason: args.reason,
                    },
                )
                .await?;
            print_json(value)
        }
        CaptchaCommand::Resolve(args) => {
            let value = client_from_args(&args.client)?
                .captcha_resolve(
                    args.session_id,
                    &CaptchaResolveRequest {
                        outcome: args.outcome,
                        note: args.note,
                    },
                )
                .await?;
            print_json(value)
        }
    }
}

async fn run_credentials(args: CredentialsArgs) -> Result<()> {
    match args.command {
        CredentialsCommand::Fill(args) => {
            let record = client_from_args(&args.client)?
                .credential_fill(
                    args.session_id,
                    &CredentialFillStartRequest {
                        alias: args.alias,
                        username_selector: args.username_selector,
                        password_selector: args.password_selector,
                        purpose: args.purpose,
                        expected_origin: args.expected_origin,
                    },
                )
                .await?;
            print_json(serde_json::to_value(record)?)
        }
        CredentialsCommand::Status(args) => {
            let record = client_from_args(&args.client)?
                .credential_fill_status(args.session_id, args.request_id)
                .await?;
            print_json(serde_json::to_value(record)?)
        }
        CredentialsCommand::Approve(args) => {
            let record = operator_client_from_args(&args.client)?
                .approve_credential_fill(args.session_id, args.request_id, args.note)
                .await?;
            print_json(serde_json::to_value(record)?)
        }
        CredentialsCommand::Deny(args) => {
            let record = operator_client_from_args(&args.client)?
                .deny_credential_fill(args.session_id, args.request_id, args.note)
                .await?;
            print_json(serde_json::to_value(record)?)
        }
        CredentialsCommand::PrivacyGuard(args) => match args.command {
            CredentialPrivacyGuardCommand::Clear(args) => {
                let response = operator_client_from_args(&args.client)?
                    .clear_credential_privacy_guard(args.session_id)
                    .await?;
                print_json(serde_json::to_value(response)?)
            }
        },
        CredentialsCommand::ClearPrivacyGuard(args) | CredentialsCommand::ClearGuard(args) => {
            let response = operator_client_from_args(&args.client)?
                .clear_credential_privacy_guard(args.session_id)
                .await?;
            print_json(serde_json::to_value(response)?)
        }
    }
}

async fn run_profiles(args: ProfilesArgs) -> Result<()> {
    match args.command {
        ProfilesCommand::Create(args) => {
            let value = client_from_args(&args.client)?
                .create_profile(&CreateProfileRequest { id: args.id })
                .await?;
            print_json(value)
        }
        ProfilesCommand::List(args) => print_json(client_from_args(&args)?.list_profiles().await?),
        ProfilesCommand::Delete(args) => {
            client_from_args(&args.client)?
                .delete_profile(&args.profile_id)
                .await?;
            Ok(())
        }
    }
}

async fn run_artifacts(args: ArtifactsArgs) -> Result<()> {
    match args.command {
        ArtifactsCommand::List(args) => print_json(
            client_from_args(&args.client)?
                .list_artifacts(args.session_id)
                .await?,
        ),
        ArtifactsCommand::Downloads(args) => print_json(
            client_from_args(&args.client)?
                .list_downloads(args.session_id)
                .await?,
        ),
        ArtifactsCommand::Download(args) => {
            let bytes = client_from_args(&args.client)?
                .download(args.session_id, &args.name)
                .await?;
            write_bytes_output(&bytes, args.output)
        }
        ArtifactsCommand::Cleanup(args) => print_json(
            client_from_args(&args.client)?
                .cleanup_artifacts(&CleanupArtifactsRequest {
                    dry_run: args.dry_run,
                    older_than_secs: args.older_than_secs,
                })
                .await?,
        ),
        ArtifactsCommand::Replay(args) => {
            let artifacts = serde_json::from_value::<ArtifactsResponse>(
                client_from_args(&args.client)?
                    .list_artifacts(args.session_id)
                    .await?,
            )
            .context("parse artifacts replay payload")?;
            let html = render_artifact_replay(&artifacts)?;
            write_text_output(&html, args.output)
        }
    }
}

fn client_from_args(args: &ClientArgs) -> Result<BrowserRuntimeClient> {
    BrowserRuntimeClient::new(&args.server, args.bearer_token.clone())
}

fn operator_client_from_args(args: &OperatorClientArgs) -> Result<BrowserRuntimeClient> {
    BrowserRuntimeClient::new(&args.server, args.operator_token.clone())
}

fn print_json(value: serde_json::Value) -> Result<()> {
    println!("{}", serde_json::to_string_pretty(&value)?);
    Ok(())
}

fn write_bytes_output(bytes: &[u8], output: Option<PathBuf>) -> Result<()> {
    if let Some(output) = output {
        fs::write(&output, bytes).with_context(|| format!("write {}", output.display()))?;
        println!("{}", output.display());
        return Ok(());
    }

    let mut stdout = io::stdout().lock();
    stdout.write_all(bytes)?;
    stdout.flush()?;
    Ok(())
}

fn write_text_output(text: &str, output: Option<PathBuf>) -> Result<()> {
    if let Some(output) = output {
        fs::write(&output, text).with_context(|| format!("write {}", output.display()))?;
        println!("{}", output.display());
        return Ok(());
    }

    let mut stdout = io::stdout().lock();
    stdout.write_all(text.as_bytes())?;
    stdout.flush()?;
    Ok(())
}

fn write_screenshot(png: &[u8], output: Option<PathBuf>) -> Result<()> {
    write_bytes_output(png, output)
}

fn render_artifact_replay(artifacts: &ArtifactsResponse) -> Result<String> {
    let mut html = String::from(
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>Hermes browser runtime replay</title><style>body{font-family:system-ui,-apple-system,sans-serif;margin:2rem;background:#0b1020;color:#f3f4f6;}h1,h2,h3{margin:0 0 1rem;}p,li{line-height:1.5;}code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;}pre{white-space:pre-wrap;background:#111827;padding:1rem;border-radius:.75rem;overflow:auto;}figure{margin:1.5rem 0;padding:1rem;background:#111827;border-radius:.75rem;}figcaption{margin-bottom:.75rem;font-weight:600;}img{max-width:100%;height:auto;border-radius:.5rem;border:1px solid #374151;}section{margin-top:2rem;}</style></head><body>",
    );
    html.push_str(&format!(
        "<h1>Artifact replay for session <code>{}</code></h1>",
        html_escape(&artifacts.session_id.to_string())
    ));
    html.push_str(&format!(
        "<p>Downloads directory: <code>{}</code></p>",
        html_escape(&artifacts.downloads_dir)
    ));

    html.push_str("<section><h2>Screenshots</h2>");
    let mut has_screenshots = false;
    for artifact in &artifacts.artifacts {
        if artifact.kind != "screenshot" {
            continue;
        }
        has_screenshots = true;
        let bytes = fs::read(&artifact.path).with_context(|| format!("read {}", artifact.path))?;
        let name = Path::new(&artifact.path)
            .file_name()
            .and_then(|file| file.to_str())
            .unwrap_or("screenshot");
        html.push_str(&format!(
            "<figure><figcaption>{}</figcaption><img alt=\"{}\" src=\"data:image/png;base64,{}\"></figure>",
            html_escape(name),
            html_escape(name),
            BASE64.encode(bytes)
        ));
    }
    if !has_screenshots {
        html.push_str("<p>No screenshots captured for this session.</p>");
    }
    html.push_str("</section>");

    html.push_str("<section><h2>Event logs</h2>");
    let mut has_event_logs = false;
    for artifact in &artifacts.artifacts {
        if artifact.kind != "event_log" {
            continue;
        }
        has_event_logs = true;
        let body = fs::read_to_string(&artifact.path)
            .with_context(|| format!("read {}", artifact.path))?;
        let name = Path::new(&artifact.path)
            .file_name()
            .and_then(|file| file.to_str())
            .unwrap_or("events.jsonl");
        html.push_str(&format!(
            "<section><h3>{}</h3><pre>{}</pre></section>",
            html_escape(name),
            html_escape(&body)
        ));
    }
    if !has_event_logs {
        html.push_str("<p>No event logs captured for this session.</p>");
    }
    html.push_str("</section></body></html>");
    Ok(html)
}

fn html_escape(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&#39;")
}

#[allow(dead_code)]
fn _assert_local_default(addr: SocketAddr) -> bool {
    addr.ip().is_loopback()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        config::{
            ClientCreateSessionArgs, CreateProfileArgs, PauseSessionArgs, ProfileIdArgs,
            ScreenshotArgs, ServerArgs, SessionIdArgs, WaitSessionArgs,
        },
        credentials::{CredentialBrokerMode, CredentialFillStatus},
        models::{
            ArtifactInfo, ArtifactsResponse, BrowserPersona, CredentialFillStatusRecord,
            CredentialPrivacyGuardResponse, DEFAULT_DEVICE_MEMORY_GB, DEFAULT_HARDWARE_CONCURRENCY,
            DEFAULT_MAX_TOUCH_POINTS, SessionStatus,
        },
        store::AppStore,
        test_support::{MockBackend, MockCdpServer, persistent_req, spawn_api_server, test_config},
    };
    use axum::{
        Json, Router,
        body::Body,
        http::{Request, StatusCode},
        routing::{delete, get, post},
    };
    use chrono::Utc;
    use clap::Parser;
    use reqwest::{Method, header};
    use serde_json::json;
    use std::{
        ffi::OsString,
        fs,
        net::TcpListener as StdTcpListener,
        sync::{Mutex, OnceLock},
        time::Duration,
    };
    use tokio::sync::oneshot;
    use tokio::time::{sleep, timeout};
    use tower::ServiceExt;
    use tracing_subscriber::fmt::writer::MakeWriter;
    use uuid::Uuid;

    #[derive(Clone, Default)]
    struct LogCapture(Arc<Mutex<Vec<u8>>>);

    struct LogWriter(Arc<Mutex<Vec<u8>>>);

    impl<'a> MakeWriter<'a> for LogCapture {
        type Writer = LogWriter;

        fn make_writer(&'a self) -> Self::Writer {
            LogWriter(self.0.clone())
        }
    }

    impl io::Write for LogWriter {
        fn write(&mut self, buf: &[u8]) -> io::Result<usize> {
            self.0.lock().unwrap().extend_from_slice(buf);
            Ok(buf.len())
        }

        fn flush(&mut self) -> io::Result<()> {
            Ok(())
        }
    }

    impl LogCapture {
        fn output(&self) -> String {
            String::from_utf8(self.0.lock().unwrap().clone()).unwrap()
        }
    }

    fn client_args(server: &str) -> ClientArgs {
        ClientArgs {
            server: server.to_string(),
            bearer_token: None,
        }
    }

    fn env_lock() -> &'static Mutex<()> {
        static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
        LOCK.get_or_init(|| Mutex::new(()))
    }

    fn set_env_var(key: &str, value: impl Into<OsString>) {
        unsafe { std::env::set_var(key, value.into()) };
    }

    fn remove_env_var(key: &str) {
        unsafe { std::env::remove_var(key) };
    }

    struct EnvRestore(Vec<(String, Option<OsString>)>);

    impl Drop for EnvRestore {
        fn drop(&mut self) {
            for (key, value) in self.0.drain(..).rev() {
                if let Some(value) = value {
                    set_env_var(&key, value);
                } else {
                    remove_env_var(&key);
                }
            }
        }
    }

    type EnvUpdate<'a> = (&'a str, Option<&'a str>);

    fn capture_env_restore(updates: &[EnvUpdate<'_>]) -> EnvRestore {
        EnvRestore(
            updates
                .iter()
                .map(|(key, _)| ((*key).to_string(), std::env::var_os(key)))
                .collect(),
        )
    }

    fn apply_env_updates(updates: &[EnvUpdate<'_>]) {
        for (key, value) in updates {
            if let Some(value) = value {
                set_env_var(key, value);
            } else {
                remove_env_var(key);
            }
        }
    }

    fn with_env_vars_locked<const N: usize, T>(
        updates: [EnvUpdate<'_>; N],
        f: impl FnOnce() -> T,
    ) -> T {
        let restore = capture_env_restore(&updates);
        apply_env_updates(&updates);
        let result = f();
        drop(restore);
        result
    }

    fn with_env_vars<const N: usize, T>(
        updates: [(&str, Option<&str>); N],
        f: impl FnOnce() -> T,
    ) -> T {
        let _guard = env_lock().lock().unwrap();
        with_env_vars_locked(updates, f)
    }

    fn with_clean_hbr_env<T>(f: impl FnOnce() -> T) -> T {
        with_env_vars(
            [
                ("HBR_BIND", None),
                ("HBR_DATA_DIR", None),
                ("HBR_CHROME_PATH", None),
                ("HBR_BEARER_TOKEN", None),
                ("HBR_HEADFUL", None),
                ("HBR_HEADLESS", None),
                ("HBR_XVFB_RUN_PATH", None),
                ("HBR_ARTIFACT_RETENTION_SECS", None),
                ("HBR_TAKEOVER_TTL_SECS", None),
                ("HBR_SERVER", None),
            ],
            f,
        )
    }

    #[test]
    fn env_helpers_restore_existing_values() {
        let _guard = env_lock().lock().unwrap();
        let restore = EnvRestore(vec![(
            "HBR_SERVER".to_string(),
            std::env::var_os("HBR_SERVER"),
        )]);
        set_env_var("HBR_SERVER", "http://127.0.0.1:7000");

        with_env_vars_locked([("HBR_SERVER", Some("http://127.0.0.1:7001"))], || {
            assert_eq!(
                std::env::var("HBR_SERVER").as_deref(),
                Ok("http://127.0.0.1:7001")
            );
        });

        assert_eq!(
            std::env::var("HBR_SERVER").as_deref(),
            Ok("http://127.0.0.1:7000")
        );
        drop(restore);
    }

    #[test]
    fn server_command_defaults_keep_private_runtime_config() {
        with_clean_hbr_env(|| {
            let cli = Cli::try_parse_from(["hermes-browser-runtime", "server"])
                .expect("server command should parse");

            let mut matched = None;
            if let Command::Server(args) = cli.command {
                matched = Some(args);
            }
            let args = matched.expect("expected server subcommand");
            assert_eq!(args.bind, "127.0.0.1:7788".parse().unwrap());
            assert!(args.data_dir.is_none());
            assert!(args.chrome_path.is_none());
            assert!(args.bearer_token.is_none());
            assert!(!args.headful);
            assert_eq!(args.takeover_ttl_secs, 900);

            let config = RuntimeConfig::from_server_args_with_environment(args, None, None, None);
            assert_eq!(config.bind, "127.0.0.1:7788".parse().unwrap());
            assert_eq!(config.localhost_base_url(), "http://127.0.0.1:7788");
            assert!(config.default_headless);
            assert_eq!(config.takeover_ttl, Duration::from_secs(900));
            assert!(config.chrome_path.is_none());
            assert!(config.bearer_token.is_none());
        });
    }

    #[test]
    fn server_flags_override_env_and_map_to_runtime_config() {
        with_env_vars(
            [
                ("HBR_BIND", Some("127.0.0.1:8899")),
                ("HBR_DATA_DIR", Some("/tmp/env-data")),
                ("HBR_CHROME_PATH", Some("/tmp/env-chrome")),
                ("HBR_BEARER_TOKEN", Some("env-server-token")),
                ("HBR_HEADFUL", Some("false")),
                ("HBR_TAKEOVER_TTL_SECS", Some("42")),
            ],
            || {
                let cli = Cli::try_parse_from([
                    "hermes-browser-runtime",
                    "server",
                    "--bind",
                    "0.0.0.0:9900",
                    "--data-dir",
                    "/tmp/flag-data",
                    "--chrome-path",
                    "/tmp/flag-chrome",
                    "--bearer-token",
                    "flag-server-token",
                    "--headful",
                    "--takeover-ttl-secs",
                    "7",
                ])
                .expect("server command should parse explicit flags");

                let mut matched = None;
                if let Command::Server(args) = cli.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected server subcommand");
                assert_eq!(args.bind, "0.0.0.0:9900".parse().unwrap());
                assert_eq!(
                    args.data_dir,
                    Some(std::path::PathBuf::from("/tmp/flag-data"))
                );
                assert_eq!(
                    args.chrome_path,
                    Some(std::path::PathBuf::from("/tmp/flag-chrome"))
                );
                assert_eq!(args.bearer_token.as_deref(), Some("flag-server-token"));
                assert!(args.headful);
                assert_eq!(args.takeover_ttl_secs, 7);

                let config = RuntimeConfig::from_server_args(args);
                assert_eq!(config.localhost_base_url(), "http://127.0.0.1:9900");
                assert_eq!(config.data_dir, std::path::PathBuf::from("/tmp/flag-data"));
                assert_eq!(
                    config.chrome_path,
                    Some(std::path::PathBuf::from("/tmp/flag-chrome"))
                );
                assert_eq!(config.bearer_token.as_deref(), Some("flag-server-token"));
                assert!(!config.default_headless);
                assert_eq!(config.takeover_ttl, Duration::from_secs(7));
            },
        );
    }

    #[test]
    fn sessions_create_defaults_and_overrides_parse_expected_args() {
        with_env_vars(
            [
                ("HBR_SERVER", Some("http://127.0.0.1:8899")),
                ("HBR_BEARER_TOKEN", Some("env-client-token")),
            ],
            || {
                let cli = Cli::try_parse_from(["hermes-browser-runtime", "sessions", "create"])
                    .expect("sessions create should parse defaults");

                let mut matched = None;
                if let Command::Sessions(args) = cli.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected sessions command");
                let mut matched = None;
                if let SessionsCommand::Create(args) = args.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected create subcommand");
                assert_eq!(args.client.server, "http://127.0.0.1:8899");
                assert_eq!(
                    args.client.bearer_token.as_deref(),
                    Some("env-client-token")
                );
                assert!(args.profile_id.is_none());
                assert!(args.persist_profile);
                assert!(!args.headless);
                assert!(!args.headful);

                let cli = Cli::try_parse_from([
                    "hermes-browser-runtime",
                    "sessions",
                    "create",
                    "--profile-id",
                    "yura-main",
                    "--server",
                    "http://127.0.0.1:9900",
                    "--bearer-token",
                    "flag-client-token",
                ])
                .expect("sessions create should parse explicit flags");

                let mut matched = None;
                if let Command::Sessions(args) = cli.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected sessions command");
                let mut matched = None;
                if let SessionsCommand::Create(args) = args.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected create subcommand");
                assert_eq!(args.client.server, "http://127.0.0.1:9900");
                assert_eq!(
                    args.client.bearer_token.as_deref(),
                    Some("flag-client-token")
                );
                assert_eq!(args.profile_id.as_deref(), Some("yura-main"));
                assert!(args.persist_profile);
                assert!(!args.headless);
                assert!(!args.headful);

                let cli = Cli::try_parse_from([
                    "hermes-browser-runtime",
                    "sessions",
                    "create",
                    "--headless",
                ])
                .expect("sessions create should accept explicit headless flag");
                let Command::Sessions(args) = cli.command else {
                    panic!("expected sessions command");
                };
                let SessionsCommand::Create(args) = args.command else {
                    panic!("expected create subcommand");
                };
                assert!(args.headless);
                assert!(!args.headful);

                assert!(
                    Cli::try_parse_from([
                        "hermes-browser-runtime",
                        "sessions",
                        "create",
                        "--headless",
                        "false",
                    ])
                    .is_err()
                );
                assert!(
                    Cli::try_parse_from([
                        "hermes-browser-runtime",
                        "sessions",
                        "create",
                        "--persist-profile",
                        "false",
                    ])
                    .is_err()
                );
            },
        );
    }

    #[test]
    fn nested_client_commands_cover_session_profile_and_artifact_shapes() {
        with_env_vars(
            [
                ("HBR_SERVER", Some("http://127.0.0.1:8899")),
                ("HBR_BEARER_TOKEN", Some("env-client-token")),
            ],
            || {
                let session_id = Uuid::new_v4();

                let cli = Cli::try_parse_from(["hermes-browser-runtime", "sessions", "list"])
                    .expect("sessions list should parse");
                let mut matched = None;
                if let Command::Sessions(args) = cli.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected sessions command");
                let mut matched = None;
                if let SessionsCommand::List(args) = args.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected list subcommand");
                assert_eq!(args.server, "http://127.0.0.1:8899");
                assert_eq!(args.bearer_token.as_deref(), Some("env-client-token"));

                let cli = Cli::try_parse_from([
                    "hermes-browser-runtime",
                    "sessions",
                    "get",
                    &session_id.to_string(),
                ])
                .expect("sessions get should parse");
                let mut matched = None;
                if let Command::Sessions(args) = cli.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected sessions command");
                let mut matched = None;
                if let SessionsCommand::Get(args) = args.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected get subcommand");
                assert_eq!(args.session_id, session_id);
                assert_eq!(args.client.server, "http://127.0.0.1:8899");

                let cli = Cli::try_parse_from([
                    "hermes-browser-runtime",
                    "sessions",
                    "delete",
                    &session_id.to_string(),
                    "--server",
                    "http://127.0.0.1:9901",
                ])
                .expect("sessions delete should parse");
                let mut matched = None;
                if let Command::Sessions(args) = cli.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected sessions command");
                let mut matched = None;
                if let SessionsCommand::Delete(args) = args.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected delete subcommand");
                assert_eq!(args.session_id, session_id);
                assert_eq!(args.client.server, "http://127.0.0.1:9901");

                let cli = Cli::try_parse_from([
                    "hermes-browser-runtime",
                    "sessions",
                    "pause",
                    &session_id.to_string(),
                    "--reason",
                    "manual oauth approval",
                ])
                .expect("sessions pause should parse");
                let mut matched = None;
                if let Command::Sessions(args) = cli.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected sessions command");
                let mut matched = None;
                if let SessionsCommand::Pause(args) = args.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected pause subcommand");
                assert_eq!(args.session_id, session_id);
                assert_eq!(args.reason.as_deref(), Some("manual oauth approval"));
                assert_eq!(args.client.server, "http://127.0.0.1:8899");

                let cli = Cli::try_parse_from([
                    "hermes-browser-runtime",
                    "sessions",
                    "release",
                    &session_id.to_string(),
                    "--bearer-token",
                    "flag-release-token",
                ])
                .expect("sessions release should parse");
                let mut matched = None;
                if let Command::Sessions(args) = cli.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected sessions command");
                let mut matched = None;
                if let SessionsCommand::Release(args) = args.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected release subcommand");
                assert_eq!(args.session_id, session_id);
                assert_eq!(
                    args.client.bearer_token.as_deref(),
                    Some("flag-release-token")
                );

                let cli = Cli::try_parse_from([
                    "hermes-browser-runtime",
                    "sessions",
                    "wait",
                    &session_id.to_string(),
                    "--timeout-secs",
                    "42",
                ])
                .expect("sessions wait should parse");
                let mut matched = None;
                if let Command::Sessions(args) = cli.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected sessions command");
                let mut matched = None;
                if let SessionsCommand::Wait(args) = args.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected wait subcommand");
                assert_eq!(args.session_id, session_id);
                assert_eq!(args.timeout_secs, 42);
                assert_eq!(args.client.server, "http://127.0.0.1:8899");

                let cli = Cli::try_parse_from([
                    "hermes-browser-runtime",
                    "sessions",
                    "screenshot",
                    &session_id.to_string(),
                    "--output",
                    "/tmp/shot.png",
                ])
                .expect("sessions screenshot should parse");
                let mut matched = None;
                if let Command::Sessions(args) = cli.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected sessions command");
                let mut matched = None;
                if let SessionsCommand::Screenshot(args) = args.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected screenshot subcommand");
                assert_eq!(args.session_id, session_id);
                assert_eq!(args.output, Some(std::path::PathBuf::from("/tmp/shot.png")));

                let cli = Cli::try_parse_from([
                    "hermes-browser-runtime",
                    "profiles",
                    "create",
                    "--id",
                    "yura-main",
                ])
                .expect("profiles create should parse");
                let mut matched = None;
                if let Command::Profiles(args) = cli.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected profiles command");
                let mut matched = None;
                if let ProfilesCommand::Create(args) = args.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected profile create subcommand");
                assert_eq!(args.id.as_deref(), Some("yura-main"));
                assert_eq!(args.client.server, "http://127.0.0.1:8899");

                let cli = Cli::try_parse_from([
                    "hermes-browser-runtime",
                    "profiles",
                    "list",
                    "--server",
                    "http://127.0.0.1:9902",
                ])
                .expect("profiles list should parse");
                let mut matched = None;
                if let Command::Profiles(args) = cli.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected profiles command");
                let mut matched = None;
                if let ProfilesCommand::List(args) = args.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected profile list subcommand");
                assert_eq!(args.server, "http://127.0.0.1:9902");
                assert_eq!(args.bearer_token.as_deref(), Some("env-client-token"));

                let cli = Cli::try_parse_from([
                    "hermes-browser-runtime",
                    "profiles",
                    "delete",
                    "yura-main",
                    "--bearer-token",
                    "flag-profile-token",
                ])
                .expect("profiles delete should parse");
                let mut matched = None;
                if let Command::Profiles(args) = cli.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected profiles command");
                let mut matched = None;
                if let ProfilesCommand::Delete(args) = args.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected profile delete subcommand");
                assert_eq!(args.profile_id, "yura-main");
                assert_eq!(
                    args.client.bearer_token.as_deref(),
                    Some("flag-profile-token")
                );

                let cli = Cli::try_parse_from([
                    "hermes-browser-runtime",
                    "artifacts",
                    "list",
                    &session_id.to_string(),
                    "--server",
                    "http://127.0.0.1:9903",
                    "--bearer-token",
                    "flag-artifact-token",
                ])
                .expect("artifacts list should parse");
                let mut matched = None;
                if let Command::Artifacts(args) = cli.command {
                    matched = Some(args);
                }
                let args = matched.expect("expected artifacts command");
                let ArtifactsCommand::List(args) = args.command else {
                    panic!("expected artifacts list subcommand");
                };
                assert_eq!(args.session_id, session_id);
                assert_eq!(args.client.server, "http://127.0.0.1:9903");
                assert_eq!(
                    args.client.bearer_token.as_deref(),
                    Some("flag-artifact-token")
                );
            },
        );
    }

    async fn wait_for_http_ready(url: &str) -> bool {
        let client = reqwest::Client::builder()
            .timeout(Duration::from_millis(25))
            .build()
            .unwrap();

        for _ in 0..50 {
            if let Ok(response) = client.get(url).send().await
                && response.status().is_success()
            {
                return true;
            }
            sleep(Duration::from_millis(20)).await;
        }

        false
    }

    #[test]
    fn default_bind_is_loopback() {
        let addr: SocketAddr = "127.0.0.1:7788".parse().unwrap();
        assert!(_assert_local_default(addr));
    }

    #[tokio::test]
    async fn wait_for_http_ready_returns_false_when_server_never_starts() {
        let reserved = StdTcpListener::bind("127.0.0.1:0").unwrap();
        let url = format!("http://{}/ping", reserved.local_addr().unwrap());

        assert!(!wait_for_http_ready(&url).await);
    }

    #[test]
    fn create_session_request_uses_expected_method_url_headers_and_body() {
        let client =
            BrowserRuntimeClient::new("http://127.0.0.1:7788/", Some("secret-token".into()))
                .expect("client should build");
        let request = client
            .create_session_request(&CreateSessionRequest {
                profile_id: Some("yura-main".into()),
                headless: Some(true),
                viewport: None,
                persist_profile: Some(false),
                launch_timeout_secs: None,
                persona: None,
                ..Default::default()
            })
            .expect("request should build");

        assert_eq!(request.method(), Method::POST);
        assert_eq!(request.url().as_str(), "http://127.0.0.1:7788/sessions");
        assert_eq!(
            request.headers().get(header::AUTHORIZATION).unwrap(),
            "Bearer secret-token"
        );
        let body = request.body().and_then(|body| body.as_bytes()).unwrap();
        let json_body: serde_json::Value = serde_json::from_slice(body).unwrap();
        assert_eq!(
            json_body,
            json!({
                "profile_id": "yura-main",
                "headless": true,
                "viewport": null,
                "persist_profile": false,
            })
        );
    }

    #[test]
    fn pause_and_artifacts_requests_target_session_scoped_paths() {
        let session_id = Uuid::new_v4();
        let client =
            BrowserRuntimeClient::new("http://127.0.0.1:7788", None).expect("client should build");

        let pause = client
            .pause_session_request(
                session_id,
                &PauseForHumanRequest {
                    reason: Some("manual oauth approval".into()),
                },
            )
            .expect("pause request should build");
        assert_eq!(pause.method(), Method::POST);
        assert_eq!(
            pause.url().as_str(),
            format!("http://127.0.0.1:7788/sessions/{session_id}/pause_for_human")
        );

        let artifacts = client
            .list_artifacts_request(session_id)
            .expect("artifacts request should build");
        assert_eq!(artifacts.method(), Method::GET);
        assert_eq!(
            artifacts.url().as_str(),
            format!("http://127.0.0.1:7788/sessions/{session_id}/artifacts")
        );
    }

    #[test]
    fn wait_request_targets_wait_endpoint_with_timeout_query() {
        let session_id = Uuid::new_v4();
        let client =
            BrowserRuntimeClient::new("http://127.0.0.1:7788", Some("secret-token".into()))
                .expect("client should build");

        let wait = client
            .wait_session_request(session_id, Duration::from_secs(42))
            .expect("wait request should build");

        assert_eq!(wait.method(), Method::GET);
        assert_eq!(
            wait.url().as_str(),
            format!("http://127.0.0.1:7788/sessions/{session_id}/wait?timeout_ms=42000")
        );
        assert_eq!(
            wait.headers().get(header::AUTHORIZATION).unwrap(),
            "Bearer secret-token"
        );
    }

    #[test]
    fn screenshot_writer_reports_output_path_when_saving_to_file() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("shot.png");

        write_screenshot(b"png", Some(path.clone())).unwrap();

        assert_eq!(fs::read(&path).unwrap(), b"png");
    }

    #[test]
    fn screenshot_writer_surfaces_output_write_errors() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("missing").join("shot.png");

        let err = write_screenshot(b"png", Some(path.clone())).unwrap_err();

        assert!(err.to_string().contains("write"));
        assert!(err.to_string().contains("shot.png"));
    }

    #[test]
    fn screenshot_writer_accepts_stdout_mode() {
        write_screenshot(&[], None).unwrap();
    }

    #[test]
    fn replay_renderer_embeds_screenshots_and_event_log() {
        let dir = tempfile::tempdir().unwrap();
        let screenshot = dir.path().join("screen.png");
        let events = dir.path().join("events.jsonl");
        fs::write(&screenshot, b"png-bytes").unwrap();
        fs::write(&events, "{\"type\":\"session_created\"}\n").unwrap();

        let html = render_artifact_replay(&ArtifactsResponse {
            session_id: Uuid::nil(),
            artifacts: vec![
                ArtifactInfo {
                    kind: "event_log".into(),
                    path: events.display().to_string(),
                    size_bytes: 27,
                    created_at: Utc::now(),
                },
                ArtifactInfo {
                    kind: "screenshot".into(),
                    path: screenshot.display().to_string(),
                    size_bytes: 9,
                    created_at: Utc::now(),
                },
            ],
            downloads_dir: dir.path().display().to_string(),
        })
        .unwrap();

        assert!(html.contains("session_created"));
        assert!(html.contains("data:image/png;base64,"));
        assert!(html.contains("screen.png"));
    }

    #[test]
    fn finalize_serve_result_accepts_ok() {
        finalize_serve_result(Ok(())).unwrap();
    }

    #[test]
    fn finalize_serve_result_wraps_io_errors() {
        let err = finalize_serve_result(Err(io::Error::other("boom"))).unwrap_err();

        assert!(err.to_string().contains("serve HTTP"));
        assert!(format!("{err:#}").contains("boom"));
    }

    #[tokio::test]
    async fn serve_app_returns_immediately_when_shutdown_is_ready() {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();

        serve_app(listener, Router::new(), Box::pin(async {}))
            .await
            .unwrap();
    }

    #[tokio::test]
    async fn serve_app_returns_after_shutdown_signal() {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let base_url = format!("http://{}", listener.local_addr().unwrap());
        let (start_tx, start_rx) = oneshot::channel();
        let (shutdown_tx, shutdown_rx) = oneshot::channel();
        let task = tokio::spawn(async move {
            let _ = start_rx.await;
            serve_app(
                listener,
                Router::new().route("/ping", get(|| async { "ok" })),
                Box::pin(async move {
                    let _ = shutdown_rx.await;
                }),
            )
            .await
        });
        tokio::spawn(async move {
            sleep(Duration::from_millis(50)).await;
            let _ = start_tx.send(());
        });

        let url = format!("{base_url}/ping");
        assert!(
            wait_for_http_ready(&url).await,
            "helper server never became ready"
        );
        shutdown_tx.send(()).unwrap();
        task.await.unwrap().unwrap();
    }

    #[tokio::test]
    async fn run_server_with_shutdown_serves_health_and_returns_cleanly() {
        let reserved = StdTcpListener::bind("127.0.0.1:0").unwrap();
        let port = reserved.local_addr().unwrap().port();
        drop(reserved);

        let dir = tempfile::tempdir().unwrap();
        let config = RuntimeConfig {
            bind: format!("127.0.0.1:{port}").parse().unwrap(),
            data_dir: dir.path().to_path_buf(),
            chrome_path: Some(dir.path().join("unused-chrome")),
            bearer_token: None,
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
        };
        let (shutdown_tx, shutdown_rx) = oneshot::channel();
        let task = tokio::spawn(run_server_with_shutdown(
            config,
            Box::pin(async move {
                let _ = shutdown_rx.await;
            }),
        ));
        let url = format!("http://127.0.0.1:{port}/health");

        assert!(
            wait_for_http_ready(&url).await,
            "health endpoint never became ready"
        );
        shutdown_tx.send(()).unwrap();
        task.await.unwrap().unwrap();
    }

    #[tokio::test]
    async fn serve_store_with_shutdown_closes_sessions_and_releases_profile_locks() {
        let reserved = StdTcpListener::bind("127.0.0.1:0").unwrap();
        let port = reserved.local_addr().unwrap().port();
        drop(reserved);

        let dir = tempfile::tempdir().unwrap();
        let cdp = MockCdpServer::spawn().await;
        let store = Arc::new(
            AppStore::new(
                test_config(dir.path().to_path_buf(), None),
                Arc::new(MockBackend::new(
                    cdp.base_url.clone(),
                    cdp.browser_ws_url.clone(),
                )),
            )
            .await
            .unwrap(),
        );
        let created = store.create_session(persistent_req("p1")).await.unwrap();
        let (shutdown_tx, shutdown_rx) = oneshot::channel();
        let task = tokio::spawn(serve_store_with_shutdown(
            format!("127.0.0.1:{port}").parse().unwrap(),
            store.clone(),
            Box::pin(async move {
                let _ = shutdown_rx.await;
            }),
        ));
        let url = format!("http://127.0.0.1:{port}/health");

        assert!(
            wait_for_http_ready(&url).await,
            "health endpoint never became ready"
        );
        shutdown_tx.send(()).unwrap();
        task.await.unwrap().unwrap();

        let closed = store.get_session(created.id).await.unwrap();
        assert_eq!(closed.status, SessionStatus::Closed);
        assert_eq!(
            store
                .list_profiles()
                .await
                .unwrap()
                .into_iter()
                .find(|profile| profile.id == "p1")
                .unwrap()
                .locked_by,
            None
        );
        let commands = cdp.recorded_commands().await;
        assert!(
            commands
                .iter()
                .any(|command| command.method == "Browser.close"),
            "expected Browser.close in {commands:?}"
        );
        cdp.stop().await;
    }

    #[tokio::test]
    async fn shutdown_signal_with_returns_when_ctrl_c_future_resolves() {
        let (ctrl_tx, ctrl_rx) = oneshot::channel::<()>();
        let (_term_tx, term_rx) = oneshot::channel::<()>();
        let task = tokio::spawn(shutdown_signal_with(
            async move {
                let _ = ctrl_rx.await;
            },
            async move {
                let _ = term_rx.await;
            },
        ));

        sleep(Duration::from_millis(25)).await;
        assert!(!task.is_finished());

        ctrl_tx.send(()).unwrap();
        timeout(Duration::from_secs(1), task)
            .await
            .unwrap()
            .unwrap();
    }

    #[tokio::test]
    async fn shutdown_signal_with_returns_when_sigterm_future_resolves() {
        let (_ctrl_tx, ctrl_rx) = oneshot::channel::<()>();
        let (term_tx, term_rx) = oneshot::channel::<()>();
        let task = tokio::spawn(shutdown_signal_with(
            async move {
                let _ = ctrl_rx.await;
            },
            async move {
                let _ = term_rx.await;
            },
        ));

        sleep(Duration::from_millis(25)).await;
        assert!(!task.is_finished());

        term_tx.send(()).unwrap();
        timeout(Duration::from_secs(1), task)
            .await
            .unwrap()
            .unwrap();
    }

    #[tokio::test(flavor = "current_thread")]
    async fn request_tracing_drops_takeover_query_tokens_from_logs() {
        let capture = LogCapture::default();
        let subscriber = tracing_subscriber::fmt()
            .with_ansi(false)
            .with_max_level(tracing::Level::DEBUG)
            .with_writer(capture.clone())
            .finish();
        let _guard = tracing::subscriber::set_default(subscriber);

        let dir = tempfile::tempdir().unwrap();
        let store = Arc::new(
            AppStore::new(
                test_config(dir.path().to_path_buf(), None),
                Arc::new(MockBackend::new(
                    "http://127.0.0.1:1".into(),
                    "ws://127.0.0.1:1".into(),
                )),
            )
            .await
            .unwrap(),
        );
        let session_id = Uuid::new_v4();
        let token = "synthetic-takeover-token";

        let response = runtime_app(store)
            .oneshot(
                Request::builder()
                    .method(Method::GET)
                    .uri(format!("/takeover/{session_id}?token={token}"))
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::FORBIDDEN);

        let logs = capture.output();
        assert!(logs.contains(&format!("/takeover/{session_id}")), "{logs}");
        assert!(!logs.contains("token="), "{logs}");
        assert!(!logs.contains(token), "{logs}");
    }

    #[tokio::test]
    async fn run_server_serves_health_until_aborted() {
        let reserved = StdTcpListener::bind("127.0.0.1:0").unwrap();
        let port = reserved.local_addr().unwrap().port();
        drop(reserved);

        let dir = tempfile::tempdir().unwrap();
        let config = RuntimeConfig {
            bind: format!("127.0.0.1:{port}").parse().unwrap(),
            data_dir: dir.path().to_path_buf(),
            chrome_path: Some(dir.path().join("unused-chrome")),
            bearer_token: None,
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
        };
        let task = tokio::spawn(run_server(config));
        let url = format!("http://127.0.0.1:{port}/health");

        assert!(
            wait_for_http_ready(&url).await,
            "health endpoint never became ready"
        );
        task.abort();
        let _ = task.await;
    }

    #[tokio::test]
    async fn run_server_surfaces_bind_errors() {
        let reserved = StdTcpListener::bind("127.0.0.1:0").unwrap();
        let bind = reserved.local_addr().unwrap();
        let dir = tempfile::tempdir().unwrap();
        let config = RuntimeConfig {
            bind,
            data_dir: dir.path().to_path_buf(),
            chrome_path: Some(dir.path().join("unused-chrome")),
            bearer_token: None,
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
        };

        let err = run_server(config).await.unwrap_err();

        assert!(err.to_string().contains("bind"));
        assert!(err.to_string().contains(&bind.to_string()));
    }

    #[tokio::test]
    async fn run_cli_server_command_surfaces_bind_errors() {
        let reserved = StdTcpListener::bind("127.0.0.1:0").unwrap();
        let bind = reserved.local_addr().unwrap();
        let dir = tempfile::tempdir().unwrap();

        let err = run_cli(Cli {
            command: Command::Server(ServerArgs {
                bind,
                data_dir: Some(dir.path().to_path_buf()),
                chrome_path: Some(dir.path().join("unused-chrome")),
                bearer_token: None,
                operator_token: None,
                headful: false,
                headless: false,
                artifact_retention_secs: 60,
                takeover_ttl_secs: 60,
                launch_timeout_secs: 15,
                captcha_solver_enabled: false,
                default_captcha_policy: CaptchaPolicy::HumanOnly,
                captcha_solver_policy_path: None,
                captcha_solver_provider_order: "capsolver".to_string(),
                captcha_solver_timeout_secs: 120,
                captcha_solver_poll_ms: 3000,
                captcha_solver_verify_timeout_secs: 20,
                captcha_solver_max_attempts: 2,
                captcha_solver_max_cost_usd_per_session: 0.25,
                credential_provider: Default::default(),
                credential_policy_path: None,
                op_path: None,
                op_timeout_secs: 5,
                credential_approval_ttl_secs: 300,
                credential_privacy_guard: true,
                webrtc_ip_policy: Default::default(),
                gpu_policy: Default::default(),
                default_locale: None,
                default_accept_language: None,
                default_timezone_id: None,
                default_platform: None,
                default_hardware_concurrency: DEFAULT_HARDWARE_CONCURRENCY,
                default_device_memory_gb: DEFAULT_DEVICE_MEMORY_GB,
                default_max_touch_points: DEFAULT_MAX_TOUCH_POINTS,
            }),
        })
        .await
        .unwrap_err();

        assert!(err.to_string().contains("bind"));
        assert!(err.to_string().contains(&bind.to_string()));
    }

    #[tokio::test]
    async fn run_cli_sessions_create_sends_launch_timeout_override_in_request_body() {
        let captured = Arc::new(Mutex::new(None::<serde_json::Value>));
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let base_url = format!("http://{}", listener.local_addr().unwrap());
        let (shutdown_tx, shutdown_rx) = oneshot::channel();
        let captured_for_server = captured.clone();
        let task = tokio::spawn(async move {
            serve_app(
                listener,
                Router::new().route("/ready", get(|| async { "ok" })).route(
                    "/sessions",
                    post(move |Json(body): Json<serde_json::Value>| {
                        let captured = captured_for_server.clone();
                        async move {
                            *captured.lock().unwrap() = Some(body);
                            let devtools_path = "devtools/browser/main";
                            Json(json!({
                                "id": Uuid::nil(),
                                "status": "running",
                                "cdp_ws_url": format!("ws://127.0.0.1:9222/{devtools_path}"),
                                "takeover_url": null,
                                "profile_id": "p1"
                            }))
                        }
                    }),
                ),
                Box::pin(async move {
                    let _ = shutdown_rx.await;
                }),
            )
            .await
        });
        assert!(
            wait_for_http_ready(&format!("{base_url}/ready")).await,
            "stub create-session server never became ready"
        );

        let cli = Cli::try_parse_from([
            "hermes-browser-runtime",
            "sessions",
            "create",
            "--server",
            base_url.as_str(),
            "--profile-id",
            "p1",
            "--launch-timeout-secs",
            "9",
        ])
        .expect("sessions create should parse launch timeout override");
        run_cli(cli).await.unwrap();

        let body = captured.lock().unwrap().clone().unwrap();
        assert_eq!(body["profile_id"], json!("p1"));
        assert_eq!(body["launch_timeout_secs"], json!(9));

        let _ = shutdown_tx.send(());
        task.await.unwrap().unwrap();
    }

    fn credential_record(
        session_id: Uuid,
        request_id: Uuid,
        status: CredentialFillStatus,
    ) -> CredentialFillStatusRecord {
        CredentialFillStatusRecord {
            session_id,
            request_id,
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

    #[tokio::test]
    async fn run_cli_credentials_contract_commands_hit_http_client_paths() {
        let session_id = Uuid::new_v4();
        let request_id = Uuid::new_v4();
        let bodies = Arc::new(Mutex::new(Vec::<serde_json::Value>::new()));
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let base_url = format!("http://{}", listener.local_addr().unwrap());
        let (shutdown_tx, shutdown_rx) = oneshot::channel();
        let bodies_for_server = bodies.clone();
        let task = tokio::spawn(async move {
            serve_app(
                listener,
                Router::new()
                    .route("/ready", get(|| async { "ok" }))
                    .route(
                        "/sessions/:id/credentials/fill",
                        post({
                            let bodies = bodies_for_server.clone();
                            move |axum::extract::Path(id): axum::extract::Path<Uuid>,
                                  Json(body): Json<serde_json::Value>| {
                                let bodies = bodies.clone();
                                async move {
                                    bodies.lock().unwrap().push(body);
                                    Json(credential_record(
                                        id,
                                        request_id,
                                        CredentialFillStatus::RequiresUserApproval,
                                    ))
                                }
                            }
                        }),
                    )
                    .route(
                        "/sessions/:id/credentials/fill/:request_id",
                        get(
                            |axum::extract::Path((id, request_id)): axum::extract::Path<(
                                Uuid,
                                Uuid,
                            )>| async move {
                                Json(credential_record(
                                    id,
                                    request_id,
                                    CredentialFillStatus::RequiresUserApproval,
                                ))
                            },
                        ),
                    )
                    .route(
                        "/sessions/:id/credentials/fill/:request_id/approve",
                        post({
                            let bodies = bodies_for_server.clone();
                            move |axum::extract::Path((id, request_id)): axum::extract::Path<(
                                Uuid,
                                Uuid,
                            )>,
                                  Json(body): Json<serde_json::Value>| {
                                let bodies = bodies.clone();
                                async move {
                                    bodies.lock().unwrap().push(body);
                                    Json(credential_record(
                                        id,
                                        request_id,
                                        CredentialFillStatus::Approved,
                                    ))
                                }
                            }
                        }),
                    )
                    .route(
                        "/sessions/:id/credentials/fill/:request_id/deny",
                        post({
                            let bodies = bodies_for_server.clone();
                            move |axum::extract::Path((id, request_id)): axum::extract::Path<(
                                Uuid,
                                Uuid,
                            )>,
                                  Json(body): Json<serde_json::Value>| {
                                let bodies = bodies.clone();
                                async move {
                                    bodies.lock().unwrap().push(body);
                                    Json(credential_record(
                                        id,
                                        request_id,
                                        CredentialFillStatus::Denied,
                                    ))
                                }
                            }
                        }),
                    )
                    .route(
                        "/sessions/:id/credentials/privacy-guard/clear",
                        post(
                            |axum::extract::Path(id): axum::extract::Path<Uuid>| async move {
                                Json(CredentialPrivacyGuardResponse {
                                    session_id: id,
                                    privacy_guard_active: false,
                                })
                            },
                        ),
                    ),
                Box::pin(async move {
                    let _ = shutdown_rx.await;
                }),
            )
            .await
        });
        assert!(
            wait_for_http_ready(&format!("{base_url}/ready")).await,
            "stub credential server never became ready"
        );

        for argv in [
            vec![
                "hermes-browser-runtime",
                "sessions",
                "credentials",
                "request",
                session_id.to_string().as_str(),
                "--server",
                base_url.as_str(),
                "--alias",
                "demo-login",
                "--username-selector",
                "#user",
                "--password-selector",
                "#pass",
            ],
            vec![
                "hermes-browser-runtime",
                "sessions",
                "credentials",
                "status",
                session_id.to_string().as_str(),
                request_id.to_string().as_str(),
                "--server",
                base_url.as_str(),
            ],
            vec![
                "hermes-browser-runtime",
                "credentials",
                "approve",
                session_id.to_string().as_str(),
                request_id.to_string().as_str(),
                "--server",
                base_url.as_str(),
                "--note",
                "operator approved",
            ],
            vec![
                "hermes-browser-runtime",
                "sessions",
                "credentials",
                "deny",
                session_id.to_string().as_str(),
                request_id.to_string().as_str(),
                "--server",
                base_url.as_str(),
                "--reason",
                "operator denied",
            ],
            vec![
                "hermes-browser-runtime",
                "sessions",
                "credentials",
                "clear-privacy-guard",
                session_id.to_string().as_str(),
                "--server",
                base_url.as_str(),
            ],
        ] {
            run_cli(Cli::try_parse_from(argv).unwrap()).await.unwrap();
        }

        let recorded = bodies.lock().unwrap().clone();
        assert_eq!(recorded[0]["alias"], json!("demo-login"));
        assert_eq!(recorded[0]["username_selector"], json!("#user"));
        assert_eq!(recorded[0]["password_selector"], json!("#pass"));
        assert_eq!(recorded[1]["note"], json!("operator approved"));
        assert_eq!(recorded[2]["reason"], json!("operator denied"));
        assert!(recorded[2].get("note").is_none());

        shutdown_tx.send(()).unwrap();
        task.await.unwrap().unwrap();
    }

    #[tokio::test]
    async fn run_helpers_surface_http_errors_for_release_wait_profiles_and_artifacts() {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let base_url = format!("http://{}", listener.local_addr().unwrap());
        let (shutdown_tx, shutdown_rx) = oneshot::channel();
        let task = tokio::spawn(async move {
            serve_app(
                listener,
                Router::new()
                    .route("/ready", get(|| async { "ok" }))
                    .route(
                        "/sessions/:id/release",
                        post(|| async { (StatusCode::CONFLICT, "release blocked") }),
                    )
                    .route(
                        "/sessions/:id/wait",
                        get(|| async { (StatusCode::REQUEST_TIMEOUT, "still paused") }),
                    )
                    .route(
                        "/sessions/:id/artifacts",
                        get(|| async { (StatusCode::UNAUTHORIZED, "missing token") }),
                    )
                    .route(
                        "/profiles/:id",
                        delete(|| async { (StatusCode::NOT_FOUND, "missing profile") }),
                    ),
                Box::pin(async move {
                    let _ = shutdown_rx.await;
                }),
            )
            .await
        });
        assert!(
            wait_for_http_ready(&format!("{base_url}/ready")).await,
            "stub helper server never became ready"
        );

        let session_id = Uuid::new_v4();
        let client = client_args(&base_url);

        let release_err = run_sessions(SessionsArgs {
            command: SessionsCommand::Release(SessionIdArgs {
                client: client.clone(),
                session_id,
            }),
        })
        .await
        .unwrap_err();
        assert_eq!(
            release_err
                .downcast_ref::<reqwest::Error>()
                .and_then(|err| err.status()),
            Some(StatusCode::CONFLICT)
        );
        assert!(release_err.to_string().contains("/release"));

        let wait_err = run_sessions(SessionsArgs {
            command: SessionsCommand::Wait(WaitSessionArgs {
                client: client.clone(),
                session_id,
                timeout_secs: 1,
            }),
        })
        .await
        .unwrap_err();
        assert_eq!(
            wait_err
                .downcast_ref::<reqwest::Error>()
                .and_then(|err| err.status()),
            Some(StatusCode::REQUEST_TIMEOUT)
        );
        assert!(wait_err.to_string().contains("/wait?timeout_ms=1000"));

        let artifacts_err = run_artifacts(ArtifactsArgs {
            command: ArtifactsCommand::List(SessionIdArgs {
                client: client.clone(),
                session_id,
            }),
        })
        .await
        .unwrap_err();
        assert_eq!(
            artifacts_err
                .downcast_ref::<reqwest::Error>()
                .and_then(|err| err.status()),
            Some(StatusCode::UNAUTHORIZED)
        );
        assert!(artifacts_err.to_string().contains("/artifacts"));

        let profile_err = run_profiles(ProfilesArgs {
            command: ProfilesCommand::Delete(ProfileIdArgs {
                client,
                profile_id: "missing-profile".into(),
            }),
        })
        .await
        .unwrap_err();
        assert_eq!(
            profile_err
                .downcast_ref::<reqwest::Error>()
                .and_then(|err| err.status()),
            Some(StatusCode::NOT_FOUND)
        );
        assert!(
            profile_err
                .to_string()
                .contains("/profiles/missing-profile")
        );

        shutdown_tx.send(()).unwrap();
        task.await.unwrap().unwrap();
    }

    #[tokio::test]
    async fn run_helpers_cover_profiles_sessions_and_artifacts_lifecycle() {
        let server = spawn_api_server(None).await;
        let client = client_args(&server.base_url);

        run_profiles(ProfilesArgs {
            command: ProfilesCommand::Create(CreateProfileArgs {
                client: client.clone(),
                id: Some("p1".into()),
            }),
        })
        .await
        .unwrap();
        run_profiles(ProfilesArgs {
            command: ProfilesCommand::List(client.clone()),
        })
        .await
        .unwrap();

        run_cli(Cli {
            command: Command::Sessions(SessionsArgs {
                command: SessionsCommand::Create(ClientCreateSessionArgs {
                    client: client.clone(),
                    profile_id: Some("p1".into()),
                    persist_profile: true,
                    headless: true,
                    headful: false,
                    launch_timeout_secs: None,
                    webrtc_ip_policy: None,
                    gpu_policy: None,
                    captcha_policy: None,
                }),
            }),
        })
        .await
        .unwrap();

        let session_id = server.store.list_sessions().await[0].id;

        run_sessions(SessionsArgs {
            command: SessionsCommand::List(client.clone()),
        })
        .await
        .unwrap();
        run_sessions(SessionsArgs {
            command: SessionsCommand::Get(SessionIdArgs {
                client: client.clone(),
                session_id,
            }),
        })
        .await
        .unwrap();
        run_sessions(SessionsArgs {
            command: SessionsCommand::Pause(PauseSessionArgs {
                client: client.clone(),
                session_id,
                reason: Some("manual oauth approval".into()),
            }),
        })
        .await
        .unwrap();

        let releaser = {
            let store = server.store.clone();
            tokio::spawn(async move {
                sleep(Duration::from_millis(25)).await;
                store.release(session_id).await.unwrap();
            })
        };
        run_sessions(SessionsArgs {
            command: SessionsCommand::Wait(WaitSessionArgs {
                client: client.clone(),
                session_id,
                timeout_secs: 1,
            }),
        })
        .await
        .unwrap();
        releaser.await.unwrap();

        run_sessions(SessionsArgs {
            command: SessionsCommand::Pause(PauseSessionArgs {
                client: client.clone(),
                session_id,
                reason: Some("release me again".into()),
            }),
        })
        .await
        .unwrap();
        run_sessions(SessionsArgs {
            command: SessionsCommand::Release(SessionIdArgs {
                client: client.clone(),
                session_id,
            }),
        })
        .await
        .unwrap();

        let shot_dir = tempfile::tempdir().unwrap();
        let shot_path = shot_dir.path().join("shot.png");
        run_sessions(SessionsArgs {
            command: SessionsCommand::Screenshot(ScreenshotArgs {
                client: client.clone(),
                session_id,
                output: Some(shot_path.clone()),
            }),
        })
        .await
        .unwrap();
        assert_eq!(fs::read(&shot_path).unwrap(), b"png");

        run_cli(Cli {
            command: Command::Artifacts(ArtifactsArgs {
                command: ArtifactsCommand::List(SessionIdArgs {
                    client: client.clone(),
                    session_id,
                }),
            }),
        })
        .await
        .unwrap();

        run_sessions(SessionsArgs {
            command: SessionsCommand::Delete(SessionIdArgs {
                client: client.clone(),
                session_id,
            }),
        })
        .await
        .unwrap();
        run_profiles(ProfilesArgs {
            command: ProfilesCommand::Delete(ProfileIdArgs {
                client,
                profile_id: "p1".into(),
            }),
        })
        .await
        .unwrap();

        server.stop().await;
    }
}
