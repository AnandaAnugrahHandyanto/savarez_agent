use std::{
    collections::{BTreeMap, HashSet},
    env, fmt,
    path::{Path, PathBuf},
    process::Stdio,
    str::FromStr,
    sync::Arc,
    time::Duration,
};

use anyhow::{Result, anyhow};
use async_trait::async_trait;
use reqwest::Url;
use serde::{Deserialize, Deserializer, Serialize, de};
use tokio::{io::AsyncReadExt, process::Command};
use uuid::Uuid;

use crate::security::{REDACTED, redact_text};

pub const DEFAULT_OP_TIMEOUT_SECS: u64 = 5;
pub const DEFAULT_CREDENTIAL_APPROVAL_TTL_SECS: u64 = 300;

#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum CredentialBrokerMode {
    #[default]
    Disabled,
    FakeStatusOnly,
    Mock,
    OnePasswordCli,
}

impl fmt::Display for CredentialBrokerMode {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::Disabled => "disabled",
            Self::FakeStatusOnly => "fake_status_only",
            Self::Mock => "mock",
            Self::OnePasswordCli => "onepassword_cli",
        })
    }
}

impl FromStr for CredentialBrokerMode {
    type Err = String;

    fn from_str(value: &str) -> std::result::Result<Self, Self::Err> {
        match value.trim().to_ascii_lowercase().as_str() {
            "disabled" => Ok(Self::Disabled),
            "fake" | "fake_status_only" => Ok(Self::FakeStatusOnly),
            "mock" => Ok(Self::Mock),
            "onepassword_cli" | "1password_cli" | "op" => Ok(Self::OnePasswordCli),
            other => Err(format!(
                "unsupported credential provider mode `{other}`; expected disabled|fake_status_only|mock|onepassword_cli"
            )),
        }
    }
}

impl CredentialBrokerMode {
    pub fn provider_reads_enabled(self) -> bool {
        matches!(self, Self::Mock | Self::OnePasswordCli)
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum CredentialFillStatus {
    Unavailable,
    RequiresUserApproval,
    Pending,
    Approved,
    Filled,
    Denied,
    NoMatch,
    OriginMismatch,
    PolicyBlocked,
    UnlockRequired,
    ProviderLocked,
    Failed,
    PrivacyGuardActive,
}

#[derive(Clone, Serialize, Deserialize)]
pub struct CredentialFillRequest {
    pub request_id: Uuid,
    pub session_id: Uuid,
    pub alias: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub username_selector: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub password_selector: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub purpose: Option<String>,
    pub observed_origin: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub expected_origin: Option<String>,
}

#[derive(Clone)]
pub struct ApprovedCredentialFill {
    pub request_id: Uuid,
    pub session_id: Uuid,
    alias: String,
    observed_origin: String,
    purpose: Option<String>,
    requested_fields: CredentialFieldSelection,
    _approval_boundary: ApprovedCredentialFillBoundary,
}

#[derive(Clone, Debug)]
struct ApprovedCredentialFillBoundary;

impl ApprovedCredentialFill {
    #[allow(dead_code)]
    pub(crate) fn from_approved_state(
        request_id: Uuid,
        session_id: Uuid,
        alias: impl Into<String>,
        observed_origin: impl Into<String>,
        purpose: Option<String>,
        status: CredentialFillStatus,
    ) -> Result<Self> {
        Self::from_approved_state_for_fields(
            request_id,
            session_id,
            alias,
            observed_origin,
            purpose,
            status,
            CredentialFieldSelection::both(),
        )
    }

    pub(crate) fn from_approved_state_for_fields(
        request_id: Uuid,
        session_id: Uuid,
        alias: impl Into<String>,
        observed_origin: impl Into<String>,
        purpose: Option<String>,
        status: CredentialFillStatus,
        requested_fields: CredentialFieldSelection,
    ) -> Result<Self> {
        if status != CredentialFillStatus::Approved {
            return Err(anyhow!("credential fill approval state is not approved"));
        }
        if requested_fields.is_empty() {
            return Err(anyhow!("credential fill approval has no requested fields"));
        }
        let alias = alias.into();
        if !is_safe_alias(&alias) {
            return Err(anyhow!("credential fill approval alias is unsafe"));
        }
        let observed_origin = normalize_origin(&observed_origin.into())?.as_string();
        Ok(Self {
            request_id,
            session_id,
            alias,
            observed_origin,
            purpose,
            requested_fields,
            _approval_boundary: ApprovedCredentialFillBoundary,
        })
    }

    fn alias(&self) -> &str {
        &self.alias
    }

    fn observed_origin(&self) -> &str {
        &self.observed_origin
    }

    fn requested_fields(&self) -> CredentialFieldSelection {
        self.requested_fields
    }
}

impl fmt::Debug for ApprovedCredentialFill {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("ApprovedCredentialFill")
            .field("request_id", &self.request_id)
            .field("session_id", &self.session_id)
            .field("alias", &self.alias)
            .field("observed_origin", &self.observed_origin)
            .field("purpose", &redacted_option(&self.purpose))
            .field("requested_fields", &self.requested_fields)
            .field("approval_boundary", &"approved")
            .finish()
    }
}

impl fmt::Debug for CredentialFillRequest {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("CredentialFillRequest")
            .field("request_id", &self.request_id)
            .field("session_id", &self.session_id)
            .field("alias", &safe_or_redacted_alias(&self.alias))
            .field(
                "username_selector",
                &redacted_option(&self.username_selector),
            )
            .field(
                "password_selector",
                &redacted_option(&self.password_selector),
            )
            .field("purpose", &redacted_option(&self.purpose))
            .field("observed_origin", &self.observed_origin)
            .field("expected_origin", &self.expected_origin)
            .finish()
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CredentialFillResponse {
    pub request_id: Uuid,
    pub session_id: Uuid,
    pub alias: String,
    pub observed_origin: String,
    pub status: CredentialFillStatus,
    pub broker: CredentialBrokerMode,
    pub audit_id: Uuid,
    pub privacy_guard: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub redacted_message: Option<String>,
}

impl CredentialFillResponse {
    pub fn audit_event(&self, event_type: impl Into<String>) -> CredentialAuditEvent {
        CredentialAuditEvent {
            event_type: event_type.into(),
            request_id: self.request_id,
            session_id: self.session_id,
            alias: self.alias.clone(),
            observed_origin: self.observed_origin.clone(),
            status: self.status,
            broker: self.broker,
            audit_id: self.audit_id,
            privacy_guard: self.privacy_guard,
            redacted_message: self.redacted_message.clone(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CredentialAuditEvent {
    pub event_type: String,
    pub request_id: Uuid,
    pub session_id: Uuid,
    pub alias: String,
    pub observed_origin: String,
    pub status: CredentialFillStatus,
    pub broker: CredentialBrokerMode,
    pub audit_id: Uuid,
    pub privacy_guard: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub redacted_message: Option<String>,
}

#[async_trait]
pub trait CredentialBroker: Send + Sync {
    async fn request_fill(&self, request: CredentialFillRequest) -> Result<CredentialFillResponse>;
}

#[async_trait]
pub trait CredentialSecretProvider: Send + Sync {
    async fn read_fields(
        &self,
        provider_refs: &CredentialProviderRefs,
    ) -> std::result::Result<CredentialSecretBundle, CredentialProviderError>;
}

#[derive(Clone)]
pub struct CredentialBrokerCore<P> {
    mode: CredentialBrokerMode,
    policy: CredentialPolicy,
    provider: P,
    privacy_guard: bool,
}

impl<P> CredentialBrokerCore<P> {
    pub fn new(mode: CredentialBrokerMode, policy: CredentialPolicy, provider: P) -> Self {
        Self {
            mode,
            policy,
            provider,
            privacy_guard: true,
        }
    }

    pub fn with_privacy_guard(mut self, privacy_guard: bool) -> Self {
        self.privacy_guard = privacy_guard;
        self
    }
}

impl<P> CredentialBrokerCore<P>
where
    P: CredentialSecretProvider,
{
    pub async fn read_approved_fields_for_executor(
        &self,
        approval: &ApprovedCredentialFill,
    ) -> std::result::Result<CredentialSecretBundle, CredentialProviderError> {
        if !self.mode.provider_reads_enabled() {
            return Err(CredentialProviderError::provider_not_enabled());
        }
        let resolved = self
            .policy
            .resolve_for_approved_use(
                approval.alias(),
                approval.observed_origin(),
                approval.requested_fields(),
            )
            .map_err(|_| CredentialProviderError::policy_blocked())?;
        self.provider.read_fields(&resolved.provider_refs).await
    }
}

#[async_trait]
impl<P> CredentialBroker for CredentialBrokerCore<P>
where
    P: CredentialSecretProvider,
{
    async fn request_fill(&self, request: CredentialFillRequest) -> Result<CredentialFillResponse> {
        let requested_fields = CredentialFieldSelection::from_selectors(
            request.username_selector.as_deref(),
            request.password_selector.as_deref(),
        );
        let decision = self.policy.evaluate_request_for_fields(
            &request.alias,
            &request.observed_origin,
            request.expected_origin.as_deref(),
            requested_fields,
        )?;
        let status = if matches!(self.mode, CredentialBrokerMode::Disabled) {
            CredentialFillStatus::Unavailable
        } else {
            decision.status
        };
        Ok(CredentialFillResponse {
            request_id: request.request_id,
            session_id: request.session_id,
            alias: safe_or_redacted_alias(&request.alias),
            observed_origin: decision.normalized_origin,
            status,
            broker: self.mode,
            audit_id: request.request_id,
            privacy_guard: self.privacy_guard,
            redacted_message: decision.redacted_message,
        })
    }
}

#[derive(Debug, Clone, Copy, Default)]
pub struct FakeCredentialBroker;

#[async_trait]
impl CredentialBroker for FakeCredentialBroker {
    async fn request_fill(&self, request: CredentialFillRequest) -> Result<CredentialFillResponse> {
        let normalized_origin = normalize_origin(&request.observed_origin)
            .map(|origin| origin.as_string())
            .unwrap_or_else(|_| REDACTED.to_string());
        Ok(CredentialFillResponse {
            request_id: request.request_id,
            session_id: request.session_id,
            alias: safe_or_redacted_alias(&request.alias),
            observed_origin: normalized_origin,
            status: CredentialFillStatus::RequiresUserApproval,
            broker: CredentialBrokerMode::FakeStatusOnly,
            audit_id: request.request_id,
            privacy_guard: true,
            redacted_message: Some(REDACTED.to_string()),
        })
    }
}

#[derive(Clone, Deserialize)]
pub struct CredentialPolicy {
    pub aliases: BTreeMap<String, CredentialAliasPolicy>,
}

impl fmt::Debug for CredentialPolicy {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("CredentialPolicy")
            .field("aliases", &self.aliases.keys().collect::<Vec<_>>())
            .finish()
    }
}

impl CredentialPolicy {
    pub fn from_json_str(json: &str) -> Result<Self> {
        let policy: Self = serde_json::from_str(json).map_err(|error| anyhow!(error))?;
        policy.validate()?;
        Ok(policy)
    }

    pub fn evaluate_request(
        &self,
        alias: &str,
        observed_origin: &str,
        expected_origin: Option<&str>,
    ) -> Result<CredentialPolicyDecision> {
        self.evaluate_request_for_fields(
            alias,
            observed_origin,
            expected_origin,
            CredentialFieldSelection::both(),
        )
    }

    pub fn evaluate_request_for_fields(
        &self,
        alias: &str,
        observed_origin: &str,
        expected_origin: Option<&str>,
        requested_fields: CredentialFieldSelection,
    ) -> Result<CredentialPolicyDecision> {
        if !is_safe_alias(alias) {
            return Ok(CredentialPolicyDecision::blocked(
                CredentialFillStatus::PolicyBlocked,
                REDACTED,
            ));
        }

        let Some(alias_policy) = self.aliases.get(alias) else {
            return Ok(CredentialPolicyDecision::blocked(
                CredentialFillStatus::PolicyBlocked,
                "unknown_alias",
            ));
        };

        let observed = match normalize_origin(observed_origin) {
            Ok(origin) => origin,
            Err(_) => {
                return Ok(CredentialPolicyDecision::blocked(
                    CredentialFillStatus::PolicyBlocked,
                    "invalid_observed_origin",
                ));
            }
        };

        if let Some(expected_origin) = expected_origin {
            match normalize_origin(expected_origin) {
                Ok(expected) if expected == observed => {}
                Ok(_) => {
                    return Ok(CredentialPolicyDecision::blocked(
                        CredentialFillStatus::OriginMismatch,
                        "expected_origin_mismatch",
                    ));
                }
                Err(_) => {
                    return Ok(CredentialPolicyDecision::blocked(
                        CredentialFillStatus::PolicyBlocked,
                        "invalid_expected_origin",
                    ));
                }
            }
        }

        if !alias_policy.allowed_origin_matches(&observed) {
            return Ok(CredentialPolicyDecision::blocked(
                CredentialFillStatus::OriginMismatch,
                "origin_not_allowed",
            ));
        }

        if let Some(message) = alias_policy.blocked_field_reason(requested_fields) {
            return Ok(CredentialPolicyDecision::blocked(
                CredentialFillStatus::PolicyBlocked,
                message,
            ));
        }

        Ok(CredentialPolicyDecision {
            status: CredentialFillStatus::RequiresUserApproval,
            alias: alias.to_string(),
            normalized_origin: observed.as_string(),
            redacted_message: Some("requires_user_approval".to_string()),
        })
    }

    fn resolve_for_approved_use(
        &self,
        alias: &str,
        observed_origin: &str,
        requested_fields: CredentialFieldSelection,
    ) -> Result<CredentialPolicyMatch> {
        let decision =
            self.evaluate_request_for_fields(alias, observed_origin, None, requested_fields)?;
        if decision.status != CredentialFillStatus::RequiresUserApproval {
            return Err(anyhow!("credential policy denied approved read"));
        }
        let alias_policy = self
            .aliases
            .get(alias)
            .ok_or_else(|| anyhow!("credential alias unavailable"))?;
        Ok(CredentialPolicyMatch {
            alias: decision.alias,
            normalized_origin: decision.normalized_origin,
            provider_refs: alias_policy.provider_refs.scoped_to(requested_fields),
        })
    }

    fn validate(&self) -> Result<()> {
        if self.aliases.is_empty() {
            return Err(anyhow!("credential policy must contain at least one alias"));
        }
        for (alias, policy) in &self.aliases {
            if !is_safe_alias(alias) {
                return Err(anyhow!("credential policy contains unsafe alias"));
            }
            if policy.allowed_origins.is_empty() {
                return Err(anyhow!("credential policy alias has no allowed origins"));
            }
            for origin in &policy.allowed_origins {
                normalize_origin(origin)?;
            }
            policy.validate()?;
        }
        Ok(())
    }
}

#[derive(Clone, Deserialize)]
pub struct CredentialAliasPolicy {
    pub allowed_origins: Vec<String>,
    pub provider_refs: CredentialProviderRefs,
    #[serde(default)]
    pub allowed_fields: Vec<CredentialFieldKind>,
}

impl fmt::Debug for CredentialAliasPolicy {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("CredentialAliasPolicy")
            .field("allowed_origins", &self.allowed_origins)
            .field("provider_refs", &REDACTED)
            .field("allowed_fields", &self.allowed_fields)
            .finish()
    }
}

impl CredentialAliasPolicy {
    fn allowed_origin_matches(&self, observed: &NormalizedOrigin) -> bool {
        self.allowed_origins
            .iter()
            .filter_map(|origin| normalize_origin(origin).ok())
            .any(|allowed| allowed == *observed)
    }

    fn validate(&self) -> Result<()> {
        let has_username = self.provider_refs.username.is_some();
        let has_password = self.provider_refs.password.is_some();
        if !has_username && !has_password {
            return Err(anyhow!(
                "credential policy alias has no fillable provider refs"
            ));
        }
        if self.allowed_fields.is_empty() {
            return Err(anyhow!("credential policy alias has no allowed fields"));
        }
        let mut allowed_fields = HashSet::new();
        for field in &self.allowed_fields {
            if !matches!(
                field,
                CredentialFieldKind::Username | CredentialFieldKind::Password
            ) {
                return Err(anyhow!(
                    "credential policy field kind is not fill-only safe"
                ));
            }
            allowed_fields.insert(*field);
        }
        if allowed_fields.contains(&CredentialFieldKind::Username) && !has_username {
            return Err(anyhow!(
                "credential policy allows username without a username provider ref"
            ));
        }
        if allowed_fields.contains(&CredentialFieldKind::Password) && !has_password {
            return Err(anyhow!(
                "credential policy allows password without a password provider ref"
            ));
        }
        Ok(())
    }

    fn blocked_field_reason(&self, fields: CredentialFieldSelection) -> Option<&'static str> {
        if fields.is_empty() {
            return Some("no_requested_fields");
        }
        let allowed_fields: HashSet<_> = self.allowed_fields.iter().copied().collect();
        if fields.username() && !allowed_fields.contains(&CredentialFieldKind::Username) {
            return Some("username_not_allowed");
        }
        if fields.password() && !allowed_fields.contains(&CredentialFieldKind::Password) {
            return Some("password_not_allowed");
        }
        if !self.provider_refs.has_requested_fields(fields) {
            return Some("provider_ref_unavailable");
        }
        None
    }
}

#[derive(Clone, Deserialize)]
pub struct CredentialProviderRefs {
    #[serde(default)]
    pub username: Option<PrivateProviderRef>,
    #[serde(default)]
    pub password: Option<PrivateProviderRef>,
}

impl CredentialProviderRefs {
    fn scoped_to(&self, fields: CredentialFieldSelection) -> Self {
        Self {
            username: fields.username().then(|| self.username.clone()).flatten(),
            password: fields.password().then(|| self.password.clone()).flatten(),
        }
    }

    fn has_requested_fields(&self, fields: CredentialFieldSelection) -> bool {
        (!fields.username() || self.username.is_some())
            && (!fields.password() || self.password.is_some())
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct CredentialFieldSelection {
    username: bool,
    password: bool,
}

impl CredentialFieldSelection {
    pub fn from_selectors(
        username_selector: Option<&str>,
        password_selector: Option<&str>,
    ) -> Self {
        Self {
            username: username_selector.is_some(),
            password: password_selector.is_some(),
        }
    }

    pub fn both() -> Self {
        Self {
            username: true,
            password: true,
        }
    }

    pub fn username_only() -> Self {
        Self {
            username: true,
            password: false,
        }
    }

    pub fn password_only() -> Self {
        Self {
            username: false,
            password: true,
        }
    }

    pub fn is_empty(self) -> bool {
        !self.username && !self.password
    }

    pub fn username(self) -> bool {
        self.username
    }

    pub fn password(self) -> bool {
        self.password
    }
}

impl fmt::Debug for CredentialProviderRefs {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("CredentialProviderRefs")
            .field("username", &redacted_presence(self.username.as_ref()))
            .field("password", &redacted_presence(self.password.as_ref()))
            .finish()
    }
}

#[derive(Debug, Clone, Copy, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum CredentialFieldKind {
    Username,
    Password,
    Otp,
    Totp,
    Card,
    Cvv,
    Passkey,
    Mfa,
}

#[derive(Clone, PartialEq, Eq)]
pub struct PrivateProviderRef(String);

impl PrivateProviderRef {
    fn new(value: String) -> Result<Self> {
        if value.trim().is_empty() {
            return Err(anyhow!("credential provider ref is empty"));
        }
        Ok(Self(value))
    }

    fn expose_for_provider(&self) -> &str {
        &self.0
    }

    #[cfg(test)]
    pub fn new_for_test(value: &str) -> Self {
        Self::new(value.to_string()).unwrap()
    }
}

impl fmt::Debug for PrivateProviderRef {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(REDACTED)
    }
}

impl<'de> Deserialize<'de> for PrivateProviderRef {
    fn deserialize<D>(deserializer: D) -> std::result::Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let value = String::deserialize(deserializer)?;
        Self::new(value).map_err(de::Error::custom)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CredentialPolicyDecision {
    pub status: CredentialFillStatus,
    pub alias: String,
    pub normalized_origin: String,
    pub redacted_message: Option<String>,
}

impl CredentialPolicyDecision {
    fn blocked(status: CredentialFillStatus, message: &str) -> Self {
        Self {
            status,
            alias: REDACTED.to_string(),
            normalized_origin: REDACTED.to_string(),
            redacted_message: Some(redact_status_message(message)),
        }
    }
}

#[derive(Clone)]
pub struct CredentialPolicyMatch {
    pub alias: String,
    pub normalized_origin: String,
    pub provider_refs: CredentialProviderRefs,
}

impl fmt::Debug for CredentialPolicyMatch {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("CredentialPolicyMatch")
            .field("alias", &self.alias)
            .field("normalized_origin", &self.normalized_origin)
            .field("provider_refs", &REDACTED)
            .finish()
    }
}

#[derive(Clone)]
pub struct CredentialSecretBundle {
    pub username: Option<SecretValue>,
    pub password: Option<SecretValue>,
}

impl CredentialSecretBundle {
    pub fn from_plaintext_for_mock(username: &str, password: &str) -> Self {
        Self {
            username: Some(SecretValue::from_bytes(username.as_bytes().to_vec())),
            password: Some(SecretValue::from_bytes(password.as_bytes().to_vec())),
        }
    }

    #[cfg(test)]
    pub fn synthetic_for_tests(username: &str, password: &str) -> Self {
        Self::from_plaintext_for_mock(username, password)
    }
}

impl fmt::Debug for CredentialSecretBundle {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("CredentialSecretBundle")
            .field("username", &redacted_presence(self.username.as_ref()))
            .field("password", &redacted_presence(self.password.as_ref()))
            .finish()
    }
}

#[derive(Clone, PartialEq, Eq)]
pub struct SecretValue {
    bytes: Vec<u8>,
}

impl SecretValue {
    fn from_bytes(mut bytes: Vec<u8>) -> Self {
        while bytes
            .last()
            .is_some_and(|byte| matches!(byte, b'\n' | b'\r'))
        {
            bytes.pop();
        }
        Self { bytes }
    }

    #[allow(dead_code)]
    pub(crate) fn expose_for_fill_executor(&self) -> Result<&str> {
        std::str::from_utf8(&self.bytes)
            .map_err(|_| anyhow!("credential secret is not valid utf-8"))
    }
}

impl fmt::Debug for SecretValue {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(REDACTED)
    }
}

impl Drop for SecretValue {
    fn drop(&mut self) {
        for byte in &mut self.bytes {
            *byte = 0;
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CredentialProviderError {
    status: CredentialFillStatus,
    class: &'static str,
}

impl CredentialProviderError {
    fn new(status: CredentialFillStatus, class: &'static str) -> Self {
        Self { status, class }
    }

    fn policy_blocked() -> Self {
        Self::new(CredentialFillStatus::PolicyBlocked, "policy_blocked")
    }

    fn provider_not_enabled() -> Self {
        Self::new(CredentialFillStatus::Unavailable, "provider_not_enabled")
    }

    pub fn provider_not_enabled_for_runtime() -> Self {
        Self::provider_not_enabled()
    }

    fn provider_unavailable() -> Self {
        Self::new(CredentialFillStatus::Unavailable, "provider_unavailable")
    }

    pub fn provider_unavailable_for_runtime() -> Self {
        Self::provider_unavailable()
    }

    fn provider_timeout() -> Self {
        Self::new(CredentialFillStatus::Failed, "provider_timeout")
    }

    fn provider_failed() -> Self {
        Self::new(CredentialFillStatus::Failed, "provider_failed")
    }

    pub fn status(&self) -> CredentialFillStatus {
        self.status
    }
}

impl fmt::Display for CredentialProviderError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(self.class)
    }
}

impl std::error::Error for CredentialProviderError {}

#[derive(Clone)]
pub struct MockCredentialProvider {
    bundle: CredentialSecretBundle,
    read_count: Arc<std::sync::atomic::AtomicUsize>,
}

impl MockCredentialProvider {
    pub fn runtime_default() -> Self {
        Self::new(CredentialSecretBundle::from_plaintext_for_mock(
            "mock-username",
            "mock-password",
        ))
    }

    pub fn new(bundle: CredentialSecretBundle) -> Self {
        Self {
            bundle,
            read_count: Arc::new(std::sync::atomic::AtomicUsize::new(0)),
        }
    }

    pub fn read_count(&self) -> usize {
        self.read_count.load(std::sync::atomic::Ordering::SeqCst)
    }
}

impl fmt::Debug for MockCredentialProvider {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("MockCredentialProvider")
            .field("bundle", &REDACTED)
            .field("read_count", &self.read_count())
            .finish()
    }
}

#[async_trait]
impl CredentialSecretProvider for MockCredentialProvider {
    async fn read_fields(
        &self,
        _provider_refs: &CredentialProviderRefs,
    ) -> std::result::Result<CredentialSecretBundle, CredentialProviderError> {
        self.read_count
            .fetch_add(1, std::sync::atomic::Ordering::SeqCst);
        Ok(self.bundle.clone())
    }
}

#[derive(Clone)]
pub struct OnePasswordCliProvider {
    op_path: PathBuf,
    timeout: Duration,
    executor: Arc<dyn OpExecutor>,
}

impl OnePasswordCliProvider {
    pub fn new(op_path: PathBuf, timeout: Duration) -> Self {
        Self::with_executor(op_path, timeout, TokioOpExecutor)
    }

    pub fn with_executor<E>(op_path: PathBuf, timeout: Duration, executor: E) -> Self
    where
        E: OpExecutor + 'static,
    {
        Self {
            op_path,
            timeout,
            executor: Arc::new(executor),
        }
    }

    async fn read_secret(
        &self,
        provider_ref: &PrivateProviderRef,
    ) -> std::result::Result<SecretValue, CredentialProviderError> {
        self.executor
            .read_secret(&self.op_path, provider_ref, self.timeout)
            .await
    }

    #[cfg(test)]
    pub async fn read_secret_for_test(
        &self,
        provider_ref: PrivateProviderRef,
    ) -> std::result::Result<SecretValue, CredentialProviderError> {
        self.read_secret(&provider_ref).await
    }
}

impl fmt::Debug for OnePasswordCliProvider {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("OnePasswordCliProvider")
            .field("op_path", &self.op_path)
            .field("timeout", &self.timeout)
            .field("executor", &"argv_only")
            .finish()
    }
}

#[async_trait]
impl CredentialSecretProvider for OnePasswordCliProvider {
    async fn read_fields(
        &self,
        provider_refs: &CredentialProviderRefs,
    ) -> std::result::Result<CredentialSecretBundle, CredentialProviderError> {
        let username = match &provider_refs.username {
            Some(provider_ref) => Some(self.read_secret(provider_ref).await?),
            None => None,
        };
        let password = match &provider_refs.password {
            Some(provider_ref) => Some(self.read_secret(provider_ref).await?),
            None => None,
        };
        Ok(CredentialSecretBundle { username, password })
    }
}

#[async_trait]
pub trait OpExecutor: Send + Sync {
    async fn read_secret(
        &self,
        op_path: &Path,
        provider_ref: &PrivateProviderRef,
        timeout: Duration,
    ) -> std::result::Result<SecretValue, CredentialProviderError>;
}

#[derive(Debug, Clone, Copy)]
pub struct TokioOpExecutor;

#[async_trait]
impl OpExecutor for TokioOpExecutor {
    async fn read_secret(
        &self,
        op_path: &Path,
        provider_ref: &PrivateProviderRef,
        timeout: Duration,
    ) -> std::result::Result<SecretValue, CredentialProviderError> {
        let mut command = Command::new(op_path);
        command
            .arg("read")
            .arg("--no-newline")
            .arg(provider_ref.expose_for_provider());
        command.env_clear();
        for (key, value) in env::vars_os() {
            if provider_env_allowed(&key) {
                command.env(key, value);
            }
        }
        command
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true);

        let mut child = command
            .spawn()
            .map_err(|_| CredentialProviderError::provider_unavailable())?;
        let mut stdout = child
            .stdout
            .take()
            .ok_or_else(CredentialProviderError::provider_unavailable)?;
        let mut stderr = child
            .stderr
            .take()
            .ok_or_else(CredentialProviderError::provider_unavailable)?;
        let stdout_task = tokio::spawn(async move {
            let mut buffer = Vec::new();
            stdout.read_to_end(&mut buffer).await.map(|_| buffer)
        });
        let stderr_task = tokio::spawn(async move {
            let mut buffer = Vec::new();
            stderr.read_to_end(&mut buffer).await.map(|_| buffer)
        });

        let status = match tokio::time::timeout(timeout, child.wait()).await {
            Ok(Ok(status)) => status,
            Ok(Err(_)) => {
                stdout_task.abort();
                stderr_task.abort();
                return Err(CredentialProviderError::provider_unavailable());
            }
            Err(_) => {
                let _ = child.start_kill();
                let _ = child.wait().await;
                let _ = stdout_task.await;
                let _ = stderr_task.await;
                return Err(CredentialProviderError::provider_timeout());
            }
        };
        let stdout = collect_op_pipe(stdout_task).await?;
        let stderr = collect_op_pipe(stderr_task).await?;

        if status.success() {
            if stdout.is_empty() {
                return Err(CredentialProviderError::new(
                    CredentialFillStatus::NoMatch,
                    "no_match",
                ));
            }
            return Ok(SecretValue::from_bytes(stdout));
        }

        Err(classify_provider_failure(&stderr))
    }
}

async fn collect_op_pipe(
    task: tokio::task::JoinHandle<std::io::Result<Vec<u8>>>,
) -> std::result::Result<Vec<u8>, CredentialProviderError> {
    task.await
        .map_err(|_| CredentialProviderError::provider_failed())?
        .map_err(|_| CredentialProviderError::provider_failed())
}

#[cfg(test)]
#[derive(Clone)]
pub struct RecordingOpExecutor {
    result: Arc<std::sync::Mutex<std::result::Result<Vec<u8>, CredentialProviderError>>>,
    invocations: Arc<std::sync::Mutex<Vec<ObservedOpInvocation>>>,
}

#[cfg(test)]
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ObservedOpInvocation {
    pub program: String,
    pub args: Vec<String>,
    pub used_shell: bool,
}

#[cfg(test)]
impl RecordingOpExecutor {
    pub fn success(stdout: &str) -> Self {
        Self {
            result: Arc::new(std::sync::Mutex::new(Ok(stdout.as_bytes().to_vec()))),
            invocations: Arc::new(std::sync::Mutex::new(Vec::new())),
        }
    }

    pub fn failure(status: CredentialFillStatus, _stdout: &str, _stderr: &str) -> Self {
        Self {
            result: Arc::new(std::sync::Mutex::new(Err(CredentialProviderError::new(
                status,
                status_class(status),
            )))),
            invocations: Arc::new(std::sync::Mutex::new(Vec::new())),
        }
    }

    pub fn observed_invocations(&self) -> Vec<ObservedOpInvocation> {
        self.invocations.lock().unwrap().clone()
    }
}

#[cfg(test)]
#[async_trait]
impl OpExecutor for RecordingOpExecutor {
    async fn read_secret(
        &self,
        op_path: &Path,
        _provider_ref: &PrivateProviderRef,
        _timeout: Duration,
    ) -> std::result::Result<SecretValue, CredentialProviderError> {
        self.invocations.lock().unwrap().push(ObservedOpInvocation {
            program: op_path.display().to_string(),
            args: vec![
                "read".to_string(),
                "--no-newline".to_string(),
                REDACTED.to_string(),
            ],
            used_shell: false,
        });
        match self.result.lock().unwrap().clone() {
            Ok(bytes) => Ok(SecretValue::from_bytes(bytes)),
            Err(error) => Err(error),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct NormalizedOrigin {
    scheme: String,
    host: String,
    port: u16,
}

impl NormalizedOrigin {
    fn as_string(&self) -> String {
        format!("{}://{}:{}", self.scheme, self.host, self.port)
    }
}

fn normalize_origin(value: &str) -> Result<NormalizedOrigin> {
    let trimmed = value.trim();
    if trimmed.is_empty() || trimmed.contains('*') {
        return Err(anyhow!("invalid credential origin"));
    }

    let parsed = Url::parse(trimmed).map_err(|_| anyhow!("invalid credential origin"))?;
    let scheme = parsed.scheme().to_ascii_lowercase();
    if !matches!(scheme.as_str(), "http" | "https") {
        return Err(anyhow!("unsupported credential origin scheme"));
    }
    let host = parsed
        .host_str()
        .ok_or_else(|| anyhow!("credential origin is missing host"))?
        .to_ascii_lowercase();
    if host.contains('*') {
        return Err(anyhow!("invalid credential origin host"));
    }
    let port = parsed
        .port_or_known_default()
        .ok_or_else(|| anyhow!("credential origin is missing port"))?;

    Ok(NormalizedOrigin { scheme, host, port })
}

fn provider_env_allowed(key: &std::ffi::OsStr) -> bool {
    let Some(key) = key.to_str() else {
        return false;
    };
    matches!(
        key,
        "HOME"
            | "PATH"
            | "LANG"
            | "LC_ALL"
            | "XDG_CONFIG_HOME"
            | "XDG_CACHE_HOME"
            | "XDG_DATA_HOME"
            | "OP_SERVICE_ACCOUNT_TOKEN"
    ) || key.starts_with("OP_SESSION_")
}

fn classify_provider_failure(stderr: &[u8]) -> CredentialProviderError {
    let stderr = String::from_utf8_lossy(stderr).to_ascii_lowercase();
    if stderr.contains("sign in")
        || stderr.contains("signin")
        || stderr.contains("authentication")
        || stderr.contains("unauthorized")
        || stderr.contains("locked")
        || stderr.contains("session")
    {
        return CredentialProviderError::new(
            CredentialFillStatus::UnlockRequired,
            "unlock_required",
        );
    }
    if stderr.contains("not found") || stderr.contains("could not find") {
        return CredentialProviderError::new(CredentialFillStatus::NoMatch, "no_match");
    }
    CredentialProviderError::new(CredentialFillStatus::Failed, "provider_failed")
}

#[cfg(test)]
fn status_class(status: CredentialFillStatus) -> &'static str {
    match status {
        CredentialFillStatus::Unavailable => "provider_unavailable",
        CredentialFillStatus::RequiresUserApproval => "requires_user_approval",
        CredentialFillStatus::Pending => "pending",
        CredentialFillStatus::Approved => "approved",
        CredentialFillStatus::Filled => "filled",
        CredentialFillStatus::Denied => "denied",
        CredentialFillStatus::NoMatch => "no_match",
        CredentialFillStatus::OriginMismatch => "origin_mismatch",
        CredentialFillStatus::PolicyBlocked => "policy_blocked",
        CredentialFillStatus::UnlockRequired => "unlock_required",
        CredentialFillStatus::ProviderLocked => "provider_locked",
        CredentialFillStatus::Failed => "failed",
        CredentialFillStatus::PrivacyGuardActive => "privacy_guard_active",
    }
}

fn is_safe_alias(alias: &str) -> bool {
    !alias.is_empty()
        && alias.len() <= 128
        && alias
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'-' | b'.'))
}

fn safe_or_redacted_alias(alias: &str) -> String {
    if is_safe_alias(alias) {
        alias.to_string()
    } else {
        REDACTED.to_string()
    }
}

fn redacted_option(value: &Option<String>) -> Option<String> {
    value.as_deref().map(|text| {
        let redacted = redact_text(text);
        if redacted == text {
            REDACTED.to_string()
        } else {
            redacted
        }
    })
}

fn redacted_presence<T>(value: Option<&T>) -> &'static str {
    if value.is_some() { REDACTED } else { "none" }
}

fn redact_status_message(message: &str) -> String {
    let redacted = redact_text(message);
    if redacted == message {
        message.to_string()
    } else {
        REDACTED.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::OnceLock;
    use uuid::Uuid;

    fn synthetic_op_exec_test_lock() -> &'static tokio::sync::Mutex<()> {
        static LOCK: OnceLock<tokio::sync::Mutex<()>> = OnceLock::new();
        LOCK.get_or_init(|| tokio::sync::Mutex::new(()))
    }

    fn policy_json_with_canaries() -> String {
        let provider_prefix = format!("{}{}", "op", "://synthetic-vault/synthetic-item");
        serde_json::json!({
            "aliases": {
                "tailor_login": {
                    "allowed_origins": ["https://www.sonofatailor.com", "https://example.test:443"],
                    "provider_refs": {
                        "username": format!("{provider_prefix}/username"),
                        "password": format!("{provider_prefix}/password")
                    },
                    "allowed_fields": ["username", "password"]
                }
            }
        })
        .to_string()
    }

    #[test]
    fn credential_policy_requires_exact_normalized_origins_and_safe_aliases() {
        let policy = CredentialPolicy::from_json_str(&policy_json_with_canaries()).unwrap();

        let allowed = policy
            .evaluate_request(
                "tailor_login",
                "https://www.sonofatailor.com/login",
                Some("https://www.sonofatailor.com"),
            )
            .unwrap();
        assert_eq!(allowed.status, CredentialFillStatus::RequiresUserApproval);
        assert_eq!(
            allowed.normalized_origin,
            "https://www.sonofatailor.com:443"
        );

        let default_port = policy
            .evaluate_request(
                "tailor_login",
                "https://example.test",
                Some("https://example.test:443"),
            )
            .unwrap();
        assert_eq!(
            default_port.status,
            CredentialFillStatus::RequiresUserApproval
        );

        let subdomain = policy
            .evaluate_request("tailor_login", "https://login.sonofatailor.com", None)
            .unwrap();
        assert_eq!(subdomain.status, CredentialFillStatus::OriginMismatch);

        let wrong_scheme = policy
            .evaluate_request("tailor_login", "http://www.sonofatailor.com", None)
            .unwrap();
        assert_eq!(wrong_scheme.status, CredentialFillStatus::OriginMismatch);

        let wildcard_policy = serde_json::json!({
            "aliases": {
                "bad": {
                    "allowed_origins": ["https://*.example.test"],
                    "provider_refs": {"password": "synthetic-ref"},
                    "allowed_fields": ["password"]
                }
            }
        })
        .to_string();
        assert!(CredentialPolicy::from_json_str(&wildcard_policy).is_err());
    }

    #[tokio::test]
    async fn broker_core_returns_status_only_and_never_calls_provider_before_approval() {
        let policy = CredentialPolicy::from_json_str(&policy_json_with_canaries()).unwrap();
        let provider = MockCredentialProvider::new(CredentialSecretBundle::synthetic_for_tests(
            "synthetic-user-canary",
            "synthetic-password-canary",
        ));
        let broker =
            CredentialBrokerCore::new(CredentialBrokerMode::Mock, policy, provider.clone());
        let response = broker
            .request_fill(CredentialFillRequest {
                request_id: Uuid::nil(),
                session_id: Uuid::nil(),
                alias: "tailor_login".into(),
                username_selector: Some("input[name=email]".into()),
                password_selector: Some("input[type=password]".into()),
                purpose: Some("login only".into()),
                observed_origin: "https://www.sonofatailor.com/login".into(),
                expected_origin: Some("https://www.sonofatailor.com".into()),
            })
            .await
            .unwrap();

        assert_eq!(response.status, CredentialFillStatus::RequiresUserApproval);
        assert_eq!(response.broker, CredentialBrokerMode::Mock);
        assert_eq!(response.audit_id, Uuid::nil());
        assert_eq!(provider.read_count(), 0);

        let serialized = serde_json::to_string(&response).unwrap();
        for forbidden in [
            "synthetic-user-canary",
            "synthetic-password-canary",
            "synthetic-vault",
            "synthetic-item",
            "input[type=password]",
            "provider_refs",
        ] {
            assert!(!serialized.contains(forbidden));
        }

        let event = response.audit_event("credential_fill_requested");
        let serialized_event = serde_json::to_string(&event).unwrap();
        let tempdir = tempfile::tempdir().unwrap();
        let event_path = tempdir.path().join("credential-events.jsonl");
        std::fs::write(&event_path, format!("{serialized_event}\n")).unwrap();
        let persisted_event = std::fs::read_to_string(event_path).unwrap();
        for forbidden in [
            "synthetic-user-canary",
            "synthetic-password-canary",
            "synthetic-vault",
            "synthetic-item",
            "input[type=password]",
            "provider_refs",
        ] {
            assert!(!persisted_event.contains(forbidden));
        }
    }

    #[tokio::test]
    async fn onepassword_provider_sanitizes_failures_and_secret_debug_output() {
        let executor = RecordingOpExecutor::failure(
            CredentialFillStatus::UnlockRequired,
            "provider stdout synthetic-secret-canary",
            "provider stderr synthetic-token-canary",
        );
        let provider = OnePasswordCliProvider::with_executor(
            "/usr/bin/op".into(),
            std::time::Duration::from_millis(50),
            executor.clone(),
        );

        let err = provider
            .read_secret_for_test(PrivateProviderRef::new_for_test(
                "synthetic-provider-ref-canary",
            ))
            .await
            .unwrap_err();
        assert_eq!(err.status(), CredentialFillStatus::UnlockRequired);
        let text = format!("{err:?} {err}");
        for forbidden in [
            "synthetic-secret-canary",
            "synthetic-token-canary",
            "synthetic-provider-ref-canary",
            "stdout",
            "stderr",
        ] {
            assert!(!text.contains(forbidden));
        }

        let observed = executor.observed_invocations();
        assert_eq!(observed.len(), 1);
        assert_eq!(observed[0].args, ["read", "--no-newline", "[REDACTED]"]);
        assert!(!observed[0].used_shell);
    }

    #[tokio::test]
    async fn approved_executor_reads_fail_closed_without_enabled_mode() {
        let policy = CredentialPolicy::from_json_str(&policy_json_with_canaries()).unwrap();
        let provider = MockCredentialProvider::new(CredentialSecretBundle::synthetic_for_tests(
            "synthetic-user-canary",
            "synthetic-password-canary",
        ));
        let approval = ApprovedCredentialFill::from_approved_state(
            Uuid::nil(),
            Uuid::nil(),
            "tailor_login",
            "https://www.sonofatailor.com/login",
            Some("login only".to_string()),
            CredentialFillStatus::Approved,
        )
        .unwrap();

        for mode in [
            CredentialBrokerMode::Disabled,
            CredentialBrokerMode::FakeStatusOnly,
        ] {
            let broker = CredentialBrokerCore::new(mode, policy.clone(), provider.clone());
            let err = broker
                .read_approved_fields_for_executor(&approval)
                .await
                .unwrap_err();
            assert_eq!(err.status(), CredentialFillStatus::Unavailable);
        }

        assert_eq!(provider.read_count(), 0);
    }

    #[tokio::test]
    async fn onepassword_cli_requires_approved_fill_state_before_reading_provider() {
        let policy = CredentialPolicy::from_json_str(&policy_json_with_canaries()).unwrap();
        let provider = MockCredentialProvider::new(CredentialSecretBundle::synthetic_for_tests(
            "synthetic-user-canary",
            "synthetic-password-canary",
        ));
        let broker = CredentialBrokerCore::new(
            CredentialBrokerMode::OnePasswordCli,
            policy,
            provider.clone(),
        );

        let response = broker
            .request_fill(CredentialFillRequest {
                request_id: Uuid::nil(),
                session_id: Uuid::nil(),
                alias: "tailor_login".into(),
                username_selector: Some("input[name=email]".into()),
                password_selector: Some("input[type=password]".into()),
                purpose: Some("login only".into()),
                observed_origin: "https://www.sonofatailor.com/login".into(),
                expected_origin: Some("https://www.sonofatailor.com".into()),
            })
            .await
            .unwrap();

        assert_eq!(response.status, CredentialFillStatus::RequiresUserApproval);
        assert_eq!(provider.read_count(), 0);

        let pending_state = ApprovedCredentialFill::from_approved_state(
            response.request_id,
            response.session_id,
            &response.alias,
            &response.observed_origin,
            Some("login only".to_string()),
            response.status,
        );
        assert!(pending_state.is_err());
        assert_eq!(provider.read_count(), 0);

        let approval = ApprovedCredentialFill::from_approved_state(
            response.request_id,
            response.session_id,
            &response.alias,
            &response.observed_origin,
            Some("login only".to_string()),
            CredentialFillStatus::Approved,
        )
        .unwrap();
        let bundle = broker
            .read_approved_fields_for_executor(&approval)
            .await
            .unwrap();

        assert_eq!(provider.read_count(), 1);
        assert_eq!(
            bundle.username.unwrap().expose_for_fill_executor().unwrap(),
            "synthetic-user-canary"
        );
        assert_eq!(
            bundle.password.unwrap().expose_for_fill_executor().unwrap(),
            "synthetic-password-canary"
        );
    }

    #[tokio::test]
    async fn approved_executor_reads_only_requested_approved_fields() {
        let policy = CredentialPolicy::from_json_str(&policy_json_with_canaries()).unwrap();
        let executor = RecordingOpExecutor::success("synthetic-op-secret\n");
        let provider = OnePasswordCliProvider::with_executor(
            PathBuf::from("/usr/bin/op"),
            Duration::from_secs(5),
            executor.clone(),
        );
        let broker =
            CredentialBrokerCore::new(CredentialBrokerMode::OnePasswordCli, policy, provider);

        async fn read_for_selection(
            broker: &CredentialBrokerCore<OnePasswordCliProvider>,
            selection: CredentialFieldSelection,
        ) -> CredentialSecretBundle {
            let approval = ApprovedCredentialFill::from_approved_state_for_fields(
                Uuid::new_v4(),
                Uuid::new_v4(),
                "tailor_login",
                "https://www.sonofatailor.com/login",
                Some("operator approved scoped read".to_string()),
                CredentialFillStatus::Approved,
                selection,
            )
            .unwrap();
            broker
                .read_approved_fields_for_executor(&approval)
                .await
                .unwrap()
        }

        let username_only = read_for_selection(
            &broker,
            CredentialFieldSelection {
                username: true,
                password: false,
            },
        )
        .await;
        assert!(username_only.username.is_some());
        assert!(username_only.password.is_none());
        assert_eq!(executor.observed_invocations().len(), 1);

        let password_only = read_for_selection(
            &broker,
            CredentialFieldSelection {
                username: false,
                password: true,
            },
        )
        .await;
        assert!(password_only.username.is_none());
        assert!(password_only.password.is_some());
        assert_eq!(executor.observed_invocations().len(), 2);

        let both = read_for_selection(&broker, CredentialFieldSelection::both()).await;
        assert!(both.username.is_some());
        assert!(both.password.is_some());
        assert_eq!(executor.observed_invocations().len(), 4);
    }

    #[tokio::test]
    async fn credential_debug_and_mode_helpers_are_sanitized() {
        assert_eq!(CredentialBrokerMode::Disabled.to_string(), "disabled");
        assert_eq!(
            CredentialBrokerMode::FakeStatusOnly.to_string(),
            "fake_status_only"
        );
        assert_eq!(CredentialBrokerMode::Mock.to_string(), "mock");
        assert_eq!(
            CredentialBrokerMode::OnePasswordCli.to_string(),
            "onepassword_cli"
        );
        assert_eq!(
            "fake".parse::<CredentialBrokerMode>().unwrap(),
            CredentialBrokerMode::FakeStatusOnly
        );
        assert_eq!(
            "1password_cli".parse::<CredentialBrokerMode>().unwrap(),
            CredentialBrokerMode::OnePasswordCli
        );
        assert!(
            "unsupported"
                .parse::<CredentialBrokerMode>()
                .unwrap_err()
                .contains("unsupported credential provider mode")
        );

        let request = CredentialFillRequest {
            request_id: Uuid::nil(),
            session_id: Uuid::nil(),
            alias: "bad/alias".into(),
            username_selector: Some("input[name=password]".into()),
            password_selector: Some("input[type=password]".into()),
            purpose: Some("credential token synthetic-canary".into()),
            observed_origin: "https://example.test/login".into(),
            expected_origin: None,
        };
        let request_debug = format!("{request:?}");
        assert!(request_debug.contains(REDACTED));
        for forbidden in [
            "bad/alias",
            "input[name=password]",
            "input[type=password]",
            "credential token synthetic-canary",
        ] {
            assert!(!request_debug.contains(forbidden));
        }

        assert_eq!(
            redacted_option(&Some("plain purpose".to_string())),
            Some(REDACTED.to_string())
        );
        assert_eq!(
            redacted_option(&Some("credential token synthetic-canary".to_string())),
            Some(REDACTED.to_string())
        );
        assert_eq!(redacted_option(&None), None);
        assert_eq!(redacted_presence::<SecretValue>(None), "none");
        assert_eq!(
            redact_status_message("credential token synthetic-canary"),
            REDACTED
        );

        let approval = ApprovedCredentialFill::from_approved_state(
            Uuid::nil(),
            Uuid::nil(),
            "tailor_login",
            "https://www.sonofatailor.com/login",
            Some("credential token synthetic-canary".to_string()),
            CredentialFillStatus::Approved,
        )
        .unwrap();
        let approval_debug = format!("{approval:?}");
        assert!(approval_debug.contains("approval_boundary"));
        assert!(!approval_debug.contains("credential token synthetic-canary"));

        let policy = CredentialPolicy::from_json_str(&policy_json_with_canaries()).unwrap();
        let policy_debug = format!("{policy:?}");
        assert!(policy_debug.contains("tailor_login"));
        assert!(!policy_debug.contains("synthetic-vault"));

        let alias_policy = policy.aliases.get("tailor_login").unwrap();
        let alias_policy_debug = format!("{alias_policy:?}");
        assert!(alias_policy_debug.contains("allowed_origins"));
        assert!(!alias_policy_debug.contains("synthetic-vault"));
        let refs_debug = format!("{:?}", alias_policy.provider_refs);
        assert!(refs_debug.contains(REDACTED));
        assert!(!refs_debug.contains("synthetic-vault"));

        let matched = policy
            .resolve_for_approved_use(
                "tailor_login",
                "https://www.sonofatailor.com/login",
                CredentialFieldSelection::both(),
            )
            .expect("origin within policy should resolve");
        let match_debug = format!("{matched:?}");
        assert!(match_debug.contains("tailor_login"));
        assert!(!match_debug.contains("synthetic-vault"));

        let bundle = CredentialSecretBundle::synthetic_for_tests(
            "synthetic-user-canary",
            "synthetic-password-canary",
        );
        let bundle_debug = format!("{bundle:?}");
        assert!(bundle_debug.contains(REDACTED));
        assert!(!bundle_debug.contains("synthetic-user-canary"));
        assert!(!bundle_debug.contains("synthetic-password-canary"));

        let secret = SecretValue::from_bytes(b"synthetic-secret-canary\n\r".to_vec());
        assert_eq!(
            secret.expose_for_fill_executor().unwrap(),
            "synthetic-secret-canary"
        );
        assert_eq!(format!("{secret:?}"), REDACTED);

        let provider_ref =
            PrivateProviderRef::new("synthetic-provider-ref-canary".to_string()).unwrap();
        assert_eq!(format!("{provider_ref:?}"), REDACTED);
        assert!(PrivateProviderRef::new("".to_string()).is_err());

        let mock = MockCredentialProvider::new(CredentialSecretBundle::synthetic_for_tests(
            "synthetic-user-canary",
            "synthetic-password-canary",
        ));
        let mock_debug = format!("{mock:?}");
        assert!(mock_debug.contains("read_count"));
        assert!(!mock_debug.contains("synthetic-password-canary"));

        let op_provider =
            OnePasswordCliProvider::new(PathBuf::from("/synthetic/op"), Duration::from_millis(1));
        let op_debug = format!("{op_provider:?}");
        assert!(op_debug.contains("argv_only"));
        assert!(!op_debug.contains("synthetic-provider-ref-canary"));

        let provider = MockCredentialProvider::new(CredentialSecretBundle::synthetic_for_tests(
            "synthetic-user-canary",
            "synthetic-password-canary",
        ));
        let broker = CredentialBrokerCore::new(CredentialBrokerMode::Mock, policy, provider)
            .with_privacy_guard(false);
        let response = broker
            .request_fill(CredentialFillRequest {
                request_id: Uuid::nil(),
                session_id: Uuid::nil(),
                alias: "tailor_login".into(),
                username_selector: None,
                password_selector: None,
                purpose: None,
                observed_origin: "https://www.sonofatailor.com/login".into(),
                expected_origin: None,
            })
            .await
            .unwrap();
        assert!(!response.privacy_guard);
    }

    #[tokio::test]
    async fn credential_policy_validation_and_approval_failures_are_sanitized() {
        let policy = CredentialPolicy::from_json_str(&policy_json_with_canaries()).unwrap();

        let unsafe_alias = policy
            .evaluate_request("bad/alias", "https://www.sonofatailor.com/login", None)
            .unwrap();
        assert_eq!(unsafe_alias.status, CredentialFillStatus::PolicyBlocked);
        assert_eq!(unsafe_alias.alias, REDACTED);

        let unknown_alias = policy
            .evaluate_request("missing_alias", "https://www.sonofatailor.com/login", None)
            .unwrap();
        assert_eq!(unknown_alias.status, CredentialFillStatus::PolicyBlocked);
        assert_eq!(
            unknown_alias.redacted_message.as_deref(),
            Some("unknown_alias")
        );

        let invalid_observed = policy
            .evaluate_request("tailor_login", "not a url", None)
            .unwrap();
        assert_eq!(invalid_observed.status, CredentialFillStatus::PolicyBlocked);

        let expected_mismatch = policy
            .evaluate_request(
                "tailor_login",
                "https://www.sonofatailor.com/login",
                Some("https://example.test"),
            )
            .unwrap();
        assert_eq!(
            expected_mismatch.status,
            CredentialFillStatus::OriginMismatch
        );

        let invalid_expected = policy
            .evaluate_request(
                "tailor_login",
                "https://www.sonofatailor.com/login",
                Some("not a url"),
            )
            .unwrap();
        assert_eq!(invalid_expected.status, CredentialFillStatus::PolicyBlocked);

        let username_only_policy = CredentialPolicy::from_json_str(
            &serde_json::json!({
                "aliases": {
                    "username_only": {
                        "allowed_origins": ["https://example.test"],
                        "provider_refs": {
                            "username": "op://vault/item/username",
                            "password": "op://vault/item/password"
                        },
                        "allowed_fields": ["username"]
                    }
                }
            })
            .to_string(),
        )
        .unwrap();
        let username_allowed = username_only_policy
            .evaluate_request_for_fields(
                "username_only",
                "https://example.test/login",
                None,
                CredentialFieldSelection {
                    username: true,
                    password: false,
                },
            )
            .unwrap();
        assert_eq!(
            username_allowed.status,
            CredentialFillStatus::RequiresUserApproval
        );
        let password_blocked = username_only_policy
            .evaluate_request_for_fields(
                "username_only",
                "https://example.test/login",
                None,
                CredentialFieldSelection {
                    username: false,
                    password: true,
                },
            )
            .unwrap();
        assert_eq!(password_blocked.status, CredentialFillStatus::PolicyBlocked);

        let provider = MockCredentialProvider::new(CredentialSecretBundle::synthetic_for_tests(
            "synthetic-user-canary",
            "synthetic-password-canary",
        ));
        let broker =
            CredentialBrokerCore::new(CredentialBrokerMode::Mock, policy, provider.clone());
        let unknown_approval = ApprovedCredentialFill::from_approved_state(
            Uuid::nil(),
            Uuid::nil(),
            "missing_alias",
            "https://www.sonofatailor.com/login",
            None,
            CredentialFillStatus::Approved,
        )
        .unwrap();
        let err = broker
            .read_approved_fields_for_executor(&unknown_approval)
            .await
            .unwrap_err();
        assert_eq!(err.status(), CredentialFillStatus::PolicyBlocked);
        assert_eq!(provider.read_count(), 0);

        assert!(
            ApprovedCredentialFill::from_approved_state(
                Uuid::nil(),
                Uuid::nil(),
                "bad/alias",
                "https://www.sonofatailor.com/login",
                None,
                CredentialFillStatus::Approved,
            )
            .is_err()
        );
        assert!(
            ApprovedCredentialFill::from_approved_state(
                Uuid::nil(),
                Uuid::nil(),
                "tailor_login",
                "ftp://www.sonofatailor.com/login",
                None,
                CredentialFillStatus::Approved,
            )
            .is_err()
        );
        assert!(normalize_origin("https://*.example.test").is_err());

        for invalid_policy in [
            serde_json::json!({"aliases": {}}),
            serde_json::json!({
                "aliases": {
                    "bad/alias": {
                        "allowed_origins": ["https://example.test"],
                        "provider_refs": {"password": "synthetic-ref"},
                        "allowed_fields": ["password"]
                    }
                }
            }),
            serde_json::json!({
                "aliases": {
                    "empty_origins": {
                        "allowed_origins": [],
                        "provider_refs": {"password": "synthetic-ref"},
                        "allowed_fields": ["password"]
                    }
                }
            }),
            serde_json::json!({
                "aliases": {
                    "no_refs": {
                        "allowed_origins": ["https://example.test"],
                        "provider_refs": {},
                        "allowed_fields": ["password"]
                    }
                }
            }),
            serde_json::json!({
                "aliases": {
                    "unsafe_field": {
                        "allowed_origins": ["https://example.test"],
                        "provider_refs": {"password": "synthetic-ref"},
                        "allowed_fields": ["otp"]
                    }
                }
            }),
            serde_json::json!({
                "aliases": {
                    "empty_ref": {
                        "allowed_origins": ["https://example.test"],
                        "provider_refs": {"password": ""},
                        "allowed_fields": ["password"]
                    }
                }
            }),
        ] {
            assert!(CredentialPolicy::from_json_str(&invalid_policy.to_string()).is_err());
        }
    }

    #[tokio::test]
    async fn onepassword_provider_reads_optional_fields_and_sanitizes_invocations() {
        let executor = RecordingOpExecutor::success("synthetic-secret-canary\n");
        let provider = OnePasswordCliProvider::with_executor(
            "/usr/bin/op".into(),
            Duration::from_millis(50),
            executor.clone(),
        );

        let username_only = provider
            .read_fields(&CredentialProviderRefs {
                username: Some(PrivateProviderRef::new_for_test(
                    "synthetic-username-ref-canary",
                )),
                password: None,
            })
            .await
            .unwrap();
        assert_eq!(
            username_only
                .username
                .unwrap()
                .expose_for_fill_executor()
                .unwrap(),
            "synthetic-secret-canary"
        );
        assert!(username_only.password.is_none());

        let both_fields = provider
            .read_fields(&CredentialProviderRefs {
                username: Some(PrivateProviderRef::new_for_test(
                    "synthetic-username-ref-canary",
                )),
                password: Some(PrivateProviderRef::new_for_test(
                    "synthetic-password-ref-canary",
                )),
            })
            .await
            .unwrap();
        assert!(both_fields.username.is_some());
        assert!(both_fields.password.is_some());

        let invocations = executor.observed_invocations();
        assert_eq!(invocations.len(), 3);
        for invocation in invocations {
            assert_eq!(invocation.args, ["read", "--no-newline", REDACTED]);
            assert!(!invocation.used_shell);
            assert!(!format!("{invocation:?}").contains("synthetic-password-ref-canary"));
        }

        let failing_executor = RecordingOpExecutor::failure(
            CredentialFillStatus::ProviderLocked,
            "synthetic stdout secret",
            "synthetic stderr token",
        );
        let failing_provider = OnePasswordCliProvider::with_executor(
            "/usr/bin/op".into(),
            Duration::from_millis(50),
            failing_executor,
        );
        let err = failing_provider
            .read_fields(&CredentialProviderRefs {
                username: None,
                password: Some(PrivateProviderRef::new_for_test(
                    "synthetic-password-ref-canary",
                )),
            })
            .await
            .unwrap_err();
        assert_eq!(err.status(), CredentialFillStatus::ProviderLocked);

        for (status, expected_class) in [
            (CredentialFillStatus::Unavailable, "provider_unavailable"),
            (
                CredentialFillStatus::RequiresUserApproval,
                "requires_user_approval",
            ),
            (CredentialFillStatus::Pending, "pending"),
            (CredentialFillStatus::Approved, "approved"),
            (CredentialFillStatus::Filled, "filled"),
            (CredentialFillStatus::Denied, "denied"),
            (CredentialFillStatus::NoMatch, "no_match"),
            (CredentialFillStatus::OriginMismatch, "origin_mismatch"),
            (CredentialFillStatus::PolicyBlocked, "policy_blocked"),
            (CredentialFillStatus::UnlockRequired, "unlock_required"),
            (CredentialFillStatus::ProviderLocked, "provider_locked"),
            (CredentialFillStatus::Failed, "failed"),
            (
                CredentialFillStatus::PrivacyGuardActive,
                "privacy_guard_active",
            ),
        ] {
            assert_eq!(status_class(status), expected_class);
        }
    }

    #[test]
    fn provider_env_allowlist_is_fail_closed() {
        assert!(provider_env_allowed(std::ffi::OsStr::new("HOME")));
        assert!(provider_env_allowed(std::ffi::OsStr::new("PATH")));
        assert!(provider_env_allowed(std::ffi::OsStr::new(
            "OP_SESSION_example"
        )));
        assert!(!provider_env_allowed(std::ffi::OsStr::new(
            "AWS_SECRET_ACCESS_KEY"
        )));
        assert!(!provider_env_allowed(std::ffi::OsStr::new(
            "OP_CONNECT_TOKEN"
        )));

        #[cfg(unix)]
        {
            use std::os::unix::ffi::OsStringExt;

            let non_utf8 = std::ffi::OsString::from_vec(vec![0xff]);
            assert!(!provider_env_allowed(non_utf8.as_os_str()));
        }
    }

    async fn run_synthetic_op_script(
        script: &str,
    ) -> std::result::Result<SecretValue, CredentialProviderError> {
        use std::os::unix::fs::PermissionsExt;

        let tempdir = tempfile::tempdir().unwrap();
        let script_path = tempdir.path().join("synthetic-op");
        std::fs::write(&script_path, script).unwrap();
        let mut permissions = std::fs::metadata(&script_path).unwrap().permissions();
        permissions.set_mode(0o700);
        std::fs::set_permissions(&script_path, permissions).unwrap();

        TokioOpExecutor
            .read_secret(
                &script_path,
                &PrivateProviderRef::new_for_test("synthetic-provider-ref-canary"),
                Duration::from_millis(500),
            )
            .await
    }

    #[tokio::test]
    async fn tokio_op_executor_classifies_success_empty_and_failure_paths_safely() {
        let _guard = synthetic_op_exec_test_lock().lock().await;
        let secret = run_synthetic_op_script("#!/bin/sh\nprintf 'synthetic-secret-canary\\n\\r'\n")
            .await
            .unwrap();
        assert_eq!(
            secret.expose_for_fill_executor().unwrap(),
            "synthetic-secret-canary"
        );

        let empty = run_synthetic_op_script("#!/bin/sh\nexit 0\n")
            .await
            .unwrap_err();
        assert_eq!(empty.status(), CredentialFillStatus::NoMatch);
        assert_eq!(empty.to_string(), "no_match");

        let unlock = run_synthetic_op_script(
            "#!/bin/sh\nprintf 'please sign in synthetic-token-canary' >&2\nexit 1\n",
        )
        .await
        .unwrap_err();
        assert_eq!(unlock.status(), CredentialFillStatus::UnlockRequired);
        assert_eq!(unlock.to_string(), "unlock_required");

        let missing = run_synthetic_op_script(
            "#!/bin/sh\nprintf 'could not find synthetic-provider-ref-canary' >&2\nexit 1\n",
        )
        .await
        .unwrap_err();
        assert_eq!(missing.status(), CredentialFillStatus::NoMatch);
        assert_eq!(missing.to_string(), "no_match");

        let failed = run_synthetic_op_script(
            "#!/bin/sh\nprintf 'other synthetic-secret-canary' >&2\nexit 2\n",
        )
        .await
        .unwrap_err();
        assert_eq!(failed.status(), CredentialFillStatus::Failed);
        assert_eq!(failed.to_string(), "provider_failed");

        for err in [empty, unlock, missing, failed] {
            let text = format!("{err:?} {err}");
            for forbidden in [
                "synthetic-provider-ref-canary",
                "synthetic-secret-canary",
                "synthetic-token-canary",
                "stdout",
                "stderr",
            ] {
                assert!(!text.contains(forbidden));
            }
        }

        let unavailable = TokioOpExecutor
            .read_secret(
                Path::new("/definitely/missing/synthetic-op"),
                &PrivateProviderRef::new_for_test("synthetic-provider-ref-canary"),
                Duration::from_millis(10),
            )
            .await
            .unwrap_err();
        assert_eq!(unavailable.status(), CredentialFillStatus::Unavailable);
        assert_eq!(unavailable.to_string(), "provider_unavailable");
    }

    #[tokio::test]
    async fn tokio_op_executor_kills_and_reaps_timed_out_child_without_leaking_error_material() {
        let _guard = synthetic_op_exec_test_lock().lock().await;
        use std::os::unix::fs::PermissionsExt;

        let tempdir = tempfile::tempdir().unwrap();
        let script_path = tempdir.path().join("synthetic-op");
        let provider_ref_path = tempdir.path().join("provider-ref");
        let provider_ref = provider_ref_path.to_string_lossy().to_string();
        let pid_path = tempdir.path().join("provider-ref.pid");
        std::fs::write(
            &script_path,
            "#!/bin/sh\nprintf '%s' \"$$\" > \"$3.pid\"\nexec /bin/sleep 30\n",
        )
        .unwrap();
        let mut permissions = std::fs::metadata(&script_path).unwrap().permissions();
        permissions.set_mode(0o700);
        std::fs::set_permissions(&script_path, permissions).unwrap();

        let err = TokioOpExecutor
            .read_secret(
                &script_path,
                &PrivateProviderRef::new_for_test(&provider_ref),
                Duration::from_millis(75),
            )
            .await
            .unwrap_err();

        assert_eq!(err.status(), CredentialFillStatus::Failed);
        let text = format!("{err:?} {err}");
        assert!(text.contains("provider_timeout"));
        assert!(!text.contains(&provider_ref));
        assert!(!text.contains("stdout"));
        assert!(!text.contains("stderr"));

        let child_pid = std::fs::read_to_string(pid_path)
            .unwrap()
            .parse::<u32>()
            .unwrap();
        for _ in 0..20 {
            if !std::path::Path::new(&format!("/proc/{child_pid}")).exists() {
                break;
            }
            tokio::time::sleep(Duration::from_millis(10)).await;
        }
        assert!(
            !std::path::Path::new(&format!("/proc/{child_pid}")).exists(),
            "timed-out synthetic op child was not reaped"
        );
    }
}
