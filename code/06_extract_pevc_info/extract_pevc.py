# -*- coding: utf-8 -*-
"""
Step 6: 使用 Deepseek API 从候选文本中提取 PE/VC 投资信息
==========================================================
输入：outputs/week1_candidate_texts/*_candidate.txt
输出：outputs/week1_sample_json/{code}_{company}_pevc.json
日志：logs/extraction_log.csv
"""
import json
import os
import re
import csv
import time
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / '.env')

# 配置
CANDIDATE_DIR = Path('outputs/week1_candidate_texts')
OUTPUT_DIR = Path('outputs/week1_sample_json')
LOG_DIR = Path('logs')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')

# VC 数据关键词（用于智能截取时的密度评分）
VC_KEYWORDS = [
    '增资', '股权转让', '出资', '认购', '入股',
    '投资者', '外部投资者', '财务投资者',
    '风险投资', '私募股权', '创投', '创业投资',
    '产业基金', '股权投资基金', '持股比例',
    '投前估值', '投后估值', '每股价格',
    '股东名称', '持股数量', '出资额',
]

# 任务书 JSON Schema 对应的 System Prompt
SYSTEM_PROMPT = """你是一位专业的金融数据分析师，专门从中国A股招股说明书中提取上市前PE/VC投资信息。

请仔细阅读提供的招股书候选文本，按照以下JSON格式提取融资事件。注意：
1. 招股书没有披露的信息，不得编造，对应字段填null或"未披露"
2. 融资轮次如招股书未明确写A/B/C轮，disclosed_round填"未披露"，不要自行推断
3. 投资方原始名称必须保留招股书原文写法
4. 每条融资事件必须有evidence_text（原文证据片段）
5. 尽量记录source_page（页码）
6. 投资总额、每股价格、投前估值、投后估值必须分字段存储

返回JSON格式（严格按照此结构）：
{
  "company": {
    "company_name": "公司全称",
    "stock_code": "股票代码",
    "exchange": "SSE/SZSE/BSE",
    "board": "主板/创业板/科创板/北交所",
    "listing_date": "",
    "prospectus_title": "",
    "prospectus_date": ""
  },
  "financing_events": [
    {
      "event_order": 1,
      "event_date": "YYYY-MM-DD",
      "date_type": "协议签署日/工商变更日/股东会决议日/未说明",
      "event_type": "增资/股权转让/增资及股权转让/其他",
      "disclosed_round": "未披露",
      "inferred_round": "",
      "round_inference_basis": "",
      "total_investment_amount": null,
      "currency": "CNY",
      "share_price": null,
      "pre_money_valuation": null,
      "post_money_valuation": null,
      "valuation_basis": "",
      "investors": [
        {
          "investor_original_name": "原文披露名称",
          "investor_short_name": "简称",
          "investor_type": "VC/PE/产业资本/自然人/员工持股平台/政府基金/其他/无法判断",
          "is_pevc": "yes/no/uncertain",
          "investment_amount": null,
          "shares_acquired": null,
          "shareholding_ratio_after_event": null,
          "exit_status_before_ipo": "未退出/部分退出/全部退出/无法判断"
        }
      ],
      "source_section": "",
      "source_page": "",
      "evidence_text": "",
      "confidence": "high/medium/low"
    }
  ],
  "processing": {
    "download_status": "success",
    "parse_status": "success",
    "locate_status": "success",
    "extract_status": "success/partial/fail",
    "review_status": "unchecked"
  }
}"""


def call_deepseek(system_prompt: str, user_prompt: str,
                  temperature: float = 0.1,
                  max_tokens: int = 8192) -> Optional[dict]:
    """调用 Deepseek API 提取结构化 JSON"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    resp = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=180,
    )
    resp.raise_for_status()
    data = resp.json()
    response_text = data["choices"][0]["message"]["content"]

    # 提取 JSON（可能在 markdown 代码块中）
    json_str = response_text
    for marker in ["```json", "```"]:
        if marker in json_str:
            parts = json_str.split(marker)
            if len(parts) >= 2:
                json_str = parts[1]
                if "```" in json_str:
                    json_str = json_str.split("```")[0]
                break

    try:
        return json.loads(json_str.strip())
    except json.JSONDecodeError:
        # 尝试提取花括号内容
        m = re.search(r'\{[\s\S]*\}', response_text)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        print(f"    [WARN] JSON解析失败，原始回复前200字符: {response_text[:200]}")
        return None


def simple_validate(pevc_data: dict) -> list:
    """简单校验 JSON 结构，返回问题列表"""
    issues = []

    if not pevc_data:
        return ["空数据"]

    # 检查顶层结构
    if 'financing_events' not in pevc_data:
        issues.append("缺少 financing_events 字段")
        return issues

    events = pevc_data.get('financing_events', [])
    if not events:
        issues.append("financing_events 为空数组")
        return issues

    # 检查每个事件
    for i, event in enumerate(events):
        prefix = f"事件{i+1}"

        if not event.get('evidence_text'):
            issues.append(f"{prefix}: 缺少 evidence_text")

        if not event.get('event_type'):
            issues.append(f"{prefix}: 缺少 event_type")

        investors = event.get('investors', [])
        if not investors:
            issues.append(f"{prefix}: investors 为空")

        for j, inv in enumerate(investors):
            ip = f"{prefix}.投资者{j+1}"
            if not inv.get('investor_original_name'):
                issues.append(f"{ip}: 缺少 investor_original_name")
            if not inv.get('is_pevc'):
                issues.append(f"{ip}: 缺少 is_pevc 标记")

        # 持股比例合理性检查
        total_ratio = sum(
            inv.get('shareholding_ratio_after_event', 0) or 0
            for inv in investors
        )
        if total_ratio > 100:
            issues.append(f"{prefix}: 持股比例合计 {total_ratio}% 超过100%")

    return issues


def main():
    if not DEEPSEEK_API_KEY:
        print("[ERROR] 未设置 DEEPSEEK_API_KEY，请检查 .env 文件")
        return

    candidate_files = sorted(Path(CANDIDATE_DIR).glob('*_candidate.txt'))
    log_entries = []

    print("=" * 60)
    print("  Step 6: Deepseek AI PE/VC 信息提取")
    print(f"  模型: {DEEPSEEK_MODEL}")
    print(f"  候选文本数: {len(candidate_files)}")
    print("=" * 60)

    for i, txt_path in enumerate(candidate_files, 1):
        parts = txt_path.stem.replace('_candidate', '').split('_')
        code = parts[0]
        company = parts[1]

        print(f"\n{'─'*50}")
        print(f"  [{i}/{len(candidate_files)}] {company} ({code})")

        # 1. 读取候选文本
        with open(txt_path, 'r', encoding='utf-8') as f:
            candidate_text = f.read()

        # 智能截断：按页面关键词密度评分，保留高分页
        max_input = 28000
        if len(candidate_text) > max_input:
            # 按页面分割
            pages = candidate_text.split('[第')
            scored_pages = []
            for p in pages:
                if not p.strip():
                    continue
                # 评分：含越多 VC 关键词得分越高
                score = sum(1 for kw in VC_KEYWORDS if kw in p)
                # 前5页（封面日期）强制保留
                page_num_match = re.search(r'(\d+)页', p)
                page_num = int(page_num_match.group(1)) if page_num_match else 999
                if page_num <= 5:
                    score += 100
                scored_pages.append((score, page_num, p))

            # 按分数降序排列
            scored_pages.sort(key=lambda x: x[0], reverse=True)

            # 取高分页直到接近 max_input
            selected = []
            total_len = 0
            for score, pnum, content in scored_pages:
                if total_len + len(content) > max_input and len(selected) > 10:
                    break
                selected.append((pnum, content))
                total_len += len(content)

            # 按页码恢复顺序
            selected.sort(key=lambda x: x[0])
            candidate_text = '\n'.join(f'[第{pnum}页]{content}' for pnum, content in selected)
            print(f"  智能截取: {len(scored_pages)}页 → {len(selected)}页, {total_len:,}字符")

        print(f"  候选文本: {len(candidate_text):,} 字符")

        # 2. 构造 User Prompt
        user_prompt = f"""公司股票代码：{code}
公司简称：{company}

以下是从招股说明书 MinerU 解析结果中截取的候选文本（包含"发行人基本情况"、历史沿革、股本变化、历次增资/股权转让、股东情况等章节）：

---
{candidate_text}
---

请从中提取上市前 PE/VC 投资信息，严格按照指定的 JSON Schema 返回。"""

        # 3. 调用 AI
        print(f"  正在调用 Deepseek API...")
        result = call_deepseek(SYSTEM_PROMPT, user_prompt)

        if not result:
            print(f"  [FAIL] AI 提取失败")
            log_entries.append({
                'company_name': company, 'stock_code': code,
                'candidate_text_path': str(txt_path),
                'model_name': DEEPSEEK_MODEL,
                'json_path': '',
                'status': 'fail',
                'error_message': 'API返回无法解析',
            })
            continue

        # 4. 补充 company 信息（如果 AI 没填）
        if 'company' not in result:
            result['company'] = {}
        result['company']['stock_code'] = result['company'].get('stock_code', '') or code
        result['company']['company_name'] = result['company'].get('company_name', '') or company

        # 补充 processing 信息
        if 'processing' not in result:
            result['processing'] = {}
        result['processing']['locate_status'] = 'success'

        # 5. 校验
        issues = simple_validate(result)
        events_count = len(result.get('financing_events', []))
        investors_count = sum(
            len(e.get('investors', []))
            for e in result.get('financing_events', [])
        )

        if issues:
            print(f"  [WARN] 校验发现 {len(issues)} 个问题:")
            for issue in issues[:5]:
                print(f"    - {issue}")
            status = 'partial'
        else:
            status = 'success'

        # 6. 保存 JSON
        json_name = f"{code}_{company}_pevc.json"
        json_path = OUTPUT_DIR / json_name
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  [OK] {events_count} 个融资事件, {investors_count} 个投资者 → {json_name}")

        log_entries.append({
            'company_name': company,
            'stock_code': code,
            'candidate_text_path': str(txt_path),
            'model_name': DEEPSEEK_MODEL,
            'json_path': str(json_path),
            'events_count': events_count,
            'investors_count': investors_count,
            'validation_issues': len(issues),
            'status': status,
            'error_message': '; '.join(issues[:3]) if issues else '',
        })

        # API 限流
        if i < len(candidate_files):
            time.sleep(2)

    # 保存日志
    if log_entries:
        log_path = LOG_DIR / 'extraction_log.csv'
        with open(log_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=log_entries[0].keys())
            writer.writeheader()
            writer.writerows(log_entries)
        print(f"\n日志已保存: {log_path}")

    # 汇总
    success = sum(1 for l in log_entries if l['status'] in ('success', 'partial'))
    fail = sum(1 for l in log_entries if l['status'] == 'fail')
    total_events = sum(l.get('events_count', 0) for l in log_entries)
    total_investors = sum(l.get('investors_count', 0) for l in log_entries)
    print(f"\n{'='*60}")
    print(f"  Step 6 完成: {success} 成功, {fail} 失败")
    print(f"  共提取 {total_events} 个融资事件, {total_investors} 个投资者")
    print(f"  JSON 输出: {OUTPUT_DIR}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
