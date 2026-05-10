use std::{
    collections::HashMap,
    fs,
    io::Write,
    path::{Path, PathBuf},
    sync::Arc,
    time::Duration,
};

use anyhow::{Context, Result, bail};
use chrono::{DateTime, Utc};
use serde_json::json;
use tokio::sync::Mutex;
use uuid::Uuid;

use crate::{
    backend::{BrowserBackend, LaunchedBrowser, StartSessionOptions},
    cdp,
    config::RuntimeConfig,
    models::{
        ArtifactInfo, ArtifactsResponse, CreateSessionRequest, ProfileInfo, SessionInfo,
        SessionStatus,
    },
    security::{ensure_private_dir, random_token, redact_text, safe_child_path, sanitize_id},
};

pub struct AppStore {
    pub config: RuntimeConfig,
    backend: Arc<dyn BrowserBackend>,
    sessions: Mutex<HashMap<Uuid, ManagedSession>>,
    profile_locks: Mutex<HashMap<String, Uuid>>,
}

pub struct ManagedSession {
    pub info: SessionInfo,
    pub browser: LaunchedBrowser,
    pub user_data_dir: PathBuf,
    pub artifacts_dir: PathBuf,
    pub downloads_dir: PathBuf,
    pub takeover_token: String,
    pub takeover_expires_at: DateTime<Utc>,
}

impl AppStore {
    pub async fn new(config: RuntimeConfig, backend: Arc<dyn BrowserBackend>) -> Result<Self> {
        ensure_private_dir(&config.data_dir)?;
        ensure_private_dir(&config.data_dir.join("profiles"))?;
        ensure_private_dir(&config.data_dir.join("sessions"))?;
        ensure_private_dir(&config.data_dir.join("tmp"))?;
        Ok(Self {
            config,
            backend,
            sessions: Mutex::new(HashMap::new()),
            profile_locks: Mutex::new(HashMap::new()),
        })
    }

    pub async fn create_session(&self, request: CreateSessionRequest) -> Result<SessionInfo> {
        let id = Uuid::new_v4();
        let now = Utc::now();
        let profile_id = request
            .profile_id
            .as_deref()
            .and_then(sanitize_id)
            .unwrap_or_else(|| format!("profile-{}", Uuid::new_v4()));
        let persist_profile = request.persist_profile.unwrap_or(true);
        let headless = request.headless.unwrap_or(self.config.default_headless);
        let viewport = request.viewport.unwrap_or_default();
        let profile_dir = self.profile_dir(&profile_id)?;
        let session_dir = self.session_dir(id);
        let artifacts_dir = session_dir.join("artifacts");
        let downloads_dir = session_dir.join("downloads");
        ensure_private_dir(&session_dir)?;
        ensure_private_dir(&artifacts_dir)?;
        ensure_private_dir(&downloads_dir)?;

        let user_data_dir = if persist_profile {
            self.acquire_profile_lock(&profile_id, id).await?;
            ensure_private_dir(&profile_dir)?;
            profile_dir.clone()
        } else {
            let tmp = self
                .config
                .data_dir
                .join("tmp")
                .join(id.to_string())
                .join("user-data");
            ensure_private_dir(&tmp)?;
            if profile_dir.exists() {
                copy_profile_read_only_seed(&profile_dir, &tmp)?;
            }
            tmp
        };

        let launch_result = self
            .backend
            .launch(StartSessionOptions {
                id,
                user_data_dir: user_data_dir.clone(),
                downloads_dir: downloads_dir.clone(),
                headless,
                viewport: viewport.clone(),
                launch_timeout: Duration::from_secs(15),
            })
            .await;
        let browser = match launch_result {
            Ok(browser) => browser,
            Err(err) => {
                if persist_profile {
                    self.release_profile_lock(&profile_id, id).await;
                }
                return Err(err);
            }
        };
        let takeover_token = random_token(32);
        let takeover_expires_at = now + chrono::Duration::from_std(self.config.takeover_ttl)?;
        let takeover_url = self.takeover_url(id, &takeover_token);
        let info = SessionInfo {
            id,
            status: SessionStatus::Running,
            cdp_ws_url: Some(browser.cdp_ws_url.clone()),
            takeover_url: Some(takeover_url),
            profile_id: profile_id.clone(),
            persist_profile,
            headless,
            viewport,
            created_at: now,
            updated_at: now,
            pause_reason: None,
        };
        let session = ManagedSession {
            info: info.clone(),
            browser,
            user_data_dir,
            artifacts_dir,
            downloads_dir,
            takeover_token,
            takeover_expires_at,
        };
        self.append_event(
            &session,
            "session_created",
            json!({"profile_id": profile_id, "persist_profile": persist_profile}),
        )?;
        self.sessions.lock().await.insert(id, session);
        Ok(info)
    }

    pub async fn list_sessions(&self) -> Vec<SessionInfo> {
        self.sessions
            .lock()
            .await
            .values()
            .map(|session| session.info.clone())
            .collect()
    }

    pub async fn get_session(&self, id: Uuid) -> Option<SessionInfo> {
        self.sessions.lock().await.get(&id).map(|s| s.info.clone())
    }

    pub async fn delete_session(&self, id: Uuid) -> Result<SessionInfo> {
        let mut session = self
            .sessions
            .lock()
            .await
            .remove(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;
        session.info.status = SessionStatus::Closing;
        session.info.updated_at = Utc::now();
        self.append_event(&session, "session_closing", json!({}))?;
        self.backend.close(&mut session.browser).await?;
        if session.info.persist_profile {
            self.release_profile_lock(&session.info.profile_id, id)
                .await;
        }
        session.info.status = SessionStatus::Closed;
        session.info.updated_at = Utc::now();
        self.append_event(&session, "session_closed", json!({}))?;
        Ok(session.info)
    }

    pub async fn pause_for_human(&self, id: Uuid, reason: Option<String>) -> Result<SessionInfo> {
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
        self.append_event(
            session,
            "pause_for_human",
            json!({"reason": session.info.pause_reason}),
        )?;
        Ok(session.info.clone())
    }

    pub async fn release(&self, id: Uuid) -> Result<SessionInfo> {
        let mut sessions = self.sessions.lock().await;
        let session = sessions
            .get_mut(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;
        session.info.status = SessionStatus::Running;
        session.info.pause_reason = None;
        session.takeover_expires_at = Utc::now();
        session.info.takeover_url = None;
        session.info.updated_at = Utc::now();
        self.append_event(session, "released", json!({}))?;
        Ok(session.info.clone())
    }

    pub async fn validate_takeover_token(&self, id: Uuid, token: &str) -> bool {
        self.sessions
            .lock()
            .await
            .get(&id)
            .map(|session| {
                session.takeover_token == token && Utc::now() < session.takeover_expires_at
            })
            .unwrap_or(false)
    }

    pub async fn screenshot(&self, id: Uuid) -> Result<Vec<u8>> {
        let (http_base, artifacts_dir) = {
            let sessions = self.sessions.lock().await;
            let session = sessions
                .get(&id)
                .ok_or_else(|| anyhow::anyhow!("session not found"))?;
            (
                session.browser.http_base.clone(),
                session.artifacts_dir.clone(),
            )
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

    pub async fn input_scroll(&self, id: Uuid, delta_x: f64, delta_y: f64) -> Result<()> {
        let http_base = self.session_http_base(id).await?;
        cdp::scroll(&http_base, delta_x, delta_y).await
    }

    pub async fn artifacts(&self, id: Uuid) -> Result<ArtifactsResponse> {
        let sessions = self.sessions.lock().await;
        let session = sessions
            .get(&id)
            .ok_or_else(|| anyhow::anyhow!("session not found"))?;
        let mut artifacts = Vec::new();
        if session.artifacts_dir.exists() {
            for entry in fs::read_dir(&session.artifacts_dir)? {
                let entry = entry?;
                let metadata = entry.metadata()?;
                if metadata.is_file() {
                    artifacts.push(ArtifactInfo {
                        kind: infer_kind(&entry.path()),
                        path: entry.path().display().to_string(),
                        created_at: DateTime::<Utc>::from(metadata.modified()?),
                        size_bytes: metadata.len(),
                    });
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

    fn profile_dir(&self, profile_id: &str) -> Result<PathBuf> {
        safe_child_path(&self.config.data_dir.join("profiles"), profile_id)
    }

    fn session_dir(&self, id: Uuid) -> PathBuf {
        self.config.data_dir.join("sessions").join(id.to_string())
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
        self.sessions
            .lock()
            .await
            .get(&id)
            .map(|session| session.browser.http_base.clone())
            .ok_or_else(|| anyhow::anyhow!("session not found"))
    }

    fn append_event(
        &self,
        session: &ManagedSession,
        kind: &str,
        payload: serde_json::Value,
    ) -> Result<()> {
        let path = session.artifacts_dir.join("events.jsonl");
        let mut file = fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)?;
        let line = json!({"ts": Utc::now(), "kind": kind, "payload": payload});
        writeln!(file, "{}", serde_json::to_string(&line)?)?;
        Ok(())
    }
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
    use crate::config::RuntimeConfig;
    use std::{net::SocketAddr, sync::Arc};

    struct NeverLaunchBackend;
    struct FakeBackend;

    #[async_trait::async_trait]
    impl BrowserBackend for NeverLaunchBackend {
        async fn launch(&self, _options: StartSessionOptions) -> Result<LaunchedBrowser> {
            bail!("intentional test backend")
        }
        async fn close(&self, _launched: &mut LaunchedBrowser) -> Result<()> {
            Ok(())
        }
    }

    #[async_trait::async_trait]
    impl BrowserBackend for FakeBackend {
        async fn launch(&self, _options: StartSessionOptions) -> Result<LaunchedBrowser> {
            let process = tokio::process::Command::new("sleep")
                .arg("60")
                .spawn()
                .context("spawn fake browser process")?;
            Ok(LaunchedBrowser {
                process,
                port: 1,
                http_base: "http://127.0.0.1:1".to_string(),
                cdp_ws_url: "ws://127.0.0.1:1/devtools/browser/fake".to_string(),
            })
        }

        async fn close(&self, launched: &mut LaunchedBrowser) -> Result<()> {
            let _ = launched.process.start_kill();
            let _ = launched.process.wait().await;
            Ok(())
        }
    }

    fn test_config(data_dir: PathBuf) -> RuntimeConfig {
        RuntimeConfig {
            bind: "127.0.0.1:7788".parse::<SocketAddr>().unwrap(),
            data_dir,
            chrome_path: None,
            bearer_token: None,
            default_headless: true,
            takeover_ttl: Duration::from_secs(60),
        }
    }

    fn persistent_req(profile_id: &str) -> CreateSessionRequest {
        CreateSessionRequest {
            profile_id: Some(profile_id.into()),
            headless: Some(true),
            viewport: None,
            persist_profile: Some(true),
        }
    }

    fn token_from_url(url: &str) -> &str {
        url.split("token=").nth(1).unwrap()
    }

    #[tokio::test]
    async fn profile_lock_releases_when_launch_fails() {
        let tmp = tempfile::tempdir().unwrap();
        let store = AppStore::new(
            test_config(tmp.path().to_path_buf()),
            Arc::new(NeverLaunchBackend),
        )
        .await
        .unwrap();
        let req = persistent_req("p1");
        assert!(store.create_session(req.clone()).await.is_err());
        assert!(store.create_session(req).await.is_err());
    }

    #[tokio::test]
    async fn persistent_profile_allows_only_one_writer() {
        let tmp = tempfile::tempdir().unwrap();
        let store = AppStore::new(test_config(tmp.path().to_path_buf()), Arc::new(FakeBackend))
            .await
            .unwrap();
        let first = store.create_session(persistent_req("p1")).await.unwrap();
        let second = store.create_session(persistent_req("p1")).await;
        assert!(second.is_err());
        store.delete_session(first.id).await.unwrap();
        assert!(store.create_session(persistent_req("p1")).await.is_ok());
    }

    #[tokio::test]
    async fn takeover_token_refreshes_on_pause_and_invalidates_on_release() {
        let tmp = tempfile::tempdir().unwrap();
        let store = AppStore::new(test_config(tmp.path().to_path_buf()), Arc::new(FakeBackend))
            .await
            .unwrap();
        let created = store.create_session(persistent_req("p1")).await.unwrap();
        let created_url = created.takeover_url.clone().unwrap();
        let old_token = token_from_url(&created_url).to_string();

        let paused = store
            .pause_for_human(created.id, Some("oauth password step".into()))
            .await
            .unwrap();
        assert_eq!(
            paused.pause_reason.as_deref(),
            Some(crate::security::REDACTED)
        );
        let paused_url = paused.takeover_url.clone().unwrap();
        let new_token = token_from_url(&paused_url).to_string();
        assert_ne!(old_token, new_token);
        assert!(!store.validate_takeover_token(created.id, &old_token).await);
        assert!(store.validate_takeover_token(created.id, &new_token).await);

        let released = store.release(created.id).await.unwrap();
        assert_eq!(released.status, SessionStatus::Running);
        assert!(released.takeover_url.is_none());
        assert!(!store.validate_takeover_token(created.id, &new_token).await);
        store.delete_session(created.id).await.unwrap();
    }
}
