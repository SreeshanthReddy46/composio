import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def normalize_val(val: Any) -> Any:
    """Normalize extracted or gold value for robust comparison."""
    if val is None:
        return "none"
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, list):
        return sorted([str(x).strip().lower() for x in val if x is not None])
    
    s = str(val).strip().lower()
    if s.startswith("[") and s.endswith("]"):
        try:
            parsed = json.loads(s.replace("'", '"'))
            if isinstance(parsed, list):
                return sorted([str(x).strip().lower() for x in parsed])
        except Exception:
            pass
    return s


def values_match(agent_val: Any, gold_val: Any) -> bool:
    """Check if agent prediction matches gold annotation."""
    norm_agent = normalize_val(agent_val)
    norm_gold = normalize_val(gold_val)

    # List comparison (e.g. auth_methods)
    if isinstance(norm_gold, list):
        if not isinstance(norm_agent, list):
            norm_agent = [norm_agent]
        # At least one significant overlap or exact match
        overlap = set(norm_agent).intersection(set(norm_gold))
        return len(overlap) > 0 and "unknown" not in norm_agent

    # Boolean string comparison
    if norm_gold in ("true", "false", "none"):
        return norm_agent == norm_gold

    # Number comparison
    try:
        return float(norm_agent) == float(norm_gold)
    except (ValueError, TypeError):
        pass

    return norm_agent == norm_gold


def score_predictions(
    predictions_path: Path,
    gold_path: Path,
    split_path: Path,
    misses_path: Path,
) -> None:
    if not predictions_path.exists():
        console.print(f"[red]Error: Predictions file {predictions_path} not found.[/red]")
        return
    if not gold_path.exists():
        console.print(f"[red]Error: Gold file {gold_path} not found.[/red]")
        return

    # Load split
    split_data = {"dev": [], "held_out": []}
    if split_path.exists():
        with open(split_path, "r", encoding="utf-8") as f:
            split_data = json.load(f)
    dev_apps = set(split_data.get("dev", []))
    held_out_apps = set(split_data.get("held_out", []))

    # Load predictions indexed by app id
    predictions: Dict[str, Dict[str, Any]] = {}
    with open(predictions_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                predictions[item["id"].lower()] = item

    # Load gold rows
    gold_df = pd.read_csv(gold_path)

    # Track stats: stats[split_name][field] = [correct_count, total_count]
    stats: Dict[str, Dict[str, List[int]]] = {
        "dev": {},
        "held_out": {},
        "overall": {},
    }

    misses: List[Dict[str, str]] = []

    for _, row in gold_df.iterrows():
        app = str(row["app"]).strip().lower()
        field = str(row["field"]).strip()
        gold_val = row["gold_value"]

        # Determine split
        split_name = "dev" if app in dev_apps else ("held_out" if app in held_out_apps else "other")

        # Get agent prediction
        pred_record = predictions.get(app)
        if pred_record and field in pred_record:
            field_obj = pred_record[field]
            agent_val = field_obj.get("value") if isinstance(field_obj, dict) else field_obj
        else:
            agent_val = "missing"

        is_correct = values_match(agent_val, gold_val)

        # Update stats
        for target_split in [split_name, "overall"]:
            if target_split not in stats:
                stats[target_split] = {}
            if field not in stats[target_split]:
                stats[target_split][field] = [0, 0]
            stats[target_split][field][1] += 1
            if is_correct:
                stats[target_split][field][0] += 1

        if not is_correct:
            misses.append({
                "app": app,
                "field": field,
                "agent": str(agent_val),
                "gold": str(gold_val),
                "root_cause": "",
            })

    # Save misses.csv
    misses_path.parent.mkdir(parents=True, exist_ok=True)
    with open(misses_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["app", "field", "agent", "gold", "root_cause"])
        writer.writeheader()
        writer.writerows(misses)

    # Render results table
    all_fields = sorted(stats["overall"].keys())

    table = Table(
        title=f"Evaluation Scorecard ({predictions_path.name})",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Field", style="bold white")
    table.add_column("Dev Accuracy (n)", justify="right")
    table.add_column("Held-Out Accuracy (n)", justify="right")
    table.add_column("Overall Accuracy (n)", justify="right", style="bold green")

    total_dev_c, total_dev_n = 0, 0
    total_ho_c, total_ho_n = 0, 0
    total_all_c, total_all_n = 0, 0

    for field in all_fields:
        dev_c, dev_n = stats.get("dev", {}).get(field, [0, 0])
        ho_c, ho_n = stats.get("held_out", {}).get(field, [0, 0])
        all_c, all_n = stats.get("overall", {}).get(field, [0, 0])

        total_dev_c += dev_c
        total_dev_n += dev_n
        total_ho_c += ho_c
        total_ho_n += ho_n
        total_all_c += all_c
        total_all_n += all_n

        dev_pct = (dev_c / dev_n * 100) if dev_n else 0.0
        ho_pct = (ho_c / ho_n * 100) if ho_n else 0.0
        all_pct = (all_c / all_n * 100) if all_n else 0.0

        table.add_row(
            field,
            f"{dev_pct:.1f}% ({dev_c}/{dev_n})",
            f"{ho_pct:.1f}% ({ho_c}/{ho_n})",
            f"{all_pct:.1f}% ({all_c}/{all_n})",
        )

    dev_tot_pct = (total_dev_c / total_dev_n * 100) if total_dev_n else 0.0
    ho_tot_pct = (total_ho_c / total_ho_n * 100) if total_ho_n else 0.0
    all_tot_pct = (total_all_c / total_all_n * 100) if total_all_n else 0.0

    table.add_section()
    table.add_row(
        "OVERALL TOTAL",
        f"{dev_tot_pct:.1f}% ({total_dev_c}/{total_dev_n})",
        f"{ho_tot_pct:.1f}% ({total_ho_c}/{total_ho_n})",
        f"{all_tot_pct:.1f}% ({total_all_c}/{total_all_n})",
        style="bold yellow",
    )

    console.print(table)
    console.print(f"[cyan]Logged {len(misses)} misses to {misses_path}[/cyan]")


def main():
    parser = argparse.ArgumentParser(description="Score predictions against gold annotations")
    parser.add_argument(
        "--predictions",
        "-p",
        type=Path,
        default=Path("data/pass1.jsonl"),
        help="Path to prediction jsonl file",
    )
    parser.add_argument(
        "--gold",
        "-g",
        type=Path,
        default=Path("eval/gold.csv"),
        help="Path to gold.csv",
    )
    parser.add_argument(
        "--split",
        "-s",
        type=Path,
        default=Path("eval/split.json"),
        help="Path to split.json",
    )
    parser.add_argument(
        "--misses",
        "-m",
        type=Path,
        default=Path("data/misses.csv"),
        help="Path to output misses.csv",
    )
    args = parser.parse_args()

    score_predictions(args.predictions, args.gold, args.split, args.misses)


if __name__ == "__main__":
    main()
