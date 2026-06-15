# -*- coding: utf-8 -*-
"""Week 3 全流程脚本——一键运行"""
import sys, json, csv, re, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv('.env')
import requests
import os

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')

# === 1. 处理三联锻造 MinerU JSON ===
print("=" * 60)
print("  Week 3: 完整流程")
print("=" * 60)

# 找三联锻造的JSON（用最新的）
import glob
sl_files = sorted(Path('MinerU_Output').glob('*001282*'))
if sl_files:
    sl_file = sl_files[0]  # 用第一份（04:04版，有关键词）而非第二份（04:09版，无关内容）
    print(f"\n[Step 1] 三联锻造 MinerU: {sl_file.name}")
    with open(sl_file, encoding='utf-8') as f:
        sl_data = json.load(f)
    sl_pages = len(sl_data.get('pdf_info', []))
    print(f"  解析页数: {sl_pages}")

    # 提取文本
    texts = []
    for pi, page in enumerate(sl_data.get('pdf_info', [])):
        pt = []
        for b in page.get('preproc_blocks', []):
            for l in b.get('lines', []):
                for s in l.get('spans', []):
                    if s.get('content', '').strip():
                        pt.append(s['content'])
        if pt:
            texts.append(f"[第{pi+1}页]\n" + '\n'.join(pt))
    sl_text = '\n'.join(texts)

    # 检查关键词覆盖
    for kw in ['增资', '股权转让', '股东', '持股', '出资', '注册资本', '历史沿革', '股本']:
        cnt = sl_text.count(kw)
        print(f"  关键词'{kw}': {cnt}次")
    sl_text = sl_text[:35000]  # 截取前35K

    # 保存候选文本
    Path('outputs/week3_candidates').mkdir(parents=True, exist_ok=True)
    with open('outputs/week3_candidates/001282_三联锻造_candidate.txt', 'w', encoding='utf-8') as f:
        f.write(sl_text)
    print(f"  候选文本: {len(sl_text):,} 字符")

    # AI 提取
    from scripts.extract_week2 import call_deepseek, SYSTEM_PROMPT as SP
    user_prompt = f"公司股票代码：001282\n公司简称：三联锻造\n上市板块：主板\n---\n{sl_text}\n---\n请提取认缴流量和股权结构存量数据。"
    print("  调用Deepseek...")
    records = call_deepseek(user_prompt)
    subs = sum(1 for r in records if r.get('record_type')=='subscription_flow')
    snaps = sum(1 for r in records if r.get('record_type')=='equity_snapshot')
    print(f"  结果: {subs}认缴 + {snaps}存量")

    Path('outputs/week2_jsonl').mkdir(parents=True, exist_ok=True)
    with open('outputs/week2_jsonl/001282_三联锻造.jsonl', 'w', encoding='utf-8') as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print("  已保存 JSONL")
else:
    print("[WARN] 未找到三联锻造 MinerU JSON")
    records = []

# === 2. 重新校验全部8家 ===
print(f"\n[Step 2] 重新校验全部公司")
from scripts.validate_jsonl import validate_jsonl

jsonl_dir = Path('outputs/week2_jsonl')
all_results = []
for fp in sorted(jsonl_dir.glob('*.jsonl')):
    r = validate_jsonl(fp)
    all_results.append(r)
    code = fp.stem.split('_')[0]
    company = fp.stem.split('_')[1] if len(fp.stem.split('_')) > 1 else code
    status = 'PASS' if not r['json_errors'] and not r['schema_errors'] else 'FAIL'
    print(f"  {code} {company}: {r['subscription_flow_count']}认缴+{r['equity_snapshot_count']}存量, t0={'有' if r['has_t0'] else '无'}, {status}")

# === 3. 生成带数字的cross-check ===
print(f"\n[Step 3] 生成带数字的Cross-check")
cross_rows = []
for fp in sorted(jsonl_dir.glob('*.jsonl')):
    code = fp.stem.split('_')[0]
    company = fp.stem.split('_')[1] if len(fp.stem.split('_')) > 1 else code

    records = []
    with open(fp, encoding='utf-8') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    subs = [r for r in records if r.get('record_type')=='subscription_flow']
    snaps = [r for r in records if r.get('record_type')=='equity_snapshot']

    # 按日期分组认缴流量
    from collections import defaultdict
    date_groups = defaultdict(list)
    for r in subs:
        date_groups[r.get('增资日期','?')].append(r)

    for date, group in date_groups.items():
        total_shares = sum((r.get('认购数量(万股)') or 0) for r in group)
        total_amount = sum((r.get('认购金额(万元)') or 0) for r in group)
        has_nulls = any(r.get('认购数量(万股)') is None for r in group)
        cross_rows.append({
            'code': code, 'company': company,
            'check_type': 'cross_check_total',
            'date': date, 'shareholder_count': len(group),
            'sum_shares_wan': None, 'sum_capital_wan': None, 'sum_ratio_pct': None, 'ratio_near_100': None,
            'total_new_shares_wan': round(total_shares, 4) if total_shares > 0 else None,
            'total_new_amount_wan': round(total_amount, 2) if total_amount > 0 else None,
            'has_null_values': has_nulls,
            'note': '有null，需人工补全' if has_nulls else '数值完整',
        })

    # 逐时点股本核对
    snap_by_time = defaultdict(list)
    for r in snaps:
        snap_by_time[r.get('时点','?')].append(r)

    for tp, holders in snap_by_time.items():
        total_shares_tp = sum((h.get('持股数(万股)') or 0) for h in holders)
        total_capital_tp = sum((h.get('出资额(万元注册资本)') or 0) for h in holders)
        total_ratio = sum((h.get('持股比例') or 0) for h in holders)
        ratio_ok = 99 <= total_ratio <= 101 if total_ratio > 0 else None
        cross_rows.append({
            'code': code, 'company': company,
            'check_type': 'snapshot_total',
            'date': tp, 'shareholder_count': len(holders),
            'sum_shares_wan': round(total_shares_tp, 4) if total_shares_tp > 0 else None,
            'sum_capital_wan': round(total_capital_tp, 2) if total_capital_tp > 0 else None,
            'sum_ratio_pct': round(total_ratio, 2) if total_ratio > 0 else None,
            'ratio_near_100': ratio_ok,
            'total_new_shares_wan': None, 'total_new_amount_wan': None, 'has_null_values': None,
            'note': f'比例合计{total_ratio:.1f}%' if total_ratio > 0 else '',
        })

# 保存cross-check
Path('logs').mkdir(exist_ok=True)
ALL_CC_FIELDS = ['code', 'company', 'check_type', 'date', 'shareholder_count',
    'sum_shares_wan', 'sum_capital_wan', 'sum_ratio_pct', 'ratio_near_100',
    'total_new_shares_wan', 'total_new_amount_wan', 'has_null_values', 'note']
with open('logs/week3_cross_check.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=ALL_CC_FIELDS, extrasaction='ignore')
    w.writeheader(); w.writerows(cross_rows)
print(f"  生成 {len(cross_rows)} 条cross-check记录")
print(f"  已保存: logs/week3_cross_check.csv")

# === 4. 生成Excel（含第三表）===
print(f"\n[Step 4] 生成Excel（含第三表cross-check）")
import pandas as pd
from scripts.jsonl_to_excel import SUB_COLS, SNAP_COLS

Path('outputs/week3_excel').mkdir(parents=True, exist_ok=True)
for fp in sorted(jsonl_dir.glob('*.jsonl')):
    code = fp.stem.split('_')[0]
    company = fp.stem.split('_')[1] if len(fp.stem.split('_')) > 1 else code

    records = []
    with open(fp, encoding='utf-8') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    subs = [r for r in records if r.get('record_type')=='subscription_flow']
    snaps = [r for r in records if r.get('record_type')=='equity_snapshot']

    df_sub = pd.DataFrame([{c: r.get(c) for c in SUB_COLS} for r in subs], columns=SUB_COLS) if subs else pd.DataFrame(columns=SUB_COLS)
    df_snap = pd.DataFrame([{c: r.get(c) for c in SNAP_COLS} for r in snaps], columns=SNAP_COLS) if snaps else pd.DataFrame(columns=SNAP_COLS)

    # Cross-check表（该公司相关行）
    cc = [r for r in cross_rows if r['code'] == code]
    df_cc = pd.DataFrame(cc)

    out_path = Path('outputs/week3_excel') / f"{code}_{company}_三表抽取.xlsx"
    with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
        df_sub.to_excel(writer, sheet_name='1_认缴流量', index=False)
        df_snap.to_excel(writer, sheet_name='2_股权结构存量', index=False)
        df_cc.to_excel(writer, sheet_name='3_cross_check', index=False)

print(f"  生成 {len(list(Path('outputs/week3_excel').glob('*.xlsx')))} 个Excel")

print(f"\n{'='*60}")
print(f"  Week 3 流程完成!")
print(f"  三联锻造: {'已处理' if sl_files else '未找到JSON'}")
print(f"  Cross-check: {len(cross_rows)} 条带数字记录")
print(f"  Excel: outputs/week3_excel/")
print(f"{'='*60}")
