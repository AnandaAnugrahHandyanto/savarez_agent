use std::time::Duration;

use anyhow::Result;
use reqwest::{Client, Method, Request, header};
use serde::{Serialize, de::DeserializeOwned};
use uuid::Uuid;

use crate::models::{
    CaptchaReportRequest, CaptchaResolveRequest, CleanupArtifactsRequest, CreateProfileRequest,
    CreateSessionRequest, CredentialDecisionRequest, CredentialFillStartRequest,
    CredentialFillStatusRecord, CredentialPrivacyGuardResponse, PauseForHumanRequest,
    WaitSessionResponse,
};

#[derive(Clone)]
pub struct BrowserRuntimeClient {
    client: Client,
    base_url: String,
    bearer_token: Option<String>,
}

impl BrowserRuntimeClient {
    pub fn new(server: &str, token: Option<String>) -> Result<Self> {
        Ok(Self {
            client: Client::builder().build()?,
            base_url: server.trim_end_matches('/').to_string(),
            bearer_token: token,
        })
    }

    pub fn create_session_request(&self, payload: &CreateSessionRequest) -> Result<Request> {
        self.build_json_request(Method::POST, "/sessions", payload)
    }

    pub fn list_sessions_request(&self) -> Result<Request> {
        self.build_request(Method::GET, "/sessions")
    }

    pub fn get_session_request(&self, session_id: Uuid) -> Result<Request> {
        self.build_request(Method::GET, &format!("/sessions/{session_id}"))
    }

    pub fn delete_session_request(&self, session_id: Uuid) -> Result<Request> {
        self.build_request(Method::DELETE, &format!("/sessions/{session_id}"))
    }

    pub fn pause_session_request(
        &self,
        session_id: Uuid,
        payload: &PauseForHumanRequest,
    ) -> Result<Request> {
        self.build_json_request(
            Method::POST,
            &format!("/sessions/{session_id}/pause_for_human"),
            payload,
        )
    }

    pub fn release_session_request(&self, session_id: Uuid) -> Result<Request> {
        self.build_request(Method::POST, &format!("/sessions/{session_id}/release"))
    }

    pub fn captcha_report_request(
        &self,
        session_id: Uuid,
        payload: &CaptchaReportRequest,
    ) -> Result<Request> {
        self.build_json_request(
            Method::POST,
            &format!("/sessions/{session_id}/captcha/report"),
            payload,
        )
    }

    pub fn captcha_resolve_request(
        &self,
        session_id: Uuid,
        payload: &CaptchaResolveRequest,
    ) -> Result<Request> {
        self.build_json_request(
            Method::POST,
            &format!("/sessions/{session_id}/captcha/resolve"),
            payload,
        )
    }

    pub fn wait_session_request(&self, session_id: Uuid, timeout: Duration) -> Result<Request> {
        self.build_request(
            Method::GET,
            &format!(
                "/sessions/{session_id}/wait?timeout_ms={}",
                timeout.as_millis()
            ),
        )
    }

    pub fn credential_fill_request(
        &self,
        session_id: Uuid,
        payload: &CredentialFillStartRequest,
    ) -> Result<Request> {
        self.build_json_request(
            Method::POST,
            &format!("/sessions/{session_id}/credentials/fill"),
            payload,
        )
    }

    pub fn credential_fill_status_request(
        &self,
        session_id: Uuid,
        request_id: Uuid,
    ) -> Result<Request> {
        self.build_request(
            Method::GET,
            &format!("/sessions/{session_id}/credentials/fill/{request_id}"),
        )
    }

    pub fn approve_credential_fill_request(
        &self,
        session_id: Uuid,
        request_id: Uuid,
        payload: &CredentialDecisionRequest,
    ) -> Result<Request> {
        self.build_json_request(
            Method::POST,
            &format!("/sessions/{session_id}/credentials/fill/{request_id}/approve"),
            payload,
        )
    }

    pub fn deny_credential_fill_request(
        &self,
        session_id: Uuid,
        request_id: Uuid,
        payload: &CredentialDecisionRequest,
    ) -> Result<Request> {
        self.build_json_request(
            Method::POST,
            &format!("/sessions/{session_id}/credentials/fill/{request_id}/deny"),
            payload,
        )
    }

    pub fn clear_credential_privacy_guard_request(&self, session_id: Uuid) -> Result<Request> {
        self.build_request(
            Method::POST,
            &format!("/sessions/{session_id}/credentials/privacy-guard/clear"),
        )
    }

    pub fn screenshot_request(&self, session_id: Uuid) -> Result<Request> {
        self.build_request(Method::GET, &format!("/sessions/{session_id}/screenshot"))
    }

    pub fn list_profiles_request(&self) -> Result<Request> {
        self.build_request(Method::GET, "/profiles")
    }

    pub fn create_profile_request(&self, payload: &CreateProfileRequest) -> Result<Request> {
        self.build_json_request(Method::POST, "/profiles", payload)
    }

    pub fn delete_profile_request(&self, profile_id: &str) -> Result<Request> {
        self.build_request(Method::DELETE, &format!("/profiles/{profile_id}"))
    }

    pub fn list_artifacts_request(&self, session_id: Uuid) -> Result<Request> {
        self.build_request(Method::GET, &format!("/sessions/{session_id}/artifacts"))
    }

    pub fn list_downloads_request(&self, session_id: Uuid) -> Result<Request> {
        self.build_request(Method::GET, &format!("/sessions/{session_id}/downloads"))
    }

    pub fn download_request(&self, session_id: Uuid, name: &str) -> Result<Request> {
        self.build_query_request(
            Method::GET,
            &format!("/sessions/{session_id}/download"),
            &[("name", name)],
        )
    }

    pub fn cleanup_artifacts_request(&self, payload: &CleanupArtifactsRequest) -> Result<Request> {
        self.build_json_request(Method::POST, "/artifacts/cleanup", payload)
    }

    pub async fn create_session(
        &self,
        payload: &CreateSessionRequest,
    ) -> Result<serde_json::Value> {
        self.execute_json(self.create_session_request(payload)?)
            .await
    }

    pub async fn list_sessions(&self) -> Result<serde_json::Value> {
        self.execute_json(self.list_sessions_request()?).await
    }

    pub async fn get_session(&self, session_id: Uuid) -> Result<serde_json::Value> {
        self.execute_json(self.get_session_request(session_id)?)
            .await
    }

    pub async fn delete_session(&self, session_id: Uuid) -> Result<serde_json::Value> {
        self.execute_json(self.delete_session_request(session_id)?)
            .await
    }

    pub async fn pause_session(
        &self,
        session_id: Uuid,
        payload: &PauseForHumanRequest,
    ) -> Result<serde_json::Value> {
        self.execute_json(self.pause_session_request(session_id, payload)?)
            .await
    }

    pub async fn release_session(&self, session_id: Uuid) -> Result<serde_json::Value> {
        self.execute_json(self.release_session_request(session_id)?)
            .await
    }

    pub async fn captcha_report(
        &self,
        session_id: Uuid,
        payload: &CaptchaReportRequest,
    ) -> Result<serde_json::Value> {
        self.execute_json(self.captcha_report_request(session_id, payload)?)
            .await
    }

    pub async fn captcha_resolve(
        &self,
        session_id: Uuid,
        payload: &CaptchaResolveRequest,
    ) -> Result<serde_json::Value> {
        self.execute_json(self.captcha_resolve_request(session_id, payload)?)
            .await
    }

    pub async fn wait_session(
        &self,
        session_id: Uuid,
        timeout: Duration,
    ) -> Result<WaitSessionResponse> {
        self.execute_typed(self.wait_session_request(session_id, timeout)?)
            .await
    }

    pub async fn credential_fill(
        &self,
        session_id: Uuid,
        payload: &CredentialFillStartRequest,
    ) -> Result<CredentialFillStatusRecord> {
        self.execute_typed(self.credential_fill_request(session_id, payload)?)
            .await
    }

    pub async fn credential_fill_status(
        &self,
        session_id: Uuid,
        request_id: Uuid,
    ) -> Result<CredentialFillStatusRecord> {
        self.execute_typed(self.credential_fill_status_request(session_id, request_id)?)
            .await
    }

    pub async fn approve_credential_fill(
        &self,
        session_id: Uuid,
        request_id: Uuid,
        note: Option<String>,
    ) -> Result<CredentialFillStatusRecord> {
        self.execute_typed(self.approve_credential_fill_request(
            session_id,
            request_id,
            &CredentialDecisionRequest { note, reason: None },
        )?)
        .await
    }

    pub async fn deny_credential_fill(
        &self,
        session_id: Uuid,
        request_id: Uuid,
        note: Option<String>,
    ) -> Result<CredentialFillStatusRecord> {
        self.execute_typed(self.deny_credential_fill_request(
            session_id,
            request_id,
            &CredentialDecisionRequest {
                note: None,
                reason: note,
            },
        )?)
        .await
    }

    pub async fn clear_credential_privacy_guard(
        &self,
        session_id: Uuid,
    ) -> Result<CredentialPrivacyGuardResponse> {
        self.execute_typed(self.clear_credential_privacy_guard_request(session_id)?)
            .await
    }

    pub async fn screenshot(&self, session_id: Uuid) -> Result<Vec<u8>> {
        self.execute_bytes(self.screenshot_request(session_id)?)
            .await
    }

    pub async fn create_profile(
        &self,
        payload: &CreateProfileRequest,
    ) -> Result<serde_json::Value> {
        self.execute_json(self.create_profile_request(payload)?)
            .await
    }

    pub async fn list_profiles(&self) -> Result<serde_json::Value> {
        self.execute_json(self.list_profiles_request()?).await
    }

    pub async fn delete_profile(&self, profile_id: &str) -> Result<()> {
        self.execute_empty(self.delete_profile_request(profile_id)?)
            .await
    }

    pub async fn list_artifacts(&self, session_id: Uuid) -> Result<serde_json::Value> {
        self.execute_json(self.list_artifacts_request(session_id)?)
            .await
    }

    pub async fn list_downloads(&self, session_id: Uuid) -> Result<serde_json::Value> {
        self.execute_json(self.list_downloads_request(session_id)?)
            .await
    }

    pub async fn download(&self, session_id: Uuid, name: &str) -> Result<Vec<u8>> {
        self.execute_bytes(self.download_request(session_id, name)?)
            .await
    }

    pub async fn cleanup_artifacts(
        &self,
        payload: &CleanupArtifactsRequest,
    ) -> Result<serde_json::Value> {
        self.execute_json(self.cleanup_artifacts_request(payload)?)
            .await
    }

    fn build_request(&self, method: Method, path: &str) -> Result<Request> {
        let mut builder = self.client.request(method, self.url(path));
        if let Some(token) = &self.bearer_token {
            builder = builder.header(header::AUTHORIZATION, format!("Bearer {token}"));
        }
        Ok(builder.build()?)
    }

    fn build_query_request<T: Serialize + ?Sized>(
        &self,
        method: Method,
        path: &str,
        query: &T,
    ) -> Result<Request> {
        let mut builder = self.client.request(method, self.url(path)).query(query);
        if let Some(token) = &self.bearer_token {
            builder = builder.header(header::AUTHORIZATION, format!("Bearer {token}"));
        }
        Ok(builder.build()?)
    }

    fn build_json_request<T: Serialize + ?Sized>(
        &self,
        method: Method,
        path: &str,
        payload: &T,
    ) -> Result<Request> {
        let body = serde_json::to_vec(payload)?;
        let mut builder = self
            .client
            .request(method, self.url(path))
            .header(header::CONTENT_TYPE, "application/json");
        if let Some(token) = &self.bearer_token {
            builder = builder.header(header::AUTHORIZATION, format!("Bearer {token}"));
        }
        Ok(builder.body(body).build()?)
    }

    fn url(&self, path: &str) -> String {
        let path = if path.starts_with('/') {
            path.to_string()
        } else {
            format!("/{path}")
        };
        format!("{}{}", self.base_url, path)
    }

    async fn execute_json(&self, request: Request) -> Result<serde_json::Value> {
        self.execute_typed(request).await
    }

    async fn execute_typed<T: DeserializeOwned>(&self, request: Request) -> Result<T> {
        Ok(self
            .client
            .execute(request)
            .await?
            .error_for_status()?
            .json::<T>()
            .await?)
    }

    async fn execute_bytes(&self, request: Request) -> Result<Vec<u8>> {
        Ok(self
            .client
            .execute(request)
            .await?
            .error_for_status()?
            .bytes()
            .await?
            .to_vec())
    }

    async fn execute_empty(&self, request: Request) -> Result<()> {
        self.client.execute(request).await?.error_for_status()?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        models::{
            CleanupArtifactsRequest, CreateProfileRequest, CreateSessionRequest,
            CredentialFillStartRequest, PauseForHumanRequest, SessionStatus,
        },
        test_support::spawn_api_server,
    };
    use reqwest::{Method, header};
    use serde_json::json;
    use tokio::time::sleep;

    #[test]
    fn request_builders_normalize_urls_and_attach_json_and_auth_headers() {
        let session_id = Uuid::new_v4();
        let client =
            BrowserRuntimeClient::new("http://127.0.0.1:7788/", Some("secret-token".into()))
                .unwrap();

        assert_eq!(client.url("sessions"), "http://127.0.0.1:7788/sessions");
        assert_eq!(client.url("/profiles"), "http://127.0.0.1:7788/profiles");

        let create = client
            .create_session_request(&CreateSessionRequest {
                profile_id: Some("p1".into()),
                headless: Some(true),
                viewport: None,
                persist_profile: Some(false),
                launch_timeout_secs: None,
                persona: None,
                ..Default::default()
            })
            .unwrap();
        assert_eq!(create.method(), Method::POST);
        assert_eq!(create.url().as_str(), "http://127.0.0.1:7788/sessions");
        assert_eq!(
            create.headers().get(header::AUTHORIZATION).unwrap(),
            "Bearer secret-token"
        );
        assert_eq!(
            create.headers().get(header::CONTENT_TYPE).unwrap(),
            "application/json"
        );
        let json_body: serde_json::Value =
            serde_json::from_slice(create.body().and_then(|body| body.as_bytes()).unwrap())
                .unwrap();
        assert_eq!(
            json_body,
            json!({
                "profile_id": "p1",
                "headless": true,
                "viewport": null,
                "persist_profile": false,
            })
        );

        let pause = client
            .pause_session_request(
                session_id,
                &PauseForHumanRequest {
                    reason: Some("manual oauth approval".into()),
                },
            )
            .unwrap();
        assert_eq!(pause.method(), Method::POST);
        assert_eq!(
            pause.url().as_str(),
            format!("http://127.0.0.1:7788/sessions/{session_id}/pause_for_human")
        );

        let release = client.release_session_request(session_id).unwrap();
        assert_eq!(release.method(), Method::POST);
        assert_eq!(
            release.url().as_str(),
            format!("http://127.0.0.1:7788/sessions/{session_id}/release")
        );

        let wait = client
            .wait_session_request(session_id, Duration::from_secs(42))
            .unwrap();
        assert_eq!(
            wait.url().as_str(),
            format!("http://127.0.0.1:7788/sessions/{session_id}/wait?timeout_ms=42000")
        );

        let screenshot = client.screenshot_request(session_id).unwrap();
        assert_eq!(screenshot.method(), Method::GET);
        assert_eq!(
            screenshot.url().as_str(),
            format!("http://127.0.0.1:7788/sessions/{session_id}/screenshot")
        );

        let credential_fill = client
            .credential_fill_request(
                session_id,
                &CredentialFillStartRequest {
                    alias: "demo-login".into(),
                    username_selector: Some("#user".into()),
                    password_selector: Some("#pass".into()),
                    purpose: Some("login".into()),
                    expected_origin: Some("https://example.test".into()),
                },
            )
            .unwrap();
        assert_eq!(credential_fill.method(), Method::POST);
        assert_eq!(
            credential_fill.url().as_str(),
            format!("http://127.0.0.1:7788/sessions/{session_id}/credentials/fill")
        );
        let credential_body: serde_json::Value = serde_json::from_slice(
            credential_fill
                .body()
                .and_then(|body| body.as_bytes())
                .unwrap(),
        )
        .unwrap();
        assert_eq!(credential_body["alias"], "demo-login");
        assert_eq!(credential_body["username_selector"], "#user");
        assert_eq!(credential_body["password_selector"], "#pass");

        let credential_request_id = Uuid::new_v4();
        let credential_status = client
            .credential_fill_status_request(session_id, credential_request_id)
            .unwrap();
        assert_eq!(credential_status.method(), Method::GET);
        assert_eq!(
            credential_status.url().as_str(),
            format!(
                "http://127.0.0.1:7788/sessions/{session_id}/credentials/fill/{credential_request_id}"
            )
        );
        let credential_approve = client
            .approve_credential_fill_request(
                session_id,
                credential_request_id,
                &CredentialDecisionRequest {
                    note: Some("operator approved".into()),
                    reason: None,
                },
            )
            .unwrap();
        assert_eq!(credential_approve.method(), Method::POST);
        assert_eq!(
            credential_approve.url().as_str(),
            format!(
                "http://127.0.0.1:7788/sessions/{session_id}/credentials/fill/{credential_request_id}/approve"
            )
        );
        let approve_body: serde_json::Value = serde_json::from_slice(
            credential_approve
                .body()
                .and_then(|body| body.as_bytes())
                .unwrap(),
        )
        .unwrap();
        assert_eq!(approve_body["note"], "operator approved");
        let credential_deny = client
            .deny_credential_fill_request(
                session_id,
                credential_request_id,
                &CredentialDecisionRequest {
                    note: None,
                    reason: Some("operator denied".into()),
                },
            )
            .unwrap();
        assert_eq!(credential_deny.method(), Method::POST);
        assert_eq!(
            credential_deny.url().as_str(),
            format!(
                "http://127.0.0.1:7788/sessions/{session_id}/credentials/fill/{credential_request_id}/deny"
            )
        );
        let deny_body: serde_json::Value = serde_json::from_slice(
            credential_deny
                .body()
                .and_then(|body| body.as_bytes())
                .unwrap(),
        )
        .unwrap();
        assert_eq!(deny_body["reason"], "operator denied");
        assert!(deny_body.get("note").is_none());
        let credential_clear = client
            .clear_credential_privacy_guard_request(session_id)
            .unwrap();
        assert_eq!(credential_clear.method(), Method::POST);
        assert_eq!(
            credential_clear.url().as_str(),
            format!("http://127.0.0.1:7788/sessions/{session_id}/credentials/privacy-guard/clear")
        );

        let profiles = client.list_profiles_request().unwrap();
        assert_eq!(profiles.url().as_str(), "http://127.0.0.1:7788/profiles");
        let create_profile = client
            .create_profile_request(&CreateProfileRequest {
                id: Some("p1".into()),
            })
            .unwrap();
        assert_eq!(create_profile.method(), Method::POST);
        assert_eq!(
            create_profile.url().as_str(),
            "http://127.0.0.1:7788/profiles"
        );

        let delete_profile = client.delete_profile_request("p1").unwrap();
        assert_eq!(delete_profile.method(), Method::DELETE);
        assert_eq!(
            delete_profile.url().as_str(),
            "http://127.0.0.1:7788/profiles/p1"
        );

        let artifacts = client.list_artifacts_request(session_id).unwrap();
        assert_eq!(artifacts.method(), Method::GET);
        assert_eq!(
            artifacts.url().as_str(),
            format!("http://127.0.0.1:7788/sessions/{session_id}/artifacts")
        );

        let downloads = client.list_downloads_request(session_id).unwrap();
        assert_eq!(downloads.method(), Method::GET);
        assert_eq!(
            downloads.url().as_str(),
            format!("http://127.0.0.1:7788/sessions/{session_id}/downloads")
        );

        let download = client
            .download_request(session_id, "report one.txt")
            .unwrap();
        assert_eq!(download.method(), Method::GET);
        assert_eq!(
            download.url().as_str(),
            format!("http://127.0.0.1:7788/sessions/{session_id}/download?name=report+one.txt")
        );

        let cleanup = client
            .cleanup_artifacts_request(&CleanupArtifactsRequest {
                dry_run: true,
                older_than_secs: Some(30),
            })
            .unwrap();
        assert_eq!(cleanup.method(), Method::POST);
        assert_eq!(
            cleanup.url().as_str(),
            "http://127.0.0.1:7788/artifacts/cleanup"
        );
        let json_body: serde_json::Value =
            serde_json::from_slice(cleanup.body().and_then(|body| body.as_bytes()).unwrap())
                .unwrap();
        assert_eq!(json_body, json!({"dry_run": true, "older_than_secs": 30}));
    }

    #[tokio::test]
    async fn async_client_methods_cover_session_profile_and_artifact_lifecycle() {
        let server = spawn_api_server(None).await;
        let client = BrowserRuntimeClient::new(&server.base_url, None).unwrap();

        let profile = client
            .create_profile(&CreateProfileRequest {
                id: Some("p1".into()),
            })
            .await
            .unwrap();
        assert_eq!(profile["id"], "p1");

        let profiles = client.list_profiles().await.unwrap();
        assert_eq!(profiles.as_array().unwrap().len(), 1);

        let created = client
            .create_session(&CreateSessionRequest {
                profile_id: Some("p1".into()),
                headless: Some(true),
                viewport: None,
                persist_profile: Some(true),
                launch_timeout_secs: None,
                persona: None,
                ..Default::default()
            })
            .await
            .unwrap();
        let session_id = Uuid::parse_str(created["id"].as_str().unwrap()).unwrap();
        assert_eq!(created["status"], "running");
        assert!(created["takeover_url"].is_null());

        let sessions = client.list_sessions().await.unwrap();
        assert_eq!(sessions.as_array().unwrap().len(), 1);

        let fetched = client.get_session(session_id).await.unwrap();
        assert_eq!(fetched["id"], session_id.to_string());
        assert_eq!(fetched["profile_id"], "p1");
        assert!(fetched["takeover_url"].is_null());

        let paused = client
            .pause_session(
                session_id,
                &PauseForHumanRequest {
                    reason: Some("manual oauth approval".into()),
                },
            )
            .await
            .unwrap();
        assert_eq!(paused["status"], "paused_for_human");
        assert!(paused["takeover_url"].is_string());

        let releaser = {
            let client = client.clone();
            tokio::spawn(async move {
                sleep(Duration::from_millis(25)).await;
                let released = client.release_session(session_id).await.unwrap();
                assert_eq!(released["status"], "running");
                assert!(released["takeover_url"].is_null());
            })
        };

        let wait = client
            .wait_session(session_id, Duration::from_millis(500))
            .await
            .unwrap();
        assert!(!wait.timed_out);
        assert_eq!(wait.session.status, SessionStatus::Running);
        releaser.await.unwrap();

        let screenshot = client.screenshot(session_id).await.unwrap();
        assert_eq!(screenshot, b"png");

        let artifacts = client.list_artifacts(session_id).await.unwrap();
        assert_eq!(artifacts["session_id"], session_id.to_string());
        assert!(artifacts["artifacts"].as_array().unwrap().len() >= 2);

        let deleted = client.delete_session(session_id).await.unwrap();
        assert_eq!(deleted["status"], "closed");
        client.delete_profile("p1").await.unwrap();

        server.stop().await;
    }

    #[tokio::test]
    async fn client_surfaces_http_status_errors_for_json_and_bytes_requests() {
        let auth_server = spawn_api_server(Some("secret-token")).await;
        let unauthenticated = BrowserRuntimeClient::new(&auth_server.base_url, None).unwrap();
        let err = unauthenticated.list_sessions().await.unwrap_err();
        assert!(err.to_string().contains("401"));
        auth_server.stop().await;

        let server = spawn_api_server(None).await;
        let client = BrowserRuntimeClient::new(&server.base_url, None).unwrap();
        let missing = Uuid::new_v4();

        let err = client.get_session(missing).await.unwrap_err();
        assert!(err.to_string().contains("404"));

        let err = client.screenshot(missing).await.unwrap_err();
        assert!(err.to_string().contains("404"));

        server.stop().await;
    }

    #[tokio::test]
    async fn client_auth_errors_do_not_echo_bearer_token_values() {
        let server = spawn_api_server(Some("secret-token")).await;
        let client =
            BrowserRuntimeClient::new(&server.base_url, Some("wrong-token".into())).unwrap();

        let err = client.list_profiles().await.unwrap_err();
        let rendered = err.to_string();
        let status = err
            .downcast_ref::<reqwest::Error>()
            .and_then(|value| value.status());

        assert_eq!(status, Some(reqwest::StatusCode::FORBIDDEN));
        assert!(!rendered.contains("wrong-token"));
        assert!(!rendered.to_ascii_lowercase().contains("authorization"));

        server.stop().await;
    }
}
