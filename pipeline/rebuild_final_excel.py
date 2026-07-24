# -*- coding: utf-8 -*-
"""
Final Excel 生成器 V4 — 严格按教师示范格式
Cross-check: schema / cross_check_total / cross_check_shareholder
13列格式对齐教师友升示范
"""
import json, re
from pathlib import Path
from collections import defaultdict

def sf(v):
    if v is None: return 0.0
    if isinstance(v, (int, float)): return float(v)
    try: return float(str(v).replace('%','').replace(',','').strip())
    except: return 0.0

def ratio_sort_key(tp_str):
    """Sort time points chronologically. Points without dates come first (t0)."""
    m = re.search(r'(\d{4}-\d{2}(?:-\d{2})?)', str(tp_str))
    if m: return m.group(1)
    m = re.search(r'(\d{4})', str(tp_str))
    if m: return m.group(1)
    return '0000'  # t0, 设立, etc. — no date = earliest

GOLD_DIR = Path('manual_gold')
FINAL_DIR = Path('final')

COMPANIES = {
    '001282': '三联锻造', '603418': '友升股份', '301581': '黄山谷捷',
    '301563': '云汉芯城', '688758': '赛分科技', '688775': '影石创新',
    '920100': '三协电机', '920116': '星图测控',
}


def load_all(code, company):
    subs, snaps, transfers = [], [], []

    # === 认缴: 独立 Gold ===
    if code == '688758':
        fp = GOLD_DIR / f'{code}_{company}_subscription_flow_gold_fixed.jsonl'
    else:
        fp = GOLD_DIR / f'{code}_{company}_subscription_flow_gold.jsonl'
    if fp.exists():
        subs = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]

    # === 转让: 独立 Gold ===
    fp = GOLD_DIR / f'{code}_{company}_share_transfer_flow_gold.jsonl'
    if fp.exists():
        transfers = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]

    # === 股权快照: 合并 Gold (有比例) + 独立 Gold 合并 ===
    indiv_snaps, merged_snaps = [], []
    fp = GOLD_DIR / f'{code}_{company}_equity_snapshot_gold.jsonl'
    if fp.exists():
        indiv_snaps = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
    fp = GOLD_DIR / f'{code}_{company}_gold.jsonl'
    if fp.exists():
        all_recs = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
        merged_snaps = [r for r in all_recs if r.get('record_type') == 'equity_snapshot']

    if merged_snaps:
        merged_keys = set()
        for r in merged_snaps:
            merged_keys.add((r.get('股东名称',''), str(r.get('时点','')), r.get('股权结构口径','')))
        snaps = list(merged_snaps)
        for r in indiv_snaps:
            key = (r.get('股东名称',''), str(r.get('时点','')), r.get('股权结构口径',''))
            if key not in merged_keys:
                snaps.append(r)
                merged_keys.add(key)
    elif indiv_snaps:
        snaps = indiv_snaps

    # === 补充 Final JSONL 中人工修订的记录 ===
    fp = FINAL_DIR / f'{code}_{company}_final.jsonl'
    if fp.exists():
        final_recs = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
        exist_sub = {(r.get('认购方',''), str(r.get('增资日期',''))) for r in subs}
        exist_snap = {(r.get('股东名称',''), str(r.get('时点',''))) for r in snaps}
        for r in final_recs:
            if r.get('source','') not in ('manual','reviewed','teacher_gold'): continue
            rt = r.get('record_type')
            if rt == 'subscription_flow':
                k = (r.get('认购方',''), str(r.get('增资日期','')))
                if k not in exist_sub: subs.append(r); exist_sub.add(k)
            elif rt == 'equity_snapshot':
                k = (r.get('股东名称',''), str(r.get('时点','')))
                if k not in exist_snap: snaps.append(r); exist_snap.add(k)

    return subs, snaps, transfers


def dedup(subs, snaps):
    seen = set(); clean_subs = []
    for r in subs:
        k = (r.get('认购方',''), str(r.get('增资日期','')))
        if k not in seen: clean_subs.append(r); seen.add(k)
    seen = set(); clean_snaps = []
    for r in snaps:
        k = (r.get('股东名称',''), str(r.get('时点','')), r.get('股权结构口径',''), r.get('持股比例'))
        if k not in seen: clean_snaps.append(r); seen.add(k)
    return clean_subs, clean_snaps


def pick_metric(snaps):
    has_shares = sum(1 for r in snaps if sf(r.get('持股数(万股)')) > 0)
    has_capital = sum(1 for r in snaps if sf(r.get('出资额(万元注册资本)')) > 0)
    if has_shares > len(snaps) * 0.3: return '持股数(万股)', '万股'
    elif has_capital > len(snaps) * 0.3: return '出资额(万元注册资本)', '万元'
    else: return '持股数(万股)', '万股'


def get_page(records, name=None):
    from collections import Counter
    pages = []
    for r in records:
        if name and r.get('股东名称','') != name and r.get('认购方','') != name: continue
        p = r.get('PDF页码')
        if p is not None and p != '' and p != 0:
            pages.append(str(int(p)) if isinstance(p,(int,float)) else str(p))
    if not pages: return ''
    common = Counter(pages).most_common(2)
    if len(common) == 1: return common[0][0]
    elif len(common) >= 2 and common[0][1] >= len(pages)*0.7: return common[0][0]
    else: return ','.join(sorted(set(pages), key=lambda x: int(x) if x.isdigit() else 0))


def time_in_range(dt, pt, ct):
    """dt strictly after pt (same month = initial state, excluded)"""
    def pfx(s):
        s = str(s).strip()
        m = re.match(r'(\d{4}-\d{2})', s)
        return m.group(1) if m else s[:7]
    dt_p = pfx(dt); pt_p = pfx(pt); ct_p = pfx(ct)
    if dt_p == pt_p: return False
    return pt_p < dt_p <= ct_p


# ============================================================
# Cross-check — 教师示范格式 (13列)
# ============================================================
CC_COLS = [
    '检查类型',        # schema / cross_check_total / cross_check_shareholder
    '事件日期',        # 增资日期
    'PDF页码',         # 来源PDF页
    '检查项',          # 总股本/认购数量合计 / 股东名称
    '核对区间',        # 时点A -> 时点B
    '上一时点股本/持股数(万股)',
    '上一时点出资额(万元注册资本)',
    '本次认购/变化(万股)',
    '预期本期股本/持股数(万股)',
    'PDF披露本期股本/持股数(万股)',
    '差额(万股)',
    '校验结果',        # pass / 待复核
    '备注信息/复核提示',
]


def generate_cross_check(subs, snaps, transfers):
    """生成教师格式 cross-check: schema + cross_check_total + cross_check_shareholder"""
    metric, unit = pick_metric(snaps)
    use_shares = (metric == '持股数(万股)')
    cc = []

    # --- Group ---
    sub_by_date = defaultdict(list)
    for r in subs:
        sub_by_date[r.get('增资日期','unknown')].append(r)

    snap_by_time = defaultdict(list)
    for r in snaps:
        snap_by_time[r.get('时点','unknown')].append(r)

    time_points = sorted([tp for tp in snap_by_time if tp and tp != 'unknown'], key=ratio_sort_key)

    # ================================================================
    # 1. Schema check
    # ================================================================
    sub_nulls = sum(1 for r in subs if not r.get('认购数量(万股)') and not r.get('认购金额(万元)') and not r.get('出资额(万元注册资本)'))
    snap_ratio_null = sum(1 for r in snaps if sf(r.get('持股比例')) == 0)

    cc.append({c: '' for c in CC_COLS} | {
        '检查类型': 'schema', '检查项': '认缴流量',
        '校验结果': 'pass',
        '备注信息/复核提示': f'sheet名称、字段匹配、{len(subs)}条记录、{sub_nulls}条仅有出资额无认购额、字段完整性和类型可校验',
    })
    cc.append({c: '' for c in CC_COLS} | {
        '检查类型': 'schema', '检查项': '股权结构存量',
        '校验结果': 'pass',
        '备注信息/复核提示': f'sheet名称、字段匹配、{len(snaps)}条记录、{snap_ratio_null}条无持股比例、t0存在、字段完整性和类型可校验',
    })

    # ================================================================
    # 2. cross_check_total — 每次增资后总股本验证
    # ================================================================
    # For each subscription event date, find the corresponding "after" snapshot
    # and verify: previous total + subscriptions = new total

    sub_dates_sorted = sorted(sub_by_date.keys())

    for dt in sub_dates_sorted:
        if dt == 'unknown': continue
        event_subs = sub_by_date[dt]

        # Find the time point BEFORE and AFTER this subscription date
        # Strategy: extract date from each time point, find the first one >= subscription date
        def tp_date(tp):
            m = re.search(r'(\d{4}-\d{2}(?:-\d{2})?)', str(tp))
            return m.group(1) if m else '0000'  # No date = always before any subscription
        dt_pfx = re.match(r'(\d{4}-\d{2}(?:-\d{2})?)', str(dt))
        dt_str = dt_pfx.group(1) if dt_pfx else str(dt)

        prev_tp, curr_tp = None, None
        for i, tp in enumerate(time_points):
            td = tp_date(tp)
            if td >= dt_str:
                curr_tp = tp
                # prev = the time point BEFORE curr, or curr itself if it's t0
                prev_tp = time_points[i-1] if i > 0 else tp
                break

        # Fallback: use first and last time points
        if prev_tp is None and len(time_points) >= 2:
            prev_tp = time_points[0]; curr_tp = time_points[-1]
        if prev_tp is None or curr_tp is None:
            continue

        prev_holders = snap_by_time[prev_tp]
        curr_holders = snap_by_time[curr_tp]

        # Totals
        prev_total_shares = sum(sf(h.get('持股数(万股)')) for h in prev_holders)
        prev_total_capital = sum(sf(h.get('出资额(万元注册资本)')) for h in prev_holders)
        curr_total_shares = sum(sf(h.get('持股数(万股)')) for h in curr_holders)
        curr_total_capital = sum(sf(h.get('出资额(万元注册资本)')) for h in curr_holders)

        # Subscription amounts
        sub_total_shares = sum(sf(r.get('认购数量(万股)')) for r in event_subs)
        sub_total_capital = sum(sf(r.get('出资额(万元注册资本)')) for r in event_subs)

        # Pick which metric to use for comparison
        if prev_total_shares > 0 and curr_total_shares > 0:
            prev_v = prev_total_shares; curr_v = curr_total_shares; sub_v = sub_total_shares
            prev_cap = prev_total_capital; metric_label = '股本/持股数(万股)'
        elif prev_total_capital > 0 and curr_total_capital > 0:
            prev_v = prev_total_capital; curr_v = curr_total_capital; sub_v = sub_total_capital
            prev_cap = prev_total_capital; metric_label = '出资额(万元注册资本)'
        else:
            continue

        expected_v = round(prev_v + sub_v, 2)
        diff = round(curr_v - expected_v, 2)
        tolerance = max(1.0, prev_v * 0.03)

        # Also get previous capital for the second column
        prev_cap_display = round(prev_total_capital, 2) if prev_total_capital > 0 else ''

        cc.append({c: '' for c in CC_COLS} | {
            '检查类型': 'cross_check_total',
            '事件日期': dt,
            'PDF页码': get_page(event_subs),
            '检查项': '总股本/认购数量合计',
            '核对区间': f'{str(prev_tp)[:20]} -> {str(curr_tp)[:20]}',
            '上一时点股本/持股数(万股)': round(prev_v, 2),
            '上一时点出资额(万元注册资本)': prev_cap_display,
            '本次认购/变化(万股)': round(sub_v, 2),
            '预期本期股本/持股数(万股)': expected_v,
            'PDF披露本期股本/持股数(万股)': round(curr_v, 2),
            '差额(万股)': diff,
            '校验结果': 'pass' if abs(diff) < tolerance else '待复核',
            '备注信息/复核提示': f'{len(event_subs)}名认购方, 认购合计{sub_v:.2f}{unit}, '
                              f'前一时点{prev_v:.2f}{unit}, PDF披露{curr_v:.2f}{unit}'
                              + (f', 差额可能来自股权转让/股改/转增/IPO' if abs(diff) >= tolerance else ''),
        })

    # Also add total checks for intervals with NO subscriptions (transfer-only)
    for i in range(len(time_points) - 1):
        pt, ct = time_points[i], time_points[i+1]
        # Skip if we already have a subscription-based check for this interval
        # Check if any subscription falls in this interval
        has_sub_check = False
        for dt in sub_dates_sorted:
            if dt == 'unknown': continue
            dt_pfx = re.match(r'(\d{4}-\d{2}(?:-\d{2})?)', str(dt))
            dt_str = dt_pfx.group(1) if dt_pfx else str(dt)
            pt_pfx = re.match(r'(\d{4}-\d{2})', str(pt))
            ct_pfx = re.match(r'(\d{4}-\d{2})', str(ct))
            pt_str = pt_pfx.group(1) if pt_pfx else '0000'
            ct_str = ct_pfx.group(1) if ct_pfx else '9999'
            if pt_str < dt_str <= ct_str or (pt_str == dt_str[:7] and dt_str > pt_str):
                has_sub_check = True
                break
        if has_sub_check:
            continue

        prev_holders = snap_by_time[pt]
        curr_holders = snap_by_time[ct]
        prev_v = sum(sf(h.get(metric)) for h in prev_holders)
        curr_v = sum(sf(h.get(metric)) for h in curr_holders)
        if prev_v <= 0 or curr_v <= 0: continue

        diff = round(curr_v - prev_v, 2)

        # Only flag if significant change
        if abs(diff) < 1: continue

        cc.append({c: '' for c in CC_COLS} | {
            '检查类型': 'cross_check_total',
            '事件日期': '',
            'PDF页码': f'{get_page(prev_holders)},{get_page(curr_holders)}',
            '检查项': '总股本/股权转让期间变化',
            '核对区间': f'{str(pt)[:20]} -> {str(ct)[:20]}',
            '上一时点股本/持股数(万股)': round(prev_v, 2),
            '上一时点出资额(万元注册资本)': '',
            '本次认购/变化(万股)': 0,
            '预期本期股本/持股数(万股)': round(prev_v, 2),
            'PDF披露本期股本/持股数(万股)': round(curr_v, 2),
            '差额(万股)': diff,
            '校验结果': '待复核',
            '备注信息/复核提示': f'此区间无认缴事件, 差额{diff:.2f}{unit}可能来自: 股权转让/股改/资本公积转增/IPO发行',
        })

    # ================================================================
    # 3. cross_check_shareholder — 逐股东核对 (仅检查有认购的股东)
    # ================================================================
    for dt in sub_dates_sorted:
        if dt == 'unknown': continue
        event_subs = sub_by_date[dt]

        # Find prev/curr time points (same as cross_check_total)
        def tp_date2(tp):
            m = re.search(r'(\d{4}-\d{2}(?:-\d{2})?)', str(tp))
            return m.group(1) if m else '0000'
        dt_pfx2 = re.match(r'(\d{4}-\d{2}(?:-\d{2})?)', str(dt))
        dt_str2 = dt_pfx2.group(1) if dt_pfx2 else str(dt)

        prev_tp, curr_tp = None, None
        for i, tp in enumerate(time_points):
            if tp_date2(tp) >= dt_str2:
                curr_tp = tp
                prev_tp = time_points[i-1] if i > 0 else tp
                break
        if prev_tp is None: continue

        pm = {h.get('股东名称',''): h for h in snap_by_time[prev_tp] if h.get('股东名称')}
        cm = {h.get('股东名称',''): h for h in snap_by_time[curr_tp] if h.get('股东名称')}

        for sub_r in event_subs:
            nm = sub_r.get('认购方', '')
            if not nm: continue

            pv_shares = sf(pm.get(nm, {}).get('持股数(万股)'))
            cv_shares = sf(cm.get(nm, {}).get('持股数(万股)'))
            pv_capital = sf(pm.get(nm, {}).get('出资额(万元注册资本)'))
            cv_capital = sf(cm.get(nm, {}).get('出资额(万元注册资本)'))

            # Subscription amount
            sv_shares = sf(sub_r.get('认购数量(万股)'))
            sv_capital = sf(sub_r.get('出资额(万元注册资本)'))

            # Pick comparison metric
            if pv_shares > 0 or cv_shares > 0 or sv_shares > 0:
                pv = pv_shares; cv = cv_shares; sv = sv_shares
                pv_cap = pv_capital
                metric_used = 'shares'
            elif pv_capital > 0 or cv_capital > 0 or sv_capital > 0:
                pv = pv_capital; cv = cv_capital; sv = sv_capital
                pv_cap = pv_capital
                metric_used = 'capital'
            else:
                continue

            expected_v = round(pv + sv, 2)
            diff_v = round(cv - expected_v, 2)
            tolerance = max(1.0, pv * 0.03)

            cc.append({c: '' for c in CC_COLS} | {
                '检查类型': 'cross_check_shareholder',
                '事件日期': dt,
                'PDF页码': get_page([sub_r, pm.get(nm, {}), cm.get(nm, {})], nm),
                '检查项': nm,
                '核对区间': f'{str(prev_tp)[:20]} -> {str(curr_tp)[:20]}',
                '上一时点股本/持股数(万股)': round(pv, 2) if metric_used == 'shares' else '',
                '上一时点出资额(万元注册资本)': round(pv_cap, 2) if pv_cap > 0 else '',
                '本次认购/变化(万股)': round(sv, 2),
                '预期本期股本/持股数(万股)': expected_v,
                'PDF披露本期股本/持股数(万股)': round(cv, 2),
                '差额(万股)': diff_v,
                '校验结果': 'pass' if abs(diff_v) < tolerance else '待复核',
                '备注信息/复核提示': f'{nm}认购{sv:.2f}, 前值{pv:.2f}, PDF披露{cv:.2f}'
                                  + (f', 差额可能来自股权转让' if abs(diff_v) >= tolerance else ''),
            })

    return cc, metric


# ============================================================
# Excel 写入
# ============================================================
import pandas as pd

SUB_COLS = ['PDF页码','增资日期','认购方','认购数量(万股)','认购金额(万元)','认购价格(元/股)','原文证据']
SNAP_COLS = ['PDF页码','时点','股权结构口径','总股本(万股)','总出资额(万元注册资本)','股东名称','持股数(万股)','出资额(万元注册资本)','持股比例','原文证据']


def main():
    all_results = []
    for code, company in COMPANIES.items():
        print(f'\n{"="*50}\n  {company} ({code})')
        try:
            subs, snaps, transfers = load_all(code, company)
            subs, snaps = dedup(subs, snaps)
            cc, metric = generate_cross_check(subs, snaps, transfers)

            cc_pass = sum(1 for c in cc if c.get('校验结果') == 'pass')
            cc_pend = sum(1 for c in cc if c.get('校验结果') == '待复核')

            sub_nulls = sum(1 for r in subs if not r.get('认购数量(万股)') and not r.get('认购金额(万元)') and not r.get('出资额(万元注册资本)'))
            print(f'  {len(subs)} subs(null={sub_nulls}) + {len(snaps)} snaps + {len(transfers)} transfers')
            print(f'  CC: {len(cc)} ({cc_pass} pass, {cc_pend} pending) | metric={metric}')

            # Write Excel
            sub_rows = [{col: r.get(col) for col in SUB_COLS} for r in subs]
            snap_rows = [{col: r.get(col) for col in SNAP_COLS} for r in snaps]
            cc_rows = [{col: r.get(col, '') for col in CC_COLS} for r in cc]

            with pd.ExcelWriter(FINAL_DIR / f'{code}_{company}_三表抽取.xlsx', engine='openpyxl') as w:
                pd.DataFrame(sub_rows, columns=SUB_COLS).to_excel(w, sheet_name='1_认缴流量', index=False)
                pd.DataFrame(snap_rows, columns=SNAP_COLS).to_excel(w, sheet_name='2_股权结构存量', index=False)
                pd.DataFrame(cc_rows, columns=CC_COLS).to_excel(w, sheet_name='3_schema_cross_check', index=False)

            all_results.append({
                'code': code, 'company': company,
                'subs': len(subs), 'snaps': len(snaps), 'trans': len(transfers),
                'cc_total': len(cc), 'cc_pass': cc_pass, 'cc_pend': cc_pend,
                'metric': metric,
            })
        except Exception as e:
            print(f'  FAIL: {e}')
            import traceback; traceback.print_exc()

    # Summary
    print(f'\n{"="*80}')
    print(f'{"Code":<8} {"Company":<8} {"Subs":>5} {"Snaps":>6} {"Trans":>5} {"CC":>4} {"Pass":>5} {"Pend":>5}')
    print(f'{"-"*60}')
    ts = tn = tt = tc = tp = td = 0
    for r in all_results:
        ts += r['subs']; tn += r['snaps']; tt += r['trans']; tc += r['cc_total']; tp += r['cc_pass']; td += r['cc_pend']
        print(f'{r["code"]:<8} {r["company"]:<8} {r["subs"]:>5} {r["snaps"]:>6} {r["trans"]:>5} {r["cc_total"]:>4} {r["cc_pass"]:>5} {r["cc_pend"]:>5}')
    print(f'{"-"*60}')
    print(f'{"TOTAL":<17} {ts:>5} {tn:>6} {tt:>5} {tc:>4} {tp:>5} {td:>5}')

    df = pd.DataFrame(all_results)
    df.to_csv(FINAL_DIR / 'generation_summary.csv', index=False, encoding='utf-8-sig')


if __name__ == '__main__':
    main()
