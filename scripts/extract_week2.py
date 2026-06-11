# -*- coding: utf-8 -*-
"""
Week 2: 认缴流量 + 股权结构存量 JSONL 抽取
==========================================
输入：MinerU_Output/*.json + outputs/week1_candidate_texts/*.txt
输出：outputs/week2_jsonl/{code}_{company}.jsonl
"""
import json, os, re, csv, time, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / '.env')

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')

MINERU_DIR = Path('MinerU_Output')
CANDIDATE_DIR = Path('outputs/week1_candidate_texts')
OUTPUT_DIR = Path('outputs/week2_jsonl')
LOG_DIR = Path('logs')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Week 2 公共样本（更新后）
COMPANIES = [
    ("001282", "三联锻造", "MB001", "主板"),
    ("603418", "友升股份", "MB002", "主板"),
    ("301581", "黄山谷捷", "GEM001", "创业板"),
    ("301563", "云汉芯城", "GEM002", "创业板"),
    ("688758", "赛分科技", "STAR001", "科创板"),
    ("688775", "影石创新", "STAR002", "科创板"),
    ("920100", "三协电机", "BSE001", "北交所"),
    ("920116", "星图测控", "BSE002", "北交所"),
]

import requests

SYSTEM_PROMPT = """你是一位专业的招股说明书数据分析师。请仔细阅读招股书文本，提取两类结构化数据：

## 一、认缴流量（subscription_flow）
回答：谁在什么时候认购了多少股、多少钱、什么价格。
从"历史沿革""股本形成及变化""历次增资及股权转让"等章节中找出每一次增资/认购事件。

每条记录必须包含：
- PDF页码：从文本中的[第X页]标记提取
- 增资日期：YYYY-MM-DD格式
- 认购方：股东/投资者名称（原文写法）
- 认购数量(万股)：PDF直接披露的数值，未披露则填null
- 认购金额(万元)：PDF直接披露的数值，未披露则填null
- 认购价格(元/股)：PDF直接披露的数值，未披露则填null
- 原文证据：招股书原文片段

重要：
1. 只抽增资/认购事件，不抽股权转让（转让人不是发行人）
2. 金额和股数只填PDF明确披露的数值，不要推算
3. 单位已在列名中写明（万股、万元），数值不要带单位
4. 每一笔认购方单独一行（同一增资事件多个认购方要分行）
5. 如果同一股东多轮认购，每次都要单独记录

## 二、股权结构存量（equity_snapshot）
回答：每个关键时点的股东结构。必须有t0（报告期初或最早可识别的股权结构），以及每次增资后的股权结构（t1, t2...）。

每条记录必须包含：
- PDF页码
- 时点：t0/t1/t2...（并在股权结构口径中说明对应日期）
- 股权结构口径：如"报告期初公司股权结构""2020年9月增资后股权结构"
- 总股本(万股)：该时点总股本
- 总出资额(万元注册资本)：如果PDF披露出资额而非股本
- 股东名称
- 持股数(万股)/出资额(万元注册资本)/持股比例(%)：PDF直接披露的数值
- 原文证据

重要：
1. 必须包含t0（报告期初）
2. 每个时点每个股东一行
3. 如果PDF只披露出资额不披露持股数，持股数列留空，反之亦然
4. 持股比例如果有就填，没有就空
5. 同一时点的总股本对应该时点所有股东（可填多行相同总股本）

返回纯JSON数组，每条记录一个JSON对象，包含record_type字段：
```json
[
  {"record_type": "subscription_flow", "PDF页码": 44, "增资日期": "2020-09-27", ...},
  {"record_type": "equity_snapshot", "PDF页码": 43, "时点": "t0", ...}
]
```"""


def call_deepseek(prompt_text: str) -> list:
    """调用Deepseek提取JSON数组"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text},
        ],
        "temperature": 0.1,
        "max_tokens": 16384,
    }
    resp = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers=headers, json=payload, timeout=300,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"]

    # 提取JSON数组
    json_str = text
    for marker in ["```json", "```"]:
        if marker in text:
            parts = text.split(marker)
            if len(parts) >= 2:
                json_str = parts[1]
                if "```" in json_str:
                    json_str = json_str.split("```")[0]
                break

    try:
        result = json.loads(json_str.strip())
        if isinstance(result, list):
            return result
        elif isinstance(result, dict) and "records" in result:
            return result["records"]
        return []
    except json.JSONDecodeError:
        # 尝试找JSON数组
        m = re.search(r'\[[\s\S]*\]', text)
        if m:
            try:
                return json.loads(m.group())
            except:
                pass
        print(f"  [WARN] JSON解析失败: {text[:300]}")
        return []


def extract_one(code, company, board):
    """对一家公司做抽取"""
    # 读候选文本
    cand_path = CANDIDATE_DIR / f"{code}_{company}_candidate.txt"
    if not cand_path.exists():
        # 尝试从MinerU直接读
        m_paths = list(MINERU_DIR.glob(f"MinerU_json_{code}_*.json"))
        if not m_paths:
            print(f"  [SKIP] 无候选文本也无MinerU JSON")
            return []
        with open(m_paths[0], encoding='utf-8') as f:
            mineru = json.load(f)
        # 简单提取文本
        texts = []
        for pi, page in enumerate(mineru.get('pdf_info', [])):
            page_text = []
            for b in page.get('preproc_blocks', []):
                for l in b.get('lines', []):
                    for s in l.get('spans', []):
                        if s.get('content', '').strip():
                            page_text.append(s['content'])
            if page_text:
                texts.append(f"[第{pi+1}页]\n" + '\n'.join(page_text))
        full_text = '\n'.join(texts)
    else:
        with open(cand_path, encoding='utf-8') as f:
            full_text = f.read()

    # 截取前35000字符（确保覆盖多轮融资）
    if len(full_text) > 35000:
        full_text = full_text[:35000]

    user_prompt = f"""公司股票代码：{code}
公司简称：{company}
上市板块：{board}

以下是招股说明书章节文本（含页码标记）：

---
{full_text}
---

请提取认缴流量和股权结构存量数据，以JSON数组格式返回。"""

    print(f"  调用Deepseek ({len(full_text):,}字符)...")
    records = call_deepseek(user_prompt)

    # 分类统计
    subs = [r for r in records if r.get('record_type') == 'subscription_flow']
    snaps = [r for r in records if r.get('record_type') == 'equity_snapshot']
    print(f"  结果: {len(subs)}条认缴流量, {len(snaps)}条股权存量")

    return records


def main():
    if not DEEPSEEK_API_KEY:
        print("[ERROR] 未设置 DEEPSEEK_API_KEY")
        return

    log_entries = []

    for code, company, sid, board in COMPANIES:
        print(f"\n{'='*50}")
        print(f"  [{sid}] {company} ({code}) - {board}")
        print(f"{'='*50}")

        records = extract_one(code, company, board)

        if not records:
            print(f"  [FAIL] 未提取到数据")
            log_entries.append({
                'company': company, 'code': code, 'board': board,
                'subscription_count': 0, 'equity_count': 0,
                'total_records': 0, 'status': 'fail',
            })
            continue

        # 保存JSONL
        out_path = OUTPUT_DIR / f"{code}_{company}.jsonl"
        with open(out_path, 'w', encoding='utf-8') as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')

        subs = sum(1 for r in records if r.get('record_type') == 'subscription_flow')
        snaps = sum(1 for r in records if r.get('record_type') == 'equity_snapshot')
        print(f"  已保存: {out_path}")

        log_entries.append({
            'company': company, 'code': code, 'board': board,
            'subscription_count': subs, 'equity_count': snaps,
            'total_records': len(records),
            'status': 'success',
        })

        time.sleep(2)

    # 保存日志
    if log_entries:
        lp = LOG_DIR / 'week2_extraction_log.csv'
        with open(lp, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=log_entries[0].keys())
            w.writeheader(); w.writerows(log_entries)
        print(f"\n日志: {lp}")

    total_subs = sum(l['subscription_count'] for l in log_entries)
    total_snaps = sum(l['equity_count'] for l in log_entries)
    print(f"\n{'='*50}")
    print(f"  完成: {len(log_entries)}家公司")
    print(f"  认缴流量: {total_subs}条 | 股权存量: {total_snaps}条")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
