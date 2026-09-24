import json
import logging
from typing import Dict, Optional, Tuple
from google import genai
from google.genai import types

from src.research.config import settings
from src.research.schema import (
    AppInput,
    AppRecord,
    EvidenceField,
    ConfidenceLevel,
    AuthMethod,
    SelfServeTier,
    ApiStyle,
    ApiBreadth,
    Verdict,
)
from src.research.checks import verify_quote_in_text

logger = logging.getLogger(__name__)

V2_EXTRACTION_SYSTEM_PROMPT = """
You are a senior integration research agent conducting forensic developer documentation analysis.

Your goal is to extract evidence-backed facts about a SaaS application's developer platform to evaluate Composio toolkit integration.

MANDATORY RULES:
1. Every field MUST be an object with:
   - "value": The extracted fact, enum, boolean, number, or string.
   - "evidence_url": The exact source URL from the provided text where this fact was found.
   - "quote": The EXACT, unedited verbatim string directly copied from the text backing this claim.
   - "confidence": "high", "medium", "low", or "unknown".
2. STRICT EVIDENCE GATE:
   - A field WITHOUT an exact verbatim quote from the provided text MUST HAVE:
     value = "unknown" (or null)
     confidence = "unknown"
     quote = null
   - Guessing or unbacked assertions are strictly penalized.
3. Enum Allowed Values:
   - auth_methods: list of strings from ["oauth2", "api_key", "basic", "bearer_token", "jwt", "other", "none", "unknown"]
   - self_serve: ["free_self_serve", "trial_self_serve", "paid_required", "approval_required", "partnership_or_sales_gated", "unknown"]
   - api_style: ["rest", "graphql", "soap", "cli", "none", "unknown"]
   - api_breadth: ["small", "medium", "large", "unknown"]
   - existing_mcp: ["none", "community", "official", "unknown"]
   - verdict: ["ship_now", "ship_with_setup_friction", "skill_or_cli_only", "needs_outreach", "blocked", "unknown"]
   - difficulty_1_to_5: integer 1 to 5, or null
   - sandbox_available: boolean or null
   - openapi_spec_available: boolean or string URL or null
   - webhooks: boolean or null
   - in_composio_already: boolean or null
"""


class Extractor:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model or settings.GEMINI_MODEL
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    async def extract_v2(
        self,
        app: AppInput,
        sources: Dict[str, str],
        mcp_info: Tuple[str, Optional[str]],
        in_composio: bool,
    ) -> AppRecord:
        """v2 extraction with strict quote requirement and multi-surface grounding."""
        if not self.client or not sources:
            record = self._fallback_grounded_extraction(app, sources, mcp_info, in_composio)
        else:
            sources_text = "\n\n".join(
                [f"=== URL: {url} ===\n{text[:9000]}" for url, text in sources.items()]
            )

            prompt = f"""
Application Name: {app.name}
Application ID: {app.id}
Category Hint: {app.category or 'Unknown'}
Hint URL: {app.hint_url or 'None'}

Retrieved Documentation Sources:
{sources_text}

Extract the AppRecord JSON. Remember: Any field without an exact unedited verbatim quote from the sources must be 'unknown'.
"""
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=V2_EXTRACTION_SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_schema=AppRecord,
                    ),
                )
                data = json.loads(response.text or "{}")
                record = AppRecord.model_validate(data)
            except Exception as e:
                logger.error(f"v2 extraction error for {app.name}: {e}")
                record = self._fallback_grounded_extraction(app, sources, mcp_info, in_composio)

        # Enforce MCP and Composio catalog info
        mcp_status, mcp_url = mcp_info
        record.existing_mcp = EvidenceField(
            value=mcp_status,
            evidence_url=mcp_url,
            quote="MCP server verified in registry" if mcp_url else None,
            confidence=ConfidenceLevel.HIGH if mcp_status != "none" else ConfidenceLevel.MEDIUM,
        )
        record.in_composio_already = EvidenceField(
            value=in_composio,
            evidence_url="https://composio.dev/tools",
            quote="Verified against Composio catalog" if in_composio else None,
            confidence=ConfidenceLevel.HIGH,
        )

        # Post-process: Enforce that unquoted fields become "unknown"
        all_sources_text = " ".join(sources.values())
        fields_to_check = [
            "category", "one_liner", "auth_methods", "self_serve", "api_style",
            "api_breadth", "sandbox_available", "openapi_spec_available",
            "webhooks", "rate_limits_note", "free_tier_note", "verdict", "main_blocker"
        ]

        for field_name in fields_to_check:
            field_obj: EvidenceField = getattr(record, field_name)
            # If no quote or quote doesn't exist in page, reset to unknown
            if not field_obj.quote or not verify_quote_in_text(field_obj.quote, all_sources_text):
                if field_name == "auth_methods":
                    field_obj.value = ["unknown"]
                elif field_name in ("sandbox_available", "openapi_spec_available", "webhooks"):
                    field_obj.value = None
                elif field_name == "difficulty_1_to_5":
                    field_obj.value = None
                else:
                    field_obj.value = "unknown"
                field_obj.confidence = ConfidenceLevel.UNKNOWN
                field_obj.quote = None

        record.id = app.id
        record.name = app.name
        record.raw_sources = list(sources.keys())
        return record

    def _fallback_grounded_extraction(
        self,
        app: AppInput,
        sources: Dict[str, str],
        mcp_info: Tuple[str, Optional[str]],
        in_composio: bool,
    ) -> AppRecord:
        """Deterministic rule-based extractor using exact substrings in retrieved text."""
        all_text = " ".join(sources.values()).lower()
        primary_url = next(iter(sources.keys())) if sources else app.hint_url

        def find_exact_quote(query: str) -> Optional[str]:
            for url, text in sources.items():
                if query.lower() in text.lower():
                    idx = text.lower().find(query.lower())
                    start = max(0, idx - 20)
                    end = min(len(text), idx + len(query) + 40)
                    return text[start:end].strip()
            return None

        # 1. Auth methods
        auth_methods = []
        auth_quote = None
        if "oauth 2.0" in all_text or "oauth2" in all_text:
            auth_methods.append("oauth2")
            auth_quote = find_exact_quote("oauth")
        if "api key" in all_text or "secret key" in all_text:
            auth_methods.append("api_key")
            if not auth_quote:
                auth_quote = find_exact_quote("api key")
        if "bearer " in all_text or "bearer token" in all_text:
            auth_methods.append("bearer_token")
            if not auth_quote:
                auth_quote = find_exact_quote("bearer")
        if not auth_methods:
            auth_methods = ["unknown"]

        # 2. Self serve
        self_serve = "unknown"
        ss_quote = None
        if "free trial" in all_text or "start your trial" in all_text:
            self_serve = "trial_self_serve"
            ss_quote = find_exact_quote("free trial")
        elif "contact sales" in all_text or "enterprise only" in all_text:
            self_serve = "partnership_or_sales_gated"
            ss_quote = find_exact_quote("contact sales")
        elif "free" in all_text or "create an account" in all_text or "sign up" in all_text:
            self_serve = "free_self_serve"
            ss_quote = find_exact_quote("free")

        # 3. API style
        api_style = "unknown"
        style_quote = None
        if "graphql" in all_text:
            api_style = "graphql"
            style_quote = find_exact_quote("graphql")
        elif "rest api" in all_text or "restful" in all_text or "http api" in all_text:
            api_style = "rest"
            style_quote = find_exact_quote("rest")

        # 4. Webhooks
        webhooks_val = None
        wh_quote = None
        if "webhook" in all_text:
            webhooks_val = True
            wh_quote = find_exact_quote("webhook")

        # 5. OpenAPI
        openapi_val = None
        oas_quote = None
        if "openapi" in all_text or "swagger" in all_text:
            openapi_val = True
            oas_quote = find_exact_quote("openapi") or find_exact_quote("swagger")

        # 6. Sandbox
        sandbox_val = None
        sb_quote = None
        if "sandbox" in all_text or "test mode" in all_text:
            sandbox_val = True
            sb_quote = find_exact_quote("sandbox") or find_exact_quote("test mode")

        # Verdict
        if self_serve in ("free_self_serve", "trial_self_serve") and api_style in ("rest", "graphql"):
            verdict = "ship_now"
        elif self_serve == "partnership_or_sales_gated":
            verdict = "needs_outreach"
        elif api_style == "none":
            verdict = "blocked"
        else:
            verdict = "ship_with_setup_friction"

        return AppRecord(
            id=app.id,
            name=app.name,
            category=EvidenceField(value=app.category or "unknown", evidence_url=primary_url, confidence=ConfidenceLevel.MEDIUM if app.category else ConfidenceLevel.UNKNOWN),
            one_liner=EvidenceField(value=f"{app.name} platform and developer API", evidence_url=primary_url, confidence=ConfidenceLevel.LOW),
            auth_methods=EvidenceField(value=auth_methods, evidence_url=primary_url if auth_quote else None, quote=auth_quote, confidence=ConfidenceLevel.HIGH if auth_quote else ConfidenceLevel.UNKNOWN),
            self_serve=EvidenceField(value=self_serve, evidence_url=primary_url if ss_quote else None, quote=ss_quote, confidence=ConfidenceLevel.HIGH if ss_quote else ConfidenceLevel.UNKNOWN),
            api_style=EvidenceField(value=api_style, evidence_url=primary_url if style_quote else None, quote=style_quote, confidence=ConfidenceLevel.HIGH if style_quote else ConfidenceLevel.UNKNOWN),
            api_breadth=EvidenceField(value="large" if len(all_text) > 8000 else "medium", evidence_url=primary_url, confidence=ConfidenceLevel.LOW),
            existing_mcp=EvidenceField(value=mcp_info[0], evidence_url=mcp_info[1], confidence=ConfidenceLevel.HIGH if mcp_info[0] != "none" else ConfidenceLevel.LOW),
            sandbox_available=EvidenceField(value=sandbox_val, evidence_url=primary_url if sb_quote else None, quote=sb_quote, confidence=ConfidenceLevel.HIGH if sb_quote else ConfidenceLevel.UNKNOWN),
            openapi_spec_available=EvidenceField(value=openapi_val, evidence_url=primary_url if oas_quote else None, quote=oas_quote, confidence=ConfidenceLevel.HIGH if oas_quote else ConfidenceLevel.UNKNOWN),
            webhooks=EvidenceField(value=webhooks_val, evidence_url=primary_url if wh_quote else None, quote=wh_quote, confidence=ConfidenceLevel.HIGH if wh_quote else ConfidenceLevel.UNKNOWN),
            rate_limits_note=EvidenceField(value="Documented rate limits apply", confidence=ConfidenceLevel.LOW),
            free_tier_note=EvidenceField(value="Free tier or trial available" if self_serve in ("free_self_serve", "trial_self_serve") else "unknown", confidence=ConfidenceLevel.LOW),
            in_composio_already=EvidenceField(value=in_composio, evidence_url="https://composio.dev/tools", confidence=ConfidenceLevel.HIGH),
            verdict=EvidenceField(value=verdict, evidence_url=primary_url, confidence=ConfidenceLevel.MEDIUM),
            main_blocker=EvidenceField(value="none" if verdict == "ship_now" else "Setup friction or gating", confidence=ConfidenceLevel.LOW),
            difficulty_1_to_5=EvidenceField(value=2 if verdict == "ship_now" else 4, confidence=ConfidenceLevel.LOW),
            raw_sources=list(sources.keys()),
        )
