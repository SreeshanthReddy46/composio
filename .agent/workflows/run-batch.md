# Workflow: Run Batch Research

## Usage
Run batch extraction on apps configured in `apps.yaml`.

```bash
# Run all apps with concurrency limit 10
python -m src.research.cli run --input apps.yaml --output data/pass1.jsonl --concurrency 10

# Resume an interrupted run
python -m src.research.cli run --input apps.yaml --output data/pass1.jsonl --resume

# Run a single app for inspection
python -m src.research.cli run --app-id notion --output data/debug.jsonl
```
