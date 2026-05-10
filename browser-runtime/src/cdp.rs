use anyhow::{Context, Result, bail};
use futures_util::{SinkExt, StreamExt};
use serde_json::{Value, json};
use tokio_tungstenite::{connect_async, tungstenite::Message};

#[derive(Debug, Clone, serde::Deserialize)]
pub struct VersionInfo {
    #[serde(rename = "webSocketDebuggerUrl")]
    pub web_socket_debugger_url: String,
}

#[derive(Debug, Clone, serde::Deserialize)]
pub struct TargetInfo {
    #[serde(default)]
    pub r#type: String,
    #[serde(default, rename = "webSocketDebuggerUrl")]
    pub web_socket_debugger_url: Option<String>,
}

pub async fn fetch_version(http_base: &str) -> Result<VersionInfo> {
    reqwest::get(format!("{http_base}/json/version"))
        .await
        .context("fetch /json/version")?
        .error_for_status()
        .context("/json/version status")?
        .json::<VersionInfo>()
        .await
        .context("parse /json/version")
}

pub async fn first_page_ws_url(http_base: &str) -> Result<String> {
    let targets = reqwest::get(format!("{http_base}/json/list"))
        .await
        .context("fetch /json/list")?
        .error_for_status()
        .context("/json/list status")?
        .json::<Vec<TargetInfo>>()
        .await
        .context("parse /json/list")?;
    targets
        .into_iter()
        .find(|target| target.r#type == "page" && target.web_socket_debugger_url.is_some())
        .and_then(|target| target.web_socket_debugger_url)
        .ok_or_else(|| anyhow::anyhow!("no page target with websocket debugger url"))
}

pub async fn open_new_page(http_base: &str, url: &str) -> Result<()> {
    reqwest::get(format!("{http_base}/json/new?{}", url))
        .await
        .context("open /json/new")?
        .error_for_status()
        .context("/json/new status")?;
    Ok(())
}

pub async fn capture_screenshot_png(http_base: &str) -> Result<Vec<u8>> {
    let ws_url = first_page_ws_url(http_base).await?;
    let response = send_page_command(
        &ws_url,
        "Page.captureScreenshot",
        json!({"format":"png","captureBeyondViewport": false}),
    )
    .await?;
    let data = response
        .get("data")
        .and_then(Value::as_str)
        .ok_or_else(|| anyhow::anyhow!("Page.captureScreenshot returned no data"))?;
    base64_decode(data)
}

pub async fn click(http_base: &str, x: f64, y: f64) -> Result<()> {
    let ws_url = first_page_ws_url(http_base).await?;
    send_page_command(
        &ws_url,
        "Input.dispatchMouseEvent",
        json!({"type":"mousePressed","x":x,"y":y,"button":"left","clickCount":1}),
    )
    .await?;
    send_page_command(
        &ws_url,
        "Input.dispatchMouseEvent",
        json!({"type":"mouseReleased","x":x,"y":y,"button":"left","clickCount":1}),
    )
    .await?;
    Ok(())
}

pub async fn insert_text(http_base: &str, text: &str) -> Result<()> {
    let ws_url = first_page_ws_url(http_base).await?;
    send_page_command(&ws_url, "Input.insertText", json!({"text": text})).await?;
    Ok(())
}

pub async fn scroll(http_base: &str, delta_x: f64, delta_y: f64) -> Result<()> {
    let ws_url = first_page_ws_url(http_base).await?;
    send_page_command(
        &ws_url,
        "Input.dispatchMouseEvent",
        json!({"type":"mouseWheel","x": 1.0,"y": 1.0,"deltaX": delta_x,"deltaY": delta_y}),
    )
    .await?;
    Ok(())
}

pub async fn browser_close(browser_ws_url: &str) -> Result<()> {
    let _ = send_command(browser_ws_url, "Browser.close", json!({})).await?;
    Ok(())
}

async fn send_page_command(ws_url: &str, method: &str, params: Value) -> Result<Value> {
    send_command(ws_url, method, params).await
}

async fn send_command(ws_url: &str, method: &str, params: Value) -> Result<Value> {
    let (mut ws, _) = connect_async(ws_url)
        .await
        .context("connect CDP websocket")?;
    let msg = json!({"id":1,"method": method,"params": params});
    ws.send(Message::Text(msg.to_string()))
        .await
        .context("send CDP command")?;
    while let Some(frame) = ws.next().await {
        let frame = frame.context("read CDP frame")?;
        let Message::Text(text) = frame else { continue };
        let value: Value = serde_json::from_str(&text).context("parse CDP frame")?;
        if value.get("id").and_then(Value::as_i64) == Some(1) {
            if let Some(error) = value.get("error") {
                bail!("CDP command failed: {error}");
            }
            return Ok(value.get("result").cloned().unwrap_or(Value::Null));
        }
    }
    bail!("CDP websocket closed before response")
}

fn base64_decode(data: &str) -> Result<Vec<u8>> {
    use base64::{Engine as _, engine::general_purpose};
    general_purpose::STANDARD
        .decode(data)
        .context("decode screenshot")
}
