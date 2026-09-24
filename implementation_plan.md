# Stage 4 Implementation Plan: v2 Verified Agent Pipeline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or inline execution to implement this plan task-by-task.

**Goal:** Upgrade the research agent from the v1 naive baseline to v2 verified architecture based on dev-half error analysis, adding multi-surface collection (docs, auth, pricing, signup, MCP registry, Composio catalog), strict quote requirements ("unknown" if unquoted), deterministic URL/quote/enum checks with confidence downgrading, dual-model independent verification, and automated logging of disagreements to `data/review_queue.csv`.

## Dev-Half Error Analysis Summary
Analysis of the 60 dev misses revealed:
- **`existing_mcp` (10/10 missed)**: Baseline never searched MCP registries or GitHub.
- **`openapi_spec_available` (10/10 missed)**: Baseline never queried spec URLs or API indexes.
- **`self_serve` & `sandbox_available` (12 misses)**: Baseline lacked pricing, signup, and sandbox testing pages.
- **`auth_methods` & `webhooks` (10 misses)**: Core auth and webhook details live on dedicated sub-pages (`/docs/auth`, `/docs/webhooks`).

## Subsystems & Architecture

### 1. Multi-Surface Collector (`src/research/collector.py`)
- Target URLs per app:
  - Official docs base URL
  - Auth page (`/docs/authentication`, `/docs/oauth`, `/docs/authorization`)
  - Pricing & developer signup (`/pricing`, `/docs/signup`)
  - Webhook guide (`/docs/webhooks`, `/docs/events`)
- MCP & GitHub registry search:
  - Checks official MCP catalog (`modelcontextprotocol/servers`) and search endpoints.
- Composio toolkit catalog check:
  - Queries local/SDK Composio toolkit list to verify `in_composio_already`.

### 2. Strict Extractor (`src/research/extractor.py`)
- System prompt and schema enforcement:
  - Any field without a valid, verbatim quote from one of the retrieved sources MUST be output as `value="unknown"`, `confidence="unknown"`, `quote=null`.
  - Structured output using Gemini Flash with Pydantic `AppRecord`.

### 3. Deterministic Verification & Checks (`src/research/checks.py`)
- `verify_url_alive(url)`: Confirms evidence URL returns 200.
- `verify_quote_verbatim(quote, text)`: Exact normalized substring match in the page text.
- `validate_enums(record)`: Verifies all categorical enums match allowed values.
- **Confidence Downgrade**: If quote is missing or URL fails, downgrade confidence to `low` or `unknown`.

### 4. Dual-Model Independent Verifier (`src/research/verifier.py`)
- Uses independent model (`settings.VERIFIER_MODEL`, default `gemini-2.5-pro`).
- Re-reads only the cited text snippets for the extracted fields.
- Returns agree/disagree boolean and critique per field.

### 5. Automated Review Queue (`data/review_queue.csv`)
- Any failed deterministic check OR verifier disagreement is appended to `data/review_queue.csv`:
  `app,field,extractor_answer,verifier_answer,url`.

---

## Tasks & Execution Order
- [ ] Task 1: Update `src/research/collector.py` for multi-surface scraping, MCP registry checks, and Composio toolkit verification.
- [ ] Task 2: Update `src/research/extractor.py` to enforce strict quote rule ("unknown" without quote).
- [ ] Task 3: Update `src/research/checks.py` for URL liveness, verbatim quote matching, enum checks, confidence downgrade, and tests.
- [ ] Task 4: Implement `src/research/verifier.py` with dual-model verification and disagreement detection.
- [ ] Task 5: Wire up v2 pipeline in `src/research/pipeline.py` (`--mode v2`), logging to `data/review_queue.csv` and writing to `data/pass2.jsonl`.
- [ ] Task 6: Test on 3 pilot apps, verify `data/review_queue.csv` output, then execute all 100 apps to `data/pass2.jsonl`.
