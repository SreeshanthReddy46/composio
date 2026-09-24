# Composio 100-App Toolkit-Buildability Research Agent

An automated, rigorous research agent investigating the buildability, auth mechanisms, API specs, and SDK coverage for 100 SaaS applications for Composio toolkit integration, paired with an interactive case-study analysis page.

## Key Features
- **Async Scraping & Extraction**: High-throughput async pipeline (`httpx`, `asyncio`) with concurrency limits (default 10).
- **Dual-Model Verification**: Extraction via Flash-class Gemini model + independent Verifier model to prevent correlated hallucinations.
- **Strict Evidence Standards**: Every extracted field is tied to an `evidence_url`, `verbatim_quote`, and `confidence` score.
- **Deterministic Validation**: URL liveness tests, quote substring match checks, and enum validation.
- **Reproducible Artifacts**: Generates structured datasets (`pass1.jsonl`, `pass2.jsonl`, `final.jsonl`, `results.csv`) and an interactive HTML case study dashboard.

## Setup

```bash
# Install dependencies with uv
uv sync

# Configure environment
cp .env.example .env
```

## Running the Pipeline

```bash
# View CLI help
python -m src.research.cli --help

# Run research batch
python -m src.research.cli run --input apps.yaml --output data/pass1.jsonl
```
