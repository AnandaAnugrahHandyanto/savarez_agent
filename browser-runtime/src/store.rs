use std::{
    collections::{HashMap, HashSet},
    fs,
    io::Write,
    path::{Path, PathBuf},
    sync::Arc,
    time::{Duration, SystemTime},
};

use anyhow::{Context, Result, bail};
use chrono::{DateTime, Utc};
use reqwest::Url;
use serde_json::json;
use tokio::sync::{Mutex, watch};
use uuid::Uuid;

use crate::{
    backend::{BrowserBackend, LaunchedBrowser, StartSessionOptions},
    captcha_solver, cdp,
    config::RuntimeConfig,
    credentials::{
        ApprovedCredentialFill, CredentialBroker, CredentialBrokerCore, CredentialBrokerMode,
        CredentialFieldSelection, CredentialFillRequest, CredentialFillResponse,
        CredentialFillStatus, CredentialPolicy, CredentialProviderError, CredentialSecretBundle,
        FakeCredentialBroker, MockCredentialProvider, OnePasswordCliProvider,
    },
    models::{
        ArtifactInfo, ArtifactsResponse, CaptchaPolicy, CaptchaReportState, CaptchaResolveOutcome,
        CaptchaScanRequest, CaptchaScanResponse, CaptchaSolverState, CaptchaSolverStatus,
        CaptchaStatus, CaptchaStatusResponse, CleanupArtifactsResponse, CleanupCandidate,
        CreateLiveLinkResponse, CreateSessionRequest, CredentialFillStartRequest,
        CredentialFillStatusRecord, CredentialPrivacyGuardResponse, DownloadInfo,
        DownloadsResponse, LiveLinkMode, LiveLinkSummary, ProfileInfo, SessionInfo, SessionStatus,
        WaitSessionResponse,
    },
    security::{
        REDACTED, ensure_private_dir, random_token, redact_json_value, redact_text,
        safe_child_path, safe_download_name, sanitize_id,
    },
};

pub struct AppStore {
    pub config: RuntimeConfig,
    backend: Arc<dyn BrowserBackend>,
    sessions: Mutex<HashMap<Uuid, ManagedSession>>,
    profile_locks: Mutex<HashMap<String, Uuid>>,
    #[cfg(test)]
    captcha_solver_test_outcome: Mutex<Option<std::result::Result<(), String>>>,
}

pub struct ManagedSession {
    pub info: SessionInfo,
    pub browser: Option<LaunchedBrowser>,
    pub user_data_dir: PathBuf,
    pub artifacts_dir: PathBuf,
    pub downloads_dir: PathBuf,
    pub persist_profile: bool,
    pub takeover_token: String,
    pub takeover_expires_at: DateTime<Utc>,
    pub live_links: HashMap<Uuid, LiveLinkRecord>,
    pub credential_fills: HashMap<Uuid, ManagedCredentialFill>,
    pub credential_privacy_guard_active: bool,
    pub status_tx: watch::Sender<SessionInfo>,
}

#[derive(Debug, Clone)]
pub struct CaptchaSolveResult {
    pub info: SessionInfo,
    pub provider_call_performed: bool,
}

#[derive(Debug, Clone)]
pub struct ManagedCredentialFill {
    pub record: CredentialFillStatusRecord,
    pub username_selector: Option<String>,
    pub password_selector: Option<String>,
    pub purpose: Option<String>,
    pub expires_at: DateTime<Utc>,
}

#[derive(Debug, Clone)]
pub struct LiveLinkRecord {
    pub mode: LiveLinkMode,
    pub token: String,
    pub created_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
    pub revoked: bool,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
struct PersistedSessionRecord {
    info: SessionInfo,
    user_data_dir: PathBuf,
    artifacts_dir: PathBuf,
    downloads_dir: PathBuf,
    persist_profile: bool,
    #[serde(default)]
    credential_fills: Vec<CredentialFillStatusRecord>,
    #[serde(default)]
    credential_privacy_guard_active: bool,
}

impl AppStore {
    pub async fn new(config: RuntimeConfig, backend: Arc<dyn BrowserBackend>) -> Result<Self> {
        ensure_private_dir(&config.data_dir)?;
        ensure_private_dir(&config.data_dir.join("profiles"))?;
        ensure_private_dir(&config.data_dir.join("sessions"))?;
        ensure_private_dir(&config.data_dir.join("tmp"))?;
        let sessions = load_persisted_sessions(&config)?;
        Ok(Self {
            config,
            backend,
            sessions: Mutex::new(sessions),
            profile_locks: Mutex::new(HashMap::new()),
            #[cfg(test)]
            captcha_solver_test_outcome: Mutex::new(None),
        })
    }

    #[cfg(test)]
    pub(crate) async fn set_captcha_solver_test_outcome(
        &self,
        outcome: std::result::Result<(), String>,
    ) {
        *self.captcha_solver_test_outcome.lock().await = Some(outcome);
    }

    async fn resolve_captcha_solver_provider(
        &self,
    ) -> Option<(&'static str, String, captcha_solver::SolverProvider)> {
        #[cfg(test)]
        if self.captcha_solver_test_outcome.lock().await.is_some() {
            return Some((
                "two_captcha",
                "test-captcha-provider-key".to_string(),
                captcha_solver::SolverProvider::TwoCaptcha,
            ));
        }

        if let Some(key) = std::env::var("HBR_2CAPTCHA_API_KEY")
            .ok()
            .filter(|k| !k.is_empty())
        {
            Some((
                "two_captcha",
                key,
                captcha_solver::SolverProvider::TwoCaptcha,
            ))
        } else if let Some(key) = std::env::var("HBR_ANTI_CAPTCHA_API_KEY")
            .ok()
            .or_else(|| std::env::var("HBR_ANTICAPTCHA_API_KEY").ok())
            .filter(|k| !k.is_empty())
        {
            Some((
                "anti_captcha",
                key,
                captcha_solver::SolverProvider::AntiCaptcha,
            ))
        } else {
            None
        }
    }

    async fn dispatch_captcha_solver(
        &self,
        api_key: &str,
        site_key: &str,
        page_url: &str,
        challenge_type: &str,
        provider: captcha_solver::SolverProvider,
        timeout: Duration,
    ) -> std::result::Result<captcha_solver::SolvedToken, String> {
        #[cfg(test)]
        if let Some(outcome) = self.captcha_solver_test_outcome.lock().await.take() {
            return outcome.map(|()| captcha_solver::SolvedToken {
                token: "test-captcha-token".to_string(),
                provider,
            });
        }

        captcha_solver::solve(
            api_key,
            site_key,
            page_url,
            challenge_type,
            provider,
            timeout,
        )
        .await
    }

    pub async fn create_session(&self, request: CreateSessionRequest) -> Result<SessionInfo> {
        self.refresh_exited_sessions().await;

        let id = Uuid::new_v4();
        let now = Utc::now();
        let profile_id = request
            .profile_id
            .as_deref()
            .and_then(sanitize_id)
            .unwrap_or_else(|| format!("profile-{}", Uuid::new_v4()));
        let persist_profile = request.persist_profile.unwrap_or(true);
        let headless = request.headless.unwrap_or(self.config.default_headless);
        let webrtc_ip_policy = request
            .webrtc_ip_policy
            .unwrap_or(self.config.default_webrtc_ip_policy);
        let gpu_policy = request.gpu_policy.unwrap_or(self.config.default_gpu_policy);
        let captcha_policy = request
            .captcha_policy
            .unwrap_or(self.config.default_captcha_policy);
        let mut persona = request
            .persona
            .unwrap_or_else(|| self.config.default_persona.clone());
        let viewport = request.viewport.unwrap_or_else(|| persona.viewport.clone());
        persona.viewport = viewport.clone();
        if persona.screen.width < viewport.width || persona.screen.height < viewport.height {
            persona.screen = viewport.clone();
        }
        let launch_timeout = request
            .launch_timeout_secs
            .map(Duration::from_secs)
            .unwrap_or(self.config.launch_timeout);
        let profile_dir = self.profile_dir(&profile_id)?;
        let session_dir = self.session_dir(id);
        let artifacts_dir = session_dir.join("artifacts");
        let downloads_dir = session_dir.join("downloads");
        ensure_private_dir(&session_dir)?;
        ensure_private_dir(&artifacts_dir)?;
        ensure_private_dir(&downloads_dir)?;

        let user_data_dir = match async {
            if persist_profile {
                self.acquire_profile_lock(&profile_id, id).await?;
                ensure_private_dir(&profile_dir)?;
                Ok(profile_dir.clone())
            } else {
                let tmp = self.session_tmp_dir(id).join("user-data");
                ensure_private_dir(&tmp)?;
                if profile_dir.exists() {
                    copy_profile_read_only_seed(&profile_dir, &tmp)?;
                }
                Ok(tmp)
            }
        }
        .await
        {
            Ok(user_data_dir) => user_data_dir,
            Err(err) => {
                self.cleanup_aborted_session(id, &profile_id, persist_profile)
                    .await;
                return Err(err);
            }
        };

        let launch_result = self
            .backend
            .launch(StartSessionOptions {
                id,
                user_data_dir: user_data_dir.clone(),
                downloads_dir: downloads_dir.clone(),
                headless,
                viewport: viewport.clone(),
                persona: persona.clone(),
                webrtc_ip_policy,
                gpu_policy,
                launch_timeout,
            })
            .await;
        let browser = match launch_result {
            Ok(browser) => browser,
            Err(err) => {
                self.cleanup_aborted_session(id, &profile_id, persist_profile)
                    .await;
                return Err(err);
            }
        };
        let info = SessionInfo {
            id,
            status: SessionStatus::Running,
            cdp_ws_url: Some(browser.cdp_ws_url.clone()),
            takeover_url: None,
            profile_id: profile_id.clone(),
            persist_profile,
            headless,
            webrtc_ip_policy,
            gpu_policy,
            captcha_policy,
            captcha_status: CaptchaStatus::None,
            captcha_challenge_type: None,
            captcha_solver_status: None,
            viewport,
            created_at: now,
            updated_at: now,
            pause_reason: None,
        };
        let (status_tx, _status_rx) = watch::channel(info.clone());
        let session = ManagedSession {
            info: info.clone(),
            browser: Some(browser),
            user_data_dir,
            artifacts_dir,
            downloads_dir,
            persist_profile,
            takeover_token: String::new(),
            takeover_expires_at: now,
            live_links: HashMap::new(),
            credential_fills: HashMap::new(),
            credential_privacy_guard_active: false,
            status_tx,
        };
        let created_payload = json!({
            "profile_id": profile_id,
            "persist_profile": persist_profile,
            "headless": headless,
            "webrtc_ip_policy": webrtc_ip_policy,
            "gpu_policy": gpu_policy,
            "persona": {
                "locale": persona.locale,
                "accept_language": persona.accept_language,
                "timezone_id": persona.timezone_id,
                "platform": persona.platform,
                "viewport": persona.viewport,
                "screen": persona.screen,
                "device_scale_factor": persona.device_scale_factor,
            }
        });
        self.append_event(&session, "session_created", created_payload)?;
        persist_session_record(&session)?;
        self.sessions.lock().await.insert(id, session);
        Ok(info)
    }

    pub async fn list_sessions(&self) -> Vec<SessionInfo> {
        self.refresh_exited_sessions().await;
        self.sessions
            .lock()
            .await
            .values()
            .map(|session| session.info.clone())
            .collect()
    }

    pub async fn get_session(&self, id: Uuid) -> Option<SessionInfo> {
        self.refresh_exited_sessions().await;
        self.sessions.lock().await.get(&id).map(|s| s.info.clone())
    }

    pub async fn delete_session(&self, id: Uuid) -> Result<SessionInfo> {
        self.refresh_exited_sessions().await;

        let mut session = self
            .sessions
            .lock()
            .await
            .remove(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;
        session.info.status = SessionStatus::Closing;
        session.info.updated_at = Utc::now();
        self.append_event(&session, "session_closing", json!({}))?;
        persist_session_record(&session)?;
        if let Some(browser) = session.browser.as_mut() {
            self.backend.close(browser).await?;
        }
        if session.persist_profile {
            self.release_profile_lock(&session.info.profile_id, id)
                .await;
        }
        if !session.persist_profile {
            self.cleanup_nonpersistent_session_tmp(id);
        }
        session.browser = None;
        session.info.status = SessionStatus::Closed;
        session.info.pause_reason = None;
        session.info.takeover_url = None;
        session.info.cdp_ws_url = None;
        session.takeover_token.clear();
        session.takeover_expires_at = Utc::now();
        session.live_links.clear();
        clear_session_credential_privacy_guard(&mut session);
        session.info.updated_at = Utc::now();
        self.append_event(&session, "session_closed", json!({}))?;
        session.status_tx.send_replace(session.info.clone());
        remove_persisted_session_record(self.session_record_path(id))?;
        Ok(session.info)
    }

    pub async fn pause_for_human(&self, id: Uuid, reason: Option<String>) -> Result<SessionInfo> {
        self.refresh_exited_sessions().await;

        let mut sessions = self.sessions.lock().await;
        let session = sessions
            .get_mut(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;
        session.info.status = SessionStatus::PausedForHuman;
        session.info.pause_reason = reason.map(|value| redact_text(&value));
        session.takeover_token = random_token(32);
        session.takeover_expires_at =
            Utc::now() + chrono::Duration::from_std(self.config.takeover_ttl)?;
        session.info.takeover_url = Some(self.takeover_url(id, &session.takeover_token));
        session.info.updated_at = Utc::now();
        let pause_payload = json!({"reason": session.info.pause_reason});
        self.append_event(session, "pause_for_human", pause_payload)?;
        persist_session_record(session)?;
        session.status_tx.send_replace(session.info.clone());
        Ok(session.info.clone())
    }

    pub async fn release(&self, id: Uuid) -> Result<SessionInfo> {
        self.refresh_exited_sessions().await;

        let mut sessions = self.sessions.lock().await;
        let session = sessions
            .get_mut(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;
        ensure_session_releasable(session)?;
        session.info.status = SessionStatus::Running;
        session.info.pause_reason = None;
        session.takeover_token.clear();
        session.takeover_expires_at = Utc::now();
        session.live_links.clear();
        session.info.takeover_url = None;
        session.info.updated_at = Utc::now();
        self.append_event(session, "released", json!({}))?;
        persist_session_record(session)?;
        session.status_tx.send_replace(session.info.clone());
        Ok(session.info.clone())
    }

    pub async fn wait_session(&self, id: Uuid, timeout: Duration) -> Result<WaitSessionResponse> {
        self.refresh_exited_sessions().await;

        let mut status_rx = {
            let sessions = self.sessions.lock().await;
            let session = sessions
                .get(&id)
                .ok_or_else(|| anyhow::anyhow!("session not found"))?;
            if session.info.status != SessionStatus::PausedForHuman {
                return Ok(WaitSessionResponse {
                    timed_out: false,
                    session: session.info.clone(),
                });
            }
            session.status_tx.subscribe()
        };

        let wait_for_change = async {
            loop {
                status_rx
                    .changed()
                    .await
                    .context("session watcher closed")?;
                let session = status_rx.borrow().clone();
                if session.status != SessionStatus::PausedForHuman {
                    return Ok(session);
                }
            }
        };

        match tokio::time::timeout(timeout, wait_for_change).await {
            Ok(Ok(session)) => Ok(WaitSessionResponse {
                timed_out: false,
                session,
            }),
            Ok(Err(err)) => Err(err),
            Err(_) => Ok(WaitSessionResponse {
                timed_out: true,
                session: status_rx.borrow().clone(),
            }),
        }
    }

    pub async fn create_live_link(
        &self,
        id: Uuid,
        mode: LiveLinkMode,
    ) -> Result<CreateLiveLinkResponse> {
        self.refresh_exited_sessions().await;
        let mut sessions = self.sessions.lock().await;
        let session = sessions
            .get_mut(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;
        if session.info.status != SessionStatus::PausedForHuman {
            bail!("live link requires paused human takeover session");
        }
        let link_id = Uuid::new_v4();
        let token = random_token(32);
        let created_at = Utc::now();
        let expires_at = created_at + chrono::Duration::from_std(self.config.takeover_ttl)?;
        session.live_links.insert(
            link_id,
            LiveLinkRecord {
                mode,
                token: token.clone(),
                created_at,
                expires_at,
                revoked: false,
            },
        );
        let url = self.takeover_url(id, &token);
        self.append_event(
            session,
            "live_link_created",
            json!({"link_id": link_id, "mode": mode, "expires_at": expires_at}),
        )?;
        Ok(CreateLiveLinkResponse {
            id: link_id,
            mode,
            url,
            created_at,
            expires_at,
        })
    }

    pub async fn revoke_live_link(&self, id: Uuid, link_id: Uuid) -> Result<LiveLinkSummary> {
        self.refresh_exited_sessions().await;
        let mut sessions = self.sessions.lock().await;
        let session = sessions
            .get_mut(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;
        let summary = {
            let link = session
                .live_links
                .get_mut(&link_id)
                .ok_or_else(|| anyhow::anyhow!("live link not found"))?;
            link.revoked = true;
            live_link_summary(link_id, link, Utc::now())
        };
        self.append_event(session, "live_link_revoked", json!({"link_id": link_id}))?;
        Ok(summary)
    }

    pub async fn live_link_summaries(&self, id: Uuid) -> Result<Vec<LiveLinkSummary>> {
        self.refresh_exited_sessions().await;
        let sessions = self.sessions.lock().await;
        let session = sessions
            .get(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;
        let now = Utc::now();
        let mut links: Vec<_> = session
            .live_links
            .iter()
            .map(|(link_id, link)| live_link_summary(*link_id, link, now))
            .collect();
        links.sort_by_key(|link| std::cmp::Reverse(link.created_at));
        Ok(links)
    }

    pub async fn takeover_access_mode(&self, id: Uuid, token: &str) -> Option<LiveLinkMode> {
        self.refresh_exited_sessions().await;
        self.sessions
            .lock()
            .await
            .get(&id)
            .and_then(|session| takeover_access_mode_for_session(session, token, Utc::now()))
    }

    pub async fn credential_fill_snapshot(
        &self,
        id: Uuid,
    ) -> Result<(Vec<CredentialFillStatusRecord>, bool)> {
        let sessions = self.sessions.lock().await;
        let session = sessions
            .get(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;
        let mut records: Vec<_> = session
            .credential_fills
            .values()
            .map(|fill| fill.record.clone())
            .collect();
        records.sort_by_key(|record| std::cmp::Reverse(record.updated_at));
        Ok((records, session.credential_privacy_guard_active))
    }

    pub async fn request_credential_fill(
        &self,
        id: Uuid,
        request: CredentialFillStartRequest,
    ) -> Result<CredentialFillStatusRecord> {
        self.refresh_exited_sessions().await;

        let http_base = {
            let sessions = self.sessions.lock().await;
            let session = sessions
                .get(&id)
                .ok_or_else(|| anyhow::anyhow!("session not found"))?;
            if session.credential_privacy_guard_active {
                bail!("credential privacy guard active; clear it before another fill");
            }
            session
                .browser
                .as_ref()
                .map(|browser| browser.http_base.clone())
                .ok_or_else(|| anyhow::anyhow!("session browser unavailable"))?
        };

        let context = cdp::credential_field_context(
            &http_base,
            request.username_selector.as_deref(),
            request.password_selector.as_deref(),
        )
        .await
        .context("credential field context unavailable")?;
        let request_id = Uuid::new_v4();
        if !context.has_requested_fields(
            request.username_selector.as_deref(),
            request.password_selector.as_deref(),
        ) {
            let record = credential_terminal_record(
                request_id,
                id,
                &request.alias,
                &context.observed_origin,
                CredentialFillStatus::NoMatch,
                self.config.credential_provider,
                "no_matching_credential_fields",
            );
            self.insert_credential_fill_record(
                id,
                record,
                request.username_selector,
                request.password_selector,
                request.purpose,
            )
            .await
        } else {
            let broker_request = CredentialFillRequest {
                request_id,
                session_id: id,
                alias: request.alias,
                username_selector: request.username_selector.clone(),
                password_selector: request.password_selector.clone(),
                purpose: request.purpose.clone().map(|purpose| redact_text(&purpose)),
                observed_origin: context.observed_origin,
                expected_origin: request.expected_origin,
            };
            let response = self.credential_broker_request(broker_request).await?;
            let record = credential_record_from_response(response, false, Utc::now());
            self.insert_credential_fill_record(
                id,
                record,
                request.username_selector,
                request.password_selector,
                request.purpose,
            )
            .await
        }
    }

    pub async fn credential_fill_status(
        &self,
        id: Uuid,
        request_id: Uuid,
    ) -> Result<CredentialFillStatusRecord> {
        self.refresh_exited_sessions().await;
        let sessions = self.sessions.lock().await;
        let session = sessions
            .get(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;
        session
            .credential_fills
            .get(&request_id)
            .map(|fill| fill.record.clone())
            .ok_or_else(|| anyhow::anyhow!("credential fill not found"))
    }

    async fn validate_credential_fill_context(
        &self,
        id: Uuid,
        request_id: Uuid,
        http_base: &str,
        observed_origin: &str,
        username_selector: Option<&str>,
        password_selector: Option<&str>,
    ) -> Result<Option<CredentialFillStatusRecord>> {
        let current_context =
            match cdp::credential_field_context(http_base, username_selector, password_selector)
                .await
            {
                Ok(context) => context,
                Err(err) => {
                    return self
                        .set_credential_fill_status(
                            id,
                            request_id,
                            CredentialFillStatus::Failed,
                            Some(format!("credential_context_unavailable: {err}")),
                        )
                        .await
                        .map(Some);
                }
            };
        if !credential_origins_match(observed_origin, &current_context.observed_origin) {
            return self
                .set_credential_fill_status(
                    id,
                    request_id,
                    CredentialFillStatus::OriginMismatch,
                    Some("credential_origin_changed".to_string()),
                )
                .await
                .map(Some);
        }
        if !current_context.has_requested_fields(username_selector, password_selector) {
            return self
                .set_credential_fill_status(
                    id,
                    request_id,
                    CredentialFillStatus::NoMatch,
                    Some(
                        current_context
                            .unsafe_reason
                            .unwrap_or_else(|| "no_matching_credential_fields".to_string()),
                    ),
                )
                .await
                .map(Some);
        }
        Ok(None)
    }

    pub async fn approve_credential_fill(
        &self,
        id: Uuid,
        request_id: Uuid,
        note: Option<String>,
    ) -> Result<CredentialFillStatusRecord> {
        self.refresh_exited_sessions().await;

        let (http_base, observed_origin, username_selector, password_selector) = {
            let mut sessions = self.sessions.lock().await;
            let session = sessions
                .get_mut(&id)
                .ok_or_else(|| anyhow::anyhow!("session not found"))?;
            let http_base = session
                .browser
                .as_ref()
                .map(|browser| browser.http_base.clone())
                .ok_or_else(|| anyhow::anyhow!("session browser unavailable"))?;
            let fill = session
                .credential_fills
                .get_mut(&request_id)
                .ok_or_else(|| anyhow::anyhow!("credential fill not found"))?;
            if fill.record.status != CredentialFillStatus::RequiresUserApproval {
                return Ok(fill.record.clone());
            }
            if Utc::now() >= fill.expires_at {
                fill.record.status = CredentialFillStatus::Failed;
                fill.record.updated_at = Utc::now();
                fill.record.redacted_message = Some("approval_expired".to_string());
                let record = fill.record.clone();
                self.append_event(
                    session,
                    credential_event_kind(record.status),
                    serde_json::to_value(&record)?,
                )?;
                persist_session_record(session)?;
                return Ok(record);
            }
            (
                http_base,
                fill.record.observed_origin.clone(),
                fill.username_selector.clone(),
                fill.password_selector.clone(),
            )
        };

        if let Some(record) = self
            .validate_credential_fill_context(
                id,
                request_id,
                &http_base,
                &observed_origin,
                username_selector.as_deref(),
                password_selector.as_deref(),
            )
            .await?
        {
            return Ok(record);
        }

        let approval = {
            let mut sessions = self.sessions.lock().await;
            let session = sessions
                .get_mut(&id)
                .ok_or_else(|| anyhow::anyhow!("session not found"))?;
            let fill = session
                .credential_fills
                .get_mut(&request_id)
                .ok_or_else(|| anyhow::anyhow!("credential fill not found"))?;
            if fill.record.status != CredentialFillStatus::RequiresUserApproval {
                return Ok(fill.record.clone());
            }
            if Utc::now() >= fill.expires_at {
                fill.record.status = CredentialFillStatus::Failed;
                fill.record.updated_at = Utc::now();
                fill.record.redacted_message = Some("approval_expired".to_string());
                let record = fill.record.clone();
                self.append_event(
                    session,
                    credential_event_kind(record.status),
                    serde_json::to_value(&record)?,
                )?;
                persist_session_record(session)?;
                return Ok(record);
            }
            let redacted_note = note.as_deref().map(redact_text);
            fill.record.status = CredentialFillStatus::Approved;
            fill.record.updated_at = Utc::now();
            fill.record.redacted_message = Some(match redacted_note.as_deref() {
                Some(note) => format!("approved: {note}"),
                None => "approved".to_string(),
            });
            let requested_fields = CredentialFieldSelection::from_selectors(
                fill.username_selector.as_deref(),
                fill.password_selector.as_deref(),
            );
            let approval = ApprovedCredentialFill::from_approved_state_for_fields(
                request_id,
                id,
                fill.record.alias.clone(),
                fill.record.observed_origin.clone(),
                fill.purpose.clone().map(|purpose| redact_text(&purpose)),
                CredentialFillStatus::Approved,
                requested_fields,
            )?;
            let record = fill.record.clone();
            self.append_event(
                session,
                "credential_fill_approved",
                serde_json::to_value(&record)?,
            )?;
            persist_session_record(session)?;
            approval
        };

        let fields = match self.read_approved_credential_fields(&approval).await {
            Ok(fields) => fields,
            Err(err) => {
                return self
                    .set_credential_fill_status(id, request_id, err.status(), Some(err.to_string()))
                    .await;
            }
        };

        if let Some(record) = self
            .validate_credential_fill_context(
                id,
                request_id,
                &http_base,
                &observed_origin,
                username_selector.as_deref(),
                password_selector.as_deref(),
            )
            .await?
        {
            return Ok(record);
        }

        let username_value = match (username_selector.as_ref(), fields.username.as_ref()) {
            (Some(_), Some(secret)) => match secret.expose_for_fill_executor() {
                Ok(value) => Some(value),
                Err(_) => {
                    return self
                        .set_credential_fill_status(
                            id,
                            request_id,
                            CredentialFillStatus::Failed,
                            Some("credential_value_invalid".to_string()),
                        )
                        .await;
                }
            },
            (Some(_), None) => {
                return self
                    .set_credential_fill_status(
                        id,
                        request_id,
                        CredentialFillStatus::NoMatch,
                        Some("missing_username_secret".to_string()),
                    )
                    .await;
            }
            (None, _) => None,
        };
        let password_value = match (password_selector.as_ref(), fields.password.as_ref()) {
            (Some(_), Some(secret)) => match secret.expose_for_fill_executor() {
                Ok(value) => Some(value),
                Err(_) => {
                    return self
                        .set_credential_fill_status(
                            id,
                            request_id,
                            CredentialFillStatus::Failed,
                            Some("credential_value_invalid".to_string()),
                        )
                        .await;
                }
            },
            (Some(_), None) => {
                return self
                    .set_credential_fill_status(
                        id,
                        request_id,
                        CredentialFillStatus::NoMatch,
                        Some("missing_password_secret".to_string()),
                    )
                    .await;
            }
            (None, _) => None,
        };

        if self.config.credential_privacy_guard {
            self.set_credential_privacy_guard(id, Some(request_id), true)
                .await?;
        }

        let fill_result = cdp::fill_credential_fields(
            &http_base,
            username_selector.as_deref(),
            username_value,
            password_selector.as_deref(),
            password_value,
        )
        .await;
        match fill_result {
            Ok(()) => {
                self.set_credential_fill_status(
                    id,
                    request_id,
                    CredentialFillStatus::Filled,
                    Some("filled".to_string()),
                )
                .await
            }
            Err(err) => {
                let status = if err.to_string().contains("field not found") {
                    CredentialFillStatus::NoMatch
                } else {
                    CredentialFillStatus::Failed
                };
                self.set_credential_fill_status(
                    id,
                    request_id,
                    status,
                    Some("browser_credential_fill_failed".to_string()),
                )
                .await
            }
        }
    }

    pub async fn deny_credential_fill(
        &self,
        id: Uuid,
        request_id: Uuid,
        note: Option<String>,
    ) -> Result<CredentialFillStatusRecord> {
        let redacted_note = note.as_deref().map(redact_text);
        self.set_credential_fill_status(
            id,
            request_id,
            CredentialFillStatus::Denied,
            Some(match redacted_note.as_deref() {
                Some(note) => format!("denied: {note}"),
                None => "denied".to_string(),
            }),
        )
        .await
    }

    pub async fn clear_credential_privacy_guard(
        &self,
        id: Uuid,
    ) -> Result<CredentialPrivacyGuardResponse> {
        self.refresh_exited_sessions().await;
        let mut sessions = self.sessions.lock().await;
        let session = sessions
            .get_mut(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;
        clear_session_credential_privacy_guard(session);
        self.append_event(
            session,
            "credential_privacy_guard_cleared",
            json!({"session_id": id, "privacy_guard_active": false}),
        )?;
        persist_session_record(session)?;
        Ok(CredentialPrivacyGuardResponse {
            session_id: id,
            privacy_guard_active: false,
        })
    }

    pub async fn validate_takeover_token(&self, id: Uuid, token: &str) -> bool {
        self.takeover_access_mode(id, token).await.is_some()
    }

    pub async fn report_captcha(
        &self,
        id: Uuid,
        state: CaptchaReportState,
        challenge_type: Option<String>,
        reason: Option<String>,
    ) -> Result<SessionInfo> {
        self.refresh_exited_sessions().await;
        let mut sessions = self.sessions.lock().await;
        let session = sessions
            .get_mut(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;
        if matches!(session.info.captcha_policy, CaptchaPolicy::Disabled) {
            bail!("captcha policy disabled for session");
        }

        let next_status = CaptchaStatus::from(state);
        if matches!(state, CaptchaReportState::Suspected)
            && matches!(
                session.info.captcha_status,
                CaptchaStatus::HumanRequired | CaptchaStatus::InProgress
            )
        {
            bail!("cannot downgrade active human CAPTCHA checkpoint to suspected");
        }

        let redacted_reason = reason.as_deref().map(redact_text);
        session.info.captcha_status = next_status;
        session.info.captcha_challenge_type = challenge_type.as_deref().map(redact_text);
        if matches!(state, CaptchaReportState::HumanRequired)
            && matches!(session.info.captcha_policy, CaptchaPolicy::HumanOnly)
        {
            session.info.status = SessionStatus::PausedForHuman;
            session.info.pause_reason = redacted_reason
                .clone()
                .or_else(|| Some("captcha/manual checkpoint requires human handling".to_string()));
            let token = random_token(32);
            session.takeover_token = token.clone();
            session.takeover_expires_at =
                Utc::now() + chrono::Duration::from_std(self.config.takeover_ttl)?;
            session.info.takeover_url = Some(self.takeover_url(id, &token));
        }
        session.info.updated_at = Utc::now();

        self.append_event(
            session,
            "captcha_reported",
            json!({
                "state": next_status,
                "policy": session.info.captcha_policy,
                "challenge_type": session.info.captcha_challenge_type,
                "reason": redacted_reason,
            }),
        )?;
        if matches!(state, CaptchaReportState::HumanRequired) {
            self.append_event(
                session,
                "captcha_human_required",
                json!({
                    "policy": session.info.captcha_policy,
                    "challenge_type": session.info.captcha_challenge_type,
                    "reason": session.info.pause_reason,
                }),
            )?;
        }
        persist_session_record(session)?;
        session.status_tx.send_replace(session.info.clone());
        Ok(session.info.clone())
    }

    pub async fn request_captcha_solve(
        &self,
        id: Uuid,
        challenge_type: Option<String>,
        reason: Option<String>,
        site_key: Option<String>,
        page_url: Option<String>,
    ) -> Result<CaptchaSolveResult> {
        self.refresh_exited_sessions().await;

        let solver_enabled = self.config.captcha_solver_enabled;
        let key_available = self.config.captcha_solver_provider_key_available;
        let budget_available = self.config.captcha_solver_max_attempts > 0
            && self.config.captcha_solver_max_cost_usd_per_session > 0.0;
        let resolved_provider = self.resolve_captcha_solver_provider().await;
        let redacted_reason = reason.as_deref().map(redact_text);
        let redacted_challenge_type = challenge_type.as_deref().map(redact_text);
        let _redacted_site_key = site_key.as_deref().map(redact_text);
        let _redacted_page_url = page_url.as_deref().map(redact_text);

        let mut sessions = self.sessions.lock().await;
        let session = sessions
            .get_mut(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;

        let (mut state, mut normalized_error, mut human_required, mut event_name) =
            match session.info.captcha_policy {
                CaptchaPolicy::Disabled => (
                    CaptchaSolverState::Disabled,
                    "policy_disabled",
                    false,
                    "captcha_policy_blocked",
                ),
                CaptchaPolicy::ObserveOnly => (
                    CaptchaSolverState::PolicyBlocked,
                    "observe_only_policy",
                    false,
                    "captcha_policy_blocked",
                ),
                CaptchaPolicy::HumanOnly => (
                    CaptchaSolverState::HumanRequired,
                    "human_only_policy",
                    true,
                    "captcha_human_required",
                ),
                CaptchaPolicy::AutoSolve if !solver_enabled => (
                    CaptchaSolverState::Disabled,
                    "solver_disabled",
                    true,
                    "captcha_solve_failed",
                ),
                CaptchaPolicy::AutoSolve if !budget_available => (
                    CaptchaSolverState::BudgetUnavailable,
                    "budget_unavailable",
                    true,
                    "captcha_solve_failed",
                ),
                CaptchaPolicy::AutoSolve if !key_available => (
                    CaptchaSolverState::NoProviderKey,
                    "no_provider_key",
                    true,
                    "captcha_solve_failed",
                ),
                CaptchaPolicy::AutoSolve => (
                    CaptchaSolverState::InProgress,
                    "solver_dispatched",
                    false,
                    "captcha_solve_dispatched",
                ),
            };

        // When all guards pass for AutoSolve, attempt the actual provider call.
        // This flag only becomes true after `dispatch_captcha_solver` is called.
        let provider_call_eligible = matches!(state, CaptchaSolverState::InProgress);
        if provider_call_eligible {
            let challenge = challenge_type
                .clone()
                .unwrap_or_else(|| "RecaptchaV2TaskProxyless".to_string());
            let sk = site_key.clone().unwrap_or_default();
            let pu = page_url.clone().unwrap_or_default();

            let provider = resolved_provider;
            if provider.is_none() {
                // Fail closed — no provider key resolved at call time.
                state = CaptchaSolverState::Failed;
                normalized_error = "provider_unavailable";
                human_required = true;
                event_name = "captcha_solve_failed";
            }

            if let (CaptchaSolverState::InProgress, Some((provider_id, api_key, solver_provider))) =
                (state, provider)
            {
                session.info.captcha_solver_status = Some(CaptchaSolverStatus {
                    status: CaptchaSolverState::InProgress,
                    enabled: solver_enabled,
                    policy: session.info.captcha_policy,
                    challenge_type: Some(challenge.clone()),
                    provider_id: Some(provider_id.to_string()),
                    normalized_error: None,
                    human_takeover_required: false,
                    redacted_message: redacted_reason.clone(),
                });

                // Drop the lock during the potentially slow external call
                drop(sessions);

                match self
                    .dispatch_captcha_solver(
                        &api_key,
                        &sk,
                        &pu,
                        &challenge,
                        solver_provider,
                        self.config.captcha_solver_timeout,
                    )
                    .await
                {
                    Ok(_solved) => {
                        // Re-acquire lock for success
                        sessions = self.sessions.lock().await;
                        if let Some(s) = sessions.get_mut(&id) {
                            s.info.captcha_solver_status = Some(CaptchaSolverStatus {
                                status: CaptchaSolverState::Resolved,
                                enabled: solver_enabled,
                                policy: s.info.captcha_policy,
                                challenge_type: redacted_challenge_type.clone(),
                                provider_id: Some(provider_id.to_string()),
                                normalized_error: None,
                                human_takeover_required: false,
                                redacted_message: redacted_reason.clone(),
                            });
                            s.info.captcha_status = CaptchaStatus::Resolved;
                            s.info.updated_at = Utc::now();
                            let event_payload = json!({
                                "state": CaptchaSolverState::Resolved,
                                "enabled": solver_enabled,
                                "policy": s.info.captcha_policy,
                                "challenge_type": s.info.captcha_challenge_type,
                                "normalized_error": null,
                                "human_takeover_required": false,
                                "message": redacted_reason,
                            });
                            let _ = self.append_event(s, "captcha_solve_resolved", event_payload);
                            let _ = persist_session_record(s);
                            s.status_tx.send_replace(s.info.clone());
                            return Ok(CaptchaSolveResult {
                                info: s.info.clone(),
                                provider_call_performed: true,
                            });
                        }
                        return Err(anyhow::anyhow!("session disappeared during solve"));
                    }
                    Err(err) => {
                        // Re-acquire lock for failure
                        sessions = self.sessions.lock().await;
                        if let Some(s) = sessions.get_mut(&id) {
                            s.info.captcha_solver_status = Some(CaptchaSolverStatus {
                                status: CaptchaSolverState::Failed,
                                enabled: solver_enabled,
                                policy: s.info.captcha_policy,
                                challenge_type: s.info.captcha_challenge_type.clone(),
                                provider_id: Some(provider_id.to_string()),
                                normalized_error: Some("provider_solve_error".to_string()),
                                human_takeover_required: true,
                                redacted_message: Some(redact_text(&err)),
                            });
                            s.info.status = SessionStatus::PausedForHuman;
                            s.info.captcha_status = CaptchaStatus::HumanRequired;
                            s.info.pause_reason =
                                Some("captcha solve failed; human handling required".to_string());
                            if s.info.takeover_url.is_none() || s.takeover_token.is_empty() {
                                let token = random_token(32);
                                s.takeover_token = token.clone();
                                s.takeover_expires_at = Utc::now()
                                    + chrono::Duration::from_std(self.config.takeover_ttl)?;
                                s.info.takeover_url = Some(self.takeover_url(id, &token));
                            }
                            s.info.updated_at = Utc::now();
                            let event_payload = json!({
                                "state": CaptchaSolverState::Failed,
                                "enabled": solver_enabled,
                                "policy": s.info.captcha_policy,
                                "challenge_type": s.info.captcha_challenge_type,
                                "normalized_error": "provider_solve_error",
                                "human_takeover_required": true,
                                "message": "[REDACTED]",
                            });
                            let _ =
                                self.append_event(s, "captcha_solve_failed", event_payload.clone());
                            let _ = self.append_event(s, "captcha_human_required", event_payload);
                            let _ = persist_session_record(s);
                            s.status_tx.send_replace(s.info.clone());
                            return Ok(CaptchaSolveResult {
                                info: s.info.clone(),
                                provider_call_performed: true,
                            });
                        }
                        return Err(anyhow::anyhow!("session disappeared during solve failure"));
                    }
                }
            }
        }

        if let Some(challenge_type) = redacted_challenge_type.clone() {
            session.info.captcha_challenge_type = Some(challenge_type);
        }
        session.info.captcha_solver_status = Some(CaptchaSolverStatus {
            status: state,
            enabled: solver_enabled,
            policy: session.info.captcha_policy,
            challenge_type: session.info.captcha_challenge_type.clone(),
            provider_id: None,
            normalized_error: Some(normalized_error.to_string()),
            human_takeover_required: human_required,
            redacted_message: redacted_reason.clone(),
        });

        if human_required {
            session.info.status = SessionStatus::PausedForHuman;
            session.info.captcha_status = CaptchaStatus::HumanRequired;
            session.info.pause_reason = redacted_reason
                .clone()
                .or_else(|| Some("captcha solve unavailable; human handling required".to_string()));
            if session.info.takeover_url.is_none() || session.takeover_token.is_empty() {
                let token = random_token(32);
                session.takeover_token = token.clone();
                session.takeover_expires_at =
                    Utc::now() + chrono::Duration::from_std(self.config.takeover_ttl)?;
                session.info.takeover_url = Some(self.takeover_url(id, &token));
            }
        }
        session.info.updated_at = Utc::now();

        let event_payload = json!({
            "state": state,
            "enabled": solver_enabled,
            "policy": session.info.captcha_policy,
            "challenge_type": session.info.captcha_challenge_type,
            "normalized_error": normalized_error,
            "human_takeover_required": human_required,
            "message": redacted_reason,
        });
        self.append_event(session, event_name, event_payload.clone())?;
        if human_required && event_name != "captcha_human_required" {
            self.append_event(session, "captcha_human_required", event_payload)?;
        }
        persist_session_record(session)?;
        session.status_tx.send_replace(session.info.clone());
        Ok(CaptchaSolveResult {
            info: session.info.clone(),
            provider_call_performed: false,
        })
    }

    pub async fn captcha_status(&self, id: Uuid) -> Result<CaptchaStatusResponse> {
        self.refresh_exited_sessions().await;
        let sessions = self.sessions.lock().await;
        let session = sessions
            .get(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;
        Ok(CaptchaStatusResponse::from_session(
            &session.info,
            self.config.captcha_solver_enabled,
        ))
    }

    pub async fn scan_captcha(
        &self,
        id: Uuid,
        request: CaptchaScanRequest,
    ) -> Result<CaptchaScanResponse> {
        let CaptchaStatusResponse {
            session_id,
            captcha_policy,
            captcha_status,
            challenge_type,
            solver,
            ..
        } = self.captcha_status(id).await?;
        let detected = captcha_status.is_checkpoint();
        let policy_decision = if detected {
            "local_checkpoint_detected"
        } else {
            match captcha_policy {
                CaptchaPolicy::AutoSolve => "auto_solve_waiting_for_detection",
                CaptchaPolicy::HumanOnly => "human_only_waiting_for_detection",
                CaptchaPolicy::ObserveOnly => "observe_only_waiting_for_detection",
                CaptchaPolicy::Disabled => "policy_disabled",
            }
        }
        .to_string();
        Ok(CaptchaScanResponse {
            session_id,
            detected,
            captcha_status,
            captcha_policy,
            challenge_type,
            policy_decision,
            provider_call_performed: false,
            dry_run: request.dry_run,
            solver,
        })
    }

    pub async fn resolve_captcha(
        &self,
        id: Uuid,
        outcome: CaptchaResolveOutcome,
        note: Option<String>,
    ) -> Result<SessionInfo> {
        self.refresh_exited_sessions().await;
        let mut sessions = self.sessions.lock().await;
        let session = sessions
            .get_mut(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;
        if !session.info.captcha_status.is_checkpoint() {
            bail!(
                "captcha resolution requires a suspected, human-required, or in-progress checkpoint"
            );
        }

        let next_status = CaptchaStatus::from(outcome);
        let redacted_note = note.as_deref().map(redact_text);
        session.info.captcha_status = next_status;
        session.info.updated_at = Utc::now();
        self.append_event(
            session,
            "captcha_resolved",
            json!({
                "outcome": next_status,
                "challenge_type": session.info.captcha_challenge_type,
                "note": redacted_note,
            }),
        )?;
        persist_session_record(session)?;
        session.status_tx.send_replace(session.info.clone());
        Ok(session.info.clone())
    }

    pub async fn screenshot(&self, id: Uuid) -> Result<Vec<u8>> {
        self.refresh_exited_sessions().await;

        let (http_base, artifacts_dir) = {
            let sessions = self.sessions.lock().await;
            let session = sessions
                .get(&id)
                .ok_or_else(|| anyhow::anyhow!("session not found"))?;
            if session.credential_privacy_guard_active {
                bail!("credential privacy guard active");
            }
            let browser = session
                .browser
                .as_ref()
                .ok_or_else(|| anyhow::anyhow!("session browser unavailable"))?;
            (browser.http_base.clone(), session.artifacts_dir.clone())
        };
        let png = cdp::capture_screenshot_png(&http_base).await?;
        let path = artifacts_dir.join(format!("screenshot-{}.png", Utc::now().timestamp_millis()));
        fs::write(&path, &png).with_context(|| format!("write {}", path.display()))?;
        Ok(png)
    }

    pub async fn input_click(&self, id: Uuid, x: f64, y: f64) -> Result<()> {
        let http_base = self.session_http_base(id).await?;
        cdp::click(&http_base, x, y).await
    }

    pub async fn input_type(&self, id: Uuid, text: &str) -> Result<()> {
        let http_base = self.session_http_base(id).await?;
        cdp::insert_text(&http_base, text).await
    }

    pub async fn input_key(&self, id: Uuid, key: &str) -> Result<()> {
        let http_base = self.session_http_base(id).await?;
        cdp::press_key(&http_base, key).await
    }

    pub async fn input_scroll(&self, id: Uuid, delta_x: f64, delta_y: f64) -> Result<()> {
        let http_base = self.session_http_base(id).await?;
        cdp::scroll(&http_base, delta_x, delta_y).await
    }

    pub async fn artifacts(&self, id: Uuid) -> Result<ArtifactsResponse> {
        self.refresh_exited_sessions().await;

        let sessions = self.sessions.lock().await;
        let session = sessions
            .get(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;
        if session.credential_privacy_guard_active {
            bail!("credential privacy guard active");
        }
        let mut artifacts = Vec::new();
        if session.artifacts_dir.exists() {
            for entry in fs::read_dir(&session.artifacts_dir)? {
                let entry = entry?;
                let metadata = entry.metadata()?;
                if metadata.is_file() {
                    let artifact = ArtifactInfo {
                        kind: infer_kind(&entry.path()),
                        path: entry.path().display().to_string(),
                        created_at: DateTime::<Utc>::from(metadata.modified()?),
                        size_bytes: metadata.len(),
                    };
                    artifacts.push(artifact);
                }
            }
        }
        artifacts.sort_by_key(|artifact| artifact.created_at);
        Ok(ArtifactsResponse {
            session_id: id,
            artifacts,
            downloads_dir: session.downloads_dir.display().to_string(),
        })
    }

    pub async fn downloads_dir(&self, id: Uuid) -> Result<PathBuf> {
        self.refresh_exited_sessions().await;

        let sessions = self.sessions.lock().await;
        Ok(sessions
            .get(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?
            .downloads_dir
            .clone())
    }

    pub async fn list_downloads(&self, id: Uuid) -> Result<DownloadsResponse> {
        self.refresh_exited_sessions().await;

        let downloads_dir = self.downloads_dir(id).await?;
        let mut downloads = Vec::new();
        if downloads_dir.exists() {
            for entry in fs::read_dir(&downloads_dir)? {
                let entry = entry?;
                let metadata = entry.metadata()?;
                if !metadata.is_file() {
                    continue;
                }
                downloads.push(DownloadInfo {
                    name: entry.file_name().to_string_lossy().to_string(),
                    created_at: DateTime::<Utc>::from(metadata.modified()?),
                    size_bytes: metadata.len(),
                });
            }
        }
        downloads.sort_by(|a, b| a.name.cmp(&b.name));
        Ok(DownloadsResponse {
            session_id: id,
            downloads,
        })
    }

    pub async fn read_download(&self, id: Uuid, name: &str) -> Result<(String, Vec<u8>)> {
        self.refresh_exited_sessions().await;

        let file_name =
            safe_download_name(name).ok_or_else(|| anyhow::anyhow!("invalid download name"))?;
        let downloads_dir = self.downloads_dir(id).await?;
        let path = downloads_dir.join(&file_name);
        let metadata = fs::metadata(&path).with_context(|| "download not found")?;
        if !metadata.is_file() {
            bail!("download not found");
        }
        let bytes = fs::read(&path).with_context(|| format!("read {}", path.display()))?;
        Ok((file_name, bytes))
    }

    pub async fn cleanup_artifacts(
        &self,
        older_than: Option<Duration>,
        dry_run: bool,
    ) -> Result<CleanupArtifactsResponse> {
        self.refresh_exited_sessions().await;

        let retention = older_than.unwrap_or(self.config.artifact_retention);
        let cutoff = SystemTime::now()
            .checked_sub(retention)
            .unwrap_or(SystemTime::UNIX_EPOCH);
        let sessions_root = self.config.data_dir.join("sessions");
        let active_ids: HashSet<String> = self
            .sessions
            .lock()
            .await
            .iter()
            .filter(|(_, session)| {
                !matches!(
                    session.info.status,
                    SessionStatus::Closed | SessionStatus::Failed
                )
            })
            .map(|(id, _)| id.to_string())
            .collect();
        let mut candidates = Vec::new();
        let mut deleted_session_ids = Vec::new();

        if sessions_root.exists() {
            for entry in fs::read_dir(&sessions_root)? {
                let entry = entry?;
                if !entry.file_type()?.is_dir() {
                    continue;
                }
                let session_id = entry.file_name().to_string_lossy().to_string();
                if active_ids.contains(&session_id) {
                    continue;
                }
                let last_activity = newest_modified_time(&entry.path())?;
                if last_activity > cutoff {
                    continue;
                }
                candidates.push(CleanupCandidate {
                    session_id: session_id.clone(),
                    last_activity_at: DateTime::<Utc>::from(last_activity),
                });
                if !dry_run {
                    fs::remove_dir_all(entry.path())?;
                    deleted_session_ids.push(session_id);
                }
            }
        }

        candidates.sort_by_key(|candidate| candidate.last_activity_at);
        deleted_session_ids.sort();
        Ok(CleanupArtifactsResponse {
            dry_run,
            retention_secs: retention.as_secs(),
            candidates,
            deleted_session_ids,
        })
    }

    pub async fn create_profile(&self, id: Option<String>) -> Result<ProfileInfo> {
        let id = id
            .as_deref()
            .and_then(sanitize_id)
            .unwrap_or_else(|| format!("profile-{}", Uuid::new_v4()));
        let path = self.profile_dir(&id)?;
        ensure_private_dir(&path)?;
        Ok(ProfileInfo {
            id,
            path: path.display().to_string(),
            locked_by: None,
            created_at: Some(Utc::now()),
        })
    }

    pub async fn list_profiles(&self) -> Result<Vec<ProfileInfo>> {
        self.refresh_exited_sessions().await;

        let locks = self.profile_locks.lock().await;
        let mut profiles = Vec::new();
        for entry in fs::read_dir(self.config.data_dir.join("profiles"))? {
            let entry = entry?;
            if !entry.file_type()?.is_dir() {
                continue;
            }
            let id = entry.file_name().to_string_lossy().to_string();
            profiles.push(ProfileInfo {
                id: id.clone(),
                path: entry.path().display().to_string(),
                locked_by: locks.get(&id).copied(),
                created_at: entry
                    .metadata()
                    .and_then(|m| m.modified())
                    .ok()
                    .map(DateTime::<Utc>::from),
            });
        }
        profiles.sort_by(|a, b| a.id.cmp(&b.id));
        Ok(profiles)
    }

    pub async fn delete_profile(&self, id: &str) -> Result<()> {
        self.refresh_exited_sessions().await;

        let id = sanitize_id(id).ok_or_else(|| anyhow::anyhow!("invalid profile id"))?;
        if self.profile_locks.lock().await.contains_key(&id) {
            bail!("profile is locked by an active session");
        }
        let path = self.profile_dir(&id)?;
        if path.exists() {
            fs::remove_dir_all(path)?;
        }
        Ok(())
    }

    pub async fn shutdown_all(&self) -> Result<()> {
        self.refresh_exited_sessions().await;

        let ids: Vec<Uuid> = self.sessions.lock().await.keys().copied().collect();
        for id in ids {
            let (mut browser, profile_id, persist_profile) = {
                let mut sessions = self.sessions.lock().await;
                let Some(session) = sessions.get_mut(&id) else {
                    continue;
                };
                if session.browser.is_none() {
                    continue;
                }
                session.info.status = SessionStatus::Closing;
                session.info.pause_reason = None;
                session.info.takeover_url = None;
                session.info.cdp_ws_url = None;
                session.takeover_token.clear();
                session.takeover_expires_at = Utc::now();
                session.live_links.clear();
                clear_session_credential_privacy_guard(session);
                session.info.updated_at = Utc::now();
                self.append_event(session, "session_closing", json!({"reason": "shutdown"}))?;
                persist_session_record(session)?;
                (
                    session.browser.take(),
                    session.info.profile_id.clone(),
                    session.persist_profile,
                )
            };

            if let Some(browser) = browser.as_mut() {
                self.backend.close(browser).await?;
            }
            if persist_profile {
                self.release_profile_lock(&profile_id, id).await;
            }
            let should_cleanup_tmp = !persist_profile;
            let mut sessions = self.sessions.lock().await;
            let Some(session) = sessions.get_mut(&id) else {
                continue;
            };
            session.browser = None;
            session.info.status = SessionStatus::Closed;
            session.info.pause_reason = None;
            session.info.takeover_url = None;
            session.info.cdp_ws_url = None;
            session.takeover_token.clear();
            session.takeover_expires_at = Utc::now();
            session.live_links.clear();
            clear_session_credential_privacy_guard(session);
            session.info.updated_at = Utc::now();
            self.append_event(session, "session_closed", json!({"reason": "shutdown"}))?;
            persist_session_record(session)?;
            session.status_tx.send_replace(session.info.clone());
            drop(sessions);
            if should_cleanup_tmp {
                self.cleanup_nonpersistent_session_tmp(id);
            }
        }
        Ok(())
    }

    fn profile_dir(&self, profile_id: &str) -> Result<PathBuf> {
        safe_child_path(&self.config.data_dir.join("profiles"), profile_id)
    }

    fn session_dir(&self, id: Uuid) -> PathBuf {
        self.config.data_dir.join("sessions").join(id.to_string())
    }

    fn session_tmp_dir(&self, id: Uuid) -> PathBuf {
        self.config.data_dir.join("tmp").join(id.to_string())
    }

    fn session_record_path(&self, id: Uuid) -> PathBuf {
        self.session_dir(id).join("session.json")
    }

    fn cleanup_nonpersistent_session_tmp(&self, id: Uuid) {
        let _ = remove_dir_if_exists(&self.session_tmp_dir(id));
    }

    async fn cleanup_aborted_session(&self, id: Uuid, profile_id: &str, persist_profile: bool) {
        if persist_profile {
            self.release_profile_lock(profile_id, id).await;
        } else {
            self.cleanup_nonpersistent_session_tmp(id);
        }
        let _ = remove_dir_if_exists(&self.session_dir(id));
    }

    fn takeover_url(&self, id: Uuid, token: &str) -> String {
        format!(
            "{}/takeover/{id}?token={token}",
            self.config.localhost_base_url()
        )
    }

    async fn acquire_profile_lock(&self, profile_id: &str, id: Uuid) -> Result<()> {
        let mut locks = self.profile_locks.lock().await;
        if let Some(owner) = locks.get(profile_id) {
            bail!("profile {profile_id} is already locked by session {owner}");
        }
        locks.insert(profile_id.to_string(), id);
        Ok(())
    }

    async fn release_profile_lock(&self, profile_id: &str, id: Uuid) {
        let mut locks = self.profile_locks.lock().await;
        if locks.get(profile_id).copied() == Some(id) {
            locks.remove(profile_id);
        }
    }

    async fn session_http_base(&self, id: Uuid) -> Result<String> {
        self.refresh_exited_sessions().await;

        let sessions = self.sessions.lock().await;
        let session = sessions
            .get(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;
        session
            .browser
            .as_ref()
            .map(|browser| browser.http_base.clone())
            .ok_or_else(|| anyhow::anyhow!("session browser unavailable"))
    }

    async fn insert_credential_fill_record(
        &self,
        id: Uuid,
        mut record: CredentialFillStatusRecord,
        username_selector: Option<String>,
        password_selector: Option<String>,
        purpose: Option<String>,
    ) -> Result<CredentialFillStatusRecord> {
        let mut sessions = self.sessions.lock().await;
        let session = sessions
            .get_mut(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;
        record.privacy_guard_active = session.credential_privacy_guard_active;
        let expires_at =
            Utc::now() + chrono::Duration::from_std(self.config.credential_approval_ttl)?;
        let request_id = record.request_id;
        let status = record.status;
        session.credential_fills.insert(
            request_id,
            ManagedCredentialFill {
                record: record.clone(),
                username_selector,
                password_selector,
                purpose,
                expires_at,
            },
        );
        self.append_event(
            session,
            "credential_fill_requested",
            serde_json::to_value(&record)?,
        )?;
        self.append_event(
            session,
            credential_event_kind(status),
            serde_json::to_value(&record)?,
        )?;
        persist_session_record(session)?;
        Ok(record)
    }

    async fn set_credential_fill_status(
        &self,
        id: Uuid,
        request_id: Uuid,
        status: CredentialFillStatus,
        message: Option<String>,
    ) -> Result<CredentialFillStatusRecord> {
        let mut sessions = self.sessions.lock().await;
        let session = sessions
            .get_mut(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;
        let record = {
            let fill = session
                .credential_fills
                .get_mut(&request_id)
                .ok_or_else(|| anyhow::anyhow!("credential fill not found"))?;
            fill.record.status = status;
            fill.record.updated_at = Utc::now();
            fill.record.privacy_guard_active = session.credential_privacy_guard_active;
            fill.record.redacted_message = message.map(|value| redact_text(&value));
            fill.record.clone()
        };
        self.append_event(
            session,
            credential_event_kind(status),
            serde_json::to_value(&record)?,
        )?;
        persist_session_record(session)?;
        Ok(record)
    }

    async fn set_credential_privacy_guard(
        &self,
        id: Uuid,
        request_id: Option<Uuid>,
        active: bool,
    ) -> Result<CredentialFillStatusRecord> {
        let mut sessions = self.sessions.lock().await;
        let session = sessions
            .get_mut(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;
        session.credential_privacy_guard_active = active;
        let selected_request_id = request_id
            .or_else(|| session.credential_fills.keys().copied().next())
            .ok_or_else(|| anyhow::anyhow!("credential fill not found"))?;
        for fill in session.credential_fills.values_mut() {
            fill.record.privacy_guard_active = active;
            fill.record.updated_at = Utc::now();
        }
        let record = session
            .credential_fills
            .get(&selected_request_id)
            .map(|fill| fill.record.clone())
            .ok_or_else(|| anyhow::anyhow!("credential fill not found"))?;
        let event = if active {
            "credential_privacy_guard_active"
        } else {
            "credential_privacy_guard_cleared"
        };
        self.append_event(session, event, serde_json::to_value(&record)?)?;
        persist_session_record(session)?;
        Ok(record)
    }

    async fn credential_broker_request(
        &self,
        request: CredentialFillRequest,
    ) -> Result<CredentialFillResponse> {
        match self.config.credential_provider {
            CredentialBrokerMode::Disabled => Ok(credential_response_for_status(
                &request,
                CredentialFillStatus::Unavailable,
                CredentialBrokerMode::Disabled,
                self.config.credential_privacy_guard,
                "provider_unavailable",
            )),
            CredentialBrokerMode::FakeStatusOnly => {
                FakeCredentialBroker.request_fill(request).await
            }
            CredentialBrokerMode::Mock => {
                let policy = self.load_credential_policy()?;
                CredentialBrokerCore::new(
                    CredentialBrokerMode::Mock,
                    policy,
                    MockCredentialProvider::runtime_default(),
                )
                .with_privacy_guard(self.config.credential_privacy_guard)
                .request_fill(request)
                .await
            }
            CredentialBrokerMode::OnePasswordCli => {
                let policy = self.load_credential_policy()?;
                CredentialBrokerCore::new(
                    CredentialBrokerMode::OnePasswordCli,
                    policy,
                    OnePasswordCliProvider::new(
                        self.config
                            .op_path
                            .clone()
                            .unwrap_or_else(|| PathBuf::from("op")),
                        self.config.op_timeout,
                    ),
                )
                .with_privacy_guard(self.config.credential_privacy_guard)
                .request_fill(request)
                .await
            }
        }
    }

    async fn read_approved_credential_fields(
        &self,
        approval: &ApprovedCredentialFill,
    ) -> std::result::Result<CredentialSecretBundle, CredentialProviderError> {
        match self.config.credential_provider {
            CredentialBrokerMode::Mock => {
                let policy = self
                    .load_credential_policy()
                    .map_err(|_| CredentialProviderError::provider_unavailable_for_runtime())?;
                CredentialBrokerCore::new(
                    CredentialBrokerMode::Mock,
                    policy,
                    MockCredentialProvider::runtime_default(),
                )
                .with_privacy_guard(self.config.credential_privacy_guard)
                .read_approved_fields_for_executor(approval)
                .await
            }
            CredentialBrokerMode::OnePasswordCli => {
                let policy = self
                    .load_credential_policy()
                    .map_err(|_| CredentialProviderError::provider_unavailable_for_runtime())?;
                CredentialBrokerCore::new(
                    CredentialBrokerMode::OnePasswordCli,
                    policy,
                    OnePasswordCliProvider::new(
                        self.config
                            .op_path
                            .clone()
                            .unwrap_or_else(|| PathBuf::from("op")),
                        self.config.op_timeout,
                    ),
                )
                .with_privacy_guard(self.config.credential_privacy_guard)
                .read_approved_fields_for_executor(approval)
                .await
            }
            _ => Err(CredentialProviderError::provider_not_enabled_for_runtime()),
        }
    }

    fn load_credential_policy(&self) -> Result<CredentialPolicy> {
        let path = self
            .config
            .credential_policy_path
            .as_ref()
            .ok_or_else(|| anyhow::anyhow!("credential policy path is required"))?;
        let contents = fs::read_to_string(path).with_context(|| "read credential policy")?;
        CredentialPolicy::from_json_str(&contents).context("parse credential policy")
    }

    async fn refresh_exited_sessions(&self) {
        let mut releases = Vec::new();
        {
            let mut sessions = self.sessions.lock().await;
            for (id, session) in sessions.iter_mut() {
                let exit_summary = {
                    let Some(browser) = session.browser.as_mut() else {
                        continue;
                    };
                    match browser.process.try_wait() {
                        Ok(Some(status)) => Some(status.to_string()),
                        Ok(None) => None,
                        Err(err) => Some(format!("wait check failed: {err}")),
                    }
                };
                let Some(exit_summary) = exit_summary else {
                    continue;
                };

                session.browser = None;
                session.info.status = SessionStatus::Failed;
                session.info.pause_reason = None;
                session.info.takeover_url = None;
                session.info.cdp_ws_url = None;
                session.takeover_token.clear();
                session.takeover_expires_at = Utc::now();
                session.live_links.clear();
                clear_session_credential_privacy_guard(session);
                session.info.updated_at = Utc::now();
                let _ = self.append_event(
                    session,
                    "browser_process_exited",
                    json!({"status": exit_summary}),
                );
                let _ = persist_session_record(session);
                session.status_tx.send_replace(session.info.clone());
                if session.persist_profile {
                    releases.push((session.info.profile_id.clone(), *id));
                }
            }
        }
        for (profile_id, id) in releases {
            self.release_profile_lock(&profile_id, id).await;
        }
    }

    fn append_event(
        &self,
        session: &ManagedSession,
        kind: &str,
        payload: serde_json::Value,
    ) -> Result<()> {
        append_event_to_path(&session.artifacts_dir, kind, payload)
    }
}

fn load_persisted_sessions(config: &RuntimeConfig) -> Result<HashMap<Uuid, ManagedSession>> {
    let sessions_root = config.data_dir.join("sessions");
    let mut sessions = HashMap::new();
    if !sessions_root.exists() {
        return Ok(sessions);
    }

    for entry in fs::read_dir(&sessions_root)? {
        let entry = entry?;
        if !entry.file_type()?.is_dir() {
            continue;
        }
        let record_path = entry.path().join("session.json");
        if !record_path.exists() {
            continue;
        }
        let contents = fs::read_to_string(&record_path)
            .with_context(|| format!("read {}", record_path.display()))?;
        let mut record: PersistedSessionRecord = serde_json::from_str(&contents)
            .with_context(|| format!("parse {}", record_path.display()))?;
        let was_live = matches!(
            record.info.status,
            SessionStatus::Starting
                | SessionStatus::Running
                | SessionStatus::PausedForHuman
                | SessionStatus::Closing
        );
        if was_live {
            record.info.status = SessionStatus::Failed;
            record.info.pause_reason = None;
            record.info.takeover_url = None;
            record.info.cdp_ws_url = None;
            record.info.updated_at = Utc::now();
        }
        let credential_fills = record
            .credential_fills
            .into_iter()
            .map(recover_persisted_credential_fill)
            .map(|fill| (fill.record.request_id, fill))
            .collect();
        let (status_tx, _status_rx) = watch::channel(record.info.clone());
        let session = ManagedSession {
            info: record.info.clone(),
            browser: None,
            user_data_dir: record.user_data_dir.clone(),
            artifacts_dir: record.artifacts_dir.clone(),
            downloads_dir: record.downloads_dir.clone(),
            persist_profile: record.persist_profile,
            takeover_token: String::new(),
            takeover_expires_at: Utc::now(),
            live_links: HashMap::new(),
            credential_fills,
            credential_privacy_guard_active: false,
            status_tx,
        };
        if was_live {
            append_event_to_path(
                &session.artifacts_dir,
                "session_recovered_after_restart",
                json!({"status": "live session could not survive runtime restart"}),
            )?;
            persist_session_record(&session)?;
        }
        sessions.insert(session.info.id, session);
    }

    Ok(sessions)
}

fn persist_session_record(session: &ManagedSession) -> Result<()> {
    ensure_private_dir(&session.artifacts_dir)?;
    if let Some(parent) = session.user_data_dir.parent() {
        fs::create_dir_all(parent).ok();
    }
    let mut info = session.info.clone();
    info.takeover_url = info.takeover_url.map(|url| redact_text(&url));
    info.cdp_ws_url = info.cdp_ws_url.map(|url| redact_text(&url));
    let record = PersistedSessionRecord {
        info,
        user_data_dir: session.user_data_dir.clone(),
        artifacts_dir: session.artifacts_dir.clone(),
        downloads_dir: session.downloads_dir.clone(),
        persist_profile: session.persist_profile,
        credential_fills: session
            .credential_fills
            .values()
            .map(|fill| sanitize_credential_record_for_persist(&fill.record))
            .collect(),
        credential_privacy_guard_active: false,
    };
    let record_path = session.artifacts_dir.parent().unwrap().join("session.json");
    fs::write(&record_path, serde_json::to_vec_pretty(&record)?)
        .with_context(|| format!("write {}", record_path.display()))?;
    Ok(())
}

fn credential_record_from_response(
    response: CredentialFillResponse,
    privacy_guard_active: bool,
    now: DateTime<Utc>,
) -> CredentialFillStatusRecord {
    CredentialFillStatusRecord {
        request_id: response.request_id,
        session_id: response.session_id,
        alias: response.alias,
        observed_origin: response.observed_origin,
        status: response.status,
        broker: response.broker,
        audit_id: response.audit_id,
        privacy_guard_active,
        created_at: now,
        updated_at: now,
        redacted_message: response.redacted_message,
    }
}

fn credential_terminal_record(
    request_id: Uuid,
    session_id: Uuid,
    alias: &str,
    observed_origin: &str,
    status: CredentialFillStatus,
    broker: CredentialBrokerMode,
    message: &str,
) -> CredentialFillStatusRecord {
    let now = Utc::now();
    CredentialFillStatusRecord {
        request_id,
        session_id,
        alias: safe_credential_alias(alias),
        observed_origin: observed_origin.to_string(),
        status,
        broker,
        audit_id: request_id,
        privacy_guard_active: false,
        created_at: now,
        updated_at: now,
        redacted_message: Some(redact_text(message)),
    }
}

fn credential_response_for_status(
    request: &CredentialFillRequest,
    status: CredentialFillStatus,
    broker: CredentialBrokerMode,
    privacy_guard: bool,
    message: &str,
) -> CredentialFillResponse {
    CredentialFillResponse {
        request_id: request.request_id,
        session_id: request.session_id,
        alias: safe_credential_alias(&request.alias),
        observed_origin: request.observed_origin.clone(),
        status,
        broker,
        audit_id: request.request_id,
        privacy_guard,
        redacted_message: Some(redact_text(message)),
    }
}

fn credential_origins_match(expected: &str, current: &str) -> bool {
    match (
        normalize_runtime_origin(expected),
        normalize_runtime_origin(current),
    ) {
        (Some(expected), Some(current)) => expected == current,
        _ => expected == current,
    }
}

fn normalize_runtime_origin(origin: &str) -> Option<String> {
    let parsed = Url::parse(origin).ok()?;
    let host = parsed.host_str()?.to_ascii_lowercase();
    let port = parsed.port_or_known_default()?;
    Some(format!(
        "{}://{}:{}",
        parsed.scheme().to_ascii_lowercase(),
        host,
        port
    ))
}

fn credential_event_kind(status: CredentialFillStatus) -> &'static str {
    match status {
        CredentialFillStatus::RequiresUserApproval => "credential_fill_approval_required",
        CredentialFillStatus::Pending => "credential_fill_pending",
        CredentialFillStatus::Approved => "credential_fill_approved",
        CredentialFillStatus::Filled => "credential_fill_filled",
        CredentialFillStatus::Denied => "credential_fill_denied",
        CredentialFillStatus::NoMatch => "credential_fill_no_match",
        CredentialFillStatus::OriginMismatch => "credential_fill_origin_mismatch",
        CredentialFillStatus::PolicyBlocked => "credential_fill_policy_blocked",
        CredentialFillStatus::UnlockRequired => "credential_fill_unlock_required",
        CredentialFillStatus::ProviderLocked => "credential_fill_provider_locked",
        CredentialFillStatus::Unavailable => "credential_fill_unavailable",
        CredentialFillStatus::Failed => "credential_fill_failed",
        CredentialFillStatus::PrivacyGuardActive => "credential_privacy_guard_active",
    }
}

fn safe_credential_alias(alias: &str) -> String {
    if !alias.is_empty()
        && alias.len() <= 128
        && alias
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'-' | b'.'))
    {
        alias.to_string()
    } else {
        REDACTED.to_string()
    }
}

fn clear_session_credential_privacy_guard(session: &mut ManagedSession) {
    session.credential_privacy_guard_active = false;
    for fill in session.credential_fills.values_mut() {
        fill.record.privacy_guard_active = false;
    }
}

fn ensure_session_releasable(session: &ManagedSession) -> Result<()> {
    if session.credential_privacy_guard_active
        || session
            .credential_fills
            .values()
            .any(|fill| fill.record.privacy_guard_active)
    {
        bail!("credential privacy guard active; clear it before releasing session");
    }
    if session
        .credential_fills
        .values()
        .any(|fill| !fill.record.is_terminal())
    {
        bail!(
            "credential fill pending; approve, deny, or wait for terminal status before releasing session"
        );
    }
    Ok(())
}

fn sanitize_credential_record_for_persist(
    record: &CredentialFillStatusRecord,
) -> CredentialFillStatusRecord {
    let mut record = record.clone();
    if matches!(
        record.status,
        CredentialFillStatus::RequiresUserApproval
            | CredentialFillStatus::Pending
            | CredentialFillStatus::Approved
            | CredentialFillStatus::PrivacyGuardActive
    ) || record.privacy_guard_active
    {
        record.status = CredentialFillStatus::Failed;
        record.redacted_message = Some("runtime_restart_expired".to_string());
    }
    record.privacy_guard_active = false;
    record
}

fn recover_persisted_credential_fill(record: CredentialFillStatusRecord) -> ManagedCredentialFill {
    let record = sanitize_credential_record_for_persist(&record);
    ManagedCredentialFill {
        expires_at: record.updated_at,
        record,
        username_selector: None,
        password_selector: None,
        purpose: None,
    }
}

fn takeover_access_mode_for_session(
    session: &ManagedSession,
    token: &str,
    now: DateTime<Utc>,
) -> Option<LiveLinkMode> {
    if session.info.status != SessionStatus::PausedForHuman || token.is_empty() {
        return None;
    }
    if !session.takeover_token.is_empty()
        && session.takeover_token == token
        && now < session.takeover_expires_at
    {
        return Some(LiveLinkMode::Interactive);
    }
    session
        .live_links
        .values()
        .find(|link| !link.revoked && link.token == token && now < link.expires_at)
        .map(|link| link.mode)
}

fn live_link_summary(id: Uuid, link: &LiveLinkRecord, now: DateTime<Utc>) -> LiveLinkSummary {
    LiveLinkSummary {
        id,
        mode: link.mode,
        created_at: link.created_at,
        expires_at: link.expires_at,
        revoked: link.revoked,
        expired: now >= link.expires_at,
    }
}

fn remove_persisted_session_record(path: PathBuf) -> Result<()> {
    match fs::remove_file(&path) {
        Ok(()) => Ok(()),
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(err) => Err(err).with_context(|| format!("remove {}", path.display())),
    }
}

fn remove_dir_if_exists(path: &Path) -> Result<()> {
    match fs::remove_dir_all(path) {
        Ok(()) => Ok(()),
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(err) => Err(err).with_context(|| format!("remove {}", path.display())),
    }
}

fn append_event_to_path(
    artifacts_dir: &Path,
    kind: &str,
    payload: serde_json::Value,
) -> Result<()> {
    ensure_private_dir(artifacts_dir)?;
    let path = artifacts_dir.join("events.jsonl");
    let mut file = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)?;
    let payload = redact_json_value(payload);
    let line = json!({"ts": Utc::now(), "kind": kind, "payload": payload});
    writeln!(file, "{}", serde_json::to_string(&line)?)?;
    Ok(())
}

fn copy_profile_read_only_seed(from: &Path, to: &Path) -> Result<()> {
    for entry in fs::read_dir(from)? {
        let entry = entry?;
        let name = entry.file_name();
        let name_str = name.to_string_lossy();
        if name_str.starts_with("Singleton") || name_str == "DevToolsActivePort" {
            continue;
        }
        let dest = to.join(&name);
        let file_type = entry.file_type()?;
        if file_type.is_dir() {
            fs::create_dir_all(&dest)?;
            copy_profile_read_only_seed(&entry.path(), &dest)?;
        } else if file_type.is_file() {
            let _ = fs::copy(entry.path(), dest);
        }
    }
    Ok(())
}

fn newest_modified_time(path: &Path) -> Result<SystemTime> {
    let metadata = fs::metadata(path).with_context(|| format!("stat {}", path.display()))?;
    let mut newest = metadata.modified().unwrap_or(SystemTime::UNIX_EPOCH);
    if metadata.is_dir() {
        for entry in fs::read_dir(path).with_context(|| format!("read {}", path.display()))? {
            let child = newest_modified_time(&entry?.path())?;
            if child > newest {
                newest = child;
            }
        }
    }
    Ok(newest)
}

fn infer_kind(path: &Path) -> String {
    match path.extension().and_then(|ext| ext.to_str()) {
        Some("png") => "screenshot".to_string(),
        Some("jsonl") => "event_log".to_string(),
        _ => "file".to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        credentials::{CredentialBrokerMode, CredentialFillStatus},
        models::{
            BrowserPersona, CaptchaReportState, CaptchaResolveOutcome, CaptchaStatus,
            CredentialFillStartRequest, Viewport,
        },
        test_support::{
            MockBackend, MockCdpServer, WsReply, persistent_req, test_config, token_from_url,
        },
    };
    #[cfg(unix)]
    use std::os::unix::fs::PermissionsExt;
    use std::{
        fs,
        sync::{Arc, Mutex},
    };
    use tokio::time::sleep;

    fn test_cdp_ws_url(port: u16, browser_id: &str) -> String {
        let prefix = format!("ws://127.0.0.1:{port}/devtools");
        format!("{prefix}/browser/{browser_id}")
    }

    fn test_takeover_url(port: u16, session_id: &str, token: &str) -> String {
        let base = format!("http://127.0.0.1:{port}");
        let path = format!("/takeover/{session_id}");
        format!("{base}{path}?token={token}")
    }

    fn test_provider_ref_prefix() -> String {
        let mut prefix = String::from("op:");
        prefix.push_str("//");
        prefix
    }

    fn test_provider_ref(field: &str) -> String {
        format!(
            "{}demo-vault/demo-login/{field}",
            test_provider_ref_prefix()
        )
    }

    struct NeverLaunchBackend;

    #[derive(Default)]
    struct RecordingTimeoutBackend {
        seen: Mutex<Vec<Duration>>,
    }

    #[async_trait::async_trait]
    impl BrowserBackend for RecordingTimeoutBackend {
        async fn launch(&self, options: StartSessionOptions) -> Result<LaunchedBrowser> {
            self.seen.lock().unwrap().push(options.launch_timeout);
            let process = tokio::process::Command::new("sleep")
                .arg("60")
                .spawn()
                .context("spawn timeout recording browser")?;
            Ok(LaunchedBrowser {
                process,
                port: 1,
                http_base: "http://127.0.0.1:1".to_string(),
                cdp_ws_url: test_cdp_ws_url(1, "timeout-recording"),
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
        http_base: String,
        cdp_ws_url: String,
    }

    #[async_trait::async_trait]
    impl BrowserBackend for ShortLivedBackend {
        async fn launch(&self, _options: StartSessionOptions) -> Result<LaunchedBrowser> {
            let process = tokio::process::Command::new("sh")
                .arg("-c")
                .arg("sleep 0.05")
                .spawn()
                .context("spawn short-lived browser")?;
            Ok(LaunchedBrowser {
                process,
                port: 1,
                http_base: self.http_base.clone(),
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

    #[async_trait::async_trait]
    impl BrowserBackend for NeverLaunchBackend {
        async fn launch(&self, _options: StartSessionOptions) -> Result<LaunchedBrowser> {
            bail!("intentional test backend")
        }
        async fn close(&self, _launched: &mut LaunchedBrowser) -> Result<()> {
            Ok(())
        }
    }

    async fn mock_store(
        default_headless: bool,
        takeover_ttl: Duration,
    ) -> (tempfile::TempDir, MockCdpServer, Arc<AppStore>) {
        let tmp = tempfile::tempdir().unwrap();
        let cdp = MockCdpServer::spawn().await;
        let mut config = test_config(tmp.path().to_path_buf(), None);
        config.default_headless = default_headless;
        config.takeover_ttl = takeover_ttl;
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
        (tmp, cdp, store)
    }

    fn assert_dir_empty(path: &Path) {
        assert!(
            fs::read_dir(path).unwrap().next().is_none(),
            "expected {} to be empty",
            path.display()
        );
    }

    fn write_demo_credential_policy(root: &Path) -> PathBuf {
        let policy_path = root.join("credential-policy.json");
        fs::write(
            &policy_path,
            serde_json::to_vec_pretty(&json!({
                "aliases": {
                    "demo-login": {
                        "allowed_origins": ["https://example.test"],
                        "provider_refs": {
                            "username": test_provider_ref("username"),
                            "password": test_provider_ref("password")
                        },
                        "allowed_fields": ["username", "password"]
                    }
                }
            }))
            .unwrap(),
        )
        .unwrap();
        policy_path
    }

    fn shell_single_quoted_path(path: &Path) -> String {
        format!("'{}'", path.to_string_lossy().replace('\'', "'\\''"))
    }

    fn install_recording_op_script(root: &Path) -> (PathBuf, PathBuf) {
        let marker_path = root.join("op-provider-called");
        let op_path = root.join("op-mock.sh");
        fs::write(
            &op_path,
            format!(
                "#!/bin/sh\nprintf 'hit' >> {}\nprintf '%s' synthetic-secret\n",
                shell_single_quoted_path(&marker_path)
            ),
        )
        .unwrap();
        #[cfg(unix)]
        {
            let mut permissions = fs::metadata(&op_path).unwrap().permissions();
            permissions.set_mode(0o700);
            fs::set_permissions(&op_path, permissions).unwrap();
        }
        (op_path, marker_path)
    }

    async fn onepassword_mock_store_with_marker()
    -> (tempfile::TempDir, MockCdpServer, Arc<AppStore>, PathBuf) {
        let tmp = tempfile::tempdir().unwrap();
        let cdp = MockCdpServer::spawn().await;
        let policy_path = write_demo_credential_policy(tmp.path());
        let (op_path, marker_path) = install_recording_op_script(tmp.path());
        let mut config = test_config(tmp.path().to_path_buf(), None);
        config.credential_provider = CredentialBrokerMode::OnePasswordCli;
        config.credential_policy_path = Some(policy_path);
        config.op_path = Some(op_path);
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
        (tmp, cdp, store, marker_path)
    }

    async fn enqueue_credential_context(
        cdp: &MockCdpServer,
        origin: &str,
        username_usable: bool,
        password_usable: bool,
    ) {
        cdp.enqueue_page_reply(WsReply::Success(json!({"result": {"value": {
            "observed_origin": origin,
            "top_frame": true,
            "same_origin_frame": true,
            "username_present": true,
            "password_present": true,
            "username": {
                "requested": true,
                "present": true,
                "usable": username_usable,
                "unsafe_reason": if username_usable { serde_json::Value::Null } else { json!("field_disabled") }
            },
            "password": {
                "requested": true,
                "present": true,
                "usable": password_usable,
                "unsafe_reason": if password_usable { serde_json::Value::Null } else { json!("field_disabled") }
            }
        }}})))
        .await;
    }

    #[tokio::test]
    async fn approve_revalidates_field_safety_before_provider_read() {
        let (_tmp, cdp, store, marker_path) = onepassword_mock_store_with_marker().await;
        let created = store.create_session(persistent_req("p1")).await.unwrap();
        enqueue_credential_context(&cdp, "https://example.test", true, true).await;
        let requested = store
            .request_credential_fill(
                created.id,
                CredentialFillStartRequest {
                    alias: "demo-login".into(),
                    username_selector: Some("#user".into()),
                    password_selector: Some("#pass".into()),
                    purpose: Some("login".into()),
                    expected_origin: Some("https://example.test".into()),
                },
            )
            .await
            .unwrap();
        assert_eq!(requested.status, CredentialFillStatus::RequiresUserApproval);

        enqueue_credential_context(&cdp, "https://example.test", true, false).await;
        let approved = store
            .approve_credential_fill(
                created.id,
                requested.request_id,
                Some("human approved".into()),
            )
            .await
            .unwrap();

        assert_eq!(approved.status, CredentialFillStatus::NoMatch);
        assert!(
            !marker_path.exists(),
            "provider must not be read after unsafe field revalidation"
        );

        store.delete_session(created.id).await.unwrap();
        cdp.stop().await;
    }

    #[tokio::test]
    async fn deny_credential_fill_accepts_redacted_note() {
        let (tmp, cdp, store) = mock_store(true, Duration::from_secs(60)).await;
        let created = store.create_session(persistent_req("p1")).await.unwrap();
        enqueue_credential_context(&cdp, "https://example.test", true, true).await;
        let requested = store
            .request_credential_fill(
                created.id,
                CredentialFillStartRequest {
                    alias: "demo-login".into(),
                    username_selector: Some("#user".into()),
                    password_selector: Some("#pass".into()),
                    purpose: Some("login".into()),
                    expected_origin: Some("https://example.test".into()),
                },
            )
            .await
            .unwrap();

        let denied = store
            .deny_credential_fill(
                created.id,
                requested.request_id,
                Some("denied because password looked wrong".into()),
            )
            .await
            .unwrap();

        assert_eq!(denied.status, CredentialFillStatus::Denied);
        let redacted_message = denied.redacted_message.as_deref().unwrap_or_default();
        assert!(redacted_message.contains(crate::security::REDACTED));
        assert!(!redacted_message.contains("raw-secret"));
        let events_path = tmp
            .path()
            .join("sessions")
            .join(created.id.to_string())
            .join("artifacts")
            .join("events.jsonl");
        let events = fs::read_to_string(events_path).unwrap();
        assert!(!events.contains("password looked wrong"));
        assert!(events.contains(crate::security::REDACTED));

        store.delete_session(created.id).await.unwrap();
        cdp.stop().await;
    }

    #[tokio::test]
    async fn release_refuses_pending_or_guarded_credential_fills_without_clearing_takeover_state() {
        let (_tmp, cdp, store, _marker_path) = onepassword_mock_store_with_marker().await;
        let created = store.create_session(persistent_req("p1")).await.unwrap();
        let paused = store
            .pause_for_human(created.id, Some("credential checkpoint".into()))
            .await
            .unwrap();
        let takeover_token = token_from_url(paused.takeover_url.as_ref().unwrap()).to_string();
        let live_link = store
            .create_live_link(created.id, LiveLinkMode::ReadOnly)
            .await
            .unwrap();
        let live_link_token = token_from_url(&live_link.url).to_string();
        enqueue_credential_context(&cdp, "https://example.test", true, true).await;
        let requested = store
            .request_credential_fill(
                created.id,
                CredentialFillStartRequest {
                    alias: "demo-login".into(),
                    username_selector: Some("#user".into()),
                    password_selector: Some("#pass".into()),
                    purpose: Some("login".into()),
                    expected_origin: Some("https://example.test".into()),
                },
            )
            .await
            .unwrap();
        assert_eq!(requested.status, CredentialFillStatus::RequiresUserApproval);

        let pending_error = store.release(created.id).await.unwrap_err().to_string();
        assert!(pending_error.contains("credential fill pending"));
        let still_paused = store.get_session(created.id).await.unwrap();
        assert_eq!(still_paused.status, SessionStatus::PausedForHuman);
        assert_eq!(still_paused.takeover_url, paused.takeover_url);
        assert_eq!(
            store
                .takeover_access_mode(created.id, &takeover_token)
                .await
                .unwrap(),
            LiveLinkMode::Interactive
        );
        assert_eq!(
            store
                .takeover_access_mode(created.id, &live_link_token)
                .await
                .unwrap(),
            LiveLinkMode::ReadOnly
        );

        store
            .set_credential_privacy_guard(created.id, Some(requested.request_id), true)
            .await
            .unwrap();
        let guard_error = store.release(created.id).await.unwrap_err().to_string();
        assert!(guard_error.contains("credential privacy guard active"));
        let (records, privacy_guard_active) =
            store.credential_fill_snapshot(created.id).await.unwrap();
        assert!(privacy_guard_active);
        assert!(records.iter().any(|record| record.privacy_guard_active));
        assert_eq!(
            store
                .takeover_access_mode(created.id, &takeover_token)
                .await
                .unwrap(),
            LiveLinkMode::Interactive
        );
        assert_eq!(
            store
                .takeover_access_mode(created.id, &live_link_token)
                .await
                .unwrap(),
            LiveLinkMode::ReadOnly
        );

        store
            .clear_credential_privacy_guard(created.id)
            .await
            .unwrap();
        store
            .deny_credential_fill(created.id, requested.request_id, Some("not now".into()))
            .await
            .unwrap();
        store.release(created.id).await.unwrap();
        assert!(
            !store
                .validate_takeover_token(created.id, &takeover_token)
                .await
        );
        assert!(
            store
                .takeover_access_mode(created.id, &live_link_token)
                .await
                .is_none()
        );

        cdp.stop().await;
    }

    #[tokio::test]
    async fn credential_store_status_privacy_nomatch_and_expiry_branches() {
        let (_tmp, cdp, store, _marker_path) = onepassword_mock_store_with_marker().await;
        let created = store.create_session(persistent_req("p1")).await.unwrap();

        enqueue_credential_context(&cdp, "https://example.test", false, true).await;
        let no_match = store
            .request_credential_fill(
                created.id,
                CredentialFillStartRequest {
                    alias: "demo-login".into(),
                    username_selector: Some("#user".into()),
                    password_selector: Some("#pass".into()),
                    purpose: Some("login".into()),
                    expected_origin: Some("https://example.test".into()),
                },
            )
            .await
            .unwrap();
        assert_eq!(no_match.status, CredentialFillStatus::NoMatch);
        assert_eq!(
            store
                .credential_fill_status(created.id, no_match.request_id)
                .await
                .unwrap()
                .status,
            CredentialFillStatus::NoMatch
        );
        assert!(
            store
                .credential_fill_status(created.id, Uuid::new_v4())
                .await
                .unwrap_err()
                .to_string()
                .contains("credential fill not found")
        );

        enqueue_credential_context(&cdp, "https://example.test", true, true).await;
        let pending = store
            .request_credential_fill(
                created.id,
                CredentialFillStartRequest {
                    alias: "demo-login".into(),
                    username_selector: Some("#user".into()),
                    password_selector: Some("#pass".into()),
                    purpose: Some("login".into()),
                    expected_origin: Some("https://example.test".into()),
                },
            )
            .await
            .unwrap();
        store
            .set_credential_privacy_guard(created.id, Some(pending.request_id), true)
            .await
            .unwrap();
        assert!(
            store
                .request_credential_fill(
                    created.id,
                    CredentialFillStartRequest {
                        alias: "demo-login".into(),
                        username_selector: Some("#user".into()),
                        password_selector: Some("#pass".into()),
                        purpose: Some("login".into()),
                        expected_origin: Some("https://example.test".into()),
                    },
                )
                .await
                .unwrap_err()
                .to_string()
                .contains("credential privacy guard active")
        );
        store
            .clear_credential_privacy_guard(created.id)
            .await
            .unwrap();
        {
            let mut sessions = store.sessions.lock().await;
            let fill = sessions
                .get_mut(&created.id)
                .unwrap()
                .credential_fills
                .get_mut(&pending.request_id)
                .unwrap();
            fill.expires_at = Utc::now() - chrono::Duration::seconds(1);
        }
        let expired = store
            .approve_credential_fill(created.id, pending.request_id, Some("too late".into()))
            .await
            .unwrap();
        assert_eq!(expired.status, CredentialFillStatus::Failed);
        assert_eq!(
            expired.redacted_message.as_deref(),
            Some("approval_expired")
        );

        store.delete_session(created.id).await.unwrap();
        cdp.stop().await;
    }

    #[tokio::test]
    async fn create_session_uses_runtime_default_persona_when_request_omits_persona() {
        let tmp = tempfile::tempdir().unwrap();
        let cdp = MockCdpServer::spawn().await;
        let mut config = test_config(tmp.path().to_path_buf(), None);
        config.default_persona = BrowserPersona {
            locale: "pt-PT".into(),
            accept_language: "pt-PT,pt;q=0.9,en;q=0.8".into(),
            timezone_id: "Europe/Lisbon".into(),
            platform: "Linux x86_64".into(),
            user_agent: None,
            viewport: Viewport {
                width: 1365,
                height: 768,
            },
            screen: Viewport {
                width: 1365,
                height: 768,
            },
            device_scale_factor: 1.0,
            hardware_concurrency: 8,
            device_memory_gb: 8,
            max_touch_points: 0,
        };
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

        let created = store
            .create_session(CreateSessionRequest {
                profile_id: Some("persona-default".into()),
                headless: Some(true),
                viewport: None,
                persist_profile: Some(false),
                launch_timeout_secs: None,
                persona: None,
                ..Default::default()
            })
            .await
            .unwrap();

        let events_path = tmp
            .path()
            .join("sessions")
            .join(created.id.to_string())
            .join("artifacts")
            .join("events.jsonl");
        let first_event: serde_json::Value = serde_json::from_str(
            fs::read_to_string(events_path)
                .unwrap()
                .lines()
                .next()
                .unwrap(),
        )
        .unwrap();
        assert_eq!(
            first_event["payload"]["persona"]["timezone_id"],
            "Europe/Lisbon"
        );
        assert_eq!(first_event["payload"]["persona"]["locale"], "pt-PT");
        assert_eq!(created.viewport.width, 1365);

        store.delete_session(created.id).await.unwrap();
        cdp.stop().await;
    }

    #[tokio::test]
    async fn create_session_defaults_to_persistent_warmed_profile_reuse() {
        let (tmp, cdp, store) = mock_store(true, Duration::from_secs(60)).await;
        let created = store
            .create_session(CreateSessionRequest {
                profile_id: Some("p1".into()),
                headless: Some(true),
                viewport: None,
                persist_profile: None,
                launch_timeout_secs: None,
                persona: None,
                ..Default::default()
            })
            .await
            .unwrap();

        assert!(created.persist_profile);
        assert_eq!(created.profile_id, "p1");
        let profile_dir = tmp.path().join("profiles").join("p1");
        {
            let sessions = store.sessions.lock().await;
            let managed = sessions.get(&created.id).unwrap();
            assert_eq!(managed.user_data_dir, profile_dir);
            assert!(managed.persist_profile);
        }
        assert!(profile_dir.is_dir());
        assert!(
            store
                .create_session(CreateSessionRequest {
                    profile_id: Some("p1".into()),
                    headless: Some(true),
                    viewport: None,
                    persist_profile: None,
                    launch_timeout_secs: None,
                    persona: None,
                    ..Default::default()
                })
                .await
                .is_err()
        );

        store.delete_session(created.id).await.unwrap();
        assert!(profile_dir.is_dir());
        let replacement = store
            .create_session(CreateSessionRequest {
                profile_id: Some("p1".into()),
                headless: Some(true),
                viewport: None,
                persist_profile: None,
                launch_timeout_secs: None,
                persona: None,
                ..Default::default()
            })
            .await
            .unwrap();
        store.delete_session(replacement.id).await.unwrap();
        cdp.stop().await;
    }

    #[tokio::test]
    async fn profile_lock_releases_when_launch_fails() {
        let tmp = tempfile::tempdir().unwrap();
        let store = AppStore::new(
            test_config(tmp.path().to_path_buf(), None),
            Arc::new(NeverLaunchBackend),
        )
        .await
        .unwrap();
        let req = persistent_req("p1");
        assert!(store.create_session(req.clone()).await.is_err());
        assert!(store.create_session(req).await.is_err());
        assert_dir_empty(&tmp.path().join("sessions"));
        assert_dir_empty(&tmp.path().join("tmp"));
    }

    #[tokio::test]
    async fn launch_failures_without_persistent_profiles_cleanup_scratch_and_profile_locks() {
        let tmp = tempfile::tempdir().unwrap();
        let store = AppStore::new(
            test_config(tmp.path().to_path_buf(), None),
            Arc::new(NeverLaunchBackend),
        )
        .await
        .unwrap();

        let seed_profile = tmp.path().join("profiles").join("p1");
        fs::create_dir_all(&seed_profile).unwrap();
        fs::write(seed_profile.join("seed.txt"), b"seed").unwrap();

        let err = store
            .create_session(CreateSessionRequest {
                profile_id: Some("p1".into()),
                headless: Some(true),
                viewport: None,
                persist_profile: Some(false),
                launch_timeout_secs: None,
                persona: None,
                ..Default::default()
            })
            .await
            .unwrap_err();

        assert!(err.to_string().contains("intentional test backend"));
        assert!(store.profile_locks.lock().await.is_empty());
        assert!(seed_profile.join("seed.txt").exists());
        assert_dir_empty(&tmp.path().join("sessions"));
        assert_dir_empty(&tmp.path().join("tmp"));
    }

    #[tokio::test]
    async fn never_launch_backend_close_is_callable() {
        let mut launched = LaunchedBrowser {
            process: tokio::process::Command::new("true").spawn().unwrap(),
            port: 1,
            http_base: "http://127.0.0.1:1".to_string(),
            cdp_ws_url: test_cdp_ws_url(1, "fake"),
            persona_guard: None,
        };

        NeverLaunchBackend.close(&mut launched).await.unwrap();
    }

    #[tokio::test]
    async fn create_session_uses_runtime_default_and_request_launch_timeout_overrides() {
        let tmp = tempfile::tempdir().unwrap();
        let mut config = test_config(tmp.path().to_path_buf(), None);
        config.launch_timeout = Duration::from_secs(11);
        let backend = Arc::new(RecordingTimeoutBackend::default());
        let store = AppStore::new(config, backend.clone()).await.unwrap();

        let first = store
            .create_session(CreateSessionRequest {
                profile_id: Some("p1".into()),
                headless: Some(true),
                viewport: None,
                persist_profile: Some(false),
                launch_timeout_secs: None,
                persona: None,
                ..Default::default()
            })
            .await
            .unwrap();
        let second = store
            .create_session(CreateSessionRequest {
                profile_id: Some("p2".into()),
                headless: Some(true),
                viewport: None,
                persist_profile: Some(false),
                launch_timeout_secs: Some(2),
                persona: None,
                ..Default::default()
            })
            .await
            .unwrap();

        assert_eq!(
            *backend.seen.lock().unwrap(),
            vec![Duration::from_secs(11), Duration::from_secs(2)]
        );

        store.delete_session(first.id).await.unwrap();
        store.delete_session(second.id).await.unwrap();
    }

    #[tokio::test]
    async fn shutdown_all_reclaims_nonpersistent_tmp_and_preserves_session_artifacts() {
        let (_tmp, cdp, store) = mock_store(true, Duration::from_secs(60)).await;
        let created = store
            .create_session(CreateSessionRequest {
                profile_id: Some("p1".into()),
                headless: Some(true),
                viewport: None,
                persist_profile: Some(false),
                launch_timeout_secs: None,
                persona: None,
                ..Default::default()
            })
            .await
            .unwrap();

        let (user_data_dir, artifacts_dir, downloads_dir, record_path) = {
            let sessions = store.sessions.lock().await;
            let managed = sessions.get(&created.id).unwrap();
            (
                managed.user_data_dir.clone(),
                managed.artifacts_dir.clone(),
                managed.downloads_dir.clone(),
                store.session_record_path(created.id),
            )
        };

        assert!(user_data_dir.exists());
        assert!(artifacts_dir.exists());
        assert!(downloads_dir.exists());
        assert!(record_path.exists());

        store.shutdown_all().await.unwrap();

        assert!(!user_data_dir.exists());
        assert!(!store.session_tmp_dir(created.id).exists());
        assert!(artifacts_dir.exists());
        assert!(downloads_dir.exists());
        assert!(record_path.exists());
        assert_eq!(
            store.get_session(created.id).await.unwrap().status,
            SessionStatus::Closed
        );

        let persisted: PersistedSessionRecord =
            serde_json::from_str(&fs::read_to_string(&record_path).unwrap()).unwrap();
        assert_eq!(persisted.info.status, SessionStatus::Closed);
        assert_eq!(persisted.user_data_dir, user_data_dir);

        let events = fs::read_to_string(artifacts_dir.join("events.jsonl")).unwrap();
        assert!(events.contains("session_closing"));
        assert!(events.contains("session_closed"));
        assert!(events.contains("shutdown"));

        cdp.stop().await;
    }

    #[tokio::test]
    async fn session_record_persists_expected_paths_and_metadata() {
        let tmp = tempfile::tempdir().unwrap();
        let cdp = MockCdpServer::spawn().await;
        let store = AppStore::new(
            test_config(tmp.path().to_path_buf(), None),
            Arc::new(MockBackend::new(
                cdp.base_url.clone(),
                cdp.browser_ws_url.clone(),
            )),
        )
        .await
        .unwrap();

        let created = store.create_session(persistent_req("p1")).await.unwrap();
        store
            .pause_for_human(created.id, Some("manual review".into()))
            .await
            .unwrap();

        let session_dir = tmp.path().join("sessions").join(created.id.to_string());
        let record_path = session_dir.join("session.json");
        let record: PersistedSessionRecord =
            serde_json::from_str(&fs::read_to_string(&record_path).unwrap()).unwrap();

        assert_eq!(record.info.id, created.id);
        assert_eq!(record.info.status, SessionStatus::PausedForHuman);
        assert_eq!(record.info.profile_id, "p1");
        assert_eq!(record.info.pause_reason.as_deref(), Some("manual review"));
        assert_eq!(
            record.info.takeover_url.as_deref(),
            Some(crate::security::REDACTED)
        );
        assert_eq!(
            record.info.cdp_ws_url.as_deref(),
            Some(crate::security::REDACTED)
        );
        let record_text = fs::read_to_string(&record_path).unwrap();
        assert!(!record_text.contains("/devtools/browser/"));
        assert!(!record_text.contains("ws://127.0.0.1"));
        assert_eq!(record.user_data_dir, tmp.path().join("profiles").join("p1"));
        assert_eq!(record.artifacts_dir, session_dir.join("artifacts"));
        assert_eq!(record.downloads_dir, session_dir.join("downloads"));
        assert!(record.persist_profile);

        store.delete_session(created.id).await.unwrap();
        cdp.stop().await;
    }

    #[tokio::test]
    async fn paused_session_persistence_and_events_redact_sensitive_artifacts() {
        let (tmp, cdp, store) = mock_store(true, Duration::from_secs(60)).await;
        let created = store.create_session(persistent_req("p1")).await.unwrap();
        let sensitive = format!("{}{}", "raw", "-secret");
        let reason = format!("oauth password step {sensitive}");

        let paused = store
            .pause_for_human(created.id, Some(reason))
            .await
            .unwrap();
        let takeover_token = token_from_url(paused.takeover_url.as_ref().unwrap()).to_string();
        assert_eq!(
            paused.pause_reason.as_deref(),
            Some(crate::security::REDACTED)
        );
        assert!(!takeover_token.is_empty());
        assert!(
            store
                .validate_takeover_token(created.id, &takeover_token)
                .await
        );

        {
            let sessions = store.sessions.lock().await;
            let managed = sessions.get(&created.id).unwrap();
            store
                .append_event(
                    managed,
                    "sensitive_probe",
                    json!({
                        "takeover_url": paused.takeover_url,
                        "cdp_ws_url": cdp.browser_ws_url,
                        "cookie": sensitive,
                        "auth_headers": {"authorization": format!("Bearer {sensitive}")},
                        "request_body": {"card_number": "4111111111111111"},
                        "raw_fingerprint_dump": format!("fingerprint dump {sensitive}"),
                        "safe_metrics": {"width": 1280, "height": 720},
                    }),
                )
                .unwrap();
        }

        let session_dir = tmp.path().join("sessions").join(created.id.to_string());
        let record: PersistedSessionRecord =
            serde_json::from_str(&fs::read_to_string(session_dir.join("session.json")).unwrap())
                .unwrap();
        assert_eq!(
            record.info.takeover_url.as_deref(),
            Some(crate::security::REDACTED)
        );
        assert_eq!(
            record.info.cdp_ws_url.as_deref(),
            Some(crate::security::REDACTED)
        );
        let record_text = serde_json::to_string(&record).unwrap();
        assert!(!record_text.contains(&takeover_token));
        assert!(!record_text.contains(&sensitive));
        assert!(!record_text.contains("/devtools/browser/"));
        assert!(!record_text.contains("ws://127.0.0.1"));

        let events = fs::read_to_string(session_dir.join("artifacts/events.jsonl")).unwrap();
        assert!(events.contains(crate::security::REDACTED));
        assert!(events.contains("safe_metrics"));
        assert!(!events.contains(&takeover_token));
        assert!(!events.contains(&sensitive));
        assert!(!events.contains("/devtools/browser/"));
        assert!(!events.contains("ws://127.0.0.1"));
        assert!(!events.contains("4111111111111111"));
        assert!(!events.contains("Bearer"));
        assert!(!events.contains("fingerprint dump"));

        store.delete_session(created.id).await.unwrap();
        cdp.stop().await;
    }

    #[test]
    fn load_persisted_sessions_preserves_non_live_records_and_marks_live_ones_failed() {
        fn write_record(root: &Path, record: &PersistedSessionRecord) {
            let session_dir = root.join("sessions").join(record.info.id.to_string());
            fs::create_dir_all(&record.user_data_dir).unwrap();
            fs::create_dir_all(&record.artifacts_dir).unwrap();
            fs::create_dir_all(&record.downloads_dir).unwrap();
            fs::write(
                session_dir.join("session.json"),
                serde_json::to_vec_pretty(record).unwrap(),
            )
            .unwrap();
        }

        let tmp = tempfile::tempdir().unwrap();
        let config = test_config(tmp.path().to_path_buf(), None);
        let now = Utc::now();
        let live_id = Uuid::new_v4();
        let closed_id = Uuid::new_v4();
        let failed_id = Uuid::new_v4();

        let live = PersistedSessionRecord {
            info: SessionInfo {
                id: live_id,
                status: SessionStatus::PausedForHuman,
                cdp_ws_url: Some(test_cdp_ws_url(9222, "live")),
                takeover_url: Some(test_takeover_url(7788, "live", "***")),
                profile_id: "live-profile".into(),
                persist_profile: true,
                headless: true,
                viewport: crate::models::Viewport::default(),
                created_at: now,
                updated_at: now,
                pause_reason: Some("manual approval".into()),
                webrtc_ip_policy: Default::default(),
                gpu_policy: Default::default(),
                captcha_policy: Default::default(),
                captcha_status: Default::default(),
                captcha_challenge_type: None,
                captcha_solver_status: None,
            },
            user_data_dir: tmp.path().join("profiles").join("live-profile"),
            artifacts_dir: tmp
                .path()
                .join("sessions")
                .join(live_id.to_string())
                .join("artifacts"),
            downloads_dir: tmp
                .path()
                .join("sessions")
                .join(live_id.to_string())
                .join("downloads"),
            persist_profile: true,
            credential_fills: Vec::new(),
            credential_privacy_guard_active: false,
        };
        let closed = PersistedSessionRecord {
            info: SessionInfo {
                id: closed_id,
                status: SessionStatus::Closed,
                cdp_ws_url: None,
                takeover_url: None,
                profile_id: "closed-profile".into(),
                persist_profile: true,
                headless: true,
                viewport: crate::models::Viewport::default(),
                created_at: now,
                updated_at: now,
                pause_reason: None,
                webrtc_ip_policy: Default::default(),
                gpu_policy: Default::default(),
                captcha_policy: Default::default(),
                captcha_status: Default::default(),
                captcha_challenge_type: None,
                captcha_solver_status: None,
            },
            user_data_dir: tmp.path().join("profiles").join("closed-profile"),
            artifacts_dir: tmp
                .path()
                .join("sessions")
                .join(closed_id.to_string())
                .join("artifacts"),
            downloads_dir: tmp
                .path()
                .join("sessions")
                .join(closed_id.to_string())
                .join("downloads"),
            persist_profile: true,
            credential_fills: Vec::new(),
            credential_privacy_guard_active: false,
        };
        let failed = PersistedSessionRecord {
            info: SessionInfo {
                id: failed_id,
                status: SessionStatus::Failed,
                cdp_ws_url: None,
                takeover_url: None,
                profile_id: "failed-profile".into(),
                persist_profile: false,
                headless: true,
                viewport: crate::models::Viewport::default(),
                created_at: now,
                updated_at: now,
                pause_reason: None,
                webrtc_ip_policy: Default::default(),
                gpu_policy: Default::default(),
                captcha_policy: Default::default(),
                captcha_status: Default::default(),
                captcha_challenge_type: None,
                captcha_solver_status: None,
            },
            user_data_dir: tmp.path().join("tmp").join(failed_id.to_string()),
            artifacts_dir: tmp
                .path()
                .join("sessions")
                .join(failed_id.to_string())
                .join("artifacts"),
            downloads_dir: tmp
                .path()
                .join("sessions")
                .join(failed_id.to_string())
                .join("downloads"),
            persist_profile: false,
            credential_fills: Vec::new(),
            credential_privacy_guard_active: false,
        };

        write_record(tmp.path(), &live);
        write_record(tmp.path(), &closed);
        write_record(tmp.path(), &failed);

        let sessions = load_persisted_sessions(&config).unwrap();
        let recovered_live = sessions.get(&live_id).unwrap();
        let recovered_closed = sessions.get(&closed_id).unwrap();
        let recovered_failed = sessions.get(&failed_id).unwrap();

        assert_eq!(recovered_live.info.status, SessionStatus::Failed);
        assert!(recovered_live.info.pause_reason.is_none());
        assert!(recovered_live.info.takeover_url.is_none());
        assert!(recovered_live.info.cdp_ws_url.is_none());
        assert_eq!(recovered_closed.info.status, SessionStatus::Closed);
        assert_eq!(recovered_failed.info.status, SessionStatus::Failed);

        let live_events =
            fs::read_to_string(recovered_live.artifacts_dir.join("events.jsonl")).unwrap();
        assert!(live_events.contains("session_recovered_after_restart"));
        assert!(!recovered_closed.artifacts_dir.join("events.jsonl").exists());
        assert!(!recovered_failed.artifacts_dir.join("events.jsonl").exists());
    }

    #[tokio::test]
    async fn restart_recovery_marks_live_session_failed_preserves_artifacts_and_unlocks_profiles() {
        let tmp = tempfile::tempdir().unwrap();
        let cdp = MockCdpServer::spawn().await;
        cdp.set_screenshot_bytes(b"mock-png").await;
        let config = test_config(tmp.path().to_path_buf(), None);
        let store = Arc::new(
            AppStore::new(
                config.clone(),
                Arc::new(MockBackend::new(
                    cdp.base_url.clone(),
                    cdp.browser_ws_url.clone(),
                )),
            )
            .await
            .unwrap(),
        );

        let created = store.create_session(persistent_req("p1")).await.unwrap();
        store
            .pause_for_human(created.id, Some("manual review".into()))
            .await
            .unwrap();
        let screenshot = store.screenshot(created.id).await.unwrap();
        assert!(screenshot.starts_with(b"mock-png"));
        let downloads_dir = store.downloads_dir(created.id).await.unwrap();
        fs::write(downloads_dir.join("report.txt"), b"ok").unwrap();
        {
            let mut sessions = store.sessions.lock().await;
            let session = sessions.get_mut(&created.id).unwrap();
            if let Some(browser) = session.browser.as_mut() {
                let _ = browser.process.start_kill();
                let _ = browser.process.wait().await;
            }
        }
        drop(store);

        let recovered = AppStore::new(
            config,
            Arc::new(MockBackend::new(
                cdp.base_url.clone(),
                cdp.browser_ws_url.clone(),
            )),
        )
        .await
        .unwrap();

        let recovered_session = recovered.get_session(created.id).await.unwrap();
        assert_eq!(recovered_session.status, SessionStatus::Failed);
        assert!(recovered_session.takeover_url.is_none());
        assert!(recovered_session.cdp_ws_url.is_none());
        assert_eq!(
            recovered
                .list_profiles()
                .await
                .unwrap()
                .into_iter()
                .find(|profile| profile.id == "p1")
                .unwrap()
                .locked_by,
            None
        );
        let downloads = recovered
            .list_downloads(created.id)
            .await
            .unwrap()
            .downloads;
        assert_eq!(downloads.len(), 1);
        assert_eq!(downloads[0].name, "report.txt");
        assert_eq!(downloads[0].size_bytes, 2);
        assert!(
            recovered
                .artifacts(created.id)
                .await
                .unwrap()
                .artifacts
                .iter()
                .any(|artifact| artifact.kind == "event_log")
        );
        let events = fs::read_to_string(
            tmp.path()
                .join("sessions")
                .join(created.id.to_string())
                .join("artifacts")
                .join("events.jsonl"),
        )
        .unwrap();
        assert!(events.contains("session_recovered_after_restart"));

        let replacement = recovered
            .create_session(persistent_req("p1"))
            .await
            .unwrap();
        recovered.delete_session(replacement.id).await.unwrap();
        recovered.delete_session(created.id).await.unwrap();
        cdp.stop().await;
    }

    #[tokio::test]
    async fn list_sessions_marks_exited_browser_failed_and_releases_profile_lock() {
        let tmp = tempfile::tempdir().unwrap();
        let cdp = MockCdpServer::spawn().await;
        let store = AppStore::new(
            test_config(tmp.path().to_path_buf(), None),
            Arc::new(ShortLivedBackend {
                http_base: cdp.base_url.clone(),
                cdp_ws_url: cdp.browser_ws_url.clone(),
            }),
        )
        .await
        .unwrap();

        let created = store.create_session(persistent_req("p1")).await.unwrap();
        sleep(Duration::from_millis(120)).await;

        let listed = store.list_sessions().await;
        let failed = listed
            .iter()
            .find(|session| session.id == created.id)
            .unwrap();
        assert_eq!(failed.status, SessionStatus::Failed);
        assert!(failed.takeover_url.is_none());
        assert!(failed.cdp_ws_url.is_none());
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
        let events = fs::read_to_string(
            tmp.path()
                .join("sessions")
                .join(created.id.to_string())
                .join("artifacts")
                .join("events.jsonl"),
        )
        .unwrap();
        assert!(events.contains("browser_process_exited"));

        let replacement = store.create_session(persistent_req("p1")).await.unwrap();
        store.delete_session(replacement.id).await.unwrap();
        store.delete_session(created.id).await.unwrap();
        cdp.stop().await;
    }

    #[tokio::test]
    async fn wait_session_errors_when_sender_closes_while_paused() {
        let (_tmp, cdp, store) = mock_store(true, Duration::from_secs(60)).await;
        let created = store
            .create_session(CreateSessionRequest {
                profile_id: Some("p1".into()),
                headless: Some(true),
                viewport: None,
                persist_profile: Some(false),
                launch_timeout_secs: None,
                persona: None,
                ..Default::default()
            })
            .await
            .unwrap();
        store
            .pause_for_human(created.id, Some("wait here".into()))
            .await
            .unwrap();

        let waiter = {
            let store = store.clone();
            tokio::spawn(
                async move { store.wait_session(created.id, Duration::from_secs(1)).await },
            )
        };
        tokio::task::yield_now().await;

        let mut removed = store.sessions.lock().await.remove(&created.id).unwrap();
        if let Some(browser) = removed.browser.as_mut() {
            let _ = browser.process.start_kill();
            let _ = browser.process.wait().await;
        }
        drop(removed);

        let err = waiter.await.unwrap().unwrap_err();
        assert!(err.to_string().contains("session watcher closed"));
        cdp.stop().await;
    }

    #[tokio::test]
    async fn wait_session_ignores_paused_updates_until_release() {
        let (_tmp, cdp, store) = mock_store(true, Duration::from_secs(60)).await;
        let created = store
            .create_session(CreateSessionRequest {
                profile_id: Some("p1".into()),
                headless: Some(true),
                viewport: None,
                persist_profile: Some(false),
                launch_timeout_secs: None,
                persona: None,
                ..Default::default()
            })
            .await
            .unwrap();
        store
            .pause_for_human(created.id, Some("keep waiting".into()))
            .await
            .unwrap();

        let waiter = {
            let store = store.clone();
            tokio::spawn(
                async move { store.wait_session(created.id, Duration::from_secs(1)).await },
            )
        };
        tokio::task::yield_now().await;

        {
            let mut sessions = store.sessions.lock().await;
            let session = sessions.get_mut(&created.id).unwrap();
            session.info.updated_at = Utc::now();
            session.status_tx.send_replace(session.info.clone());
        }
        tokio::task::yield_now().await;

        let releaser = {
            let store = store.clone();
            tokio::spawn(async move {
                sleep(Duration::from_millis(25)).await;
                store.release(created.id).await.unwrap();
            })
        };

        let resumed = waiter.await.unwrap().unwrap();
        assert!(!resumed.timed_out);
        assert_eq!(resumed.session.status, SessionStatus::Running);
        releaser.await.unwrap();

        store.delete_session(created.id).await.unwrap();
        cdp.stop().await;
    }

    #[tokio::test]
    async fn session_lifecycle_copies_seed_profiles_records_events_and_lists_artifacts() {
        let (_tmp, cdp, store) = mock_store(false, Duration::from_secs(60)).await;
        let profile = store.create_profile(Some("p1".into())).await.unwrap();
        let profile_path = PathBuf::from(&profile.path);
        fs::write(profile_path.join("seed.txt"), b"seed").unwrap();
        fs::create_dir_all(profile_path.join("nested")).unwrap();
        fs::write(profile_path.join("nested/state.json"), b"{}").unwrap();
        fs::write(profile_path.join("SingletonLock"), b"skip").unwrap();
        fs::write(profile_path.join("DevToolsActivePort"), b"skip").unwrap();

        let created = store
            .create_session(CreateSessionRequest {
                profile_id: Some("p1".into()),
                headless: None,
                viewport: None,
                persist_profile: Some(false),
                launch_timeout_secs: None,
                persona: None,
                ..Default::default()
            })
            .await
            .unwrap();
        assert_eq!(created.profile_id, "p1");
        assert!(!created.persist_profile);
        assert!(!created.headless);
        assert!(created.takeover_url.is_none());

        let sessions = store.list_sessions().await;
        assert_eq!(sessions.len(), 1);
        assert_eq!(store.get_session(created.id).await.unwrap().id, created.id);

        {
            let sessions = store.sessions.lock().await;
            let managed = sessions.get(&created.id).unwrap();
            assert!(
                managed
                    .user_data_dir
                    .ends_with(created.id.to_string() + "/user-data")
            );
            assert_eq!(
                managed
                    .browser
                    .as_ref()
                    .expect("active session should retain launched browser")
                    .http_base,
                cdp.base_url
            );
            assert!(managed.takeover_token.is_empty());
            assert!(managed.user_data_dir.join("seed.txt").exists());
            assert!(managed.user_data_dir.join("nested/state.json").exists());
            assert!(!managed.user_data_dir.join("SingletonLock").exists());
            assert!(!managed.user_data_dir.join("DevToolsActivePort").exists());
        }

        assert_eq!(store.screenshot(created.id).await.unwrap(), b"png");
        store.input_click(created.id, 3.0, 4.0).await.unwrap();
        store.input_type(created.id, "hello").await.unwrap();
        store.input_key(created.id, "tab").await.unwrap();
        store.input_scroll(created.id, 0.0, 12.0).await.unwrap();

        let artifacts = store.artifacts(created.id).await.unwrap();
        assert_eq!(artifacts.session_id, created.id);
        assert!(artifacts.downloads_dir.ends_with("/downloads"));
        assert!(
            artifacts
                .artifacts
                .iter()
                .any(|artifact| artifact.kind == "event_log")
        );
        assert!(
            artifacts
                .artifacts
                .iter()
                .any(|artifact| artifact.kind == "screenshot")
        );

        let events_path = PathBuf::from(&artifacts.artifacts[0].path)
            .parent()
            .unwrap()
            .join("events.jsonl");
        let events = fs::read_to_string(events_path).unwrap();
        assert!(events.contains("session_created"));

        let deleted = store.delete_session(created.id).await.unwrap();
        assert_eq!(deleted.status, SessionStatus::Closed);
        assert!(store.get_session(created.id).await.is_none());

        let commands = cdp.recorded_commands().await;
        assert!(
            commands
                .iter()
                .any(|command| command.method == "Page.captureScreenshot")
        );
        assert!(
            commands
                .iter()
                .any(|command| command.method == "Browser.close")
        );

        cdp.stop().await;
    }

    #[tokio::test]
    async fn download_listing_and_fetch_reject_path_traversal() {
        let (_tmp, cdp, store) = mock_store(true, Duration::from_secs(60)).await;
        let created = store
            .create_session(CreateSessionRequest {
                profile_id: None,
                headless: Some(true),
                viewport: None,
                persist_profile: Some(true),
                launch_timeout_secs: None,
                persona: None,
                ..Default::default()
            })
            .await
            .unwrap();

        let downloads_dir = store.downloads_dir(created.id).await.unwrap();
        fs::write(downloads_dir.join("report.txt"), b"hello").unwrap();

        let downloads = store.list_downloads(created.id).await.unwrap();
        assert_eq!(downloads.downloads.len(), 1);
        assert_eq!(downloads.downloads[0].name, "report.txt");
        assert_eq!(downloads.downloads[0].size_bytes, 5);

        let (name, bytes) = store.read_download(created.id, "report.txt").await.unwrap();
        assert_eq!(name, "report.txt");
        assert_eq!(bytes, b"hello");

        let err = store
            .read_download(created.id, "../secret.txt")
            .await
            .unwrap_err();
        assert!(err.to_string().contains("invalid download name"));

        cdp.stop().await;
    }

    #[tokio::test]
    async fn cleanup_artifacts_supports_dry_run_and_live_deletion() {
        let (_tmp, cdp, store) = mock_store(true, Duration::from_secs(60)).await;

        let closed = store
            .create_session(CreateSessionRequest {
                profile_id: None,
                headless: Some(true),
                viewport: None,
                persist_profile: Some(true),
                launch_timeout_secs: None,
                persona: None,
                ..Default::default()
            })
            .await
            .unwrap();
        let closed_dir = store.session_dir(closed.id);
        store.delete_session(closed.id).await.unwrap();

        let active = store
            .create_session(CreateSessionRequest {
                profile_id: None,
                headless: Some(true),
                viewport: None,
                persist_profile: Some(true),
                launch_timeout_secs: None,
                persona: None,
                ..Default::default()
            })
            .await
            .unwrap();
        let active_dir = store.session_dir(active.id);

        let dry_run = store
            .cleanup_artifacts(Some(Duration::ZERO), true)
            .await
            .unwrap();
        assert_eq!(dry_run.retention_secs, 0);
        assert!(
            dry_run
                .candidates
                .iter()
                .any(|candidate| candidate.session_id == closed.id.to_string())
        );
        assert!(closed_dir.is_dir());

        let live = store
            .cleanup_artifacts(Some(Duration::ZERO), false)
            .await
            .unwrap();
        assert!(live.deleted_session_ids.contains(&closed.id.to_string()));
        assert!(!closed_dir.exists());
        assert!(active_dir.exists());

        cdp.stop().await;
    }

    #[tokio::test]
    async fn persistent_profiles_require_pause_before_takeover_tokens_work() {
        let (_tmp, cdp, store) = mock_store(true, Duration::from_secs(60)).await;
        let first = store.create_session(persistent_req("p1")).await.unwrap();
        let second = store.create_session(persistent_req("p1")).await;
        assert!(second.is_err());

        let immediate = store
            .wait_session(first.id, Duration::from_millis(1))
            .await
            .unwrap();
        assert!(!immediate.timed_out);
        assert_eq!(immediate.session.status, SessionStatus::Running);
        assert!(first.takeover_url.is_none());
        {
            let sessions = store.sessions.lock().await;
            let managed = sessions.get(&first.id).unwrap();
            assert!(managed.takeover_token.is_empty());
        }
        assert!(
            !store
                .validate_takeover_token(first.id, "pre-pause-token")
                .await
        );

        let paused = store
            .pause_for_human(first.id, Some("oauth password step".into()))
            .await
            .unwrap();
        assert_eq!(
            paused.pause_reason.as_deref(),
            Some(crate::security::REDACTED)
        );
        let new_token = token_from_url(paused.takeover_url.as_ref().unwrap()).to_string();
        assert!(store.validate_takeover_token(first.id, &new_token).await);

        let releaser = {
            let store = store.clone();
            tokio::spawn(async move {
                sleep(Duration::from_millis(25)).await;
                store.release(first.id).await.unwrap();
            })
        };
        let resumed = store
            .wait_session(first.id, Duration::from_millis(500))
            .await
            .unwrap();
        assert!(!resumed.timed_out);
        assert_eq!(resumed.session.status, SessionStatus::Running);
        releaser.await.unwrap();

        store
            .pause_for_human(first.id, Some("still waiting".into()))
            .await
            .unwrap();
        let timed_out = store
            .wait_session(first.id, Duration::from_millis(10))
            .await
            .unwrap();
        assert!(timed_out.timed_out);
        assert_eq!(timed_out.session.status, SessionStatus::PausedForHuman);

        let released = store.release(first.id).await.unwrap();
        assert_eq!(released.status, SessionStatus::Running);
        assert!(released.takeover_url.is_none());
        assert!(!store.validate_takeover_token(first.id, &new_token).await);
        {
            let sessions = store.sessions.lock().await;
            let managed = sessions.get(&first.id).unwrap();
            assert!(managed.takeover_token.is_empty());
        }

        store.delete_session(first.id).await.unwrap();
        assert!(store.create_session(persistent_req("p1")).await.is_ok());
        cdp.stop().await;
    }

    #[tokio::test]
    async fn live_links_require_pause_support_modes_revoke_and_clear_on_release() {
        let (tmp, cdp, store) = mock_store(true, Duration::from_secs(60)).await;
        let created = store.create_session(persistent_req("p1")).await.unwrap();
        assert!(
            store
                .create_live_link(created.id, LiveLinkMode::ReadOnly)
                .await
                .unwrap_err()
                .to_string()
                .contains("paused human takeover")
        );

        store
            .pause_for_human(created.id, Some("manual checkpoint".into()))
            .await
            .unwrap();
        let read_only = store
            .create_live_link(created.id, LiveLinkMode::ReadOnly)
            .await
            .unwrap();
        let interactive = store
            .create_live_link(created.id, LiveLinkMode::Interactive)
            .await
            .unwrap();
        assert_eq!(read_only.mode, LiveLinkMode::ReadOnly);
        assert_eq!(interactive.mode, LiveLinkMode::Interactive);
        assert_ne!(read_only.id, interactive.id);

        let read_only_token = token_from_url(&read_only.url).to_string();
        let interactive_token = token_from_url(&interactive.url).to_string();
        assert_eq!(
            store
                .takeover_access_mode(created.id, &read_only_token)
                .await,
            Some(LiveLinkMode::ReadOnly)
        );
        assert_eq!(
            store
                .takeover_access_mode(created.id, &interactive_token)
                .await,
            Some(LiveLinkMode::Interactive)
        );

        let summaries = store.live_link_summaries(created.id).await.unwrap();
        assert_eq!(summaries.len(), 2);
        assert_eq!(summaries[0].id, interactive.id);
        assert!(!summaries.iter().any(|link| link.revoked || link.expired));

        let revoked = store
            .revoke_live_link(created.id, read_only.id)
            .await
            .unwrap();
        assert!(revoked.revoked);
        assert!(
            store
                .takeover_access_mode(created.id, &read_only_token)
                .await
                .is_none()
        );
        assert_eq!(
            store
                .takeover_access_mode(created.id, &interactive_token)
                .await,
            Some(LiveLinkMode::Interactive)
        );

        let events = fs::read_to_string(
            tmp.path()
                .join("sessions")
                .join(created.id.to_string())
                .join("artifacts/events.jsonl"),
        )
        .unwrap();
        assert!(events.contains("live_link_created"));
        assert!(events.contains("live_link_revoked"));
        assert!(!events.contains(&read_only_token));
        assert!(!events.contains(&interactive_token));

        store.release(created.id).await.unwrap();
        assert!(
            store
                .live_link_summaries(created.id)
                .await
                .unwrap()
                .is_empty()
        );
        assert!(
            store
                .takeover_access_mode(created.id, &interactive_token)
                .await
                .is_none()
        );
        cdp.stop().await;
    }

    #[tokio::test]
    async fn store_handles_profile_crud_errors_missing_sessions_and_zero_ttl_tokens() {
        let (_tmp, cdp, store) = mock_store(true, Duration::ZERO).await;
        let generated = store.create_profile(Some("bad path".into())).await.unwrap();
        assert!(generated.id.starts_with("profile-"));
        let named = store
            .create_profile(Some("b-profile".into()))
            .await
            .unwrap();
        fs::write(
            PathBuf::from(&named.path).with_extension("txt"),
            b"ignore me",
        )
        .unwrap();

        let mut profiles = store.list_profiles().await.unwrap();
        profiles.sort_by(|a, b| a.id.cmp(&b.id));
        assert!(profiles.iter().any(|profile| profile.id == named.id));
        assert!(profiles.iter().all(|profile| !profile.id.ends_with(".txt")));

        assert!(store.delete_profile("bad/path").await.is_err());
        let session = store
            .create_session(persistent_req(&named.id))
            .await
            .unwrap();
        assert!(store.delete_profile(&named.id).await.is_err());
        assert!(
            !store
                .validate_takeover_token(Uuid::new_v4(), "missing")
                .await
        );
        let paused = store
            .pause_for_human(session.id, Some("reason".into()))
            .await
            .unwrap();
        let expired = token_from_url(paused.takeover_url.as_ref().unwrap()).to_string();
        assert!(!store.validate_takeover_token(session.id, &expired).await);

        let missing = Uuid::new_v4();
        assert!(store.get_session(missing).await.is_none());
        assert!(
            store
                .delete_session(missing)
                .await
                .unwrap_err()
                .to_string()
                .contains("session not found")
        );
        assert!(
            store
                .pause_for_human(missing, None)
                .await
                .unwrap_err()
                .to_string()
                .contains("session not found")
        );
        assert!(
            store
                .release(missing)
                .await
                .unwrap_err()
                .to_string()
                .contains("session not found")
        );
        assert!(
            store
                .wait_session(missing, Duration::from_millis(1))
                .await
                .unwrap_err()
                .to_string()
                .contains("session not found")
        );
        assert!(
            store
                .screenshot(missing)
                .await
                .unwrap_err()
                .to_string()
                .contains("session not found")
        );
        assert!(
            store
                .artifacts(missing)
                .await
                .unwrap_err()
                .to_string()
                .contains("session not found")
        );
        assert!(
            store
                .input_click(missing, 0.0, 0.0)
                .await
                .unwrap_err()
                .to_string()
                .contains("session not found")
        );
        assert!(
            store
                .input_type(missing, "hello")
                .await
                .unwrap_err()
                .to_string()
                .contains("session not found")
        );
        assert!(
            store
                .input_key(missing, "tab")
                .await
                .unwrap_err()
                .to_string()
                .contains("session not found")
        );
        assert!(
            store
                .input_scroll(missing, 0.0, 1.0)
                .await
                .unwrap_err()
                .to_string()
                .contains("session not found")
        );

        store.delete_session(session.id).await.unwrap();
        store.delete_profile(&named.id).await.unwrap();
        assert!(!PathBuf::from(named.path).exists());
        cdp.stop().await;
    }

    #[tokio::test]
    async fn create_session_generates_profile_id_when_request_omits_it() {
        let (_tmp, cdp, store) = mock_store(true, Duration::from_secs(60)).await;
        let created = store
            .create_session(CreateSessionRequest {
                profile_id: None,
                headless: Some(true),
                viewport: None,
                persist_profile: Some(false),
                launch_timeout_secs: None,
                persona: None,
                ..Default::default()
            })
            .await
            .unwrap();

        assert!(created.profile_id.starts_with("profile-"));
        assert_eq!(created.status, SessionStatus::Running);
        assert!(!created.persist_profile);
        cdp.stop().await;
    }

    #[tokio::test]
    async fn screenshot_reports_artifact_write_failures_with_context() {
        let (_tmp, cdp, store) = mock_store(true, Duration::from_secs(60)).await;
        let created = store.create_session(persistent_req("p1")).await.unwrap();
        let bad_root = store.config.data_dir.join("not-a-dir");
        fs::write(&bad_root, b"blocking file").unwrap();
        {
            let mut sessions = store.sessions.lock().await;
            sessions.get_mut(&created.id).unwrap().artifacts_dir = bad_root;
        }

        let err = store.screenshot(created.id).await.unwrap_err();

        assert!(err.to_string().contains("write"));
        assert!(err.to_string().contains("screenshot-"));
        cdp.stop().await;
    }

    #[tokio::test]
    async fn delete_profile_is_a_noop_when_directory_is_missing() {
        let tmp = tempfile::tempdir().unwrap();
        let store = AppStore::new(
            test_config(tmp.path().to_path_buf(), None),
            Arc::new(NeverLaunchBackend),
        )
        .await
        .unwrap();

        store.delete_profile("ghost-profile").await.unwrap();
    }

    #[tokio::test]
    async fn artifacts_skip_nested_directories_and_missing_artifacts_root() {
        let (_tmp, cdp, store) = mock_store(true, Duration::from_secs(60)).await;
        let created = store.create_session(persistent_req("p1")).await.unwrap();
        let artifacts_dir = store
            .config
            .data_dir
            .join("sessions")
            .join(created.id.to_string())
            .join("artifacts");

        fs::create_dir_all(artifacts_dir.join("nested")).unwrap();
        let listed = store.artifacts(created.id).await.unwrap();
        assert!(listed.artifacts.iter().all(|artifact| {
            !artifact.path.ends_with("/nested") && !artifact.path.contains("/nested/")
        }));
        assert!(
            listed
                .artifacts
                .iter()
                .any(|artifact| artifact.kind == "event_log")
        );

        fs::remove_dir_all(&artifacts_dir).unwrap();
        let missing_root = store.artifacts(created.id).await.unwrap();
        assert!(missing_root.artifacts.is_empty());
        assert!(missing_root.downloads_dir.ends_with("/downloads"));

        fs::create_dir_all(&artifacts_dir).unwrap();
        store.delete_session(created.id).await.unwrap();
        cdp.stop().await;
    }

    #[tokio::test]
    async fn credential_fill_uses_mock_provider_and_privacy_guard_blocks_artifacts() {
        let tmp = tempfile::tempdir().unwrap();
        let cdp = MockCdpServer::spawn().await;
        let policy_path = tmp.path().join("credential-policy.json");
        fs::write(
            &policy_path,
            serde_json::to_vec_pretty(&json!({
                "aliases": {
                    "demo-login": {
                        "allowed_origins": ["https://example.test"],
                        "provider_refs": {
                            "username": test_provider_ref("username"),
                            "password": test_provider_ref("password")
                        },
                        "allowed_fields": ["username", "password"]
                    }
                }
            }))
            .unwrap(),
        )
        .unwrap();
        let mut config = test_config(tmp.path().to_path_buf(), None);
        config.credential_provider = CredentialBrokerMode::Mock;
        config.credential_policy_path = Some(policy_path);
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
        let created = store.create_session(persistent_req("p1")).await.unwrap();
        cdp.clear_recorded_commands().await;
        cdp.enqueue_page_reply(WsReply::Success(json!({"result": {"value": {
            "observed_origin": "https://example.test",
            "username_present": true,
            "password_present": true
        }}})))
        .await;

        let requested = store
            .request_credential_fill(
                created.id,
                CredentialFillStartRequest {
                    alias: "demo-login".into(),
                    username_selector: Some("#user".into()),
                    password_selector: Some("#pass".into()),
                    purpose: Some("login password".into()),
                    expected_origin: Some("https://example.test".into()),
                },
            )
            .await
            .unwrap();
        assert_eq!(requested.status, CredentialFillStatus::RequiresUserApproval);
        assert!(!requested.privacy_guard_active);

        cdp.enqueue_page_reply(WsReply::Success(json!({"result": {"value": {
            "observed_origin": "https://example.test",
            "username_present": true,
            "password_present": true
        }}})))
        .await;
        for reply in [
            WsReply::Success(json!({"result": {"value": {
                "observed_origin": "https://example.test",
                "username_present": true,
                "password_present": true
            }}})),
            WsReply::Success(json!({"result": {"value": {"focused": true}}})),
            WsReply::Success(json!({"result": {}})),
            WsReply::Success(json!({"result": {"value": {"focused": true}}})),
            WsReply::Success(json!({"result": {}})),
        ] {
            cdp.enqueue_page_reply(reply).await;
        }
        let filled = store
            .approve_credential_fill(created.id, requested.request_id, None)
            .await
            .unwrap();
        assert_eq!(filled.status, CredentialFillStatus::Filled);
        assert!(filled.privacy_guard_active);
        assert!(
            store
                .screenshot(created.id)
                .await
                .unwrap_err()
                .to_string()
                .contains("credential privacy guard active")
        );
        assert!(
            store
                .artifacts(created.id)
                .await
                .unwrap_err()
                .to_string()
                .contains("credential privacy guard active")
        );

        let cleared = store
            .clear_credential_privacy_guard(created.id)
            .await
            .unwrap();
        assert!(!cleared.privacy_guard_active);
        let png = store.screenshot(created.id).await.unwrap();
        assert_eq!(png, b"png");

        let events = fs::read_to_string(
            store
                .config
                .data_dir
                .join("sessions")
                .join(created.id.to_string())
                .join("artifacts")
                .join("events.jsonl"),
        )
        .unwrap();
        assert!(events.contains("credential_fill_approval_required"));
        assert!(events.contains("credential_fill_filled"));
        assert!(events.contains("credential_privacy_guard_active"));
        assert!(!events.contains("#user"));
        assert!(!events.contains("#pass"));
        assert!(!events.contains("mock-username"));
        assert!(!events.contains("mock-password"));
        let provider_ref_prefix = test_provider_ref_prefix();
        assert!(!events.contains(&provider_ref_prefix));
        cdp.stop().await;
    }

    #[tokio::test]
    async fn credential_fill_origin_mismatch_never_reaches_provider_or_browser_fill() {
        let tmp = tempfile::tempdir().unwrap();
        let cdp = MockCdpServer::spawn().await;
        let policy_path = tmp.path().join("credential-policy.json");
        fs::write(
            &policy_path,
            serde_json::to_vec_pretty(&json!({
                "aliases": {
                    "demo-login": {
                        "allowed_origins": ["https://example.test"],
                        "provider_refs": {
                            "username": test_provider_ref("username"),
                            "password": test_provider_ref("password")
                        },
                        "allowed_fields": ["username", "password"]
                    }
                }
            }))
            .unwrap(),
        )
        .unwrap();
        let mut config = test_config(tmp.path().to_path_buf(), None);
        config.credential_provider = CredentialBrokerMode::Mock;
        config.credential_policy_path = Some(policy_path);
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
        let created = store.create_session(persistent_req("p1")).await.unwrap();
        cdp.clear_recorded_commands().await;
        cdp.enqueue_page_reply(WsReply::Success(json!({"result": {"value": {
            "observed_origin": "https://evil.test",
            "username_present": true,
            "password_present": true
        }}})))
        .await;

        let response = store
            .request_credential_fill(
                created.id,
                CredentialFillStartRequest {
                    alias: "demo-login".into(),
                    username_selector: Some("#user".into()),
                    password_selector: Some("#pass".into()),
                    purpose: None,
                    expected_origin: Some("https://example.test".into()),
                },
            )
            .await
            .unwrap();
        assert_eq!(response.status, CredentialFillStatus::OriginMismatch);
        let approved = store
            .approve_credential_fill(created.id, response.request_id, None)
            .await
            .unwrap();
        assert_eq!(approved.status, CredentialFillStatus::OriginMismatch);
        assert!(!approved.privacy_guard_active);
        let commands = cdp.recorded_commands().await;
        assert_eq!(
            commands
                .iter()
                .filter(|command| command.method == "Runtime.evaluate")
                .count(),
            1
        );
        cdp.stop().await;
    }

    #[tokio::test]
    async fn approve_credential_fill_rechecks_current_origin_before_provider_read() {
        let (_tmp, cdp, store, provider_marker) = onepassword_mock_store_with_marker().await;
        let created = store.create_session(persistent_req("p1")).await.unwrap();
        cdp.clear_recorded_commands().await;
        cdp.enqueue_page_reply(WsReply::Success(json!({"result": {"value": {
            "observed_origin": "https://example.test",
            "username_present": true,
            "password_present": true
        }}})))
        .await;

        let requested = store
            .request_credential_fill(
                created.id,
                CredentialFillStartRequest {
                    alias: "demo-login".into(),
                    username_selector: Some("#user".into()),
                    password_selector: Some("#pass".into()),
                    purpose: Some("login password".into()),
                    expected_origin: Some("https://example.test".into()),
                },
            )
            .await
            .unwrap();
        assert_eq!(requested.status, CredentialFillStatus::RequiresUserApproval);

        cdp.enqueue_page_reply(WsReply::Success(json!({"result": {"value": {
            "observed_origin": "https://evil.test",
            "username_present": true,
            "password_present": true
        }}})))
        .await;
        let approved = store
            .approve_credential_fill(created.id, requested.request_id, None)
            .await
            .unwrap();

        assert_eq!(approved.status, CredentialFillStatus::OriginMismatch);
        assert!(!approved.privacy_guard_active);
        assert!(
            !provider_marker.exists(),
            "provider must not be read after navigation"
        );
        assert_eq!(store.screenshot(created.id).await.unwrap(), b"png");
        let commands = cdp.recorded_commands().await;
        assert_eq!(
            commands
                .iter()
                .filter(|command| command.method == "Runtime.evaluate")
                .count(),
            2
        );
        assert!(!commands.iter().any(|command| {
            command.params["expression"]
                .as_str()
                .is_some_and(|expression| expression.contains("username_filled"))
        }));
        cdp.stop().await;
    }

    #[tokio::test]
    async fn approve_credential_fill_rechecks_current_fields_before_provider_read() {
        let (_tmp, cdp, store, provider_marker) = onepassword_mock_store_with_marker().await;
        let created = store.create_session(persistent_req("p1")).await.unwrap();
        cdp.clear_recorded_commands().await;
        cdp.enqueue_page_reply(WsReply::Success(json!({"result": {"value": {
            "observed_origin": "https://example.test",
            "username_present": true,
            "password_present": true
        }}})))
        .await;

        let requested = store
            .request_credential_fill(
                created.id,
                CredentialFillStartRequest {
                    alias: "demo-login".into(),
                    username_selector: Some("input[".into()),
                    password_selector: Some("#pass".into()),
                    purpose: Some("login password".into()),
                    expected_origin: Some("https://example.test".into()),
                },
            )
            .await
            .unwrap();
        assert_eq!(requested.status, CredentialFillStatus::RequiresUserApproval);

        cdp.enqueue_page_reply(WsReply::Success(json!({"result": {"value": {
            "observed_origin": "https://example.test",
            "username_present": false,
            "password_present": true
        }}})))
        .await;
        let approved = store
            .approve_credential_fill(created.id, requested.request_id, None)
            .await
            .unwrap();

        assert_eq!(approved.status, CredentialFillStatus::NoMatch);
        assert!(!approved.privacy_guard_active);
        assert!(
            !provider_marker.exists(),
            "provider must not be read when fields disappeared"
        );
        assert_eq!(store.screenshot(created.id).await.unwrap(), b"png");
        let commands = cdp.recorded_commands().await;
        assert_eq!(
            commands
                .iter()
                .filter(|command| command.method == "Runtime.evaluate")
                .count(),
            2
        );
        assert!(!commands.iter().any(|command| {
            command.params["expression"]
                .as_str()
                .is_some_and(|expression| expression.contains("username_filled"))
        }));
        cdp.stop().await;
    }

    #[tokio::test]
    async fn captcha_solver_default_config_keeps_manual_policy_without_status() {
        let (_tmp, cdp, store) = mock_store(true, Duration::from_secs(60)).await;
        let created = store
            .create_session(persistent_req("solver-defaults"))
            .await
            .unwrap();

        assert_eq!(created.captcha_policy, CaptchaPolicy::HumanOnly);
        assert!(created.captcha_solver_status.is_none());

        cdp.stop().await;
    }

    #[tokio::test]
    async fn captcha_scan_reports_local_policy_decisions_without_provider_calls() {
        let (_tmp, cdp, store) = mock_store(true, Duration::from_secs(60)).await;
        for (profile_id, policy, decision) in [
            (
                "scan-human-only",
                CaptchaPolicy::HumanOnly,
                "human_only_waiting_for_detection",
            ),
            (
                "scan-observe-only",
                CaptchaPolicy::ObserveOnly,
                "observe_only_waiting_for_detection",
            ),
            ("scan-disabled", CaptchaPolicy::Disabled, "policy_disabled"),
        ] {
            let mut request = persistent_req(profile_id);
            request.captcha_policy = Some(policy);
            let created = store.create_session(request).await.unwrap();
            let scan = store
                .scan_captcha(created.id, CaptchaScanRequest { dry_run: false })
                .await
                .unwrap();
            assert!(!scan.detected);
            assert_eq!(scan.captcha_policy, policy);
            assert_eq!(scan.captcha_status, CaptchaStatus::None);
            assert_eq!(scan.policy_decision, decision);
            assert!(!scan.provider_call_performed);
            assert!(!scan.dry_run);
        }

        let checkpoint = store
            .create_session(persistent_req("scan-local-checkpoint"))
            .await
            .unwrap();
        store
            .report_captcha(
                checkpoint.id,
                CaptchaReportState::Suspected,
                Some("turnstile".into()),
                Some("local checkpoint text with password=raw-token".into()),
            )
            .await
            .unwrap();
        let detected = store
            .scan_captcha(checkpoint.id, CaptchaScanRequest { dry_run: true })
            .await
            .unwrap();
        assert!(detected.detected);
        assert_eq!(detected.captcha_status, CaptchaStatus::Suspected);
        assert_eq!(detected.challenge_type.as_deref(), Some("turnstile"));
        assert_eq!(detected.policy_decision, "local_checkpoint_detected");
        assert!(!detected.provider_call_performed);
        assert!(detected.dry_run);
        assert_eq!(detected.solver.status, CaptchaSolverState::NotRequested);

        store.shutdown_all().await.unwrap();
        cdp.stop().await;
    }

    #[tokio::test]
    async fn captcha_solver_disabled_auto_policy_fails_closed_to_human() {
        let tmp = tempfile::tempdir().unwrap();
        let cdp = MockCdpServer::spawn().await;
        let mut config = test_config(tmp.path().to_path_buf(), None);
        config.default_captcha_policy = CaptchaPolicy::AutoSolve;
        config.captcha_solver_enabled = false;
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
        let created = store
            .create_session(persistent_req("solver-disabled"))
            .await
            .unwrap();

        let updated_result = store
            .request_captcha_solve(
                created.id,
                Some("turnstile".into()),
                Some("sitekey raw-token should stay redacted".into()),
                None,
                None,
            )
            .await
            .unwrap();
        assert!(!updated_result.provider_call_performed);
        let updated = updated_result.info;

        assert_eq!(updated.captcha_policy, CaptchaPolicy::AutoSolve);
        assert_eq!(updated.status, SessionStatus::PausedForHuman);
        assert_eq!(updated.captcha_status, CaptchaStatus::HumanRequired);
        let solver_status = updated.captcha_solver_status.as_ref().unwrap();
        assert_eq!(solver_status.status, CaptchaSolverState::Disabled);
        assert!(!solver_status.enabled);
        assert!(solver_status.human_takeover_required);
        assert_eq!(
            solver_status.normalized_error.as_deref(),
            Some("solver_disabled")
        );
        assert_eq!(
            solver_status.redacted_message.as_deref(),
            Some("[REDACTED]")
        );
        assert!(updated.takeover_url.is_some());

        let artifacts_dir = store
            .config
            .data_dir
            .join("sessions")
            .join(created.id.to_string())
            .join("artifacts");
        let events = fs::read_to_string(artifacts_dir.join("events.jsonl")).unwrap();
        assert!(events.contains("captcha_solve_failed"));
        assert!(events.contains("captcha_human_required"));
        assert!(events.contains("solver_disabled"));
        assert!(!events.contains("raw-token"));
        assert!(events.contains("[REDACTED]"));

        cdp.stop().await;
    }

    #[tokio::test]
    async fn captcha_solver_no_key_fails_closed_and_preserves_human_takeover() {
        let tmp = tempfile::tempdir().unwrap();
        let cdp = MockCdpServer::spawn().await;
        let mut config = test_config(tmp.path().to_path_buf(), None);
        config.default_captcha_policy = CaptchaPolicy::AutoSolve;
        config.captcha_solver_enabled = true;
        config.captcha_solver_provider_key_available = false;
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
        let created = store
            .create_session(persistent_req("solver-no-key"))
            .await
            .unwrap();

        let first_result = store
            .request_captcha_solve(
                created.id,
                Some("turnstile".into()),
                Some("provider_task_id task-123 and answer raw-token".into()),
                None,
                None,
            )
            .await
            .unwrap();
        assert!(!first_result.provider_call_performed);
        let first = first_result.info;
        let takeover_url = first.takeover_url.clone().unwrap();
        let token = token_from_url(&takeover_url).to_string();

        assert_eq!(first.status, SessionStatus::PausedForHuman);
        assert_eq!(first.captcha_status, CaptchaStatus::HumanRequired);
        let solver_status = first.captcha_solver_status.as_ref().unwrap();
        assert_eq!(solver_status.status, CaptchaSolverState::NoProviderKey);
        assert!(solver_status.enabled);
        assert_eq!(solver_status.policy, CaptchaPolicy::AutoSolve);
        assert_eq!(solver_status.challenge_type.as_deref(), Some("turnstile"));
        assert_eq!(solver_status.provider_id, None);
        assert_eq!(
            solver_status.normalized_error.as_deref(),
            Some("no_provider_key")
        );
        assert!(solver_status.human_takeover_required);
        assert!(store.validate_takeover_token(created.id, &token).await);

        let second = store
            .request_captcha_solve(
                created.id,
                Some("turnstile".into()),
                Some("another provider_task_id task-456".into()),
                None,
                None,
            )
            .await
            .unwrap();
        assert_eq!(
            second.info.takeover_url.as_deref(),
            Some(takeover_url.as_str())
        );
        assert!(store.validate_takeover_token(created.id, &token).await);

        let resolved = store
            .resolve_captcha(
                created.id,
                CaptchaResolveOutcome::Resolved,
                Some("operator note with otp 123456".into()),
            )
            .await
            .unwrap();
        assert_eq!(resolved.status, SessionStatus::PausedForHuman);
        assert_eq!(resolved.captcha_status, CaptchaStatus::Resolved);
        assert_eq!(
            resolved.takeover_url.as_deref(),
            Some(takeover_url.as_str())
        );

        let released = store.release(created.id).await.unwrap();
        assert_eq!(released.status, SessionStatus::Running);
        assert!(released.takeover_url.is_none());
        assert!(!store.validate_takeover_token(created.id, &token).await);

        let events = fs::read_to_string(
            store
                .config
                .data_dir
                .join("sessions")
                .join(created.id.to_string())
                .join("artifacts")
                .join("events.jsonl"),
        )
        .unwrap();
        assert!(events.contains("captcha_solve_failed"));
        assert!(events.contains("no_provider_key"));
        assert!(!events.contains(&token));
        assert!(!events.contains("task-123"));
        assert!(!events.contains("task-456"));
        assert!(!events.contains("123456"));
        assert!(!events.contains("raw-token"));

        cdp.stop().await;
    }

    #[tokio::test]
    async fn captcha_solver_success_reports_provider_call_performed_true() {
        let tmp = tempfile::tempdir().unwrap();
        let cdp = MockCdpServer::spawn().await;
        let mut config = test_config(tmp.path().to_path_buf(), None);
        config.default_captcha_policy = CaptchaPolicy::AutoSolve;
        config.captcha_solver_enabled = true;
        config.captcha_solver_provider_key_available = true;
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
        let created = store
            .create_session(persistent_req("solver-success"))
            .await
            .unwrap();

        // provider success path
        store.set_captcha_solver_test_outcome(Ok(())).await;
        let result = store
            .request_captcha_solve(
                created.id,
                Some("turnstile".into()),
                Some("reason".into()),
                Some("site-key".into()),
                Some("https://example.test".into()),
            )
            .await
            .unwrap();
        assert!(result.provider_call_performed);
        assert_eq!(result.info.captcha_status, CaptchaStatus::Resolved);
        let solver = result.info.captcha_solver_status.as_ref().unwrap();
        assert_eq!(solver.status, CaptchaSolverState::Resolved);

        // provider error path — new session to avoid re-acquire complications
        let created2 = store
            .create_session(persistent_req("solver-error"))
            .await
            .unwrap();
        store
            .set_captcha_solver_test_outcome(Err("test provider error".into()))
            .await;
        let result2 = store
            .request_captcha_solve(
                created2.id,
                Some("turnstile".into()),
                Some("reason".into()),
                Some("site-key".into()),
                Some("https://example.test".into()),
            )
            .await
            .unwrap();
        assert!(result2.provider_call_performed);
        assert_eq!(result2.info.captcha_status, CaptchaStatus::HumanRequired);
        let solver2 = result2.info.captcha_solver_status.as_ref().unwrap();
        assert_eq!(solver2.status, CaptchaSolverState::Failed);
        assert_eq!(
            solver2.normalized_error.as_deref(),
            Some("provider_solve_error")
        );

        // redaction: no raw provider task_id, api key, or site key leaked
        let events = fs::read_to_string(
            store
                .config
                .data_dir
                .join("sessions")
                .join(created2.id.to_string())
                .join("artifacts")
                .join("events.jsonl"),
        )
        .unwrap();
        assert!(!events.contains("test-captcha-provider-key"));
        assert!(!events.contains("site-key"));
        assert!(!events.contains("test provider error"));
        assert!(events.contains("[REDACTED]"));

        cdp.stop().await;
    }

    #[tokio::test]
    async fn captcha_human_required_pauses_session_and_redacts_persisted_events() {
        let (_tmp, cdp, store) = mock_store(true, Duration::from_secs(60)).await;
        let created = store.create_session(persistent_req("p1")).await.unwrap();

        let updated = store
            .report_captcha(
                created.id,
                CaptchaReportState::HumanRequired,
                Some("hcaptcha".into()),
                Some("checkpoint includes raw password token and card text".into()),
            )
            .await
            .unwrap();

        assert_eq!(updated.status, SessionStatus::PausedForHuman);
        assert_eq!(updated.captcha_status, CaptchaStatus::HumanRequired);
        assert_eq!(updated.captcha_challenge_type.as_deref(), Some("hcaptcha"));
        let takeover_url = updated.takeover_url.as_ref().unwrap();
        let token = token_from_url(takeover_url).to_string();
        assert!(store.validate_takeover_token(created.id, &token).await);

        let resolved = store
            .resolve_captcha(
                created.id,
                CaptchaResolveOutcome::Resolved,
                Some("operator secret code 123456".into()),
            )
            .await
            .unwrap();
        assert_eq!(resolved.status, SessionStatus::PausedForHuman);
        assert_eq!(resolved.captcha_status, CaptchaStatus::Resolved);
        assert_eq!(resolved.pause_reason, updated.pause_reason);
        assert_eq!(
            resolved.takeover_url.as_deref(),
            Some(takeover_url.as_str())
        );
        assert!(store.validate_takeover_token(created.id, &token).await);

        let timed_out = store
            .wait_session(created.id, Duration::from_millis(10))
            .await
            .unwrap();
        assert!(timed_out.timed_out);
        assert_eq!(timed_out.session.status, SessionStatus::PausedForHuman);
        assert_eq!(timed_out.session.captcha_status, CaptchaStatus::Resolved);

        let artifacts_dir = store
            .config
            .data_dir
            .join("sessions")
            .join(created.id.to_string())
            .join("artifacts");
        let events = fs::read_to_string(artifacts_dir.join("events.jsonl")).unwrap();
        assert!(events.contains("captcha_human_required"));
        assert!(events.contains("captcha_resolved"));
        assert!(!events.contains(&token));
        assert!(!events.contains("123456"));
        assert!(!events.contains("raw password"));
        assert!(!events.contains("card text"));
        assert!(events.contains("[REDACTED]"));

        let persisted = fs::read_to_string(
            store
                .config
                .data_dir
                .join("sessions")
                .join(created.id.to_string())
                .join("session.json"),
        )
        .unwrap();
        assert!(!persisted.contains(&token));
        assert!(persisted.contains("[REDACTED]"));

        let release_waiter = {
            let store = store.clone();
            tokio::spawn(
                async move { store.wait_session(created.id, Duration::from_secs(1)).await },
            )
        };
        tokio::task::yield_now().await;
        let released = store.release(created.id).await.unwrap();
        assert_eq!(released.status, SessionStatus::Running);
        assert_eq!(released.captcha_status, CaptchaStatus::Resolved);
        assert!(released.pause_reason.is_none());
        assert!(released.takeover_url.is_none());
        assert!(!store.validate_takeover_token(created.id, &token).await);
        let waited = release_waiter.await.unwrap().unwrap();
        assert!(!waited.timed_out);
        assert_eq!(waited.session.status, SessionStatus::Running);
        assert_eq!(waited.session.captcha_status, CaptchaStatus::Resolved);
        cdp.stop().await;
    }

    #[tokio::test]
    async fn captcha_resolution_requires_checkpoint_and_records_manual_outcome() {
        let (_tmp, cdp, store) = mock_store(true, Duration::from_secs(60)).await;
        let created = store.create_session(persistent_req("p1")).await.unwrap();

        assert!(
            store
                .resolve_captcha(
                    created.id,
                    CaptchaResolveOutcome::Resolved,
                    Some("manual code 123456".into()),
                )
                .await
                .is_err()
        );

        let reported = store
            .report_captcha(
                created.id,
                CaptchaReportState::Suspected,
                Some("turnstile".into()),
                Some("manual review".into()),
            )
            .await
            .unwrap();
        assert_eq!(reported.captcha_status, CaptchaStatus::Suspected);

        let resolved = store
            .resolve_captcha(
                created.id,
                CaptchaResolveOutcome::Dismissed,
                Some("operator dismissed otp 123456".into()),
            )
            .await
            .unwrap();
        assert_eq!(resolved.captcha_status, CaptchaStatus::Dismissed);

        let artifacts_dir = store
            .config
            .data_dir
            .join("sessions")
            .join(created.id.to_string())
            .join("artifacts");
        let events = fs::read_to_string(artifacts_dir.join("events.jsonl")).unwrap();
        assert!(events.contains("captcha_reported"));
        assert!(events.contains("captcha_resolved"));
        assert!(!events.contains("123456"));
        cdp.stop().await;
    }

    #[test]
    fn infer_kind_maps_file_extensions() {
        assert_eq!(infer_kind(Path::new("shot.png")), "screenshot");
        assert_eq!(infer_kind(Path::new("events.jsonl")), "event_log");
        assert_eq!(infer_kind(Path::new("misc.txt")), "file");
    }
}
