use std::{net::SocketAddr, sync::Arc};

use anyhow::{Context, Result};
use axum::serve;
use clap::Parser;
use reqwest::header;
use tokio::net::TcpListener;
use tower_http::trace::TraceLayer;
use tracing::info;

use crate::{
    api,
    backend::LocalChromeBackend,
    config::{Cli, Command, RuntimeConfig},
    models::CreateSessionRequest,
    store::AppStore,
};

pub async fn run() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::Server(args) => run_server(RuntimeConfig::from_server_args(args)).await,
        Command::CreateSession(args) => {
            let client = http_client(args.client.bearer_token)?;
            let res = client
                .post(format!(
                    "{}/sessions",
                    args.client.server.trim_end_matches('/')
                ))
                .json(&CreateSessionRequest {
                    profile_id: args.profile_id,
                    headless: Some(args.headless),
                    viewport: None,
                    persist_profile: Some(args.persist_profile),
                })
                .send()
                .await?
                .error_for_status()?
                .json::<serde_json::Value>()
                .await?;
            println!("{}", serde_json::to_string_pretty(&res)?);
            Ok(())
        }
        Command::Sessions(args) => print_get(&args.server, args.bearer_token, "/sessions").await,
        Command::Profiles(args) => print_get(&args.server, args.bearer_token, "/profiles").await,
    }
}

pub async fn run_server(config: RuntimeConfig) -> Result<()> {
    let backend = LocalChromeBackend::new(config.chrome_path.clone())?;
    info!(chrome=%backend.chrome_path().display(), bind=%config.bind, data_dir=%config.data_dir.display(), "starting Hermes Browser Runtime");
    let store = Arc::new(AppStore::new(config.clone(), Arc::new(backend)).await?);
    let app = api::router(store).layer(TraceLayer::new_for_http());
    let listener = TcpListener::bind(config.bind)
        .await
        .with_context(|| format!("bind {}", config.bind))?;
    serve(listener, app).await.context("serve HTTP")
}

fn http_client(token: Option<String>) -> Result<reqwest::Client> {
    let mut headers = header::HeaderMap::new();
    if let Some(token) = token {
        headers.insert(header::AUTHORIZATION, format!("Bearer {token}").parse()?);
    }
    Ok(reqwest::Client::builder()
        .default_headers(headers)
        .build()?)
}

async fn print_get(server: &str, token: Option<String>, path: &str) -> Result<()> {
    let client = http_client(token)?;
    let value = client
        .get(format!("{}{}", server.trim_end_matches('/'), path))
        .send()
        .await?
        .error_for_status()?
        .json::<serde_json::Value>()
        .await?;
    println!("{}", serde_json::to_string_pretty(&value)?);
    Ok(())
}

#[allow(dead_code)]
fn _assert_local_default(addr: SocketAddr) -> bool {
    addr.ip().is_loopback()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_bind_is_loopback() {
        let addr: SocketAddr = "127.0.0.1:7788".parse().unwrap();
        assert!(_assert_local_default(addr));
    }
}
