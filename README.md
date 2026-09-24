# Composio 100-App Toolkit-Buildability Research Agent + Case-Study Dashboard

An automated, rigorous research agent investigating the API specifications, authentication mechanisms, SDK coverage, and buildability of 100 SaaS applications for Composio toolkit integration.

---

## Key Features

- **Multi-Surface Collection**: Crawls developer portals, dedicated `/authentication` & `/oauth` paths, `/pricing` tables, `/webhooks` event references, GitHub MCP registries (`modelcontextprotocol/servers`), and Composio's official catalog.
- **Strict Evidence Standard**: Every extracted field is wrapped as `{value, evidence_url, quote, confidence}`. A claim without an exact verbatim quote in retrieved source text is strictly classified as `unknown` (honesty over hallucination).
- **Dual-Model Verification**: Extraction via Flash-class Gemini model + independent verification via a separate Verifier model (`gemini-2.5-pro`) to eliminate correlated hallucinations.
- **Deterministic Check Gate**: Validates that evidence URLs return HTTP 200, quotes exist verbatim in retrieved text, and categorical fields match schemas before lowering confidence on failure.
- **Human-in-the-Loop Review Queue**: Discrepancies and check failures are routed to `data/review_queue.csv` for targeted human review.
- **Self-Contained Case-Study Dashboard**: Compiles findings into an interactive, zero-dependency `dist/index.html` featuring interactive matrix filtering, modal quote viewers, inline SVG pipeline diagram, and evaluation metrics.

---

## Project Structure

```
composio-app-research/
├── GEMINI.md                    # Project identity and non-negotiables
├── .agent/rules/00-quality.md   # Code quality standards and stage rules
├── .agent/workflows/            # run-batch.md, score.md
├── README.md                    # This documentation
├── pyproject.toml               # uv configuration & dependencies
├── .env.example                 # Template for required environment variables
├── apps.yaml                    # 100 SaaS apps + category + hint URLs
├── apps_raw.md                  # Raw markdown tables of the 100 apps
├── src/research/
│   ├── schema.py                # Pydantic v2 models (AppRecord, EvidenceField)
│   ├── config.py                # Pydantic Settings
│   ├── tools.py                 # Multi-tier fetchers (Trafilatura, Jina, Playwright) + SHA-256 cache
│   ├── collector.py             # Multi-surface scraper + MCP/Composio catalog checker
│   ├── extractor.py             # Grounded LLM extractor with strict quote gate
│   ├── checks.py                # Deterministic URL, quote, and enum checks
│   ├── verifier.py              # Dual-model independent verifier
│   ├── pipeline.py              # Async bounded pipeline (v1 naive & v2 verified modes)
│   └── cli.py                   # Research CLI entrypoint
├── eval/
│   ├── rubric.md                # Ground-truth definitions for all fields
│   ├── gold.csv                 # 20-app blind evaluation ground truth
│   ├── split.json               # 10 Dev / 10 Held-out app partition
│   └── score.py                 # Evaluation scorecard engine
├── data/
│   ├── cache/                   # SHA-256 disk cache for web requests
│   ├── pass1.jsonl              # Frozen v1 naive baseline (read-only)
│   ├── pass1.sha256             # Pass 1 integrity hash
│   ├── pass2.jsonl              # Frozen v2 verified baseline (read-only)
│   ├── pass2.sha256             # Pass 2 integrity hash
│   ├── final.jsonl              # Polished 100-app dataset after review queue triage
│   └── review_queue.csv         # Flagged discrepancies for human audit
├── analysis/
│   ├── patterns.py              # Empirical pattern mining script
│   └── patterns.json            # Auth breakdown, self-serve ratios, ranked build-first list
├── site/
│   ├── template.html            # Case-study dashboard template
│   └── build.py                 # Static site compiler with data validation
├── dist/
│   ├── index.html               # Self-contained case-study dashboard
│   ├── results.json             # 100-app JSON export
│   └── results.csv              # 100-app CSV tabular export
├── .github/workflows/
│   └── research.yml             # GitHub Action with workflow_dispatch
└── tests/                       # Complete pytest suite (checks, schema, tools)
```

---

## Setup & Installation

### Prerequisites
- Python 3.11 or 3.12
- [uv](https://github.com/astral-sh/uv) (recommended package manager)

```bash
# Clone the repository
git clone https://github.com/your-username/composio-app-research.git
cd composio-app-research

# Install dependencies with uv
uv sync

# Install Playwright browser binaries (for JS fallback rendering)
uv run playwright install chromium
```

---

## Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Configure your API credentials in `.env`:

```ini
# Composio API key (from https://dashboard.composio.dev/settings/api-keys)
COMPOSIO_API_KEY=your_composio_api_key

# Google Gemini API key (for Flash-class extraction)
GEMINI_API_KEY=your_gemini_api_key

# Verifier Model Key (defaults to GEMINI_API_KEY if omitted)
VERIFIER_API_KEY=your_verifier_api_key

# Concurrency & Cache settings
MAX_CONCURRENCY=10
CACHE_DIR=data/cache
GEMINI_MODEL=gemini-2.5-flash
VERIFIER_MODEL=gemini-2.5-pro
```

> **Security Note:** `.env` is strictly gitignored. Never hardcode credentials in code.

---

## CLI Usage

The CLI provides entrypoints for single-app testing, batch execution, and evaluation.

### 1. Research a Single App
Run research on any application by name or ID:

```bash
# Research Notion using the v2 verified pipeline
python -m research run --app "Notion" --mode v2

# Research GitHub using naive v1 baseline
python -m research run --app "GitHub" --mode v1
```

### 2. Run the Full 100-App Batch
Execute research across all 100 applications defined in `apps.yaml`:

```bash
# Run v2 verified pipeline with 10 concurrent async workers
python -m research run --all --mode v2 --concurrency 10 --output data/pass2.jsonl

# Resume an interrupted batch run
python -m research run --all --mode v2 --resume
```

---

## Reproducing Evaluation & Scoring

Score any output dataset against the 20-app blind gold evaluation standard (`eval/gold.csv` across `eval/split.json`):

```bash
# Score Pass 1 Naive Baseline
python eval/score.py --predictions data/pass1.jsonl --gold eval/gold.csv --split eval/split.json

# Score Pass 2 Verified Pipeline
python eval/score.py --predictions data/pass2.jsonl --gold eval/gold.csv --split eval/split.json

# Score Final Triage Dataset
python eval/score.py --predictions data/final.jsonl --gold eval/gold.csv --split eval/split.json
```

Diagnostic misses are automatically output to `data/misses.csv`.

---

## Generating the Case-Study Dashboard

Compile the interactive dashboard and data artifacts into `dist/`:

```bash
python site/build.py
```

Outputs:
- `dist/index.html`: Fully self-contained static HTML case-study dashboard with inline CSS/JS/SVG and light/dark mode support.
- `dist/results.json`: Complete 100-app dataset in JSON format.
- `dist/results.csv`: Complete 100-app dataset in CSV format.

---

## Known Limits & Edge Cases

1. **JavaScript-Rendered SPAs**: Certain developer portals (SwaggerUI, Redoc, Docusaurus) render endpoint schemas client-side. The multi-tier fetcher uses Playwright and Jina Reader to mitigate this, but high-latency hydration can occasionally limit endpoint discovery.
2. **Ambiguous Plan Tiers**: SaaS marketing pages frequently omit developer API quotas or sandbox availability from public pricing tables, requiring an authenticated console login to verify.
3. **Closed Ecosystems (NotebookLM)**: Products lacking a public developer API are identified and flagged as `blocked`.
4. **Complex Dual-Auth (Amazon SP-API)**: Platforms requiring AWS IAM Signature Version 4 + OAuth 2.0 LWA alongside developer vetting are categorized as `ship_with_setup_friction` with difficulty 5/5.
5. **CLI Tools (Sherlock)**: Open-source terminal utilities without SaaS HTTP backends are properly classified as `skill_or_cli_only`.
