def _register_and_login(client, email: str):
    password = "Password123!"
    reg = client.post(
        "/api/auth/register",
        json={
            "company_name": "Acme Oy",
            "name": "Admin",
            "email": email,
            "password": password,
        },
    )
    assert reg.status_code in (200, 409), reg.text

    login = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_ask_idempotency_replays_same_response(client):
    headers = _register_and_login(client, "idempo@example.com")

    # seed one document so retrieval has material
    created = client.post(
        "/api/documents/text",
        headers=headers,
        json={
            "title": "Refund policy",
            "text": "Refunds are allowed within 14 days with original receipt.",
            "roles_allowed": ["admin", "manager", "employee", "viewer"],
            "groups_allowed": [],
            "tags": ["policy"],
            "classification": "internal",
            "source_url": "",
            "freshness_score": 0.9,
        },
    )
    assert created.status_code == 200, created.text

    payload = {
        "question": "What is our refund window?",
        "top_k": 5,
        "idempotency_key": "ask-123",
    }

    first = client.post("/api/ask", headers=headers, json=payload)
    assert first.status_code == 200, first.text
    first_json = first.json()

    second = client.post("/api/ask", headers=headers, json=payload)
    assert second.status_code == 200, second.text
    second_json = second.json()

    assert first_json["query_log_id"] == second_json["query_log_id"]
    assert first_json["run_id"] == second_json["run_id"]
    assert first_json["answer"] == second_json["answer"]


def test_policy_pack_update_and_usage_endpoint(client):
    headers = _register_and_login(client, "policy-pack@example.com")

    before = client.get("/api/policy", headers=headers)
    assert before.status_code == 200, before.text

    updated = client.put(
        "/api/policy",
        headers=headers,
        json={
            "policy_pack": "safe",
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["policy_pack"] == "safe"
    assert body["daily_query_budget"] >= 1
    assert body["max_top_k"] >= 1

    usage = client.get("/api/analytics/usage", headers=headers)
    assert usage.status_code == 200, usage.text
    usage_body = usage.json()
    assert "query_budget_remaining" in usage_body
    assert "run_budget_remaining" in usage_body
    assert "cost_budget_remaining_usd" in usage_body


def test_runs_endpoint_and_replay(client):
    headers = _register_and_login(client, "runs@example.com")

    created = client.post(
        "/api/documents/text",
        headers=headers,
        json={
            "title": "Billing FAQ",
            "text": "Invoices are sent at end of month.",
            "roles_allowed": ["admin", "manager", "employee", "viewer"],
            "groups_allowed": [],
            "tags": ["billing"],
            "classification": "internal",
            "source_url": "",
            "freshness_score": 0.8,
        },
    )
    assert created.status_code == 200, created.text

    ask_resp = client.post(
        "/api/ask",
        headers=headers,
        json={"question": "When are invoices sent?", "idempotency_key": "run-1"},
    )
    assert ask_resp.status_code == 200, ask_resp.text
    run_id = ask_resp.json()["run_id"]

    runs = client.get("/api/analytics/runs", headers=headers)
    assert runs.status_code == 200, runs.text
    rows = runs.json()
    assert any(r["id"] == run_id for r in rows)

    replay = client.post(f"/api/analytics/runs/{run_id}/replay", headers=headers)
    assert replay.status_code == 200, replay.text
    replay_json = replay.json()
    assert replay_json["success"] is True
    assert replay_json["source_run_id"] == run_id
    assert replay_json["replay_run_id"] != run_id


def test_audit_export_csv_and_healthz(client):
    headers = _register_and_login(client, "audit-export@example.com")

    ev = client.get("/api/audit/events/export?format=csv&limit=10", headers=headers)
    assert ev.status_code == 200, ev.text
    assert "text/csv" in ev.headers.get("content-type", "")
    assert "action" in ev.text

    health = client.get("/healthz")
    assert health.status_code == 200, health.text
    hb = health.json()
    assert hb["ok"] is True
    assert "ingestion_queue_depth" in hb
    assert "ingestion_dead_letter_count" in hb
