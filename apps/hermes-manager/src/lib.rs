//! Library modules for the Hermes install manager.

pub mod bundled_manifest;
pub mod commands;
pub mod error;
pub mod installed_manifest;
pub mod ownership;
pub mod platform;
pub mod paths;

pub use error::{ManagerError, Result};
