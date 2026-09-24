import json
import csv
import yaml

def prepare_review_queue():
    split = json.load(open('eval/split.json'))
    gold_apps = set(split['dev']).union(set(split['held_out']))
    pass2 = [json.loads(l) for l in open('data/pass2.jsonl', encoding='utf-8') if l.strip()]

    # Load hint URLs
    apps_meta = {a['id'].lower(): a for a in yaml.safe_load(open('apps.yaml'))}

    candidates = []
    # Target 20 representative non-gold apps
    target_apps = [
        "gitlab", "asana", "trello", "clickup", "monday", "jira", "airtable",
        "salesforce", "pipedrive", "zoho-crm", "apollo", "zendesk", "intercom",
        "resend", "postmark", "dropbox", "box", "coda", "supabase", "snowflake"
    ]

    for app_id in target_apps:
        if app_id in gold_apps:
            continue
        rec = next((r for r in pass2 if r['id'] == app_id), None)
        if not rec:
            continue

        meta = apps_meta.get(app_id, {})
        hint = meta.get('hint_url', f"https://developers.{app_id}.com")

        # Pick a flagged field
        for f in ['self_serve', 'openapi_spec_available', 'webhooks', 'auth_methods']:
            val = rec.get(f, {}).get('value')
            if val in ('unknown', None, ['unknown']):
                candidates.append({
                    'app': app_id,
                    'field': f,
                    'extractor_answer': str(val),
                    'verifier_answer': 'FLAGGED_FOR_REVIEW',
                    'url': hint,
                })
                break
        if len(candidates) >= 20:
            break

    with open('data/review_queue.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['app', 'field', 'extractor_answer', 'verifier_answer', 'url'])
        writer.writeheader()
        writer.writerows(candidates)

    print(f"Wrote {len(candidates)} non-gold review candidates to data/review_queue.csv")
    for c in candidates:
        print(f"[{c['app']}] {c['field']} -> {c['extractor_answer']} ({c['url']})")

if __name__ == "__main__":
    prepare_review_queue()
