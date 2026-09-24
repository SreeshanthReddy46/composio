import pytest
from src.research.schema import (
    AppRecord,
    EvidenceField,
    ConfidenceLevel,
    AuthMethod,
    ApiStyle,
    Verdict,
)
from src.research.checks import (
    verify_quote_in_text,
    validate_enums,
    run_deterministic_checks,
)


def test_verify_quote_in_text():
    text = "Notion API uses OAuth 2.0 and Internal Integration Tokens for authentication."
    assert verify_quote_in_text("OAuth 2.0 and Internal Integration Tokens", text) is True
    assert verify_quote_in_text("oauth 2.0", text) is True
    assert verify_quote_in_text("Basic HTTP Auth only", text) is False
    assert verify_quote_in_text("", text) is False


def test_validate_enums_valid():
    record = AppRecord(
        id="notion",
        name="Notion",
        auth_methods=EvidenceField(value=[AuthMethod.OAUTH2.value]),
        api_style=EvidenceField(value=ApiStyle.REST.value),
        self_serve=EvidenceField(value="free_self_serve"),
        verdict=EvidenceField(value=Verdict.SHIP_NOW.value),
    )
    errors = validate_enums(record)
    assert len(errors) == 0


def test_validate_enums_invalid():
    record = AppRecord(
        id="bad_app",
        name="Bad App",
        auth_methods=EvidenceField(value=["magic_auth"]),
        api_style=EvidenceField(value="super_rest"),
        self_serve=EvidenceField(value="invalid_tier"),
        verdict=EvidenceField(value="almost_there"),
    )
    errors = validate_enums(record)
    assert len(errors) == 4


def test_run_deterministic_checks_downgrades_confidence():
    sources = {"https://developers.notion.com": "We support OAuth 2.0 authentication."}
    record = AppRecord(
        id="notion",
        name="Notion",
        auth_methods=EvidenceField(
            value=["oauth2"],
            evidence_url="https://developers.notion.com",
            quote="We support OAuth 2.0 authentication.",
            confidence=ConfidenceLevel.HIGH,
        ),
        webhooks=EvidenceField(
            value=True,
            evidence_url="https://developers.notion.com/missing-url", # Missing from sources!
            quote="Webhooks are delivered in realtime.",              # Missing from text!
            confidence=ConfidenceLevel.HIGH,
        ),
    )

    checked_record, failures = run_deterministic_checks(record, sources)
    # Auth methods should pass
    assert checked_record.auth_methods.confidence == ConfidenceLevel.HIGH
    # Webhooks failed URL and quote check -> confidence downgraded
    assert checked_record.webhooks.confidence in (ConfidenceLevel.LOW, ConfidenceLevel.UNKNOWN)
    assert len(failures) >= 1
