# -*- coding: utf-8 -*-
"""验证陈雨昂检查报告中的关键指控"""
import json, openpyxl
from pathlib import Path

ROOT = Path("C:/Users/Carol/Desktop/招股书统计作业_刘宇轩")

def check_yunhan():
    """云汉芯城：陈说深创投等4人33.332万误记为50万，郦韩英48.4495万误记为20万"""
    print("=" * 60)
    print("云汉芯城 - 验证持股数")
    print("=" * 60)

    # Read Gold
    fp = ROOT / "manual_gold/301563_云汉芯城_gold.jsonl"
    if fp.exists():
        recs = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]

    # Check specific shareholders
    check = {
        '深创投': None, '镇江红土': None, '昆山红土': None, '富海深湾': None, '郦韩英': None
    }
    for r in recs:
        name = r.get('股东名称', '')
        for key in check:
            if key in str(name):
                check[key] = r

    for key, r in check.items():
        if r:
            print(f"  {key}: 持股={r.get('持股数(万股)', r.get('持股数(万股)'))}万, "
                  f"出资={r.get('出资额(万元注册资本)')}, 比例={r.get('持股比例')}, "
                  f"页码={r.get('PDF页码')}, 时点={r.get('时点', '')[:30]}")
        else:
            print(f"  {key}: 未找到")

    # Read final Excel
    fp_excel = ROOT / "final/301563_云汉芯城_三表抽取.xlsx"
    if fp_excel.exists():
        wb = openpyxl.load_workbook(fp_excel, data_only=True)
        ws = wb['2_股权结构存量']
        for r in range(2, ws.max_row+1):
            name = str(ws.cell(r, 8).value or '')
            for key in check:
                if key in name:
                    shares = ws.cell(r, 9).value
                    ratio = ws.cell(r, 11).value
                    time_pt = str(ws.cell(r, 4).value or '')[:40]
                    print(f'  [Excel] {key}: 持股={shares}, 比例={ratio}, 时点={time_pt}')

def check_huangshan():
    """黄山谷捷 - 认购金额"""
    print("\n" + "=" * 60)
    print("黄山谷捷 - 认购金额检查")
    print("=" * 60)
    fp = ROOT / "manual_gold/301581_黄山谷捷_subscription_flow_gold.jsonl"
    if fp.exists():
        recs = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
        for r in recs:
            print(f"  {r.get('认购方')}: 认购数量={r.get('认购数量(万股)')}, "
                  f"认购金额={r.get('认购金额(万元)')}, 价格={r.get('认购价格(元/股)')}")

def check_sanlian():
    """三联锻造 - 数据源差异"""
    print("\n" + "=" * 60)
    print("三联锻造 - Gold认缴")
    print("=" * 60)
    fp = ROOT / "manual_gold/001282_三联锻造_subscription_flow_gold.jsonl"
    if fp.exists():
        recs = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
        for i, r in enumerate(recs):
            source = r.get('source', '')
            print(f"  {i+1}. {r.get('增资日期')} | {r.get('认购方')} | "
                  f"出资={r.get('出资额(万元注册资本)')} | source={source}")
        print(f"\n  共{len(recs)}条")

def check_xingtu():
    """星图测控 - 缺失设立期"""
    print("\n" + "=" * 60)
    print("星图测控 - 认缴")
    print("=" * 60)
    fp = ROOT / "manual_gold/920116_星图测控_subscription_flow_gold.jsonl"
    if fp.exists():
        recs = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
        for r in recs:
            print(f"  {r.get('增资日期')} | {r.get('认购方')}")
        print(f"  共{len(recs)}条")

check_yunhan()
check_huangshan()
check_sanlian()
check_xingtu()
