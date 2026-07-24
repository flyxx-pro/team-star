# -*- coding: utf-8 -*-
"""生成 PostgreSQL SQL 导入文件"""
import json, re
from pathlib import Path

PREFIX = 'lyx'
GOLD_DIR = Path('manual_gold')
OUT = Path('pipeline/lyx_import.sql')

COMPANIES = {
    '001282':'三联锻造','603418':'友升股份','301581':'黄山谷捷',
    '301563':'云汉芯城','688758':'赛分科技','688775':'影石创新',
    '920100':'三协电机','920116':'星图测控',
}

def T(v):
    """TEXT value escape"""
    if v is None: return 'NULL'
    if isinstance(v,(int,float)): return str(int(v))
    return "'" + str(v).replace("'","''") + "'"

def N(v):
    """NUMERIC value escape - extracts number or returns NULL"""
    if v is None: return 'NULL'
    if isinstance(v,(int,float)):
        return str(int(v)) if int(v)!=0 else 'NULL'
    s = str(v).strip().replace('%','').replace(',','')
    if s in ('','-','—','未披露','不适用','无','N/A'): return 'NULL'
    m = re.search(r'(\d+\.?\d*)', s)
    if m:
        try: float(m.group(1)); return m.group(1)
        except: pass
    return 'NULL'

def P(v):
    """Page number: extract integer"""
    if v is None: return 'NULL'
    if isinstance(v,(int,float)): return str(int(v))
    m = re.search(r'(\d+)', str(v))
    return m.group(1) if m else 'NULL'

lines = []
lines.append("-- 刘宇轩 Week6 PostgreSQL 导入")
lines.append("-- 运行此文件即可建表+导入全部数据")
lines.append("")

for tbl,cols in [
    (f"{PREFIX}_subscription_flow", "id SERIAL PRIMARY KEY, company_code VARCHAR(10), company_name VARCHAR(50), pdf_page INTEGER, subscription_date VARCHAR(20), subscriber VARCHAR(100), shares_wan NUMERIC(15,4), amount_wan NUMERIC(15,2), price_yuan NUMERIC(15,4), capital_wan NUMERIC(15,4), evidence TEXT, source VARCHAR(50), review_status VARCHAR(20), investor_type VARCHAR(50), is_pevc VARCHAR(10)"),
    (f"{PREFIX}_equity_snapshot", "id SERIAL PRIMARY KEY, company_code VARCHAR(10), company_name VARCHAR(50), pdf_page INTEGER, time_point VARCHAR(200), equity_scope VARCHAR(200), total_shares_wan NUMERIC(15,4), total_capital_wan NUMERIC(15,4), shareholder_name VARCHAR(100), shares_wan NUMERIC(15,4), capital_wan NUMERIC(15,4), share_ratio NUMERIC(10,4), evidence TEXT, source VARCHAR(50), review_status VARCHAR(20)"),
    (f"{PREFIX}_share_transfer_flow", "id SERIAL PRIMARY KEY, company_code VARCHAR(10), company_name VARCHAR(50), pdf_page INTEGER, transfer_date VARCHAR(20), transferor VARCHAR(100), transferee VARCHAR(100), shares_wan NUMERIC(15,4), amount_wan NUMERIC(15,2), price_yuan NUMERIC(15,4), evidence TEXT, source VARCHAR(50), review_status VARCHAR(20)"),
]:
    lines.append(f"DROP TABLE IF EXISTS {tbl};")
    lines.append(f"CREATE TABLE {tbl} ({cols});")
    lines.append("")

total = 0
for code, co in COMPANIES.items():
    lines.append(f"-- {co} ({code}) --")

    # 认缴
    fp = GOLD_DIR / f'{code}_{co}_subscription_flow_gold.jsonl'
    if not fp.exists() and code == '688758':
        fp = GOLD_DIR / f'{code}_{co}_subscription_flow_gold_fixed.jsonl'
    if fp.exists():
        for r in [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]:
            v = f"{T(code)},{T(co)},{P(r.get('PDF页码'))},{T(r.get('增资日期'))},{T(r.get('认购方'))},{N(r.get('认购数量(万股)'))},{N(r.get('认购金额(万元)'))},{N(r.get('认购价格(元/股)'))},{N(r.get('出资额(万元注册资本)'))},{T(r.get('原文证据'))},{T(r.get('source'))},{T(r.get('review_status'))},{T(r.get('investor_type'))},{T(r.get('is_pevc'))}"
            lines.append(f"INSERT INTO {PREFIX}_subscription_flow (company_code,company_name,pdf_page,subscription_date,subscriber,shares_wan,amount_wan,price_yuan,capital_wan,evidence,source,review_status,investor_type,is_pevc) VALUES ({v});")
            total += 1

    # 存量
    fp = GOLD_DIR / f'{code}_{co}_equity_snapshot_gold.jsonl'
    if fp.exists():
        for r in [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]:
            v = f"{T(code)},{T(co)},{P(r.get('PDF页码'))},{T(r.get('时点'))},{T(r.get('股权结构口径'))},{N(r.get('总股本(万股)'))},{N(r.get('总出资额(万元注册资本)'))},{T(r.get('股东名称'))},{N(r.get('持股数(万股)'))},{N(r.get('出资额(万元注册资本)'))},{N(r.get('持股比例'))},{T(r.get('原文证据'))},{T(r.get('source'))},{T(r.get('review_status'))}"
            lines.append(f"INSERT INTO {PREFIX}_equity_snapshot (company_code,company_name,pdf_page,time_point,equity_scope,total_shares_wan,total_capital_wan,shareholder_name,shares_wan,capital_wan,share_ratio,evidence,source,review_status) VALUES ({v});")
            total += 1

    # 转让
    fp = GOLD_DIR / f'{code}_{co}_share_transfer_flow_gold.jsonl'
    if fp.exists():
        for r in [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]:
            v = f"{T(code)},{T(co)},{P(r.get('PDF页码'))},{T(r.get('转让日期'))},{T(r.get('转让方'))},{T(r.get('受让方'))},{N(r.get('转让数量(万股)'))},{N(r.get('转让金额(万元)'))},{N(r.get('转让价格(元/股)'))},{T(r.get('原文证据'))},{T(r.get('source'))},{T(r.get('review_status'))}"
            lines.append(f"INSERT INTO {PREFIX}_share_transfer_flow (company_code,company_name,pdf_page,transfer_date,transferor,transferee,shares_wan,amount_wan,price_yuan,evidence,source,review_status) VALUES ({v});")
            total += 1

lines.append("")
lines.append("-- 验证")
lines.append(f"SELECT 'subscription_flow', COUNT(*) FROM {PREFIX}_subscription_flow;")
lines.append(f"SELECT 'equity_snapshot', COUNT(*) FROM {PREFIX}_equity_snapshot;")
lines.append(f"SELECT 'share_transfer_flow', COUNT(*) FROM {PREFIX}_share_transfer_flow;")

OUT.write_text('\n'.join(lines), encoding='utf-8')
print(f'OK: {OUT} ({len(lines)}行, {total}条)')
