from typing import Dict, List, Optional, Tuple
from src.research.schema import (
    AppRecord,
    EvidenceField,
    AuthMethod,
    ApiStyle,
    SelfServeTier,
    Verdict,
    ConfidenceLevel,
)


def verify_quote_in_text(quote: str, text: str) -> bool:
    """Check if verbatim quote or normalized version exists in the retrieved text."""
    if not quote or not text:
        return False
    
    clean_quote = " ".join(quote.strip().lower().split())
    clean_text = " ".join(text.strip().lower().split())
    return clean_quote in clean_text


def validate_enums(record: AppRecord) -> List[Tuple[str, str]]:
    """Validate that categorical fields match schema enums."""
    errors: List[Tuple[str, str]] = []
    
    valid_auth = {e.value for e in AuthMethod}
    auth_vals = record.auth_methods.value if isinstance(record.auth_methods.value, list) else [record.auth_methods.value]
    for val in auth_vals:
        if val not in valid_auth:
            errors.append(("auth_methods", f"Invalid auth_method '{val}'"))
        
    valid_api = {e.value for e in ApiStyle}
    if record.api_style.value not in valid_api:
        errors.append(("api_style", f"Invalid api_style '{record.api_style.value}'"))

    valid_ss = {e.value for e in SelfServeTier}
    if record.self_serve.value not in valid_ss:
        errors.append(("self_serve", f"Invalid self_serve '{record.self_serve.value}'"))
        
    valid_verdict = {e.value for e in Verdict}
    if record.verdict.value not in valid_verdict:
        errors.append(("verdict", f"Invalid verdict '{record.verdict.value}'"))
        
    return errors


def run_deterministic_checks(
    record: AppRecord,
    sources: Dict[str, str],
) -> Tuple[AppRecord, List[Tuple[str, str]]]:
    """
    Run deterministic checks:
    1. Evidence URL returns 200 (exists in sources)
    2. Quote appears verbatim in page text
    3. Categorical enum validity
    Failures lower confidence and are logged for review.
    """
    failures: List[Tuple[str, str]] = []
    
    # 1. Enum checks
    enum_errors = validate_enums(record)
    for field_name, err in enum_errors:
        failures.append((field_name, err))
        field: EvidenceField = getattr(record, field_name)
        field.confidence = ConfidenceLevel.UNKNOWN

    # 2. Evidence & Quote verification
    all_text = " ".join(sources.values())
    evidence_fields = [
        "category", "one_liner", "auth_methods", "self_serve", "api_style",
        "api_breadth", "existing_mcp", "sandbox_available", "openapi_spec_available",
        "webhooks", "rate_limits_note", "free_tier_note", "verdict", "main_blocker"
    ]

    for field_name in evidence_fields:
        field: EvidenceField = getattr(record, field_name)
        
        # Check evidence URL validity
        if field.evidence_url:
            if sources and field.evidence_url not in sources:
                # URL wasn't retrieved with 200 OK
                failures.append((field_name, f"Evidence URL {field.evidence_url} not in 200 OK sources"))
                if field.confidence == ConfidenceLevel.HIGH:
                    field.confidence = ConfidenceLevel.LOW

        # Check verbatim quote
        if field.quote:
            if not verify_quote_in_text(field.quote, all_text):
                failures.append((field_name, f"Quote not found verbatim in sources: '{field.quote[:40]}'"))
                # Quote failure strictly resets confidence to low/unknown
                field.confidence = ConfidenceLevel.UNKNOWN
                field.quote = None

    return record, failures
