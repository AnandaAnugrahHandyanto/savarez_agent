"""
Alert Enrichment — Webhook Receiver
===================================
Flask app that receives alerts from Opsgenie (or mock lab) and
immediately processes them through the enrichment pipeline.

Each alert is processed synchronously: receive → enrich (NetBox + LLM) → Telegram.

No buffering. No cron. No separate processor process.
"""

import os
import sys
import json
import threading
import werkzeug.exceptions
from flask import Flask, request, jsonify

# Import the enrichment pipeline
from alert_processor import enrich_alert_from_dict, AlertRecord

app = Flask(__name__)

# Processing lock to prevent concurrent access to shared resources
_processing_lock = threading.Lock()


def _checkmk_state_to_severity(state: str) -> str:
    """Map Checkmk state strings to internal severity labels."""
    state = (state or "").upper()
    if state in ("CRIT", "CRITICAL", "DOWN", "UNREACHABLE"):
        return "critical"
    if state in ("WARN", "WARNING"):
        return "warning"
    if state in ("OK", "UP", "RECOVERY"):
        return "ok"
    return "unknown"


def _librenms_to_severity(msg: str) -> str:
    """Infer severity from LibreNMS alert message content."""
    msg_lower = (msg or "").lower()
    if any(k in msg_lower for k in ("down", "unreachable", "critical", "lost", "fail")):
        return "critical"
    if any(k in msg_lower for k in ("warn", "warning", "degraded", "recovery")):
        return "warning"
    return "info"


# ────────────────────────────────────────────────────────────────
# WEBHOOK ENDPOINT
# ────────────────────────────────────────────────────────────────

@app.route("/alerts", methods=["POST"])
def receive_alert():
    """
    POST /alerts — single synchronous alert processor.

    THREE SOURCE FORMATS DETECTED:

    1. MOCK LAB (single alert):
         {"alert_id": "STRESS-01", "device": "DC1-BORDER-01", ...}
         → enrich_alert_from_dict(alert_dict, source="mock_lab")

    2. MOCK LAB (batch):
         {"alerts": [{"alert_id": ...}, {"alert_id": ...}]}
         → processes ALL alerts, returns count in response

    3. OPSGENIE (production):
         {"action": "Create", "alert": {"alertID": "...", "alias": "HOSTNAME", ...}}
         → enrich_alert_from_dict(alert_dict, source="opsgenie")
         → non-Create actions (Ack, Resolve, etc.) → 200 OK, ignored

    WHY SYNCHRONOUS:
        Opsgenie expects an HTTP response code to decide whether to retry.
        Returning 200 = "processed successfully, don't retry".
        Returning 500 = "failed, retry".
        Since the LLM call is idempotent for the same input, retries are safe.

    RETURN CODES:
        200 — Telegram dispatch succeeded (or non-Create action acknowledged)
        400 — malformed JSON or unknown payload format
        500 — Telegram dispatch failed (NetBox error, LLM error, network error)
    """
    try:
        # Checkmk sends application/x-www-form-urlencoded (not JSON).
        # Flask's request.form parses it into a MultiDict; request.json
        # handles JSON bodies. We merge both so the dispatcher sees a
        # flat dict regardless of content-type.
        # NOTE: request.form.to_dict(flat=True) is critical — dict(request.form)
        # returns values as lists, breaking all the payload.get("key") calls.
        form_data = request.form.to_dict(flat=True) if request.form else {}
        # Use silent=True to avoid 400 if Content-Type is JSON but body is empty
        # (happens with LibreNMS which sends ?title=...&msg=... in query params).
        json_data = request.get_json(force=False, silent=True) or {}
        # Merge: form fields override JSON fields (Checkmk's context=JSON
        # field should take precedence over any flat JSON fields)
        payload = {**json_data, **form_data}
        # LibreNMS sends data in query params (?title=...&msg=...) with no body.
        # Merge request.args so query params are also captured.
        if request.args:
            payload = {**payload, **request.args.to_dict()}
    except werkzeug.exceptions.BadRequest as e:
        print(f"[Webhook] Payload parse error (BadRequest): {e}", flush=True)
        return jsonify({"status": "error", "message": "Invalid payload"}), 400
    except Exception as e:
        print(f"[Webhook] Payload parse error: {e}", flush=True)
        return jsonify({"status": "error", "message": "Invalid payload"}), 400

    if not payload:
        print(f"[Webhook] Empty payload — is_json={request.is_json}, form_keys={list(request.form.keys())}, args_keys={list(request.args.keys())}", flush=True)
        return jsonify({"status": "error", "message": "Empty payload"}), 400

    # DEBUG: log raw payload to understand what Checkmk actually sends
    print(f"[Webhook] RAW payload keys={list(payload.keys())} is_json={request.is_json} content_type={request.content_type}", flush=True)

    # Detect source format
    if "action" in payload and "alert" in payload:
        # Opsgenie format
        alert_dict = payload.get("alert", {})
        action = payload.get("action", "")
        if action != "Create":
            return jsonify({"status": "ok", "note": f"action={action} — acknowledged"}), 200
        source = "opsgenie"
    elif "title" in payload and "msg" in payload:
        # LibreNMS webhook format — title + msg in query params
        # Maps to internal alert dict
        alert_dict = {
            "alert_id": f"librenms-{payload.get('title', '')}-{payload.get('timestamp', '')}",
            "device": payload.get("hostname", payload.get("title", "").split()[0] if payload.get("title") else ""),
            "alert_type": "librenms",
            "severity": _librenms_to_severity(payload.get("msg", "")),
            "message": f"{payload.get('title', '')}: {payload.get('msg', '')}",
            "site": "",
            "timestamp": payload.get("timestamp", ""),
            "raw_payload": payload,
        }
        source = "librenms"
    elif "context" in payload or "host_name" in payload:
        # Checkmk alert handler format (application/x-www-form-urlencoded)
        alert_dict = payload
        source = "checkmk"
    elif "alert_id" in payload or "alerts" in payload:
        # Mock lab format — but also check for Checkmk Python script format
        # (checkmk-webhook-hermes.py sends {alert_id, device, alert_type, severity,
        #  message, site, timestamp, _checkmk: {...}} — has _checkmk key = Checkmk)
        if "_checkmk" in payload:
            # Checkmk Python notification script format
            alert_dict = payload
            source = "checkmk"
        elif "alerts" in payload:
            # Batch format from mock lab
            results = []
            for a in payload.get("alerts", []):
                result = enrich_alert_from_dict(a, source="mock_lab")
                results.append(result)
            total = len(results)
            sent = sum(1 for r in results if r.get("sent"))
            print(f"[Webhook] Mock lab batch: {sent}/{total} Telegram dispatches", flush=True)
            return jsonify({"status": "ok", "total": total, "sent": sent, "results": results}), 200
        else:
            # Single mock lab alert
            alert_dict = payload
            source = "mock_lab"
    elif "what" in payload and "notification_type" in payload and "host" in payload:
        # Checkmk webhook JSON format (application/json, not form-encoded)
        # Maps Checkmk JSON → internal alert dict
        checkmk = payload
        host_info = checkmk.get("host", {})
        svc_info = checkmk.get("service")
        alert_dict = {
            # Standard fields the processor expects
            "alert_id": checkmk.get("incident", {}).get("id") or checkmk.get("timing", {}).get("unix_timestamp") or "",
            "device": host_info.get("name", ""),
            "description": svc_info.get("output") if svc_info else (host_info.get("output") or checkmk.get("description", "")),
            "severity": _checkmk_state_to_severity(
                svc_info.get("state") if svc_info else host_info.get("state", "")
            ),
            # Full Checkmk context for enrichment
            "_checkmk": checkmk,
        }
        source = "checkmk"
    else:
        return jsonify({"status": "error", "message": "Unknown payload format"}), 400

    # Process the alert synchronously
    try:
        result = enrich_alert_from_dict(alert_dict, source=source)
    except Exception as e:
        print(f"[Webhook] Processing error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

    status_code = 200 if result.get("sent") else 500
    return jsonify({
        "status": "ok" if result.get("sent") else "error",
        "alert_id": result.get("alert_id"),
        "device": result.get("device"),
        "severity": result.get("severity"),
        "sent": result.get("sent"),
        "briefing_length": len(result.get("briefing", "")),
    }), status_code


# ────────────────────────────────────────────────────────────────
# STATUS ENDPOINT
# ────────────────────────────────────────────────────────────────

@app.route("/alerts/status", methods=["GET"])
def status():
    """Basic health check."""
    return jsonify({
        "status": "ok",
        "service": "alert-enrichment",
        "mode": "synchronous"
    })


# ────────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("WEBHOOK_PORT", 5001))
    print(f"[Webhook Receiver] Starting on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
