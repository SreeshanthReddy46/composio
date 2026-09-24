# Workflow: Score & Evaluation

## Usage
Evaluate extracted dataset against gold labels in `eval/gold.csv` using the rubric defined in `eval/rubric.md`.

```bash
# Score pass1 predictions against gold split
python eval/score.py --predictions data/pass1.jsonl --gold eval/gold.csv --split eval/split.json

# Score verified pass2 predictions
python eval/score.py --predictions data/pass2.jsonl --gold eval/gold.csv --split eval/split.json
```
