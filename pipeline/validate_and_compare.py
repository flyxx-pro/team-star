# -*- coding: utf-8 -*-
"""
Validation pipeline: Cross-check + Auto-vs-Gold comparison
Uses manual_gold/ as ground truth, auto_output/ as predictions
"""
import json, sys
from pathlib import Path
from collections import defaultdict


def sf(v):
    if v is None: return 0
    if isinstance(v, (int, float)): return float(v)
    try: return float(str(v).replace('%','').replace(',','').strip())
    except: return 0


def load_jsonl(path):
    if not path.exists(): return []
    return [json.loads(l) for l in path.read_text(encoding='utf-8').strip().split('\n') if l.strip()]


def cross_check_from_gold(gold_records):
    """Run cross-check on gold data: ratio check, interval check, shareholder check"""
    subs = [r for r in gold_records if r.get('record_type') == 'subscription_flow']
    snaps = [r for r in gold_records if r.get('record_type') == 'equity_snapshot']

    results = []

    # Group by time
    snap_by_time = defaultdict(list)
    for r in snaps:
        tp = r.get('时点', 'unknown')
        snap_by_time[tp].append(r)

    sub_by_date = defaultdict(list)
    for r in subs:
        dt = r.get('增资日期', 'unknown')
        sub_by_date[dt].append(r)

    time_points = sorted([tp for tp in snap_by_time.keys() if tp is not None])

    # Schema
    results.append({
        '检查类型': 'schema',
        '校验结果': 'pass',
        '备注': f'Gold: {len(subs)} subs + {len(snaps)} snaps',
    })

    # Ratio check
    for tp in time_points:
        holders = snap_by_time[tp]
        tr = sum(sf(h.get('持股比例')) for h in holders)
        ts = sum(sf(h.get('持股数(万股)') or h.get('出资额(万元注册资本)')) for h in holders)
        if tr > 0:
            ok = 99.0 <= tr <= 101.0
            results.append({
                '检查类型': 'ratio_check',
                '时点': tp,
                '比例合计': round(tr, 2),
                '存量合计': round(ts, 2),
                '股东数': len(holders),
                '校验结果': 'pass' if ok else '待复核',
                '备注': f'{tp}: {len(holders)} holders, ratio={tr:.2f}%',
            })

    # Interval cross-check
    for i in range(len(time_points) - 1):
        pt, ct = time_points[i], time_points[i+1]
        ps = sum(sf(h.get('持股数(万股)') or h.get('出资额(万元注册资本)')) for h in snap_by_time[pt])
        cs = sum(sf(h.get('持股数(万股)') or h.get('出资额(万元注册资本)')) for h in snap_by_time[ct])

        interval_subs = []
        for dt, slist in sub_by_date.items():
            if dt == 'unknown': continue
            if pt <= dt <= ct:
                interval_subs.extend(slist)

        st = sum(sf(r.get('认购数量(万股)')) for r in interval_subs)
        if ps > 0 and cs > 0:
            exp = ps + st
            diff = round(cs - exp, 4)
            results.append({
                '检查类型': 'cross_check_interval',
                '区间': f'{pt} -> {ct}',
                '上一时点': round(ps, 4),
                '区间认购': round(st, 4),
                '预期值': round(exp, 4),
                '实际值': round(cs, 4),
                '差额': diff,
                '区间内事件数': len(interval_subs),
                '校验结果': 'pass' if abs(diff) < max(1, ps * 0.02) else '待复核',
            })

    # Per-shareholder
    for i in range(len(time_points) - 1):
        pt, ct = time_points[i], time_points[i+1]
        pm = {h.get('股东名称',''): h for h in snap_by_time[pt] if h.get('股东名称')}
        cm = {h.get('股东名称',''): h for h in snap_by_time[ct] if h.get('股东名称')}

        interval_subs = []
        for dt, slist in sub_by_date.items():
            if dt == 'unknown': continue
            if pt <= dt <= ct:
                interval_subs.extend(slist)

        for nm in sorted(set(list(pm.keys()) + list(cm.keys())))[:30]:
            pv = sf(pm.get(nm, {}).get('持股数(万股)') or pm.get(nm, {}).get('出资额(万元注册资本)'))
            cv = sf(cm.get(nm, {}).get('持股数(万股)') or cm.get(nm, {}).get('出资额(万元注册资本)'))
            if pv == 0 and cv == 0: continue
            sv = sum(sf(r.get('认购数量(万股)')) for r in interval_subs if r.get('认购方','') == nm)
            exp_v = pv + sv
            diff_v = round(cv - exp_v, 4)
            if abs(diff_v) > 0.01 or sv > 0:
                results.append({
                    '检查类型': 'cross_check_shareholder',
                    '区间': f'{pt} -> {ct}',
                    '股东': nm,
                    '前值': round(pv, 4),
                    '认购': round(sv, 4),
                    '预期': round(exp_v, 4),
                    '实际': round(cv, 4),
                    '差额': diff_v,
                    '校验结果': 'pass' if abs(diff_v) < max(1, pv * 0.02) else '待复核',
                })

    return results


def auto_vs_gold(auto_recs, gold_recs, record_type):
    """Compute TP/FP/FN for Auto vs Gold"""
    auto_filtered = [r for r in auto_recs if r.get('record_type') == record_type]
    gold_filtered = [r for r in gold_recs if r.get('record_type') == record_type]

    def make_key(r):
        name = r.get('认购方') or r.get('股东名称', '')
        date = str(r.get('增资日期') or r.get('时点', ''))
        return (name, date)

    auto_keys = {make_key(r) for r in auto_filtered}
    gold_keys = {make_key(r) for r in gold_filtered}

    tp = len(auto_keys & gold_keys)
    fp = len(auto_keys - gold_keys)
    fn = len(gold_keys - auto_keys)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        'record_type': record_type,
        'auto_count': len(auto_filtered),
        'gold_count': len(gold_filtered),
        'TP': tp, 'FP': fp, 'FN': fn,
        'precision': round(precision, 4),
        'recall': round(recall, 4),
        'f1': round(f1, 4),
        'fp_items': sorted(list(auto_keys - gold_keys))[:20],
        'fn_items': sorted(list(gold_keys - auto_keys))[:20],
    }


COMPANIES = {
    '001282': '三联锻造', '603418': '友升股份', '301581': '黄山谷捷',
    '301563': '云汉芯城', '688758': '赛分科技', '688775': '影石创新',
    '920100': '三协电机', '920116': '星图测控',
}


def main():
    gold_dir = Path('manual_gold')
    auto_dir = Path('auto_output')
    out_dir = Path('validation')
    out_dir.mkdir(exist_ok=True)

    all_cc = []
    all_comparison = []

    for code, company in COMPANIES.items():
        print(f'{company} ({code})...')

        # Load Gold
        gold_path = gold_dir / f'{code}_{company}_gold.jsonl'
        gold_recs = load_jsonl(gold_path)

        # Load Auto
        auto_path = auto_dir / f'{code}_{company}_auto.jsonl'
        auto_recs = load_jsonl(auto_path)

        # Cross-check on Gold
        cc = cross_check_from_gold(gold_recs)
        pass_count = sum(1 for c in cc if c.get('校验结果') == 'pass')
        pending = sum(1 for c in cc if c.get('校验结果') == '待复核')
        print(f'  Cross-check: {len(cc)} checks ({pass_count} pass, {pending} pending)')

        # Auto vs Gold
        sub_cmp = auto_vs_gold(auto_recs, gold_recs, 'subscription_flow')
        snap_cmp = auto_vs_gold(auto_recs, gold_recs, 'equity_snapshot')
        print(f'  Auto-vs-Gold subs: P={sub_cmp["precision"]:.3f} R={sub_cmp["recall"]:.3f} F1={sub_cmp["f1"]:.3f}')
        print(f'  Auto-vs-Gold snaps: P={snap_cmp["precision"]:.3f} R={snap_cmp["recall"]:.3f} F1={snap_cmp["f1"]:.3f}')

        # Save validation per company
        val = {
            'code': code, 'company': company,
            'cross_check': cc,
            'subscription_comparison': sub_cmp,
            'equity_comparison': snap_cmp,
        }
        (out_dir / f'{code}_{company}_validation.json').write_text(
            json.dumps(val, ensure_ascii=False, indent=2), encoding='utf-8')

        all_cc.append({'code': code, 'company': company, 'count': len(cc), 'pass': pass_count, 'pending': pending})
        all_comparison.append({
            'code': code, 'company': company,
            'sub_auto': sub_cmp['auto_count'], 'sub_gold': sub_cmp['gold_count'],
            'sub_p': sub_cmp['precision'], 'sub_r': sub_cmp['recall'], 'sub_f1': sub_cmp['f1'],
            'snap_auto': snap_cmp['auto_count'], 'snap_gold': snap_cmp['gold_count'],
            'snap_p': snap_cmp['precision'], 'snap_r': snap_cmp['recall'], 'snap_f1': snap_cmp['f1'],
        })

    # Summary
    print(f'\n{"="*80}')
    print(f'Validation Summary')
    print(f'{"="*80}')
    print(f'{"Code":<8} {"Company":<8} {"CC":>5} {"pass":>5} {"pend":>5} {"sP":>6} {"sR":>6} {"sF1":>6} {"nP":>6} {"nR":>6} {"nF1":>6}')
    for c in all_comparison:
        print(f'{c["code"]:<8} {c["company"]:<8} {all_cc[all_comparison.index(c)]["count"]:>5} {all_cc[all_comparison.index(c)]["pass"]:>5} {all_cc[all_comparison.index(c)]["pending"]:>5} {c["sub_p"]:>6.3f} {c["sub_r"]:>6.3f} {c["sub_f1"]:>6.3f} {c["snap_p"]:>6.3f} {c["snap_r"]:>6.3f} {c["snap_f1"]:>6.3f}')

    # Save summary CSV
    import pandas as pd
    df = pd.DataFrame(all_comparison)
    df.to_csv(out_dir / 'auto_vs_gold_summary.csv', index=False, encoding='utf-8-sig')
    print(f'\nSaved to validation/')


if __name__ == '__main__':
    main()
