import json
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd
import yaml


def analyze_patterns(input_path: Path, output_path: Path, apps_yaml_path: Path = Path("apps.yaml")) -> Dict[str, Any]:
    """Analyze patterns across the 100 SaaS applications and generate patterns.json."""
    # Load app categories from apps.yaml
    app_meta = {}
    if apps_yaml_path.exists():
        with open(apps_yaml_path, "r", encoding="utf-8") as f:
            for item in yaml.safe_load(f):
                app_meta[item["id"].lower()] = item

    records = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    flat_rows = []
    for r in records:
        app_id = r["id"].lower()
        meta = app_meta.get(app_id, {})
        category = meta.get("category") or r.get("category", {}).get("value", "Uncategorized")

        auth_vals = r.get("auth_methods", {}).get("value", ["unknown"])
        if not isinstance(auth_vals, list):
            auth_vals = [auth_vals]

        flat_rows.append({
            "id": app_id,
            "name": r["name"],
            "category": category,
            "auth_methods": auth_vals,
            "self_serve": r.get("self_serve", {}).get("value", "unknown"),
            "api_style": r.get("api_style", {}).get("value", "unknown"),
            "api_breadth": r.get("api_breadth", {}).get("value", "unknown"),
            "existing_mcp": r.get("existing_mcp", {}).get("value", "none"),
            "sandbox_available": r.get("sandbox_available", {}).get("value"),
            "openapi_spec_available": r.get("openapi_spec_available", {}).get("value"),
            "webhooks": r.get("webhooks", {}).get("value"),
            "in_composio_already": r.get("in_composio_already", {}).get("value"),
            "verdict": r.get("verdict", {}).get("value", "unknown"),
            "main_blocker": r.get("main_blocker", {}).get("value", "none"),
            "difficulty_1_to_5": r.get("difficulty_1_to_5", {}).get("value", 3) or 3,
        })

    df = pd.DataFrame(flat_rows)

    # 1. Auth Distribution
    auth_counter = {}
    for auth_list in df["auth_methods"]:
        for a in auth_list:
            auth_counter[a] = auth_counter.get(a, 0) + 1

    # 2. Self-Serve vs Gated by Category
    self_serve_by_cat = {}
    for cat, group in df.groupby("category"):
        ss_count = int(group["self_serve"].isin(["free_self_serve", "trial_self_serve"]).sum())
        gated_count = int(group["self_serve"].isin(["paid_required", "approval_required", "partnership_or_sales_gated"]).sum())
        unknown_count = int((group["self_serve"] == "unknown").sum())
        self_serve_by_cat[cat] = {
            "self_serve": ss_count,
            "gated": gated_count,
            "unknown": unknown_count,
            "total": len(group),
        }

    # 3. Top Blockers
    blockers = df["main_blocker"].value_counts().to_dict()
    top_blockers = {k: int(v) for k, v in blockers.items() if k != "none"}

    # 4. Verdict Tiers
    verdict_tiers = {k: int(v) for k, v in df["verdict"].value_counts().to_dict().items()}

    # 5. Ranked "Build First" List (10 apps: Ease × Demand)
    demand_priors = {
        "github": 10, "slack": 10, "notion": 10, "stripe": 10, "linear": 9,
        "hubspot": 9, "posthog": 9, "shopify": 9, "twilio": 8, "webflow": 8,
        "google-drive": 9, "sentry": 8, "typeform": 8, "attio": 7, "brex": 7,
        "zendesk": 8, "jira": 9, "airtable": 8, "supabase": 9, "figma": 8,
    }

    scored_apps = []
    for _, row in df.iterrows():
        app_id = row["id"]
        demand = demand_priors.get(app_id, 6)
        difficulty = int(row["difficulty_1_to_5"]) if row["difficulty_1_to_5"] else 3
        ease = max(1, 6 - difficulty)

        bonus = 1.0
        if row["openapi_spec_available"] is True:
            bonus += 0.3
        if row["self_serve"] in ("free_self_serve", "trial_self_serve"):
            bonus += 0.4
        if row["existing_mcp"] in ("official", "community"):
            bonus += 0.2

        score = round((demand * ease) * bonus, 2)
        scored_apps.append({
            "id": app_id,
            "name": row["name"],
            "category": row["category"],
            "verdict": row["verdict"],
            "difficulty": difficulty,
            "demand": demand,
            "ease": ease,
            "score": score,
            "rationale": f"High demand tier ({demand}/10), low setup friction (difficulty {difficulty}/5)",
        })

    ranked_build_first = sorted(scored_apps, key=lambda x: x["score"], reverse=True)[:10]

    output_data = {
        "total_analyzed": len(df),
        "auth_distribution": auth_counter,
        "self_serve_vs_gated_by_category": self_serve_by_cat,
        "top_blockers": top_blockers,
        "verdict_tiers": verdict_tiers,
        "ranked_build_first_list": ranked_build_first,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"Generated patterns analysis at {output_path}")
    return output_data


if __name__ == "__main__":
    analyze_patterns(Path("data/pass2.jsonl"), Path("analysis/patterns.json"))
