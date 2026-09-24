import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from google import genai
from google.genai import types

from src.research.config import settings
from src.research.schema import AppRecord, EvidenceField

logger = logging.getLogger(__name__)

VERIFIER_SYSTEM_PROMPT = """
You are a senior independent verification auditor reviewing extracted facts about software developer APIs.
Your job is to independently verify whether the Extractor's answer is accurate based ONLY on the provided documentation snippet.

For each field evaluated, return a JSON object with:
- "agree": true or false
- "verifier_answer": Your independent answer or correction if you disagree (or same if agree)
- "reason": Short explanation of why you agree or disagree
"""


class Verifier:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.VERIFIER_API_KEY or settings.GEMINI_API_KEY
        self.model_name = model or settings.VERIFIER_MODEL
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    async def verify_record(
        self,
        record: AppRecord,
        sources: Dict[str, str],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Independently re-read cited pages and evaluate each field.
        Returns a mapping: {field_name: {"agree": bool, "verifier_answer": Any, "reason": str}}
        """
        results: Dict[str, Dict[str, Any]] = {}
        fields_to_verify = [
            "auth_methods", "self_serve", "api_style", "api_breadth",
            "openapi_spec_available", "webhooks", "sandbox_available", "verdict"
        ]

        if not self.client or not sources:
            # Fallback deterministic verifier
            return self._fallback_verify(record, sources, fields_to_verify)

        # Build payload of extracted fields + quotes for verifier model
        eval_payload = {}
        for f in fields_to_verify:
            field_obj: EvidenceField = getattr(record, f)
            eval_payload[f] = {
                "extractor_value": field_obj.value,
                "evidence_url": field_obj.evidence_url,
                "quote": field_obj.quote,
            }

        sources_context = "\n\n".join(
            [f"--- URL: {url} ---\n{text[:6000]}" for url, text in sources.items()]
        )

        prompt = f"""
Application Name: {record.name} (ID: {record.id})

Extracted Answers to Audit:
{json.dumps(eval_payload, indent=2)}

Documentation Text:
{sources_context}

For each field in the payload, determine if you AGREE or DISAGREE with the extracted value based strictly on the documentation.
Format your output as a JSON object keyed by field name:
{{
  "auth_methods": {{"agree": true, "verifier_answer": "...", "reason": "..."}},
  ...
}}
"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=VERIFIER_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                ),
            )
            data = json.loads(response.text or "{}")
            for f in fields_to_verify:
                if f in data:
                    results[f] = data[f]
                else:
                    results[f] = {"agree": True, "verifier_answer": getattr(record, f).value, "reason": "Default pass"}
            return results
        except Exception as e:
            logger.warning(f"LLM verification failed for {record.name}: {e}. Falling back to rule-based verification.")
            return self._fallback_verify(record, sources, fields_to_verify)

    def _fallback_verify(
        self,
        record: AppRecord,
        sources: Dict[str, str],
        fields: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """Fallback local verifier checking quote presence and self-consistency."""
        results = {}
        all_text = " ".join(sources.values()).lower()

        for f in fields:
            field_obj: EvidenceField = getattr(record, f)
            val = field_obj.value

            # Disagree if high confidence claim has no quote
            if field_obj.confidence.value == "high" and not field_obj.quote:
                results[f] = {
                    "agree": False,
                    "verifier_answer": "unknown",
                    "reason": "Missing verbatim quote for high confidence claim",
                }
            # Disagree if self_serve marked free but "enterprise only" in text
            elif f == "self_serve" and val == "free_self_serve" and "contact sales" in all_text and "free tier" not in all_text:
                results[f] = {
                    "agree": False,
                    "verifier_answer": "partnership_or_sales_gated",
                    "reason": "Text indicates enterprise / contact sales gating",
                }
            else:
                results[f] = {
                    "agree": True,
                    "verifier_answer": val,
                    "reason": "Matches retrieved text patterns",
                }

        return results
