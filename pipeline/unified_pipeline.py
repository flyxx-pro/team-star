# -*- coding: utf-8 -*-
"""
Week 6 统一流水线: Markdown → rowspan/colspan展开 → 正则表格(0 token) →
逐事件Cross-check(区间匹配) → 逐股东核对 → Gold/Auto/Final分离
"""
import re, json, sys
from pathlib import Path
from collections import defaultdict

# 导入 table_parser
sys.path.insert(0, str(Path(__file__).parent))
from table_parser import parse_all_tables


ALL_COMPANIES = {
    '001282': ('三联锻造', 'MinerU_Output/MinerU_markdown_001282_三联锻造_招股说明书_2076218706897772550.md'),
    '603418': ('友升股份', 'MinerU_Output/MinerU_markdown_603418_友升股份_招股说明书_2076218706897772552.md'),
    '301581': ('黄山谷捷', 'MinerU_Output/MinerU_markdown_301581_黄山谷捷_招股说明书_2076218706897772551.md'),
    '301563': ('云汉芯城', 'MinerU_Output/MinerU_markdown_301563_云汉芯城_招股说明书_2076218706897772544.md'),
    '688758': ('赛分科技', 'MinerU_Output/MinerU_markdown_688758_赛分科技_招股说明书_2076218706897772546.md'),
    '688775': ('影石创新', 'MinerU_Output/MinerU_markdown_688775_影石创新_招股说明书_2076218706897772547.md'),
    '920100': ('三协电机', 'MinerU_Output/MinerU_markdown_920100_三协电机_招股说明书_2076218706897772548.md'),
    '920116': ('星图测控', 'MinerU_Output/MinerU_markdown_920116_星图测控_招股说明书_2076218706897772549.md'),
}


def sf(v):
    """Safe float conversion"""
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace('%', '').replace(',', '').strip()
    try:
        return float(s)
    except ValueError:
        return 0


def find_relevant_section(md_text):
    """Locate the relevant section containing capital history"""
    # Primary: look for "股本和股东变化" or "股本演变" which contains all capital events
    primary_patterns = [
        r'股本.*?股东.*?变化',
        r'公司设立.*?股本',
        r'历史沿革',
        r'历次增资',
        r'发行人基本情况',
    ]

    start, end = 0, len(md_text)
    method = 'full_text'

    for pat in primary_patterns:
        m = re.search(pat, md_text)
        if m:
            start = max(0, m.start() - 1000)
            # Extend to cover all subsections: find the next ## or # header that isn't a subsection
            # Try to capture until "业务" or "财务" section or end
            stop_patterns = [
                r'^##\s+(?:业务|财务|募集|公司治理|关联交易|财务|风险)',
                r'^#\s+第[六七八九十]',
            ]
            end_search_start = m.end()
            end = len(md_text)
            for sp in stop_patterns:
                stop_m = re.search(sp, md_text[end_search_start:], re.MULTILINE)
                if stop_m and end_search_start + stop_m.start() < end:
                    end = end_search_start + stop_m.start()
            # Ensure at least 30000 chars
            if end - start < 30000:
                end = min(len(md_text), start + 60000)
            method = f'section: {m.group(0)[:50]}'
            break

    return start, end, method


def extract_subscription_records(tables, section_text):
    """Extract subscription flow records from tables"""
    records = []
    for t in tables:
        hdr = ' '.join(t['headers'])
        # Match tables about 增资/认购/定向发行
        if not any(kw in hdr for kw in ['认购', '增资', '发行对象', '定向发行']):
            continue
        if not any(kw in hdr for kw in ['数量', '金额', '股份', '出资', '价格']):
            continue

        # Find context: date of this capital increase
        pos = t['position']
        context = section_text[max(0, pos - 2000):pos]
        date_match = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月', context)
        date_str = f"{date_match.group(1)}-{int(date_match.group(2)):02d}" if date_match else None

        # Find price from context or header
        price = None
        for row in t['rows']:
            if len(row) < 3:
                continue
            name = row[1] if len(row) > 1 else ''
            if not name or '合' in name or '本次' in name or name in ('-', '—'):
                continue

            # Find column indices
            col_map = {}
            for j, h in enumerate(t['headers']):
                hc = h.replace(' ', '')
                if '认购数量' in hc or '发行数量' in hc or '股份' in hc or '股数' in hc:
                    if j not in col_map:
                        col_map[j] = 'shares'
                if '认购金额' in hc or '增资金额' in hc or '投资金额' in hc or '金额' in hc:
                    if j not in col_map:
                        col_map[j] = 'amount'
                if '价格' in hc or '单价' in hc:
                    if j not in col_map:
                        col_map[j] = 'price'
                if '认缴出资额' in hc or '注册资本' in hc:
                    if j not in col_map:
                        col_map[j] = 'capital'
                if '出资方式' in hc:
                    col_map[j] = 'method'

            shares_val = None
            amount_val = None
            price_val = None
            capital_val = None

            # Use expected column positions for known table structures
            if len(t['headers']) >= 5:
                # Common pattern: 序号|名称|认购/股份数量|价格|金额|方式
                if len(row) >= 5:
                    if 'shares' in col_map or any('股份' in h or '数量' in h or '股数' in h for h in t['headers'][:4]):
                        shares_col = next((j for j, v in col_map.items() if v == 'shares'), 2)
                        if len(row) > shares_col:
                            shares_val = row[shares_col].replace(',', '').strip() if row[shares_col] else None
                    if 'amount' in col_map or any('金额' in h for h in t['headers'][:4]):
                        amt_col = next((j for j, v in col_map.items() if v == 'amount'), 4)
                        if len(row) > amt_col:
                            amount_val = row[amt_col].replace(',', '').strip() if row[amt_col] else None
                    if 'price' in col_map:
                        price_col = next((j for j, v in col_map.items() if v == 'price'), 3)
                        if len(row) > price_col:
                            price_val = row[price_col].replace(',', '').strip() if row[price_col] else None
                    if 'capital' in col_map:
                        cap_col = next((j for j, v in col_map.items() if v == 'capital'), 2)
                        if len(row) > cap_col:
                            capital_val = row[cap_col].replace(',', '').strip() if row[cap_col] else None

            # Convert units
            try:
                if shares_val:
                    sv = float(shares_val)
                    shares_val = round(sv / 10000, 4)  # Convert to 万股
            except ValueError:
                shares_val = None
            try:
                if amount_val:
                    av = float(amount_val)
                    amount_val = round(av / 10000, 2) if av > 100000 else av  # Convert to 万元
            except ValueError:
                amount_val = None
            try:
                if price_val:
                    price_val = float(price_val)
            except ValueError:
                price_val = None
            try:
                if capital_val:
                    capital_val = float(capital_val)
            except ValueError:
                capital_val = None

            if shares_val or amount_val or capital_val:
                rec = {
                    "record_type": "subscription_flow",
                    "增资日期": date_str,
                    "认购方": name,
                    "source": "markdown_table_auto",
                    "review_status": "auto",
                }
                if shares_val:
                    rec["认购数量(万股)"] = shares_val
                if amount_val:
                    rec["认购金额(万元)"] = amount_val
                if price_val:
                    rec["认购价格(元/股)"] = price_val
                if capital_val:
                    rec["出资额(万元注册资本)"] = capital_val
                if t.get('had_rowspan_colspan'):
                    rec["rowspan_processed"] = True

                # Add PDF page reference
                page_match = re.search(r'(\d+)', context[-500:])
                if page_match:
                    rec["PDF页码"] = int(page_match.group(1))

                records.append(rec)

    return records


def extract_equity_snapshots(tables, section_text):
    """Extract equity snapshot records from tables"""
    records = []
    for t in tables:
        hdr = ' '.join(t['headers'])
        # Match tables about equity structure
        if not any(kw in hdr for kw in ['股东', '持股', '出资', '股权结构']):
            continue
        if not any(kw in hdr for kw in ['比例', '数量', '%', '股']):
            continue

        # Determine if this is a post-event snapshot with context
        pos = t['position']
        context = section_text[max(0, pos - 2000):pos]
        # Try to determine time point from context
        time_point = None
        tm = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月.*?(?:股权结构|完成后|变更后)', context)
        if tm:
            try:
                time_point = f"{tm.group(1)}-{int(tm.group(2)):02d}"
            except (ValueError, IndexError):
                pass

        # Check if this looks like an equity snapshot (ratio + quantity)
        ratio_col = None
        shares_col = None
        capital_col = None
        for j, h in enumerate(t['headers']):
            hc = h.replace(' ', '')
            if '持股比例' in hc or '出资比例' in hc or '比例' in hc:
                ratio_col = j
            if '持股数量' in hc or '股份数量' in hc or '持股数' in hc or '股数' in hc:
                shares_col = j
            if '认缴出资额' in hc or '实缴出资额' in hc or '出资额' in hc:
                capital_col = j

        if ratio_col is None and shares_col is None and capital_col is None:
            continue

        for row in t['rows']:
            if len(row) < 3:
                continue
            name = row[1] if len(row) > 1 else ''
            if not name or '合' in name or '本次' in name or name in ('-', '—', '/'):
                continue

            ratio_val = None
            shares_val = None
            capital_val = None

            if ratio_col and ratio_col < len(row):
                r_str = row[ratio_col].replace('%', '').replace(',', '').strip()
                try:
                    ratio_val = float(r_str)
                except ValueError:
                    pass

            if shares_col and shares_col < len(row):
                s_str = row[shares_col].replace(',', '').strip()
                try:
                    sv = float(s_str)
                    shares_val = round(sv / 10000, 4) if sv > 10000 else sv
                except ValueError:
                    pass

            if capital_col and capital_col < len(row):
                c_str = row[capital_col].replace(',', '').strip()
                try:
                    capital_val = float(c_str)
                except ValueError:
                    pass

            if ratio_val or shares_val or capital_val:
                rec = {
                    "record_type": "equity_snapshot",
                    "时点": time_point,
                    "股东名称": name,
                    "source": "markdown_table_auto",
                    "review_status": "auto",
                }
                if ratio_val is not None:
                    rec["持股比例"] = ratio_val
                if shares_val is not None:
                    rec["持股数(万股)"] = shares_val
                if capital_val is not None:
                    rec["出资额(万元注册资本)"] = capital_val
                if t.get('had_rowspan_colspan'):
                    rec["rowspan_processed"] = True

                records.append(rec)

    return records


def cross_check_per_interval(subs, snaps):
    """
    Fixed cross-check: match subscription events to specific time intervals.
    Each pair of consecutive snapshots only includes subscription events
    that occurred between those two time points.
    """
    cc_results = []

    if not snaps or not subs:
        cc_results.append({
            '检查类型': 'cross_check_skip',
            '备注': f'快照{len(snaps)}个, 认缴{len(subs)}条 - 数据不足,跳过cross_check',
            '校验结果': 'skip',
        })
        return cc_results

    # Group snapshots by time point
    snap_by_time = defaultdict(list)
    for r in snaps:
        tp = r.get('时点', 'unknown')
        snap_by_time[tp].append(r)

    # Sort time points (filter out None)
    time_points = sorted([tp for tp in snap_by_time.keys() if tp is not None])

    # Group subscriptions by date
    sub_by_date = defaultdict(list)
    for r in subs:
        dt = r.get('增资日期', 'unknown')
        sub_by_date[dt].append(r)

    # Schema check
    cc_results.append({
        '检查类型': 'schema',
        'PDF页码': '',
        '股东/认购方': f'认缴{len(subs)}条,存量{len(snaps)}条',
        '校验结果': 'pass',
        '差额(万股)': '',
        '备注': 'markdown_table_auto + rowspan展开',
    })

    # Ratio check per time point
    for tp in time_points:
        holders = snap_by_time[tp]
        total_ratio = sum(sf(h.get('持股比例')) for h in holders)
        total_shares = sum(sf(h.get('持股数(万股)')) for h in holders)
        total_capital = sum(sf(h.get('出资额(万元注册资本)')) for h in holders)
        if total_ratio > 0:
            ok = 99.0 <= total_ratio <= 101.0
            detail = f'比例={total_ratio:.2f}%'
            if total_shares > 0:
                detail += f',持股={total_shares:.2f}万'
            if total_capital > 0:
                detail += f',出资={total_capital:.2f}万'
            cc_results.append({
                '检查类型': 'ratio_check',
                'PDF页码': '',
                '股东/认购方': f'{tp}: {len(holders)}股东',
                '校验结果': 'pass' if ok else '待复核',
                '差额(万股)': '',
                '备注': detail,
            })

    # Per-interval cross-check: 前后快照只连接该区间内的认购事件
    for i in range(len(time_points) - 1):
        prev_tp, curr_tp = time_points[i], time_points[i + 1]
        prev_holders = snap_by_time[prev_tp]
        curr_holders = snap_by_time[curr_tp]

        # Total equity in previous snapshot
        prev_total = sum(sf(h.get('持股数(万股)') or h.get('出资额(万元注册资本)')) for h in prev_holders)
        curr_total = sum(sf(h.get('持股数(万股)') or h.get('出资额(万元注册资本)')) for h in curr_holders)

        # Only match subscriptions dated between prev_tp and curr_tp
        interval_subs = []
        for dt, sub_list in sub_by_date.items():
            if dt == 'unknown':
                continue
            # Check if date falls in [prev_tp, curr_tp]
            if prev_tp <= dt <= curr_tp:
                interval_subs.extend(sub_list)

        sub_total = sum(sf(r.get('认购数量(万股)')) for r in interval_subs)
        expected = prev_total + sub_total
        diff = round(curr_total - expected, 4)

        if prev_total > 0 and curr_total > 0:
            cc_results.append({
                '检查类型': 'cross_check_interval',
                'PDF页码': '',
                '股东/认购方': f'总股本({prev_tp}->{curr_tp})',
                '上一时点(万股)': round(prev_total, 4),
                '本次变化(万股)': round(sub_total, 4),
                '预期值(万股)': round(expected, 4),
                'PDF值(万股)': round(curr_total, 4),
                '差额(万股)': diff,
                '校验结果': 'pass' if abs(diff) < max(1, prev_total * 0.02) else '待复核',
                '备注': f'区间内{len(interval_subs)}笔认购',
            })

    # Per-shareholder cross-check
    for i in range(len(time_points) - 1):
        prev_tp, curr_tp = time_points[i], time_points[i + 1]
        prev_map = {h.get('股东名称', ''): h for h in snap_by_time[prev_tp] if h.get('股东名称')}
        curr_map = {h.get('股东名称', ''): h for h in snap_by_time[curr_tp] if h.get('股东名称')}

        all_names = sorted(set(list(prev_map.keys()) + list(curr_map.keys())))

        # Get subscriptions in this interval
        interval_subs = []
        for dt, sub_list in sub_by_date.items():
            if dt == 'unknown': continue
            if prev_tp <= dt <= curr_tp:
                interval_subs.extend(sub_list)

        for nm in all_names[:30]:  # Cap at 30 shareholders per interval
            pv = sf(prev_map.get(nm, {}).get('持股数(万股)') or prev_map.get(nm, {}).get('出资额(万元注册资本)'))
            cv = sf(curr_map.get(nm, {}).get('持股数(万股)') or curr_map.get(nm, {}).get('出资额(万元注册资本)'))
            if pv == 0 and cv == 0:
                continue

            # Subscription by this shareholder in this interval
            sv = sum(sf(r.get('认购数量(万股)')) for r in interval_subs if r.get('认购方', '') == nm)
            expected_sh = pv + sv
            diff_sh = round(cv - expected_sh, 4)

            if abs(diff_sh) > 0.01 or sv > 0:
                cc_results.append({
                    '检查类型': 'cross_check_shareholder',
                    'PDF页码': '',
                    '股东/认购方': nm,
                    '上一时点(万股)': round(pv, 4),
                    '本次变化(万股)': round(sv, 4),
                    '预期值(万股)': round(expected_sh, 4),
                    'PDF值(万股)': round(cv, 4),
                    '差额(万股)': diff_sh,
                    '校验结果': 'pass' if abs(diff_sh) < max(1, pv * 0.02) else '待复核',
                    '备注': f'{prev_tp}->{curr_tp}',
                })

    return cc_results


def load_gold(gold_dir='manual_gold'):
    """Load gold standard records for comparison"""
    gold_dir = Path(gold_dir)
    gold_data = {}
    for fp in sorted(gold_dir.glob('*_gold.jsonl')):
        code = fp.stem.split('_')[0]
        records = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
        gold_data[code] = records
    return gold_data


def auto_vs_gold(auto_records, gold_records, record_type='subscription_flow'):
    """
    Compare Auto extraction results against Gold standard.
    Computes TP, FP, FN at record level.
    """
    auto_subs = [r for r in auto_records if r.get('record_type') == record_type]
    gold_subs = [r for r in gold_records if r.get('record_type') == record_type]

    # Key matching: (认购方/股东名称, 增资日期/时点)
    def make_key(r):
        name = r.get('认购方') or r.get('股东名称', '')
        date = r.get('增资日期') or r.get('时点', '')
        return (name, str(date))

    auto_keys = {make_key(r): r for r in auto_subs}
    gold_keys = {make_key(r): r for r in gold_subs}

    tp = len(set(auto_keys.keys()) & set(gold_keys.keys()))
    fp = len(set(auto_keys.keys()) - set(gold_keys.keys()))
    fn = len(set(gold_keys.keys()) - set(auto_keys.keys()))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        'record_type': record_type,
        'auto_count': len(auto_subs),
        'gold_count': len(gold_subs),
        'TP': tp,
        'FP': fp,
        'FN': fn,
        'precision': round(precision, 4),
        'recall': round(recall, 4),
        'f1': round(f1, 4),
        'fp_items': [k for k in set(auto_keys.keys()) - set(gold_keys.keys())],
        'fn_items': [k for k in set(gold_keys.keys()) - set(auto_keys.keys())],
    }


def process_company(code, company, md_path):
    """Process one company: extract records + cross-check"""
    print(f'\n{"=" * 60}')
    print(f'  {company} ({code})')
    print(f'{"=" * 60}')

    md = Path(md_path).read_text(encoding='utf-8')
    print(f'[1] Markdown: {len(md):,} chars')

    # Locate relevant section
    start, end, method = find_relevant_section(md)
    section = md[start:end]
    print(f'[2] Section: {method} -> {len(section):,} chars')

    # Parse all tables with rowspan/colspan expansion
    tables = parse_all_tables(section, expand_spans=True)
    span_count = sum(1 for t in tables if t.get('had_rowspan_colspan'))
    key_tables = [t for t in tables if any(
        kw in ' '.join(t['headers']) for kw in
        ['股东', '持股', '出资', '认购', '股本', '发行', '转让']
    )]
    print(f'[3] Tables: {len(tables)} total, {span_count} with rowspan/colspan, {len(key_tables)} key')

    # Extract records
    subs = extract_subscription_records(tables, section)
    snaps = extract_equity_snapshots(tables, section)
    print(f'[4] Extracted: {len(subs)} subs + {len(snaps)} snaps (0 token)')

    # Cross-check
    cc = cross_check_per_interval(subs, snaps)
    pass_count = sum(1 for c in cc if c.get('校验结果') == 'pass')
    pending_count = sum(1 for c in cc if c.get('校验结果') == '待复核')
    print(f'[5] Cross-check: {len(cc)} checks ({pass_count} pass, {pending_count} pending)')

    return subs, snaps, cc, tables


def main():
    all_results = {}
    all_cc = {}

    for code, (company, md_path) in ALL_COMPANIES.items():
        try:
            subs, snaps, cc, tables = process_company(code, company, md_path)
            all_results[code] = {
                'company': company,
                'subs': subs,
                'snaps': snaps,
                'cc': cc,
            }
            all_cc[code] = cc
        except Exception as e:
            print(f'  [FAIL] {company}: {e}')
            import traceback
            traceback.print_exc()

    # === Generate outputs ===
    out_auto = Path('auto_output')
    out_final = Path('final')
    out_val = Path('validation')
    out_auto.mkdir(exist_ok=True)
    out_final.mkdir(exist_ok=True)
    out_val.mkdir(exist_ok=True)

    # Load gold for comparison
    gold_data = load_gold()

    # Summary stats
    summary = []
    for code, data in all_results.items():
        company = data['company']
        subs = data['subs']
        snaps = data['snaps']
        cc = data['cc']

        # Save Auto JSONL
        auto_records = subs + snaps
        auto_path = out_auto / f'{code}_{company}_auto.jsonl'
        auto_path.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in auto_records), encoding='utf-8')

        # Auto-vs-Gold comparison
        gold_recs = gold_data.get(code, [])
        if gold_recs:
            sub_cmp = auto_vs_gold(auto_records, gold_recs, 'subscription_flow')
            snap_cmp = auto_vs_gold(auto_records, gold_recs, 'equity_snapshot')
        else:
            sub_cmp = snap_cmp = None

        # Save validation results
        val_path = out_val / f'{code}_{company}_validation.json'
        val_data = {
            'code': code,
            'company': company,
            'cross_check': cc,
            'auto_vs_gold_subscription': sub_cmp,
            'auto_vs_gold_equity': snap_cmp,
        }
        val_path.write_text(json.dumps(val_data, ensure_ascii=False, indent=2), encoding='utf-8')

        # Counts
        sub_count = len(subs)
        snap_count = len(snaps)
        ratio_checks = [c for c in cc if c.get('检查类型') == 'ratio_check']
        ratios_ok = all(c.get('校验结果') == 'pass' for c in ratio_checks) if ratio_checks else None

        summary.append({
            'code': code,
            'company': company,
            'subs': sub_count,
            'snaps': snap_count,
            'ratio_ok': ratios_ok,
            'cc_total': len(cc),
            'cc_pass': sum(1 for c in cc if c.get('校验结果') == 'pass'),
            'cc_pending': sum(1 for c in cc if c.get('校验结果') == '待复核'),
            'sub_precision': sub_cmp['precision'] if sub_cmp else None,
            'sub_recall': sub_cmp['recall'] if sub_cmp else None,
            'snap_precision': snap_cmp['precision'] if snap_cmp else None,
            'snap_recall': snap_cmp['recall'] if snap_cmp else None,
        })

    # Print summary
    print(f'\n{"=" * 80}')
    print(f'  Week 6 Pipeline Summary')
    print(f'{"=" * 80}')
    print(f'{"Code":<8} {"Company":<8} {"Subs":>5} {"Snaps":>5} {"Ratio":>6} {"CC":>4} {"CC OK":>5} {"Sub P":>6} {"Sub R":>6} {"Snap P":>6} {"Snap R":>6}')
    print(f'{"-" * 80}')
    total_subs = total_snaps = 0
    for s in summary:
        total_subs += s['subs']
        total_snaps += s['snaps']
        ratio_str = 'OK' if s['ratio_ok'] else ('FAIL' if s['ratio_ok'] is False else 'N/A')
        sp = f'{s["sub_precision"]:.2f}' if s['sub_precision'] is not None else 'N/A'
        sr = f'{s["sub_recall"]:.2f}' if s['sub_recall'] is not None else 'N/A'
        ep = f'{s["snap_precision"]:.2f}' if s['snap_precision'] is not None else 'N/A'
        er = f'{s["snap_recall"]:.2f}' if s['snap_recall'] is not None else 'N/A'
        print(f'{s["code"]:<8} {s["company"]:<8} {s["subs"]:>5} {s["snaps"]:>5} {ratio_str:>6} {s["cc_total"]:>4} {s["cc_pass"]:>5} {sp:>6} {sr:>6} {ep:>6} {er:>6}')
    print(f'{"-" * 80}')
    print(f'{"TOTAL":<17} {total_subs:>5} {total_snaps:>5}')

    # Save summary
    import pandas as pd
    df = pd.DataFrame(summary)
    df.to_csv(out_val / 'pipeline_summary.csv', index=False, encoding='utf-8-sig')
    print(f'\nSummary saved to validation/pipeline_summary.csv')

    return all_results, summary


if __name__ == '__main__':
    main()
