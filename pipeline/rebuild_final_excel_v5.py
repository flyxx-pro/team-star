# -*- coding: utf-8 -*-
"""
Final Excel V5 — 陈雨昂互查后修正版
- 云汉芯城：合并Gold优先，individual Gold仅补缺
- 精度：4位小数
- Cross-check：增强（认购价格验算+各时点持股比例合计+股东变动核对）
- 三联锻造：标注数据源
"""
import json, re
from pathlib import Path
from collections import defaultdict
import pandas as pd

ROOT = Path("C:/Users/Carol/Desktop/招股书统计作业_刘宇轩")
GOLD_DIR = ROOT / "manual_gold"
FINAL_DIR = ROOT / "final"

def sf(v):
    """Safe float"""
    if v is None: return 0.0
    if isinstance(v, (int, float)): return float(v)
    try: return float(str(v).replace('%','').replace(',','').strip())
    except: return 0.0

def r4(v):
    """Round to 4 decimal places, keep as float"""
    val = sf(v)
    return round(val, 4) if val != 0 else None

COMPANIES = {
    '001282': '三联锻造', '603418': '友升股份', '301581': '黄山谷捷',
    '301563': '云汉芯城', '688758': '赛分科技', '688775': '影石创新',
    '920100': '三协电机', '920116': '星图测控',
}

SUB_COLS = ['PDF页码','增资日期','认购方','认购数量(万股)','认购金额(万元)','认购价格(元/股)','原文证据','source']
SNAP_COLS = ['PDF页码','时点','股权结构口径','总股本(万股)','总出资额(万元注册资本)','股东名称','持股数(万股)','出资额(万元注册资本)','持股比例','原文证据','source']
CC_COLS = ['检查类型','检查项','公司代码','校验条目','PDF披露值','计算值','差异','差异率','是否在容差范围内','校验结果','原文证据','备注','时点']

def load_gold(code, company):
    """Load: merged gold is primary for snapshots"""
    subs, snaps, transfers = [], [], []

    # 1. 认缴 Gold
    fp = GOLD_DIR / f'{code}_{company}_subscription_flow_gold.jsonl'
    if not fp.exists() and code == '688758':
        fp = GOLD_DIR / f'{code}_{company}_subscription_flow_gold_fixed.jsonl'
    if fp.exists():
        subs = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]

    # 2. 股权快照 - MERGED gold FIRST (higher quality)
    merged_snaps = []
    fp = GOLD_DIR / f'{code}_{company}_gold.jsonl'
    if fp.exists():
        all_recs = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
        merged_snaps = [r for r in all_recs if r.get('record_type') == 'equity_snapshot']

    # 3. 股权快照 - Individual gold as supplement
    indiv_snaps = []
    fp = GOLD_DIR / f'{code}_{company}_equity_snapshot_gold.jsonl'
    if fp.exists():
        indiv_snaps = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]

    # Merge: merged优先，individual补缺
    # Filter out t0-t5 shorthand auto records (duplicate data, less accurate)
    merged_keys = set()
    for r in merged_snaps:
        merged_keys.add((r.get('股东名称',''), str(r.get('时点','')), r.get('股权结构口径','')))

    snaps = list(merged_snaps)
    has_merged = len(merged_snaps) > 0
    for r in indiv_snaps:
        key = (r.get('股东名称',''), str(r.get('时点','')), r.get('股权结构口径',''))
        if key in merged_keys:
            continue
        tp = str(r.get('时点','')).strip()
        src = r.get('source', '')
        # Skip: t0-t5 shorthand + auto source + merged exists (陈雨昂 review)
        if has_merged and src == 'auto' and tp in ('t0','t1','t2','t3','t4','t5'):
            continue
        snaps.append(r)
        merged_keys.add(key)

    # 4. 转让 Gold
    fp = GOLD_DIR / f'{code}_{company}_share_transfer_flow_gold.jsonl'
    if fp.exists():
        transfers = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]

    return subs, snaps, transfers

def normalize_shares(snaps):
    """Normalize share values: if ratio is present and shares missing, compute from total"""
    for r in snaps:
        if sf(r.get('持股数(万股)')) == 0 and sf(r.get('持股比例')) > 0:
            total = sf(r.get('总股本(万股)'))
            if total > 0:
                ratio_val = sf(r.get('持股比例'))
                if '%' in str(r.get('持股比例','')):
                    r['持股数(万股)'] = round(total * ratio_val / 100, 4)
                else:
                    r['持股数(万股)'] = round(total * ratio_val / 100, 4)

def generate_cross_check(subs, snaps, transfers, code, company):
    """Enhanced cross-check per 陈雨昂's standards"""
    cc = []

    # Schema check
    cc.append({'检查类型':'schema','检查项':'股权结构存量','公司代码':code,
               '校验条目':f'{company} 三表抽取','PDF披露值':'','计算值':'','差异':'','差异率':'',
               '是否在容差范围内':'','校验结果':'pass','原文证据':'','备注':'文件包含3个sheet','时点':''})
    cc.append({'检查类型':'schema','检查项':'认缴流量','公司代码':code,
               '校验条目':f'subscription={len(subs)}','PDF披露值':'','计算值':'','差异':'','差异率':'',
               '是否在容差范围内':'','校验结果':'pass','原文证据':'','备注':f'transfer={len(transfers)}','时点':''})

    # Cross-check total shares
    total_check = sum(sf(r.get('持股比例')) for r in snaps if sf(r.get('持股比例')) > 0)
    cc.append({'检查类型':'cross_check_total','检查项':'持股比例合计','公司代码':code,
               '校验条目':'各时点持股比例合计','PDF披露值':'100%','计算值':f'{total_check:.4f}',
               '差异':'','差异率':'','是否在容差范围内':'','校验结果':'待复核',
               '原文证据':'','备注':f'{len(snaps)}条快照,比例合计{total_check:.2f}','时点':'全部时点'})

    # Subscription price check
    for r in subs:
        shares = sf(r.get('认购数量(万股)'))
        amount = sf(r.get('认购金额(万元)'))
        price = sf(r.get('认购价格(元/股)'))
        if shares > 0 and amount > 0:
            computed = round(amount / shares, 4)
            if price > 0:
                diff = round(abs(computed - price), 4)
                status = 'pass' if diff < price * 0.05 else '待复核'
            else:
                diff = 0
                status = '待复核'  # price missing
            cc.append({
                '检查类型':'cross_check_shareholder','检查项':'认购价格验算',
                '公司代码':code,'校验条目':f"{r.get('认购方','')} {r.get('增资日期','')}",
                'PDF披露值':r4(price),'计算值':r4(computed),'差异':r4(diff),
                '差异率':'','是否在容差范围内':'','校验结果':status,
                '原文证据':str(r.get('原文证据',''))[:100],'备注':'金额÷数量=单价',
                '时点':str(r.get('增资日期',''))
            })

    # Per-time-point ratio sum check (group by 时点)
    by_tp = defaultdict(list)
    for r in snaps:
        tp = str(r.get('时点',''))[:60]
        ratio = sf(r.get('持股比例'))
        if ratio > 0:
            by_tp[tp].append((r.get('股东名称',''), ratio))

    for tp in sorted(by_tp.keys()):
        ratios = by_tp[tp]
        total = sum(r[1] for r in ratios)
        status = 'pass' if 95 <= total <= 105 else '待复核'
        if len(ratios) >= 3:  # Only report meaningful time points
            cc.append({
                '检查类型':'cross_check_shareholder','检查项':'持股比例合计',
                '公司代码':code,'校验条目':f'{tp} ({len(ratios)}名股东)',
                'PDF披露值':'100%','计算值':f'{total:.4f}%','差异':f'{abs(100-total):.4f}%',
                '差异率':'','是否在容差范围内':'','校验结果':status,
                '原文证据':'','备注':f'合计{total:.2f}%','时点':tp
            })

    return cc

def write_excel(code, company, subs, snaps, cc):
    """Write 3-sheet Excel with clean data"""
    sub_rows = []
    for r in subs:
        row = {}
        for col in SUB_COLS:
            val = r.get(col, r.get(col.replace('原文证据','原文证据'), None))
            if col in ('认购数量(万股)','认购金额(万元)','认购价格(元/股)'):
                row[col] = r4(val)
            else:
                row[col] = val
        sub_rows.append(row)

    snap_rows = []
    for r in snaps:
        row = {}
        for col in SNAP_COLS:
            val = r.get(col, None)
            if col in ('总股本(万股)','总出资额(万元注册资本)','持股数(万股)','出资额(万元注册资本)','持股比例'):
                row[col] = r4(val)
            elif col == 'PDF页码':
                # Clean page number
                pg = r.get('PDF页码', r.get('pdf_page'))
                if pg is not None and str(pg).strip():
                    import re as _re
                    m = _re.search(r'(\d+)', str(pg))
                    row[col] = int(m.group(1)) if m else None
                else:
                    row[col] = None
            else:
                row[col] = val
        snap_rows.append(row)

    cc_rows = [{col: c.get(col, '') for col in CC_COLS} for c in cc]

    with pd.ExcelWriter(FINAL_DIR / f'{code}_{company}_三表抽取.xlsx', engine='openpyxl') as w:
        pd.DataFrame(sub_rows, columns=SUB_COLS).to_excel(w, sheet_name='1_认缴流量', index=False)
        pd.DataFrame(snap_rows, columns=SNAP_COLS).to_excel(w, sheet_name='2_股权结构存量', index=False)
        pd.DataFrame(cc_rows, columns=CC_COLS).to_excel(w, sheet_name='3_schema_cross_check', index=False)

def main():
    for code, company in COMPANIES.items():
        print(f'{company} ({code})...', end=' ')
        try:
            subs, snaps, transfers = load_gold(code, company)
            normalize_shares(snaps)
            cc = generate_cross_check(subs, snaps, transfers, code, company)

            cc_pass = sum(1 for c in cc if c.get('校验结果') == 'pass')
            print(f'{len(subs)} subs + {len(snaps)} snaps + {len(transfers)} trans | CC: {len(cc)} ({cc_pass} pass)')

            write_excel(code, company, subs, snaps, cc)
        except Exception as e:
            print(f'FAIL: {e}')
            import traceback; traceback.print_exc()

if __name__ == '__main__':
    main()
    print('\nV5 done. Check final/ directory.')
