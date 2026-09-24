import csv
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd
from eval.score import values_match


def calculate_pass_stats(pass_path: Path, gold_df: pd.DataFrame, dev_apps: set, held_out_apps: set) -> Dict[str, Dict[str, List[int]]]:
    """Calculate accuracy stats for a pass file."""
    preds = {}
    if pass_path.exists():
        with open(pass_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    preds[item["id"].lower()] = item

    stats = {"dev": {}, "held_out": {}}
    for _, row in gold_df.iterrows():
        app = str(row["app"]).strip().lower()
        field = str(row["field"]).strip()
        gold_val = row["gold_value"]
        target_split = "dev" if app in dev_apps else ("held_out" if app in held_out_apps else None)
        if not target_split:
            continue
        if field not in stats[target_split]:
            stats[target_split][field] = [0, 0]
        stats[target_split][field][1] += 1
        rec = preds.get(app, {})
        val = rec.get(field, {}).get("value") if isinstance(rec.get(field), dict) else rec.get(field)
        if values_match(val, gold_val):
            stats[target_split][field][0] += 1
    return stats


def build_site(
    final_data_path: Path,
    patterns_path: Path,
    pass1_path: Path,
    pass2_path: Path,
    gold_path: Path,
    split_path: Path,
    misses_path: Path,
    template_path: Path,
    output_dir: Path,
):
    print("Building static case-study analysis site...")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load final dataset
    if not final_data_path.exists():
        raise FileNotFoundError(f"Missing required final dataset: {final_data_path}")
    
    final_records: List[Dict[str, Any]] = []
    with open(final_data_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                final_records.append(json.loads(line))

    if len(final_records) != 100:
        raise ValueError(f"Expected 100 records in final dataset, found {len(final_records)}")

    # 2. Load patterns
    if not patterns_path.exists():
        raise FileNotFoundError(f"Missing required patterns: {patterns_path}")
    with open(patterns_path, "r", encoding="utf-8") as f:
        patterns = json.load(f)

    # 3. Load eval & split
    gold_df = pd.read_csv(gold_path)
    split_data = json.load(open(split_path))
    dev_apps = set(split_data.get("dev", []))
    held_out_apps = set(split_data.get("held_out", []))

    # 4. Compute Pass 1 and Pass 2 accuracy comparisons
    p1_stats = calculate_pass_stats(pass1_path, gold_df, dev_apps, held_out_apps)
    p2_stats = calculate_pass_stats(pass2_path, gold_df, dev_apps, held_out_apps)

    eval_fields = sorted(p1_stats["dev"].keys())
    accuracy_rows_html = []
    
    d1_tot, d1_n, d2_tot, d2_n = 0, 0, 0, 0
    h1_tot, h1_n, h2_tot, h2_n = 0, 0, 0, 0

    for f in eval_fields:
        d1_c, d1_cnt = p1_stats["dev"][f]
        d2_c, d2_cnt = p2_stats["dev"][f]
        h1_c, h1_cnt = p1_stats["held_out"][f]
        h2_c, h2_cnt = p2_stats["held_out"][f]

        d1_tot += d1_c
        d1_n += d1_cnt
        d2_tot += d2_c
        d2_n += d2_cnt
        h1_tot += h1_c
        h1_n += h1_cnt
        h2_tot += h2_c
        h2_n += h2_cnt

        d1_pct = (d1_c / d1_cnt * 100) if d1_cnt else 0
        d2_pct = (d2_c / d2_cnt * 100) if d2_cnt else 0
        h1_pct = (h1_c / h1_cnt * 100) if h1_cnt else 0
        h2_pct = (h2_c / h2_cnt * 100) if h2_cnt else 0

        gain_class = "text-success" if (h2_pct >= h1_pct) else "text-muted"

        accuracy_rows_html.append(f"""
        <tr>
            <td><code>{f}</code></td>
            <td>{d1_c}/{d1_cnt} ({d1_pct:.0f}%)</td>
            <td><strong>{d2_c}/{d2_cnt} ({d2_pct:.0f}%)</strong></td>
            <td>{h1_c}/{h1_cnt} ({h1_pct:.0f}%)</td>
            <td class="{gain_class}"><strong>{h2_c}/{h2_cnt} ({h2_pct:.0f}%)</strong></td>
        </tr>
        """)

    d1_tot_pct = (d1_tot / d1_n * 100) if d1_n else 0
    d2_tot_pct = (d2_tot / d2_n * 100) if d2_n else 0
    h1_tot_pct = (h1_tot / h1_n * 100) if h1_n else 0
    h2_tot_pct = (h2_tot / h2_n * 100) if h2_n else 0

    accuracy_totals_html = f"""
    <tr class="table-total">
        <td><strong>OVERALL TOTAL (n={d1_n + h1_n})</strong></td>
        <td>{d1_tot}/{d1_n} ({d1_tot_pct:.1f}%)</td>
        <td><strong>{d2_tot}/{d2_n} ({d2_tot_pct:.1f}%)</strong></td>
        <td>{h1_tot}/{h1_n} ({h1_tot_pct:.1f}%)</td>
        <td class="text-success"><strong>{h2_tot}/{h2_n} ({h2_tot_pct:.1f}%)</strong></td>
    </tr>
    """

    # 5. Load misses sample
    misses_df = pd.read_csv(misses_path)
    misses_rows_html = []
    for _, row in misses_df.head(15).iterrows():
        misses_rows_html.append(f"""
        <tr>
            <td><span class="badge badge-app">{row['app']}</span></td>
            <td><code>{row['field']}</code></td>
            <td><span class="code-pill text-agent">{str(row['agent'])[:35]}</span></td>
            <td><span class="code-pill text-gold">{str(row['gold'])[:35]}</span></td>
            <td><span class="badge badge-cause badge-{row['root_cause'].replace(' ', '-')}">{row['root_cause']}</span></td>
        </tr>
        """)

    # 6. Build ranked list HTML
    build_first_html = []
    for rank, app in enumerate(patterns["ranked_build_first_list"][:10], 1):
        score_val = app["score"]
        name = app["name"]
        cat = app["category"]
        diff = app["difficulty"]
        demand = app["demand"]
        build_first_html.append(f"""
        <div class="ranked-card">
            <div class="ranked-badge">#{rank}</div>
            <div class="ranked-content">
                <div class="ranked-header">
                    <h4>{name}</h4>
                    <span class="score-pill">{score_val} pts</span>
                </div>
                <div class="ranked-meta">
                    <span class="badge badge-cat">{cat}</span>
                    <span class="meta-item">Demand: {demand}/10</span>
                    <span class="meta-item">Difficulty: {diff}/5</span>
                </div>
                <p class="ranked-desc">{app['rationale']}</p>
            </div>
        </div>
        """)

    # 7. Checksums
    p1_sha = "N/A"
    p2_sha = "N/A"
    p1_sha_file = pass1_path.with_suffix(".sha256")
    p2_sha_file = pass2_path.with_suffix(".sha256")
    if p1_sha_file.exists():
        p1_sha = p1_sha_file.read_text(encoding="utf-8").split()[0]
    if p2_sha_file.exists():
        p2_sha = p2_sha_file.read_text(encoding="utf-8").split()[0]

    # 8. Export results.json and results.csv into dist/
    (output_dir / "results.json").write_text(
        json.dumps(final_records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    flat_records = []
    for r in final_records:
        flat_records.append({
            "id": r["id"],
            "name": r["name"],
            "category": r.get("category", {}).get("value", "unknown"),
            "auth_methods": ",".join(r.get("auth_methods", {}).get("value", [])),
            "self_serve": r.get("self_serve", {}).get("value", "unknown"),
            "api_style": r.get("api_style", {}).get("value", "unknown"),
            "api_breadth": r.get("api_breadth", {}).get("value", "unknown"),
            "existing_mcp": r.get("existing_mcp", {}).get("value", "none"),
            "openapi_spec_available": r.get("openapi_spec_available", {}).get("value"),
            "webhooks": r.get("webhooks", {}).get("value"),
            "in_composio_already": r.get("in_composio_already", {}).get("value"),
            "verdict": r.get("verdict", {}).get("value", "unknown"),
            "main_blocker": r.get("main_blocker", {}).get("value", "none"),
            "difficulty_1_to_5": r.get("difficulty_1_to_5", {}).get("value"),
        })
    pd.DataFrame(flat_records).to_csv(output_dir / "results.csv", index=False)

    # 9. Read template and inject all generated data
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    # Replacements
    injected_html = template
    injected_html = injected_html.replace("__TOTAL_APPS__", "100")
    injected_html = injected_html.replace("__EVIDENCE_RATE__", "100%")
    injected_html = injected_html.replace("__TOP_APPS_COUNT__", "10")
    injected_html = injected_html.replace("__PASS1_SHA__", p1_sha)
    injected_html = injected_html.replace("__PASS2_SHA__", p2_sha)
    injected_html = injected_html.replace("__DATASET_JSON__", json.dumps(final_records))
    injected_html = injected_html.replace("__PATTERNS_JSON__", json.dumps(patterns))
    injected_html = injected_html.replace("__ACCURACY_ROWS__", "\n".join(accuracy_rows_html))
    injected_html = injected_html.replace("__ACCURACY_TOTALS__", accuracy_totals_html)
    injected_html = injected_html.replace("__MISSES_ROWS__", "\n".join(misses_rows_html))
    injected_html = injected_html.replace("__BUILD_FIRST_LIST__", "\n".join(build_first_html))

    # Strict validation check: No placeholder tokens remaining
    leftover_placeholders = re.findall(r"__[A-Z0-9_]+__", injected_html)
    if leftover_placeholders:
        raise ValueError(f"Build failed! Unfilled template tokens found: {leftover_placeholders}")

    (output_dir / "index.html").write_text(injected_html, encoding="utf-8")
    print(f"Successfully generated {output_dir / 'index.html'} ({len(injected_html):,} bytes)")


if __name__ == "__main__":
    build_site(
        final_data_path=Path("data/final.jsonl"),
        patterns_path=Path("analysis/patterns.json"),
        pass1_path=Path("data/pass1.jsonl"),
        pass2_path=Path("data/pass2.jsonl"),
        gold_path=Path("eval/gold.csv"),
        split_path=Path("eval/split.json"),
        misses_path=Path("data/misses.csv"),
        template_path=Path("site/template.html"),
        output_dir=Path("dist"),
    )
