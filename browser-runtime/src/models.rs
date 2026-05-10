use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

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

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateSessionRequest {
    pub profile_id: Option<String>,
    pub headless: Option<bool>,
    pub viewport: Option<Viewport>,
    pub persist_profile: Option<bool>,
}

#[derive(Debug, Clone, Serialize)]
pub struct SessionInfo {
    pub id: Uuid,
    pub status: SessionStatus,
    pub cdp_ws_url: Option<String>,
    pub takeover_url: Option<String>,
    pub profile_id: String,
    pub persist_profile: bool,
    pub headless: bool,
    pub viewport: Viewport,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub pause_reason: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateSessionResponse {
    pub id: Uuid,
    pub status: SessionStatus,
    pub cdp_ws_url: String,
    pub takeover_url: String,
    pub profile_id: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct PauseForHumanRequest {
    pub reason: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ProfileInfo {
    pub id: String,
    pub path: String,
    pub locked_by: Option<Uuid>,
    pub created_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CreateProfileRequest {
    pub id: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ArtifactInfo {
    pub kind: String,
    pub path: String,
    pub created_at: DateTime<Utc>,
    pub size_bytes: u64,
}

#[derive(Debug, Clone, Serialize)]
pub struct ArtifactsResponse {
    pub session_id: Uuid,
    pub artifacts: Vec<ArtifactInfo>,
    pub downloads_dir: String,
}

#[derive(Debug, Clone, Serialize)]
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
}
