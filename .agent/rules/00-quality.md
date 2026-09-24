# Workspace Quality Rules

## 1. Code Standards
- **Type Hints**: All functions and methods must have complete type annotations (`typing` and Pydantic models).
- **Small, Modular Components**: Keep modules focused with single responsibilities (e.g. collector, extractor, verifier, checks).
- **Async First**: Use `asyncio`, `httpx.AsyncClient` with connection pooling and a global semaphore limit (default 10).
- **Deterministic Validation**: Always run checks from `src/research/checks.py` (URL liveness, quote verification in page text, enum validation) before trusting extraction results.
- **Testing**: Maintain comprehensive tests in `tests/` including full test coverage for `checks.py`.

## 2. Execution Discipline
- **Stage Verification**: Every stage must end with a runnable command and a short walkthrough of outputs and metrics.
- **No Secrets**: Never commit `.env` or hardcode API keys. Always load via `pydantic-settings` or `os.environ`.
- **Cache Integrity**: Cache all external HTTP responses in `data/cache/` keyed by SHA-256 hash. Never delete or overwrite frozen datasets like `data/pass1.jsonl`.
