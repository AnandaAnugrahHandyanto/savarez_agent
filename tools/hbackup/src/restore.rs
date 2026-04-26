use std::fs::{self, File};
use std::io;
use std::path::PathBuf;

use anyhow::{Context, Result};
use indicatif::{ProgressBar, ProgressStyle};

use crate::manifest::Manifest;

pub struct RestoreOptions {
    pub archive: PathBuf,
    pub dry_run: bool,
    pub force: bool,
}

pub fn run_restore(opts: &RestoreOptions) -> Result<()> {
    let home = dirs::home_dir().context("Could not determine home directory")?;

    let file = File::open(&opts.archive)
        .with_context(|| format!("Opening archive {}", opts.archive.display()))?;
    let decoder = zstd::stream::Decoder::new(file)?;
    let mut archive = tar::Archive::new(decoder);

    let entries = archive.entries()?;
    let mut manifest: Option<Manifest> = None;
    let mut file_count: usize = 0;

    let pb = ProgressBar::new_spinner();
    pb.set_style(
        ProgressStyle::default_spinner()
            .template("{spinner:.green} {pos} files restored: {msg}")
            .unwrap(),
    );

    for entry in entries {
        let mut entry = entry?;
        let path = entry.path()?.to_path_buf();
        let path_str = path.to_string_lossy().to_string();

        // Parse manifest
        if path_str == "manifest.json" {
            let mut buf = String::new();
            io::Read::read_to_string(&mut entry, &mut buf)?;
            manifest = Some(serde_json::from_str(&buf)?);
            if let Some(ref m) = manifest {
                eprintln!(
                    "Archive: {} files, {} total, created {}",
                    m.file_count,
                    crate::backup::human_size(m.total_size_bytes),
                    m.timestamp,
                );
            }
            continue;
        }

        // Skip WAL/SHM files
        if path_str.ends_with(".db-wal") || path_str.ends_with(".db-shm") {
            continue;
        }

        let dest = home.join(&path_str);

        if opts.dry_run {
            println!("Would restore: {}", dest.display());
            file_count += 1;
            continue;
        }

        // Check existing
        if dest.exists() && !opts.force {
            eprintln!("Skipping (exists): {} (use --force to overwrite)", dest.display());
            continue;
        }

        if let Some(parent) = dest.parent() {
            fs::create_dir_all(parent)?;
        }

        let mut out = File::create(&dest)
            .with_context(|| format!("Creating {}", dest.display()))?;
        io::copy(&mut entry, &mut out)?;

        file_count += 1;
        pb.set_position(file_count as u64);
        pb.set_message(truncate(&path_str, 50));
    }

    pb.finish_with_message("done");

    if manifest.is_none() {
        eprintln!("Warning: no manifest.json found in archive");
    }

    eprintln!(
        "{} {} files",
        if opts.dry_run { "Would restore" } else { "Restored" },
        file_count,
    );

    Ok(())
}

fn truncate(s: &str, max: usize) -> String {
    if s.len() <= max {
        s.to_string()
    } else {
        format!("...{}", &s[s.len() - max + 3..])
    }
}
