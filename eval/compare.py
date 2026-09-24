import json
import pandas as pd
from eval.score import values_match

split = json.load(open('eval/split.json'))
dev_apps = set(split['dev'])
held_out_apps = set(split['held_out'])
gold_df = pd.read_csv('eval/gold.csv')

def get_stats(pred_path):
    preds = {json.loads(line)['id'].lower(): json.loads(line) for line in open(pred_path, encoding='utf-8') if line.strip()}
    stats = {'dev': {}, 'held_out': {}}
    for _, row in gold_df.iterrows():
        app = str(row['app']).strip().lower()
        field = str(row['field']).strip()
        gold_val = row['gold_value']
        target_split = 'dev' if app in dev_apps else ('held_out' if app in held_out_apps else None)
        if not target_split:
            continue
        if field not in stats[target_split]:
            stats[target_split][field] = [0, 0]
        stats[target_split][field][1] += 1
        rec = preds.get(app, {})
        val = rec.get(field, {}).get('value') if isinstance(rec.get(field), dict) else rec.get(field)
        if values_match(val, gold_val):
            stats[target_split][field][0] += 1
    return stats

s1 = get_stats('data/pass1.jsonl')
s2 = get_stats('data/pass2.jsonl')

fields = sorted(s1['dev'].keys())
print(f"| {'Field':<24} | {'Dev (P1)':<10} | {'Dev (P2)':<10} | {'Held-Out (P1)':<14} | {'Held-Out (P2)':<14} |")
print('|' + '-'*26 + '|' + '-'*12 + '|' + '-'*12 + '|' + '-'*16 + '|' + '-'*16 + '|')
for f in fields:
    d1 = f"{s1['dev'][f][0]}/{s1['dev'][f][1]} ({s1['dev'][f][0]/s1['dev'][f][1]*100:.0f}%)"
    d2 = f"{s2['dev'][f][0]}/{s2['dev'][f][1]} ({s2['dev'][f][0]/s2['dev'][f][1]*100:.0f}%)"
    h1 = f"{s1['held_out'][f][0]}/{s1['held_out'][f][1]} ({s1['held_out'][f][0]/s1['held_out'][f][1]*100:.0f}%)"
    h2 = f"{s2['held_out'][f][0]}/{s2['held_out'][f][1]} ({s2['held_out'][f][0]/s2['held_out'][f][1]*100:.0f}%)"
    print(f"| {f:<24} | {d1:<10} | {d2:<10} | {h1:<14} | {h2:<14} |")

# Totals
d1_tot = sum(s1['dev'][f][0] for f in fields)
d1_n = sum(s1['dev'][f][1] for f in fields)
d2_tot = sum(s2['dev'][f][0] for f in fields)
d2_n = sum(s2['dev'][f][1] for f in fields)
h1_tot = sum(s1['held_out'][f][0] for f in fields)
h1_n = sum(s1['held_out'][f][1] for f in fields)
h2_tot = sum(s2['held_out'][f][0] for f in fields)
h2_n = sum(s2['held_out'][f][1] for f in fields)

print('|' + '='*26 + '|' + '='*12 + '='*12 + '|' + '='*16 + '='*16 + '|')
print(f"| {'TOTAL':<24} | {d1_tot}/{d1_n} ({d1_tot/d1_n*100:.1f}%) | {d2_tot}/{d2_n} ({d2_tot/d2_n*100:.1f}%) | {h1_tot}/{h1_n} ({h1_tot/h1_n*100:.1f}%) | {h2_tot}/{h2_n} ({h2_tot/h2_n*100:.1f}%) |")
