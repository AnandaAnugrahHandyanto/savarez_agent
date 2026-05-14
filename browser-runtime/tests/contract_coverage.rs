use std::str::FromStr;

use axum::{
    Json, Router,
    extract::{Path, State},
    routing::{get, post},
};
use chrono::Utc;
use hermes_browser_runtime::{
    client::BrowserRuntimeClient,
    credentials::{CredentialBrokerMode, CredentialFillStatus},
    models::{
        BrowserPersona, CaptchaPolicy, CaptchaReportState, CaptchaResolveOutcome, CaptchaStatus,
        CleanupArtifactsRequest, CredentialDecisionRequest, CredentialFillStartRequest,
        CredentialFillStatusRecord, CredentialPrivacyGuardResponse, GpuPolicy, WebRtcIpPolicy,
        chrome_full_version_from_user_agent, chrome_major_version, client_hint_architecture,
        client_hint_bitness, client_hint_platform, client_hint_platform_version,
        extract_chrome_full_version,
    },
};
use serde_json::json;
use tokio::{net::TcpListener, sync::oneshot};
use uuid::Uuid;

#[derive(Clone, Default)]
struct Capture {
    bodies: std::sync::Arc<std::sync::Mutex<Vec<serde_json::Value>>>,
}

fn credential_record(
    session_id: Uuid,
    request_id: Uuid,
    status: CredentialFillStatus,
) -> CredentialFillStatusRecord {
    CredentialFillStatusRecord {
        request_id,
        session_id,
        alias: "demo-login".into(),
        observed_origin: "https://example.test".into(),
        status,
        broker: CredentialBrokerMode::Mock,
        audit_id: Uuid::new_v4(),
        privacy_guard_active: false,
        created_at: Utc::now(),
        updated_at: Utc::now(),
        redacted_message: None,
    }
}

#[tokio::test]
async fn public_client_credential_methods_send_contract_json_and_parse_responses() {
    let capture = Capture::default();
    let session_id = Uuid::new_v4();
    let request_id = Uuid::new_v4();
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let base_url = format!("http://{}", listener.local_addr().unwrap());
    let (shutdown_tx, shutdown_rx) = oneshot::channel();
    let server_capture = capture.clone();

    let task = tokio::spawn(async move {
        axum::serve(
            listener,
            Router::new()
                .route(
                    "/sessions/:session_id/credentials/fill",
                    post(
                        move |State(capture): State<Capture>,
                              Path(session_id): Path<Uuid>,
                              Json(body): Json<serde_json::Value>| async move {
                            capture.bodies.lock().unwrap().push(body);
                            Json(credential_record(
                                session_id,
                                request_id,
                                CredentialFillStatus::RequiresUserApproval,
                            ))
                        },
                    ),
                )
                .route(
                    "/sessions/:session_id/credentials/fill/:request_id",
                    get(
                        |Path((session_id, request_id)): Path<(Uuid, Uuid)>| async move {
                            Json(credential_record(
                                session_id,
                                request_id,
                                CredentialFillStatus::RequiresUserApproval,
                            ))
                        },
                    ),
                )
                .route(
                    "/sessions/:session_id/credentials/fill/:request_id/approve",
                    post(
                        |State(capture): State<Capture>,
                         Path((session_id, request_id)): Path<(Uuid, Uuid)>,
                         Json(body): Json<serde_json::Value>| async move {
                            capture.bodies.lock().unwrap().push(body);
                            Json(credential_record(
                                session_id,
                                request_id,
                                CredentialFillStatus::Approved,
                            ))
                        },
                    ),
                )
                .route(
                    "/sessions/:session_id/credentials/fill/:request_id/deny",
                    post(
                        |State(capture): State<Capture>,
                         Path((session_id, request_id)): Path<(Uuid, Uuid)>,
                         Json(body): Json<serde_json::Value>| async move {
                            capture.bodies.lock().unwrap().push(body);
                            Json(credential_record(
                                session_id,
                                request_id,
                                CredentialFillStatus::Denied,
                            ))
                        },
                    ),
                )
                .route(
                    "/sessions/:session_id/credentials/privacy-guard/clear",
                    post(|Path(session_id): Path<Uuid>| async move {
                        Json(CredentialPrivacyGuardResponse {
                            session_id,
                            privacy_guard_active: false,
                        })
                    }),
                )
                .route(
                    "/sessions/:session_id/downloads",
                    get(|Path(session_id): Path<Uuid>| async move {
                        Json(json!({"session_id": session_id, "downloads": []}))
                    }),
                )
                .route(
                    "/sessions/:session_id/download",
                    get(|| async { b"download-bytes".to_vec() }),
                )
                .route(
                    "/artifacts/cleanup",
                    post(|Json(body): Json<serde_json::Value>| async move {
                        Json(json!({"deleted_count": 0, "dry_run": body["dry_run"]}))
                    }),
                )
                .with_state(server_capture),
        )
        .with_graceful_shutdown(async {
            let _ = shutdown_rx.await;
        })
        .await
        .unwrap();
    });

    let client = BrowserRuntimeClient::new(&base_url, Some("secret-token".into())).unwrap();
    let fill = client
        .credential_fill(
            session_id,
            &CredentialFillStartRequest {
                alias: "demo-login".into(),
                username_selector: Some("#user".into()),
                password_selector: Some("#pass".into()),
                purpose: Some("login".into()),
                expected_origin: Some("https://example.test".into()),
            },
        )
        .await
        .unwrap();
    assert_eq!(fill.status, CredentialFillStatus::RequiresUserApproval);

    let status = client
        .credential_fill_status(session_id, request_id)
        .await
        .unwrap();
    assert_eq!(status.request_id, request_id);

    let approved = client
        .approve_credential_fill(session_id, request_id, Some("operator approved".into()))
        .await
        .unwrap();
    assert_eq!(approved.status, CredentialFillStatus::Approved);

    let denied = client
        .deny_credential_fill(session_id, request_id, Some("operator denied".into()))
        .await
        .unwrap();
    assert_eq!(denied.status, CredentialFillStatus::Denied);

    let guard = client
        .clear_credential_privacy_guard(session_id)
        .await
        .unwrap();
    assert!(!guard.privacy_guard_active);

    let downloads = client.list_downloads(session_id).await.unwrap();
    assert_eq!(downloads["session_id"], session_id.to_string());
    let downloaded = client.download(session_id, "file.txt").await.unwrap();
    assert_eq!(downloaded, b"download-bytes");
    let cleanup = client
        .cleanup_artifacts(&CleanupArtifactsRequest {
            dry_run: true,
            older_than_secs: Some(60),
        })
        .await
        .unwrap();
    assert_eq!(cleanup["dry_run"], true);

    let bodies = capture.bodies.lock().unwrap().clone();
    assert_eq!(bodies[0]["alias"], "demo-login");
    assert_eq!(bodies[0]["username_selector"], "#user");
    assert_eq!(bodies[0]["password_selector"], "#pass");
    assert_eq!(bodies[0]["purpose"], "login");
    assert_eq!(bodies[0]["expected_origin"], "https://example.test");
    assert_eq!(bodies[1]["note"], "operator approved");
    assert_eq!(bodies[2]["reason"], "operator denied");
    assert!(bodies[2].get("note").is_none());

    shutdown_tx.send(()).unwrap();
    task.await.unwrap();
}

#[test]
fn public_model_contract_helpers_cover_aliases_and_terminal_statuses() {
    let mut persona = BrowserPersona {
        platform: "Mac OS X 14.5".into(),
        user_agent: Some("HeadlessChrome/126.0.6478.114".into()),
        hardware_concurrency: 2,
        device_memory_gb: 1,
        max_touch_points: 11,
        ..BrowserPersona::default()
    };
    assert_eq!(
        persona.resolved_launch_user_agent(None).unwrap(),
        "Chrome/126.0.6478.114"
    );
    assert_eq!(persona.normalized_hardware_concurrency(), 2);
    assert_eq!(persona.normalized_device_memory_gb(), 1);
    assert_eq!(persona.normalized_max_touch_points(), 0);

    persona.user_agent = None;
    persona.platform = "Linux aarch64".into();
    persona.hardware_concurrency = 3;
    persona.device_memory_gb = 3;
    persona.max_touch_points = 7;
    let linux_launch = persona
        .resolved_launch_user_agent(Some("Chrome 127.0.1.2"))
        .unwrap();
    assert!(linux_launch.contains("Linux aarch64"));
    assert_eq!(persona.normalized_hardware_concurrency(), 4);
    assert_eq!(persona.normalized_device_memory_gb(), 4);
    assert_eq!(persona.normalized_max_touch_points(), 7);

    persona.platform = "Plan9 Mystery".into();
    assert!(
        persona
            .resolved_launch_user_agent(Some("not-a-version"))
            .is_none()
    );
    assert!(
        persona
            .resolved_user_agent(None)
            .contains("Chrome/125.0.0.0")
    );
    assert_eq!(client_hint_platform("Android 14"), "Android");
    assert_eq!(client_hint_platform("Something Weird 1.0"), "Something");
    assert_eq!(client_hint_platform_version("macOS 14.5 arm64"), "14.5");
    assert_eq!(client_hint_architecture("Linux aarch64"), "arm");
    assert_eq!(client_hint_architecture("Linux x86_64"), "x86");
    assert_eq!(client_hint_bitness("Linux x86_64"), "64");
    assert_eq!(client_hint_bitness("Linux armv7"), "");
    assert_eq!(
        extract_chrome_full_version("Chrome/128.0.6613.85"),
        Some("128.0.6613.85".into())
    );
    assert_eq!(
        extract_chrome_full_version("v129.0.0.1 stable"),
        Some("129.0.0.1".into())
    );
    assert_eq!(
        chrome_full_version_from_user_agent("Chromium/130.0.1.2"),
        Some("130.0.1.2".into())
    );
    assert_eq!(chrome_major_version("bad.version"), "125");

    assert_eq!(
        WebRtcIpPolicy::DefaultPublicInterfaceOnly.as_chrome_value(),
        "default_public_interface_only"
    );
    assert_eq!(
        WebRtcIpPolicy::DefaultPublicAndPrivateInterfaces.as_chrome_value(),
        "default_public_and_private_interfaces"
    );
    assert_eq!(
        WebRtcIpPolicy::DisableNonProxiedUdp.as_chrome_value(),
        "disable_non_proxied_udp"
    );
    assert_eq!(
        WebRtcIpPolicy::from_str("disable-non-proxied-udp").unwrap(),
        WebRtcIpPolicy::DisableNonProxiedUdp
    );
    assert!(
        WebRtcIpPolicy::from_str("unsafe")
            .unwrap_err()
            .contains("expected one")
    );

    assert_eq!(GpuPolicy::Auto.as_config_value(), "auto");
    assert_eq!(
        GpuPolicy::SwiftshaderCompat.as_config_value(),
        "swiftshader_compat"
    );
    assert_eq!(GpuPolicy::Disable3d.as_config_value(), "disable_3d");
    assert_eq!(
        GpuPolicy::from_str("disable-3d").unwrap(),
        GpuPolicy::Disable3d
    );
    assert!(
        GpuPolicy::from_str("turbo")
            .unwrap_err()
            .contains("expected one")
    );

    assert_eq!(CaptchaPolicy::HumanOnly.as_config_value(), "human_only");
    assert_eq!(CaptchaPolicy::ObserveOnly.as_config_value(), "observe_only");
    assert_eq!(CaptchaPolicy::Disabled.as_config_value(), "disabled");
    assert_eq!(
        CaptchaPolicy::from_str("observe-only").unwrap(),
        CaptchaPolicy::ObserveOnly
    );
    assert!(
        CaptchaPolicy::from_str("solve")
            .unwrap_err()
            .contains("expected one")
    );
    assert_eq!(
        CaptchaStatus::from(CaptchaReportState::Suspected),
        CaptchaStatus::Suspected
    );
    assert_eq!(
        CaptchaStatus::from(CaptchaReportState::HumanRequired),
        CaptchaStatus::HumanRequired
    );
    assert_eq!(
        CaptchaReportState::from_str("in-progress").unwrap(),
        CaptchaReportState::InProgress
    );
    assert_eq!(
        CaptchaStatus::from(CaptchaReportState::InProgress),
        CaptchaStatus::InProgress
    );
    assert_eq!(
        CaptchaResolveOutcome::from_str("dismissed").unwrap(),
        CaptchaResolveOutcome::Dismissed
    );
    assert_eq!(
        CaptchaStatus::from(CaptchaResolveOutcome::Resolved),
        CaptchaStatus::Resolved
    );
    assert_eq!(
        CaptchaStatus::from(CaptchaResolveOutcome::Failed),
        CaptchaStatus::Failed
    );
    assert_eq!(
        CaptchaStatus::from(CaptchaResolveOutcome::Dismissed),
        CaptchaStatus::Dismissed
    );
    for status in [
        CaptchaStatus::Suspected,
        CaptchaStatus::HumanRequired,
        CaptchaStatus::InProgress,
    ] {
        assert!(status.is_checkpoint());
    }
    for status in [
        CaptchaStatus::None,
        CaptchaStatus::Resolved,
        CaptchaStatus::Failed,
        CaptchaStatus::Dismissed,
    ] {
        assert!(!status.is_checkpoint());
    }

    let note = CredentialDecisionRequest {
        note: Some("approved".into()),
        reason: Some("denied".into()),
    };
    assert_eq!(note.operator_note(), Some("approved".into()));
    let reason = CredentialDecisionRequest {
        note: None,
        reason: Some("denied".into()),
    };
    assert_eq!(reason.operator_note(), Some("denied".into()));
    assert_eq!(
        serde_json::to_value(CredentialDecisionRequest {
            note: None,
            reason: Some("denied".into()),
        })
        .unwrap(),
        json!({"reason": "denied"})
    );

    let terminal = [
        CredentialFillStatus::Unavailable,
        CredentialFillStatus::Filled,
        CredentialFillStatus::Denied,
        CredentialFillStatus::NoMatch,
        CredentialFillStatus::OriginMismatch,
        CredentialFillStatus::PolicyBlocked,
        CredentialFillStatus::UnlockRequired,
        CredentialFillStatus::ProviderLocked,
        CredentialFillStatus::Failed,
    ];
    for status in terminal {
        assert!(credential_record(Uuid::new_v4(), Uuid::new_v4(), status).is_terminal());
    }
    for status in [
        CredentialFillStatus::RequiresUserApproval,
        CredentialFillStatus::Pending,
        CredentialFillStatus::Approved,
        CredentialFillStatus::PrivacyGuardActive,
    ] {
        assert!(!credential_record(Uuid::new_v4(), Uuid::new_v4(), status).is_terminal());
    }
}
