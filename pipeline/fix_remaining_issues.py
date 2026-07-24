# -*- coding: utf-8 -*-
"""批量修复陈雨昂互查发现的剩余问题"""
import json, re
from pathlib import Path

GOLD_DIR = Path("C:/Users/Carol/Desktop/招股书统计作业_刘宇轩/manual_gold")

def compute_ratio(r):
    """Compute 持股比例 from 持股数/总股本"""
    try:
        shares = float(r.get('持股数(万股)') or 0)
        total = float(r.get('总股本(万股)') or 0)
        if shares > 0 and total > 0:
            # Check all possible ratio field names
            for ratio_key in ['持股比例(%)', '持股比例', 'ratio']:
                pct = r.get(ratio_key)
                if pct is not None and pct != '' and pct != 0:
                    try:
                        if float(str(pct).replace('%','')) > 0:
                            return None  # Already has a value
                    except: pass
            return round(shares / total * 100, 4)
    except: pass
    return None

# 1. 黄山谷捷Gold: 补填持股比例
print("1. 黄山谷捷 持股比例...")
for fname in ['301581_黄山谷捷_gold.jsonl', '301581_黄山谷捷_equity_snapshot_gold.jsonl']:
    fp = GOLD_DIR / fname
    if not fp.exists(): continue
    recs = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
    fixed = 0
    for r in recs:
        ratio_col = next((k for k in r.keys() if '比例' in k), None)
        if ratio_col:
            old = r.get(ratio_col)
            computed = compute_ratio(r)
            if computed and (old is None or old == 0 or old == ''):
                r[ratio_col] = computed
                fixed += 1
    fp.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in recs), encoding='utf-8')
    print(f'  {fname}: fixed {fixed} records')

# 2. 星图测控: 补充2016设立期3条认缴
print("\n2. 星图测控 2016设立期...")
fp = GOLD_DIR / '920116_星图测控_subscription_flow_gold.jsonl'
recs = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
print(f"  现有{len(recs)}条认缴:")
for r in recs:
    print(f"    {r.get('增资日期')} | {r.get('认购方')} | source={r.get('source')}")

# Add 2016 establishment records if not found
has_2016 = any('2016' in str(r.get('增资日期','')) for r in recs)
if not has_2016:
    # 陈雨昂说刘宇轩缺失2016年公司设立阶段3条
    # 星图测控2016年6月设立,注册资本500万
    # 发起人: 中科星图(深圳)、四方测量、策星投资
    # 这些是设立时的出资，不是增资
    new_recs = [
        {
            'record_type': 'subscription_flow',
            'PDF页码': 34,
            '增资日期': '2016-06-02',
            '认购方': '中科星图(深圳)',
            '认购数量(万股)': None,
            '认购金额(万元)': None,
            '认购价格(元/股)': None,
            '出资额(万元注册资本)': 255,
            '原文证据': '2016年6月2日设立,中科星图(深圳)出资255万(招股书第34页)',
            'source': 'manual',
            'review_status': '待核实',
        },
        {
            'record_type': 'subscription_flow',
            'PDF页码': 34,
            '增资日期': '2016-06-02',
            '认购方': '四方测量',
            '认购数量(万股)': None,
            '认购金额(万元)': None,
            '认购价格(元/股)': None,
            '出资额(万元注册资本)': 155,
            '原文证据': '2016年6月2日设立,四方测量出资155万(招股书第34页)',
            'source': 'manual',
            'review_status': '待核实',
        },
        {
            'record_type': 'subscription_flow',
            'PDF页码': 34,
            '增资日期': '2016-06-02',
            '认购方': '策星投资',
            '认购数量(万股)': None,
            '认购金额(万元)': None,
            '认购价格(元/股)': None,
            '出资额(万元注册资本)': 90,
            '原文证据': '2016年6月2日设立,策星投资出资90万(招股书第34页)',
            'source': 'manual',
            'review_status': '待核实',
        },
    ]
    recs = new_recs + recs
    fp.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in recs), encoding='utf-8')
    print(f"  -> 已添加3条2016设立期认缴,共{len(recs)}条")
else:
    print("  -> 已有2016年记录")

# 3. 黄山谷捷: 每股单价 — 已有价格,验证即可
print("\n3. 黄山谷捷 价格验证...")
fp = GOLD_DIR / '301581_黄山谷捷_subscription_flow_gold.jsonl'
recs = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
for r in recs:
    shares = float(r.get('认购数量(万股)') or 0)
    amount = float(r.get('认购金额(万元)') or 0)
    price = float(r.get('认购价格(元/股)') or 0)
    if shares > 0 and amount > 0:
        computed = round(amount / shares, 4)
        if price == 0:
            r['认购价格(元/股)'] = computed
            print(f"  {r.get('认购方')}: 补填价格={computed}")
        else:
            status = 'OK' if abs(computed-price)<0.01 else 'WARN'
            print(f"  {r.get('认购方')}: 价格={price}, 验算={computed} [{status}]")

fp.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in recs), encoding='utf-8')

print("\n全部修复完成!")
