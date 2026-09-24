import pytest
from src.research.schema import (
    AppRecord,
    EvidenceField,
    EvidenceWrapper,
    ConfidenceLevel,
    AuthMethod,
    SelfServeTier,
    ApiStyle,
    ApiBreadth,
    Verdict,
)


def test_app_record_serialization():
    record = AppRecord(
        id="notion",
        name="Notion",
        category=EvidenceField(value="Productivity", confidence=ConfidenceLevel.HIGH),
        one_liner=EvidenceField(value="Connected workspace for docs and wikis"),
        auth_methods=EvidenceField(value=[AuthMethod.OAUTH2.value, AuthMethod.BEARER_TOKEN.value]),
        self_serve=EvidenceField(value=SelfServeTier.FREE_SELF_SERVE.value),
        api_style=EvidenceField(value=ApiStyle.REST.value),
        api_breadth=EvidenceField(value=ApiBreadth.LARGE.value),
        existing_mcp=EvidenceField(value="official", evidence_url="https://github.com/modelcontextprotocol/servers"),
        sandbox_available=EvidenceField(value=False),
        openapi_spec_available=EvidenceField(value=True, evidence_url="https://developers.notion.com/reference"),
        webhooks=EvidenceField(value=True),
        rate_limits_note=EvidenceField(value="3 requests per second avg"),
        free_tier_note=EvidenceField(value="Free plan available for individuals"),
        in_composio_already=EvidenceField(value=True),
        verdict=EvidenceField(value=Verdict.SHIP_NOW.value),
        main_blocker=EvidenceField(value="None"),
        difficulty_1_to_5=EvidenceField(value=2),
    )

    data = record.model_dump()
    assert data["id"] == "notion"
    assert data["category"]["value"] == "Productivity"
    assert data["category"]["confidence"] == "high"
    assert "oauth2" in data["auth_methods"]["value"]
    assert data["verdict"]["value"] == "ship_now"
    assert data["difficulty_1_to_5"]["value"] == 2


def test_evidence_wrapper_defaults():
    wrapper = EvidenceField(value="unknown")
    assert wrapper.confidence == ConfidenceLevel.UNKNOWN
    assert wrapper.evidence_url is None
    assert wrapper.quote is None
