# -*- coding: utf-8 -*-
"""
Week 4 新流水线: Markdown → TOC定位 → 正则抓表(0 token) → AI抽段落 → Cross-check
核心优化: 表格走正则不消耗token, 段落走AI精准提取
"""
import re, json, sys, time
from pathlib import Path
from collections import defaultdict

# 8家公司的Markdown文件
MD_FILES = {
    '001282': 'MinerU_Output/MinerU_markdown_001282_三联锻造_招股说明书_2076218706897772550.md',
    '603418': 'MinerU_Output/MinerU_markdown_603418_友升股份_招股说明书_2076218706897772552.md',
    '301581': 'MinerU_Output/MinerU_markdown_301581_黄山谷捷_招股说明书_2076218706897772551.md',
    '301563': 'MinerU_Output/MinerU_markdown_301563_云汉芯城_招股说明书_2076218706897772544.md',
    '688758': 'MinerU_Output/MinerU_markdown_688758_赛分科技_招股说明书_2076218706897772546.md',
    '688775': 'MinerU_Output/MinerU_markdown_688775_影石创新_招股说明书_2076218706897772547.md',
    '920100': 'MinerU_Output/MinerU_markdown_920100_三协电机_招股说明书_2076218706897772548.md',
    '920116': 'MinerU_Output/MinerU_markdown_920116_星图测控_招股说明书_2076218706897772549.md',
}

# VC相关章节关键词
SECTION_KEYWORDS = [
    '发行人基本情况', '历史沿革', '股本形成', '历次增资', '历次股权转让',
    '股东情况', '发行前股本结构', '前十名股东', '控股股东', '实际控制人',
    '股权结构', '股本结构', '定向发行', '员工持股',
]

def extract_tables_from_md(md_text):
    """从Markdown中提取所有HTML表格, 返回 [{type, headers, rows}]"""
    tables = []
    for m in re.finditer(r'<table>(.+?)</table>', md_text, re.DOTALL):
        rows = re.findall(r'<tr>(.+?)</tr>', m.group(1), re.DOTALL)
        parsed_rows = []
        for row_html in rows:
            cells = [c.strip() for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row_html, re.DOTALL)]
            if cells:
                parsed_rows.append(cells)
        if parsed_rows:
            tables.append({
                'headers': parsed_rows[0] if parsed_rows else [],
                'rows': parsed_rows[1:] if len(parsed_rows) > 1 else [],
                'html': m.group(0),
                'position': m.start(),
            })
    return tables

def locate_section(md_text, section_name='发行人基本情况'):
    """在Markdown中定位目标章节的起止位置"""
    # 找所有#和##标题
    headers = list(re.finditer(r'^#{1,3}\s+(.+)$', md_text, re.MULTILINE))
    target_idx = None
    for i, m in enumerate(headers):
        title = m.group(1)
        if section_name in title and len(title) < 80:
            target_idx = i
            break

    if target_idx is None:
        m = re.search(r'发行人基本情况', md_text)
        if m:
            start = max(0, m.start() - 500)
            end = min(len(md_text), m.end() + 50000)
            return start, end, 'fallback_text_search'
        return 0, len(md_text), 'full_text'

    start = headers[target_idx].start()
    # 找下一个同级或更高级标题
    next_start = len(md_text)
    for j in range(target_idx + 1, min(target_idx + 20, len(headers))):
        end = headers[j].start()
        next_start = end
        break
    # 至少取20000字符
    if next_start - start < 20000:
        next_start = min(len(md_text), start + 50000)
    return start, next_start, f'section: {headers[target_idx].group(1)}'

def main():
    code = sys.argv[1] if len(sys.argv) > 1 else '920116'
    md_path = Path(MD_FILES.get(code, ''))
    if not md_path.exists():
        print(f'Markdown文件不存在: {code}')
        return

    company = {
        '001282':'三联锻造','603418':'友升股份','301581':'黄山谷捷',
        '301563':'云汉芯城','688758':'赛分科技','688775':'影石创新',
        '920100':'三协电机','920116':'星图测控',
    }.get(code, code)

    print(f'{"="*60}')
    print(f'  Week4 Markdown流水线: {company} ({code})')
    print(f'{"="*60}')

    md_text = md_path.read_text(encoding='utf-8')
    print(f'[1] Markdown总字符: {len(md_text):,}')

    # Step 1: TOC定位
    start, end, method = locate_section(md_text)
    section_text = md_text[start:end]
    print(f'[2] TOC定位: {method} → 截取 {len(section_text):,} 字符 ({start}-{end})')

    # Step 2: 提取表格(0 token)
    all_tables = extract_tables_from_md(section_text)
    print(f'[3] 表格提取: {len(all_tables)} 个表格')

    # 识别关键表格
    key_tables = []
    for t in all_tables:
        header_text = ' '.join(t['headers']).lower()
        if any(kw in header_text for kw in ['股东', '持股', '出资', '认购', '股本', '合伙']):
            key_tables.append(t)
    print(f'    其中关键表格: {len(key_tables)} 个')

    # Step 3: 关键表格内容预览
    for i, t in enumerate(key_tables[:5]):
        headers = t['headers']
        print(f'\n  表格{i+1}: {headers[:5]}')
        for row in t['rows'][:5]:
            print(f'    {" | ".join(row[:5])}')
        if len(t['rows']) > 5:
            print(f'    ... ({len(t["rows"])} 行总计)')

    # Step 4: 关键词覆盖检查
    for kw in ['增资','股权转让','出资','认购','持股比例','股东名称','定向发行']:
        cnt = section_text.count(kw)
        ok = 'OK' if cnt >= 2 else 'LOW'
    print(f'[4] 关键词"{kw}": {cnt}次 [{ok}]')

    # Step 5: 段落文本(去表格)准备喂AI
    text_wo_tables = section_text
    for t in all_tables:
        text_wo_tables = text_wo_tables.replace(t['html'], f'\n[表格: {len(t["rows"])}行, 表头: {t["headers"][:3]}]\n')
    text_wo_tables = text_wo_tables[:12000]  # 截断到12K字符

    print(f'\n[5] 去表格后文本: {len(text_wo_tables):,} 字符 → 准备喂AI (约 {len(text_wo_tables)//2} tokens)')
    print(f'    对比旧方式(全文~45000 tokens): 节省约 {(1-len(text_wo_tables)/2/45000)*100:.0f}%')

    # Step 6: 如果有认缴/增资相关表格, 正则直接写入JSONL (0 token!)
    records = []
    for t in key_tables:
        if any(kw in ' '.join(t['headers']) for kw in ['持股', '股东', '出资', '比例']):
            for row in t['rows']:
                if len(row) >= 3 and row[1] and any(c.isdigit() for c in ' '.join(row[-2:])):
                    # 这很可能是股权结构表, 尝试解析
                    pass  # 需要具体表格结构判断

    print(f'\n[6] 正则直接提取: {len(records)} 条 (0 token)')

    # 保存中间结果
    out_dir = Path('outputs/week4_markdown')
    out_dir.mkdir(exist_ok=True)

    # 保存截取的章节文本
    (out_dir / f'{code}_{company}_section.txt').write_text(section_text, encoding='utf-8')

    # 保存去表格文本(用于AI)
    (out_dir / f'{code}_{company}_ai_input.txt').write_text(text_wo_tables, encoding='utf-8')

    print(f'\n[7] 中间结果已保存: {out_dir}')
    print(f'    section.txt: {len(section_text):,} 字符')
    print(f'    ai_input.txt: {len(text_wo_tables):,} 字符 (约 {len(text_wo_tables)//2} tokens)')

    print(f'\n{"="*60}')
    print(f'  完成! 下一步: py scripts/extract_week2.py 或手动调用AI')
    print(f'{"="*60}')

if __name__ == '__main__':
    main()
