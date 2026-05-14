use std::collections::VecDeque;

use anyhow::{Context, Result, bail};
use futures_util::{SinkExt, StreamExt};
use serde_json::{Value, json};
use tokio::task::JoinHandle;
use tokio_tungstenite::{WebSocketStream, connect_async, tungstenite::Message};
use tracing::warn;

use crate::models::{BrowserPersona, ResolvedBrowserIdentity};

#[derive(Debug, Clone, serde::Deserialize)]
pub struct VersionInfo {
    #[serde(rename = "webSocketDebuggerUrl")]
    pub web_socket_debugger_url: String,
    #[serde(default, rename = "User-Agent")]
    pub user_agent: Option<String>,
}

#[derive(Debug, Clone, serde::Deserialize)]
pub struct TargetInfo {
    #[serde(default)]
    pub r#type: String,
    #[serde(default, rename = "webSocketDebuggerUrl")]
    pub web_socket_debugger_url: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct PendingAttachment {
    session_id: String,
    target_type: String,
    waiting_for_debugger: bool,
}

const AUTOMATION_GLOBAL_DENYLIST: &[&str] = &[
    "webdriver",
    "domAutomation",
    "domAutomationController",
    "_WEBDRIVER_ELEM_CACHE",
    "ChromeDriverw",
    "__webdriver_script_fn",
    "__webdriver_script_func",
    "__webdriver_script_function",
    "__webdriver_evaluate",
    "__selenium_evaluate",
    "__driver_evaluate",
    "__fxdriver_evaluate",
    "__webdriver_unwrapped",
    "__webdriver_unwrapped_result",
    "$chrome_asyncScriptInfo",
    "calledSelenium",
    "callSelenium",
    "_selenium",
    "cdc_adoQpoasnfa76pfcZLmcfl_Array",
    "cdc_adoQpoasnfa76pfcZLmcfl_Promise",
    "cdc_adoQpoasnfa76pfcZLmcfl_Symbol",
];

const AUTOMATION_GLOBAL_PREFIX_DENYLIST: &[&str] = &[
    "cdc_",
    "wdc_",
    "__webdriver",
    "__selenium",
    "__driver",
    "__fxdriver",
];

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

pub async fn page_ws_urls(http_base: &str) -> Result<Vec<String>> {
    let targets = reqwest::get(format!("{http_base}/json/list"))
        .await
        .context("fetch /json/list")?
        .error_for_status()
        .context("/json/list status")?
        .json::<Vec<TargetInfo>>()
        .await
        .context("parse /json/list")?;
    let urls = targets
        .into_iter()
        .filter(|target| target.r#type == "page")
        .filter_map(|target| target.web_socket_debugger_url)
        .collect::<Vec<_>>();
    if urls.is_empty() {
        bail!("no page target with websocket debugger url");
    }
    Ok(urls)
}

pub async fn first_page_ws_url(http_base: &str) -> Result<String> {
    page_ws_urls(http_base)
        .await?
        .into_iter()
        .next()
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

pub async fn navigate(http_base: &str, url: &str) -> Result<()> {
    let ws_url = first_page_ws_url(http_base).await?;
    send_page_command(&ws_url, "Page.navigate", json!({"url": url})).await?;
    Ok(())
}

pub async fn evaluate_json(http_base: &str, expression: &str) -> Result<Value> {
    let ws_url = first_page_ws_url(http_base).await?;
    let response = send_page_command(
        &ws_url,
        "Runtime.evaluate",
        json!({
            "expression": expression,
            "awaitPromise": true,
            "returnByValue": true,
            "userGesture": true,
        }),
    )
    .await?;
    if let Some(exception) = response.get("exceptionDetails") {
        bail!("Runtime.evaluate failed: {exception}");
    }
    Ok(response
        .get("result")
        .and_then(|result| result.get("value"))
        .cloned()
        .unwrap_or(Value::Null))
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CredentialFieldContext {
    pub observed_origin: String,
    pub username_present: bool,
    pub username_usable: bool,
    pub password_present: bool,
    pub password_usable: bool,
    pub top_frame: bool,
    pub same_origin_frame: bool,
    pub unsafe_reason: Option<String>,
}

impl CredentialFieldContext {
    pub fn has_requested_fields(
        &self,
        username_selector: Option<&str>,
        password_selector: Option<&str>,
    ) -> bool {
        if username_selector.is_none() && password_selector.is_none() {
            return false;
        }
        self.top_frame
            && self.same_origin_frame
            && username_selector.is_none_or(|_| self.username_present && self.username_usable)
            && password_selector.is_none_or(|_| self.password_present && self.password_usable)
    }
}

#[derive(Debug, Default)]
struct ProbedCredentialField {
    present: bool,
    usable: bool,
    unsafe_reason: Option<String>,
}

pub async fn credential_field_context(
    http_base: &str,
    username_selector: Option<&str>,
    password_selector: Option<&str>,
) -> Result<CredentialFieldContext> {
    let username_selector_json = optional_js_string(username_selector)?;
    let password_selector_json = optional_js_string(password_selector)?;
    let expression = format!(
        r#"(() => {{
  const usernameSelector = {username_selector_json};
  const passwordSelector = {password_selector_json};
  const topFrame = window.top === window;
  let sameOriginFrame = true;
  try {{ void window.top.location.href; }} catch (_) {{ sameOriginFrame = false; }}
  const inspect = (selector, role) => {{
    if (!selector) {{ return {{ requested: false, present: false, usable: false, unsafe_reason: null }}; }}
    let node;
    try {{ node = document.querySelector(selector); }} catch (_) {{
      return {{ requested: true, present: false, usable: false, unsafe_reason: 'invalid_selector' }};
    }}
    if (!node) {{ return {{ requested: true, present: false, usable: false, unsafe_reason: 'field_missing' }}; }}
    const tag = (node.tagName || '').toLowerCase();
    const type = String(node.getAttribute('type') || (tag === 'textarea' ? 'textarea' : 'text')).toLowerCase();
    const disabled = !!node.disabled;
    const readOnly = !!node.readOnly;
    const usernameTypes = ['text', 'email', 'search', 'tel', 'url', 'password'];
    const safeUsernameType = tag === 'textarea' || (tag === 'input' && usernameTypes.includes(type));
    const safePasswordType = tag === 'input' && type === 'password';
    const safeType = role === 'password' ? safePasswordType : safeUsernameType;
    const reason = disabled ? 'field_disabled'
      : readOnly ? 'field_readonly'
      : !safeType ? `unsafe_${{role}}_field_type`
      : !topFrame ? 'field_not_in_top_frame'
      : !sameOriginFrame ? 'field_cross_origin_frame'
      : null;
    return {{
      requested: true,
      present: true,
      usable: reason === null,
      unsafe_reason: reason,
      tag,
      type,
      disabled,
      read_only: readOnly,
      top_frame: topFrame,
      same_origin_frame: sameOriginFrame
    }};
  }};
  const username = inspect(usernameSelector, 'username');
  const password = inspect(passwordSelector, 'password');
  return {{
    observed_origin: window.location && window.location.origin ? window.location.origin : String(document.location.origin || 'null'),
    top_frame: topFrame,
    same_origin_frame: sameOriginFrame,
    username,
    password,
    username_present: username.present,
    username_usable: username.usable,
    password_present: password.present,
    password_usable: password.usable
  }};
}})();"#
    );
    let value = evaluate_json(http_base, &expression).await?;
    parse_credential_field_context(&value, username_selector, password_selector)
}

fn parse_credential_field_context(
    value: &Value,
    username_selector: Option<&str>,
    password_selector: Option<&str>,
) -> Result<CredentialFieldContext> {
    let observed_origin = value
        .get("observed_origin")
        .and_then(Value::as_str)
        .ok_or_else(|| anyhow::anyhow!("credential field context missing observed origin"))?
        .to_string();
    let username =
        parse_probed_credential_field(value, "username", "username_present", "username_usable");
    let password =
        parse_probed_credential_field(value, "password", "password_present", "password_usable");
    let top_frame = value
        .get("top_frame")
        .and_then(Value::as_bool)
        .unwrap_or(true);
    let same_origin_frame = value
        .get("same_origin_frame")
        .and_then(Value::as_bool)
        .unwrap_or(true);
    let unsafe_reason = credential_field_unsafe_reason(
        username_selector,
        password_selector,
        &username,
        &password,
        top_frame,
        same_origin_frame,
    );
    Ok(CredentialFieldContext {
        observed_origin,
        username_present: username.present,
        username_usable: username.usable,
        password_present: password.present,
        password_usable: password.usable,
        top_frame,
        same_origin_frame,
        unsafe_reason,
    })
}

fn parse_probed_credential_field(
    value: &Value,
    nested_key: &str,
    present_key: &str,
    usable_key: &str,
) -> ProbedCredentialField {
    let nested = value.get(nested_key).unwrap_or(&Value::Null);
    let present = nested
        .get("present")
        .and_then(Value::as_bool)
        .or_else(|| value.get(present_key).and_then(Value::as_bool))
        .unwrap_or(false);
    let usable = nested
        .get("usable")
        .and_then(Value::as_bool)
        .or_else(|| value.get(usable_key).and_then(Value::as_bool))
        .unwrap_or(present);
    let unsafe_reason = nested
        .get("unsafe_reason")
        .and_then(Value::as_str)
        .map(ToString::to_string);
    ProbedCredentialField {
        present,
        usable,
        unsafe_reason,
    }
}

fn credential_field_unsafe_reason(
    username_selector: Option<&str>,
    password_selector: Option<&str>,
    username: &ProbedCredentialField,
    password: &ProbedCredentialField,
    top_frame: bool,
    same_origin_frame: bool,
) -> Option<String> {
    if !top_frame {
        return Some("field_not_in_top_frame".to_string());
    }
    if !same_origin_frame {
        return Some("field_cross_origin_frame".to_string());
    }
    if username_selector.is_some() {
        if !username.present {
            return Some("username_field_missing".to_string());
        }
        if !username.usable {
            return Some(prefix_credential_unsafe_reason(
                "username",
                username.unsafe_reason.as_deref(),
                "username_field_unsafe",
            ));
        }
    }
    if password_selector.is_some() {
        if !password.present {
            return Some("password_field_missing".to_string());
        }
        if !password.usable {
            return Some(prefix_credential_unsafe_reason(
                "password",
                password.unsafe_reason.as_deref(),
                "password_field_unsafe",
            ));
        }
    }
    None
}

fn prefix_credential_unsafe_reason(
    role: &str,
    reason: Option<&str>,
    default_reason: &str,
) -> String {
    let Some(reason) = reason else {
        return default_reason.to_string();
    };
    if reason.starts_with(role) {
        reason.to_string()
    } else if let Some(field_reason) = reason.strip_prefix("field_") {
        format!("{role}_field_{field_reason}")
    } else {
        format!("{role}_{reason}")
    }
}

pub async fn fill_credential_fields(
    http_base: &str,
    username_selector: Option<&str>,
    username: Option<&str>,
    password_selector: Option<&str>,
    password: Option<&str>,
) -> Result<()> {
    if let (Some(selector), Some(value)) = (username_selector, username) {
        focus_credential_field(http_base, selector, "username").await?;
        insert_text(http_base, value).await?;
    }
    if let (Some(selector), Some(value)) = (password_selector, password) {
        focus_credential_field(http_base, selector, "password").await?;
        insert_text(http_base, value).await?;
    }
    Ok(())
}

async fn focus_credential_field(http_base: &str, selector: &str, role: &str) -> Result<()> {
    let selector_json = optional_js_string(Some(selector))?;
    let role_json = optional_js_string(Some(role))?;
    let expression = format!(
        r#"(() => {{
  const selector = {selector_json};
  const role = {role_json};
  const topFrame = window.top === window;
  let sameOriginFrame = true;
  try {{ void window.top.location.href; }} catch (_) {{ sameOriginFrame = false; }}
  const inspect = (node) => {{
    if (!node) {{ return 'field_missing'; }}
    const tag = (node.tagName || '').toLowerCase();
    const type = String(node.getAttribute('type') || (tag === 'textarea' ? 'textarea' : 'text')).toLowerCase();
    const usernameTypes = ['text', 'email', 'search', 'tel', 'url', 'password'];
    const safeUsernameType = tag === 'textarea' || (tag === 'input' && usernameTypes.includes(type));
    const safePasswordType = tag === 'input' && type === 'password';
    const safeType = role === 'password' ? safePasswordType : safeUsernameType;
    if (node.disabled) {{ return 'field_disabled'; }}
    if (node.readOnly) {{ return 'field_readonly'; }}
    if (!safeType) {{ return `unsafe_${{role}}_field_type`; }}
    if (!topFrame) {{ return 'field_not_in_top_frame'; }}
    if (!sameOriginFrame) {{ return 'field_cross_origin_frame'; }}
    return null;
  }};
  let node;
  try {{ node = document.querySelector(selector); }} catch (_) {{ return {{ focused: false, unsafe_reason: 'invalid_selector' }}; }}
  const unsafeReason = inspect(node);
  if (unsafeReason !== null) {{ return {{ focused: false, unsafe_reason: unsafeReason }}; }}
  try {{ node.focus(); }} catch (_) {{}}
  const focused = document.activeElement === node;
  if (!focused) {{ return {{ focused: false, unsafe_reason: 'field_not_focusable' }}; }}
  const proto = Object.getPrototypeOf(node);
  const descriptor = proto ? Object.getOwnPropertyDescriptor(proto, 'value') : undefined;
  if (descriptor && typeof descriptor.set === 'function') {{ descriptor.set.call(node, ''); }}
  else {{ node.value = ''; }}
  try {{
    if (typeof node.setSelectionRange === 'function') {{ node.setSelectionRange(0, 0); }}
  }} catch (_) {{}}
  return {{ focused: true, unsafe_reason: null }};
}})();"#
    );
    let value = evaluate_json(http_base, &expression).await?;
    if !value
        .get("focused")
        .and_then(Value::as_bool)
        .unwrap_or(false)
    {
        let reason = value
            .get("unsafe_reason")
            .and_then(Value::as_str)
            .unwrap_or("field_not_focusable");
        bail!("credential {role} field unsafe: {reason}");
    }
    Ok(())
}

fn optional_js_string(value: Option<&str>) -> Result<String> {
    match value {
        Some(value) => {
            serde_json::to_string(value).context("serialize credential fill script value")
        }
        None => Ok("null".to_string()),
    }
}

pub async fn apply_persona(
    http_base: &str,
    persona: &BrowserPersona,
    browser_user_agent: Option<&str>,
) -> Result<()> {
    let ws_urls = page_ws_urls(http_base).await?;
    for ws_url in ws_urls {
        apply_persona_to_page(&ws_url, persona, browser_user_agent).await?;
    }
    Ok(())
}

#[derive(Debug)]
pub struct PersonaGuard {
    handles: Vec<JoinHandle<()>>,
}

impl PersonaGuard {
    fn new(handles: Vec<JoinHandle<()>>) -> Self {
        Self { handles }
    }

    pub fn abort(&mut self) {
        for handle in self.handles.drain(..) {
            handle.abort();
        }
    }
}

impl Drop for PersonaGuard {
    fn drop(&mut self) {
        self.abort();
    }
}

pub async fn start_persona_guard(
    http_base: &str,
    persona: &BrowserPersona,
    browser_user_agent: Option<&str>,
) -> Result<PersonaGuard> {
    let ws_urls = page_ws_urls(http_base).await?;
    let mut handles = Vec::with_capacity(ws_urls.len() + 1);
    for ws_url in ws_urls {
        let (mut ws, _) = match connect_async(&ws_url).await {
            Ok(connected) => connected,
            Err(error) => {
                abort_join_handles(&mut handles);
                return Err(error).context("connect CDP persona guard websocket");
            }
        };
        if let Err(error) = apply_persona_over_websocket(&mut ws, persona, browser_user_agent).await
        {
            abort_join_handles(&mut handles);
            return Err(error);
        }
        handles.push(tokio::spawn(async move {
            while let Some(frame) = ws.next().await {
                if frame.is_err() {
                    break;
                }
            }
        }));
    }

    let version = match fetch_version(http_base).await {
        Ok(version) => version,
        Err(error) => {
            abort_join_handles(&mut handles);
            return Err(error).context("fetch CDP version for browser persona guard");
        }
    };
    match start_browser_target_persona_guard(
        version.web_socket_debugger_url,
        persona,
        browser_user_agent,
    )
    .await
    {
        Ok(handle) => handles.push(handle),
        Err(error) => {
            abort_join_handles(&mut handles);
            return Err(error);
        }
    }

    Ok(PersonaGuard::new(handles))
}

fn abort_join_handles(handles: &mut Vec<JoinHandle<()>>) {
    for handle in handles.drain(..) {
        handle.abort();
    }
}

async fn apply_persona_to_page(
    ws_url: &str,
    persona: &BrowserPersona,
    browser_user_agent: Option<&str>,
) -> Result<()> {
    let (mut ws, _) = connect_async(ws_url)
        .await
        .context("connect CDP persona websocket")?;
    apply_persona_over_websocket(&mut ws, persona, browser_user_agent).await
}

async fn apply_persona_over_websocket<S>(
    ws: &mut WebSocketStream<S>,
    persona: &BrowserPersona,
    browser_user_agent: Option<&str>,
) -> Result<()>
where
    S: tokio::io::AsyncRead + tokio::io::AsyncWrite + Unpin,
{
    for command in persona_command_plan(persona, browser_user_agent) {
        send_command_over_websocket(ws, command.method, command.params).await?;
    }
    Ok(())
}

#[derive(Debug, Clone)]
struct PersonaCommand {
    method: &'static str,
    params: Value,
}

impl PersonaCommand {
    fn new(method: &'static str, params: Value) -> Self {
        Self { method, params }
    }
}

fn persona_command_plan(
    persona: &BrowserPersona,
    browser_user_agent: Option<&str>,
) -> Vec<PersonaCommand> {
    target_persona_command_plan("page", persona, browser_user_agent)
}

fn target_persona_command_plan(
    target_type: &str,
    persona: &BrowserPersona,
    browser_user_agent: Option<&str>,
) -> Vec<PersonaCommand> {
    if is_page_like_target(target_type) {
        return page_persona_command_plan(persona, browser_user_agent);
    }
    if is_worker_like_target(target_type) {
        return worker_persona_command_plan(persona, browser_user_agent);
    }
    Vec::new()
}

fn page_persona_command_plan(
    persona: &BrowserPersona,
    browser_user_agent: Option<&str>,
) -> Vec<PersonaCommand> {
    let identity = persona.resolved_identity(browser_user_agent);
    let user_agent_metadata = user_agent_metadata(persona, &identity);
    vec![
        PersonaCommand::new("Network.enable", json!({})),
        PersonaCommand::new(
            "Network.setExtraHTTPHeaders",
            json!({"headers": {"Accept-Language": persona.accept_language.clone()}}),
        ),
        PersonaCommand::new(
            "Emulation.setLocaleOverride",
            json!({"locale": persona.locale.clone()}),
        ),
        PersonaCommand::new(
            "Emulation.setTimezoneOverride",
            json!({"timezoneId": persona.timezone_id.clone()}),
        ),
        PersonaCommand::new(
            "Emulation.setDeviceMetricsOverride",
            json!({
                "width": persona.viewport.width,
                "height": persona.viewport.height,
                "deviceScaleFactor": persona.device_scale_factor,
                "mobile": false,
                "screenWidth": persona.screen.width,
                "screenHeight": persona.screen.height,
            }),
        ),
        PersonaCommand::new(
            "Network.setUserAgentOverride",
            json!({
                "userAgent": identity.user_agent,
                "acceptLanguage": persona.accept_language.clone(),
                "platform": persona.platform.clone(),
                "userAgentMetadata": user_agent_metadata,
            }),
        ),
        PersonaCommand::new("Page.enable", json!({})),
        PersonaCommand::new(
            "Page.addScriptToEvaluateOnNewDocument",
            json!({"source": persona_init_script(persona), "runImmediately": true}),
        ),
    ]
}

fn worker_persona_command_plan(
    persona: &BrowserPersona,
    browser_user_agent: Option<&str>,
) -> Vec<PersonaCommand> {
    let identity = persona.resolved_identity(browser_user_agent);
    vec![PersonaCommand::new(
        "Runtime.evaluate",
        json!({
            "expression": worker_persona_init_script(persona, &identity),
            "awaitPromise": false,
            "returnByValue": false,
        }),
    )]
}

async fn start_browser_target_persona_guard(
    browser_ws_url: String,
    persona: &BrowserPersona,
    browser_user_agent: Option<&str>,
) -> Result<JoinHandle<()>> {
    let (mut ws, _) = connect_async(&browser_ws_url)
        .await
        .context("connect CDP browser persona guard websocket")?;
    let mut pending_attachments = VecDeque::new();
    send_browser_command(
        &mut ws,
        "Target.setDiscoverTargets",
        json!({"discover": true}),
        &mut pending_attachments,
    )
    .await
    .context("enable CDP target discovery")?;
    send_browser_command(
        &mut ws,
        "Target.setAutoAttach",
        json!({"autoAttach": true, "waitForDebuggerOnStart": true, "flatten": true}),
        &mut pending_attachments,
    )
    .await
    .context("enable CDP target auto-attach")?;
    process_pending_attachments(
        &mut ws,
        persona,
        browser_user_agent,
        &mut pending_attachments,
    )
    .await;

    let persona = persona.clone();
    let browser_user_agent = browser_user_agent.map(str::to_owned);
    Ok(tokio::spawn(async move {
        if let Err(error) =
            browser_persona_event_loop(ws, persona, browser_user_agent, pending_attachments).await
        {
            warn!(error = %error, "browser persona target guard stopped");
        }
    }))
}

async fn browser_persona_event_loop<S>(
    mut ws: WebSocketStream<S>,
    persona: BrowserPersona,
    browser_user_agent: Option<String>,
    mut pending_attachments: VecDeque<PendingAttachment>,
) -> Result<()>
where
    S: tokio::io::AsyncRead + tokio::io::AsyncWrite + Unpin,
{
    process_pending_attachments(
        &mut ws,
        &persona,
        browser_user_agent.as_deref(),
        &mut pending_attachments,
    )
    .await;
    while let Some(frame) = ws.next().await {
        let frame = frame.context("read CDP browser persona guard frame")?;
        collect_attached_target_event(&frame, &mut pending_attachments)?;
        process_pending_attachments(
            &mut ws,
            &persona,
            browser_user_agent.as_deref(),
            &mut pending_attachments,
        )
        .await;
    }
    Ok(())
}

fn collect_attached_target_event(
    frame: &Message,
    pending_attachments: &mut VecDeque<PendingAttachment>,
) -> Result<()> {
    let Message::Text(text) = frame else {
        return Ok(());
    };
    let value: Value = match serde_json::from_str(text) {
        Ok(value) => value,
        Err(_) => return Ok(()),
    };
    if value.get("method").and_then(Value::as_str) != Some("Target.attachedToTarget") {
        return Ok(());
    }
    let params = value
        .get("params")
        .context("Target.attachedToTarget event missing params")?;
    let session_id = params
        .get("sessionId")
        .and_then(Value::as_str)
        .context("Target.attachedToTarget event missing sessionId")?
        .to_owned();
    let target_type = params
        .get("targetInfo")
        .and_then(|target_info| target_info.get("type"))
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_owned();
    let waiting_for_debugger = params
        .get("waitingForDebugger")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    pending_attachments.push_back(PendingAttachment {
        session_id,
        target_type,
        waiting_for_debugger,
    });
    Ok(())
}

async fn process_pending_attachments<S>(
    ws: &mut WebSocketStream<S>,
    persona: &BrowserPersona,
    browser_user_agent: Option<&str>,
    pending_attachments: &mut VecDeque<PendingAttachment>,
) where
    S: tokio::io::AsyncRead + tokio::io::AsyncWrite + Unpin,
{
    while let Some(attachment) = pending_attachments.pop_front() {
        if is_persona_target(&attachment.target_type)
            && let Err(error) = apply_persona_to_attached_target(
                ws,
                &attachment.session_id,
                &attachment.target_type,
                persona,
                browser_user_agent,
                pending_attachments,
            )
            .await
        {
            warn!(
                session_id = %attachment.session_id,
                target_type = %attachment.target_type,
                error = %error,
                "failed to apply persona to attached CDP target"
            );
        }
        if attachment.waiting_for_debugger
            && let Err(error) = send_attached_command(
                ws,
                &attachment.session_id,
                "Runtime.runIfWaitingForDebugger",
                json!({}),
                pending_attachments,
            )
            .await
        {
            warn!(
                session_id = %attachment.session_id,
                target_type = %attachment.target_type,
                error = %error,
                "failed to resume attached CDP target after persona setup"
            );
        }
    }
}

async fn apply_persona_to_attached_target<S>(
    ws: &mut WebSocketStream<S>,
    session_id: &str,
    target_type: &str,
    persona: &BrowserPersona,
    browser_user_agent: Option<&str>,
    pending_attachments: &mut VecDeque<PendingAttachment>,
) -> Result<()>
where
    S: tokio::io::AsyncRead + tokio::io::AsyncWrite + Unpin,
{
    for command in target_persona_command_plan(target_type, persona, browser_user_agent) {
        send_attached_command(
            ws,
            session_id,
            command.method,
            command.params,
            pending_attachments,
        )
        .await?;
    }
    Ok(())
}

fn is_persona_target(target_type: &str) -> bool {
    is_page_like_target(target_type) || is_worker_like_target(target_type)
}

fn is_page_like_target(target_type: &str) -> bool {
    matches!(target_type, "page" | "iframe")
}

fn is_worker_like_target(target_type: &str) -> bool {
    matches!(target_type, "worker" | "shared_worker" | "service_worker")
}

fn user_agent_metadata(persona: &BrowserPersona, identity: &ResolvedBrowserIdentity) -> Value {
    json!({
        "brands": [
            {"brand": "Chromium", "version": identity.chrome_major_version.clone()},
            {"brand": "Google Chrome", "version": identity.chrome_major_version.clone()},
            {"brand": "Not.A/Brand", "version": "24"},
        ],
        "fullVersionList": [
            {"brand": "Chromium", "version": identity.chrome_full_version.clone()},
            {"brand": "Google Chrome", "version": identity.chrome_full_version.clone()},
            {"brand": "Not.A/Brand", "version": "24.0.0.0"},
        ],
        "platform": identity.client_hint_platform.clone(),
        "platformVersion": identity.platform_version.clone(),
        "architecture": identity.architecture.clone(),
        "model": "",
        "mobile": identity.mobile,
        "bitness": identity.bitness.clone(),
        "wow64": false,
        "formFactors": identity.form_factors.clone(),
        "locale": persona.locale.clone(),
    })
}

fn language_list_from_accept_language(accept_language: &str, fallback_locale: &str) -> Vec<String> {
    let languages = accept_language
        .split(',')
        .filter_map(|part| part.split(';').next())
        .map(str::trim)
        .filter(|part| !part.is_empty())
        .map(str::to_owned)
        .collect::<Vec<_>>();
    if languages.is_empty() {
        vec![fallback_locale.to_owned()]
    } else {
        languages
    }
}

fn persona_init_script(persona: &BrowserPersona) -> String {
    let languages = language_list_from_accept_language(&persona.accept_language, &persona.locale);
    let languages_json = serde_json::to_string(&languages).expect("languages serialize");
    let locale_json = serde_json::to_string(&persona.locale).expect("locale serialize");
    let platform_json = serde_json::to_string(&persona.platform).expect("platform serialize");
    let hardware_concurrency = persona.normalized_hardware_concurrency();
    let device_memory_gb = persona.normalized_device_memory_gb();
    let max_touch_points = persona.normalized_max_touch_points();
    let automation_globals_json =
        serde_json::to_string(AUTOMATION_GLOBAL_DENYLIST).expect("automation globals serialize");
    let automation_global_prefixes_json = serde_json::to_string(AUTOMATION_GLOBAL_PREFIX_DENYLIST)
        .expect("automation global prefixes serialize");
    format!(
        r#"(() => {{
  const languages = {languages_json};
  const viewportWidth = {viewport_width};
  const viewportHeight = {viewport_height};
  const screenWidth = {screen_width};
  const screenHeight = {screen_height};
  const deviceScaleFactor = {device_scale_factor};
  const hardwareConcurrency = {hardware_concurrency};
  const deviceMemory = {device_memory_gb};
  const maxTouchPoints = {max_touch_points};
  const automationGlobalDenylist = new Set({automation_globals_json});
  const automationGlobalPrefixDenylist = {automation_global_prefixes_json};
  const defineGetter = (target, key, value) => {{
    try {{ Object.defineProperty(target, key, {{ get: () => value, configurable: true }}); }} catch (_) {{}}
  }};
  const isAutomationGlobalName = (key) => {{
    try {{
      const name = String(key);
      return automationGlobalDenylist.has(name) || automationGlobalPrefixDenylist.some((prefix) => name.startsWith(prefix));
    }} catch (_) {{ return false; }}
  }};
  const cleanupAutomationGlobals = (root) => {{
    try {{
      const objectCtor = root.Object || Object;
      const names = objectCtor.getOwnPropertyNames(root);
      for (const key of names) {{
        if (!isAutomationGlobalName(key)) {{ continue; }}
        try {{ delete root[key]; }} catch (_) {{}}
        try {{
          if (key in root) {{
            objectCtor.defineProperty(root, key, {{ value: undefined, configurable: true, writable: true }});
          }}
        }} catch (_) {{}}
      }}
    }} catch (_) {{}}
  }};
  const scheduleAutomationGlobalCleanup = (root) => {{
    try {{ cleanupAutomationGlobals(root); }} catch (_) {{}}
    try {{
      const enqueue = root.queueMicrotask || ((fn) => root.Promise.resolve().then(fn));
      enqueue(() => cleanupAutomationGlobals(root));
    }} catch (_) {{}}
    try {{ root.setTimeout(() => cleanupAutomationGlobals(root), 0); }} catch (_) {{}}
    try {{ root.setTimeout(() => cleanupAutomationGlobals(root), 250); }} catch (_) {{}}
    try {{ root.setTimeout(() => cleanupAutomationGlobals(root), 1000); }} catch (_) {{}}
    try {{
      const doc = root.document;
      if (doc) {{ doc.addEventListener('DOMContentLoaded', () => cleanupAutomationGlobals(root), {{ once: true }}); }}
      root.addEventListener('load', () => cleanupAutomationGlobals(root), {{ once: true }});
    }} catch (_) {{}}
  }};
  const hideWebDriver = (root) => {{
    try {{
      const nav = root.navigator;
      const proto = root.Navigator && root.Navigator.prototype;
      if (!nav || !proto) {{ return; }}
      try {{ delete proto.webdriver; }} catch (_) {{}}
      try {{ delete nav.webdriver; }} catch (_) {{}}
      if ('webdriver' in nav) {{
        try {{ root.Object.defineProperty(proto, 'webdriver', {{ get: () => undefined, configurable: true }}); }} catch (_) {{}}
        try {{ delete proto.webdriver; }} catch (_) {{}}
      }}
      if (!('webdriver' in nav)) {{ return; }}
      const objectCtor = root.Object || Object;
      const reflectCtor = root.Reflect || Reflect;
      const isWebDriverLookup = (target, key) => {{
        if (key !== 'webdriver') {{ return false; }}
        try {{ return target === nav || target === proto || (target && target.constructor && target.constructor.name === 'Navigator'); }} catch (_) {{ return false; }}
      }};
      const nativeObjectGetOwnPropertyDescriptor = objectCtor.getOwnPropertyDescriptor || Object.getOwnPropertyDescriptor;
      try {{
        objectCtor.defineProperty(objectCtor, 'getOwnPropertyDescriptor', {{
          configurable: true,
          writable: true,
          value: (target, key) => isWebDriverLookup(target, key) ? undefined : nativeObjectGetOwnPropertyDescriptor(target, key),
        }});
      }} catch (_) {{}}
      const nativeReflectGetOwnPropertyDescriptor = reflectCtor.getOwnPropertyDescriptor || Reflect.getOwnPropertyDescriptor;
      try {{
        objectCtor.defineProperty(reflectCtor, 'getOwnPropertyDescriptor', {{
          configurable: true,
          writable: true,
          value: (target, key) => isWebDriverLookup(target, key) ? undefined : nativeReflectGetOwnPropertyDescriptor(target, key),
        }});
      }} catch (_) {{}}
      const nativeHasOwnProperty = objectCtor.prototype.hasOwnProperty;
      try {{
        objectCtor.defineProperty(objectCtor.prototype, 'hasOwnProperty', {{
          configurable: true,
          writable: true,
          value: function(key) {{ return isWebDriverLookup(this, key) ? false : nativeHasOwnProperty.call(this, key); }},
        }});
      }} catch (_) {{}}
    }} catch (_) {{}}
  }};
  const evaluatePersonaMediaQuery = (query) => {{
    try {{
      const text = String(query).toLowerCase();
      const checks = [];
      const dimensionPattern = /\(\s*(min|max)?-?(device-)?(width|height)\s*:\s*([0-9.]+)px\s*\)/g;
      for (const match of text.matchAll(dimensionPattern)) {{
        const [, operator, devicePrefix, axis, rawValue] = match;
        const personaValue = devicePrefix ? (axis === 'width' ? screenWidth : screenHeight) : (axis === 'width' ? viewportWidth : viewportHeight);
        const requestedValue = Number.parseFloat(rawValue);
        checks.push(operator === 'min' ? personaValue >= requestedValue : operator === 'max' ? personaValue <= requestedValue : personaValue === requestedValue);
      }}
      const resolutionPattern = /\(\s*(min|max)?-?resolution\s*:\s*([0-9.]+)dppx\s*\)/g;
      for (const match of text.matchAll(resolutionPattern)) {{
        const [, operator, rawValue] = match;
        const requestedValue = Number.parseFloat(rawValue);
        checks.push(operator === 'min' ? deviceScaleFactor >= requestedValue : operator === 'max' ? deviceScaleFactor <= requestedValue : deviceScaleFactor === requestedValue);
      }}
      return checks.length ? checks.every(Boolean) : null;
    }} catch (_) {{
      return null;
    }}
  }};
  const applyPersonaToWindow = (root) => {{
    try {{
      scheduleAutomationGlobalCleanup(root);
      hideWebDriver(root);
      const navigatorPrototype = root.Navigator && root.Navigator.prototype;
      const screenPrototype = root.Screen && root.Screen.prototype;
      if (navigatorPrototype) {{
        defineGetter(navigatorPrototype, 'language', {locale_json});
        defineGetter(navigatorPrototype, 'languages', root.Object.freeze([...languages]));
        defineGetter(navigatorPrototype, 'platform', {platform_json});
        defineGetter(navigatorPrototype, 'hardwareConcurrency', hardwareConcurrency);
        defineGetter(navigatorPrototype, 'deviceMemory', deviceMemory);
        defineGetter(navigatorPrototype, 'maxTouchPoints', maxTouchPoints);
      }}
      if (screenPrototype) {{
        defineGetter(screenPrototype, 'width', {screen_width});
        defineGetter(screenPrototype, 'height', {screen_height});
        defineGetter(screenPrototype, 'availWidth', {screen_width});
        defineGetter(screenPrototype, 'availHeight', {screen_height});
        defineGetter(screenPrototype, 'colorDepth', 24);
        defineGetter(screenPrototype, 'pixelDepth', 24);
      }}
      defineGetter(root, 'outerWidth', screenWidth);
      defineGetter(root, 'outerHeight', screenHeight);
      defineGetter(root, 'innerWidth', viewportWidth);
      defineGetter(root, 'innerHeight', viewportHeight);
      defineGetter(root, 'devicePixelRatio', deviceScaleFactor);
      const doc = root.document;
      const visualViewport = root.visualViewport;
      if (visualViewport) {{
        const visualViewportPrototype = root.Object.getPrototypeOf(visualViewport);
        defineGetter(visualViewportPrototype, 'width', viewportWidth);
        defineGetter(visualViewportPrototype, 'height', viewportHeight);
        defineGetter(visualViewportPrototype, 'scale', 1);
      }}
      const nativeMatchMedia = root.matchMedia;
      root.Object.defineProperty(root, 'matchMedia', {{
        value(query) {{
          const text = root.String(query);
          const response = nativeMatchMedia ? nativeMatchMedia.call(this, text) : {{ media: text, matches: false }};
          const forced = evaluatePersonaMediaQuery(text);
          if (forced !== null) {{
            defineGetter(response, 'matches', forced);
          }}
          return response;
        }},
        configurable: true,
        writable: true,
      }});
      removeAutomationSignals(root, root, navigatorPrototype);

      const applyIframeViewport = () => {{
        try {{
          for (const frame of doc.querySelectorAll('iframe')) {{
            frame.style.setProperty('width', `${{viewportWidth}}px`, 'important');
            frame.style.setProperty('height', `${{viewportHeight}}px`, 'important');
          }}
        }} catch (_) {{}}
      }};
      try {{
        if (doc) {{
          applyIframeViewport();
          doc.addEventListener('DOMContentLoaded', applyIframeViewport, {{ once: true }});
          new root.MutationObserver(applyIframeViewport).observe(doc.documentElement || doc, {{ childList: true, subtree: true }});
        }}
      }} catch (_) {{}}
    }} catch (_) {{}}
  }};
  applyPersonaToWindow(window);
  try {{
    const nativeOpen = window.open;
    Object.defineProperty(window, 'open', {{
      configurable: true,
      writable: true,
      value: function(...args) {{
        const opened = nativeOpen.apply(this, args);
        try {{ if (opened) {{ applyPersonaToWindow(opened); }} }} catch (_) {{}}
        return opened;
      }},
    }});
  }} catch (_) {{}}
}})();"#,
        screen_width = persona.screen.width,
        screen_height = persona.screen.height,
        viewport_width = persona.viewport.width,
        viewport_height = persona.viewport.height,
        device_scale_factor = persona.device_scale_factor,
        hardware_concurrency = hardware_concurrency,
        device_memory_gb = device_memory_gb,
        max_touch_points = max_touch_points,
    )
}

fn worker_persona_init_script(
    persona: &BrowserPersona,
    identity: &ResolvedBrowserIdentity,
) -> String {
    let languages = language_list_from_accept_language(&persona.accept_language, &persona.locale);
    let languages_json = serde_json::to_string(&languages).expect("languages serialize");
    let locale_json = serde_json::to_string(&persona.locale).expect("locale serialize");
    let platform_json = serde_json::to_string(&persona.platform).expect("platform serialize");
    let user_agent_json =
        serde_json::to_string(&identity.user_agent).expect("user agent serialize");
    let hardware_concurrency = persona.normalized_hardware_concurrency();
    let device_memory_gb = persona.normalized_device_memory_gb();
    let max_touch_points = persona.normalized_max_touch_points();

    format!(
        r#"(() => {{
  const root = globalThis;
  const navigator = root.navigator;
  if (!navigator) {{ return; }}
  const languages = {languages_json};
  const defineGetter = (target, key, value) => {{
    if (!target) {{ return; }}
    try {{ Object.defineProperty(target, key, {{ get: () => value, configurable: true }}); }} catch (_) {{}}
  }};
  const navigatorPrototype = Object.getPrototypeOf(navigator);
  defineGetter(navigatorPrototype, 'userAgent', {user_agent_json});
  defineGetter(navigatorPrototype, 'language', {locale_json});
  defineGetter(navigatorPrototype, 'languages', Object.freeze([...languages]));
  defineGetter(navigatorPrototype, 'platform', {platform_json});
  defineGetter(navigatorPrototype, 'hardwareConcurrency', {hardware_concurrency});
  defineGetter(navigatorPrototype, 'deviceMemory', {device_memory_gb});
  defineGetter(navigatorPrototype, 'maxTouchPoints', {max_touch_points});
}})();"#,
    )
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

pub async fn press_key(http_base: &str, key: &str) -> Result<()> {
    let ws_url = first_page_ws_url(http_base).await?;
    let definition = key_definition(key)?;
    send_page_command(
        &ws_url,
        "Input.dispatchKeyEvent",
        key_event_params(definition, key_down_type(definition)),
    )
    .await?;
    send_page_command(
        &ws_url,
        "Input.dispatchKeyEvent",
        key_event_params(definition, "keyUp"),
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
    send_command_over_websocket(&mut ws, method, params).await
}

async fn send_command_over_websocket<S>(
    ws: &mut WebSocketStream<S>,
    method: &str,
    params: Value,
) -> Result<Value>
where
    S: tokio::io::AsyncRead + tokio::io::AsyncWrite + Unpin,
{
    let mut pending_attachments = VecDeque::new();
    send_command_over_websocket_collecting_target_events(
        ws,
        None,
        method,
        params,
        &mut pending_attachments,
    )
    .await
}

async fn send_browser_command<S>(
    ws: &mut WebSocketStream<S>,
    method: &str,
    params: Value,
    pending_attachments: &mut VecDeque<PendingAttachment>,
) -> Result<Value>
where
    S: tokio::io::AsyncRead + tokio::io::AsyncWrite + Unpin,
{
    send_command_over_websocket_collecting_target_events(
        ws,
        None,
        method,
        params,
        pending_attachments,
    )
    .await
}

async fn send_attached_command<S>(
    ws: &mut WebSocketStream<S>,
    session_id: &str,
    method: &str,
    params: Value,
    pending_attachments: &mut VecDeque<PendingAttachment>,
) -> Result<Value>
where
    S: tokio::io::AsyncRead + tokio::io::AsyncWrite + Unpin,
{
    send_command_over_websocket_collecting_target_events(
        ws,
        Some(session_id),
        method,
        params,
        pending_attachments,
    )
    .await
}

async fn send_command_over_websocket_collecting_target_events<S>(
    ws: &mut WebSocketStream<S>,
    session_id: Option<&str>,
    method: &str,
    params: Value,
    pending_attachments: &mut VecDeque<PendingAttachment>,
) -> Result<Value>
where
    S: tokio::io::AsyncRead + tokio::io::AsyncWrite + Unpin,
{
    let mut msg = serde_json::Map::new();
    msg.insert("id".to_owned(), json!(1));
    msg.insert("method".to_owned(), json!(method));
    msg.insert("params".to_owned(), params);
    if let Some(session_id) = session_id {
        msg.insert("sessionId".to_owned(), json!(session_id));
    }
    ws.send(Message::Text(Value::Object(msg).to_string()))
        .await
        .context("send CDP command")?;
    while let Some(frame) = ws.next().await {
        let frame = frame.context("read CDP frame")?;
        collect_attached_target_event(&frame, pending_attachments)?;
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

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct KeyDefinition {
    key: &'static str,
    code: &'static str,
    key_code: u32,
    text: Option<&'static str>,
}

fn key_definition(key: &str) -> Result<KeyDefinition> {
    match key.to_ascii_lowercase().as_str() {
        "tab" => Ok(KeyDefinition {
            key: "Tab",
            code: "Tab",
            key_code: 9,
            text: None,
        }),
        "enter" | "return" => Ok(KeyDefinition {
            key: "Enter",
            code: "Enter",
            key_code: 13,
            text: Some("\r"),
        }),
        "escape" | "esc" => Ok(KeyDefinition {
            key: "Escape",
            code: "Escape",
            key_code: 27,
            text: None,
        }),
        "backspace" => Ok(KeyDefinition {
            key: "Backspace",
            code: "Backspace",
            key_code: 8,
            text: None,
        }),
        "space" => Ok(KeyDefinition {
            key: " ",
            code: "Space",
            key_code: 32,
            text: Some(" "),
        }),
        "arrowup" | "up" => Ok(KeyDefinition {
            key: "ArrowUp",
            code: "ArrowUp",
            key_code: 38,
            text: None,
        }),
        "arrowdown" | "down" => Ok(KeyDefinition {
            key: "ArrowDown",
            code: "ArrowDown",
            key_code: 40,
            text: None,
        }),
        "arrowleft" | "left" => Ok(KeyDefinition {
            key: "ArrowLeft",
            code: "ArrowLeft",
            key_code: 37,
            text: None,
        }),
        "arrowright" | "right" => Ok(KeyDefinition {
            key: "ArrowRight",
            code: "ArrowRight",
            key_code: 39,
            text: None,
        }),
        "pageup" => Ok(KeyDefinition {
            key: "PageUp",
            code: "PageUp",
            key_code: 33,
            text: None,
        }),
        "pagedown" => Ok(KeyDefinition {
            key: "PageDown",
            code: "PageDown",
            key_code: 34,
            text: None,
        }),
        "home" => Ok(KeyDefinition {
            key: "Home",
            code: "Home",
            key_code: 36,
            text: None,
        }),
        "end" => Ok(KeyDefinition {
            key: "End",
            code: "End",
            key_code: 35,
            text: None,
        }),
        "delete" => Ok(KeyDefinition {
            key: "Delete",
            code: "Delete",
            key_code: 46,
            text: None,
        }),
        _ => bail!("unsupported takeover key: {key}"),
    }
}

fn key_down_type(definition: KeyDefinition) -> &'static str {
    if definition.text.is_some() {
        "keyDown"
    } else {
        "rawKeyDown"
    }
}

fn key_event_params(definition: KeyDefinition, event_type: &str) -> Value {
    let mut params = serde_json::Map::from_iter([
        ("type".to_string(), Value::String(event_type.to_string())),
        ("key".to_string(), Value::String(definition.key.to_string())),
        (
            "code".to_string(),
            Value::String(definition.code.to_string()),
        ),
        (
            "windowsVirtualKeyCode".to_string(),
            Value::Number(definition.key_code.into()),
        ),
        (
            "nativeVirtualKeyCode".to_string(),
            Value::Number(definition.key_code.into()),
        ),
    ]);
    if event_type != "keyUp"
        && let Some(text) = definition.text
    {
        params.insert("text".to_string(), Value::String(text.to_string()));
        params.insert(
            "unmodifiedText".to_string(),
            Value::String(text.to_string()),
        );
    }
    Value::Object(params)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        models::BrowserPersona,
        test_support::{MockCdpServer, MockEndpointResponse, WsReply},
    };
    use axum::http::StatusCode;
    use futures_util::{SinkExt, StreamExt};
    use serde_json::json;
    use std::{
        io,
        pin::Pin,
        task::{Context as TaskContext, Poll},
        time::Duration,
    };
    use tokio::{
        io::{AsyncRead, AsyncWrite, ReadBuf, duplex},
        net::TcpListener,
        time::timeout,
    };
    use tokio_tungstenite::tungstenite::protocol::Role;

    #[derive(Default)]
    struct WriteErrorStream;

    impl AsyncRead for WriteErrorStream {
        fn poll_read(
            self: Pin<&mut Self>,
            _cx: &mut TaskContext<'_>,
            _buf: &mut ReadBuf<'_>,
        ) -> Poll<io::Result<()>> {
            Poll::Ready(Ok(()))
        }
    }

    impl AsyncWrite for WriteErrorStream {
        fn poll_write(
            self: Pin<&mut Self>,
            _cx: &mut TaskContext<'_>,
            _buf: &[u8],
        ) -> Poll<io::Result<usize>> {
            Poll::Ready(Err(io::Error::new(
                io::ErrorKind::BrokenPipe,
                "forced write failure",
            )))
        }

        fn poll_flush(self: Pin<&mut Self>, _cx: &mut TaskContext<'_>) -> Poll<io::Result<()>> {
            Poll::Ready(Ok(()))
        }

        fn poll_shutdown(self: Pin<&mut Self>, _cx: &mut TaskContext<'_>) -> Poll<io::Result<()>> {
            Poll::Ready(Ok(()))
        }
    }

    #[derive(Default)]
    struct ReadErrorStream {
        read_failed: bool,
    }

    impl AsyncRead for ReadErrorStream {
        fn poll_read(
            mut self: Pin<&mut Self>,
            _cx: &mut TaskContext<'_>,
            _buf: &mut ReadBuf<'_>,
        ) -> Poll<io::Result<()>> {
            if self.read_failed {
                Poll::Ready(Ok(()))
            } else {
                self.read_failed = true;
                Poll::Ready(Err(io::Error::new(
                    io::ErrorKind::ConnectionReset,
                    "forced read failure",
                )))
            }
        }
    }

    impl AsyncWrite for ReadErrorStream {
        fn poll_write(
            self: Pin<&mut Self>,
            _cx: &mut TaskContext<'_>,
            buf: &[u8],
        ) -> Poll<io::Result<usize>> {
            Poll::Ready(Ok(buf.len()))
        }

        fn poll_flush(self: Pin<&mut Self>, _cx: &mut TaskContext<'_>) -> Poll<io::Result<()>> {
            Poll::Ready(Ok(()))
        }

        fn poll_shutdown(self: Pin<&mut Self>, _cx: &mut TaskContext<'_>) -> Poll<io::Result<()>> {
            Poll::Ready(Ok(()))
        }
    }

    async fn unused_socket_addr() -> std::net::SocketAddr {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        drop(listener);
        addr
    }

    fn attached_target_event(session_id: &str, target_type: &str, waiting: bool) -> Value {
        json!({
            "method": "Target.attachedToTarget",
            "params": {
                "sessionId": session_id,
                "targetInfo": {"targetId": format!("{session_id}-target"), "type": target_type},
                "waitingForDebugger": waiting
            }
        })
    }

    async fn read_peer_command<S>(ws: &mut WebSocketStream<S>) -> Value
    where
        S: AsyncRead + AsyncWrite + Unpin,
    {
        let frame = timeout(Duration::from_secs(1), ws.next())
            .await
            .expect("timed out waiting for command")
            .expect("websocket closed before command")
            .expect("command frame should be readable");
        let Message::Text(text) = frame else {
            panic!("expected text CDP command frame");
        };
        serde_json::from_str(&text).expect("CDP command should be valid JSON")
    }

    async fn send_peer_success<S>(ws: &mut WebSocketStream<S>, command: &Value)
    where
        S: AsyncRead + AsyncWrite + Unpin,
    {
        ws.send(Message::Text(
            json!({"id": command["id"].clone(), "result": {}}).to_string(),
        ))
        .await
        .expect("send CDP success response");
    }

    #[test]
    fn custom_stream_helpers_cover_remaining_poll_paths() {
        let waker = futures_util::task::noop_waker_ref();
        let mut cx = TaskContext::from_waker(waker);

        let mut write_stream = WriteErrorStream;
        let mut write_read_buf = ReadBuf::new(&mut []);
        assert!(matches!(
            Pin::new(&mut write_stream).poll_read(&mut cx, &mut write_read_buf),
            Poll::Ready(Ok(()))
        ));
        assert!(matches!(
            Pin::new(&mut write_stream).poll_flush(&mut cx),
            Poll::Ready(Ok(()))
        ));
        assert!(matches!(
            Pin::new(&mut write_stream).poll_shutdown(&mut cx),
            Poll::Ready(Ok(()))
        ));

        let mut read_stream = ReadErrorStream { read_failed: true };
        let mut read_read_buf = ReadBuf::new(&mut []);
        assert!(matches!(
            Pin::new(&mut read_stream).poll_read(&mut cx, &mut read_read_buf),
            Poll::Ready(Ok(()))
        ));
        assert!(matches!(
            Pin::new(&mut read_stream).poll_shutdown(&mut cx),
            Poll::Ready(Ok(()))
        ));
    }

    #[tokio::test]
    async fn cdp_http_and_ws_helpers_round_trip_against_mock_runtime() {
        let server = MockCdpServer::spawn().await;
        server.set_screenshot_bytes(b"mock-png").await;
        let version = fetch_version(&server.base_url).await.unwrap();
        assert_eq!(version.web_socket_debugger_url, server.browser_ws_url);
        assert_eq!(
            first_page_ws_url(&server.base_url).await.unwrap(),
            server.page_ws_url
        );

        open_new_page(&server.base_url, "about:blank")
            .await
            .unwrap();
        assert_eq!(server.new_page_calls(), 1);
        assert_eq!(
            capture_screenshot_png(&server.base_url).await.unwrap(),
            b"mock-png"
        );
        click(&server.base_url, 10.0, 20.0).await.unwrap();
        insert_text(&server.base_url, "hello world").await.unwrap();
        scroll(&server.base_url, -2.0, 30.0).await.unwrap();
        press_key(&server.base_url, "tab").await.unwrap();
        browser_close(&server.browser_ws_url).await.unwrap();

        let commands = server.recorded_commands().await;
        let methods: Vec<_> = commands
            .iter()
            .map(|command| command.method.as_str())
            .collect();
        assert_eq!(
            methods,
            vec![
                "Page.captureScreenshot",
                "Input.dispatchMouseEvent",
                "Input.dispatchMouseEvent",
                "Input.insertText",
                "Input.dispatchMouseEvent",
                "Input.dispatchKeyEvent",
                "Input.dispatchKeyEvent",
                "Browser.close",
            ]
        );
        assert_eq!(commands[0].params["format"], "png");
        assert_eq!(commands[1].params["type"], "mousePressed");
        assert_eq!(commands[1].params["x"], 10.0);
        assert_eq!(commands[3].params["text"], "hello world");
        assert_eq!(commands[4].params["deltaX"], -2.0);
        assert_eq!(commands[5].params["type"], "rawKeyDown");
        assert_eq!(commands[6].params["type"], "keyUp");
        assert_eq!(commands[7].websocket, "browser");

        server.stop().await;
    }

    #[tokio::test]
    async fn credential_field_context_requires_fields_to_be_safe_in_top_frame() {
        let server = MockCdpServer::spawn().await;
        server
            .enqueue_page_reply(WsReply::Success(json!({"result": {"value": {
                "observed_origin": "https://example.test",
                "top_frame": true,
                "same_origin_frame": true,
                "username": {"requested": true, "present": true, "usable": true, "unsafe_reason": null},
                "password": {"requested": true, "present": true, "usable": false, "unsafe_reason": "field_disabled"}
            }}})))
            .await;

        let context = credential_field_context(&server.base_url, Some("#user"), Some("#pass"))
            .await
            .unwrap();

        assert_eq!(context.observed_origin, "https://example.test");
        assert!(context.username_present);
        assert!(context.username_usable);
        assert!(context.password_present);
        assert!(!context.password_usable);
        assert!(!context.has_requested_fields(Some("#user"), Some("#pass")));
        assert_eq!(
            context.unsafe_reason.as_deref(),
            Some("password_field_disabled")
        );

        server.stop().await;
    }

    #[tokio::test]
    async fn fill_credential_fields_uses_insert_text_without_runtime_evaluate_secrets() {
        let server = MockCdpServer::spawn().await;
        for reply in [
            WsReply::Success(json!({"result": {"value": {"focused": true}}})),
            WsReply::Success(json!({"result": {}})),
            WsReply::Success(json!({"result": {"value": {"focused": true}}})),
            WsReply::Success(json!({"result": {}})),
        ] {
            server.enqueue_page_reply(reply).await;
        }
        let username = "synthetic-user-secret";
        let password = "synthetic-password-secret";

        fill_credential_fields(
            &server.base_url,
            Some("#user"),
            Some(username),
            Some("#pass"),
            Some(password),
        )
        .await
        .unwrap();

        let commands = server.recorded_commands().await;
        assert_eq!(
            commands
                .iter()
                .filter(|command| command.method == "Input.insertText")
                .count(),
            2
        );
        for command in commands
            .iter()
            .filter(|command| command.method == "Runtime.evaluate")
        {
            let expression = command.params["expression"].as_str().unwrap_or_default();
            assert!(!expression.contains(username));
            assert!(!expression.contains(password));
        }

        server.stop().await;
    }

    #[tokio::test]
    async fn fill_credential_fields_requires_actual_focus_before_insert_text() {
        let server = MockCdpServer::spawn().await;
        server
            .enqueue_page_reply(WsReply::Success(json!({"result": {"value": {
                "focused": false,
                "unsafe_reason": "field_not_focusable"
            }}})))
            .await;
        let username = "synthetic-user-secret";

        let err = fill_credential_fields(
            &server.base_url,
            Some("#hidden-user"),
            Some(username),
            None,
            None,
        )
        .await
        .unwrap_err();

        assert!(
            err.to_string()
                .contains("credential username field unsafe: field_not_focusable")
        );
        let commands = server.recorded_commands().await;
        assert!(
            commands
                .iter()
                .all(|command| command.method != "Input.insertText"),
            "focus failure must fail closed before any secret Input.insertText"
        );
        let focus_expression = commands
            .iter()
            .find(|command| command.method == "Runtime.evaluate")
            .and_then(|command| command.params["expression"].as_str())
            .expect("focus probe should use Runtime.evaluate");
        assert!(focus_expression.contains("document.activeElement === node"));
        assert!(
            focus_expression.contains("try {\n    if (typeof node.setSelectionRange"),
            "focus probe must ignore setSelectionRange failures on email/search-like inputs"
        );
        assert!(
            !focus_expression.contains("|| true"),
            "focus probe must not report success when the requested node is not active"
        );
        assert!(!focus_expression.contains(username));

        server.stop().await;
    }

    #[tokio::test]
    async fn apply_persona_sends_coherent_overrides_without_headless_marker() {
        let server = MockCdpServer::spawn().await;
        let persona = BrowserPersona {
            locale: "en-US".into(),
            accept_language: "en-US,en;q=0.9".into(),
            timezone_id: "America/New_York".into(),
            platform: "Linux x86_64".into(),
            user_agent: None,
            viewport: crate::models::Viewport {
                width: 1280,
                height: 800,
            },
            screen: crate::models::Viewport {
                width: 1920,
                height: 1080,
            },
            device_scale_factor: 1.25,
            hardware_concurrency: 8,
            device_memory_gb: 8,
            max_touch_points: 0,
        };

        apply_persona(
            &server.base_url,
            &persona,
            Some(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 \
                 (KHTML, like Gecko) HeadlessChrome/125.0.0.0 Safari/537.36",
            ),
        )
        .await
        .unwrap();

        let commands = server.recorded_commands().await;
        let methods: Vec<_> = commands
            .iter()
            .map(|command| command.method.as_str())
            .collect();
        assert_eq!(
            methods,
            vec![
                "Network.enable",
                "Network.setExtraHTTPHeaders",
                "Emulation.setLocaleOverride",
                "Emulation.setTimezoneOverride",
                "Emulation.setDeviceMetricsOverride",
                "Network.setUserAgentOverride",
                "Page.enable",
                "Page.addScriptToEvaluateOnNewDocument",
            ]
        );
        assert_eq!(
            commands[1].params["headers"]["Accept-Language"],
            persona.accept_language
        );
        assert_eq!(commands[2].params["locale"], persona.locale);
        assert_eq!(commands[3].params["timezoneId"], persona.timezone_id);
        assert_eq!(commands[4].params["width"], persona.viewport.width);
        assert_eq!(commands[4].params["height"], persona.viewport.height);
        assert_eq!(commands[4].params["screenWidth"], persona.screen.width);
        assert_eq!(commands[4].params["screenHeight"], persona.screen.height);
        assert_eq!(
            commands[4].params["deviceScaleFactor"],
            persona.device_scale_factor
        );
        assert_eq!(commands[4].params["mobile"], false);
        assert_eq!(
            commands[5].params["acceptLanguage"],
            persona.accept_language
        );
        assert_eq!(commands[5].params["platform"], persona.platform);
        assert_eq!(commands[5].params["userAgentMetadata"]["platform"], "Linux");
        assert_eq!(
            commands[5].params["userAgentMetadata"]["locale"],
            persona.locale
        );
        assert_eq!(commands[5].params["userAgentMetadata"]["mobile"], false);
        assert_eq!(
            commands[5].params["userAgentMetadata"]["formFactors"][0],
            "Desktop"
        );
        assert_eq!(
            commands[5].params["userAgentMetadata"]["brands"][0]["version"],
            "125"
        );
        for key in ["brands", "fullVersionList"] {
            for brand in commands[5].params["userAgentMetadata"][key]
                .as_array()
                .unwrap()
            {
                assert_ne!(brand["brand"], "HeadlessChrome");
            }
        }
        let user_agent = commands[5].params["userAgent"].as_str().unwrap();
        assert!(user_agent.contains("X11; Linux x86_64"));
        assert!(user_agent.contains("Chrome/125.0.0.0"));
        assert!(!user_agent.contains("HeadlessChrome"));
        let init_script = commands[7].params["source"].as_str().unwrap();
        assert_eq!(commands[7].params["runImmediately"], true);
        assert!(init_script.contains("Navigator.prototype"));
        assert!(init_script.contains("Screen.prototype"));
        assert!(init_script.contains("innerWidth"));
        assert!(init_script.contains("MutationObserver"));
        assert!(init_script.contains("automationGlobalDenylist"));
        assert!(init_script.contains("scheduleAutomationGlobalCleanup(root)"));
        assert!(init_script.contains("cleanupAutomationGlobals(root)"));
        assert!(init_script.contains("domAutomationController"));
        assert!(init_script.contains("$chrome_asyncScriptInfo"));
        assert!(init_script.contains("cdc_adoQpoasnfa76pfcZLmcfl_Array"));
        assert!(init_script.contains("__webdriver"));
        assert!(init_script.contains("startsWith(prefix)"));
        assert!(init_script.contains("delete root[key]"));
        assert!(init_script.contains("value: undefined"));
        assert!(init_script.contains("en-US"));
        assert!(init_script.contains("Linux x86_64"));
        assert!(init_script.contains("1920"));
        assert!(init_script.contains("1.25"));

        server.stop().await;
    }

    #[tokio::test]
    async fn start_persona_guard_keeps_overrides_attached_until_aborted() {
        let server = MockCdpServer::spawn().await;
        let persona = BrowserPersona::default();

        let mut guard = start_persona_guard(
            &server.base_url,
            &persona,
            Some(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 \
                 (KHTML, like Gecko) HeadlessChrome/125.0.0.0 Safari/537.36",
            ),
        )
        .await
        .unwrap();

        let commands = server.recorded_commands().await;
        assert_eq!(commands[0].method, "Network.enable");
        assert_eq!(commands[4].method, "Emulation.setDeviceMetricsOverride");
        assert_eq!(commands[7].method, "Page.addScriptToEvaluateOnNewDocument");
        assert_eq!(commands[7].params["runImmediately"], true);
        assert!(commands.iter().any(|command| {
            command.websocket == "browser" && command.method == "Target.setDiscoverTargets"
        }));
        let auto_attach = commands
            .iter()
            .find(|command| {
                command.websocket == "browser" && command.method == "Target.setAutoAttach"
            })
            .expect("browser persona guard should enable target auto-attach");
        assert_eq!(auto_attach.params["autoAttach"], true);
        assert_eq!(auto_attach.params["waitForDebuggerOnStart"], true);
        assert_eq!(auto_attach.params["flatten"], true);
        guard.abort();
        drop(guard);
        server.stop().await;
    }

    #[tokio::test]
    async fn start_persona_guard_applies_persona_to_auto_attached_pages_before_resume() {
        let server = MockCdpServer::spawn().await;
        server
            .enqueue_browser_reply(WsReply::Success(json!({})))
            .await;
        server
            .enqueue_browser_reply(WsReply::CustomEventThenSuccess {
                event: json!({
                    "method": "Target.attachedToTarget",
                    "params": {
                        "sessionId": "popup-session",
                        "targetInfo": {"targetId": "popup-target", "type": "page"},
                        "waitingForDebugger": true
                    }
                }),
                result: json!({}),
            })
            .await;
        let persona = BrowserPersona::default();

        let mut guard = start_persona_guard(&server.base_url, &persona, None)
            .await
            .unwrap();

        let commands = server.recorded_commands().await;
        let attached_commands = commands
            .iter()
            .filter(|command| {
                command.websocket == "browser"
                    && command.session_id.as_deref() == Some("popup-session")
            })
            .collect::<Vec<_>>();
        assert_eq!(attached_commands.len(), 9);
        assert_eq!(attached_commands[0].method, "Network.enable");
        assert_eq!(
            attached_commands[4].method,
            "Emulation.setDeviceMetricsOverride"
        );
        assert_eq!(
            attached_commands[7].method,
            "Page.addScriptToEvaluateOnNewDocument"
        );
        assert_eq!(attached_commands[7].params["runImmediately"], true);
        assert_eq!(
            attached_commands[8].method,
            "Runtime.runIfWaitingForDebugger"
        );
        guard.abort();
        drop(guard);
        server.stop().await;
    }

    #[tokio::test]
    async fn browser_persona_event_loop_routes_nested_auto_attach_by_session_id() {
        let (guard_io, peer_io) = duplex(64 * 1024);
        let guard_ws = WebSocketStream::from_raw_socket(guard_io, Role::Server, None).await;
        let mut peer_ws = WebSocketStream::from_raw_socket(peer_io, Role::Client, None).await;
        let handle = tokio::spawn(browser_persona_event_loop(
            guard_ws,
            BrowserPersona::default(),
            None,
            VecDeque::new(),
        ));

        peer_ws
            .send(Message::Text(
                attached_target_event("first-page", "page", true).to_string(),
            ))
            .await
            .unwrap();
        let first_command = read_peer_command(&mut peer_ws).await;
        assert_eq!(first_command["sessionId"], "first-page");
        assert_eq!(first_command["method"], "Network.enable");

        peer_ws
            .send(Message::Text(
                attached_target_event("second-page", "page", false).to_string(),
            ))
            .await
            .unwrap();
        send_peer_success(&mut peer_ws, &first_command).await;

        let mut routed = vec![(
            first_command["sessionId"].as_str().unwrap().to_string(),
            first_command["method"].as_str().unwrap().to_string(),
        )];
        for _ in 0..16 {
            let command = read_peer_command(&mut peer_ws).await;
            routed.push((
                command["sessionId"].as_str().unwrap().to_string(),
                command["method"].as_str().unwrap().to_string(),
            ));
            send_peer_success(&mut peer_ws, &command).await;
        }

        let first_methods = routed
            .iter()
            .filter(|(session, _)| session == "first-page")
            .map(|(_, method)| method.as_str())
            .collect::<Vec<_>>();
        assert_eq!(
            first_methods,
            vec![
                "Network.enable",
                "Network.setExtraHTTPHeaders",
                "Emulation.setLocaleOverride",
                "Emulation.setTimezoneOverride",
                "Emulation.setDeviceMetricsOverride",
                "Network.setUserAgentOverride",
                "Page.enable",
                "Page.addScriptToEvaluateOnNewDocument",
                "Runtime.runIfWaitingForDebugger",
            ]
        );
        let second_methods = routed
            .iter()
            .filter(|(session, _)| session == "second-page")
            .map(|(_, method)| method.as_str())
            .collect::<Vec<_>>();
        assert_eq!(
            second_methods,
            vec![
                "Network.enable",
                "Network.setExtraHTTPHeaders",
                "Emulation.setLocaleOverride",
                "Emulation.setTimezoneOverride",
                "Emulation.setDeviceMetricsOverride",
                "Network.setUserAgentOverride",
                "Page.enable",
                "Page.addScriptToEvaluateOnNewDocument",
            ]
        );

        peer_ws.close(None).await.unwrap();
        let result = timeout(Duration::from_secs(1), handle)
            .await
            .expect("browser persona event loop should exit")
            .expect("event-loop task should not panic");
        result.unwrap();
    }

    #[tokio::test]
    async fn browser_persona_event_loop_applies_worker_persona_without_resume_when_not_waiting() {
        let (guard_io, peer_io) = duplex(4096);
        let guard_ws = WebSocketStream::from_raw_socket(guard_io, Role::Server, None).await;
        let mut peer_ws = WebSocketStream::from_raw_socket(peer_io, Role::Client, None).await;
        let handle = tokio::spawn(browser_persona_event_loop(
            guard_ws,
            BrowserPersona::default(),
            None,
            VecDeque::new(),
        ));

        peer_ws
            .send(Message::Text(
                attached_target_event("worker-session", "service_worker", false).to_string(),
            ))
            .await
            .unwrap();
        let command = read_peer_command(&mut peer_ws).await;
        assert_eq!(command["sessionId"], "worker-session");
        assert_eq!(command["method"], "Runtime.evaluate");
        assert_eq!(command["params"]["awaitPromise"], false);
        assert!(
            command["params"]["expression"]
                .as_str()
                .unwrap()
                .contains("hardwareConcurrency")
        );
        send_peer_success(&mut peer_ws, &command).await;
        assert!(
            timeout(Duration::from_millis(100), peer_ws.next())
                .await
                .is_err(),
            "worker targets that are not waiting should not receive resume commands"
        );

        peer_ws.close(None).await.unwrap();
        let result = timeout(Duration::from_secs(1), handle)
            .await
            .expect("browser persona event loop should exit")
            .expect("event-loop task should not panic");
        result.unwrap();
    }

    #[test]
    fn collect_attached_target_event_reports_partial_events_but_ignores_noise() {
        let mut pending = VecDeque::new();
        collect_attached_target_event(&Message::Binary(vec![1, 2, 3]), &mut pending).unwrap();
        collect_attached_target_event(&Message::Text("not-json".to_string()), &mut pending)
            .unwrap();
        collect_attached_target_event(
            &Message::Text(json!({"method": "Runtime.consoleAPICalled"}).to_string()),
            &mut pending,
        )
        .unwrap();
        assert!(pending.is_empty());

        let err = collect_attached_target_event(
            &Message::Text(json!({"method": "Target.attachedToTarget"}).to_string()),
            &mut pending,
        )
        .unwrap_err();
        assert!(err.to_string().contains("missing params"));

        let err = collect_attached_target_event(
            &Message::Text(json!({"method": "Target.attachedToTarget", "params": {}}).to_string()),
            &mut pending,
        )
        .unwrap_err();
        assert!(err.to_string().contains("missing sessionId"));

        collect_attached_target_event(
            &Message::Text(
                json!({"method": "Target.attachedToTarget", "params": {"sessionId": "partial-session"}})
                    .to_string(),
            ),
            &mut pending,
        )
        .unwrap();
        assert_eq!(
            pending.pop_front().unwrap(),
            PendingAttachment {
                session_id: "partial-session".to_string(),
                target_type: String::new(),
                waiting_for_debugger: false,
            }
        );
    }

    #[tokio::test]
    async fn start_persona_guard_surfaces_page_version_and_browser_setup_errors() {
        let connect_server = MockCdpServer::spawn().await;
        let closed_addr = unused_socket_addr().await;
        connect_server
            .set_list_response(MockEndpointResponse::Json(
                StatusCode::OK,
                json!([{"type": "page", "webSocketDebuggerUrl": format!("ws://{closed_addr}/page")}]),
            ))
            .await;
        let err = start_persona_guard(&connect_server.base_url, &BrowserPersona::default(), None)
            .await
            .unwrap_err();
        assert!(
            err.to_string()
                .contains("connect CDP persona guard websocket")
        );
        connect_server.stop().await;

        let page_error_server = MockCdpServer::spawn().await;
        page_error_server
            .enqueue_page_reply(WsReply::Error(json!({"message": "persona denied"})))
            .await;
        let err = start_persona_guard(
            &page_error_server.base_url,
            &BrowserPersona::default(),
            None,
        )
        .await
        .unwrap_err();
        assert!(err.to_string().contains("CDP command failed"));
        page_error_server.stop().await;

        let version_error_server = MockCdpServer::spawn().await;
        version_error_server
            .set_version_response(MockEndpointResponse::Text(
                StatusCode::BAD_GATEWAY,
                "bad gateway".to_string(),
            ))
            .await;
        let err = start_persona_guard(
            &version_error_server.base_url,
            &BrowserPersona::default(),
            None,
        )
        .await
        .unwrap_err();
        assert!(
            err.to_string()
                .contains("fetch CDP version for browser persona guard")
        );
        version_error_server.stop().await;

        let browser_error_server = MockCdpServer::spawn().await;
        browser_error_server
            .enqueue_browser_reply(WsReply::Error(json!({"message": "discover denied"})))
            .await;
        let err = start_persona_guard(
            &browser_error_server.base_url,
            &BrowserPersona::default(),
            None,
        )
        .await
        .unwrap_err();
        assert!(err.to_string().contains("enable CDP target discovery"));
        browser_error_server.stop().await;
    }

    #[tokio::test]
    async fn evaluate_json_surfaces_exception_details() {
        let server = MockCdpServer::spawn().await;
        server
            .enqueue_page_reply(WsReply::Success(json!({
                "exceptionDetails": {"text": "boom"},
                "result": {"type": "undefined"}
            })))
            .await;

        let err = evaluate_json(&server.base_url, "throw new Error('boom')")
            .await
            .unwrap_err();

        assert!(err.to_string().contains("Runtime.evaluate failed"));
        server.stop().await;
    }

    #[tokio::test]
    async fn navigate_and_evaluate_json_use_page_cdp_target() {
        let server = MockCdpServer::spawn().await;
        server
            .enqueue_page_reply(WsReply::Success(json!({"frameId": "main"})))
            .await;
        server
            .enqueue_page_reply(WsReply::Success(json!({
                "result": {"type": "object", "value": {"ok": true}}
            })))
            .await;

        navigate(&server.base_url, "https://example.com")
            .await
            .unwrap();
        let value = evaluate_json(&server.base_url, "({ok: true})")
            .await
            .unwrap();

        assert_eq!(value, json!({"ok": true}));
        let commands = server.recorded_commands().await;
        assert_eq!(commands[0].method, "Page.navigate");
        assert_eq!(commands[0].params["url"], "https://example.com");
        assert_eq!(commands[1].method, "Runtime.evaluate");
        assert_eq!(commands[1].params["awaitPromise"], true);
        assert_eq!(commands[1].params["returnByValue"], true);

        server.stop().await;
    }

    #[tokio::test]
    async fn credential_field_context_treats_invalid_selector_as_missing_field() {
        let server = MockCdpServer::spawn().await;
        server
            .enqueue_page_reply(WsReply::Success(json!({"result": {"value": {
                "observed_origin": "https://example.test",
                "username_present": false,
                "password_present": true
            }}})))
            .await;

        let context = credential_field_context(&server.base_url, Some("input["), Some("#pass"))
            .await
            .unwrap();

        assert_eq!(context.observed_origin, "https://example.test");
        assert!(!context.username_present);
        assert!(context.password_present);
        assert!(!context.has_requested_fields(Some("input["), Some("#pass")));
        let commands = server.recorded_commands().await;
        assert_eq!(commands.len(), 1);
        let expression = commands[0].params["expression"].as_str().unwrap();
        assert!(expression.contains("try {"));
        assert!(expression.contains("catch (_)"));
        assert!(expression.contains("document.querySelector(selector)"));
        assert!(expression.contains("input["));

        server.stop().await;
    }

    #[test]
    fn credential_field_context_requires_each_requested_field_to_be_present() {
        let missing_username = CredentialFieldContext {
            observed_origin: "https://example.test".to_string(),
            username_present: false,
            username_usable: false,
            password_present: true,
            password_usable: true,
            top_frame: true,
            same_origin_frame: true,
            unsafe_reason: Some("username_field_missing".to_string()),
        };
        assert!(!missing_username.has_requested_fields(Some("#user"), Some("#pass")));
        assert!(missing_username.has_requested_fields(None, Some("#pass")));
        assert!(!missing_username.has_requested_fields(None, None));

        let present = CredentialFieldContext {
            observed_origin: "https://example.test".to_string(),
            username_present: true,
            username_usable: true,
            password_present: true,
            password_usable: true,
            top_frame: true,
            same_origin_frame: true,
            unsafe_reason: None,
        };
        assert!(present.has_requested_fields(Some("#user"), Some("#pass")));
    }

    #[test]
    fn user_agent_metadata_tracks_persona_platform_and_chrome_version() {
        let persona = BrowserPersona {
            locale: "fr-FR".into(),
            accept_language: "fr-FR,fr;q=0.9".into(),
            timezone_id: "Europe/Paris".into(),
            platform: "macOS 14.5 arm64".into(),
            user_agent: None,
            viewport: crate::models::Viewport {
                width: 1440,
                height: 900,
            },
            screen: crate::models::Viewport {
                width: 1440,
                height: 900,
            },
            device_scale_factor: 2.0,
            hardware_concurrency: 8,
            device_memory_gb: 8,
            max_touch_points: 0,
        };

        let identity = persona.resolved_identity(Some(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 \
             (KHTML, like Gecko) Chrome/126.0.6478.127 Safari/537.36",
        ));
        let metadata = user_agent_metadata(&persona, &identity);

        assert_eq!(metadata["brands"][0]["version"], "126");
        assert_eq!(metadata["fullVersionList"][0]["version"], "126.0.6478.127");
        assert_eq!(metadata["platform"], "macOS");
        assert_eq!(metadata["platformVersion"], "14.5");
        assert_eq!(metadata["architecture"], "arm");
        assert_eq!(metadata["bitness"], "64");
        assert_eq!(metadata["locale"], "fr-FR");
    }

    #[test]
    fn persona_init_script_includes_language_platform_screen_and_automation_overrides() {
        let persona = BrowserPersona {
            locale: "de-DE".into(),
            accept_language: "de-DE,de;q=0.9,en;q=0.7".into(),
            timezone_id: "Europe/Berlin".into(),
            platform: "Linux x86_64".into(),
            user_agent: None,
            viewport: crate::models::Viewport {
                width: 1366,
                height: 768,
            },
            screen: crate::models::Viewport {
                width: 1920,
                height: 1080,
            },
            device_scale_factor: 1.25,
            hardware_concurrency: 8,
            device_memory_gb: 8,
            max_touch_points: 0,
        };

        let script = persona_init_script(&persona);

        assert!(script.contains("de-DE"));
        assert!(script.contains("Navigator.prototype"));
        assert!(script.contains("Screen.prototype"));
        assert!(script.contains("1920"));
        assert!(script.contains("1.25"));
        assert!(script.contains("delete proto.webdriver"));
        assert!(script.contains("delete nav.webdriver"));
        assert!(script.contains("Object.getOwnPropertyDescriptor"));
        assert!(script.contains("Reflect.getOwnPropertyDescriptor"));
        assert!(script.contains("objectCtor.prototype.hasOwnProperty"));
        assert!(!script.contains("token"));
    }

    #[test]
    fn persona_init_script_contains_hardware_visualviewport_outer_and_matchmedia_surfaces() {
        let persona = BrowserPersona {
            hardware_concurrency: 4,
            device_memory_gb: 8,
            max_touch_points: 0,
            ..BrowserPersona::default()
        };

        let script = persona_init_script(&persona);

        assert!(script.contains("hardwareConcurrency"));
        assert!(script.contains("deviceMemory"));
        assert!(script.contains("maxTouchPoints"));
        assert!(script.contains("outerWidth"));
        assert!(script.contains("outerHeight"));
        assert!(script.contains("visualViewport"));
        assert!(script.contains("matchMedia"));
    }

    #[test]
    fn target_type_persona_plan_routes_page_like_and_worker_like_targets() {
        let persona = BrowserPersona::default();

        let iframe = target_persona_command_plan("iframe", &persona, Some("Chrome/143.0.7499.40"));
        assert!(
            iframe
                .iter()
                .any(|command| command.method == "Page.addScriptToEvaluateOnNewDocument")
        );
        assert!(
            iframe
                .iter()
                .any(|command| command.method == "Emulation.setDeviceMetricsOverride")
        );

        for target_type in ["worker", "shared_worker", "service_worker"] {
            let worker =
                target_persona_command_plan(target_type, &persona, Some("Chrome/143.0.7499.40"));
            assert_eq!(
                worker.len(),
                1,
                "{target_type} should receive one worker-safe command"
            );
            assert_eq!(worker[0].method, "Runtime.evaluate");
            let expression = worker[0].params["expression"].as_str().unwrap();
            assert!(expression.contains("hardwareConcurrency"));
            assert!(expression.contains("deviceMemory"));
            assert!(
                !worker
                    .iter()
                    .any(|command| command.method.starts_with("Page."))
            );
            assert!(
                !worker
                    .iter()
                    .any(|command| command.method.starts_with("Emulation."))
            );
        }

        assert!(
            target_persona_command_plan("browser", &persona, Some("Chrome/143.0.7499.40"))
                .is_empty()
        );
    }

    #[test]
    fn key_definition_covers_all_supported_takeover_keys() {
        let cases = [
            ("tab", "Tab", "Tab", 9, None),
            ("return", "Enter", "Enter", 13, Some("\r")),
            ("esc", "Escape", "Escape", 27, None),
            ("backspace", "Backspace", "Backspace", 8, None),
            ("space", " ", "Space", 32, Some(" ")),
            ("up", "ArrowUp", "ArrowUp", 38, None),
            ("down", "ArrowDown", "ArrowDown", 40, None),
            ("left", "ArrowLeft", "ArrowLeft", 37, None),
            ("right", "ArrowRight", "ArrowRight", 39, None),
            ("pageup", "PageUp", "PageUp", 33, None),
            ("pagedown", "PageDown", "PageDown", 34, None),
            ("home", "Home", "Home", 36, None),
            ("end", "End", "End", 35, None),
            ("delete", "Delete", "Delete", 46, None),
        ];

        for (input, key, code, key_code, text) in cases {
            assert_eq!(
                key_definition(input).unwrap(),
                KeyDefinition {
                    key,
                    code,
                    key_code,
                    text,
                }
            );
        }
    }

    #[test]
    fn unsupported_takeover_key_is_rejected() {
        let err = key_definition("Meta").unwrap_err();
        assert!(err.to_string().contains("unsupported takeover key"));
    }

    #[test]
    fn key_event_params_only_include_text_for_keydown_events() {
        let enter = key_definition("Enter").unwrap();
        let key_down = key_event_params(enter, key_down_type(enter));
        let key_up = key_event_params(enter, "keyUp");
        let tab = key_definition("Tab").unwrap();

        assert_eq!(key_down["type"], "keyDown");
        assert_eq!(key_down["text"], "\r");
        assert_eq!(
            key_event_params(tab, key_down_type(tab))["type"],
            "rawKeyDown"
        );
        assert!(key_up.get("text").is_none());
        assert_eq!(key_up["type"], "keyUp");
    }

    #[test]
    fn base64_decode_rejects_invalid_payload() {
        let err = base64_decode("not-base64").unwrap_err();
        assert!(err.to_string().contains("decode screenshot"));
    }

    #[tokio::test]
    async fn first_page_ws_url_requires_a_page_target() {
        let server = MockCdpServer::spawn().await;
        server
            .set_list_response(MockEndpointResponse::Json(
                StatusCode::OK,
                json!([{"type": "service_worker"}]),
            ))
            .await;

        let err = first_page_ws_url(&server.base_url).await.unwrap_err();
        assert!(
            err.to_string()
                .contains("no page target with websocket debugger url")
        );

        server.stop().await;
    }

    #[tokio::test]
    async fn capture_screenshot_requires_data_field() {
        let server = MockCdpServer::spawn().await;
        server.enqueue_page_reply(WsReply::Success(json!({}))).await;

        let err = capture_screenshot_png(&server.base_url).await.unwrap_err();
        assert!(
            err.to_string()
                .contains("Page.captureScreenshot returned no data")
        );

        server.stop().await;
    }

    #[tokio::test]
    async fn http_helpers_surface_text_parse_and_status_failures() {
        let server = MockCdpServer::spawn().await;
        server
            .set_version_response(MockEndpointResponse::Text(
                StatusCode::OK,
                "not-json".to_string(),
            ))
            .await;
        let err = fetch_version(&server.base_url).await.unwrap_err();
        assert!(err.to_string().contains("parse /json/version"));

        server
            .set_new_response(MockEndpointResponse::Text(
                StatusCode::BAD_REQUEST,
                "bad new target".to_string(),
            ))
            .await;
        let err = open_new_page(&server.base_url, "about:blank")
            .await
            .unwrap_err();
        assert!(err.to_string().contains("/json/new status"));

        server.stop().await;
    }

    #[tokio::test]
    async fn http_helpers_surface_version_status_list_parse_and_transport_failures() {
        let version_server = MockCdpServer::spawn().await;
        version_server
            .set_version_response(MockEndpointResponse::Text(
                StatusCode::BAD_GATEWAY,
                "bad gateway".to_string(),
            ))
            .await;
        let err = fetch_version(&version_server.base_url).await.unwrap_err();
        assert!(err.to_string().contains("/json/version status"));
        version_server.stop().await;

        let list_server = MockCdpServer::spawn().await;
        list_server
            .set_list_response(MockEndpointResponse::Text(
                StatusCode::OK,
                "not-json".to_string(),
            ))
            .await;
        let err = first_page_ws_url(&list_server.base_url).await.unwrap_err();
        assert!(err.to_string().contains("parse /json/list"));
        list_server.stop().await;

        let closed_addr = unused_socket_addr().await;
        let err = open_new_page(&format!("http://{closed_addr}"), "about:blank")
            .await
            .unwrap_err();
        assert!(err.to_string().contains("open /json/new"));
    }

    #[tokio::test]
    async fn send_command_surfaces_protocol_errors_and_invalid_json() {
        let server = MockCdpServer::spawn().await;
        server
            .enqueue_page_reply(WsReply::Error(json!({"message": "boom"})))
            .await;
        let err = insert_text(&server.base_url, "hello").await.unwrap_err();
        assert!(err.to_string().contains("CDP command failed"));

        server.clear_recorded_commands().await;
        server.enqueue_page_reply(WsReply::InvalidJson).await;
        let err = click(&server.base_url, 1.0, 2.0).await.unwrap_err();
        assert!(err.to_string().contains("parse CDP frame"));

        server.stop().await;
    }

    #[tokio::test]
    async fn public_helpers_surface_nested_cdp_failures() {
        let screenshot_server = MockCdpServer::spawn().await;
        screenshot_server
            .enqueue_page_reply(WsReply::Error(json!({"message": "no screenshot"})))
            .await;
        let err = capture_screenshot_png(&screenshot_server.base_url)
            .await
            .unwrap_err();
        assert!(err.to_string().contains("CDP command failed"));
        screenshot_server.stop().await;

        let click_server = MockCdpServer::spawn().await;
        click_server
            .enqueue_page_reply(WsReply::Success(json!({})))
            .await;
        click_server
            .enqueue_page_reply(WsReply::Error(json!({"message": "mouse up failed"})))
            .await;
        let err = click(&click_server.base_url, 1.0, 2.0).await.unwrap_err();
        assert!(err.to_string().contains("CDP command failed"));
        click_server.stop().await;

        let scroll_server = MockCdpServer::spawn().await;
        scroll_server
            .enqueue_page_reply(WsReply::Error(json!({"message": "wheel failed"})))
            .await;
        let err = scroll(&scroll_server.base_url, 1.0, 2.0).await.unwrap_err();
        assert!(err.to_string().contains("CDP command failed"));
        scroll_server.stop().await;
    }

    #[tokio::test]
    async fn press_key_surfaces_lookup_and_dispatch_failures() {
        let invalid_key_server = MockCdpServer::spawn().await;
        let err = press_key(&invalid_key_server.base_url, "meta")
            .await
            .unwrap_err();
        assert!(err.to_string().contains("unsupported takeover key"));
        invalid_key_server.stop().await;

        let keydown_server = MockCdpServer::spawn().await;
        keydown_server
            .enqueue_page_reply(WsReply::Error(json!({"message": "key down failed"})))
            .await;
        let err = press_key(&keydown_server.base_url, "tab")
            .await
            .unwrap_err();
        assert!(err.to_string().contains("CDP command failed"));
        keydown_server.stop().await;

        let keyup_server = MockCdpServer::spawn().await;
        keyup_server
            .enqueue_page_reply(WsReply::Success(json!({})))
            .await;
        keyup_server
            .enqueue_page_reply(WsReply::Error(json!({"message": "key up failed"})))
            .await;
        let err = press_key(&keyup_server.base_url, "tab").await.unwrap_err();
        assert!(err.to_string().contains("CDP command failed"));
        keyup_server.stop().await;
    }

    #[tokio::test]
    async fn send_command_surfaces_connect_send_and_read_failures() {
        let closed_addr = unused_socket_addr().await;
        let err = send_command(
            &format!("ws://{closed_addr}/devtools/page/main"),
            "Runtime.evaluate",
            json!({}),
        )
        .await
        .unwrap_err();
        assert!(err.to_string().contains("connect CDP websocket"));

        let mut write_error_ws =
            WebSocketStream::from_raw_socket(WriteErrorStream, Role::Client, None).await;
        let err = send_command_over_websocket(&mut write_error_ws, "Runtime.evaluate", json!({}))
            .await
            .unwrap_err();
        assert!(err.to_string().contains("send CDP command"));

        let mut read_error_ws =
            WebSocketStream::from_raw_socket(ReadErrorStream::default(), Role::Client, None).await;
        let err = send_command_over_websocket(&mut read_error_ws, "Runtime.evaluate", json!({}))
            .await
            .unwrap_err();
        assert!(err.to_string().contains("read CDP frame"));
    }

    #[tokio::test]
    async fn send_command_ignores_binary_frames_and_reports_closed_sockets() {
        let server = MockCdpServer::spawn().await;
        server
            .enqueue_page_reply(WsReply::BinaryThenSuccess(json!({})))
            .await;
        scroll(&server.base_url, 1.0, 2.0).await.unwrap();

        server.clear_recorded_commands().await;
        server
            .enqueue_page_reply(WsReply::CloseBeforeResponse)
            .await;
        let err = insert_text(&server.base_url, "hello").await.unwrap_err();
        assert!(
            err.to_string()
                .contains("CDP websocket closed before response")
        );

        server.clear_recorded_commands().await;
        server
            .enqueue_browser_reply(WsReply::EventThenSuccess(json!({})))
            .await;
        browser_close(&server.browser_ws_url).await.unwrap();

        server.stop().await;
    }
}
