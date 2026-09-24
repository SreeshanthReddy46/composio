from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional, Union
from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class AuthMethod(str, Enum):
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    BASIC = "basic"
    BEARER_TOKEN = "bearer_token"
    JWT = "jwt"
    OTHER = "other"
    NONE = "none"
    UNKNOWN = "unknown"


class SelfServeTier(str, Enum):
    FREE_SELF_SERVE = "free_self_serve"
    TRIAL_SELF_SERVE = "trial_self_serve"
    PAID_REQUIRED = "paid_required"
    APPROVAL_REQUIRED = "approval_required"
    PARTNERSHIP_OR_SALES_GATED = "partnership_or_sales_gated"
    UNKNOWN = "unknown"


class ApiStyle(str, Enum):
    REST = "rest"
    GRAPHQL = "graphql"
    SOAP = "soap"
    CLI = "cli"
    NONE = "none"
    UNKNOWN = "unknown"


class ApiBreadth(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    UNKNOWN = "unknown"


class ExistingMcp(str, Enum):
    NONE = "none"
    COMMUNITY = "community"
    OFFICIAL = "official"
    UNKNOWN = "unknown"


class Verdict(str, Enum):
    SHIP_NOW = "ship_now"
    SHIP_WITH_SETUP_FRICTION = "ship_with_setup_friction"
    SKILL_OR_CLI_ONLY = "skill_or_cli_only"
    NEEDS_OUTREACH = "needs_outreach"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class EvidenceField(BaseModel):
    """Standard wrapper for any researched field containing evidence and quote."""
    value: Any = Field(default="unknown", description="Extracted value or answer")
    evidence_url: Optional[str] = Field(default=None, description="Exact documentation or spec URL")
    quote: Optional[str] = Field(default=None, description="Verbatim unedited snippet from retrieved source")
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.UNKNOWN, description="Confidence level")


# Alias for backward compatibility / terminology
EvidenceWrapper = EvidenceField


class AppInput(BaseModel):
    id: str
    name: str
    category: Optional[str] = None
    hint_url: Optional[str] = None


class AppRecord(BaseModel):
    id: str
    name: str
    category: EvidenceField = Field(default_factory=lambda: EvidenceField(value="unknown"))
    one_liner: EvidenceField = Field(default_factory=lambda: EvidenceField(value="unknown"))
    auth_methods: EvidenceField = Field(default_factory=lambda: EvidenceField(value=["unknown"]))
    self_serve: EvidenceField = Field(default_factory=lambda: EvidenceField(value="unknown"))
    api_style: EvidenceField = Field(default_factory=lambda: EvidenceField(value="unknown"))
    api_breadth: EvidenceField = Field(default_factory=lambda: EvidenceField(value="unknown"))
    existing_mcp: EvidenceField = Field(default_factory=lambda: EvidenceField(value="none"))
    sandbox_available: EvidenceField = Field(default_factory=lambda: EvidenceField(value=None))
    openapi_spec_available: EvidenceField = Field(default_factory=lambda: EvidenceField(value=None))
    webhooks: EvidenceField = Field(default_factory=lambda: EvidenceField(value=None))
    rate_limits_note: EvidenceField = Field(default_factory=lambda: EvidenceField(value="unknown"))
    free_tier_note: EvidenceField = Field(default_factory=lambda: EvidenceField(value="unknown"))
    in_composio_already: EvidenceField = Field(default_factory=lambda: EvidenceField(value=None))
    verdict: EvidenceField = Field(default_factory=lambda: EvidenceField(value="unknown"))
    main_blocker: EvidenceField = Field(default_factory=lambda: EvidenceField(value="none"))
    difficulty_1_to_5: EvidenceField = Field(default_factory=lambda: EvidenceField(value=None))

    # Meta
    raw_sources: List[str] = Field(default_factory=list)
