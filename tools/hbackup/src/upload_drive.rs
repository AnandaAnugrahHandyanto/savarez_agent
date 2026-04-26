use std::path::Path;
use std::process::{Command, Stdio};

use anyhow::{Context, Result};
use indicatif::{ProgressBar, ProgressStyle};

/// Upload a backup archive to Google Drive via rclone.
/// If rclone is not installed, prints setup instructions.
pub fn upload_to_drive(archive: &Path, remote_name: &str, folder: &str) -> Result<()> {
    // Check rclone is installed
    let rclone_check = Command::new("which")
        .arg("rclone")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status();

    if rclone_check.map(|s| !s.success()).unwrap_or(true) {
        print_rclone_setup_instructions();
        anyhow::bail!("rclone is not installed");
    }

    // Check remote is configured
    let remote_check = Command::new("rclone")
        .args(["listremotes"])
        .output()
        .context("Running rclone listremotes")?;

    let remotes = String::from_utf8_lossy(&remote_check.stdout);
    let full_remote = format!("{}:", remote_name);
    if !remotes.contains(&full_remote) {
        eprintln!(
            "rclone remote '{}' not found. Configured remotes:\n{}",
            remote_name, remotes
        );
        eprintln!("\nTo configure Google Drive, run:");
        eprintln!("  rclone config");
        eprintln!("  # Select 'n' for new remote, name it '{}', choose 'Google Drive'", remote_name);
        anyhow::bail!("rclone remote '{}' not configured", remote_name);
    }

    // Build destination path
    let dest = if folder.is_empty() {
        format!("{}:", remote_name)
    } else {
        format!("{}:{}", remote_name, folder)
    };

    eprintln!("Uploading {} to Google Drive ({})", archive.display(), dest);

    // Run rclone copyto with progress
    let pb = ProgressBar::new_spinner();
    pb.set_style(
        ProgressStyle::default_spinner()
            .template("{spinner:.green} Uploading to Google Drive... {msg}")
            .unwrap(),
    );
    pb.enable_steady_tick(std::time::Duration::from_millis(100));

    let status = Command::new("rclone")
        .args([
            "copyto",
            "--progress",
            "--transfers",
            "4",
            archive.to_str().unwrap(),
            &format!("{}/{}", dest, archive.file_name().unwrap().to_string_lossy()),
        ])
        .status()
        .context("Running rclone copyto")?;

    pb.finish_and_clear();

    if !status.success() {
        anyhow::bail!("rclone exited with status {}", status);
    }

    eprintln!("Upload to Google Drive complete.");
    Ok(())
}

fn print_rclone_setup_instructions() {
    eprintln!("╔══════════════════════════════════════════════════════════════════╗");
    eprintln!("║  rclone is not installed. Google Drive upload requires rclone.   ║");
    eprintln!("╠══════════════════════════════════════════════════════════════════╣");
    eprintln!("║  Install rclone:                                                 ║");
    eprintln!("║    curl https://rclone.org/install.sh | sudo bash                ║");
    eprintln!("║                                                                  ║");
    eprintln!("║  Or on macOS:                                                    ║");
    eprintln!("║    brew install rclone                                           ║");
    eprintln!("║                                                                  ║");
    eprintln!("║  Then configure Google Drive:                                    ║");
    eprintln!("║    rclone config                                                 ║");
    eprintln!("║    # Select 'n' for new remote                                   ║");
    eprintln!("║    # Name it 'gdrive' (or your preferred name)                   ║");
    eprintln!("║    # Choose 'Google Drive' (option 18)                           ║");
    eprintln!("║    # Leave client_id and client_secret blank for default         ║");
    eprintln!("║    # Choose '1' for full access                                  ║");
    eprintln!("║    # Follow the OAuth2 browser flow                              ║");
    eprintln!("╚══════════════════════════════════════════════════════════════════╝");
}

/// Print setup instructions for hbackup + Google Drive
pub fn print_drive_setup_guide() {
    eprintln!("╔══════════════════════════════════════════════════════════════════╗");
    eprintln!("║           hbackup Google Drive Setup Guide                       ║");
    eprintln!("╠══════════════════════════════════════════════════════════════════╣");
    eprintln!("║  1. Install rclone:                                              ║");
    eprintln!("║       curl https://rclone.org/install.sh | sudo bash             ║");
    eprintln!("║                                                                  ║");
    eprintln!("║  2. Configure Google Drive remote:                               ║");
    eprintln!("║       rclone config                                              ║");
    eprintln!("║       # Name: gdrive                                             ║");
    eprintln!("║       # Storage: Google Drive                                    ║");
    eprintln!("║       # Follow OAuth2 flow in browser                            ║");
    eprintln!("║                                                                  ║");
    eprintln!("║  3. Verify:                                                      ║");
    eprintln!("║       rclone listremotes                                         ║");
    eprintln!("║       rclone ls gdrive:                                          ║");
    eprintln!("║                                                                  ║");
    eprintln!("║  4. Upload a backup:                                             ║");
    eprintln!("║       hbackup upload --drive <archive.tar.zst>                   ║");
    eprintln!("║                                                                  ║");
    eprintln!("║  5. Or use auto backup + upload:                                 ║");
    eprintln!("║       hbackup auto                                               ║");
    eprintln!("║       # (requires upload.destination in config.toml)             ║");
    eprintln!("╚══════════════════════════════════════════════════════════════════╝");
}
