"""Markdown/HTML table parser with rowspan/colspan expansion.

This file is intentionally standalone so the Week 6 submission can show how
Markdown tables are normalized before table-type classification. MinerU often
exports normal Markdown pipe tables, while some preserved table fragments are
HTML tables containing rowspan/colspan. The parser expands those spans into a
rectangular grid so downstream extraction can read stable columns.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable


def clean_cell(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class HTMLTableParser(HTMLParser):
    """Collect HTML tables and preserve each cell's row/column span."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[dict[str, Any]]]] = []
        self._table_stack = 0
        self._current_rows: list[list[dict[str, Any]]] = []
        self._current_row: list[dict[str, Any]] | None = None
        self._current_cell: dict[str, Any] | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k.lower(): v for k, v in attrs}
        if tag == "table":
            self._table_stack += 1
            if self._table_stack == 1:
                self._current_rows = []
        elif tag == "tr" and self._table_stack:
            self._current_row = []
        elif tag in {"td", "th"} and self._table_stack and self._current_row is not None:
            self._current_cell = {
                "text": "",
                "rowspan": int(attrs_dict.get("rowspan") or 1),
                "colspan": int(attrs_dict.get("colspan") or 1),
            }
            self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._current_cell is not None and self._current_row is not None:
            self._current_cell["text"] = clean_cell("".join(self._text_parts))
            self._current_row.append(self._current_cell)
            self._current_cell = None
            self._text_parts = []
        elif tag == "tr" and self._table_stack and self._current_row is not None:
            self._current_rows.append(self._current_row)
            self._current_row = None
        elif tag == "table" and self._table_stack:
            self._table_stack -= 1
            if self._table_stack == 0:
                self.tables.append(self._current_rows)


def expand_spans(rows: list[list[dict[str, Any]]]) -> list[list[str]]:
    """Expand rowspan/colspan into a rectangular grid.

    Repeated span cells are copied into covered positions. This makes later
    column matching deterministic, which is more reliable than trying to infer
    missing cells after classification.
    """

    grid: list[list[str]] = []
    carry: dict[tuple[int, int], str] = {}
    max_cols = 0

    for row_idx, row in enumerate(rows):
        out_row: list[str] = []
        col_idx = 0

        for cell in row:
            while (row_idx, col_idx) in carry:
                out_row.append(carry.pop((row_idx, col_idx)))
                col_idx += 1

            text = clean_cell(cell.get("text", ""))
            rowspan = max(int(cell.get("rowspan") or 1), 1)
            colspan = max(int(cell.get("colspan") or 1), 1)

            for offset in range(colspan):
                out_row.append(text)
                for r_offset in range(1, rowspan):
                    carry[(row_idx + r_offset, col_idx + offset)] = text
            col_idx += colspan

        while (row_idx, col_idx) in carry:
            out_row.append(carry.pop((row_idx, col_idx)))
            col_idx += 1

        max_cols = max(max_cols, len(out_row))
        grid.append(out_row)

    for row in grid:
        row.extend([""] * (max_cols - len(row)))
    return grid


def parse_html_tables(text: str) -> list[list[list[str]]]:
    parser = HTMLTableParser()
    parser.feed(text)
    return [expand_spans(table) for table in parser.tables]


def parse_pipe_table_block(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [clean_cell(c) for c in stripped.strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", c.replace(" ", "")) for c in cells):
            continue
        rows.append(cells)
    width = max((len(r) for r in rows), default=0)
    for row in rows:
        row.extend([""] * (width - len(row)))
    return rows


def parse_pipe_tables(text: str) -> list[list[list[str]]]:
    tables: list[list[list[str]]] = []
    block: list[str] = []
    for line in text.splitlines():
        if line.strip().startswith("|") and "|" in line.strip()[1:]:
            block.append(line)
        else:
            if len(block) >= 2:
                table = parse_pipe_table_block(block)
                if table:
                    tables.append(table)
            block = []
    if len(block) >= 2:
        table = parse_pipe_table_block(block)
        if table:
            tables.append(table)
    return tables


def parse_tables_from_markdown(text: str) -> list[dict[str, Any]]:
    html_tables = parse_html_tables(text)
    pipe_tables = parse_pipe_tables(re.sub(r"<table.*?</table>", "", text, flags=re.I | re.S))
    parsed = []
    for i, table in enumerate(html_tables, 1):
        parsed.append({"table_id": f"html_table_{i:03d}", "source_type": "html", "rows": table})
    for i, table in enumerate(pipe_tables, 1):
        parsed.append({"table_id": f"markdown_table_{i:03d}", "source_type": "pipe_markdown", "rows": table})
    return parsed


def write_tables_csv(tables: Iterable[dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for table in tables:
        rows = table["rows"]
        with (out_dir / f"{table['table_id']}.csv").open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse Markdown/HTML tables and expand rowspan/colspan.")
    parser.add_argument("input", help="Markdown file path.")
    parser.add_argument("--out-dir", default="auto_output/parsed_markdown_tables", help="Directory for parsed CSV tables.")
    parser.add_argument("--json", default="", help="Optional JSON output path.")
    args = parser.parse_args()

    text = Path(args.input).read_text(encoding="utf-8")
    tables = parse_tables_from_markdown(text)
    write_tables_csv(tables, Path(args.out_dir))
    if args.json:
        Path(args.json).write_text(json.dumps(tables, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"parsed_tables={len(tables)}")


if __name__ == "__main__":
    main()
