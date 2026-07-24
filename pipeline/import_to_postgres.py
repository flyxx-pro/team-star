# -*- coding: utf-8 -*-
"""
将 8 家公司 Gold 数据导入 PostgreSQL 数据库
表名: lyx_subscription_flow / lyx_equity_snapshot / lyx_share_transfer_flow
"""
import json, sys
from pathlib import Path
import psycopg2
from psycopg2 import sql

# ============================================================
# 数据库连接
# ============================================================
DB_CONFIG = {
    'host': '123.45.67.89',    # 或 localhost（校园网/VPN环境）
    'port': 5433,
    'database': 'student',
    'user': 'student2026',
    'password': 'student2026',
}

PREFIX = 'lyx'  # 刘宇轩首字母

COMPANIES = {
    '001282': '三联锻造', '603418': '友升股份', '301581': '黄山谷捷',
    '301563': '云汉芯城', '688758': '赛分科技', '688775': '影石创新',
    '920100': '三协电机', '920116': '星图测控',
}

GOLD_DIR = Path('manual_gold')


# ============================================================
# 建表 SQL
# ============================================================
CREATE_TABLES = {
    'subscription_flow': f"""
        CREATE TABLE IF NOT EXISTS {PREFIX}_subscription_flow (
            id SERIAL PRIMARY KEY,
            company_code VARCHAR(10) NOT NULL,
            company_name VARCHAR(50) NOT NULL,
            pdf_page INTEGER,
            subscription_date VARCHAR(20),
            subscriber VARCHAR(100),
            shares_wan NUMERIC(15,4),
            amount_wan NUMERIC(15,2),
            price_yuan NUMERIC(15,4),
            capital_wan NUMERIC(15,4),
            evidence TEXT,
            source VARCHAR(50),
            review_status VARCHAR(20),
            investor_type VARCHAR(50),
            is_pevc VARCHAR(10),
            created_at TIMESTAMP DEFAULT NOW()
        );
    """,
    'equity_snapshot': f"""
        CREATE TABLE IF NOT EXISTS {PREFIX}_equity_snapshot (
            id SERIAL PRIMARY KEY,
            company_code VARCHAR(10) NOT NULL,
            company_name VARCHAR(50) NOT NULL,
            pdf_page INTEGER,
            time_point VARCHAR(200),
            equity_scope VARCHAR(200),
            total_shares_wan NUMERIC(15,4),
            total_capital_wan NUMERIC(15,4),
            shareholder_name VARCHAR(100),
            shares_wan NUMERIC(15,4),
            capital_wan NUMERIC(15,4),
            share_ratio NUMERIC(10,4),
            evidence TEXT,
            source VARCHAR(50),
            review_status VARCHAR(20),
            created_at TIMESTAMP DEFAULT NOW()
        );
    """,
    'share_transfer_flow': f"""
        CREATE TABLE IF NOT EXISTS {PREFIX}_share_transfer_flow (
            id SERIAL PRIMARY KEY,
            company_code VARCHAR(10) NOT NULL,
            company_name VARCHAR(50) NOT NULL,
            pdf_page INTEGER,
            transfer_date VARCHAR(20),
            transferor VARCHAR(100),
            transferee VARCHAR(100),
            shares_wan NUMERIC(15,4),
            amount_wan NUMERIC(15,2),
            price_yuan NUMERIC(15,4),
            evidence TEXT,
            source VARCHAR(50),
            review_status VARCHAR(20),
            created_at TIMESTAMP DEFAULT NOW()
        );
    """,
}


# ============================================================
# 导入函数
# ============================================================
def import_company(conn, code, company):
    """Import one company's Gold data"""
    cur = conn.cursor()
    total = 0

    # --- 认缴流量 ---
    fp = GOLD_DIR / f'{code}_{company}_subscription_flow_gold.jsonl'
    if not fp.exists() and code == '688758':
        fp = GOLD_DIR / f'{code}_{company}_subscription_flow_gold_fixed.jsonl'
    if fp.exists():
        records = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
        for r in records:
            cur.execute(f"""
                INSERT INTO {PREFIX}_subscription_flow
                (company_code, company_name, pdf_page, subscription_date, subscriber,
                 shares_wan, amount_wan, price_yuan, capital_wan, evidence, source, review_status,
                 investor_type, is_pevc)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                code, company,
                r.get('PDF页码'), r.get('增资日期'), r.get('认购方'),
                r.get('认购数量(万股)'), r.get('认购金额(万元)'), r.get('认购价格(元/股)'),
                r.get('出资额(万元注册资本)'), r.get('原文证据'), r.get('source'),
                r.get('review_status'), r.get('investor_type'), r.get('is_pevc'),
            ))
        total += len(records)
        print(f'  {PREFIX}_subscription_flow: {len(records)} rows')

    # --- 股权存量 ---
    fp = GOLD_DIR / f'{code}_{company}_equity_snapshot_gold.jsonl'
    if fp.exists():
        records = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
        for r in records:
            cur.execute(f"""
                INSERT INTO {PREFIX}_equity_snapshot
                (company_code, company_name, pdf_page, time_point, equity_scope,
                 total_shares_wan, total_capital_wan, shareholder_name,
                 shares_wan, capital_wan, share_ratio, evidence, source, review_status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                code, company,
                r.get('PDF页码'), r.get('时点'), r.get('股权结构口径'),
                r.get('总股本(万股)'), r.get('总出资额(万元注册资本)'), r.get('股东名称'),
                r.get('持股数(万股)'), r.get('出资额(万元注册资本)'), r.get('持股比例'),
                r.get('原文证据'), r.get('source'), r.get('review_status'),
            ))
        total += len(records)
        print(f'  {PREFIX}_equity_snapshot: {len(records)} rows')

    # --- 股权转让 ---
    fp = GOLD_DIR / f'{code}_{company}_share_transfer_flow_gold.jsonl'
    if fp.exists():
        records = [json.loads(l) for l in fp.read_text(encoding='utf-8').strip().split('\n') if l.strip()]
        for r in records:
            cur.execute(f"""
                INSERT INTO {PREFIX}_share_transfer_flow
                (company_code, company_name, pdf_page, transfer_date, transferor, transferee,
                 shares_wan, amount_wan, price_yuan, evidence, source, review_status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                code, company,
                r.get('PDF页码'), r.get('转让日期'), r.get('转让方'), r.get('受让方'),
                r.get('转让数量(万股)'), r.get('转让金额(万元)'), r.get('转让价格(元/股)'),
                r.get('原文证据'), r.get('source'), r.get('review_status'),
            ))
        total += len(records)
        print(f'  {PREFIX}_share_transfer_flow: {len(records)} rows')

    conn.commit()
    cur.close()
    return total


def main():
    # 连接数据库
    print('连接数据库...')
    try:
        conn = psycopg2.connect(**DB_CONFIG, connect_timeout=10)
        print('连接成功!')
    except Exception as e:
        print(f'连接失败: {e}')
        print('\n请确认: 1) 已连校园网/VPN  2) 主机IP正确')
        print(f'当前配置: host={DB_CONFIG["host"]}, port={DB_CONFIG["port"]}')
        sys.exit(1)

    # 建表
    cur = conn.cursor()
    for table_name, ddl in CREATE_TABLES.items():
        cur.execute(ddl)
        print(f'创建表: {PREFIX}_{table_name}')
    conn.commit()
    cur.close()

    # 导入数据
    total = 0
    for code, company in COMPANIES.items():
        print(f'\n{company} ({code}):')
        try:
            n = import_company(conn, code, company)
            total += n
        except Exception as e:
            print(f'  导入失败: {e}')
            conn.rollback()

    print(f'\n{"="*50}')
    print(f'导入完成! 共 {total} 条记录')
    print(f'表: {PREFIX}_subscription_flow / {PREFIX}_equity_snapshot / {PREFIX}_share_transfer_flow')

    # 验证
    cur = conn.cursor()
    for tbl in ['subscription_flow', 'equity_snapshot', 'share_transfer_flow']:
        cur.execute(f'SELECT COUNT(*) FROM {PREFIX}_{tbl}')
        cnt = cur.fetchone()[0]
        print(f'  {PREFIX}_{tbl}: {cnt} rows')
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
