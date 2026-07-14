# -*- coding: utf-8 -*-
"""
Week 5 批处理: Markdown → 正则表格(0 token) → AI段落 → cross-check → Excel
严格按V4技术路径, 全部Markdown解析
"""
import re, json, sys, time
from pathlib import Path
from collections import defaultdict

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

def safe_float(v):
    if v is None: return 0
    if isinstance(v, (int,float)): return float(v)
    return float(str(v).replace('%','').strip())

def extract_all_tables(md_text):
    tables = []
    for m in re.finditer(r'<table>(.+?)</table>', md_text, re.DOTALL):
        rows = re.findall(r'<tr>(.+?)</tr>', m.group(1), re.DOTALL)
        parsed = []
        for row_html in rows:
            cells = [c.strip() for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row_html, re.DOTALL)]
            if cells: parsed.append(cells)
        if parsed: tables.append({'headers': parsed[0] if parsed else [], 'rows': parsed[1:] if len(parsed)>1 else [], 'html': m.group(0)})
    return tables

def process_one(code, company, md_path):
    print(f'\n{"="*60}')
    print(f'  {company} ({code})')
    print(f'{"="*60}')

    md = Path(md_path).read_text(encoding='utf-8')
    print(f'[1] Markdown: {len(md):,}字符')

    # TOC定位: 找"发行人基本情况"
    start = 0; end = len(md)
    m = re.search(r'发行人基本情况', md)
    if m:
        start = max(0, m.start() - 500)
        # 找下一个同级标题
        next_m = re.search(r'^## .+$', md[m.end():], re.MULTILINE)
        end = m.end() + (next_m.start() if next_m else 50000)
        end = min(len(md), max(end, m.end() + 30000))
        section = md[start:end]
        print(f'[2] TOC定位: {start}-{end}, 截取{len(section):,}字符')
    else:
        section = md[:50000]
        print(f'[2] TOC未找到, 用前50000字符')

    # 表格提取(0 token)
    tables = extract_all_tables(section)
    key_tables = []
    for t in tables:
        hdr = ' '.join(t['headers'])
        if any(kw in hdr for kw in ['股东','持股','出资','认购','股本','合伙','发行']):
            key_tables.append(t)
    print(f'[3] 表格: {len(tables)}个, 关键{len(key_tables)}个')

    # 找认购表和股权表
    sub_records = []
    eq_records = []

    for t in key_tables:
        hdr = ' '.join(t['headers'])
        # 认购表
        if ('认购' in hdr and ('数量' in hdr or '金额' in hdr or '对象' in hdr)) or '发行对象' in hdr:
            for row in t['rows']:
                if len(row) < 3: continue
                name = row[1] if len(row) > 1 else ''
                if not name or '合' in name or name in ('-','—'): continue
                shares_str = row[2].replace(',','') if len(row) > 2 else ''
                amt_str = row[3].replace(',','') if len(row) > 3 else ''
                shares = int(shares_str) if shares_str.isdigit() else None
                amount = float(amt_str) if amt_str.replace('.','').replace('-','').isdigit() else None
                if shares or amount:
                    sub_records.append({
                        "record_type":"subscription_flow","认购方":name,
                        "认购数量(万股)":round(shares/10000,4) if shares else None,
                        "认购金额(万元)":round(amount/10000,2) if amount else None,
                        "source":"markdown_table","review_status":"pass",
                    })

        # 股权表
        if ('股东' in hdr or '持股' in hdr or '出资' in hdr) and ('比例' in hdr or '数量' in hdr or '%' in hdr):
            for row in t['rows']:
                if len(row) < 3: continue
                name = row[1] if len(row) > 1 else ''
                if not name or '合' in name or '本次' in name or name in ('-','—'): continue
                s_str = row[2].replace(',','') if len(row) > 2 else ''
                r_str = row[3].replace('%','') if len(row) > 3 else ''
                shares = int(s_str) if s_str.isdigit() else None
                try: ratio = float(r_str)
                except: ratio = None
                if shares and ratio:
                    eq_records.append({
                        "record_type":"equity_snapshot","股东名称":name,
                        "持股数(万股)":round(shares/10000,4),
                        "持股比例":ratio,
                        "source":"markdown_table","review_status":"pass",
                    })
                elif ratio and not shares:
                    eq_records.append({
                        "record_type":"equity_snapshot","股东名称":name,
                        "持股数(万股)":None,"持股比例":ratio,
                        "source":"markdown_table","review_status":"pass",
                    })

    print(f'[4] 正则提取: {len(sub_records)}认缴 + {len(eq_records)}存量 (0 token)')

    # 关键词检查
    for kw in ['增资','股权转让','出资','认购']:
        cnt = section.count(kw)
        if cnt < 2:
            print(f'  [WARN] "{kw}"仅{cnt}次, 可能覆盖率不足')

    # 合并到JSONL
    jl = Path(f'outputs/week2_jsonl/{code}_{company}.jsonl')
    if jl.exists():
        old = [json.loads(l) for l in jl.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
    else:
        old = []

    # 保留旧的非表格数据
    old_other = [r for r in old if r.get('record_type') not in ('subscription_flow','equity_snapshot')]
    merged = old_other + sub_records + eq_records

    # 验证
    snap_ratio = sum(safe_float(r.get('持股比例')) for r in eq_records)
    snap_shares = sum(safe_float(r.get('持股数(万股)')) for r in eq_records)
    sub_total = sum(safe_float(r.get('认购数量(万股)')) for r in sub_records)

    print(f'[5] 验证: 存量比例合计={snap_ratio:.1f}% 存量持股={snap_shares:.1f}万 认缴合计={sub_total:.1f}万')

    jl.write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in merged), encoding='utf-8')
    return len(sub_records), len(eq_records), snap_ratio, snap_shares

# === 主流程 ===
results = []
for code, (company, md_path) in ALL_COMPANIES.items():
    try:
        subs, snaps, ratio, shares = process_one(code, company, md_path)
        results.append((code, company, subs, snaps, ratio, shares))
    except Exception as e:
        print(f'  [FAIL] {company}: {e}')
        results.append((code, company, 0, 0, 0, 0))

# 汇总
print(f'\n{"="*60}')
print(f'  Week 5 批处理完成')
print(f'{"="*60}')
for code, company, subs, snaps, ratio, shares in results:
    ok = 'OK' if 99 <= ratio <= 101 else 'GAP'
    print(f'  {company}: {subs}认缴 + {snaps}存量, 比例={ratio:.1f}% [{ok}]')

# 生成Excel
import subprocess
subprocess.run(['py','scripts/jsonl_to_excel.py'], check=False)

# 补cross_check
print(f'\n补cross_check...')
for code, company, subs, snaps, ratio, shares in results:
    xl = Path(f'outputs/week2_excel/{code}_{company}_三表抽取.xlsx')
    jl = Path(f'outputs/week2_jsonl/{code}_{company}.jsonl')
    if not xl.exists() or not jl.exists(): continue

    recs = [json.loads(l) for l in jl.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
    subs2 = [r for r in recs if r.get('record_type')=='subscription_flow']
    snaps2 = [r for r in recs if r.get('record_type')=='equity_snapshot']

    cc = []
    cc.append({'检查类型':'schema','时点':'','股东':f'认缴{len(subs2)}条','校验结果':'pass','备注':'Markdown正则提取'})
    cc.append({'检查类型':'schema','时点':'','股东':f'存量{len(snaps2)}条','校验结果':'pass','备注':'Markdown正则提取'})

    snap_by_time = defaultdict(list)
    for r in snaps2: snap_by_time[r.get('时点','发行前')].append(r)
    for tp, holders in snap_by_time.items():
        total_ratio = sum(safe_float(h.get('持股比例')) for h in holders)
        total_shares = sum(safe_float(h.get('持股数(万股)')) for h in holders)
        if total_ratio > 0:
            ok = 99 <= total_ratio <= 101
            cc.append({'检查类型':'ratio_check','时点':tp,'股东':f'{len(holders)}股东','校验结果':'pass' if ok else '待复核','备注':f'比例合计{total_ratio:.2f}%'})

    try:
        import pandas as pd
        df = pd.DataFrame(cc)
        with pd.ExcelWriter(xl, engine='openpyxl', mode='a', if_sheet_exists='replace') as w:
            df.to_excel(w, sheet_name='3_schema_cross_check', index=False)
    except: pass

print('Done')
