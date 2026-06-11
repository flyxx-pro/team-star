# -*- coding: utf-8 -*-
"""JSONL → Excel 转换器（按示范格式）"""
import json, pandas as pd
from pathlib import Path

JSONL_DIR = Path('outputs/week2_jsonl')
EXCEL_DIR = Path('outputs/week2_excel')
EXCEL_DIR.mkdir(exist_ok=True)

SUB_COLS = ['PDF页码', '增资日期', '认购方', '认购数量(万股)',
            '认购金额(万元)', '认购价格(元/股)', '原文证据']
SNAP_COLS = ['PDF页码', '时点', '股权结构口径', '总股本(万股)',
             '总出资额(万元注册资本)', '股东名称', '持股数(万股)',
             '出资额(万元注册资本)', '持股比例', '原文证据']


def convert_one(jsonl_path):
    records = []
    with open(jsonl_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    subs = [r for r in records if r.get('record_type') == 'subscription_flow']
    snaps = [r for r in records if r.get('record_type') == 'equity_snapshot']

    # 构建DataFrame
    sub_rows = []
    for r in subs:
        row = {col: r.get(col, None) for col in SUB_COLS}
        sub_rows.append(row)

    snap_rows = []
    for r in snaps:
        row = {col: r.get(col, None) for col in SNAP_COLS}
        snap_rows.append(row)

    df_sub = pd.DataFrame(sub_rows, columns=SUB_COLS) if sub_rows else pd.DataFrame(columns=SUB_COLS)
    df_snap = pd.DataFrame(snap_rows, columns=SNAP_COLS) if snap_rows else pd.DataFrame(columns=SNAP_COLS)

    # 写入Excel
    code = jsonl_path.stem.split('_')[0]
    company = jsonl_path.stem.split('_')[1]
    out_path = EXCEL_DIR / f"{code}_{company}_三表抽取.xlsx"

    with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
        df_sub.to_excel(writer, sheet_name='1_认缴流量', index=False)
        df_snap.to_excel(writer, sheet_name='2_股权结构存量', index=False)

    print(f"  {out_path.name}: {len(sub_rows)}认缴 + {len(snap_rows)}存量")
    return out_path


def main():
    jsonl_files = sorted(JSONL_DIR.glob('*.jsonl'))
    for fp in jsonl_files:
        convert_one(fp)
    print(f"\n完成 {len(jsonl_files)} 家 → {EXCEL_DIR}")


if __name__ == '__main__':
    main()
