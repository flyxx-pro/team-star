# -*- coding: utf-8 -*-
"""Generate comparison CSV from Gold data for group review"""
import json, csv
from pathlib import Path
from collections import defaultdict

GOLD_DIR = Path('manual_gold')
COMPANIES = {
    '001282': '三联锻造', '603418': '友升股份', '301581': '黄山谷捷',
    '301563': '云汉芯城', '688758': '赛分科技', '688775': '影石创新',
    '920100': '三协电机', '920116': '星图测控',
}

def sf(v):
    if v is None: return 0
    if isinstance(v, (int,float)): return float(v)
    try: return float(str(v).replace('%','').replace(',','').strip())
    except: return 0

def load_gold(code, company):
    """Load gold records from merged file + individual files to get complete data"""
    recs = []
    # Try merged file first
    fp = GOLD_DIR / f'{code}_{company}_gold.jsonl'
    if fp.exists():
        recs.extend(json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip())
    # Also check individual files for any missing record types
    for suffix in ['subscription_flow', 'equity_snapshot', 'share_transfer_flow']:
        fp2 = GOLD_DIR / f'{code}_{company}_{suffix}_gold.jsonl'
        if fp2.exists():
            extra = [json.loads(l) for l in fp2.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
            existing_ids = {(r.get('record_type'), r.get('认购方') or r.get('股东名称'), str(r.get('增资日期') or r.get('时点'))) for r in recs}
            for r in extra:
                rid = (r.get('record_type'), r.get('认购方') or r.get('股东名称'), str(r.get('增资日期') or r.get('时点')))
                if rid not in existing_ids:
                    recs.append(r)
                    existing_ids.add(rid)
    return recs

rows = []
for code, company in COMPANIES.items():
    recs = load_gold(code, company)
    subs = [r for r in recs if r.get('record_type') == 'subscription_flow']
    snaps = [r for r in recs if r.get('record_type') == 'equity_snapshot']
    transfers = [r for r in recs if r.get('record_type') == 'share_transfer_flow']

    # Subscription stats
    sub_total_shares = sum(sf(r.get('认购数量(万股)')) for r in subs)
    sub_total_amount = sum(sf(r.get('认购金额(万元)')) for r in subs)

    # Snapshot stats
    times = set(r.get('时点','') for r in snaps)
    # Find the latest time point with ratios
    snap_by_time = defaultdict(list)
    for r in snaps:
        snap_by_time[r.get('时点','')].append(r)
    latest_tp = sorted(snap_by_time.keys())[-1] if snap_by_time else ''
    latest_holders = snap_by_time.get(latest_tp, [])
    latest_ratio = sum(sf(r.get('持股比例')) for r in latest_holders)
    latest_shares = sum(sf(r.get('持股数(万股)') or r.get('出资额(万元注册资本)')) for r in latest_holders)

    # PE/VC
    has_pevc = any(r.get('investor_type') and 'PE' in str(r.get('investor_type','')).upper() or
                   r.get('is_pevc') == 'yes' for r in subs)

    rows.append({
        'code': code, 'company': company,
        'sub_count': len(subs), 'sub_rounds': len(set(r.get('增资日期','') for r in subs)),
        'sub_total_shares_wan': round(sub_total_shares, 2),
        'sub_total_amount_wan': round(sub_total_amount, 2),
        'snap_count': len(snaps), 'snap_times': len(times),
        'latest_ratio_pct': round(latest_ratio, 2),
        'latest_total_shares_wan': round(latest_shares, 2),
        'transfer_count': len(transfers),
        'has_pevc': 'Y' if has_pevc else 'N',
        'notes': '刘宇轩 Gold',
    })

# Write CSV
out = Path('review/liuyuxuan_gold_summary.csv')
with open(out, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(rows)
print(f'Saved: {out}')

# Print table
for r in rows:
    print(f'{r["code"]} {r["company"]:<6} | subs={r["sub_count"]:>2}({r["sub_rounds"]}轮) | shares={r["sub_total_shares_wan"]:>8.1f}万 | amt={r["sub_total_amount_wan"]:>8.0f}万 | snaps={r["snap_count"]:>3}({r["snap_times"]}时点) | ratio={r["latest_ratio_pct"]:.1f}% | 转让={r["transfer_count"]} | PEVC={r["has_pevc"]}')
