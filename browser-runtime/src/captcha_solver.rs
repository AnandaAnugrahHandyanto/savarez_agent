//! CAPTCHA solver module — HTTP clients for 2Captcha and Anti-Captcha.
//!
//! Uses the standard `createTask` / `getTaskResult` polling pattern.
//! Both providers share the same API contract with minor URL differences.

use std::time::Duration;

use reqwest::Client;
use serde::{Deserialize, Serialize};
use tokio::time::sleep;
use tracing::{debug, info, warn};

/// Which provider to use.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SolverProvider {
    TwoCaptcha,
    AntiCaptcha,
}

/// Successful solve result.
#[derive(Debug, Clone)]
pub struct SolvedToken {
    pub token: String,
    pub provider: SolverProvider,
}

// ── Request / Response types ──────────────────────────────────────────────

#[derive(Serialize)]
struct CreateTaskRequest {
    #[serde(rename = "clientKey")]
    client_key: String,
    task: TaskPayload,
}

#[derive(Serialize)]
struct TaskPayload {
    #[serde(rename = "type")]
    challenge_type: String,
    #[serde(rename = "websiteURL")]
    website_url: String,
    #[serde(rename = "websiteKey")]
    website_key: String,
}

#[derive(Deserialize)]
struct CreateTaskResponse {
    #[serde(rename = "errorId")]
    error_id: u8,
    #[serde(rename = "taskId")]
    task_id: Option<u64>,
    #[serde(rename = "errorCode", default)]
    error_code: String,
}

#[derive(Serialize)]
struct GetTaskResultRequest<'a> {
    #[serde(rename = "clientKey")]
    client_key: &'a str,
    #[serde(rename = "taskId")]
    task_id: u64,
}

#[derive(Deserialize, Debug)]
struct GetTaskResultResponse {
    status: String,
    solution: Option<SolutionPayload>,
    #[serde(rename = "errorId", default)]
    error_id: u8,
    #[serde(rename = "errorCode", default)]
    error_code: String,
}

#[derive(Deserialize, Debug)]
struct SolutionPayload {
    #[serde(rename = "gRecaptchaResponse")]
    g_recaptcha_response: Option<String>,
    #[serde(rename = "token")]
    token: Option<String>,
}

// ── Public API ─────────────────────────────────────────────────────────────

impl SolverProvider {
    fn create_task_url(&self) -> &'static str {
        match self {
            Self::TwoCaptcha => "https://api.2captcha.com/createTask",
            Self::AntiCaptcha => "https://api.anti-captcha.com/createTask",
        }
    }

    fn get_result_url(&self) -> &'static str {
        match self {
            Self::TwoCaptcha => "https://api.2captcha.com/getTaskResult",
            Self::AntiCaptcha => "https://api.anti-captcha.com/getTaskResult",
        }
    }
}

/// Solve a CAPTCHA using the given provider.
///
/// * `api_key` — provider API key (from `HBR_2CAPTCHA_API_KEY` or `HBR_ANTI_CAPTCHA_API_KEY`).
/// * `site_key` — the site's CAPTCHA key (extracted from the page).
/// * `page_url` — the URL where the CAPTCHA appeared.
/// * `challenge_type` — e.g. `"RecaptchaV2TaskProxyless"` or `"HCaptchaTaskProxyless"`.
/// * `provider` — which service to use.
/// * `timeout` — maximum total wait time.
pub async fn solve(
    api_key: &str,
    site_key: &str,
    page_url: &str,
    challenge_type: &str,
    provider: SolverProvider,
    timeout: Duration,
) -> Result<SolvedToken, String> {
    let client = Client::builder()
        .timeout(Duration::from_secs(30))
        .build()
        .map_err(|e| format!("reqwest build error: {e}"))?;

    let provider_label = match provider {
        SolverProvider::TwoCaptcha => "2Captcha",
        SolverProvider::AntiCaptcha => "AntiCaptcha",
    };

    // 1. Create task
    let create_body = CreateTaskRequest {
        client_key: api_key.to_string(),
        task: TaskPayload {
            challenge_type: challenge_type.to_string(),
            website_url: page_url.to_string(),
            website_key: site_key.to_string(),
        },
    };

    info!(
        provider = provider_label,
        site_key_present = !site_key.is_empty(),
        page_url_present = !page_url.is_empty(),
        challenge_type,
        "Creating CAPTCHA task"
    );

    let create_resp: CreateTaskResponse = client
        .post(provider.create_task_url())
        .json(&create_body)
        .send()
        .await
        .map_err(|e| format!("HTTP error creating task: {e}"))?
        .json()
        .await
        .map_err(|e| format!("JSON parse error: {e}"))?;

    if create_resp.error_id != 0 {
        return Err(format!(
            "Provider returned error {}: {}",
            create_resp.error_id, create_resp.error_code
        ));
    }

    let task_id = create_resp
        .task_id
        .ok_or_else(|| "No taskId in response".to_string())?;

    debug!(
        provider = provider_label,
        task_id_present = true,
        "Task created, polling…"
    );

    // 2. Poll for result
    let deadline = tokio::time::Instant::now() + timeout;

    loop {
        if tokio::time::Instant::now() >= deadline {
            return Err(format!(
                "CAPTCHA solve timed out after {:.0}s",
                timeout.as_secs()
            ));
        }

        sleep(Duration::from_secs(3)).await;

        let poll_resp: GetTaskResultResponse = client
            .post(provider.get_result_url())
            .json(&GetTaskResultRequest {
                client_key: api_key,
                task_id,
            })
            .send()
            .await
            .map_err(|e| format!("HTTP error polling: {e}"))?
            .json()
            .await
            .map_err(|e| format!("JSON parse error polling: {e}"))?;

        match poll_resp.status.as_str() {
            "ready" => {
                let token = poll_resp
                    .solution
                    .as_ref()
                    .and_then(|s| {
                        s.g_recaptcha_response
                            .as_deref()
                            .or(s.token.as_deref())
                            .map(String::from)
                    })
                    .ok_or_else(|| "Solution missing token".to_string())?;

                info!(
                    provider = provider_label,
                    task_id_present = true,
                    "CAPTCHA solved successfully"
                );
                return Ok(SolvedToken { token, provider });
            }
            "processing" => {
                // Normal — keep polling
                continue;
            }
            other => {
                warn!(
                    provider = provider_label,
                    task_id_present = true,
                    status = other,
                    error_id = poll_resp.error_id,
                    error_code = poll_resp.error_code,
                    "Unexpected status"
                );
                return Err(format!(
                    "Unexpected status '{other}' (error {})",
                    poll_resp.error_id
                ));
            }
        }
    }
}
