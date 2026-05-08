from hermes_cli.nous_account import (
    format_nous_billing_guidance_lines,
    parse_nous_account_status,
)


def test_paid_access_requires_positive_usable_credits_even_with_subscription():
    status = parse_nous_account_status(
        {
            "subscription": {"plan": "Plus", "monthly_charge": 20, "credits_remaining": 0},
            "purchased_credits_remaining": 0,
            "paid_service_access": {
                "paid_access": False,
                "has_active_subscription": True,
                "active_subscription_is_paid": True,
                "total_usable_credits": 0,
                "subscription_credits_remaining": 0,
                "purchased_credits_remaining": 0,
            },
        },
        portal_base_url="https://portal.example.com",
    )

    assert status.available is True
    assert status.paid_access is False
    assert status.has_active_subscription is True
    assert status.total_usable_credits == 0
    assert any("Top up credits" in line for line in format_nous_billing_guidance_lines(status))


def test_purchased_credits_grant_paid_access_without_subscription():
    status = parse_nous_account_status(
        {
            "subscription": None,
            "purchased_credits_remaining": 12.5,
            "paid_service_access": {
                "paid_access": True,
                "has_active_subscription": False,
                "total_usable_credits": 12.5,
                "purchased_credits_remaining": 12.5,
            },
        }
    )

    assert status.paid_access is True
    assert status.has_active_subscription is False
    assert status.total_usable_credits == 12.5


def test_billing_guidance_recommends_subscription_when_none_active():
    status = parse_nous_account_status(
        {
            "subscription": None,
            "purchased_credits_remaining": 0,
            "paid_service_access": {
                "paid_access": False,
                "has_active_subscription": False,
                "total_usable_credits": 0,
            },
        },
        portal_base_url="https://portal.example.com",
    )

    lines = format_nous_billing_guidance_lines(status)

    assert any("does not have an active subscription" in line for line in lines)
    assert "https://portal.example.com/billing" in "\n".join(lines)
