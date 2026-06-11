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
    /// Plan PATH changes needed to expose the Hermes command.
    PlanPath {
        /// Override install root; defaults to HERMES_HOME/hermes-agent.
        #[arg(long)]
        install_root: Option<PathBuf>,
        /// Current user PATH value to plan from; defaults to HKCU Environment Path.
        #[arg(long)]
        current_path: Option<String>,
        /// Plan using Windows PATH conventions.
        #[arg(long, conflicts_with = "unix")]
        windows: bool,
        /// Plan using Unix PATH conventions.
        #[arg(long, conflicts_with = "windows")]
        unix: bool,
    },
    /// Write an idempotent Hermes PATH block to a shell profile file.
    WriteProfileHint {
        /// Shell profile path to update.
        #[arg(long)]
        profile: PathBuf,
        /// Override install root; defaults to HERMES_HOME/hermes-agent.
        #[arg(long)]
        install_root: Option<PathBuf>,
        /// Do not write the profile; only report what would happen.
        #[arg(long)]
        dry_run: bool,
    },
    /// Write Hermes to the current user's Windows PATH.
    WriteUserPath {
        /// Override install root; defaults to HERMES_HOME/hermes-agent.
        #[arg(long)]
        install_root: Option<PathBuf>,
        /// Current PATH value to plan from; defaults to the process PATH.
        #[arg(long)]
        current_path: Option<String>,
        /// Do not write the registry; only report what would happen.
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

#[derive(Debug, Serialize)]
struct ProfileReport {
    ok: bool,
    command: &'static str,
    #[serde(rename = "dryRun")]
    dry_run: bool,
    profile: String,
    #[serde(rename = "hermesBin")]
    hermes_bin: String,
    changed: bool,
}

#[derive(Debug, Serialize)]
struct PathApplyReport {
    ok: bool,
    command: &'static str,
    #[serde(rename = "dryRun")]
    dry_run: bool,
    target: String,
    #[serde(rename = "hermesBin")]
    hermes_bin: String,
    changed: bool,
    applied: bool,
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
        Command::PlanPath {
            install_root,
            current_path,
            windows,
            unix,
        } => {
            let install_root = install_root.unwrap_or_else(|| hermes_manager::paths::agent_root(&home));
            let current_path = current_path.or_else(|| std::env::var("PATH").ok());
            let use_windows = if windows {
                true
            } else if unix {
                false
            } else {
                cfg!(target_os = "windows")
            };
            let plan =
                hermes_manager::platform::plan_path_update(&install_root, current_path, use_windows);
            if cli.json {
                let text = serde_json::to_string_pretty(&plan)
                    .map_err(|err| hermes_manager::ManagerError::InvalidManifest(err.to_string()))?;
                println!("{text}");
            } else {
                println!("hermes_bin={}", plan.hermes_bin.display());
                println!("path_changed={}", plan.changed);
                println!("next_path={}", plan.next_path);
                if !use_windows {
                    println!("profile_hint={}", hermes_manager::platform::shell_profile_hint(&plan));
                }
            }
        }
        Command::WriteProfileHint {
            profile,
            install_root,
            dry_run,
        } => {
            let install_root =
                install_root.unwrap_or_else(|| hermes_manager::paths::agent_root(&home));
            let current_path = std::env::var("PATH").ok();
            let plan = hermes_manager::platform::plan_path_update(&install_root, current_path, false);
            if !dry_run {
                hermes_manager::platform::write_shell_profile_update(&profile, &plan)?;
            }
            if cli.json {
                let text = serde_json::to_string_pretty(&ProfileReport {
                    ok: true,
                    command: "write-profile-hint",
                    dry_run,
                    profile: profile.display().to_string(),
                    hermes_bin: plan.hermes_bin.display().to_string(),
                    changed: true,
                })
                .map_err(|err| hermes_manager::ManagerError::InvalidManifest(err.to_string()))?;
                println!("{text}");
            } else {
                let action = if dry_run { "would_update" } else { "updated" };
                println!("{action}={}", profile.display());
                println!("profile_hint={}", hermes_manager::platform::shell_profile_hint(&plan));
            }
        }
        Command::WriteUserPath {
            install_root,
            current_path,
            dry_run,
        } => {
            let install_root =
                install_root.unwrap_or_else(|| hermes_manager::paths::agent_root(&home));
            let current_path = match current_path {
                Some(value) => Some(value),
                None => hermes_manager::platform::read_windows_user_path()?,
            };
            let plan = hermes_manager::platform::plan_path_update(&install_root, current_path, true);
            let applied = if dry_run {
                false
            } else {
                hermes_manager::platform::write_windows_user_path_update(&plan)?
            };
            if cli.json {
                let text = serde_json::to_string_pretty(&PathApplyReport {
                    ok: true,
                    command: "write-user-path",
                    dry_run,
                    target: "user".to_string(),
                    hermes_bin: plan.hermes_bin.display().to_string(),
                    changed: plan.changed,
                    applied,
                })
                .map_err(|err| hermes_manager::ManagerError::InvalidManifest(err.to_string()))?;
                println!("{text}");
            } else {
                let action = if dry_run {
                    "would_update_user_path"
                } else if applied {
                    "updated_user_path"
                } else {
                    "user_path_unchanged"
                };
                println!("{action}=Path");
                println!("hermes_bin={}", plan.hermes_bin.display());
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

    #[test]
    fn path_apply_report_serializes_machine_readable_result() {
        let report = PathApplyReport {
            ok: true,
            command: "write-user-path",
            dry_run: true,
            target: "user".to_string(),
            hermes_bin: "C:/Users/example/hermes/hermes-agent/venv/Scripts".to_string(),
            changed: true,
            applied: false,
        };

        let value = serde_json::to_value(report).expect("report should serialize");

        assert_eq!(value["ok"], true);
        assert_eq!(value["command"], "write-user-path");
        assert_eq!(value["dryRun"], true);
        assert_eq!(value["target"], "user");
        assert_eq!(
            value["hermesBin"],
            "C:/Users/example/hermes/hermes-agent/venv/Scripts"
        );
        assert_eq!(value["changed"], true);
        assert_eq!(value["applied"], false);
    }
}
