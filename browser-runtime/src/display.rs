use std::{
    ffi::OsString,
    path::{Path, PathBuf},
};

pub fn headed_mode_supported(
    display: Option<OsString>,
    wayland_display: Option<OsString>,
    xvfb_run_path: Option<PathBuf>,
) -> bool {
    non_empty(display.as_ref()) || non_empty(wayland_display.as_ref()) || xvfb_run_path.is_some()
}

pub fn local_display_available(
    display: Option<OsString>,
    wayland_display: Option<OsString>,
) -> bool {
    non_empty(display.as_ref()) || non_empty(wayland_display.as_ref())
}

pub fn find_xvfb_run_path() -> Option<PathBuf> {
    xvfb_run_path_from(
        std::env::var_os("HBR_XVFB_RUN_PATH"),
        std::env::var_os("PATH"),
    )
}

pub fn xvfb_run_path_from(
    env_override: Option<OsString>,
    path_env: Option<OsString>,
) -> Option<PathBuf> {
    env_override
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
        .or_else(|| find_executable_in_path("xvfb-run", path_env))
}

fn find_executable_in_path(binary: &str, path_env: Option<OsString>) -> Option<PathBuf> {
    std::env::split_paths(&path_env?).find_map(|dir| {
        let candidate = dir.join(binary);
        executable_file(&candidate).then_some(candidate)
    })
}

fn executable_file(path: &Path) -> bool {
    let Ok(metadata) = path.metadata() else {
        return false;
    };
    if !metadata.is_file() {
        return false;
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        metadata.permissions().mode() & 0o111 != 0
    }
    #[cfg(not(unix))]
    {
        true
    }
}

fn non_empty(value: Option<&OsString>) -> bool {
    value.is_some_and(|value| !value.is_empty())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn headed_mode_accepts_local_display_wayland_or_xvfb_wrapper() {
        assert!(headed_mode_supported(
            Some(OsString::from(":99")),
            None,
            None
        ));
        assert!(headed_mode_supported(
            None,
            Some(OsString::from("wayland-0")),
            None
        ));
        assert!(headed_mode_supported(
            None,
            None,
            Some(PathBuf::from("/usr/bin/xvfb-run"))
        ));
        assert!(!headed_mode_supported(
            Some(OsString::new()),
            Some(OsString::new()),
            None
        ));
    }

    #[test]
    fn xvfb_path_prefers_explicit_env_then_executable_path() {
        let tmp = tempfile::tempdir().unwrap();
        let xvfb = tmp.path().join("xvfb-run");
        fs::write(&xvfb, b"#!/bin/sh\n").unwrap();
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mut perms = fs::metadata(&xvfb).unwrap().permissions();
            perms.set_mode(0o755);
            fs::set_permissions(&xvfb, perms).unwrap();
        }

        assert_eq!(
            xvfb_run_path_from(Some(OsString::from("/custom/xvfb-run")), None),
            Some(PathBuf::from("/custom/xvfb-run"))
        );
        assert_eq!(
            xvfb_run_path_from(None, Some(tmp.path().as_os_str().to_os_string())),
            Some(xvfb)
        );
        assert_eq!(xvfb_run_path_from(None, Some(OsString::new())), None);
    }
}
