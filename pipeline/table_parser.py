# -*- coding: utf-8 -*-
"""
HTML表格解析器 — rowspan/colspan 展开 + 单元格提取
解决MinerU Markdown中rowspan/colspan导致的列偏移和重复填充问题

测试用例:
- 赛分科技 2021-04 增资表: rowspan=4 (增资价格53.99)
- 赛分科技 2021-11 增资表: rowspan=10 (股份价格127.24)
- 赛分科技 2021-12 股权结构表: colspan=2 (合计行)
"""
import re
from copy import deepcopy


def expand_rowspan_colspan(html_table: str) -> str:
    """
    展开HTML表格中的rowspan和colspan属性，返回等价的完整行列HTML。

    原理:
    1. 解析每个单元格的rowspan/colspan属性
    2. 维护一个占用矩阵，标记哪些位置已被rowspan/colspan覆盖
    3. 对每个cell，在占用矩阵中找到下一个空闲位置
    4. 根据rowspan/colspan在占用矩阵中标记后续位置
    5. 生成新的完整HTML（无rowspan/colspan属性，缺失cell用前一行的值填充）

    Args:
        html_table: 原始HTML表格字符串 (不含<table>标签)

    Returns:
        展开后的HTML表格字符串 (不含<table>标签)，每行cell数一致
    """
    # 提取所有行
    rows_html = re.findall(r'<tr>(.+?)</tr>', html_table, re.DOTALL)
    if not rows_html:
        return html_table

    # 第一遍: 解析所有单元格，建立grid
    # grid[row][col] = {'html': ..., 'rowspan': int, 'colspan': int}
    grid = []
    rowspans = {}  # (row, col) -> (end_row, html)  记录跨行单元格

    for i, row_html in enumerate(rows_html):
        cells = re.findall(r'<t[dh]([^>]*?)>(.*?)</t[dh]>', row_html, re.DOTALL)
        grid_row = []
        col = 0

        for attrs, content in cells:
            # 跳过已被rowspan占用的列
            while (i, col) in rowspans:
                end_row, span_html = rowspans[(i, col)]
                grid_row.append({'html': span_html, 'rowspan': 1, 'colspan': 1, 'is_span_fill': True})
                col += 1

            # 解析rowspan/colspan
            rs_match = re.search(r'rowspan\s*=\s*["\']?(\d+)', attrs)
            cs_match = re.search(r'colspan\s*=\s*["\']?(\d+)', attrs)
            rs = int(rs_match.group(1)) if rs_match else 1
            cs = int(cs_match.group(1)) if cs_match else 1

            cell_data = {
                'html': content.strip(),
                'rowspan': rs,
                'colspan': cs,
                'is_span_fill': False,
            }

            # 在grid中填充colspan
            for c_offset in range(cs):
                grid_row.append(cell_data)
                # 标记rowspan占用的后续行位置
                if rs > 1:
                    for r_offset in range(1, rs):
                        rowspans[(i + r_offset, col + c_offset)] = (i + rs - 1, content.strip())
            col += cs

        grid.append(grid_row)

    # 第二遍: 找到最大列数
    max_cols = max(len(row) for row in grid) if grid else 0

    # 第三遍: 填充每行到相同列数，并处理rowspan填充
    result_rows = []
    for i, row in enumerate(grid):
        result_cells = []
        for j in range(max_cols):
            if j < len(row):
                cell = row[j]
            else:
                result_cells.append('')
                continue

            if (i, j) in rowspans and not cell.get('is_span_fill'):
                # 这是rowspan的起始cell，已经正确，但后续行已有标记
                pass

            content = cell['html']
            # 清理残留的rowspan/colspan属性（仅保留内容文本）
            # 但保留子标签如<eq>, <sup>等
            result_cells.append(content)

        result_rows.append(result_cells)

    # 第四遍: 重建HTML
    result_parts = []
    for row in result_rows:
        cells_html = ''.join(f'<td>{cell}</td>' for cell in row)
        result_parts.append(f'<tr>{cells_html}</tr>')

    return '\n'.join(result_parts)


def extract_cells_from_table(html_table: str, expand_spans: bool = True) -> list[list[str]]:
    """
    从HTML表格中提取所有单元格文本，可选择是否展开rowspan/colspan。

    Args:
        html_table: HTML表格字符串 (可以包含<table>标签)
        expand_spans: 是否展开rowspan/colspan

    Returns:
        [['cell11', 'cell12', ...], ['cell21', 'cell22', ...], ...]
    """
    if expand_spans:
        # 先展开rowspan/colspan
        inner = html_table
        m = re.search(r'<table>(.+?)</table>', inner, re.DOTALL)
        if m:
            inner = m.group(1)
        expanded = expand_rowspan_colspan(inner)
        html_table = f'<table>{expanded}</table>' if m else expanded

    # 提取所有行
    rows = re.findall(r'<tr>(.+?)</tr>', html_table, re.DOTALL)
    result = []
    for row_html in rows:
        cells = [c.strip() for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row_html, re.DOTALL)]
        if cells:
            result.append(cells)
    return result


def parse_all_tables(md_text: str, expand_spans: bool = True) -> list[dict]:
    """
    从Markdown文本中提取所有HTML表格，可选展开rowspan/colspan。

    Returns:
        [{'headers': [...], 'rows': [[...], ...], 'html': '<table>...</table>', 'position': int}, ...]
    """
    tables = []
    for m in re.finditer(r'<table>(.+?)</table>', md_text, re.DOTALL):
        original_html = m.group(0)
        inner = m.group(1)

        if expand_spans and ('rowspan' in inner or 'colspan' in inner):
            expanded_inner = expand_rowspan_colspan(inner)
            expanded_html = f'<table>{expanded_inner}</table>'
        else:
            expanded_html = original_html

        cells = extract_cells_from_table(expanded_html, expand_spans=False)

        if len(cells) >= 2:
            tables.append({
                'headers': cells[0],
                'rows': cells[1:],
                'html': expanded_html,
                'original_html': original_html,
                'position': m.start(),
                'had_rowspan_colspan': 'rowspan' in inner or 'colspan' in inner,
            })
        elif len(cells) == 1:
            tables.append({
                'headers': cells[0],
                'rows': [],
                'html': expanded_html,
                'original_html': original_html,
                'position': m.start(),
                'had_rowspan_colspan': 'rowspan' in inner or 'colspan' in inner,
            })
    return tables


# === 测试用例 ===
if __name__ == '__main__':
    # 测试1: 赛分科技2021-04增资表 rowspan=4
    print("=" * 60)
    print("测试1: rowspan=4 (增资价格53.99)")
    test1 = '<table><tr><td>序号</td><td>股东姓名/名称</td><td>认缴出资额(万元)</td><td>增资价格(元/注册资本)</td><td>增资金额(万元)</td><td>出资方式</td></tr><tr><td>1</td><td>国寿走泉</td><td>250.0615</td><td rowspan="4">53.99</td><td>13,500.0000</td><td>货币</td></tr><tr><td>2</td><td>复星惟盈</td><td>89.0431</td><td>4,807.1429</td><td>货币</td></tr><tr><td>3</td><td>唐斌</td><td>2.1169</td><td>114.2857</td><td>货币</td></tr><tr><td>4</td><td>张敏</td><td>1.4554</td><td>78.5714</td><td>货币</td></tr></table>'

    tables1 = parse_all_tables(test1, expand_spans=True)
    print(f"  表格数: {len(tables1)}")
    print(f"  表头: {tables1[0]['headers']}")
    print(f"  有rowspan/colspan: {tables1[0]['had_rowspan_colspan']}")
    for i, row in enumerate(tables1[0]['rows']):
        print(f"  Row {i+1} ({len(row)} cells): {row}")
    # 验证: 每行应该有6个cell
    all_6 = all(len(r) == 6 for r in tables1[0]['rows'])
    prices = [r[3] for r in tables1[0]['rows']]
    all_5399 = all(p == '53.99' for p in prices)
    print(f"  [PASS] All 6-cols={all_6}, All 53.99={all_5399}")

    # 测试2: 赛分科技2021-11增资表 rowspan=10
    print("\n" + "=" * 60)
    print("测试2: rowspan=10 (股份价格127.24)")
    test2 = '<table><tr><td>序号</td><td>股东姓名/名称</td><td>认购股份(股)</td><td>股份价格(元/股)</td><td>认购金额(万元)</td><td>出资方式</td></tr><tr><td>1</td><td>源峰磐赛</td><td>1,571,815</td><td rowspan="10">127.24</td><td>20,000.00</td><td>货币</td></tr><tr><td>2</td><td>珠海峦恒</td><td>628,726</td><td>8,000.00</td><td>货币</td></tr><tr><td>3</td><td>高瓴祈睿</td><td>628,726</td><td>8,000.00</td><td>货币</td></tr><tr><td>4</td><td>国药中生</td><td>461,846</td><td>5,876.59</td><td>货币</td></tr><tr><td>5</td><td>圣成投资</td><td>9,699</td><td>123.41</td><td>货币</td></tr><tr><td>6</td><td>国药二期</td><td>155,625</td><td>1,980.20</td><td>货币</td></tr><tr><td>7</td><td>圣祁投资</td><td>1,556</td><td>19.80</td><td>货币</td></tr><tr><td>8</td><td>夏尔巴二期</td><td>392,954</td><td>5,000.00</td><td>货币</td></tr><tr><td>9</td><td>甘李药业</td><td>235,772</td><td>3,000.00</td><td>货币</td></tr><tr><td>10</td><td>吴征涛</td><td>157,182</td><td>2,000.00</td><td>货币</td></tr><tr><td colspan="2">合计</td><td>4,243,901</td><td>-</td><td>54,000.00</td><td>-</td></tr></table>'

    tables2 = parse_all_tables(test2, expand_spans=True)
    print(f"  表格数: {len(tables2)}")
    print(f"  表头: {tables2[0]['headers']}")
    for i, row in enumerate(tables2[0]['rows']):
        print(f"  Row {i+1} ({len(row)} cells): {row}")
    all_6_v2 = all(len(r) == 6 for r in tables2[0]['rows'])
    prices2 = [r[3] for r in tables2[0]['rows'] if '合计' not in str(r)]
    all_12724 = all(p == '127.24' for p in prices2)
    print(f"  [PASS] All 6-cols={all_6_v2}, All 127.24={all_12724}")

    # 测试3: colspan=2 (合计行)
    print("\n" + "=" * 60)
    print("测试3: colspan=2 (合计行)")
    test3 = '<table><tr><td>序号</td><td>股东</td><td>持股数量(股)</td><td>持股比例(%)</td></tr><tr><td>1</td><td>赛分有限</td><td>79,399</td><td>100.0000</td></tr><tr><td colspan="2">总计</td><td>79,399</td><td>100.0000</td></tr></table>'

    tables3 = parse_all_tables(test3, expand_spans=True)
    print(f"  表头: {tables3[0]['headers']}")
    for i, row in enumerate(tables3[0]['rows']):
        print(f"  Row {i+1} ({len(row)} cells): {row}")

    print("\n" + "=" * 60)
    all_pass = all_6 and all_5399 and all_6_v2 and all_12724
    print("ALL TESTS PASS!" if all_pass else "SOME TESTS FAILED!")
    exit(0 if all_pass else 1)
