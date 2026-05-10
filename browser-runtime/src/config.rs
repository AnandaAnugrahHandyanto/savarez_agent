use std::{
    net::{IpAddr, Ipv4Addr, SocketAddr},
    path::PathBuf,
    time::Duration,
};

use clap::Parser;

#[derive(Parser, Debug, Clone)]
#[command(
    name = "hermes-browser-runtime",
    about = "Local CDP-first browser runtime for agents"
)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Command,
}

#[derive(clap::Subcommand, Debug, Clone)]
pub enum Command {
    /// Run the HTTP API server.
    Server(ServerArgs),
    /// Create a browser session against a running server.
    CreateSession(ClientCreateSessionArgs),
    /// List sessions against a running server.
    Sessions(ClientArgs),
    /// List profiles against a running server.
    Profiles(ClientArgs),
}

#[derive(Parser, Debug, Clone)]
pub struct ServerArgs {
    #[arg(long, env = "HBR_BIND", default_value = "127.0.0.1:7788")]
    pub bind: SocketAddr,

    #[arg(long, env = "HBR_DATA_DIR")]
    pub data_dir: Option<PathBuf>,

    #[arg(long, env = "HBR_CHROME_PATH")]
    pub chrome_path: Option<PathBuf>,

    #[arg(long, env = "HBR_BEARER_TOKEN")]
    pub bearer_token: Option<String>,

    #[arg(long, env = "HBR_HEADFUL", default_value_t = false)]
    pub headful: bool,

    #[arg(long, env = "HBR_TAKEOVER_TTL_SECS", default_value_t = 900)]
    pub takeover_ttl_secs: u64,
}

#[derive(Parser, Debug, Clone)]
pub struct ClientArgs {
    #[arg(long, env = "HBR_SERVER", default_value = "http://127.0.0.1:7788")]
    pub server: String,

    #[arg(long, env = "HBR_BEARER_TOKEN")]
    pub bearer_token: Option<String>,
}

#[derive(Parser, Debug, Clone)]
pub struct ClientCreateSessionArgs {
    #[command(flatten)]
    pub client: ClientArgs,

    #[arg(long)]
    pub profile_id: Option<String>,

    #[arg(long, default_value_t = true)]
    pub persist_profile: bool,

    #[arg(long, default_value_t = true)]
    pub headless: bool,
}

#[derive(Debug, Clone)]
pub struct RuntimeConfig {
    pub bind: SocketAddr,
    pub data_dir: PathBuf,
    pub chrome_path: Option<PathBuf>,
    pub bearer_token: Option<String>,
    pub default_headless: bool,
    pub takeover_ttl: Duration,
}

impl RuntimeConfig {
    pub fn from_server_args(args: ServerArgs) -> Self {
        Self {
            bind: args.bind,
            data_dir: args.data_dir.unwrap_or_else(default_data_dir),
            chrome_path: args.chrome_path,
            bearer_token: args.bearer_token,
            default_headless: !args.headful,
            takeover_ttl: Duration::from_secs(args.takeover_ttl_secs),
        }
    }

    pub fn localhost_base_url(&self) -> String {
        let host = match self.bind.ip() {
            IpAddr::V4(ip) if ip == Ipv4Addr::UNSPECIFIED => "127.0.0.1".to_string(),
            IpAddr::V6(_) => format!("[{}]", self.bind.ip()),
            ip => ip.to_string(),
        };
        format!("http://{}:{}", host, self.bind.port())
    }
}

pub fn default_data_dir() -> PathBuf {
    dirs::data_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("hermes-browser-runtime")
}
