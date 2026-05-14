use std::{fmt, str::FromStr};

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::credentials::{CredentialBrokerMode, CredentialFillStatus};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum SessionStatus {
    Starting,
    Running,
    PausedForHuman,
    Closing,
    Closed,
    Failed,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Viewport {
    pub width: u32,
    pub height: u32,
}

impl Default for Viewport {
    fn default() -> Self {
        Self {
            width: 1280,
            height: 800,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BrowserPersona {
    pub locale: String,
    pub accept_language: String,
    pub timezone_id: String,
    pub platform: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub user_agent: Option<String>,
    pub viewport: Viewport,
    pub screen: Viewport,
    pub device_scale_factor: f64,
    #[serde(default = "default_hardware_concurrency")]
    pub hardware_concurrency: u32,
    #[serde(default = "default_device_memory_gb")]
    pub device_memory_gb: u32,
    #[serde(default = "default_max_touch_points")]
    pub max_touch_points: u32,
}

pub const DEFAULT_HARDWARE_CONCURRENCY: u32 = 8;
pub const DEFAULT_DEVICE_MEMORY_GB: u32 = 8;
pub const DEFAULT_MAX_TOUCH_POINTS: u32 = 0;

impl Default for BrowserPersona {
    fn default() -> Self {
        Self {
            locale: "en-US".to_string(),
            accept_language: "en-US,en;q=0.9".to_string(),
            timezone_id: "America/New_York".to_string(),
            platform: "Linux x86_64".to_string(),
            user_agent: None,
            viewport: Viewport::default(),
            screen: Viewport::default(),
            device_scale_factor: 1.0,
            hardware_concurrency: DEFAULT_HARDWARE_CONCURRENCY,
            device_memory_gb: DEFAULT_DEVICE_MEMORY_GB,
            max_touch_points: DEFAULT_MAX_TOUCH_POINTS,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ResolvedBrowserIdentity {
    pub user_agent: String,
    pub chrome_full_version: String,
    pub chrome_major_version: String,
    pub client_hint_platform: String,
    pub platform_version: String,
    pub architecture: String,
    pub bitness: String,
    pub mobile: bool,
    pub form_factors: Vec<String>,
}

impl BrowserPersona {
    pub fn normalized_hardware_concurrency(&self) -> u32 {
        normalize_hardware_concurrency(self.hardware_concurrency)
    }

    pub fn normalized_device_memory_gb(&self) -> u32 {
        normalize_device_memory_gb(self.device_memory_gb)
    }

    pub fn normalized_max_touch_points(&self) -> u32 {
        normalize_max_touch_points(self.max_touch_points)
    }

    pub fn resolved_identity(&self, browser_user_agent: Option<&str>) -> ResolvedBrowserIdentity {
        let user_agent = self.resolved_user_agent(browser_user_agent);
        let chrome_full_version = chrome_full_version_from_user_agent(&user_agent)
            .unwrap_or_else(|| DEFAULT_CHROME_FULL_VERSION.to_string());
        let chrome_major_version = chrome_major_version(&chrome_full_version);
        ResolvedBrowserIdentity {
            user_agent,
            chrome_full_version,
            chrome_major_version,
            client_hint_platform: client_hint_platform(&self.platform),
            platform_version: client_hint_platform_version(&self.platform),
            architecture: client_hint_architecture(&self.platform).to_string(),
            bitness: client_hint_bitness(&self.platform).to_string(),
            mobile: false,
            form_factors: vec!["Desktop".to_string()],
        }
    }

    pub fn resolved_user_agent(&self, browser_user_agent: Option<&str>) -> String {
        if let Some(user_agent) = self.user_agent.as_deref() {
            return sanitize_browser_user_agent(user_agent);
        }

        let sanitized_browser_user_agent = browser_user_agent.map(sanitize_browser_user_agent);
        let full_version = sanitized_browser_user_agent
            .as_deref()
            .and_then(chrome_full_version_from_user_agent)
            .unwrap_or_else(|| DEFAULT_CHROME_FULL_VERSION.to_string());

        user_agent_for_platform(&self.platform, &full_version)
            .or(sanitized_browser_user_agent)
            .unwrap_or_else(default_user_agent)
    }

    pub fn resolved_launch_user_agent(&self, chrome_full_version: Option<&str>) -> Option<String> {
        if let Some(user_agent) = self.user_agent.as_deref() {
            return Some(sanitize_browser_user_agent(user_agent));
        }

        let full_version = chrome_full_version.and_then(extract_chrome_full_version)?;
        user_agent_for_platform(&self.platform, &full_version)
    }
}

#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum WebRtcIpPolicy {
    #[default]
    DefaultPublicInterfaceOnly,
    DefaultPublicAndPrivateInterfaces,
    DisableNonProxiedUdp,
}

impl WebRtcIpPolicy {
    pub fn as_chrome_value(self) -> &'static str {
        match self {
            Self::DefaultPublicInterfaceOnly => "default_public_interface_only",
            Self::DefaultPublicAndPrivateInterfaces => "default_public_and_private_interfaces",
            Self::DisableNonProxiedUdp => "disable_non_proxied_udp",
        }
    }
}

impl fmt::Display for WebRtcIpPolicy {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_chrome_value())
    }
}

impl FromStr for WebRtcIpPolicy {
    type Err = String;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match normalized_policy_value(value).as_str() {
            "default_public_interface_only" => Ok(Self::DefaultPublicInterfaceOnly),
            "default_public_and_private_interfaces" => Ok(Self::DefaultPublicAndPrivateInterfaces),
            "disable_non_proxied_udp" => Ok(Self::DisableNonProxiedUdp),
            _ => Err(format!(
                "expected one of default_public_interface_only, default_public_and_private_interfaces, disable_non_proxied_udp; got {value:?}"
            )),
        }
    }
}

#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum GpuPolicy {
    #[default]
    Auto,
    SwiftshaderCompat,
    Disable3d,
}

impl GpuPolicy {
    pub fn as_config_value(self) -> &'static str {
        match self {
            Self::Auto => "auto",
            Self::SwiftshaderCompat => "swiftshader_compat",
            Self::Disable3d => "disable_3d",
        }
    }
}

impl fmt::Display for GpuPolicy {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_config_value())
    }
}

impl FromStr for GpuPolicy {
    type Err = String;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match normalized_policy_value(value).as_str() {
            "auto" => Ok(Self::Auto),
            "swiftshader_compat" => Ok(Self::SwiftshaderCompat),
            "disable_3d" => Ok(Self::Disable3d),
            _ => Err(format!(
                "expected one of auto, swiftshader_compat, disable_3d; got {value:?}"
            )),
        }
    }
}

#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum CaptchaPolicy {
    /// Safe default: do not attempt automatic challenge solving; pause for human handling.
    #[default]
    HumanOnly,
    /// Record challenge telemetry only; callers must decide whether to pause separately.
    ObserveOnly,
    /// Opt-in policy that allows an explicitly requested solve to pass runtime safety gates.
    AutoSolve,
    /// Disable runtime-level CAPTCHA/checkpoint state tracking for the session.
    Disabled,
}

impl CaptchaPolicy {
    pub fn as_config_value(self) -> &'static str {
        match self {
            Self::HumanOnly => "human_only",
            Self::ObserveOnly => "observe_only",
            Self::AutoSolve => "auto_solve",
            Self::Disabled => "disabled",
        }
    }
}

impl fmt::Display for CaptchaPolicy {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_config_value())
    }
}

impl FromStr for CaptchaPolicy {
    type Err = String;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match normalized_policy_value(value).as_str() {
            "human_only" => Ok(Self::HumanOnly),
            "observe_only" => Ok(Self::ObserveOnly),
            "auto_solve" => Ok(Self::AutoSolve),
            "disabled" => Ok(Self::Disabled),
            _ => Err(format!(
                "expected one of human_only, observe_only, auto_solve, disabled; got {value:?}"
            )),
        }
    }
}

#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum CaptchaStatus {
    #[default]
    None,
    Suspected,
    HumanRequired,
    InProgress,
    Resolved,
    Failed,
    Dismissed,
}

impl CaptchaStatus {
    pub fn is_checkpoint(self) -> bool {
        matches!(
            self,
            Self::Suspected | Self::HumanRequired | Self::InProgress
        )
    }
}

#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum CaptchaSolverState {
    #[default]
    NotRequested,
    Disabled,
    PolicyBlocked,
    NoProviderKey,
    BudgetUnavailable,
    InProgress,
    Resolved,
    Failed,
    HumanRequired,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct CaptchaSolverStatus {
    pub status: CaptchaSolverState,
    pub enabled: bool,
    pub policy: CaptchaPolicy,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub challenge_type: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub provider_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub normalized_error: Option<String>,
    pub human_takeover_required: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub redacted_message: Option<String>,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum CaptchaReportState {
    Suspected,
    HumanRequired,
    InProgress,
}

impl CaptchaReportState {
    pub fn as_config_value(self) -> &'static str {
        match self {
            Self::Suspected => "suspected",
            Self::HumanRequired => "human_required",
            Self::InProgress => "in_progress",
        }
    }
}

impl fmt::Display for CaptchaReportState {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_config_value())
    }
}

impl FromStr for CaptchaReportState {
    type Err = String;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match normalized_policy_value(value).as_str() {
            "suspected" => Ok(Self::Suspected),
            "human_required" => Ok(Self::HumanRequired),
            "in_progress" => Ok(Self::InProgress),
            _ => Err(format!(
                "expected one of suspected, human_required, in_progress; got {value:?}"
            )),
        }
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum CaptchaResolveOutcome {
    Resolved,
    Failed,
    Dismissed,
}

impl CaptchaResolveOutcome {
    pub fn as_config_value(self) -> &'static str {
        match self {
            Self::Resolved => "resolved",
            Self::Failed => "failed",
            Self::Dismissed => "dismissed",
        }
    }
}

impl fmt::Display for CaptchaResolveOutcome {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_config_value())
    }
}

impl FromStr for CaptchaResolveOutcome {
    type Err = String;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match normalized_policy_value(value).as_str() {
            "resolved" => Ok(Self::Resolved),
            "failed" => Ok(Self::Failed),
            "dismissed" => Ok(Self::Dismissed),
            _ => Err(format!(
                "expected one of resolved, failed, dismissed; got {value:?}"
            )),
        }
    }
}

impl From<CaptchaReportState> for CaptchaStatus {
    fn from(value: CaptchaReportState) -> Self {
        match value {
            CaptchaReportState::Suspected => Self::Suspected,
            CaptchaReportState::HumanRequired => Self::HumanRequired,
            CaptchaReportState::InProgress => Self::InProgress,
        }
    }
}

impl From<CaptchaResolveOutcome> for CaptchaStatus {
    fn from(value: CaptchaResolveOutcome) -> Self {
        match value {
            CaptchaResolveOutcome::Resolved => Self::Resolved,
            CaptchaResolveOutcome::Failed => Self::Failed,
            CaptchaResolveOutcome::Dismissed => Self::Dismissed,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Default, PartialEq)]
pub struct CaptchaScanRequest {
    #[serde(default)]
    pub dry_run: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default, PartialEq)]
pub struct CaptchaSolveRequest {
    #[serde(default)]
    pub dry_run: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub challenge_type: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub site_key: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub page_url: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CaptchaStatusResponse {
    pub session_id: Uuid,
    pub session_status: SessionStatus,
    pub captcha_policy: CaptchaPolicy,
    pub captcha_status: CaptchaStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub challenge_type: Option<String>,
    pub solver: CaptchaSolverStatus,
}

impl CaptchaStatusResponse {
    pub fn from_session(info: &SessionInfo, solver_enabled: bool) -> Self {
        let solver = info
            .captcha_solver_status
            .clone()
            .unwrap_or_else(|| CaptchaSolverStatus {
                status: CaptchaSolverState::NotRequested,
                enabled: solver_enabled,
                policy: info.captcha_policy,
                challenge_type: info.captcha_challenge_type.clone(),
                provider_id: None,
                normalized_error: None,
                human_takeover_required: false,
                redacted_message: None,
            });
        Self {
            session_id: info.id,
            session_status: info.status.clone(),
            captcha_policy: info.captcha_policy,
            captcha_status: info.captcha_status,
            challenge_type: info.captcha_challenge_type.clone(),
            solver,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CaptchaScanResponse {
    pub session_id: Uuid,
    pub detected: bool,
    pub captcha_status: CaptchaStatus,
    pub captcha_policy: CaptchaPolicy,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub challenge_type: Option<String>,
    pub policy_decision: String,
    pub provider_call_performed: bool,
    pub dry_run: bool,
    pub solver: CaptchaSolverStatus,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CaptchaSolveResponse {
    pub session_id: Uuid,
    pub captcha_status: CaptchaStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub challenge_type: Option<String>,
    pub solver: CaptchaSolverStatus,
    pub provider_call_performed: bool,
}

impl CaptchaSolveResponse {
    pub fn from_session(info: SessionInfo, provider_call_performed: bool) -> Self {
        let status = CaptchaStatusResponse::from_session(&info, false);
        Self::from_status(status, provider_call_performed)
    }

    pub fn from_status(status: CaptchaStatusResponse, provider_call_performed: bool) -> Self {
        Self {
            session_id: status.session_id,
            captcha_status: status.captcha_status,
            challenge_type: status.challenge_type,
            solver: status.solver,
            provider_call_performed,
        }
    }
}

const DEFAULT_CHROME_FULL_VERSION: &str = "125.0.0.0";

fn default_hardware_concurrency() -> u32 {
    DEFAULT_HARDWARE_CONCURRENCY
}

fn default_device_memory_gb() -> u32 {
    DEFAULT_DEVICE_MEMORY_GB
}

fn default_max_touch_points() -> u32 {
    DEFAULT_MAX_TOUCH_POINTS
}

fn normalize_hardware_concurrency(value: u32) -> u32 {
    match value {
        2 => 2,
        3 | 4 => 4,
        5..=16 => 8,
        _ => DEFAULT_HARDWARE_CONCURRENCY,
    }
}

fn normalize_device_memory_gb(value: u32) -> u32 {
    match value {
        1 => 1,
        2 => 2,
        3 | 4 => 4,
        5..=16 => 8,
        _ => DEFAULT_DEVICE_MEMORY_GB,
    }
}

fn normalize_max_touch_points(value: u32) -> u32 {
    if value <= 10 {
        value
    } else {
        DEFAULT_MAX_TOUCH_POINTS
    }
}

fn normalized_policy_value(value: &str) -> String {
    value.trim().to_ascii_lowercase().replace('-', "_")
}

fn sanitize_browser_user_agent(user_agent: &str) -> String {
    user_agent.replace("HeadlessChrome/", "Chrome/")
}

pub fn extract_chrome_full_version(value: &str) -> Option<String> {
    chrome_full_version_from_user_agent(value).or_else(|| {
        value
            .split(|ch: char| !(ch.is_ascii_digit() || ch == '.'))
            .find(|candidate| is_full_chrome_version(candidate))
            .map(str::to_string)
    })
}

pub fn chrome_full_version_from_user_agent(user_agent: &str) -> Option<String> {
    user_agent
        .split("Chrome/")
        .nth(1)
        .or_else(|| user_agent.split("Chromium/").nth(1))
        .and_then(|rest| rest.split_whitespace().next())
        .filter(|value| is_full_chrome_version(value))
        .map(str::to_string)
}

pub fn chrome_major_version(full_version: &str) -> String {
    full_version
        .split('.')
        .next()
        .filter(|value| !value.is_empty() && value.chars().all(|ch| ch.is_ascii_digit()))
        .unwrap_or("125")
        .to_string()
}

pub fn client_hint_platform(platform: &str) -> String {
    let platform_lower = platform.to_ascii_lowercase();
    if platform_lower.contains("windows") {
        "Windows".to_string()
    } else if platform_lower.contains("mac") {
        "macOS".to_string()
    } else if platform_lower.contains("android") {
        "Android".to_string()
    } else if platform_lower.contains("linux") {
        "Linux".to_string()
    } else {
        platform
            .split_whitespace()
            .next()
            .unwrap_or("Linux")
            .to_string()
    }
}

pub fn client_hint_platform_version(platform: &str) -> String {
    platform
        .split_whitespace()
        .find(|part| part.chars().any(|ch| ch.is_ascii_digit()))
        .unwrap_or("")
        .to_string()
}

pub fn client_hint_architecture(platform: &str) -> &'static str {
    let platform_lower = platform.to_ascii_lowercase();
    if platform_lower.contains("arm") || platform_lower.contains("aarch") {
        "arm"
    } else {
        "x86"
    }
}

pub fn client_hint_bitness(platform: &str) -> &'static str {
    let platform_lower = platform.to_ascii_lowercase();
    if platform_lower.contains("64") || platform_lower.contains("x86_64") {
        "64"
    } else {
        ""
    }
}

fn is_full_chrome_version(value: &str) -> bool {
    let mut parts = value.split('.');
    let Some(first) = parts.next() else {
        return false;
    };
    if first.is_empty() || !first.chars().all(|ch| ch.is_ascii_digit()) {
        return false;
    }
    let mut has_minor_parts = false;
    for part in parts {
        has_minor_parts = true;
        if part.is_empty() || !part.chars().all(|ch| ch.is_ascii_digit()) {
            return false;
        }
    }
    has_minor_parts
}

fn user_agent_for_platform(platform: &str, chrome_version: &str) -> Option<String> {
    let platform_lower = platform.to_ascii_lowercase();
    let os_token = if platform_lower.contains("windows") {
        "Windows NT 10.0; Win64; x64".to_string()
    } else if platform_lower.contains("mac") {
        let version = platform_version_token(platform)
            .map(|version| version.replace('.', "_"))
            .unwrap_or_else(|| "10_15_7".to_string());
        format!("Macintosh; Intel Mac OS X {version}")
    } else if platform_lower.contains("linux") {
        if platform_lower.contains("arm") || platform_lower.contains("aarch") {
            "X11; Linux aarch64".to_string()
        } else {
            "X11; Linux x86_64".to_string()
        }
    } else {
        return None;
    };

    Some(format!(
        "Mozilla/5.0 ({os_token}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"
    ))
}

fn platform_version_token(platform: &str) -> Option<&str> {
    platform
        .split_whitespace()
        .find(|part| part.chars().any(|ch| ch.is_ascii_digit()))
}

fn default_user_agent() -> String {
    user_agent_for_platform("Linux x86_64", DEFAULT_CHROME_FULL_VERSION).expect("default Linux UA")
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct CreateSessionRequest {
    pub profile_id: Option<String>,
    pub headless: Option<bool>,
    pub viewport: Option<Viewport>,
    pub persist_profile: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub captcha_policy: Option<CaptchaPolicy>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub launch_timeout_secs: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub persona: Option<BrowserPersona>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub webrtc_ip_policy: Option<WebRtcIpPolicy>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub gpu_policy: Option<GpuPolicy>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionInfo {
    pub id: Uuid,
    pub status: SessionStatus,
    pub cdp_ws_url: Option<String>,
    pub takeover_url: Option<String>,
    pub profile_id: String,
    pub persist_profile: bool,
    pub headless: bool,
    pub viewport: Viewport,
    #[serde(default)]
    pub webrtc_ip_policy: WebRtcIpPolicy,
    #[serde(default)]
    pub gpu_policy: GpuPolicy,
    #[serde(default)]
    pub captcha_policy: CaptchaPolicy,
    #[serde(default)]
    pub captcha_status: CaptchaStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub captcha_challenge_type: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub captcha_solver_status: Option<CaptchaSolverStatus>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub pause_reason: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateSessionResponse {
    pub id: Uuid,
    pub status: SessionStatus,
    pub cdp_ws_url: String,
    pub takeover_url: Option<String>,
    pub profile_id: String,
    pub webrtc_ip_policy: WebRtcIpPolicy,
    pub gpu_policy: GpuPolicy,
    pub captcha_policy: CaptchaPolicy,
    pub captcha_status: CaptchaStatus,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PauseForHumanRequest {
    pub reason: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CaptchaReportRequest {
    pub state: CaptchaReportState,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub challenge_type: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CaptchaResolveRequest {
    pub outcome: CaptchaResolveOutcome,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub note: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WaitSessionResponse {
    pub timed_out: bool,
    pub session: SessionInfo,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum LiveLinkMode {
    ReadOnly,
    Interactive,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateLiveLinkRequest {
    #[serde(default = "default_live_link_mode")]
    pub mode: LiveLinkMode,
}

fn default_live_link_mode() -> LiveLinkMode {
    LiveLinkMode::ReadOnly
}

#[derive(Debug, Clone, Serialize)]
pub struct CreateLiveLinkResponse {
    pub id: Uuid,
    pub mode: LiveLinkMode,
    pub url: String,
    pub created_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize)]
pub struct LiveLinkSummary {
    pub id: Uuid,
    pub mode: LiveLinkMode,
    pub created_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
    pub revoked: bool,
    pub expired: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CredentialFillStartRequest {
    pub alias: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub username_selector: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub password_selector: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub purpose: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub expected_origin: Option<String>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct CredentialDecisionRequest {
    /// Human-readable approval note. Notes are redacted before persistence.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub note: Option<String>,
    /// Human-readable denial reason. Reasons are redacted before persistence.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
}

impl CredentialDecisionRequest {
    pub fn operator_note(self) -> Option<String> {
        self.note.or(self.reason)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CredentialFillStatusRecord {
    pub request_id: Uuid,
    pub session_id: Uuid,
    pub alias: String,
    pub observed_origin: String,
    pub status: CredentialFillStatus,
    pub broker: CredentialBrokerMode,
    pub audit_id: Uuid,
    pub privacy_guard_active: bool,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub redacted_message: Option<String>,
}

impl CredentialFillStatusRecord {
    pub fn is_terminal(&self) -> bool {
        matches!(
            self.status,
            CredentialFillStatus::Unavailable
                | CredentialFillStatus::Filled
                | CredentialFillStatus::Denied
                | CredentialFillStatus::NoMatch
                | CredentialFillStatus::OriginMismatch
                | CredentialFillStatus::PolicyBlocked
                | CredentialFillStatus::UnlockRequired
                | CredentialFillStatus::ProviderLocked
                | CredentialFillStatus::Failed
        )
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CredentialPrivacyGuardResponse {
    pub session_id: Uuid,
    pub privacy_guard_active: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct ProfileInfo {
    pub id: String,
    pub path: String,
    pub locked_by: Option<Uuid>,
    pub created_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateProfileRequest {
    pub id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ArtifactInfo {
    pub kind: String,
    pub path: String,
    pub created_at: DateTime<Utc>,
    pub size_bytes: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ArtifactsResponse {
    pub session_id: Uuid,
    pub artifacts: Vec<ArtifactInfo>,
    pub downloads_dir: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DownloadInfo {
    pub name: String,
    pub created_at: DateTime<Utc>,
    pub size_bytes: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DownloadsResponse {
    pub session_id: Uuid,
    pub downloads: Vec<DownloadInfo>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CleanupArtifactsRequest {
    pub dry_run: bool,
    pub older_than_secs: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CleanupCandidate {
    pub session_id: String,
    pub last_activity_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CleanupArtifactsResponse {
    pub dry_run: bool,
    pub retention_secs: u64,
    pub candidates: Vec<CleanupCandidate>,
    pub deleted_session_ids: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ErrorResponse {
    pub error: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ClickRequest {
    pub x: f64,
    pub y: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct TypeRequest {
    pub text: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct KeyRequest {
    pub key: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ScrollRequest {
    pub delta_x: Option<f64>,
    pub delta_y: Option<f64>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn viewport_defaults_to_agent_friendly_size() {
        assert_eq!(
            Viewport::default(),
            Viewport {
                width: 1280,
                height: 800
            }
        );
    }

    #[test]
    fn session_status_serializes_as_snake_case() {
        assert_eq!(
            serde_json::to_string(&SessionStatus::PausedForHuman).unwrap(),
            "\"paused_for_human\""
        );
    }

    #[test]
    fn live_link_request_defaults_to_read_only_and_serializes_modes() {
        let request: CreateLiveLinkRequest = serde_json::from_value(serde_json::json!({})).unwrap();
        assert_eq!(request.mode, LiveLinkMode::ReadOnly);
        assert_eq!(
            serde_json::to_string(&LiveLinkMode::ReadOnly).unwrap(),
            "\"read_only\""
        );
        assert_eq!(
            serde_json::to_string(&LiveLinkMode::Interactive).unwrap(),
            "\"interactive\""
        );
    }

    #[test]
    fn captcha_models_default_to_human_only_and_legacy_sessions_deserialize() {
        assert_eq!(CaptchaPolicy::default(), CaptchaPolicy::HumanOnly);
        assert_eq!(CaptchaStatus::default(), CaptchaStatus::None);
        assert_eq!(
            serde_json::to_string(&CaptchaPolicy::HumanOnly).unwrap(),
            "\"human_only\""
        );
        assert_eq!(
            serde_json::to_string(&CaptchaStatus::HumanRequired).unwrap(),
            "\"human_required\""
        );

        for (policy, value) in [
            (CaptchaPolicy::HumanOnly, "human_only"),
            (CaptchaPolicy::ObserveOnly, "observe_only"),
            (CaptchaPolicy::AutoSolve, "auto_solve"),
            (CaptchaPolicy::Disabled, "disabled"),
        ] {
            assert_eq!(policy.as_config_value(), value);
            assert_eq!(policy.to_string(), value);
            assert_eq!(value.parse::<CaptchaPolicy>().unwrap(), policy);
            assert_eq!(
                value.replace('_', "-").parse::<CaptchaPolicy>().unwrap(),
                policy
            );
        }
        assert!(
            "maybe"
                .parse::<CaptchaPolicy>()
                .unwrap_err()
                .contains("expected")
        );

        for status in [
            CaptchaStatus::Suspected,
            CaptchaStatus::HumanRequired,
            CaptchaStatus::InProgress,
        ] {
            assert!(status.is_checkpoint());
        }
        for status in [
            CaptchaStatus::None,
            CaptchaStatus::Resolved,
            CaptchaStatus::Failed,
            CaptchaStatus::Dismissed,
        ] {
            assert!(!status.is_checkpoint());
        }

        for (state, value, status) in [
            (
                CaptchaReportState::Suspected,
                "suspected",
                CaptchaStatus::Suspected,
            ),
            (
                CaptchaReportState::HumanRequired,
                "human_required",
                CaptchaStatus::HumanRequired,
            ),
            (
                CaptchaReportState::InProgress,
                "in_progress",
                CaptchaStatus::InProgress,
            ),
        ] {
            assert_eq!(state.as_config_value(), value);
            assert_eq!(state.to_string(), value);
            assert_eq!(value.parse::<CaptchaReportState>().unwrap(), state);
            assert_eq!(CaptchaStatus::from(state), status);
        }
        assert!(
            "ignored"
                .parse::<CaptchaReportState>()
                .unwrap_err()
                .contains("expected")
        );

        for (outcome, value, status) in [
            (
                CaptchaResolveOutcome::Resolved,
                "resolved",
                CaptchaStatus::Resolved,
            ),
            (
                CaptchaResolveOutcome::Failed,
                "failed",
                CaptchaStatus::Failed,
            ),
            (
                CaptchaResolveOutcome::Dismissed,
                "dismissed",
                CaptchaStatus::Dismissed,
            ),
        ] {
            assert_eq!(outcome.as_config_value(), value);
            assert_eq!(outcome.to_string(), value);
            assert_eq!(value.parse::<CaptchaResolveOutcome>().unwrap(), outcome);
            assert_eq!(CaptchaStatus::from(outcome), status);
        }
        assert!(
            "ignored"
                .parse::<CaptchaResolveOutcome>()
                .unwrap_err()
                .contains("expected")
        );

        assert_eq!(normalize_device_memory_gb(2), 2);
        assert_eq!(client_hint_platform("Windows 11"), "Windows");
        assert!(chrome_full_version_from_user_agent("Chrome/1.bad").is_none());

        let legacy: SessionInfo = serde_json::from_value(serde_json::json!({
            "id": Uuid::nil(),
            "status": "running",
            "cdp_ws_url": null,
            "takeover_url": null,
            "profile_id": "legacy-profile",
            "persist_profile": true,
            "headless": true,
            "viewport": {"width": 1280, "height": 800},
            "webrtc_ip_policy": "default_public_interface_only",
            "gpu_policy": "auto",
            "created_at": "2026-05-12T00:00:00Z",
            "updated_at": "2026-05-12T00:00:00Z",
            "pause_reason": null
        }))
        .unwrap();

        assert_eq!(legacy.captcha_policy, CaptchaPolicy::HumanOnly);
        assert_eq!(legacy.captcha_status, CaptchaStatus::None);
        assert!(legacy.captcha_challenge_type.is_none());
    }

    #[test]
    fn default_browser_persona_is_coherent_and_sanitizes_headless_user_agent() {
        let persona = BrowserPersona::default();
        assert_eq!(persona.locale, "en-US");
        assert!(persona.accept_language.starts_with(&persona.locale));
        assert_eq!(persona.viewport, Viewport::default());
        assert_eq!(persona.screen, Viewport::default());
        assert_eq!(persona.device_scale_factor, 1.0);
        assert_eq!(persona.hardware_concurrency, 8);
        assert_eq!(persona.device_memory_gb, 8);
        assert_eq!(persona.max_touch_points, 0);

        let ua =
            persona.resolved_user_agent(Some("Mozilla/5.0 HeadlessChrome/125.0.0.0 Safari/537.36"));
        assert!(ua.contains("X11; Linux x86_64"));
        assert!(ua.contains("Chrome/125.0.0.0"));
        assert!(!ua.contains("HeadlessChrome"));
    }

    #[test]
    fn browser_persona_deserializes_legacy_json_with_hardware_defaults() {
        let persona: BrowserPersona = serde_json::from_value(serde_json::json!({
            "locale": "pt-PT",
            "accept_language": "pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "timezone_id": "Europe/Lisbon",
            "platform": "Linux x86_64",
            "viewport": {"width": 1280, "height": 800},
            "screen": {"width": 1280, "height": 800},
            "device_scale_factor": 1.0
        }))
        .unwrap();

        assert_eq!(persona.hardware_concurrency, 8);
        assert_eq!(persona.device_memory_gb, 8);
        assert_eq!(persona.max_touch_points, 0);
        assert_eq!(persona.normalized_hardware_concurrency(), 8);
        assert_eq!(persona.normalized_device_memory_gb(), 8);
        assert_eq!(persona.normalized_max_touch_points(), 0);
    }

    #[test]
    fn browser_persona_normalizes_conservative_hardware_buckets() {
        let high_entropy_host_like = BrowserPersona {
            hardware_concurrency: 96,
            device_memory_gb: 128,
            max_touch_points: 42,
            ..BrowserPersona::default()
        };
        assert_eq!(high_entropy_host_like.normalized_hardware_concurrency(), 8);
        assert_eq!(high_entropy_host_like.normalized_device_memory_gb(), 8);
        assert_eq!(high_entropy_host_like.normalized_max_touch_points(), 0);

        let conservative_override = BrowserPersona {
            hardware_concurrency: 4,
            device_memory_gb: 4,
            max_touch_points: 5,
            ..BrowserPersona::default()
        };
        assert_eq!(conservative_override.normalized_hardware_concurrency(), 4);
        assert_eq!(conservative_override.normalized_device_memory_gb(), 4);
        assert_eq!(conservative_override.normalized_max_touch_points(), 5);
    }

    #[test]
    fn browser_persona_derives_user_agent_from_platform_when_no_explicit_ua_is_set() {
        let browser_ua = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) \
             HeadlessChrome/126.0.6478.127 Safari/537.36";
        let mac = BrowserPersona {
            platform: "macOS 14.5 arm64".into(),
            user_agent: None,
            ..BrowserPersona::default()
        };
        let mac_ua = mac.resolved_user_agent(Some(browser_ua));
        assert!(mac_ua.contains("Macintosh; Intel Mac OS X 14_5"));
        assert!(mac_ua.contains("Chrome/126.0.6478.127"));
        assert!(!mac_ua.contains("Linux"));
        assert!(!mac_ua.contains("HeadlessChrome"));

        let windows = BrowserPersona {
            platform: "Windows x86_64".into(),
            user_agent: None,
            ..BrowserPersona::default()
        };
        let windows_ua = windows.resolved_user_agent(Some(browser_ua));
        assert!(windows_ua.contains("Windows NT 10.0; Win64; x64"));
        assert!(windows_ua.contains("Chrome/126.0.6478.127"));
        assert!(!windows_ua.contains("HeadlessChrome"));
    }

    #[test]
    fn browser_persona_resolves_shared_identity_for_ua_and_client_hints() {
        let persona = BrowserPersona {
            locale: "fr-FR".into(),
            accept_language: "fr-FR,fr;q=0.9".into(),
            timezone_id: "Europe/Paris".into(),
            platform: "macOS 14.5 arm64".into(),
            user_agent: None,
            viewport: Viewport {
                width: 1440,
                height: 900,
            },
            screen: Viewport {
                width: 1440,
                height: 900,
            },
            device_scale_factor: 2.0,
            hardware_concurrency: DEFAULT_HARDWARE_CONCURRENCY,
            device_memory_gb: DEFAULT_DEVICE_MEMORY_GB,
            max_touch_points: DEFAULT_MAX_TOUCH_POINTS,
        };

        let identity = persona.resolved_identity(Some(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 \
             (KHTML, like Gecko) HeadlessChrome/143.0.7499.40 Safari/537.36",
        ));

        assert_eq!(identity.chrome_full_version, "143.0.7499.40");
        assert_eq!(identity.chrome_major_version, "143");
        assert_eq!(identity.client_hint_platform, "macOS");
        assert_eq!(identity.platform_version, "14.5");
        assert_eq!(identity.architecture, "arm");
        assert_eq!(identity.bitness, "64");
        assert!(!identity.mobile);
        assert_eq!(identity.form_factors, vec!["Desktop".to_string()]);
        assert!(
            identity
                .user_agent
                .contains("Macintosh; Intel Mac OS X 14_5")
        );
        assert!(identity.user_agent.contains("Chrome/143.0.7499.40"));
        assert!(!identity.user_agent.contains("HeadlessChrome"));
    }

    #[test]
    fn explicit_persona_user_agent_is_still_sanitized() {
        let persona = BrowserPersona {
            user_agent: Some("Mozilla/5.0 HeadlessChrome/127.0.0.0 Safari/537.36".into()),
            ..BrowserPersona::default()
        };

        let ua = persona.resolved_user_agent(None);

        assert!(ua.contains("Chrome/127.0.0.0"));
        assert!(!ua.contains("HeadlessChrome"));
    }

    #[test]
    fn browser_policy_enums_round_trip_as_snake_case_and_parse_aliases() {
        assert_eq!(
            serde_json::to_string(&WebRtcIpPolicy::DefaultPublicInterfaceOnly).unwrap(),
            "\"default_public_interface_only\""
        );
        assert_eq!(
            "disable-non-proxied-udp".parse::<WebRtcIpPolicy>().unwrap(),
            WebRtcIpPolicy::DisableNonProxiedUdp
        );
        assert_eq!(
            WebRtcIpPolicy::default().as_chrome_value(),
            "default_public_interface_only"
        );

        assert_eq!(
            serde_json::to_string(&GpuPolicy::SwiftshaderCompat).unwrap(),
            "\"swiftshader_compat\""
        );
        assert_eq!(
            "disable-3d".parse::<GpuPolicy>().unwrap(),
            GpuPolicy::Disable3d
        );
        assert_eq!(GpuPolicy::default(), GpuPolicy::Auto);
    }
}
