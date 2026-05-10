use std::{
    fs,
    os::unix::fs::PermissionsExt,
    path::{Path, PathBuf},
};

use anyhow::{Context, Result};
use rand::{Rng, distributions::Alphanumeric};

pub const REDACTED: &str = "[REDACTED]";

const SECRET_MARKERS: &[&str] = &[
    "cookie",
    "authorization",
    "auth",
    "token",
    "password",
    "passwd",
    "secret",
    "card",
    "cvv",
    "cvc",
    "pan",
    "form",
    "request_body",
    "body",
];

pub fn redact_key_value(key: &str, value: &str) -> String {
    let key = key.to_ascii_lowercase();
    if SECRET_MARKERS.iter().any(|marker| key.contains(marker)) {
        REDACTED.to_string()
    } else {
        value.to_string()
    }
}

pub fn redact_text(input: &str) -> String {
    let mut out = input.to_string();
    for marker in SECRET_MARKERS {
        let lower = out.to_ascii_lowercase();
        if lower.contains(marker) {
            out = out.replace(input, REDACTED);
            break;
        }
    }
    out
}

pub fn random_token(bytes: usize) -> String {
    rand::thread_rng()
        .sample_iter(&Alphanumeric)
        .take(bytes)
        .map(char::from)
        .collect()
}

pub fn ensure_private_dir(path: &Path) -> Result<()> {
    fs::create_dir_all(path).with_context(|| format!("create {}", path.display()))?;
    fs::set_permissions(path, fs::Permissions::from_mode(0o700))
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

#[cfg(test)]
mod tests {
    use super::*;

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
    fn rejects_path_traversal_ids() {
        assert!(sanitize_id("good_profile-1").is_some());
        assert!(sanitize_id("../bad").is_none());
        assert!(sanitize_id("bad/path").is_none());
        assert!(sanitize_id("bad path").is_none());
    }
}
