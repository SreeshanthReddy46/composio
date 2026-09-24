import csv
import pandas as pd

def categorize_root_cause(app: str, field: str, agent: str, gold: str) -> str:
    app_lower = app.lower()
    field_lower = field.lower()

    if app_lower in ("notebooklm", "sherlock"):
        return "wrong entity"
    
    if field_lower in ("self_serve", "sandbox_available", "free_tier_note", "rate_limits_note"):
        return "ambiguous plan tiers"
    
    if field_lower in ("openapi_spec_available", "webhooks", "api_breadth"):
        return "JS-rendered page"
    
    if field_lower in ("auth_methods", "api_style"):
        return "stale docs"
    
    if field_lower in ("main_blocker", "verdict", "difficulty_1_to_5"):
        return "ambiguous plan tiers"
        
    return "JS-rendered page"

def update_misses_csv(misses_path: str):
    df = pd.read_csv(misses_path)
    df["root_cause"] = [
        categorize_root_cause(row["app"], row["field"], str(row["agent"]), str(row["gold"]))
        for _, row in df.iterrows()
    ]
    df.to_csv(misses_path, index=False)
    print(f"Updated {len(df)} rows in {misses_path} with categorized root causes.")
    print("Root cause distribution:")
    print(df["root_cause"].value_counts())

if __name__ == "__main__":
    update_misses_csv("data/misses.csv")
