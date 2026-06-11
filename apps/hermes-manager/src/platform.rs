//! Platform integration planning for PATH and shell setup.
//!
//! This module keeps the first platform-integration slice side-effect free:
//! callers can inspect the planned PATH/profile changes before a later command
//! applies them through OS-specific mechanisms.

use std::fs;
use std::path::{Path, PathBuf};

use crate::{ManagerError, Result};

/// Start marker for Hermes-managed shell profile content.
pub const HERMES_PROFILE_BEGIN: &str = "# >>> Hermes Agent PATH >>>";

/// End marker for Hermes-managed shell profile content.
pub const HERMES_PROFILE_END: &str = "# <<< Hermes Agent PATH <<<";

/// Planned PATH mutation for a Hermes CLI binary directory.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct PathUpdatePlan {
    pub hermes_bin: PathBuf,
    pub changed: bool,
    pub next_path: String,
}

/// Compute the PATH that would make the Hermes command available.
pub fn plan_path_update(
    install_root: &Path,
    current_path: Option<String>,
    windows: bool,
) -> PathUpdatePlan {
    let hermes_bin = if windows {
        install_root.join("venv").join("Scripts")
    } else {
        install_root.join("venv").join("bin")
    };
    let delimiter = if windows { ';' } else { ':' };
    let current_path = current_path.unwrap_or_default();
    let mut parts = split_path_like(&current_path, delimiter);
    let already_present = parts
        .iter()
        .any(|part| path_eq_for_platform(part, &hermes_bin, windows));

    if !already_present {
        parts.insert(0, hermes_bin.display().to_string());
    }

    PathUpdatePlan {
        hermes_bin,
        changed: !already_present,
        next_path: parts.join(&delimiter.to_string()),
    }
}

/// Return a shell profile line users can apply on Unix-like platforms.
pub fn shell_profile_hint(plan: &PathUpdatePlan) -> String {
    format!("export PATH=\"{}:$PATH\"", plan.hermes_bin.display())
}

/// Write or replace the Hermes-managed PATH block in a shell profile file.
pub fn write_shell_profile_update(profile_path: &Path, plan: &PathUpdatePlan) -> Result<()> {
    let existing = match fs::read_to_string(profile_path) {
        Ok(text) => text,
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => String::new(),
        Err(err) => return Err(ManagerError::io(profile_path, err)),
    };
    let block = format!(
        "{HERMES_PROFILE_BEGIN}\n{}\n{HERMES_PROFILE_END}\n",
        shell_profile_hint(plan)
    );
    let next = replace_managed_block(&existing, &block);
    if let Some(parent) = profile_path.parent() {
        fs::create_dir_all(parent).map_err(|err| ManagerError::io(parent, err))?;
    }
    fs::write(profile_path, next).map_err(|err| ManagerError::io(profile_path, err))
}

/// Read the current user's Windows PATH registry value.
#[cfg(target_os = "windows")]
pub fn read_windows_user_path() -> Result<Option<String>> {
    use winreg::enums::HKEY_CURRENT_USER;
    use winreg::RegKey;

    let hkcu = RegKey::predef(HKEY_CURRENT_USER);
    let environment = match hkcu.open_subkey("Environment") {
        Ok(key) => key,
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(err) => return Err(ManagerError::io("HKCU\\Environment", err)),
    };
    match environment.get_value::<String, _>("Path") {
        Ok(value) => Ok(Some(value)),
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => {
            match environment.get_value::<String, _>("PATH") {
                Ok(value) => Ok(Some(value)),
                Err(err) if err.kind() == std::io::ErrorKind::NotFound => Ok(None),
                Err(err) => Err(ManagerError::io("HKCU\\Environment\\PATH", err)),
            }
        }
        Err(err) => Err(ManagerError::io("HKCU\\Environment\\Path", err)),
    }
}

/// Return no registry PATH off Windows.
#[cfg(not(target_os = "windows"))]
pub fn read_windows_user_path() -> Result<Option<String>> {
    Ok(None)
}

/// Write the planned PATH value to the current user's Windows environment.
#[cfg(target_os = "windows")]
pub fn write_windows_user_path_update(plan: &PathUpdatePlan) -> Result<bool> {
    if !plan.changed {
        return Ok(false);
    }

    use winreg::enums::HKEY_CURRENT_USER;
    use winreg::RegKey;

    let hkcu = RegKey::predef(HKEY_CURRENT_USER);
    let (environment, _) = hkcu
        .create_subkey("Environment")
        .map_err(|err| ManagerError::io("HKCU\\Environment", err))?;
    environment
        .set_value("Path", &plan.next_path)
        .map_err(|err| ManagerError::io("HKCU\\Environment\\Path", err))?;
    broadcast_windows_environment_change();
    Ok(true)
}

/// Return an actionable error on non-Windows platforms.
#[cfg(not(target_os = "windows"))]
pub fn write_windows_user_path_update(_plan: &PathUpdatePlan) -> Result<bool> {
    Err(ManagerError::InvalidManifest(
        "write-user-path is only supported on Windows".to_string(),
    ))
}

#[cfg(target_os = "windows")]
fn broadcast_windows_environment_change() {
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        SendMessageTimeoutW, HWND_BROADCAST, SMTO_ABORTIFHUNG, WM_SETTINGCHANGE,
    };

    let environment = "Environment\0".encode_utf16().collect::<Vec<_>>();
    unsafe {
        SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            environment.as_ptr() as isize,
            SMTO_ABORTIFHUNG,
            5000,
            std::ptr::null_mut(),
        );
    }
}

fn replace_managed_block(existing: &str, block: &str) -> String {
    if let Some(begin) = existing.find(HERMES_PROFILE_BEGIN) {
        if let Some(end_offset) = existing[begin..].find(HERMES_PROFILE_END) {
            let end = begin + end_offset + HERMES_PROFILE_END.len();
            let mut next = String::new();
            next.push_str(existing[..begin].trim_end_matches(['\r', '\n']));
            if !next.is_empty() {
                next.push('\n');
            }
            next.push_str(block);
            let suffix = existing[end..].trim_start_matches(['\r', '\n']);
            if !suffix.is_empty() {
                next.push_str(suffix);
                if !next.ends_with('\n') {
                    next.push('\n');
                }
            }
            return next;
        }
    }

    let mut next = existing.trim_end_matches(['\r', '\n']).to_string();
    if !next.is_empty() {
        next.push_str("\n\n");
    }
    next.push_str(block);
    next
}

fn split_path_like(value: &str, delimiter: char) -> Vec<String> {
    value
        .split(delimiter)
        .filter(|part| !part.trim().is_empty())
        .map(str::to_string)
        .collect()
}

fn path_eq_for_platform(left: &str, right: &Path, windows: bool) -> bool {
    let right = right.display().to_string();
    if windows {
        left.eq_ignore_ascii_case(&right)
    } else {
        left == right
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn path_plan_prepends_hermes_bin_once() {
        let install_root = PathBuf::from("C:/Users/example/hermes/hermes-agent");
        let hermes_bin = install_root.join("venv").join("Scripts");
        let plan = plan_path_update(
            &install_root,
            Some(format!("{};C:/Windows/System32", hermes_bin.display())),
            true,
        );

        assert_eq!(plan.hermes_bin, hermes_bin);
        assert_eq!(plan.changed, false);
        assert_eq!(
            plan.next_path,
            format!("{};C:/Windows/System32", plan.hermes_bin.display())
        );
    }

    #[test]
    fn path_plan_prepends_missing_hermes_bin() {
        let install_root = PathBuf::from("/home/user/.hermes/hermes-agent");
        let plan = plan_path_update(&install_root, Some("/usr/bin:/bin".to_string()), false);

        assert_eq!(plan.hermes_bin, install_root.join("venv").join("bin"));
        assert_eq!(plan.changed, true);
        assert_eq!(
            plan.next_path,
            format!("{}:/usr/bin:/bin", plan.hermes_bin.display())
        );
    }

    #[test]
    fn shell_profile_hint_uses_export_line_for_unix() {
        let plan = PathUpdatePlan {
            hermes_bin: PathBuf::from("/home/user/.hermes/hermes-agent/venv/bin"),
            changed: true,
            next_path: String::new(),
        };

        let hint = shell_profile_hint(&plan);

        assert!(hint.contains("export PATH=\"/home/user/.hermes/hermes-agent/venv/bin:$PATH\""));
    }

    #[test]
    fn write_shell_profile_update_appends_managed_block_once() {
        let dir = tempfile::tempdir().expect("tempdir should be created");
        let profile = dir.path().join(".bashrc");
        std::fs::write(&profile, "alias ll='ls -la'\n").unwrap();
        let plan = PathUpdatePlan {
            hermes_bin: PathBuf::from("/home/user/.hermes/hermes-agent/venv/bin"),
            changed: true,
            next_path: String::new(),
        };

        write_shell_profile_update(&profile, &plan).unwrap();
        write_shell_profile_update(&profile, &plan).unwrap();

        let text = std::fs::read_to_string(&profile).unwrap();
        assert_eq!(text.matches(HERMES_PROFILE_BEGIN).count(), 1);
        assert!(text.contains("alias ll='ls -la'"));
        assert!(text.contains("export PATH=\"/home/user/.hermes/hermes-agent/venv/bin:$PATH\""));
    }

    #[test]
    fn write_shell_profile_update_replaces_existing_managed_block() {
        let dir = tempfile::tempdir().expect("tempdir should be created");
        let profile = dir.path().join(".zshrc");
        std::fs::write(
            &profile,
            format!("{HERMES_PROFILE_BEGIN}\nold\n{HERMES_PROFILE_END}\n"),
        )
        .unwrap();
        let plan = PathUpdatePlan {
            hermes_bin: PathBuf::from("/new/hermes/bin"),
            changed: true,
            next_path: String::new(),
        };

        write_shell_profile_update(&profile, &plan).unwrap();

        let text = std::fs::read_to_string(&profile).unwrap();
        assert!(!text.contains("old"));
        assert!(text.contains("export PATH=\"/new/hermes/bin:$PATH\""));
    }

    #[test]
    #[cfg(not(target_os = "windows"))]
    fn windows_user_path_write_reports_unsupported_off_windows() {
        let plan = PathUpdatePlan {
            hermes_bin: PathBuf::from("/home/user/.hermes/hermes-agent/venv/bin"),
            changed: true,
            next_path: String::new(),
        };

        let err = write_windows_user_path_update(&plan).unwrap_err();

        assert!(err.to_string().contains("only supported on Windows"));
    }
}
