# -*- coding: utf-8 -*-
"""
Step 5: 从 MinerU JSON 中定位 VC 相关章节并截取候选文本
========================================================
输入：MinerU_Output/*.json
输出：
  - outputs/week1_candidate_texts/{code}_{company}_candidate.txt
  - logs/locate_log.csv
"""
import json
import os
import re
import csv
from pathlib import Path
from collections import defaultdict

# 配置
MINERU_DIR = Path('MinerU_Output')
OUTPUT_DIR = Path('outputs/week1_candidate_texts')
LOG_DIR = Path('logs')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# VC 章节定位关键词（按优先级）
SECTION_MARKERS = [
    # 一级：精确章节标题
    ('发行人基本情况', '第五节'),
    ('历史沿革', '发行人'),
    ('股本形成及变化', '发行人'),
    ('历次增资', '发行人'),
    ('历次股权转让', '发行人'),
    ('股东情况', '发行人'),
    ('发行前股本结构', '发行人'),
    ('前十名股东', '发行人'),
    ('控股股东及实际控制人', '发行人'),
    ('持有5%以上股份', '发行人'),
    # 二级：正文中的子标题
    ('发行人设立情况', ''),
    ('发行人股本形成', ''),
    ('发行人历次增资', ''),
    ('发行人股权转让', ''),
    ('本次发行前后的股本结构', ''),
    ('股权结构', '发行人'),
]

# VC 数据关键词（用于截取上下文）
VC_KEYWORDS = [
    '增资', '股权转让', '出资', '认购', '入股',
    '投资者', '外部投资者', '财务投资者',
    '风险投资', '私募股权', '创投', '创业投资',
    '产业基金', '股权投资基金', '持股比例',
    '投前估值', '投后估值', '每股价格', '认购价格',
    '股份锁定', '对赌', '特殊投资条款',
]


def read_mineru_json(filepath: Path) -> list:
    """读取 MinerU JSON，返回 [{'page': N, 'text': str}, ...]"""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    pages = []
    pdf_info = data.get('pdf_info', [])
    for page_idx, page_data in enumerate(pdf_info):
        page_num = page_idx + 1
        texts = []
        for block in page_data.get('preproc_blocks', []):
            for line in block.get('lines', []):
                for span in line.get('spans', []):
                    content = span.get('content', '').strip()
                    if content:
                        texts.append(content)
        pages.append({
            'page': page_num,
            'text': '\n'.join(texts),
        })
    return pages


def locate_vc_sections(pages: list) -> dict:
    """
    定位 VC 相关章节的页码范围
    返回：{'section_name': (start_page, end_page), ...}
    """
    full_text = '\n'.join([f'[第{p["page"]}页]\n{p["text"]}' for p in pages])

    sections = {}
    for marker, context in SECTION_MARKERS:
        # 在文本中搜索章节标题
        idx = full_text.find(marker)
        if idx == -1:
            continue

        # 找到所在页码
        before = full_text[:idx]
        page_match = list(re.finditer(r'\[第(\d+)页\]', before))
        if page_match:
            page_num = int(page_match[-1].group(1))
            sections[marker] = page_num

    return sections


def extract_candidate_text(pages: list, section_pages: dict,
                           context_radius: int = 3) -> str:
    """
    提取候选文本：包含目录页 + VC 章节页 + 关键词所在页
    context_radius: 关键词所在页前后各取几页
    """
    selected = set()

    # 始终包含前 10 页（封面、目录、日期）
    selected.update(range(1, min(11, len(pages) + 1)))

    # 包含 VC 章节所在页及前后各3页
    for marker, page_num in section_pages.items():
        start = max(1, page_num - context_radius)
        end = min(len(pages), page_num + context_radius + 20)  # 章节后多取一些
        selected.update(range(start, end + 1))

    # 包含含 VC 关键词的页面
    for i, p in enumerate(pages):
        page_num = i + 1
        if page_num in selected:
            continue
        for kw in VC_KEYWORDS:
            if kw in p['text']:
                # 检查这个关键词是否在实质性内容中（非目录）
                if len(p['text']) > 200:  # 正文页通常有较多文字
                    start = max(1, page_num - context_radius)
                    end = min(len(pages), page_num + context_radius + 5)
                    selected.update(range(start, end + 1))
                    break

    # 按页码排序，生成文本
    texts = []
    for page_num in sorted(selected):
        p = pages[page_num - 1]
        texts.append(f"\n{'='*60}")
        texts.append(f"[第{page_num}页]")
        texts.append(f"{'='*60}")
        texts.append(p['text'])

    return '\n'.join(texts)


def main():
    json_files = sorted(Path(MINERU_DIR).glob('MinerU_json_*.json'))
    log_entries = []

    print("=" * 60)
    print("  Step 5: 章节定位 & 候选文本截取")
    print("=" * 60)

    for filepath in json_files:
        # 从文件名解析信息
        parts = filepath.stem.split('_')
        code = parts[2]
        company = parts[3]

        print(f"\n[{code}] {company}")

        # 1. 读取 MinerU JSON
        pages = read_mineru_json(filepath)
        total = len(pages)
        total_chars = sum(len(p['text']) for p in pages)
        print(f"  读取 {total} 页, {total_chars:,} 字符")

        # 2. 定位 VC 章节
        sections = locate_vc_sections(pages)
        print(f"  定位到 {len(sections)} 个 VC 相关章节:")
        for marker, page_num in sorted(sections.items(),
                                        key=lambda x: x[1]):
            print(f"    第{page_num}页: {marker}")

        # 3. 截取候选文本
        candidate = extract_candidate_text(pages, sections)
        selected_pages = candidate.count('[第')
        print(f"  截取候选文本: {selected_pages} 页, {len(candidate):,} 字符")

        # 4. 保存
        out_name = f"{code}_{company}_candidate.txt"
        out_path = OUTPUT_DIR / out_name
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(candidate)
        print(f"  已保存: {out_path}")

        # 5. 记录日志
        log_entries.append({
            'company_name': company,
            'stock_code': code,
            'matched_keywords': '; '.join(sections.keys()),
            'sections_found': len(sections),
            'first_vc_page': min(sections.values()) if sections else '',
            'last_vc_page': max(sections.values()) if sections else '',
            'total_pages_parsed': total,
            'candidate_pages': selected_pages,
            'candidate_chars': len(candidate),
            'candidate_text_path': str(out_path),
            'status': 'success' if sections else 'partial',
        })

    # 保存日志
    if log_entries:
        log_path = LOG_DIR / 'locate_log.csv'
        with open(log_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=log_entries[0].keys())
            writer.writeheader()
            writer.writerows(log_entries)
        print(f"\n日志已保存: {log_path}")

    # 汇总
    print(f"\n{'='*60}")
    success = sum(1 for l in log_entries if l['status'] == 'success')
    print(f"  完成: {success}/{len(log_entries)} 家公司章节定位成功")
    print(f"  候选文本已保存到: {OUTPUT_DIR}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
