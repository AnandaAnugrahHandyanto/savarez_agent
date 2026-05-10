use std::{
    fs,
    net::TcpListener,
    path::{Path, PathBuf},
    process::Stdio,
    time::Duration,
};

use anyhow::{Context, Result, bail};
use async_trait::async_trait;
use tokio::{
    process::{Child, Command},
    time::{Instant, sleep},
};
use tracing::{debug, info};
use uuid::Uuid;

use crate::{cdp, models::Viewport};

#[derive(Debug, Clone)]
pub struct StartSessionOptions {
    pub id: Uuid,
    pub user_data_dir: PathBuf,
    pub downloads_dir: PathBuf,
    pub headless: bool,
    pub viewport: Viewport,
    pub launch_timeout: Duration,
}

#[derive(Debug)]
pub struct LaunchedBrowser {
    pub process: Child,
    pub port: u16,
    pub http_base: String,
    pub cdp_ws_url: String,
}

#[async_trait]
pub trait BrowserBackend: Send + Sync + 'static {
    async fn launch(&self, options: StartSessionOptions) -> Result<LaunchedBrowser>;
    async fn close(&self, launched: &mut LaunchedBrowser) -> Result<()>;
}

#[derive(Debug, Clone)]
pub struct LocalChromeBackend {
    chrome_path: PathBuf,
}

impl LocalChromeBackend {
    pub fn new(chrome_path: Option<PathBuf>) -> Result<Self> {
        let chrome_path = chrome_path
            .or_else(|| std::env::var_os("HBR_CHROME_PATH").map(PathBuf::from))
            .or_else(find_chrome_path)
            .ok_or_else(|| {
                anyhow::anyhow!(
                    "Chrome/Chromium not found. Set HBR_CHROME_PATH or install Chrome/Chromium."
                )
            })?;
        Ok(Self { chrome_path })
    }

    pub fn chrome_path(&self) -> &Path {
        &self.chrome_path
    }
}

#[async_trait]
impl BrowserBackend for LocalChromeBackend {
    async fn launch(&self, options: StartSessionOptions) -> Result<LaunchedBrowser> {
        fs::create_dir_all(&options.user_data_dir).context("create user data dir")?;
        fs::create_dir_all(&options.downloads_dir).context("create downloads dir")?;
        let port = free_local_port()?;
        let http_base = format!("http://127.0.0.1:{port}");
        let mut command = Command::new(&self.chrome_path);
        command
            .arg(format!("--remote-debugging-port={port}"))
            .arg(format!(
                "--user-data-dir={}",
                options.user_data_dir.display()
            ))
            .arg("--no-first-run")
            .arg("--no-default-browser-check")
            .arg("--disable-background-networking")
            .arg("--disable-sync")
            .arg("--disable-extensions")
            .arg("--disable-dev-shm-usage")
            .arg(format!(
                "--window-size={},{}",
                options.viewport.width, options.viewport.height
            ))
            .arg(format!(
                "--download-default-directory={}",
                options.downloads_dir.display()
            ))
            .arg("about:blank")
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        if options.headless {
            command.arg("--headless=new").arg("--disable-gpu");
        }
        if std::env::var_os("HBR_CHROME_NO_SANDBOX").is_some() {
            command.arg("--no-sandbox");
        }
        info!(session_id=%options.id, chrome=%self.chrome_path.display(), port, "launching local chrome");
        let mut process = command.spawn().context("spawn Chrome")?;
        let started = Instant::now();
        loop {
            if let Some(status) = process.try_wait().context("poll Chrome process")? {
                bail!("Chrome exited before CDP became ready: {status}");
            }
            match cdp::fetch_version(&http_base).await {
                Ok(version) => {
                    debug!(session_id=%options.id, "CDP ready");
                    let _ = cdp::open_new_page(&http_base, "about:blank").await;
                    return Ok(LaunchedBrowser {
                        process,
                        port,
                        http_base,
                        cdp_ws_url: version.web_socket_debugger_url,
                    });
                }
                Err(err) if started.elapsed() < options.launch_timeout => {
                    debug!(session_id=%options.id, error=%err, "waiting for CDP");
                    sleep(Duration::from_millis(150)).await;
                }
                Err(err) => {
                    let _ = process.start_kill();
                    bail!(
                        "Chrome CDP did not become ready within {:?}: {err}",
                        options.launch_timeout
                    );
                }
            }
        }
    }

    async fn close(&self, launched: &mut LaunchedBrowser) -> Result<()> {
        let _ = cdp::browser_close(&launched.cdp_ws_url).await;
        match tokio::time::timeout(Duration::from_secs(5), launched.process.wait()).await {
            Ok(Ok(_status)) => Ok(()),
            _ => {
                let _ = launched.process.start_kill();
                let _ = launched.process.wait().await;
                Ok(())
            }
        }
    }
}

fn free_local_port() -> Result<u16> {
    let listener = TcpListener::bind(("127.0.0.1", 0)).context("bind ephemeral port")?;
    Ok(listener.local_addr()?.port())
}

fn find_chrome_path() -> Option<PathBuf> {
    let candidates = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/opt/google/chrome/chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
        "/usr/bin/brave-browser",
        "/opt/brave.com/brave/brave-browser",
    ];
    candidates
        .iter()
        .map(PathBuf::from)
        .find(|path| path.exists())
        .or_else(find_playwright_chromium)
}

fn find_playwright_chromium() -> Option<PathBuf> {
    let base = dirs::home_dir()?.join(".cache/ms-playwright");
    let entries = fs::read_dir(base).ok()?;
    let mut matches: Vec<PathBuf> = entries
        .flatten()
        .flat_map(|entry| {
            let root = entry.path();
            [
                root.join("chrome-linux/chrome"),
                root.join("chrome-linux64/chrome"),
                root.join("chrome-headless-shell-linux64/chrome-headless-shell"),
            ]
        })
        .filter(|path| path.exists())
        .collect();
    matches.sort();
    matches.pop()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn finds_a_free_local_port() {
        let port = free_local_port().unwrap();
        assert!(port > 0);
    }
}
