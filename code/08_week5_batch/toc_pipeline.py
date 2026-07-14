# -*- coding: utf-8 -*-
"""
Week5 V4: 严格TOC定位→提取发行人基本情况章节→正则表格+AI段落→填充null
"""
import re, json, sys, time
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from dotenv import load_dotenv
load_dotenv('.env')
import requests, os

API_KEY = os.getenv('DEEPSEEK_API_KEY','')
MODEL = os.getenv('DEEPSEEK_MODEL','deepseek-chat')

MD_FILES = {
    '001282': ('三联锻造', 'MinerU_Output/MinerU_markdown_001282_三联锻造_招股说明书_2076218706897772550.md'),
    '603418': ('友升股份', 'MinerU_Output/MinerU_markdown_603418_友升股份_招股说明书_2076218706897772552.md'),
    '301581': ('黄山谷捷', 'MinerU_Output/MinerU_markdown_301581_黄山谷捷_招股说明书_2076218706897772551.md'),
    '301563': ('云汉芯城', 'MinerU_Output/MinerU_markdown_301563_云汉芯城_招股说明书_2076218706897772544.md'),
    '688758': ('赛分科技', 'MinerU_Output/MinerU_markdown_688758_赛分科技_招股说明书_2076218706897772546.md'),
    '688775': ('影石创新', 'MinerU_Output/MinerU_markdown_688775_影石创新_招股说明书_2076218706897772547.md'),
    '920100': ('三协电机', 'MinerU_Output/MinerU_markdown_920100_三协电机_招股说明书_2076218706897772548.md'),
}

SP = """你是专业的招股书数据分析师。请从文本中提取认缴流量和股权结构存量。

## 公司类型判断
- 有限责任公司：出资记录用"出资额(万元注册资本)"，出资额=认购金额，认购数量留空
- 股份有限公司：标准"持股数(万股)"+"认购金额(万元)"格式
- 有过股改的：股改前按有限责任公司、股改后按股份有限公司

## 关键规则
- Temperature=0，只提取PDF明确披露的数值
- 原文只披露总量未披露个体量时填null，不要均分
- 每个认购方/股东单独一行
- 返回JSON数组，record_type区分subscription_flow和equity_snapshot"""

def locate_toc_section(md_text):
    """在Markdown中找到'发行人基本情况'的起止位置"""
    # 找所有##标题
    headers = list(re.finditer(r'^#{1,3}\s+(.+)$', md_text, re.MULTILINE))
    target = None
    for i, m in enumerate(headers):
        title = m.group(1)
        if '发行人基本情况' in title and len(title) < 80:
            target = i
            break

    if target is None:
        # fallback: 搜"发行人基本情况"关键词
        m = re.search(r'发行人基本情况', md_text)
        if m:
            return max(0, m.start() - 1000), min(len(md_text), m.end() + 60000)
        return 0, min(len(md_text), 60000)

    start = headers[target].start()
    # 找下一个同级标题
    end = len(md_text)
    for j in range(target + 1, min(target + 30, len(headers))):
        end = headers[j].start()
        break
    # 确保至少6万字符
    if end - start < 20000:
        end = min(len(md_text), start + 60000)
    return start, end

def extract_tables_from_text(text):
    """从文本中提取HTML表格"""
    tables = []
    for m in re.finditer(r'<table>(.+?)</table>', text, re.DOTALL):
        rows = re.findall(r'<tr>(.+?)</tr>', m.group(1), re.DOTALL)
        parsed = []
        for row_html in rows:
            cells = [c.strip() for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row_html, re.DOTALL)]
            if cells: parsed.append(cells)
        if len(parsed) >= 2:
            tables.append({'headers': parsed[0], 'rows': parsed[1:], 'html': m.group(0)})
    return tables

def call_deepseek(prompt_text):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"model": MODEL, "messages": [
        {"role": "system", "content": SP},
        {"role": "user", "content": prompt_text},
    ], "temperature": 0.0, "max_tokens": 8192}
    resp = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=180)
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"]
    for marker in ["```json","```"]:
        if marker in text:
            p = text.split(marker)
            if len(p) >= 2:
                text = p[1].split("```")[0] if "```" in p[1] else p[1]
                break
    try:
        result = json.loads(text.strip())
        if isinstance(result, list): return result
        if isinstance(result, dict): return result.get("records", [])
    except:
        m = re.search(r'\[[\s\S]*\]', text)
        return json.loads(m.group()) if m else []
    return []

for code, (company, md_path) in MD_FILES.items():
    print(f'\n{"="*60}')
    print(f'  {company} ({code})')
    print(f'{"="*60}')

    md = Path(md_path).read_text(encoding='utf-8')
    print(f'[1] Markdown: {len(md):,}字符')

    # Step 1: TOC定位
    start, end = locate_toc_section(md)
    section = md[start:end]
    print(f'[2] TOC定位: {start}-{end}, 截取{len(section):,}字符')

    # Step 2: 正则提取表格(0 token)
    tables = extract_tables_from_text(section)
    key_tables = [t for t in tables if any(kw in ' '.join(t['headers']) for kw in ['股东','持股','出资','认购','比例','数量'])]
    print(f'[3] 表格: {len(tables)}个, 关键{len(key_tables)}个')

    # Step 3: 去表格文本准备喂AI
    text_wo_tables = section
    for t in tables:
        text_wo_tables = text_wo_tables.replace(t['html'], f'\n[表格:{len(t["rows"])}行]\n')
    text_wo_tables = text_wo_tables[:10000]
    print(f'[4] 去表格文本: {len(text_wo_tables):,}字符 → AI输入(~{len(text_wo_tables)//2} tokens)')

    # Step 4: 关键词覆盖检查
    for kw in ['增资','股权转让','出资','认购','持股比例']:
        cnt = section.count(kw)
        status = 'OK' if cnt >= 2 else 'LOW'
        print(f'     "{kw}": {cnt}次 [{status}]')

    # Step 5: AI提取
    print(f'[5] 调用Deepseek(T=0.0)...')
    user_prompt = f"公司: {company}({code})\n---\n{text_wo_tables}\n---\n请提取认缴流量和股权存量。"
    ai_records = call_deepseek(user_prompt)
    ai_subs = sum(1 for r in ai_records if r.get('record_type')=='subscription_flow')
    ai_snaps = sum(1 for r in ai_records if r.get('record_type')=='equity_snapshot')
    print(f'    AI结果: {ai_subs}认缴 + {ai_snaps}存量')

    # Step 6: 用AI结果更新JSONL的null值
    jl = Path(f'outputs/week2_jsonl/{code}_{company}.jsonl')
    recs = [json.loads(l) for l in jl.read_text(encoding='utf-8').strip().split('\n') if l.strip()]

    filled = 0
    for ai_r in ai_records:
        ai_name = ai_r.get('认购方') or ai_r.get('股东名称','')
        ai_date = ai_r.get('增资日期','')
        ai_tp = ai_r.get('时点','')

        for r in recs:
            r_name = r.get('认购方') or r.get('股东名称','')
            r_date = r.get('增资日期','')
            r_tp = r.get('时点','')

            # 匹配: 同名+(同时点或同日期)
            if r_name != ai_name: continue
            if ai_date and r_date and ai_date != r_date: continue
            if ai_tp and r_tp and ai_tp != r_tp: continue

            # 填充null字段
            for field in ['认购数量(万股)','认购金额(万元)','认购价格(元/股)',
                         '持股数(万股)','出资额(万元注册资本)','持股比例']:
                ai_val = ai_r.get(field)
                if ai_val is not None and r.get(field) is None:
                    r[field] = ai_val
                    filled += 1

    jl.write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in recs), encoding='utf-8')

    # 统计
    subs = [r for r in recs if r.get('record_type')=='subscription_flow']
    snaps = [r for r in recs if r.get('record_type')=='equity_snapshot']
    sub_null = sum(1 for r in subs if r.get('认购数量(万股)') is None and r.get('认购金额(万元)') is None)
    snap_null = sum(1 for r in snaps if r.get('持股比例') is None and r.get('持股数(万股)') is None and r.get('出资额(万元注册资本)') is None)
    print(f'[6] AI填充: {filled}个值 | 认缴null={sub_null} 存量null={snap_null}')

    time.sleep(2)

# 生成Excel+cross_check
print(f'\n{"="*60}')
print('  生成Excel + cross_check')
import subprocess
subprocess.run(['py','scripts/jsonl_to_excel.py'], check=False)
print('Done')
