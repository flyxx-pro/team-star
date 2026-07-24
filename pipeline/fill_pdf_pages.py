# -*- coding: utf-8 -*-
"""
Fill missing PDF page numbers in Gold records.
Approach:
  1. Parse "第X页" from 时点/原文证据 fields
  2. Map subscription dates → pages (subs have good page numbers)
  3. For equity snapshots: assign page = nearest subscription round's page
  4. Save updated gold files
"""
import json, re
from pathlib import Path
from collections import defaultdict

GOLD_DIR = Path('manual_gold')

COMPANIES = {
    '001282': '三联锻造', '603418': '友升股份', '301581': '黄山谷捷',
    '301563': '云汉芯城', '688758': '赛分科技', '688775': '影石创新',
    '920100': '三协电机', '920116': '星图测控',
}


def fill_one_company(code, company):
    """Fill pages for all gold files of one company"""
    total = 0

    # === 1. Load subscription records (best source of page numbers) ===
    sub_path = GOLD_DIR / f'{code}_{company}_subscription_flow_gold.jsonl'
    # Also check fixed version for 赛分
    if code == '688758':
        alt = GOLD_DIR / f'{code}_{company}_subscription_flow_gold_fixed.jsonl'
        if alt.exists():
            sub_path = alt

    subs = []
    date_page_map = {}  # 增资日期 → page
    if sub_path.exists():
        subs = [json.loads(l) for l in sub_path.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
        for r in subs:
            dt = r.get('增资日期', '')
            pg = r.get('PDF页码')
            if dt and pg and pg != 0 and pg != '':
                try:
                    date_page_map[dt] = int(pg)
                except: pass

    # === 2. Load equity snapshot records ===
    snap_path = GOLD_DIR / f'{code}_{company}_equity_snapshot_gold.jsonl'
    snaps = []
    if snap_path.exists():
        snaps = [json.loads(l) for l in snap_path.read_text(encoding='utf-8').strip().split('\n') if l.strip()]

    # === 3. Load merged gold (has more snaps, may have page hints in 时点) ===
    merged_path = GOLD_DIR / f'{code}_{company}_gold.jsonl'
    merged_snaps = []
    if merged_path.exists():
        all_recs = [json.loads(l) for l in merged_path.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
        merged_snaps = [r for r in all_recs if r.get('record_type') == 'equity_snapshot']

    # === 4. Build time_point → page mapping from all sources ===
    tp_page_map = {}

    # 4a: Parse "第X页" from 时点 and 原文证据 fields
    for r in snaps + merged_snaps:
        tp = str(r.get('时点', ''))
        evidence = str(r.get('原文证据', ''))
        for text in [tp, evidence]:
            m = re.search(r'第\s*(\d+)\s*页', text)
            if m:
                pg = int(m.group(1))
                if pg > 0:
                    tp_page_map[tp] = pg
                    break

    # 4b: Map time points to dates, then to pages
    for r in snaps + merged_snaps:
        tp = str(r.get('时点', ''))
        if tp in tp_page_map:
            continue
        # Try to find a date in the time point text
        m = re.search(r'(\d{4})[-年]\s*(\d{1,2})[-月]', tp)
        if m:
            year, month = int(m.group(1)), int(m.group(2))
            # Find closest subscription date
            best_page = None
            for dt, pg in date_page_map.items():
                dm = re.search(r'(\d{4})-(\d{2})', dt)
                if dm:
                    dy, dm_val = int(dm.group(1)), int(dm.group(2))
                    if dy == year and abs(dm_val - month) <= 3:
                        best_page = pg
                        break
            if best_page:
                tp_page_map[tp] = best_page

    # 4c: Map time points that share shareholder names to known page time points
    # (If t0 and t1 have the same shareholders, they're likely on same/adjacent pages)
    for r in snaps + merged_snaps:
        tp = str(r.get('时点', ''))
        name = r.get('股东名称', '')
        if tp in tp_page_map or not name:
            continue
        # Find another record with same shareholder name that has a known page
        for r2 in snaps + merged_snaps:
            tp2 = str(r2.get('时点', ''))
            if tp2 in tp_page_map and r2.get('股东名称') == name:
                tp_page_map[tp] = tp_page_map[tp2]
                break

    print(f'  Built {len(tp_page_map)} time-point → page mappings')
    print(f'  Subscription date → page: {date_page_map}')

    # === 5. Fill pages in equity snapshots ===
    filled_snaps = 0
    for r in snaps:
        tp = str(r.get('时点', ''))
        cur = r.get('PDF页码')
        if cur and cur != 0 and cur != '':
            continue
        if tp in tp_page_map:
            r['PDF页码'] = tp_page_map[tp]
            filled_snaps += 1

    if filled_snaps > 0 and snap_path.exists():
        snap_path.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in snaps), encoding='utf-8')
    print(f'  Individual snaps: filled {filled_snaps} pages')

    # === 6. Fill pages in merged gold snaps ===
    filled_merged = 0
    for r in merged_snaps:
        tp = str(r.get('时点', ''))
        cur = r.get('PDF页码')
        if cur and cur != 0 and cur != '':
            continue
        if tp in tp_page_map:
            r['PDF页码'] = tp_page_map[tp]
            filled_merged += 1

    if filled_merged > 0 and merged_path.exists():
        # Rewrite merged gold with updated snaps
        all_recs = [json.loads(l) for l in merged_path.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
        for i, r in enumerate(all_recs):
            if r.get('record_type') == 'equity_snapshot':
                for mr in merged_snaps:
                    if (mr.get('股东名称') == r.get('股东名称') and
                        str(mr.get('时点')) == str(r.get('时点')) and
                        mr.get('持股比例') == r.get('持股比例')):
                        if mr.get('PDF页码') and mr['PDF页码'] != 0:
                            all_recs[i]['PDF页码'] = mr['PDF页码']
        merged_path.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in all_recs), encoding='utf-8')
    print(f'  Merged gold snaps: filled {filled_merged} pages')

    # === 7. Also fill subscription pages if missing ===
    filled_subs = 0
    for r in subs:
        cur = r.get('PDF页码')
        if cur and cur != 0 and cur != '':
            continue
        dt = r.get('增资日期', '')
        if dt in date_page_map:
            r['PDF页码'] = date_page_map[dt]
            filled_subs += 1

    if filled_subs > 0 and sub_path.exists():
        sub_path.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in subs), encoding='utf-8')
    print(f'  Subscriptions: filled {filled_subs} pages')

    total = filled_snaps + filled_merged + filled_subs
    return total


def main():
    total = 0
    for code, company in COMPANIES.items():
        print(f'\n{company} ({code}):')
        try:
            n = fill_one_company(code, company)
            total += n
            print(f'  → Total filled: {n}')
        except Exception as e:
            print(f'  FAIL: {e}')
            import traceback
            traceback.print_exc()

    print(f'\n{"="*50}')
    print(f'Grand total: {total} page numbers filled')

    # Verify
    print(f'\n--- Verification ---')
    for code, company in COMPANIES.items():
        fp = GOLD_DIR / f'{code}_{company}_equity_snapshot_gold.jsonl'
        if fp.exists():
            recs = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
            has = sum(1 for r in recs if r.get('PDF页码') and r['PDF页码'] != 0 and r['PDF页码'] != '')
            print(f'{company}: {has}/{len(recs)} snap records have page numbers')


if __name__ == '__main__':
    main()
