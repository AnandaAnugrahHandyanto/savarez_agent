from hermes_cli.auth import AuthError, format_auth_error


def test_format_auth_error_handles_canonical_nous_billing_access_code(monkeypatch):
    monkeypatch.setattr(
        "hermes_cli.nous_account.get_nous_portal_account_info",
        lambda force_fresh=True: None,
    )

    rendered = format_auth_error(
        AuthError(
            "billing access required",
            provider="nous",
            code="billing_access_required",
            relogin_required=False,
        )
    )

    assert "subscription required" not in rendered.lower()
    assert "entitlement" in rendered.lower()
    assert "billing" in rendered.lower()


def test_format_auth_error_non_nous_subscription_code_uses_billing_access_copy():
    rendered = format_auth_error(
        AuthError(
            "subscription required",
            provider="example",
            code="subscription_required",
            relogin_required=False,
        )
    )

    assert rendered == "Billing access is required. Select an eligible org, add credits, or activate billing, then retry."
