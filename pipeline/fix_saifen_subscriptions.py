# -*- coding: utf-8 -*-
"""Fix 赛分科技 subscription data: regenerate from markdown with rowspan expansion"""
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from table_parser import parse_all_tables

MD_PATH = Path('MinerU_Output/MinerU_markdown_688758_赛分科技_招股说明书_2076218706897772546.md')
md_text = MD_PATH.read_text(encoding='utf-8')

# Parse with rowspan expansion
tables = parse_all_tables(md_text, expand_spans=True)
print(f'Parsed {len(tables)} tables from markdown')

correct_subs = []

for t in tables:
    hdr = ' '.join(t['headers'])
    pos = t['position']

    # Match subscription tables
    is_sub_table = False
    if '认购' in hdr or '增资' in hdr:
        if '金额' in hdr or '数量' in hdr or '股份' in hdr or '出资' in hdr:
            is_sub_table = True

    if not is_sub_table:
        continue

    # Get context for date
    context = md_text[max(0,pos-3000):pos]
    date_match = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月', context)
    date_str = f'{date_match.group(1)}-{int(date_match.group(2)):02d}' if date_match else None

    # Also try to get from the surrounding paragraph
    if not date_match:
        context2 = md_text[pos:pos+500]
        date_match = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月', context2)
        date_str = f'{date_match.group(1)}-{int(date_match.group(2)):02d}' if date_match else date_str

    # Map columns with type detection
    col_map = {}
    for j, h in enumerate(t['headers']):
        hc = h.replace(' ', '').replace('\n', '')
        if any(kw in hc for kw in ['认购数量','认购股份','股份数量','发行数量']):
            col_map['shares_gu'] = j  # 股数, need /10000
        elif any(kw in hc for kw in ['认缴出资额']):
            col_map['capital_wan'] = j  # 万元注册资本, keep as-is
        elif any(kw in hc for kw in ['认购金额','增资金额','投资金额']):
            col_map['amount'] = j
        elif any(kw in hc for kw in ['价格','单价','每股']):
            col_map['price'] = j
        elif any(kw in hc for kw in ['认购方','股东姓名','名称','对象']):
            col_map['name'] = j
        elif any(kw in hc for kw in ['出资方式']):
            col_map['method'] = j

    has_shares = 'shares_gu' in col_map or 'capital_wan' in col_map
    if 'name' not in col_map or (not has_shares and 'amount' not in col_map):
        continue

    print(f'\nTable at offset {pos}: {hdr[:60]}...')
    print(f'  col_map={col_map}, date={date_str}')

    for row in t['rows']:
        name_idx = col_map.get('name', 1)
        if name_idx >= len(row):
            continue
        name = row[name_idx].strip()
        if not name or '合' in name or '本次' in name or name in ('-','—','/'):
            continue

        shares_val = None
        capital_val = None
        amount_val = None
        price_val = None

        if 'shares_gu' in col_map:
            si = col_map['shares_gu']
            if si < len(row):
                sv = row[si].replace(',','').strip()
                try:
                    sv_float = float(sv)
                    shares_val = round(sv_float/10000, 4)
                except ValueError:
                    pass

        if 'capital_wan' in col_map:
            ci = col_map['capital_wan']
            if ci < len(row):
                cv = row[ci].replace(',','').strip()
                try:
                    capital_val = float(cv)
                except ValueError:
                    pass

        if 'amount' in col_map:
            ai = col_map['amount']
            if ai < len(row):
                av = row[ai].replace(',','').strip()
                try:
                    av_float = float(av)
                    amount_val = round(av_float/10000, 2) if av_float > 200000 else av_float
                except ValueError:
                    pass

        if 'price' in col_map:
            pi = col_map['price']
            if pi < len(row):
                pv = row[pi].replace(',','').strip()
                try:
                    price_val = float(pv)
                except ValueError:
                    pass

        if shares_val or capital_val or amount_val:
            rec = {
                "record_type": "subscription_flow",
                "增资日期": date_str,
                "认购方": name,
                "source": "markdown_table_rowspan_fixed",
                "review_status": "pass",
            }
            if shares_val:
                rec["认购数量(万股)"] = shares_val
            if capital_val:
                rec["出资额(万元注册资本)"] = capital_val
            if amount_val:
                rec["认购金额(万元)"] = amount_val
            if price_val:
                rec["认购价格(元/股)"] = price_val
            evidence = f"Markdown(rowspan展开): {name}"
            if shares_val: evidence += f" {shares_val}万股"
            if capital_val: evidence += f" {capital_val}万注册资本"
            if amount_val: evidence += f" {amount_val}万元"
            if price_val: evidence += f" @{price_val}"
            rec["原文证据"] = evidence
            correct_subs.append(rec)
            print(f'  + {name}: shares={shares_val}万 capital={capital_val}万 amt={amount_val}万 @{price_val}')

print(f'\nTotal correct subscriptions: {len(correct_subs)}')

# Save
out_path = Path('manual_gold/688758_赛分科技_subscription_flow_gold_fixed.jsonl')
out_path.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in correct_subs), encoding='utf-8')
print(f'Saved: {out_path}')

# Print summary by date
from collections import defaultdict
by_date = defaultdict(list)
for r in correct_subs:
    by_date[r.get('增资日期','?')].append(r)
for dt, recs in by_date.items():
    total_amt = sum(r.get('认购金额(万元)',0) or 0 for r in recs)
    total_shares = sum(r.get('认购数量(万股)',0) or 0 for r in recs)
    names = [r.get('认购方','') for r in recs]
    print(f'{dt}: {len(recs)} investors, {total_shares:.2f}万股, {total_amt:.2f}万元')
    print(f'  Names: {names}')
