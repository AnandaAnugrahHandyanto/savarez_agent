use std::{
    fs,
    os::unix::fs::PermissionsExt,
    path::{Path, PathBuf},
};

use anyhow::{Context, Result};
use rand::{Rng, distributions::Alphanumeric};
use serde_json::Value;

pub const REDACTED: &str = "[REDACTED]";

const SECRET_MARKERS: &[&str] = &[
    "cookie",
    "authorization",
    "header",
    "auth",
    "cdp_ws",
    "takeover_url",
    "devtools",
    "websocket",
    "token",
    "password",
    "passwd",
    "secret",
    "credential",
    "label_hint",
    "onepassword",
    "op_uri",
    "op://",
    "vault",
    "item_id",
    "otp",
    "totp",
    "one_time",
    "passcode",
    "api_key",
    "card",
    "cvv",
    "cvc",
    "pan",
    "form",
    "request_body",
    "body",
    "fingerprint",
    "captcha_token",
    "g-recaptcha-response",
    "h-captcha-response",
    "cf-turnstile-response",
    "captcha_solution",
    "sitekey",
    "website_key",
    "client_key",
    "provider_task_id",
    "provider_ref",
    "solution",
    "answer",
    "website_url",
    "page_url",
    "cost",
    "balance",
];

fn is_sensitive_key(key: &str) -> bool {
    let key = key.to_ascii_lowercase();
    SECRET_MARKERS.iter().any(|marker| key.contains(marker))
}

fn is_sensitive_text(value: &str) -> bool {
    let value = value.to_ascii_lowercase();
    SECRET_MARKERS.iter().any(|marker| value.contains(marker))
        || ((value.contains("ws://") || value.contains("wss://"))
            && value.contains("/devtools/browser/"))
        || (value.contains("/takeover/") && value.contains("token="))
}

pub fn redact_key_value(key: &str, value: &str) -> String {
    if is_sensitive_key(key) {
        REDACTED.to_string()
    } else {
        value.to_string()
    }
}

pub fn redact_text(input: &str) -> String {
    if is_sensitive_text(input) {
        REDACTED.to_string()
    } else {
        input.to_string()
    }
}

pub fn redact_json_value(value: Value) -> Value {
    match value {
        Value::Object(map) => Value::Object(
            map.into_iter()
                .map(|(key, value)| {
                    let value = if is_sensitive_key(&key) {
                        Value::String(REDACTED.to_string())
                    } else {
                        redact_json_value(value)
                    };
                    (key, value)
                })
                .collect(),
        ),
        Value::Array(values) => Value::Array(values.into_iter().map(redact_json_value).collect()),
        Value::String(value) => Value::String(redact_text(&value)),
        value => value,
    }
}

pub fn random_token(bytes: usize) -> String {
    rand::thread_rng()
        .sample_iter(&Alphanumeric)
        .take(bytes)
        .map(char::from)
        .collect()
}

pub fn ensure_private_dir(path: &Path) -> Result<()> {
    ensure_private_dir_with(
        path,
        |path| fs::create_dir_all(path),
        |path, perms| fs::set_permissions(path, perms),
    )
}

fn ensure_private_dir_with<C, P>(path: &Path, create_dir_all: C, set_permissions: P) -> Result<()>
where
    C: FnOnce(&Path) -> std::io::Result<()>,
    P: FnOnce(&Path, fs::Permissions) -> std::io::Result<()>,
{
    create_dir_all(path).with_context(|| format!("create {}", path.display()))?;
    set_permissions(path, fs::Permissions::from_mode(0o700))
        .with_context(|| format!("chmod 700 {}", path.display()))?;
    Ok(())
}

pub fn sanitize_id(raw: &str) -> Option<String> {
    let trimmed = raw.trim();
    if trimmed.is_empty()
        || trimmed == "."
        || trimmed == ".."
        || trimmed.contains('/')
        || trimmed.contains('\\')
    {
        return None;
    }
    if trimmed
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')
    {
        Some(trimmed.to_string())
    } else {
        None
    }
}

pub fn safe_child_path(base: &Path, raw_id: &str) -> Result<PathBuf> {
    let id = sanitize_id(raw_id).ok_or_else(|| anyhow::anyhow!("invalid id"))?;
    Ok(base.join(id))
}

pub fn safe_download_name(raw: &str) -> Option<String> {
    let trimmed = raw.trim();
    if trimmed.is_empty() || trimmed == "." || trimmed == ".." {
        return None;
    }

    let path = Path::new(trimmed);
    if path.components().count() != 1 {
        return None;
    }

    if trimmed.contains('/') || trimmed.contains('\\') || trimmed.chars().any(|ch| ch.is_control())
    {
        return None;
    }

    Some(trimmed.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::PermissionsExt;

    #[test]
    fn redacts_sensitive_keys() {
        assert_eq!(redact_key_value("Cookie", "abc"), REDACTED);
        assert_eq!(redact_key_value("x-card-number", "4111"), REDACTED);
        assert_eq!(
            redact_key_value("url", "https://example.com"),
            "https://example.com"
        );
    }

    #[test]
    fn redacts_hbr_credential_and_human_checkpoint_payloads() {
        let payload = serde_json::json!({
            "event": "credential_fill_requested",
            "credential_label_hint": "primary login for example.com",
            "onepassword_item_id": "item-123",
            "op_uri": "op://PrivateVault/Example/Login",
            "otp_code": "123456",
            "captcha_reason": "human checkpoint; card verification required",
            "captcha_token": "token-value",
            "sitekey": "site-key-value",
            "website_key": "website-key-value",
            "client_key": "client-key-value",
            "provider_task_id": "task-123",
            "g-recaptcha-response": "answer-token",
            "h-captcha-response": "answer-token",
            "cf-turnstile-response": "answer-token",
            "solution": "raw-solution",
            "answer": "raw-answer",
            "website_url": "https://example.test/path?private=query",
            "page_url": "https://example.test/path#fragment",
            "balance": "12.34",
            "safe_note": "manual approval requested"
        });

        let redacted = redact_json_value(payload);
        let text = serde_json::to_string(&redacted).unwrap();

        assert!(text.contains("manual approval requested"));
        assert!(!text.contains("primary login"));
        assert!(!text.contains("item-123"));
        assert!(!text.contains("op://"));
        assert!(!text.contains("123456"));
        assert!(!text.contains("card verification"));
        assert!(!text.contains("site-key-value"));
        assert!(!text.contains("website-key-value"));
        assert!(!text.contains("client-key-value"));
        assert!(!text.contains("task-123"));
        assert!(!text.contains("answer-token"));
        assert!(!text.contains("raw-solution"));
        assert!(!text.contains("raw-answer"));
        assert!(!text.contains("private=query"));
        assert!(!text.contains("fragment"));
        assert!(!text.contains("12.34"));
        assert!(text.matches(REDACTED).count() >= 15);
    }

    #[test]
    fn redacts_nested_json_artifact_payloads() {
        let payload = serde_json::json!({
            "event": "probe",
            "takeover_url": "synthetic takeover capability canary",
            "cdp_ws_url": "synthetic CDP websocket canary",
            "headers": {
                "Authorization": "synthetic authorization canary",
                "Accept-Language": "en-US,en;q=0.9"
            },
            "nested": [
                {"request_body": {"card_number": "4111111111111111"}},
                "fingerprint dump contained raw UA/client-hint values",
                "plain note"
            ],
            "viewport": {"width": 1280, "height": 800}
        });

        let redacted = redact_json_value(payload);
        let text = serde_json::to_string(&redacted).unwrap();

        assert!(text.contains(REDACTED));
        assert!(text.contains("plain note"));
        assert!(text.contains("1280"));
        assert!(!text.contains("synthetic authorization canary"));
        assert!(!text.contains("synthetic CDP websocket canary"));
        assert!(!text.contains("synthetic takeover capability canary"));
        assert!(!text.contains("devtools/browser"));
        assert!(!text.contains("ws://127.0.0.1"));
        assert!(!text.contains("4111111111111111"));
        assert!(!text.contains("fingerprint dump"));
        assert_eq!(
            redacted["headers"],
            serde_json::Value::String(REDACTED.to_string())
        );
    }

    #[test]
    fn rejects_path_traversal_ids() {
        assert!(sanitize_id("good_profile-1").is_some());
        assert!(sanitize_id("../bad").is_none());
        assert!(sanitize_id("bad/path").is_none());
        assert!(sanitize_id("bad path").is_none());
    }

    #[test]
    fn safe_download_names_allow_leaf_filenames_only() {
        assert_eq!(
            safe_download_name("report 2026-05-11.csv").as_deref(),
            Some("report 2026-05-11.csv")
        );
        assert!(safe_download_name("../secrets.txt").is_none());
        assert!(safe_download_name("nested/report.csv").is_none());
        assert!(safe_download_name("").is_none());
    }

    #[test]
    fn ensure_private_dir_and_safe_child_path_validate_filesystem_inputs() {
        let tempdir = tempfile::tempdir().unwrap();
        let path = tempdir.path().join("runtime/private");
        ensure_private_dir(&path).unwrap();
        assert!(path.is_dir());
        assert_eq!(
            fs::metadata(&path).unwrap().permissions().mode() & 0o777,
            0o700
        );

        assert_eq!(
            safe_child_path(tempdir.path(), "good_profile").unwrap(),
            tempdir.path().join("good_profile")
        );
        assert!(safe_child_path(tempdir.path(), "../bad").is_err());
    }

    #[test]
    fn ensure_private_dir_surfaces_permission_errors_with_context() {
        let tempdir = tempfile::tempdir().unwrap();
        let path = tempdir.path().join("runtime/private");
        let err = ensure_private_dir_with(
            &path,
            |path| fs::create_dir_all(path),
            |_path, _perms| {
                Err(std::io::Error::new(
                    std::io::ErrorKind::PermissionDenied,
                    "chmod denied",
                ))
            },
        )
        .unwrap_err();

        assert!(err.to_string().contains("chmod 700"));
        assert!(path.is_dir());
    }
}
