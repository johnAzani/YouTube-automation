from __future__ import annotations

from scripts.studio_autopilot import check_zero_dollar_lock


def test_local_cost_audit_does_not_claim_external_billing_is_verified() -> None:
    report = check_zero_dollar_lock()
    assert report["status"] == "account_side_billing_unverified"
    assert report["monthly_cost_usd"] is None
    assert report["billing_disabled_verified"] is False
    assert "10 requests/day" in report["tts_limit"]
    assert "cannot be inspected" in report["tts_cost"]
