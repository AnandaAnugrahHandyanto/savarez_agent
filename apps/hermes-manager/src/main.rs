//! Command-line entrypoint for the Hermes install manager.

use std::path::PathBuf;

use clap::{Parser, Subcommand};
use serde::Serialize;

/// Manage Hermes runtime installation resources.
#[derive(Debug, Parser)]
#[command(name = "hermes-manager")]
#[command(about = "Hermes install, repair, and uninstall manager")]
struct Cli {
    /// Override Hermes home for tests or isolated installs.
    #[arg(long)]
    hermes_home: Option<PathBuf>,

    /// Optional bundled manifest path to validate.
    #[arg(long)]
    manifest: Option<PathBuf>,

    /// Emit machine-readable JSON for cleanup commands.
    #[arg(long)]
    json: bool,

    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Print the manager version.
    Version,
    /// Print resolved manager paths.
    Doctor,
    /// Create manager state and initial install metadata.
    InstallMetadata,
    /// Remove paths recorded in the installed-files manifest.
    UninstallLite {
        /// Report paths that would be removed without deleting them.
        #[arg(long)]
        dry_run: bool,
    },
    /// Remove runtime checkout state so launch can repair it.
    RepairClean {
        /// Report paths that would be removed without deleting them.
        #[arg(long)]
        dry_run: bool,
    },
}

#[derive(Debug, Serialize)]
struct CommandReport {
    ok: bool,
    command: &'static str,
    #[serde(rename = "dryRun")]
    dry_run: bool,
    paths: Vec<String>,
}

fn main() {
    if let Err(err) = run() {
        eprintln!("{err}");
        std::process::exit(1);
    }
}

fn run() -> hermes_manager::Result<()> {
    let cli = Cli::parse();
    let home = hermes_manager::paths::hermes_home(cli.hermes_home);

    match cli.command {
        Command::Version => {
            println!("{}", env!("CARGO_PKG_VERSION"));
        }
        Command::Doctor => {
            for line in hermes_manager::commands::doctor(&home) {
                println!("{line}");
            }
            if let Some(manifest_path) = cli.manifest.as_deref() {
                match hermes_manager::bundled_manifest::BundledManifest::read(manifest_path) {
                    Ok(manifest) => {
                        let manifest_root = manifest_path.parent().unwrap_or_else(|| ".".as_ref());
                        manifest.verify_resources(manifest_root)?;
                        println!("bundled_manifest=ok");
                        println!(
                            "bundled_manifest_hermes_version={}",
                            manifest.hermes_version
                        );
                        println!("bundled_manifest_resources=ok");
                    }
                    Err(err) => {
                        eprintln!("bundled_manifest=error: {err}");
                        std::process::exit(2);
                    }
                }
            }
        }
        Command::InstallMetadata => {
            hermes_manager::commands::install_metadata(&home)?;
            println!("install_metadata=ok");
        }
        Command::UninstallLite { dry_run } => {
            let paths = if dry_run {
                hermes_manager::commands::uninstall_lite_plan(&home)?
            } else {
                hermes_manager::commands::uninstall_lite(&home)?
            };
            if cli.json {
                print_json_report(CommandReport {
                    ok: true,
                    command: "uninstall-lite",
                    dry_run,
                    paths,
                })?;
            } else {
                let prefix = if dry_run { "would_remove" } else { "removed" };
                for path in paths {
                    println!("{prefix}={path}");
                }
                println!("uninstall_lite=ok");
            }
        }
        Command::RepairClean { dry_run } => {
            let paths = if dry_run {
                hermes_manager::commands::repair_clean_plan(&home)?
            } else {
                hermes_manager::commands::repair_clean(&home)?
            };
            if cli.json {
                print_json_report(CommandReport {
                    ok: true,
                    command: "repair-clean",
                    dry_run,
                    paths,
                })?;
            } else {
                let prefix = if dry_run { "would_remove" } else { "removed" };
                for path in paths {
                    println!("{prefix}={path}");
                }
                println!("repair_clean=ok");
            }
        }
    }

    Ok(())
}

fn print_json_report(report: CommandReport) -> hermes_manager::Result<()> {
    let text = serde_json::to_string_pretty(&report)
        .map_err(|err| hermes_manager::ManagerError::InvalidManifest(err.to_string()))?;
    println!("{text}");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn command_report_serializes_machine_readable_cleanup_result() {
        let report = CommandReport {
            ok: true,
            command: "uninstall-lite",
            dry_run: true,
            paths: vec!["/tmp/hermes/hermes-agent".to_string()],
        };

        let value = serde_json::to_value(report).expect("report should serialize");

        assert_eq!(value["ok"], true);
        assert_eq!(value["command"], "uninstall-lite");
        assert_eq!(value["dryRun"], true);
        assert_eq!(value["paths"][0], "/tmp/hermes/hermes-agent");
    }
}
