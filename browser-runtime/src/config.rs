use std::{
    ffi::OsString,
    fs,
    net::{IpAddr, Ipv4Addr, SocketAddr},
    path::PathBuf,
    time::Duration,
};

use clap::{Args, Parser, Subcommand};
use uuid::Uuid;

use crate::credentials::{
    CredentialBrokerMode, DEFAULT_CREDENTIAL_APPROVAL_TTL_SECS, DEFAULT_OP_TIMEOUT_SECS,
};
use crate::models::{
    BrowserPersona, CaptchaPolicy, CaptchaReportState, CaptchaResolveOutcome,
    DEFAULT_DEVICE_MEMORY_GB, DEFAULT_HARDWARE_CONCURRENCY, DEFAULT_MAX_TOUCH_POINTS, GpuPolicy,
    WebRtcIpPolicy,
};

pub const DEFAULT_OP_TIMEOUT: Duration = Duration::from_secs(DEFAULT_OP_TIMEOUT_SECS);
pub const DEFAULT_CREDENTIAL_APPROVAL_TTL: Duration =
    Duration::from_secs(DEFAULT_CREDENTIAL_APPROVAL_TTL_SECS);
const DEFAULT_CAPTCHA_SOLVER_TIMEOUT_SECS: u64 = 120;
const DEFAULT_CAPTCHA_SOLVER_POLL_MS: u64 = 3000;
const DEFAULT_CAPTCHA_SOLVER_VERIFY_TIMEOUT_SECS: u64 = 20;
const DEFAULT_CAPTCHA_SOLVER_MAX_ATTEMPTS: u32 = 2;
const DEFAULT_CAPTCHA_SOLVER_MAX_COST_USD_PER_SESSION: f64 = 0.25;

#[derive(Parser, Debug, Clone)]
#[command(
    name = "hermes-browser-runtime",
    about = "Local CDP-first browser runtime for agents"
)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Subcommand, Debug, Clone)]
// Keep the derived clap command enum unboxed: `ServerArgs` is large because it
// owns all server CLI/env configuration, but this enum is parsed once at
// process startup and boxing the subcommand would complicate clap's derive
// shape without improving runtime safety.
#[allow(clippy::large_enum_variant)]
pub enum Command {
    /// Run the HTTP API server.
    Server(ServerArgs),
    /// Manage sessions against a running server.
    Sessions(SessionsArgs),
    /// Request and approve credential fills through the broker.
    #[command(alias = "credential")]
    Credentials(CredentialsArgs),
    /// Report or resolve CAPTCHA checkpoints for a session.
    Captcha(CaptchaArgs),
    /// Manage profiles against a running server.
    Profiles(ProfilesArgs),
    /// Inspect session artifacts against a running server.
    Artifacts(ArtifactsArgs),
}

#[derive(Args, Debug, Clone)]
pub struct SessionsArgs {
    #[command(subcommand)]
    pub command: SessionsCommand,
}

#[derive(Subcommand, Debug, Clone)]
pub enum SessionsCommand {
    /// Create a browser session.
    Create(ClientCreateSessionArgs),
    /// List active sessions.
    List(ClientArgs),
    /// Fetch one session.
    Get(SessionIdArgs),
    /// Delete one session.
    Delete(SessionIdArgs),
    /// Pause a session for human takeover.
    Pause(PauseSessionArgs),
    /// Release a paused session back to the agent.
    Release(SessionIdArgs),
    /// Wait until a paused session leaves takeover mode.
    Wait(WaitSessionArgs),
    /// Capture a screenshot from one session.
    Screenshot(ScreenshotArgs),
    /// Request and approve credential fills through the broker for a session.
    Credentials(CredentialsArgs),
    /// Report or resolve CAPTCHA checkpoints for a session.
    Captcha(CaptchaArgs),
}

#[derive(Args, Debug, Clone)]
pub struct CaptchaArgs {
    #[command(subcommand)]
    pub command: CaptchaCommand,
}

#[derive(Subcommand, Debug, Clone)]
pub enum CaptchaCommand {
    /// Report a CAPTCHA checkpoint for a session.
    Report(CaptchaReportArgs),
    /// Resolve a previously reported CAPTCHA checkpoint.
    Resolve(CaptchaResolveArgs),
}

#[derive(Args, Debug, Clone)]
pub struct CaptchaReportArgs {
    #[command(flatten)]
    pub client: ClientArgs,
    pub session_id: Uuid,
    #[arg(long)]
    pub state: CaptchaReportState,
    #[arg(long)]
    pub challenge_type: Option<String>,
    #[arg(long)]
    pub reason: Option<String>,
}

#[derive(Args, Debug, Clone)]
pub struct CaptchaResolveArgs {
    #[command(flatten)]
    pub client: ClientArgs,
    pub session_id: Uuid,
    #[arg(long)]
    pub outcome: CaptchaResolveOutcome,
    #[arg(long)]
    pub note: Option<String>,
}

#[derive(Args, Debug, Clone)]
pub struct CredentialsArgs {
    #[command(subcommand)]
    pub command: CredentialsCommand,
}

#[derive(Subcommand, Debug, Clone)]
pub enum CredentialsCommand {
    /// Request a broker-gated fill into the live browser session.
    #[command(alias = "request")]
    Fill(CredentialFillArgs),
    /// Show a credential fill status without exposing selectors or provider refs.
    Status(CredentialStatusArgs),
    /// Approve and execute a pending credential fill.
    Approve(CredentialDecisionArgs),
    /// Deny a pending credential fill.
    Deny(CredentialDecisionArgs),
    /// Clear the credential privacy guard after a human confirms sensitive fields are no longer visible.
    #[command(name = "privacy-guard")]
    PrivacyGuard(CredentialPrivacyGuardArgs),
    /// Clear the credential privacy guard with the accepted flat operator CLI spelling.
    #[command(name = "clear-privacy-guard")]
    ClearPrivacyGuard(OperatorSessionIdArgs),
    /// Backward-compatible alias for `credentials privacy-guard clear`.
    #[command(name = "clear-guard", hide = true)]
    ClearGuard(OperatorSessionIdArgs),
}

#[derive(Args, Debug, Clone)]
pub struct CredentialPrivacyGuardArgs {
    #[command(subcommand)]
    pub command: CredentialPrivacyGuardCommand,
}

#[derive(Subcommand, Debug, Clone)]
pub enum CredentialPrivacyGuardCommand {
    /// Clear the credential privacy guard after a human confirms sensitive fields are no longer visible.
    Clear(OperatorSessionIdArgs),
}

#[derive(Args, Debug, Clone)]
pub struct ProfilesArgs {
    #[command(subcommand)]
    pub command: ProfilesCommand,
}

#[derive(Subcommand, Debug, Clone)]
pub enum ProfilesCommand {
    /// Create a persistent profile directory.
    Create(CreateProfileArgs),
    /// List known profiles.
    List(ClientArgs),
    /// Delete one profile.
    Delete(ProfileIdArgs),
}

#[derive(Args, Debug, Clone)]
pub struct ArtifactsArgs {
    #[command(subcommand)]
    pub command: ArtifactsCommand,
}

#[derive(Subcommand, Debug, Clone)]
pub enum ArtifactsCommand {
    /// List artifacts for one session.
    List(SessionIdArgs),
    /// List files captured in the session downloads directory.
    Downloads(SessionIdArgs),
    /// Fetch one downloaded file.
    Download(DownloadArtifactArgs),
    /// Delete expired artifact directories.
    Cleanup(CleanupArtifactsArgs),
    /// Render a static HTML replay from local artifact files.
    Replay(ReplayArtifactsArgs),
}

#[derive(Args, Debug, Clone)]
pub struct ServerArgs {
    #[arg(long, env = "HBR_BIND", default_value = "127.0.0.1:7788")]
    pub bind: SocketAddr,

    #[arg(long, env = "HBR_DATA_DIR")]
    pub data_dir: Option<PathBuf>,

    #[arg(long, env = "HBR_CHROME_PATH")]
    pub chrome_path: Option<PathBuf>,

    /// Agent/client bearer token for non-operator API routes.
    #[arg(long, env = "HBR_BEARER_TOKEN")]
    pub bearer_token: Option<String>,

    /// Operator-only bearer token for credential approvals, denials, and privacy-guard clear.
    #[arg(long, env = "HBR_OPERATOR_TOKEN")]
    pub operator_token: Option<String>,

    /// Force headed Chrome even when no local display or xvfb-run wrapper was detected.
    #[arg(
        long,
        env = "HBR_HEADFUL",
        default_value_t = false,
        conflicts_with = "headless"
    )]
    pub headful: bool,

    /// Force headless Chrome. When omitted, the runtime prefers headed mode if DISPLAY/WAYLAND_DISPLAY or xvfb-run exists.
    #[arg(long, env = "HBR_HEADLESS", default_value_t = false)]
    pub headless: bool,

    #[arg(long, env = "HBR_ARTIFACT_RETENTION_SECS", default_value_t = 604800)]
    pub artifact_retention_secs: u64,

    #[arg(long, env = "HBR_TAKEOVER_TTL_SECS", default_value_t = 900)]
    pub takeover_ttl_secs: u64,

    #[arg(long, env = "HBR_LAUNCH_TIMEOUT_SECS", default_value_t = 15)]
    pub launch_timeout_secs: u64,

    /// Global CAPTCHA solve kill switch. Defaults off; manual human handling remains the safe path.
    #[arg(long, env = "HBR_CAPTCHA_SOLVER_ENABLED", default_value_t = false)]
    pub captcha_solver_enabled: bool,

    /// Server default applied when a session request omits captcha_policy.
    #[arg(
        long,
        env = "HBR_DEFAULT_CAPTCHA_POLICY",
        default_value_t = CaptchaPolicy::default()
    )]
    pub default_captcha_policy: CaptchaPolicy,

    /// Private solver policy allowlist path. This is a path only, not a provider credential.
    #[arg(long, env = "HBR_CAPTCHA_SOLVER_POLICY_PATH")]
    pub captcha_solver_policy_path: Option<PathBuf>,

    /// Ordered provider IDs for future solver routing; parsed later by the provider seam.
    #[arg(
        long,
        env = "HBR_CAPTCHA_SOLVER_PROVIDER_ORDER",
        default_value = "capsolver"
    )]
    pub captcha_solver_provider_order: String,

    #[arg(
        long,
        env = "HBR_CAPTCHA_SOLVER_TIMEOUT_SECS",
        default_value_t = DEFAULT_CAPTCHA_SOLVER_TIMEOUT_SECS
    )]
    pub captcha_solver_timeout_secs: u64,

    #[arg(
        long,
        env = "HBR_CAPTCHA_SOLVER_POLL_MS",
        default_value_t = DEFAULT_CAPTCHA_SOLVER_POLL_MS
    )]
    pub captcha_solver_poll_ms: u64,

    #[arg(
        long,
        env = "HBR_CAPTCHA_SOLVER_VERIFY_TIMEOUT_SECS",
        default_value_t = DEFAULT_CAPTCHA_SOLVER_VERIFY_TIMEOUT_SECS
    )]
    pub captcha_solver_verify_timeout_secs: u64,

    #[arg(
        long,
        env = "HBR_CAPTCHA_SOLVER_MAX_ATTEMPTS",
        default_value_t = DEFAULT_CAPTCHA_SOLVER_MAX_ATTEMPTS
    )]
    pub captcha_solver_max_attempts: u32,

    #[arg(
        long,
        env = "HBR_CAPTCHA_SOLVER_MAX_COST_USD_PER_SESSION",
        default_value_t = DEFAULT_CAPTCHA_SOLVER_MAX_COST_USD_PER_SESSION
    )]
    pub captcha_solver_max_cost_usd_per_session: f64,

    /// Credential provider mode. Real 1Password access is explicit-only and still approval-gated.
    #[arg(
        long,
        env = "HBR_CREDENTIAL_PROVIDER",
        default_value_t = CredentialBrokerMode::default()
    )]
    pub credential_provider: CredentialBrokerMode,

    /// Private credential policy path containing alias allowlists and provider refs; never committed/logged.
    #[arg(long, env = "HBR_CREDENTIAL_POLICY_PATH")]
    pub credential_policy_path: Option<PathBuf>,

    /// Path to the local 1Password CLI binary. This is a path only, not a token.
    #[arg(long, env = "HBR_OP_PATH")]
    pub op_path: Option<PathBuf>,

    #[arg(long, env = "HBR_OP_TIMEOUT_SECS", default_value_t = DEFAULT_OP_TIMEOUT_SECS)]
    pub op_timeout_secs: u64,

    #[arg(
        long,
        env = "HBR_CREDENTIAL_APPROVAL_TTL_SECS",
        default_value_t = DEFAULT_CREDENTIAL_APPROVAL_TTL_SECS
    )]
    pub credential_approval_ttl_secs: u64,

    #[arg(long, env = "HBR_CREDENTIAL_PRIVACY_GUARD", default_value_t = true)]
    pub credential_privacy_guard: bool,

    #[arg(
        long,
        env = "HBR_WEBRTC_IP_POLICY",
        default_value_t = WebRtcIpPolicy::default()
    )]
    pub webrtc_ip_policy: WebRtcIpPolicy,

    #[arg(long, env = "HBR_GPU_POLICY", default_value_t = GpuPolicy::default())]
    pub gpu_policy: GpuPolicy,

    /// Default browser locale used when a session request omits an explicit persona.
    #[arg(long, env = "HBR_DEFAULT_LOCALE")]
    pub default_locale: Option<String>,

    /// Default Accept-Language override used with the default browser persona.
    #[arg(long, env = "HBR_DEFAULT_ACCEPT_LANGUAGE")]
    pub default_accept_language: Option<String>,

    /// Default browser timezone used when a session request omits an explicit persona.
    #[arg(long, env = "HBR_DEFAULT_TIMEZONE_ID")]
    pub default_timezone_id: Option<String>,

    /// Default navigator.platform override used with the default browser persona.
    #[arg(long, env = "HBR_DEFAULT_PLATFORM")]
    pub default_platform: Option<String>,

    /// Default navigator.hardwareConcurrency used with the default browser persona.
    #[arg(
        long,
        env = "HBR_DEFAULT_HARDWARE_CONCURRENCY",
        default_value_t = DEFAULT_HARDWARE_CONCURRENCY
    )]
    pub default_hardware_concurrency: u32,

    /// Default navigator.deviceMemory used with the default browser persona.
    #[arg(
        long,
        env = "HBR_DEFAULT_DEVICE_MEMORY_GB",
        default_value_t = DEFAULT_DEVICE_MEMORY_GB
    )]
    pub default_device_memory_gb: u32,

    /// Default navigator.maxTouchPoints used with the default browser persona.
    #[arg(
        long,
        env = "HBR_DEFAULT_MAX_TOUCH_POINTS",
        default_value_t = DEFAULT_MAX_TOUCH_POINTS
    )]
    pub default_max_touch_points: u32,
}

#[derive(Args, Debug, Clone)]
pub struct ClientArgs {
    #[arg(long, env = "HBR_SERVER", default_value = "http://127.0.0.1:7788")]
    pub server: String,

    #[arg(long, env = "HBR_BEARER_TOKEN")]
    pub bearer_token: Option<String>,
}

#[derive(Args, Debug, Clone)]
pub struct OperatorClientArgs {
    #[arg(long, env = "HBR_SERVER", default_value = "http://127.0.0.1:7788")]
    pub server: String,

    /// Operator-only token for credential approval, denial, and privacy-guard clear.
    #[arg(long = "operator-token", env = "HBR_OPERATOR_TOKEN")]
    pub operator_token: Option<String>,
}

#[derive(Args, Debug, Clone)]
pub struct ClientCreateSessionArgs {
    #[command(flatten)]
    pub client: ClientArgs,

    #[arg(long)]
    pub profile_id: Option<String>,

    #[arg(long, default_value_t = true)]
    pub persist_profile: bool,

    /// Ask the server for a headless session. If omitted, the server uses its headed/headless default.
    #[arg(long, default_value_t = false, conflicts_with = "headful")]
    pub headless: bool,

    /// Ask the server for a headed session. If omitted, the server uses its headed/headless default.
    #[arg(long, default_value_t = false)]
    pub headful: bool,

    #[arg(long)]
    pub launch_timeout_secs: Option<u64>,

    #[arg(long, env = "HBR_WEBRTC_IP_POLICY")]
    pub webrtc_ip_policy: Option<WebRtcIpPolicy>,

    #[arg(long, env = "HBR_GPU_POLICY")]
    pub gpu_policy: Option<GpuPolicy>,

    #[arg(long, env = "HBR_CAPTCHA_POLICY")]
    pub captcha_policy: Option<CaptchaPolicy>,
}

#[derive(Args, Debug, Clone)]
pub struct SessionIdArgs {
    #[command(flatten)]
    pub client: ClientArgs,

    pub session_id: Uuid,
}

#[derive(Args, Debug, Clone)]
pub struct OperatorSessionIdArgs {
    #[command(flatten)]
    pub client: OperatorClientArgs,

    pub session_id: Uuid,
}

#[derive(Args, Debug, Clone)]
pub struct CredentialFillArgs {
    #[command(flatten)]
    pub client: ClientArgs,

    pub session_id: Uuid,

    #[arg(long)]
    pub alias: String,

    #[arg(long)]
    pub username_selector: Option<String>,

    #[arg(long)]
    pub password_selector: Option<String>,

    #[arg(long)]
    pub expected_origin: Option<String>,

    #[arg(long)]
    pub purpose: Option<String>,
}

#[derive(Args, Debug, Clone)]
pub struct CredentialStatusArgs {
    #[command(flatten)]
    pub client: ClientArgs,

    pub session_id: Uuid,
    pub request_id: Uuid,
}

#[derive(Args, Debug, Clone)]
pub struct CredentialDecisionArgs {
    #[command(flatten)]
    pub client: OperatorClientArgs,

    pub session_id: Uuid,
    pub request_id: Uuid,

    /// Human-readable approval/denial note. Notes are redacted before persistence.
    #[arg(long, alias = "reason")]
    pub note: Option<String>,
}

#[derive(Args, Debug, Clone)]
pub struct DownloadArtifactArgs {
    #[command(flatten)]
    pub client: ClientArgs,

    pub session_id: Uuid,

    pub name: String,

    #[arg(long)]
    pub output: Option<PathBuf>,
}

#[derive(Args, Debug, Clone)]
pub struct CleanupArtifactsArgs {
    #[command(flatten)]
    pub client: ClientArgs,

    #[arg(long, default_value_t = false)]
    pub dry_run: bool,

    #[arg(long)]
    pub older_than_secs: Option<u64>,
}

#[derive(Args, Debug, Clone)]
pub struct ReplayArtifactsArgs {
    #[command(flatten)]
    pub client: ClientArgs,

    pub session_id: Uuid,

    #[arg(long)]
    pub output: Option<PathBuf>,
}

#[derive(Args, Debug, Clone)]
pub struct PauseSessionArgs {
    #[command(flatten)]
    pub client: ClientArgs,

    pub session_id: Uuid,

    #[arg(long)]
    pub reason: Option<String>,
}

#[derive(Args, Debug, Clone)]
pub struct WaitSessionArgs {
    #[command(flatten)]
    pub client: ClientArgs,

    pub session_id: Uuid,

    #[arg(long, default_value_t = 300)]
    pub timeout_secs: u64,
}

#[derive(Args, Debug, Clone)]
pub struct ScreenshotArgs {
    #[command(flatten)]
    pub client: ClientArgs,

    pub session_id: Uuid,

    #[arg(long)]
    pub output: Option<PathBuf>,
}

#[derive(Args, Debug, Clone)]
pub struct CreateProfileArgs {
    #[command(flatten)]
    pub client: ClientArgs,

    #[arg(long)]
    pub id: Option<String>,
}

#[derive(Args, Debug, Clone)]
pub struct ProfileIdArgs {
    #[command(flatten)]
    pub client: ClientArgs,

    pub profile_id: String,
}

#[derive(Debug, Clone)]
pub struct RuntimeConfig {
    pub bind: SocketAddr,
    pub data_dir: PathBuf,
    pub chrome_path: Option<PathBuf>,
    pub default_headless: bool,
    pub default_webrtc_ip_policy: WebRtcIpPolicy,
    pub default_gpu_policy: GpuPolicy,
    pub default_persona: BrowserPersona,
    pub artifact_retention: Duration,
    pub takeover_ttl: Duration,
    pub launch_timeout: Duration,
    pub captcha_solver_enabled: bool,
    pub default_captcha_policy: CaptchaPolicy,
    pub captcha_solver_policy_path: Option<PathBuf>,
    pub captcha_solver_provider_order: String,
    pub captcha_solver_timeout: Duration,
    pub captcha_solver_poll_interval: Duration,
    pub captcha_solver_verify_timeout: Duration,
    pub captcha_solver_max_attempts: u32,
    pub captcha_solver_max_cost_usd_per_session: f64,
    pub captcha_solver_provider_key_available: bool,
    pub credential_provider: CredentialBrokerMode,
    pub credential_policy_path: Option<PathBuf>,
    pub op_path: Option<PathBuf>,
    pub op_timeout: Duration,
    pub credential_approval_ttl: Duration,
    pub credential_privacy_guard: bool,
    pub bearer_token: Option<String>,
    pub operator_token: Option<String>,
}

impl RuntimeConfig {
    pub fn from_server_args(args: ServerArgs) -> Self {
        Self::from_server_args_with_environment(
            args,
            std::env::var_os("DISPLAY"),
            std::env::var_os("WAYLAND_DISPLAY"),
            crate::display::find_xvfb_run_path(),
        )
    }

    pub(crate) fn from_server_args_with_environment(
        args: ServerArgs,
        display: Option<OsString>,
        wayland_display: Option<OsString>,
        xvfb_run_path: Option<PathBuf>,
    ) -> Self {
        let default_persona = default_persona_for_environment(&args);
        Self {
            bind: args.bind,
            data_dir: args.data_dir.unwrap_or_else(default_data_dir),
            chrome_path: args.chrome_path,
            bearer_token: args.bearer_token,
            operator_token: args.operator_token,
            default_headless: default_headless_for_environment(
                args.headless,
                args.headful,
                display,
                wayland_display,
                xvfb_run_path,
            ),
            artifact_retention: Duration::from_secs(args.artifact_retention_secs),
            takeover_ttl: Duration::from_secs(args.takeover_ttl_secs),
            launch_timeout: Duration::from_secs(args.launch_timeout_secs),
            captcha_solver_enabled: args.captcha_solver_enabled,
            default_captcha_policy: args.default_captcha_policy,
            captcha_solver_policy_path: args.captcha_solver_policy_path,
            captcha_solver_provider_order: args.captcha_solver_provider_order,
            captcha_solver_timeout: Duration::from_secs(args.captcha_solver_timeout_secs),
            captcha_solver_poll_interval: Duration::from_millis(args.captcha_solver_poll_ms),
            captcha_solver_verify_timeout: Duration::from_secs(
                args.captcha_solver_verify_timeout_secs,
            ),
            captcha_solver_max_attempts: args.captcha_solver_max_attempts,
            captcha_solver_max_cost_usd_per_session: args.captcha_solver_max_cost_usd_per_session,
            captcha_solver_provider_key_available: captcha_solver_provider_key_available(),
            credential_provider: args.credential_provider,
            credential_policy_path: args.credential_policy_path,
            op_path: args.op_path,
            op_timeout: Duration::from_secs(args.op_timeout_secs),
            credential_approval_ttl: Duration::from_secs(args.credential_approval_ttl_secs),
            credential_privacy_guard: args.credential_privacy_guard,
            default_webrtc_ip_policy: args.webrtc_ip_policy,
            default_gpu_policy: args.gpu_policy,
            default_persona,
        }
    }

    pub fn localhost_base_url(&self) -> String {
        let host = match self.bind.ip() {
            IpAddr::V4(ip) if ip == Ipv4Addr::UNSPECIFIED => "127.0.0.1".to_string(),
            IpAddr::V6(_) => format!("[{}]", self.bind.ip()),
            ip => ip.to_string(),
        };
        format!("http://{}:{}", host, self.bind.port())
    }
}

fn captcha_solver_provider_key_available() -> bool {
    [
        "HBR_CAPSOLVER_API_KEY",
        "HBR_2CAPTCHA_API_KEY",
        "HBR_ANTI_CAPTCHA_API_KEY",
        "HBR_ANTICAPTCHA_API_KEY",
        "HBR_CAPTCHA_SOLVER_API_KEY",
    ]
    .iter()
    .any(|name| std::env::var_os(name).is_some_and(|value| !value.is_empty()))
}

fn default_headless_for_environment(
    explicit_headless: bool,
    explicit_headful: bool,
    display: Option<OsString>,
    wayland_display: Option<OsString>,
    xvfb_run_path: Option<PathBuf>,
) -> bool {
    if explicit_headless {
        return true;
    }
    if explicit_headful {
        return false;
    }
    !crate::display::headed_mode_supported(display, wayland_display, xvfb_run_path)
}

fn default_persona_for_environment(args: &ServerArgs) -> BrowserPersona {
    let mut persona = BrowserPersona::default();
    if let Some(locale) = detect_host_locale() {
        persona.locale = locale.clone();
        persona.accept_language = accept_language_for_locale(&locale);
    }
    if let Some(timezone_id) = detect_host_timezone_id() {
        persona.timezone_id = timezone_id;
    }

    if let Some(locale) = normalized_non_empty(args.default_locale.as_deref()) {
        persona.locale = locale.clone();
        if args.default_accept_language.is_none() {
            persona.accept_language = accept_language_for_locale(&locale);
        }
    }
    if let Some(accept_language) = normalized_non_empty(args.default_accept_language.as_deref()) {
        persona.accept_language = accept_language;
    }
    if let Some(timezone_id) = normalized_non_empty(args.default_timezone_id.as_deref()) {
        persona.timezone_id = timezone_id;
    }
    if let Some(platform) = normalized_non_empty(args.default_platform.as_deref()) {
        persona.platform = platform;
    }
    persona.hardware_concurrency = args.default_hardware_concurrency;
    persona.device_memory_gb = args.default_device_memory_gb;
    persona.max_touch_points = args.default_max_touch_points;
    persona
}

fn detect_host_locale() -> Option<String> {
    ["LC_ALL", "LC_MESSAGES", "LANG"]
        .into_iter()
        .filter_map(|key| std::env::var(key).ok())
        .find_map(|value| normalize_locale(&value))
}

fn normalize_locale(value: &str) -> Option<String> {
    let trimmed = value.trim();
    if trimmed.is_empty()
        || trimmed.eq_ignore_ascii_case("C")
        || trimmed.eq_ignore_ascii_case("POSIX")
    {
        return None;
    }
    let base = trimmed
        .split('.')
        .next()
        .unwrap_or(trimmed)
        .split('@')
        .next()
        .unwrap_or(trimmed)
        .replace('_', "-");
    normalized_non_empty(Some(&base))
}

fn accept_language_for_locale(locale: &str) -> String {
    let primary = locale.split('-').next().unwrap_or(locale);
    if primary == locale {
        format!("{locale},en-US;q=0.8,en;q=0.7")
    } else {
        format!("{locale},{primary};q=0.9,en-US;q=0.8,en;q=0.7")
    }
}

fn detect_host_timezone_id() -> Option<String> {
    std::env::var("TZ")
        .ok()
        .and_then(|value| normalize_timezone_id(&value))
        .or_else(|| {
            fs::read_to_string("/etc/timezone")
                .ok()
                .and_then(|value| normalize_timezone_id(&value))
        })
        .or_else(|| {
            fs::read_link("/etc/localtime")
                .ok()
                .and_then(|path| path.to_str().and_then(timezone_from_localtime_path))
        })
}

fn normalize_timezone_id(value: &str) -> Option<String> {
    let trimmed = value.trim();
    if trimmed.is_empty() || trimmed.starts_with(':') || trimmed.starts_with('/') {
        return None;
    }
    if !trimmed.contains('/') {
        return None;
    }
    normalized_non_empty(Some(trimmed))
}

fn timezone_from_localtime_path(path: &str) -> Option<String> {
    path.split("/zoneinfo/")
        .nth(1)
        .and_then(|value| normalized_non_empty(Some(value)))
}

fn normalized_non_empty(value: Option<&str>) -> Option<String> {
    value
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
}

pub fn default_data_dir() -> PathBuf {
    default_data_dir_from(dirs::data_dir())
}

fn default_data_dir_from(base_dir: Option<PathBuf>) -> PathBuf {
    base_dir
        .unwrap_or_else(|| PathBuf::from("."))
        .join("hermes-browser-runtime")
}

#[cfg(test)]
mod tests {
    use super::*;
    use clap::{Command as ClapCommand, CommandFactory, Parser};
    use std::{
        ffi::{OsStr, OsString},
        sync::{Mutex, OnceLock},
    };

    fn sessions_args(command: Command) -> SessionsArgs {
        let Command::Sessions(args) = command else {
            panic!("expected sessions command");
        };
        args
    }

    fn profiles_args(command: Command) -> ProfilesArgs {
        let Command::Profiles(args) = command else {
            panic!("expected profiles command");
        };
        args
    }

    fn credentials_args(command: Command) -> CredentialsArgs {
        let Command::Credentials(args) = command else {
            panic!("expected credentials command");
        };
        args
    }

    fn captcha_args(command: Command) -> CaptchaArgs {
        let Command::Captcha(args) = command else {
            panic!("expected captcha command");
        };
        args
    }

    fn artifacts_args(command: Command) -> ArtifactsArgs {
        let Command::Artifacts(args) = command else {
            panic!("expected artifacts command");
        };
        args
    }

    fn server_args(command: Command) -> ServerArgs {
        let Command::Server(args) = command else {
            panic!("expected server command");
        };
        args
    }

    fn create_session_args(command: SessionsCommand) -> ClientCreateSessionArgs {
        let SessionsCommand::Create(args) = command else {
            panic!("expected create subcommand");
        };
        args
    }

    fn pause_session_args(command: SessionsCommand) -> PauseSessionArgs {
        let SessionsCommand::Pause(args) = command else {
            panic!("expected pause subcommand");
        };
        args
    }

    fn wait_session_args(command: SessionsCommand) -> WaitSessionArgs {
        let SessionsCommand::Wait(args) = command else {
            panic!("expected wait subcommand");
        };
        args
    }

    fn sessions_credentials_args(command: SessionsCommand) -> CredentialsArgs {
        let SessionsCommand::Credentials(args) = command else {
            panic!("expected sessions credentials subcommand");
        };
        args
    }

    fn sessions_captcha_args(command: SessionsCommand) -> CaptchaArgs {
        let SessionsCommand::Captcha(args) = command else {
            panic!("expected sessions captcha subcommand");
        };
        args
    }

    fn report_captcha_args(command: CaptchaCommand) -> CaptchaReportArgs {
        let CaptchaCommand::Report(args) = command else {
            panic!("expected captcha report subcommand");
        };
        args
    }

    fn resolve_captcha_args(command: CaptchaCommand) -> CaptchaResolveArgs {
        let CaptchaCommand::Resolve(args) = command else {
            panic!("expected captcha resolve subcommand");
        };
        args
    }

    fn release_session_args(command: SessionsCommand) -> SessionIdArgs {
        let SessionsCommand::Release(args) = command else {
            panic!("expected release subcommand");
        };
        args
    }

    fn screenshot_session_args(command: SessionsCommand) -> ScreenshotArgs {
        let SessionsCommand::Screenshot(args) = command else {
            panic!("expected screenshot subcommand");
        };
        args
    }

    fn create_profile_args(command: ProfilesCommand) -> CreateProfileArgs {
        let ProfilesCommand::Create(args) = command else {
            panic!("expected create subcommand");
        };
        args
    }

    fn list_profile_args(command: ProfilesCommand) -> ClientArgs {
        let ProfilesCommand::List(args) = command else {
            panic!("expected list subcommand");
        };
        args
    }

    fn delete_profile_args(command: ProfilesCommand) -> ProfileIdArgs {
        let ProfilesCommand::Delete(args) = command else {
            panic!("expected delete subcommand");
        };
        args
    }

    fn approve_credential_args(command: CredentialsCommand) -> CredentialDecisionArgs {
        let CredentialsCommand::Approve(args) = command else {
            panic!("expected approve subcommand");
        };
        args
    }

    fn deny_credential_args(command: CredentialsCommand) -> CredentialDecisionArgs {
        let CredentialsCommand::Deny(args) = command else {
            panic!("expected deny subcommand");
        };
        args
    }

    fn privacy_guard_args(command: CredentialsCommand) -> CredentialPrivacyGuardArgs {
        let CredentialsCommand::PrivacyGuard(args) = command else {
            panic!("expected privacy-guard subcommand");
        };
        args
    }

    fn clear_privacy_guard_args(command: CredentialPrivacyGuardCommand) -> OperatorSessionIdArgs {
        match command {
            CredentialPrivacyGuardCommand::Clear(args) => args,
        }
    }

    fn env_lock() -> &'static Mutex<()> {
        static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
        LOCK.get_or_init(|| Mutex::new(()))
    }

    fn set_env_var<K, V>(key: K, value: V)
    where
        K: AsRef<OsStr>,
        V: AsRef<OsStr>,
    {
        unsafe { std::env::set_var(key, value) };
    }

    fn remove_env_var<K>(key: K)
    where
        K: AsRef<OsStr>,
    {
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
                ("HBR_OPERATOR_TOKEN", None),
                ("HBR_HEADFUL", None),
                ("HBR_HEADLESS", None),
                ("HBR_XVFB_RUN_PATH", None),
                ("HBR_TAKEOVER_TTL_SECS", None),
                ("HBR_CREDENTIAL_PROVIDER", None),
                ("HBR_CREDENTIAL_POLICY_PATH", None),
                ("HBR_OP_PATH", None),
                ("HBR_OP_TIMEOUT_SECS", None),
                ("HBR_CREDENTIAL_APPROVAL_TTL_SECS", None),
                ("HBR_CREDENTIAL_PRIVACY_GUARD", None),
                ("HBR_WEBRTC_IP_POLICY", None),
                ("HBR_GPU_POLICY", None),
                ("HBR_DEFAULT_CAPTCHA_POLICY", None),
                ("HBR_CAPTCHA_POLICY", None),
                ("HBR_CAPTCHA_SOLVER_ENABLED", None),
                ("HBR_CAPTCHA_SOLVER_POLICY_PATH", None),
                ("HBR_CAPTCHA_SOLVER_PROVIDER_ORDER", None),
                ("HBR_CAPTCHA_SOLVER_TIMEOUT_SECS", None),
                ("HBR_CAPTCHA_SOLVER_POLL_MS", None),
                ("HBR_CAPTCHA_SOLVER_VERIFY_TIMEOUT_SECS", None),
                ("HBR_CAPTCHA_SOLVER_MAX_ATTEMPTS", None),
                ("HBR_CAPTCHA_SOLVER_MAX_COST_USD_PER_SESSION", None),
                ("HBR_CAPSOLVER_API_KEY", None),
                ("HBR_2CAPTCHA_API_KEY", None),
                ("HBR_ANTI_CAPTCHA_API_KEY", None),
                ("HBR_ANTICAPTCHA_API_KEY", None),
                ("HBR_SERVER", None),
                ("DISPLAY", None),
                ("WAYLAND_DISPLAY", None),
            ],
            f,
        )
    }

    #[test]
    fn with_env_vars_restores_existing_values() {
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
    fn server_credential_provider_config_defaults_disabled_and_env_overrides() {
        with_clean_hbr_env(|| {
            let default_args = server_args(Cli::parse_from(["hbr", "server"]).command);
            let default_config =
                RuntimeConfig::from_server_args_with_environment(default_args, None, None, None);
            assert_eq!(
                default_config.credential_provider,
                CredentialBrokerMode::Disabled
            );
            assert!(default_config.credential_policy_path.is_none());
            assert_eq!(default_config.op_timeout, DEFAULT_OP_TIMEOUT);
            assert_eq!(
                default_config.credential_approval_ttl,
                DEFAULT_CREDENTIAL_APPROVAL_TTL
            );
            assert!(default_config.credential_privacy_guard);
        });

        with_env_vars(
            [
                ("HBR_CREDENTIAL_PROVIDER", Some("onepassword_cli")),
                (
                    "HBR_CREDENTIAL_POLICY_PATH",
                    Some("/tmp/private-policy.json"),
                ),
                ("HBR_OP_PATH", Some("/usr/bin/op")),
                ("HBR_OP_TIMEOUT_SECS", Some("7")),
                ("HBR_CREDENTIAL_APPROVAL_TTL_SECS", Some("11")),
                ("HBR_CREDENTIAL_PRIVACY_GUARD", Some("false")),
            ],
            || {
                let args = server_args(Cli::parse_from(["hbr", "server"]).command);
                let config =
                    RuntimeConfig::from_server_args_with_environment(args, None, None, None);
                assert_eq!(
                    config.credential_provider,
                    CredentialBrokerMode::OnePasswordCli
                );
                assert_eq!(
                    config.credential_policy_path.as_deref(),
                    Some(std::path::Path::new("/tmp/private-policy.json"))
                );
                assert_eq!(
                    config.op_path.as_deref(),
                    Some(std::path::Path::new("/usr/bin/op"))
                );
                assert_eq!(config.op_timeout, Duration::from_secs(7));
                assert_eq!(config.credential_approval_ttl, Duration::from_secs(11));
                assert!(!config.credential_privacy_guard);
            },
        );
    }

    fn command_named<'a>(command: &'a ClapCommand, name: &str) -> &'a ClapCommand {
        command
            .get_subcommands()
            .find(|subcommand| subcommand.get_name() == name)
            .unwrap_or_else(|| panic!("missing subcommand {name}"))
    }

    fn arg_named<'a>(command: &'a ClapCommand, id: &str) -> &'a clap::Arg {
        command
            .get_arguments()
            .find(|arg| arg.get_id().as_str() == id)
            .unwrap_or_else(|| panic!("missing arg {id}"))
    }

    #[test]
    fn command_extractors_reject_wrong_top_level_variants() {
        assert!(
            std::panic::catch_unwind(|| {
                sessions_args(Command::Server(ServerArgs {
                    bind: "127.0.0.1:7788".parse().unwrap(),
                    data_dir: None,
                    chrome_path: None,
                    bearer_token: None,
                    operator_token: None,
                    headful: false,
                    headless: false,
                    artifact_retention_secs: 604800,
                    takeover_ttl_secs: 900,
                    launch_timeout_secs: 15,
                    captcha_solver_enabled: false,
                    default_captcha_policy: CaptchaPolicy::HumanOnly,
                    captcha_solver_policy_path: None,
                    captcha_solver_provider_order: "capsolver".into(),
                    captcha_solver_timeout_secs: DEFAULT_CAPTCHA_SOLVER_TIMEOUT_SECS,
                    captcha_solver_poll_ms: DEFAULT_CAPTCHA_SOLVER_POLL_MS,
                    captcha_solver_verify_timeout_secs: DEFAULT_CAPTCHA_SOLVER_VERIFY_TIMEOUT_SECS,
                    captcha_solver_max_attempts: DEFAULT_CAPTCHA_SOLVER_MAX_ATTEMPTS,
                    captcha_solver_max_cost_usd_per_session:
                        DEFAULT_CAPTCHA_SOLVER_MAX_COST_USD_PER_SESSION,
                    credential_provider: Default::default(),
                    credential_policy_path: None,
                    op_path: None,
                    op_timeout_secs: 5,
                    credential_approval_ttl_secs: 300,
                    credential_privacy_guard: true,
                    webrtc_ip_policy: WebRtcIpPolicy::default(),
                    gpu_policy: GpuPolicy::default(),
                    default_locale: None,
                    default_accept_language: None,
                    default_timezone_id: None,
                    default_platform: None,
                    default_hardware_concurrency: DEFAULT_HARDWARE_CONCURRENCY,
                    default_device_memory_gb: DEFAULT_DEVICE_MEMORY_GB,
                    default_max_touch_points: DEFAULT_MAX_TOUCH_POINTS,
                }))
            })
            .is_err()
        );
        assert!(
            std::panic::catch_unwind(|| {
                profiles_args(Command::Server(ServerArgs {
                    bind: "127.0.0.1:7788".parse().unwrap(),
                    data_dir: None,
                    chrome_path: None,
                    bearer_token: None,
                    operator_token: None,
                    headful: false,
                    headless: false,
                    artifact_retention_secs: 604800,
                    takeover_ttl_secs: 900,
                    launch_timeout_secs: 15,
                    captcha_solver_enabled: false,
                    default_captcha_policy: CaptchaPolicy::HumanOnly,
                    captcha_solver_policy_path: None,
                    captcha_solver_provider_order: "capsolver".into(),
                    captcha_solver_timeout_secs: DEFAULT_CAPTCHA_SOLVER_TIMEOUT_SECS,
                    captcha_solver_poll_ms: DEFAULT_CAPTCHA_SOLVER_POLL_MS,
                    captcha_solver_verify_timeout_secs: DEFAULT_CAPTCHA_SOLVER_VERIFY_TIMEOUT_SECS,
                    captcha_solver_max_attempts: DEFAULT_CAPTCHA_SOLVER_MAX_ATTEMPTS,
                    captcha_solver_max_cost_usd_per_session:
                        DEFAULT_CAPTCHA_SOLVER_MAX_COST_USD_PER_SESSION,
                    credential_provider: Default::default(),
                    credential_policy_path: None,
                    op_path: None,
                    op_timeout_secs: 5,
                    credential_approval_ttl_secs: 300,
                    credential_privacy_guard: true,
                    webrtc_ip_policy: WebRtcIpPolicy::default(),
                    gpu_policy: GpuPolicy::default(),
                    default_locale: None,
                    default_accept_language: None,
                    default_timezone_id: None,
                    default_platform: None,
                    default_hardware_concurrency: DEFAULT_HARDWARE_CONCURRENCY,
                    default_device_memory_gb: DEFAULT_DEVICE_MEMORY_GB,
                    default_max_touch_points: DEFAULT_MAX_TOUCH_POINTS,
                }))
            })
            .is_err()
        );
        assert!(
            std::panic::catch_unwind(|| {
                artifacts_args(Command::Server(ServerArgs {
                    bind: "127.0.0.1:7788".parse().unwrap(),
                    data_dir: None,
                    chrome_path: None,
                    bearer_token: None,
                    operator_token: None,
                    headful: false,
                    headless: false,
                    artifact_retention_secs: 604800,
                    takeover_ttl_secs: 900,
                    launch_timeout_secs: 15,
                    captcha_solver_enabled: false,
                    default_captcha_policy: CaptchaPolicy::HumanOnly,
                    captcha_solver_policy_path: None,
                    captcha_solver_provider_order: "capsolver".into(),
                    captcha_solver_timeout_secs: DEFAULT_CAPTCHA_SOLVER_TIMEOUT_SECS,
                    captcha_solver_poll_ms: DEFAULT_CAPTCHA_SOLVER_POLL_MS,
                    captcha_solver_verify_timeout_secs: DEFAULT_CAPTCHA_SOLVER_VERIFY_TIMEOUT_SECS,
                    captcha_solver_max_attempts: DEFAULT_CAPTCHA_SOLVER_MAX_ATTEMPTS,
                    captcha_solver_max_cost_usd_per_session:
                        DEFAULT_CAPTCHA_SOLVER_MAX_COST_USD_PER_SESSION,
                    credential_provider: Default::default(),
                    credential_policy_path: None,
                    op_path: None,
                    op_timeout_secs: 5,
                    credential_approval_ttl_secs: 300,
                    credential_privacy_guard: true,
                    webrtc_ip_policy: WebRtcIpPolicy::default(),
                    gpu_policy: GpuPolicy::default(),
                    default_locale: None,
                    default_accept_language: None,
                    default_timezone_id: None,
                    default_platform: None,
                    default_hardware_concurrency: DEFAULT_HARDWARE_CONCURRENCY,
                    default_device_memory_gb: DEFAULT_DEVICE_MEMORY_GB,
                    default_max_touch_points: DEFAULT_MAX_TOUCH_POINTS,
                }))
            })
            .is_err()
        );
        assert!(
            std::panic::catch_unwind(|| {
                server_args(Command::Profiles(ProfilesArgs {
                    command: ProfilesCommand::List(ClientArgs {
                        server: "http://127.0.0.1:7788".into(),
                        bearer_token: None,
                    }),
                }))
            })
            .is_err()
        );
    }

    #[test]
    fn nested_command_extractors_reject_wrong_variants() {
        let client = ClientArgs {
            server: "http://127.0.0.1:7788".into(),
            bearer_token: None,
        };
        let session_id = Uuid::nil();

        assert!(
            std::panic::catch_unwind(|| create_session_args(SessionsCommand::List(client.clone())))
                .is_err()
        );
        assert!(
            std::panic::catch_unwind(|| {
                pause_session_args(SessionsCommand::Release(SessionIdArgs {
                    client: client.clone(),
                    session_id,
                }))
            })
            .is_err()
        );
        assert!(
            std::panic::catch_unwind(|| wait_session_args(SessionsCommand::List(client.clone())))
                .is_err()
        );
        assert!(
            std::panic::catch_unwind(|| {
                release_session_args(SessionsCommand::Create(ClientCreateSessionArgs {
                    client: client.clone(),
                    profile_id: None,
                    persist_profile: true,
                    headless: true,
                    headful: false,
                    launch_timeout_secs: None,
                    webrtc_ip_policy: None,
                    gpu_policy: None,
                    captcha_policy: None,
                }))
            })
            .is_err()
        );
        assert!(
            std::panic::catch_unwind(|| {
                screenshot_session_args(SessionsCommand::Pause(PauseSessionArgs {
                    client: client.clone(),
                    session_id,
                    reason: None,
                }))
            })
            .is_err()
        );
        assert!(
            std::panic::catch_unwind(|| create_profile_args(ProfilesCommand::List(client.clone())))
                .is_err()
        );
        assert!(
            std::panic::catch_unwind(|| {
                list_profile_args(ProfilesCommand::Delete(ProfileIdArgs {
                    client: client.clone(),
                    profile_id: "yura-main".into(),
                }))
            })
            .is_err()
        );
        assert!(
            std::panic::catch_unwind(|| {
                delete_profile_args(ProfilesCommand::Create(CreateProfileArgs {
                    client,
                    id: None,
                }))
            })
            .is_err()
        );
    }

    #[test]
    fn clap_metadata_helpers_reject_missing_items() {
        let cli = Cli::command();
        assert!(
            std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| command_named(
                &cli, "missing"
            )))
            .is_err()
        );

        let server = command_named(&cli, "server");
        assert!(
            std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| arg_named(
                server, "missing"
            )))
            .is_err()
        );
    }

    #[test]
    fn runtime_config_defaults_localhost_urls_and_data_dir_suffix() {
        let config = RuntimeConfig::from_server_args(ServerArgs {
            bind: "0.0.0.0:7788".parse().unwrap(),
            data_dir: None,
            chrome_path: Some(PathBuf::from("/tmp/chrome")),
            bearer_token: Some("secret".into()),
            operator_token: Some("operator-secret".into()),
            headful: true,
            headless: false,
            artifact_retention_secs: 3600,
            takeover_ttl_secs: 42,
            launch_timeout_secs: 17,
            captcha_solver_enabled: false,
            default_captcha_policy: CaptchaPolicy::HumanOnly,
            captcha_solver_policy_path: None,
            captcha_solver_provider_order: "capsolver".into(),
            captcha_solver_timeout_secs: DEFAULT_CAPTCHA_SOLVER_TIMEOUT_SECS,
            captcha_solver_poll_ms: DEFAULT_CAPTCHA_SOLVER_POLL_MS,
            captcha_solver_verify_timeout_secs: DEFAULT_CAPTCHA_SOLVER_VERIFY_TIMEOUT_SECS,
            captcha_solver_max_attempts: DEFAULT_CAPTCHA_SOLVER_MAX_ATTEMPTS,
            captcha_solver_max_cost_usd_per_session:
                DEFAULT_CAPTCHA_SOLVER_MAX_COST_USD_PER_SESSION,
            credential_provider: Default::default(),
            credential_policy_path: None,
            op_path: None,
            op_timeout_secs: 5,
            credential_approval_ttl_secs: 300,
            credential_privacy_guard: true,
            webrtc_ip_policy: WebRtcIpPolicy::DisableNonProxiedUdp,
            gpu_policy: GpuPolicy::Disable3d,
            default_locale: None,
            default_accept_language: None,
            default_timezone_id: None,
            default_platform: None,
            default_hardware_concurrency: DEFAULT_HARDWARE_CONCURRENCY,
            default_device_memory_gb: DEFAULT_DEVICE_MEMORY_GB,
            default_max_touch_points: DEFAULT_MAX_TOUCH_POINTS,
        });
        assert_eq!(config.localhost_base_url(), "http://127.0.0.1:7788");
        assert!(!config.default_headless);
        assert_eq!(
            config.default_webrtc_ip_policy,
            WebRtcIpPolicy::DisableNonProxiedUdp
        );
        assert_eq!(config.default_gpu_policy, GpuPolicy::Disable3d);
        assert_eq!(config.takeover_ttl, Duration::from_secs(42));
        assert_eq!(config.chrome_path, Some(PathBuf::from("/tmp/chrome")));
        assert_eq!(config.bearer_token.as_deref(), Some("secret"));
        assert_eq!(config.operator_token.as_deref(), Some("operator-secret"));

        let ipv6 = RuntimeConfig {
            bind: "[::1]:8899".parse().unwrap(),
            data_dir: PathBuf::from("/tmp/runtime"),
            chrome_path: None,
            bearer_token: None,
            operator_token: None,
            default_headless: true,
            default_webrtc_ip_policy: WebRtcIpPolicy::default(),
            default_gpu_policy: GpuPolicy::default(),
            default_persona: BrowserPersona::default(),
            artifact_retention: Duration::from_secs(60),
            takeover_ttl: Duration::from_secs(60),
            launch_timeout: Duration::from_secs(15),
            captcha_solver_enabled: false,
            default_captcha_policy: CaptchaPolicy::HumanOnly,
            captcha_solver_policy_path: None,
            captcha_solver_provider_order: "capsolver".into(),
            captcha_solver_timeout: Duration::from_secs(DEFAULT_CAPTCHA_SOLVER_TIMEOUT_SECS),
            captcha_solver_poll_interval: Duration::from_millis(DEFAULT_CAPTCHA_SOLVER_POLL_MS),
            captcha_solver_verify_timeout: Duration::from_secs(
                DEFAULT_CAPTCHA_SOLVER_VERIFY_TIMEOUT_SECS,
            ),
            captcha_solver_max_attempts: DEFAULT_CAPTCHA_SOLVER_MAX_ATTEMPTS,
            captcha_solver_max_cost_usd_per_session:
                DEFAULT_CAPTCHA_SOLVER_MAX_COST_USD_PER_SESSION,
            captcha_solver_provider_key_available: false,
            credential_provider: Default::default(),
            credential_policy_path: None,
            op_path: None,
            op_timeout: Duration::from_secs(5),
            credential_approval_ttl: Duration::from_secs(300),
            credential_privacy_guard: true,
        };
        assert_eq!(ipv6.localhost_base_url(), "http://[::1]:8899");

        let private_ipv4 = RuntimeConfig {
            bind: "192.168.10.20:9900".parse().unwrap(),
            data_dir: PathBuf::from("/tmp/runtime"),
            chrome_path: None,
            bearer_token: None,
            operator_token: None,
            default_headless: true,
            default_webrtc_ip_policy: WebRtcIpPolicy::default(),
            default_gpu_policy: GpuPolicy::default(),
            default_persona: BrowserPersona::default(),
            artifact_retention: Duration::from_secs(60),
            takeover_ttl: Duration::from_secs(60),
            launch_timeout: Duration::from_secs(15),
            captcha_solver_enabled: false,
            default_captcha_policy: CaptchaPolicy::HumanOnly,
            captcha_solver_policy_path: None,
            captcha_solver_provider_order: "capsolver".into(),
            captcha_solver_timeout: Duration::from_secs(DEFAULT_CAPTCHA_SOLVER_TIMEOUT_SECS),
            captcha_solver_poll_interval: Duration::from_millis(DEFAULT_CAPTCHA_SOLVER_POLL_MS),
            captcha_solver_verify_timeout: Duration::from_secs(
                DEFAULT_CAPTCHA_SOLVER_VERIFY_TIMEOUT_SECS,
            ),
            captcha_solver_max_attempts: DEFAULT_CAPTCHA_SOLVER_MAX_ATTEMPTS,
            captcha_solver_max_cost_usd_per_session:
                DEFAULT_CAPTCHA_SOLVER_MAX_COST_USD_PER_SESSION,
            captcha_solver_provider_key_available: false,
            credential_provider: Default::default(),
            credential_policy_path: None,
            op_path: None,
            op_timeout: Duration::from_secs(5),
            credential_approval_ttl: Duration::from_secs(300),
            credential_privacy_guard: true,
        };
        assert_eq!(
            private_ipv4.localhost_base_url(),
            "http://192.168.10.20:9900"
        );
        assert!(default_data_dir().ends_with("hermes-browser-runtime"));
        assert_eq!(
            default_data_dir_from(None),
            PathBuf::from(".").join("hermes-browser-runtime")
        );
    }

    #[test]
    fn parses_server_command_defaults() {
        with_clean_hbr_env(|| {
            let cli = Cli::try_parse_from(["hermes-browser-runtime", "server"])
                .expect("server command should parse");

            let args = server_args(cli.command);
            assert_eq!(args.bind, "127.0.0.1:7788".parse().unwrap());
            assert!(args.data_dir.is_none());
            assert!(args.chrome_path.is_none());
            assert!(args.bearer_token.is_none());
            assert!(args.operator_token.is_none());
            assert!(!args.headful);
            assert!(!args.headless);
            assert_eq!(args.takeover_ttl_secs, 900);
            assert_eq!(
                args.webrtc_ip_policy,
                WebRtcIpPolicy::DefaultPublicInterfaceOnly
            );
            assert_eq!(args.gpu_policy, GpuPolicy::Auto);
            assert_eq!(args.default_hardware_concurrency, 8);
            assert_eq!(args.default_device_memory_gb, 8);
            assert_eq!(args.default_max_touch_points, 0);
        });
    }

    #[test]
    fn default_persona_reads_hardware_device_defaults_from_server_args() {
        with_env_vars(
            [
                ("HBR_DEFAULT_HARDWARE_CONCURRENCY", Some("4")),
                ("HBR_DEFAULT_DEVICE_MEMORY_GB", Some("4")),
                ("HBR_DEFAULT_MAX_TOUCH_POINTS", Some("5")),
                ("HBR_DEFAULT_LOCALE", Some("pt-PT")),
                (
                    "HBR_DEFAULT_ACCEPT_LANGUAGE",
                    Some("pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7"),
                ),
                ("HBR_DEFAULT_TIMEZONE_ID", Some("Europe/Lisbon")),
                ("HBR_DEFAULT_PLATFORM", Some("Linux x86_64")),
            ],
            || {
                let cli = Cli::try_parse_from(["hermes-browser-runtime", "server"])
                    .expect("server command should parse hardware persona env bindings");
                let args = server_args(cli.command);
                assert_eq!(args.default_hardware_concurrency, 4);
                assert_eq!(args.default_device_memory_gb, 4);
                assert_eq!(args.default_max_touch_points, 5);

                let config =
                    RuntimeConfig::from_server_args_with_environment(args, None, None, None);
                assert_eq!(config.default_persona.hardware_concurrency, 4);
                assert_eq!(config.default_persona.device_memory_gb, 4);
                assert_eq!(config.default_persona.max_touch_points, 5);
                assert_eq!(config.default_persona.normalized_hardware_concurrency(), 4);
                assert_eq!(config.default_persona.normalized_device_memory_gb(), 4);
                assert_eq!(config.default_persona.normalized_max_touch_points(), 5);
            },
        );
    }

    #[test]
    fn parses_server_launch_timeout_flag_into_runtime_config() {
        with_clean_hbr_env(|| {
            let cli = Cli::try_parse_from([
                "hermes-browser-runtime",
                "server",
                "--launch-timeout-secs",
                "21",
            ])
            .expect("server launch timeout flag should parse");

            let args = server_args(cli.command);
            assert_eq!(args.launch_timeout_secs, 21);

            let config = RuntimeConfig::from_server_args(args);
            assert_eq!(config.launch_timeout, Duration::from_secs(21));
        });
    }

    #[test]
    fn runtime_config_captcha_solver_defaults_disabled_and_accepts_env_overrides() {
        with_clean_hbr_env(|| {
            let cli = Cli::try_parse_from(["hermes-browser-runtime", "server"])
                .expect("server command should parse");
            let config = RuntimeConfig::from_server_args_with_environment(
                server_args(cli.command),
                None,
                None,
                None,
            );

            assert!(!config.captcha_solver_enabled);
            assert_eq!(config.default_captcha_policy, CaptchaPolicy::HumanOnly);
            assert!(config.captcha_solver_policy_path.is_none());
            assert_eq!(config.captcha_solver_provider_order, "capsolver");
            assert_eq!(config.captcha_solver_timeout, Duration::from_secs(120));
            assert_eq!(
                config.captcha_solver_poll_interval,
                Duration::from_millis(3000)
            );
            assert_eq!(
                config.captcha_solver_verify_timeout,
                Duration::from_secs(20)
            );
            assert_eq!(config.captcha_solver_max_attempts, 2);
            assert!((config.captcha_solver_max_cost_usd_per_session - 0.25).abs() < f64::EPSILON);
            assert!(!config.captcha_solver_provider_key_available);
        });

        with_env_vars(
            [
                ("HBR_CAPTCHA_SOLVER_ENABLED", Some("true")),
                ("HBR_DEFAULT_CAPTCHA_POLICY", Some("auto-solve")),
                (
                    "HBR_CAPTCHA_SOLVER_POLICY_PATH",
                    Some("/tmp/hbr-captcha-policy.json"),
                ),
                (
                    "HBR_CAPTCHA_SOLVER_PROVIDER_ORDER",
                    Some("capsolver,2captcha"),
                ),
                ("HBR_CAPTCHA_SOLVER_TIMEOUT_SECS", Some("9")),
                ("HBR_CAPTCHA_SOLVER_POLL_MS", Some("250")),
                ("HBR_CAPTCHA_SOLVER_VERIFY_TIMEOUT_SECS", Some("4")),
                ("HBR_CAPTCHA_SOLVER_MAX_ATTEMPTS", Some("1")),
                ("HBR_CAPTCHA_SOLVER_MAX_COST_USD_PER_SESSION", Some("0.10")),
                ("HBR_ANTI_CAPTCHA_API_KEY", Some("present")),
            ],
            || {
                let cli = Cli::try_parse_from(["hermes-browser-runtime", "server"])
                    .expect("server command should parse captcha solver env bindings");
                let args = server_args(cli.command);
                assert!(args.captcha_solver_enabled);
                assert_eq!(args.default_captcha_policy, CaptchaPolicy::AutoSolve);
                assert_eq!(
                    args.captcha_solver_policy_path,
                    Some(PathBuf::from("/tmp/hbr-captcha-policy.json"))
                );
                assert_eq!(args.captcha_solver_provider_order, "capsolver,2captcha");
                assert_eq!(args.captcha_solver_timeout_secs, 9);
                assert_eq!(args.captcha_solver_poll_ms, 250);
                assert_eq!(args.captcha_solver_verify_timeout_secs, 4);
                assert_eq!(args.captcha_solver_max_attempts, 1);
                assert!((args.captcha_solver_max_cost_usd_per_session - 0.10).abs() < f64::EPSILON);

                let config =
                    RuntimeConfig::from_server_args_with_environment(args, None, None, None);
                assert!(config.captcha_solver_enabled);
                assert_eq!(config.default_captcha_policy, CaptchaPolicy::AutoSolve);
                assert_eq!(config.captcha_solver_timeout, Duration::from_secs(9));
                assert_eq!(
                    config.captcha_solver_poll_interval,
                    Duration::from_millis(250)
                );
                assert_eq!(config.captcha_solver_verify_timeout, Duration::from_secs(4));
                assert!(config.captcha_solver_provider_key_available);
            },
        );
    }

    #[test]
    fn runtime_config_from_default_server_args_keeps_local_private_defaults() {
        with_clean_hbr_env(|| {
            let cli = Cli::try_parse_from(["hermes-browser-runtime", "server"])
                .expect("server command should parse");

            let config = RuntimeConfig::from_server_args_with_environment(
                server_args(cli.command),
                None,
                None,
                None,
            );
            assert_eq!(config.bind, "127.0.0.1:7788".parse().unwrap());
            assert_eq!(config.localhost_base_url(), "http://127.0.0.1:7788");
            assert!(config.default_headless);
            assert_eq!(config.artifact_retention, Duration::from_secs(604800));
            assert_eq!(config.takeover_ttl, Duration::from_secs(900));
            assert_eq!(
                config.default_webrtc_ip_policy,
                WebRtcIpPolicy::DefaultPublicInterfaceOnly
            );
            assert_eq!(config.default_gpu_policy, GpuPolicy::Auto);
            assert!(config.chrome_path.is_none());
            assert!(config.bearer_token.is_none());
            assert!(config.operator_token.is_none());
        });
    }

    #[test]
    fn runtime_config_default_browser_mode_prefers_headed_when_display_or_xvfb_exists() {
        assert!(default_headless_for_environment(
            false, false, None, None, None
        ));
        assert!(!default_headless_for_environment(
            false,
            false,
            Some(OsString::from(":99")),
            None,
            None,
        ));
        assert!(!default_headless_for_environment(
            false,
            false,
            None,
            Some(OsString::from("wayland-0")),
            None,
        ));
        assert!(!default_headless_for_environment(
            false,
            false,
            None,
            None,
            Some(PathBuf::from("/usr/bin/xvfb-run")),
        ));
        assert!(default_headless_for_environment(
            true,
            false,
            Some(OsString::from(":99")),
            None,
            Some(PathBuf::from("/usr/bin/xvfb-run")),
        ));
        assert!(!default_headless_for_environment(
            false, true, None, None, None
        ));
    }

    #[test]
    fn parses_server_command_env_bindings() {
        with_env_vars(
            [
                ("HBR_BIND", Some("127.0.0.1:8899")),
                ("HBR_DATA_DIR", Some("/tmp/hbr-data")),
                ("HBR_CHROME_PATH", Some("/tmp/chrome-bin")),
                ("HBR_BEARER_TOKEN", Some("env-secret")),
                ("HBR_OPERATOR_TOKEN", Some("env-operator-secret")),
                ("HBR_HEADFUL", Some("true")),
                ("HBR_HEADLESS", None),
                ("HBR_ARTIFACT_RETENTION_SECS", Some("3600")),
                ("HBR_TAKEOVER_TTL_SECS", Some("42")),
                ("HBR_LAUNCH_TIMEOUT_SECS", Some("33")),
                ("HBR_WEBRTC_IP_POLICY", Some("disable_non_proxied_udp")),
                ("HBR_GPU_POLICY", Some("swiftshader_compat")),
            ],
            || {
                let cli = Cli::try_parse_from(["hermes-browser-runtime", "server"])
                    .expect("server command should parse env bindings");

                let args = server_args(cli.command);
                assert_eq!(args.bind, "127.0.0.1:8899".parse().unwrap());
                assert_eq!(args.data_dir, Some(PathBuf::from("/tmp/hbr-data")));
                assert_eq!(args.chrome_path, Some(PathBuf::from("/tmp/chrome-bin")));
                assert_eq!(args.bearer_token.as_deref(), Some("env-secret"));
                assert_eq!(args.operator_token.as_deref(), Some("env-operator-secret"));
                assert!(args.headful);
                assert!(!args.headless);
                assert_eq!(args.artifact_retention_secs, 3600);
                assert_eq!(args.takeover_ttl_secs, 42);
                assert_eq!(args.launch_timeout_secs, 33);
                assert_eq!(args.webrtc_ip_policy, WebRtcIpPolicy::DisableNonProxiedUdp);
                assert_eq!(args.gpu_policy, GpuPolicy::SwiftshaderCompat);

                let config = RuntimeConfig::from_server_args(args);
                assert_eq!(config.localhost_base_url(), "http://127.0.0.1:8899");
                assert_eq!(config.data_dir, PathBuf::from("/tmp/hbr-data"));
                assert_eq!(config.chrome_path, Some(PathBuf::from("/tmp/chrome-bin")));
                assert_eq!(config.bearer_token.as_deref(), Some("env-secret"));
                assert_eq!(
                    config.operator_token.as_deref(),
                    Some("env-operator-secret")
                );
                assert!(!config.default_headless);
                assert_eq!(config.artifact_retention, Duration::from_secs(3600));
                assert_eq!(config.takeover_ttl, Duration::from_secs(42));
                assert_eq!(config.launch_timeout, Duration::from_secs(33));
                assert_eq!(
                    config.default_webrtc_ip_policy,
                    WebRtcIpPolicy::DisableNonProxiedUdp
                );
                assert_eq!(config.default_gpu_policy, GpuPolicy::SwiftshaderCompat);
            },
        );
    }

    #[test]
    fn rejects_invalid_server_env_and_flag_values() {
        with_env_vars([("HBR_TAKEOVER_TTL_SECS", Some("not-a-number"))], || {
            assert!(Cli::try_parse_from(["hermes-browser-runtime", "server"]).is_err());
        });

        assert!(
            Cli::try_parse_from(["hermes-browser-runtime", "server", "--bind", "not-an-addr"])
                .is_err()
        );
    }

    #[test]
    fn clap_metadata_exposes_server_env_and_defaults() {
        let cli = Cli::command();
        let server = command_named(&cli, "server");

        let bind = arg_named(server, "bind");
        assert_eq!(bind.get_env(), Some(OsStr::new("HBR_BIND")));
        assert_eq!(bind.get_default_values(), &[OsStr::new("127.0.0.1:7788")]);

        let data_dir = arg_named(server, "data_dir");
        assert_eq!(data_dir.get_env(), Some(OsStr::new("HBR_DATA_DIR")));

        let chrome_path = arg_named(server, "chrome_path");
        assert_eq!(chrome_path.get_env(), Some(OsStr::new("HBR_CHROME_PATH")));

        let bearer_token = arg_named(server, "bearer_token");
        assert_eq!(bearer_token.get_env(), Some(OsStr::new("HBR_BEARER_TOKEN")));

        let headful = arg_named(server, "headful");
        assert_eq!(headful.get_env(), Some(OsStr::new("HBR_HEADFUL")));
        assert_eq!(headful.get_default_values(), &[OsStr::new("false")]);

        let headless = arg_named(server, "headless");
        assert_eq!(headless.get_env(), Some(OsStr::new("HBR_HEADLESS")));
        assert_eq!(headless.get_default_values(), &[OsStr::new("false")]);

        let artifact_retention_secs = arg_named(server, "artifact_retention_secs");
        assert_eq!(
            artifact_retention_secs.get_env(),
            Some(OsStr::new("HBR_ARTIFACT_RETENTION_SECS"))
        );
        assert_eq!(
            artifact_retention_secs.get_default_values(),
            &[OsStr::new("604800")]
        );

        let takeover_ttl_secs = arg_named(server, "takeover_ttl_secs");
        assert_eq!(
            takeover_ttl_secs.get_env(),
            Some(OsStr::new("HBR_TAKEOVER_TTL_SECS"))
        );
        assert_eq!(takeover_ttl_secs.get_default_values(), &[OsStr::new("900")]);

        let launch_timeout_secs = arg_named(server, "launch_timeout_secs");
        assert_eq!(
            launch_timeout_secs.get_env(),
            Some(OsStr::new("HBR_LAUNCH_TIMEOUT_SECS"))
        );
        assert_eq!(
            launch_timeout_secs.get_default_values(),
            &[OsStr::new("15")]
        );

        let webrtc_ip_policy = arg_named(server, "webrtc_ip_policy");
        assert_eq!(
            webrtc_ip_policy.get_env(),
            Some(OsStr::new("HBR_WEBRTC_IP_POLICY"))
        );
        assert_eq!(
            webrtc_ip_policy.get_default_values(),
            &[OsStr::new("default_public_interface_only")]
        );

        let gpu_policy = arg_named(server, "gpu_policy");
        assert_eq!(gpu_policy.get_env(), Some(OsStr::new("HBR_GPU_POLICY")));
        assert_eq!(gpu_policy.get_default_values(), &[OsStr::new("auto")]);
    }

    #[test]
    fn clap_metadata_exposes_client_env_bindings_on_nested_commands() {
        let cli = Cli::command();

        let sessions = command_named(&cli, "sessions");
        let pause = command_named(sessions, "pause");
        let session_server = arg_named(pause, "server");
        assert_eq!(session_server.get_env(), Some(OsStr::new("HBR_SERVER")));
        assert_eq!(
            session_server.get_default_values(),
            &[OsStr::new("http://127.0.0.1:7788")]
        );
        let session_token = arg_named(pause, "bearer_token");
        assert_eq!(
            session_token.get_env(),
            Some(OsStr::new("HBR_BEARER_TOKEN"))
        );

        let create = command_named(sessions, "create");
        assert_eq!(
            arg_named(create, "webrtc_ip_policy").get_env(),
            Some(OsStr::new("HBR_WEBRTC_IP_POLICY"))
        );
        assert_eq!(
            arg_named(create, "gpu_policy").get_env(),
            Some(OsStr::new("HBR_GPU_POLICY"))
        );
        assert_eq!(
            arg_named(create, "captcha_policy").get_env(),
            Some(OsStr::new("HBR_CAPTCHA_POLICY"))
        );

        let profiles = command_named(&cli, "profiles");
        let profile_list = command_named(profiles, "list");
        assert_eq!(
            arg_named(profile_list, "server").get_env(),
            Some(OsStr::new("HBR_SERVER"))
        );
        assert_eq!(
            arg_named(profile_list, "bearer_token").get_env(),
            Some(OsStr::new("HBR_BEARER_TOKEN"))
        );

        let artifacts = command_named(&cli, "artifacts");
        let artifact_list = command_named(artifacts, "list");
        assert_eq!(
            arg_named(artifact_list, "server").get_env(),
            Some(OsStr::new("HBR_SERVER"))
        );
        assert_eq!(
            arg_named(artifact_list, "bearer_token").get_env(),
            Some(OsStr::new("HBR_BEARER_TOKEN"))
        );
    }

    #[test]
    fn parses_nested_client_env_bindings() {
        with_env_vars(
            [
                ("HBR_SERVER", Some("http://127.0.0.1:8899")),
                ("HBR_BEARER_TOKEN", Some("env-client-token")),
            ],
            || {
                let session_id = Uuid::new_v4();
                let cli = Cli::try_parse_from([
                    "hermes-browser-runtime",
                    "sessions",
                    "release",
                    &session_id.to_string(),
                ])
                .expect("sessions release should parse nested env bindings");
                let args = sessions_args(cli.command);
                let args = release_session_args(args.command);
                assert_eq!(args.session_id, session_id);
                assert_eq!(args.client.server, "http://127.0.0.1:8899");
                assert_eq!(
                    args.client.bearer_token.as_deref(),
                    Some("env-client-token")
                );

                let cli = Cli::try_parse_from(["hermes-browser-runtime", "profiles", "list"])
                    .expect("profiles list should parse nested env bindings");
                let args = profiles_args(cli.command);
                let args = list_profile_args(args.command);
                assert_eq!(args.server, "http://127.0.0.1:8899");
                assert_eq!(args.bearer_token.as_deref(), Some("env-client-token"));
            },
        );
    }

    #[test]
    fn parses_credentials_singular_alias_notes_and_privacy_guard_clear() {
        with_clean_hbr_env(|| {
            let session_id = Uuid::new_v4();
            let request_id = Uuid::new_v4();
            let cli = Cli::try_parse_from([
                "hermes-browser-runtime",
                "credential",
                "approve",
                &session_id.to_string(),
                &request_id.to_string(),
                "--note",
                "approved after human review",
            ])
            .expect("singular credential alias should parse approve note");
            let args = credentials_args(cli.command);
            let args = approve_credential_args(args.command);
            assert_eq!(args.session_id, session_id);
            assert_eq!(args.request_id, request_id);
            assert_eq!(args.note.as_deref(), Some("approved after human review"));

            let cli = Cli::try_parse_from([
                "hermes-browser-runtime",
                "credentials",
                "privacy-guard",
                "clear",
                &session_id.to_string(),
            ])
            .expect("credentials privacy-guard clear should parse");
            let args = credentials_args(cli.command);
            let args = privacy_guard_args(args.command);
            let args = clear_privacy_guard_args(args.command);
            assert_eq!(args.session_id, session_id);
        });
    }

    #[test]
    fn parses_sessions_credentials_contract_aliases_and_reason() {
        with_clean_hbr_env(|| {
            let session_id = Uuid::new_v4();
            let request_id = Uuid::new_v4();

            let request = Cli::try_parse_from([
                "hermes-browser-runtime",
                "sessions",
                "credentials",
                "request",
                &session_id.to_string(),
                "--alias",
                "demo-login",
                "--username-selector",
                "#user",
                "--password-selector",
                "#pass",
            ])
            .expect("sessions credentials request should parse as credential fill");
            let args = sessions_args(request.command);
            let args = sessions_credentials_args(args.command);
            let CredentialsCommand::Fill(fill_args) = args.command else {
                panic!("expected request alias to parse as fill");
            };
            assert_eq!(fill_args.session_id, session_id);
            assert_eq!(fill_args.alias, "demo-login");
            assert_eq!(fill_args.username_selector.as_deref(), Some("#user"));
            assert_eq!(fill_args.password_selector.as_deref(), Some("#pass"));

            let deny = Cli::try_parse_from([
                "hermes-browser-runtime",
                "sessions",
                "credentials",
                "deny",
                &session_id.to_string(),
                &request_id.to_string(),
                "--reason",
                "operator denied",
            ])
            .expect("sessions credentials deny should accept --reason");
            let args = sessions_args(deny.command);
            let args = sessions_credentials_args(args.command);
            let args = deny_credential_args(args.command);
            assert_eq!(args.session_id, session_id);
            assert_eq!(args.request_id, request_id);
            assert_eq!(args.note.as_deref(), Some("operator denied"));

            let clear = Cli::try_parse_from([
                "hermes-browser-runtime",
                "sessions",
                "credentials",
                "clear-privacy-guard",
                &session_id.to_string(),
            ])
            .expect("sessions credentials clear-privacy-guard should parse");
            let args = sessions_args(clear.command);
            let args = sessions_credentials_args(args.command);
            assert!(matches!(
                args.command,
                CredentialsCommand::ClearPrivacyGuard(_)
            ));
        });
    }

    #[test]
    fn parses_captcha_report_and_resolve_commands() {
        with_clean_hbr_env(|| {
            let session_id = Uuid::new_v4();

            let report = Cli::try_parse_from([
                "hermes-browser-runtime",
                "sessions",
                "captcha",
                "report",
                &session_id.to_string(),
                "--state",
                "in-progress",
                "--challenge-type",
                "turnstile",
                "--reason",
                "operator started",
                "--server",
                "http://127.0.0.1:8899",
            ])
            .expect("sessions captcha report should parse");
            let args = sessions_args(report.command);
            let args = sessions_captcha_args(args.command);
            let args = report_captcha_args(args.command);
            assert_eq!(args.session_id, session_id);
            assert_eq!(args.state, CaptchaReportState::InProgress);
            assert_eq!(args.challenge_type.as_deref(), Some("turnstile"));
            assert_eq!(args.reason.as_deref(), Some("operator started"));
            assert_eq!(args.client.server, "http://127.0.0.1:8899");

            let resolve = Cli::try_parse_from([
                "hermes-browser-runtime",
                "captcha",
                "resolve",
                &session_id.to_string(),
                "--outcome",
                "dismissed",
                "--note",
                "operator skipped",
            ])
            .expect("top-level captcha resolve should parse");
            let args = captcha_args(resolve.command);
            let args = resolve_captcha_args(args.command);
            assert_eq!(args.session_id, session_id);
            assert_eq!(args.outcome, CaptchaResolveOutcome::Dismissed);
            assert_eq!(args.note.as_deref(), Some("operator skipped"));
        });
    }

    #[test]
    fn parses_nested_sessions_create_command() {
        with_clean_hbr_env(|| {
            let cli = Cli::try_parse_from([
                "hermes-browser-runtime",
                "sessions",
                "create",
                "--profile-id",
                "yura-main",
            ])
            .expect("sessions create should parse");

            let args = sessions_args(cli.command);
            let args = create_session_args(args.command);
            assert_eq!(args.profile_id.as_deref(), Some("yura-main"));
            assert!(args.persist_profile);
            assert!(!args.headless);
            assert!(!args.headful);
            assert_eq!(args.launch_timeout_secs, None);

            let cli = Cli::try_parse_from([
                "hermes-browser-runtime",
                "sessions",
                "create",
                "--profile-id",
                "yura-main",
                "--launch-timeout-secs",
                "9",
                "--webrtc-ip-policy",
                "disable_non_proxied_udp",
                "--gpu-policy",
                "swiftshader_compat",
                "--captcha-policy",
                "observe-only",
            ])
            .expect("sessions create should parse launch timeout and browser-policy overrides");

            let args = sessions_args(cli.command);
            let args = create_session_args(args.command);
            assert_eq!(args.profile_id.as_deref(), Some("yura-main"));
            assert_eq!(args.launch_timeout_secs, Some(9));
            assert_eq!(
                args.webrtc_ip_policy,
                Some(WebRtcIpPolicy::DisableNonProxiedUdp)
            );
            assert_eq!(args.gpu_policy, Some(GpuPolicy::SwiftshaderCompat));
            assert_eq!(args.captcha_policy, Some(CaptchaPolicy::ObserveOnly));
        });
    }

    #[test]
    fn parses_nested_sessions_pause_command() {
        with_clean_hbr_env(|| {
            let session_id = Uuid::new_v4();
            let cli = Cli::try_parse_from([
                "hermes-browser-runtime",
                "sessions",
                "pause",
                &session_id.to_string(),
                "--reason",
                "oauth approval required",
                "--server",
                "http://127.0.0.1:8899",
            ])
            .expect("sessions pause should parse");

            let args = sessions_args(cli.command);
            let args = pause_session_args(args.command);
            assert_eq!(args.session_id, session_id);
            assert_eq!(args.reason.as_deref(), Some("oauth approval required"));
            assert_eq!(args.client.server, "http://127.0.0.1:8899");
        });
    }

    #[test]
    fn parses_nested_sessions_wait_command() {
        with_clean_hbr_env(|| {
            let session_id = Uuid::new_v4();
            let cli = Cli::try_parse_from([
                "hermes-browser-runtime",
                "sessions",
                "wait",
                &session_id.to_string(),
                "--timeout-secs",
                "42",
                "--server",
                "http://127.0.0.1:8899",
            ])
            .expect("sessions wait should parse");

            let args = sessions_args(cli.command);
            let args = wait_session_args(args.command);
            assert_eq!(args.session_id, session_id);
            assert_eq!(args.timeout_secs, 42);
            assert_eq!(args.client.server, "http://127.0.0.1:8899");
        });
    }

    #[test]
    fn parses_nested_sessions_release_and_screenshot_commands() {
        with_clean_hbr_env(|| {
            let session_id = Uuid::new_v4();
            let cli = Cli::try_parse_from([
                "hermes-browser-runtime",
                "sessions",
                "release",
                &session_id.to_string(),
            ])
            .expect("sessions release should parse");

            let args = sessions_args(cli.command);
            let args = release_session_args(args.command);
            assert_eq!(args.session_id, session_id);
            assert_eq!(args.client.server, "http://127.0.0.1:7788");

            let cli = Cli::try_parse_from([
                "hermes-browser-runtime",
                "sessions",
                "screenshot",
                &session_id.to_string(),
                "--output",
                "/tmp/shot.png",
            ])
            .expect("sessions screenshot should parse");

            let args = sessions_args(cli.command);
            let args = screenshot_session_args(args.command);
            assert_eq!(args.session_id, session_id);
            assert_eq!(args.output, Some(PathBuf::from("/tmp/shot.png")));
        });
    }

    #[test]
    fn parses_credential_commands() {
        with_clean_hbr_env(|| {
            let session_id = Uuid::new_v4();
            let request_id = Uuid::new_v4();
            let fill = Cli::try_parse_from([
                "hermes-browser-runtime",
                "credentials",
                "fill",
                &session_id.to_string(),
                "--alias",
                "demo-login",
                "--username-selector",
                "#user",
                "--password-selector",
                "#pass",
                "--expected-origin",
                "https://example.test",
                "--purpose",
                "login",
            ])
            .expect("credential fill command should parse");
            let args = credentials_args(fill.command);
            let CredentialsCommand::Fill(fill_args) = args.command else {
                panic!("expected fill subcommand");
            };
            assert_eq!(fill_args.session_id, session_id);
            assert_eq!(fill_args.alias, "demo-login");
            assert_eq!(fill_args.username_selector.as_deref(), Some("#user"));
            assert_eq!(fill_args.password_selector.as_deref(), Some("#pass"));
            assert_eq!(
                fill_args.expected_origin.as_deref(),
                Some("https://example.test")
            );
            assert_eq!(fill_args.purpose.as_deref(), Some("login"));

            let status = Cli::try_parse_from([
                "hermes-browser-runtime",
                "credentials",
                "status",
                &session_id.to_string(),
                &request_id.to_string(),
            ])
            .expect("credential status command should parse");
            let args = credentials_args(status.command);
            let CredentialsCommand::Status(status_args) = args.command else {
                panic!("expected status subcommand");
            };
            assert_eq!(status_args.session_id, session_id);
            assert_eq!(status_args.request_id, request_id);

            let clear = Cli::try_parse_from([
                "hermes-browser-runtime",
                "credentials",
                "clear-guard",
                &session_id.to_string(),
            ])
            .expect("credential clear-guard command should parse");
            let args = credentials_args(clear.command);
            assert!(matches!(args.command, CredentialsCommand::ClearGuard(_)));
        });
    }

    #[test]
    fn parses_nested_profiles_delete_command() {
        with_clean_hbr_env(|| {
            let cli =
                Cli::try_parse_from(["hermes-browser-runtime", "profiles", "delete", "yura-main"])
                    .expect("profiles delete should parse");

            let args = profiles_args(cli.command);
            let args = delete_profile_args(args.command);
            assert_eq!(args.profile_id, "yura-main");
        });
    }

    #[test]
    fn parses_nested_profiles_create_and_list_commands() {
        with_clean_hbr_env(|| {
            let cli = Cli::try_parse_from([
                "hermes-browser-runtime",
                "profiles",
                "create",
                "--id",
                "yura-main",
            ])
            .expect("profiles create should parse");

            let args = profiles_args(cli.command);
            let args = create_profile_args(args.command);
            assert_eq!(args.id.as_deref(), Some("yura-main"));
            assert_eq!(args.client.server, "http://127.0.0.1:7788");

            let cli = Cli::try_parse_from(["hermes-browser-runtime", "profiles", "list"])
                .expect("profiles list should parse");
            let args = profiles_args(cli.command);
            let args = list_profile_args(args.command);
            assert_eq!(args.server, "http://127.0.0.1:7788");
            assert!(args.bearer_token.is_none());
        });
    }

    #[test]
    fn parses_nested_artifacts_list_command() {
        with_clean_hbr_env(|| {
            let session_id = Uuid::new_v4();
            let cli = Cli::try_parse_from([
                "hermes-browser-runtime",
                "artifacts",
                "list",
                &session_id.to_string(),
            ])
            .expect("artifacts list should parse");

            let args = artifacts_args(cli.command);
            let ArtifactsCommand::List(args) = args.command else {
                panic!("expected artifacts list command");
            };
            assert_eq!(args.session_id, session_id);

            let cli = Cli::try_parse_from([
                "hermes-browser-runtime",
                "artifacts",
                "downloads",
                &session_id.to_string(),
            ])
            .expect("artifacts downloads should parse");
            let args = artifacts_args(cli.command);
            let ArtifactsCommand::Downloads(args) = args.command else {
                panic!("expected artifacts downloads command");
            };
            assert_eq!(args.session_id, session_id);

            let cli = Cli::try_parse_from([
                "hermes-browser-runtime",
                "artifacts",
                "download",
                &session_id.to_string(),
                "report.txt",
                "--output",
                "/tmp/report.txt",
            ])
            .expect("artifacts download should parse");
            let args = artifacts_args(cli.command);
            let ArtifactsCommand::Download(args) = args.command else {
                panic!("expected artifacts download command");
            };
            assert_eq!(args.session_id, session_id);
            assert_eq!(args.name, "report.txt");
            assert_eq!(args.output, Some(PathBuf::from("/tmp/report.txt")));

            let cli = Cli::try_parse_from([
                "hermes-browser-runtime",
                "artifacts",
                "cleanup",
                "--dry-run",
                "--older-than-secs",
                "60",
            ])
            .expect("artifacts cleanup should parse");
            let args = artifacts_args(cli.command);
            let ArtifactsCommand::Cleanup(args) = args.command else {
                panic!("expected artifacts cleanup command");
            };
            assert!(args.dry_run);
            assert_eq!(args.older_than_secs, Some(60));

            let cli = Cli::try_parse_from([
                "hermes-browser-runtime",
                "artifacts",
                "replay",
                &session_id.to_string(),
                "--output",
                "/tmp/replay.html",
            ])
            .expect("artifacts replay should parse");
            let args = artifacts_args(cli.command);
            let ArtifactsCommand::Replay(args) = args.command else {
                panic!("expected artifacts replay command");
            };
            assert_eq!(args.session_id, session_id);
            assert_eq!(args.output, Some(PathBuf::from("/tmp/replay.html")));
        });
    }
}
