# Project Identity: Composio 100-App Toolkit-Buildability Research Agent + Case-Study Page

## Mission
Build and operate an automated, rigorous research agent that investigates the buildability, auth mechanisms, API specifications, and SDK coverage for 100 SaaS applications for Composio toolkit integration, and outputs an interactive case-study analysis page.

## Non-Negotiables
1. **Evidence & Rigor**: Every extracted field must have:
   - `evidence_url`: The exact source URL from official documentation, OpenAPI specs, or repository.
   - `verbatim_quote`: Exact unedited snippet from the page backing the claim.
   - `confidence`: Confidence rating (`high`, `medium`, `low`).
2. **Honesty over Hallucination**: `unknown` strictly beats guessing. If documentation is contradictory or missing, record as `unknown` with a note.
3. **Architecture & Performance**:
   - The pipeline must be fully **async** with bounded concurrency (default: 10 concurrent requests via `httpx`).
   - On-disk caching in `data/cache/` keyed by SHA-256 hash of `(url + prompt)`.
   - The pipeline must be fully **resumable**.
   - **Never overwrite `data/pass1.jsonl`** once it is frozen.
4. **Security**: Zero secrets in code. All credentials and API keys (`COMPOSIO_API_KEY`, `GEMINI_API_KEY`, `VERIFIER_API_KEY`) must come from environment variables or `.env`.
5. **Quality & Validation**: Deterministic verification via `src/research/checks.py` ensures URLs are alive, verbatim quotes exist in retrieved text, and categorical enums match schemas.
