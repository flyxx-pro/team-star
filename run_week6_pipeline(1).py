# -*- coding: utf-8 -*-
"""Week 6 reproducible pipeline.

This entry point intentionally starts from saved PDF/Markdown-derived raw records
under data/raw_response, not from manual_gold or final outputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List


UNIFIED_CODES = ["603418", "001282", "301581", "301563", "688758", "688775", "920100", "920116"]
FORBIDDEN_SUBSTITUTES = {"603072", "920091"}

SUBSCRIPTION_COLUMNS = [
    "record_id",
    "stock_code",
    "company_short",
    "source_file",
    "source_record_no",
    "pdf_page",
    "event_date",
    "batch_label",
    "subscriber_name",
    "investor_type_auto",
    "subscription_shares_wan",
    "subscription_amount_wan",
    "subscription_price_yuan",
    "computed_price_yuan",
    "entity_type",
    "subscription_ratio_pct",
    "paid_in_amount_wan",
    "currency",
    "source_evidence",
    "auto_flags",
]

TRANSFER_COLUMNS = [
    "record_id",
    "stock_code",
    "company_short",
    "source_file",
    "source_record_no",
    "pdf_page",
    "transfer_date",
    "batch_label",
    "transferor_name",
    "transferee_name",
    "transferred_shares_wan",
    "transfer_amount_wan",
    "transfer_price_yuan",
    "transfer_ratio_pct",
    "source_evidence",
    "auto_flags",
]

SNAPSHOT_COLUMNS = [
    "record_id",
    "stock_code",
    "company_short",
    "source_file",
    "source_record_no",
    "pdf_page",
    "time_point",
    "equity_structure_scope",
    "shareholder_name",
    "investor_type_auto",
    "shares_held_wan",
    "capital_contribution_wan",
    "shareholding_ratio_pct",
    "total_shares_wan",
    "total_capital_wan",
    "source_evidence",
    "auto_flags",
]


def read_csv_dict(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, Any]], columns: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_text(value: Any, limit: int = 800) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def to_float(value: Any) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def classify_investor(name: str, entity_type: str = "") -> str:
    text = f"{name} {entity_type}"
    if any(k in text for k in ["员工", "持股平台", "策星", "岚沣", "泽升", "三联合伙", "贤达", "杰贤", "博达"]):
        return "员工持股平台/员工激励"
    if any(k in text for k in ["私募", "基金", "创投", "创业投资", "投资基金", "红土", "富海", "达晨", "国科瑞华", "华泰", "金浦", "高瓴", "朗玛", "华金", "基石"]):
        return "PE/VC或私募基金"
    if any(k in text for k in ["有限公司", "股份有限公司", "集团", "公司"]):
        return "产业资本/法人股东"
    if any(k in text for k in ["合伙企业", "有限合伙"]):
        return "合伙企业-待复核"
    return "自然人/其他"


def flag_missing(row: Dict[str, Any], fields: Iterable[str]) -> List[str]:
    flags = []
    for field in fields:
        if row.get(field) in ("", None):
            flags.append(f"缺少{field}")
    return flags


def load_raw_records(raw_dir: Path, manifest_rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    allowed = {r["stock_code"] for r in manifest_rows}
    short_name = {r["stock_code"]: r["company_short"] for r in manifest_rows}
    for path in sorted(raw_dir.glob("*.jsonl")):
        stock_code = path.name.split("_", 1)[0]
        if stock_code not in allowed:
            continue
        with path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                row["_source_file"] = path.name
                row["_source_record_no"] = i
                row["_company_short"] = short_name.get(stock_code, row.get("company_name", ""))
                records.append(row)
    return records


def build_subscription_auto(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    counters = defaultdict(int)
    for r in records:
        if r.get("record_type") != "subscription_flow":
            continue
        code = str(r.get("stock_code"))
        counters[code] += 1
        shares = to_float(r.get("subscription_shares_wan"))
        amount = to_float(r.get("subscription_amount_wan"))
        price = to_float(r.get("subscription_price_yuan"))
        computed_price = round(amount / shares, 4) if shares and amount else ""
        flags = flag_missing(
            r,
            ["subscription_date", "subscriber_name"],
        )
        if price is None and computed_price != "":
            flags.append("PDF未直接披露单价，按金额/股份计算")
        if computed_price != "" and (computed_price < 0.1 or computed_price > 500):
            flags.append("计算单价疑似单位异常，需人工复核")
        if amount is None:
            flags.append("投资金额未披露或非现金出资，保留空值")
        if shares is None:
            flags.append("认购/新增股份未披露，保留空值")
        entity = r.get("entity_type") or ""
        name = r.get("subscriber_name") or ""
        rows.append(
            {
                "record_id": f"AUTO-SUB-{code}-{counters[code]:03d}",
                "stock_code": code,
                "company_short": r.get("_company_short", r.get("company_name", "")),
                "source_file": r.get("_source_file", ""),
                "source_record_no": r.get("_source_record_no", ""),
                "pdf_page": r.get("pdf_page", ""),
                "event_date": r.get("subscription_date", ""),
                "batch_label": r.get("batch_label", ""),
                "subscriber_name": name,
                "investor_type_auto": classify_investor(name, entity),
                "subscription_shares_wan": shares if shares is not None else "",
                "subscription_amount_wan": amount if amount is not None else "",
                "subscription_price_yuan": price if price is not None else "",
                "computed_price_yuan": computed_price,
                "entity_type": entity,
                "subscription_ratio_pct": r.get("subscription_ratio", ""),
                "paid_in_amount_wan": r.get("paid_in_amount_wan", ""),
                "currency": r.get("currency", "人民币"),
                "source_evidence": clean_text(r.get("evidence_text")),
                "auto_flags": "|".join(flags),
            }
        )
    return rows


def build_snapshot_auto(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    counters = defaultdict(int)
    for r in records:
        if r.get("record_type") != "equity_snapshot":
            continue
        code = str(r.get("stock_code"))
        counters[code] += 1
        name = r.get("shareholder_name") or ""
        flags = flag_missing(r, ["time_point", "shareholder_name"])
        if r.get("shareholding_ratio") in ("", None):
            flags.append("持股比例未披露，保留空值")
        if r.get("shares_held_wan") in ("", None) and r.get("capital_contribution_wan") in ("", None):
            flags.append("股份数/出资额均未披露，进入复核")
        rows.append(
            {
                "record_id": f"AUTO-SNAP-{code}-{counters[code]:03d}",
                "stock_code": code,
                "company_short": r.get("_company_short", r.get("company_name", "")),
                "source_file": r.get("_source_file", ""),
                "source_record_no": r.get("_source_record_no", ""),
                "pdf_page": r.get("pdf_page", ""),
                "time_point": r.get("time_point", ""),
                "equity_structure_scope": r.get("equity_structure_scope", ""),
                "shareholder_name": name,
                "investor_type_auto": classify_investor(name),
                "shares_held_wan": r.get("shares_held_wan", ""),
                "capital_contribution_wan": r.get("capital_contribution_wan", ""),
                "shareholding_ratio_pct": r.get("shareholding_ratio", ""),
                "total_shares_wan": r.get("total_shares_wan", ""),
                "total_capital_wan": r.get("total_capital_wan", ""),
                "source_evidence": clean_text(r.get("evidence_text")),
                "auto_flags": "|".join(flags),
            }
        )
    return rows


def parse_transfer_candidate(r: Dict[str, Any]) -> Dict[str, Any]:
    text = clean_text(" ".join([str(r.get("evidence_text") or ""), str(r.get("notes") or ""), str(r.get("batch_label") or "")]), 1000)
    date_match = re.search(r"(\d{4}年\d{1,2}月\d{1,2}日|\d{4}年\d{1,2}月|\d{4}-\d{1,2}-\d{1,2})", text)
    pct_match = re.search(r"(\d+(?:\.\d+)?)%\s*股权", text)
    amount_match = re.search(r"对价(?:为|向)?\s*([0-9,]+(?:\.\d+)?)\s*万元", text)
    shares_match = re.search(r"股本\s*([0-9,]+(?:\.\d+)?)\s*万元|([0-9,]+(?:\.\d+)?)\s*万股", text)

    transferor = ""
    transferee = ""
    m = re.search(r"([\u4e00-\u9fa5A-Za-z0-9（）()·\-]+?)将其持有.*?转让给([\u4e00-\u9fa5A-Za-z0-9（）()·\-]+)", text)
    if m:
        transferor = m.group(1)[-30:]
        transferee = m.group(2)[:30]
    else:
        m = re.search(r"同意([\u4e00-\u9fa5A-Za-z0-9（）()·\-]+?)以.*?向([\u4e00-\u9fa5A-Za-z0-9（）()·\-]+?)转让", text)
        if m:
            transferor = m.group(1)[-30:]
            transferee = m.group(2)[:30]

    flags = []
    if not transferor or not transferee:
        flags.append("仅定位到转让语句，转让方/受让方需人工复核")
    if not amount_match:
        flags.append("转让金额未稳定抽取")
    if not (pct_match or shares_match):
        flags.append("转让比例/股份数未稳定抽取")

    return {
        "transfer_date": date_match.group(1) if date_match else "",
        "transferor_name": transferor,
        "transferee_name": transferee,
        "transferred_shares_wan": (shares_match.group(1) or shares_match.group(2)) if shares_match else "",
        "transfer_amount_wan": amount_match.group(1).replace(",", "") if amount_match else "",
        "transfer_price_yuan": "",
        "transfer_ratio_pct": pct_match.group(1) if pct_match else "",
        "auto_flags": "|".join(flags),
    }


def build_transfer_auto(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates = []
    seen = set()
    term = "转让"
    for r in records:
        text = " ".join([str(r.get("evidence_text") or ""), str(r.get("notes") or ""), str(r.get("batch_label") or "")])
        if term not in text:
            continue
        key = (r.get("stock_code"), r.get("pdf_page"), clean_text(text, 120))
        if key in seen:
            continue
        seen.add(key)
        candidates.append(r)

    rows = []
    counters = defaultdict(int)
    for r in candidates:
        code = str(r.get("stock_code"))
        counters[code] += 1
        parsed = parse_transfer_candidate(r)
        rows.append(
            {
                "record_id": f"AUTO-TR-{code}-{counters[code]:03d}",
                "stock_code": code,
                "company_short": r.get("_company_short", r.get("company_name", "")),
                "source_file": r.get("_source_file", ""),
                "source_record_no": r.get("_source_record_no", ""),
                "pdf_page": r.get("pdf_page", ""),
                "transfer_date": parsed["transfer_date"],
                "batch_label": r.get("batch_label", ""),
                "transferor_name": parsed["transferor_name"],
                "transferee_name": parsed["transferee_name"],
                "transferred_shares_wan": parsed["transferred_shares_wan"],
                "transfer_amount_wan": parsed["transfer_amount_wan"],
                "transfer_price_yuan": parsed["transfer_price_yuan"],
                "transfer_ratio_pct": parsed["transfer_ratio_pct"],
                "source_evidence": clean_text(r.get("evidence_text")),
                "auto_flags": parsed["auto_flags"],
            }
        )
    return rows


def write_raw_markdown(records: List[Dict[str, Any]], raw_text_dir: Path) -> None:
    raw_text_dir.mkdir(parents=True, exist_ok=True)
    for old_file in raw_text_dir.glob("*_parsed_evidence.md"):
        old_file.unlink()
    by_code: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_code[str(r.get("stock_code"))].append(r)
    for code, rows in by_code.items():
        company = rows[0].get("_company_short", rows[0].get("company_name", ""))
        out = raw_text_dir / f"{code}_{company}_parsed_evidence.md"
        parts = [f"# {code} {company} 页码化证据文本", ""]
        for i, r in enumerate(rows, 1):
            parts.append(f"## raw_record_{i:03d}")
            parts.append(f"- record_type: {r.get('record_type', '')}")
            parts.append(f"- pdf_page: {r.get('pdf_page', '')}")
            parts.append(f"- batch/time: {r.get('batch_label') or r.get('time_point') or ''}")
            parts.append("")
            parts.append(clean_text(r.get("evidence_text"), 1600))
            parts.append("")
        out.write_text("\n".join(parts), encoding="utf-8")


def validate_manifest(manifest_rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    codes = [r["stock_code"] for r in manifest_rows]
    rows = []
    for code in UNIFIED_CODES:
        rows.append(
            {
                "check": f"统一样本包含{code}",
                "status": "PASS" if code in codes else "FAIL",
                "detail": "必须包含统一8家公司",
            }
        )
    for code in FORBIDDEN_SUBSTITUTES:
        rows.append(
            {
                "check": f"不得使用替代样本{code}",
                "status": "PASS" if code not in codes else "FAIL",
                "detail": "老师要求不能继续用天和磁材/大鹏工业替代",
            }
        )
    rows.append(
        {
            "check": "样本数量",
            "status": "PASS" if len(set(codes)) == 8 else "FAIL",
            "detail": f"manifest唯一代码数={len(set(codes))}",
        }
    )
    return rows


def build_cross_check(subscription_rows: List[Dict[str, Any]], snapshot_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    # Price consistency for subscriptions.
    for r in subscription_rows:
        shares = to_float(r.get("subscription_shares_wan"))
        amount = to_float(r.get("subscription_amount_wan"))
        price = to_float(r.get("subscription_price_yuan"))
        if shares and amount and price:
            calc = amount / shares
            diff = abs(calc - price)
            rows.append(
                {
                    "check_type": "subscription_price",
                    "stock_code": r["stock_code"],
                    "record_id": r["record_id"],
                    "status": "PASS" if diff <= 0.05 else "REVIEW",
                    "metric": round(diff, 4),
                    "detail": f"金额/股数={calc:.4f}, PDF单价={price}",
                }
            )
        elif shares and amount:
            rows.append(
                {
                    "check_type": "subscription_price",
                    "stock_code": r["stock_code"],
                    "record_id": r["record_id"],
                    "status": "INFO",
                    "metric": round(amount / shares, 4),
                    "detail": "PDF未直接披露单价，给出计算单价供人工确认",
                }
            )

    grouped: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
    for r in snapshot_rows:
        grouped[(r.get("stock_code"), r.get("time_point"))].append(r)
    for (code, tp), group in grouped.items():
        ratios = [to_float(r.get("shareholding_ratio_pct")) for r in group]
        ratios = [x for x in ratios if x is not None]
        if not ratios:
            rows.append(
                {
                    "check_type": "snapshot_ratio_sum",
                    "stock_code": code,
                    "record_id": "",
                    "status": "REVIEW",
                    "metric": "",
                    "detail": f"{tp}: 无可求和比例",
                }
            )
            continue
        total = sum(ratios)
        status = "PASS" if 99.5 <= total <= 100.5 else "REVIEW"
        rows.append(
            {
                "check_type": "snapshot_ratio_sum",
                "stock_code": code,
                "record_id": "",
                "status": status,
                "metric": round(total, 4),
                "detail": f"{tp}: 持股比例合计={total:.4f}%",
            }
        )
    return rows


def build_review_queue(auto_rows: List[Dict[str, Any]], table_name: str) -> List[Dict[str, Any]]:
    rows = []
    for r in auto_rows:
        flags = r.get("auto_flags", "")
        if flags:
            rows.append(
                {
                    "table_name": table_name,
                    "record_id": r["record_id"],
                    "stock_code": r["stock_code"],
                    "pdf_page": r.get("pdf_page", ""),
                    "review_reason": flags,
                    "source_evidence": r.get("source_evidence", ""),
                    "review_status": "待人工复核",
                }
            )
    return rows


def compare_auto_gold(root: Path, auto_name: str, key_col: str) -> List[Dict[str, Any]]:
    auto_path = root / "auto_output" / f"{auto_name}_auto.csv"
    gold_path = root / "manual_gold" / f"{auto_name}_gold.csv"
    if not gold_path.exists():
        return [
            {
                "table_name": auto_name,
                "metric": "auto_vs_gold",
                "status": "SKIP",
                "detail": "manual_gold尚未提供，已跳过对比",
            }
        ]
    auto = read_csv_dict(auto_path)
    gold = read_csv_dict(gold_path)
    auto_keys = {(r.get("stock_code"), r.get(key_col), r.get("pdf_page")) for r in auto}
    gold_keys = {(r.get("stock_code"), r.get(key_col), r.get("pdf_page")) for r in gold}
    tp = len(auto_keys & gold_keys)
    fp = len(auto_keys - gold_keys)
    fn = len(gold_keys - auto_keys)
    return [
        {
            "table_name": auto_name,
            "metric": "record_level_match",
            "status": "INFO",
            "detail": f"TP={tp}; FP={fp}; FN={fn}; key=stock_code+{key_col}+pdf_page",
        }
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Week 6 IPO financing extraction pipeline.")
    parser.add_argument("--root", default=".", help="Project root. Default: current directory.")
    parser.add_argument("--manifest", default="data/manifest/company_manifest.csv")
    parser.add_argument("--raw-response-dir", default="data/raw_response")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    manifest_path = root / args.manifest
    raw_dir = root / args.raw_response_dir

    manifest = read_csv_dict(manifest_path)
    records = load_raw_records(raw_dir, manifest)
    write_raw_markdown(records, root / "data" / "raw_text")

    subscription = build_subscription_auto(records)
    snapshot = build_snapshot_auto(records)
    transfer = build_transfer_auto(records)

    write_csv(root / "auto_output" / "subscription_auto.csv", subscription, SUBSCRIPTION_COLUMNS)
    write_csv(root / "auto_output" / "transfer_auto.csv", transfer, TRANSFER_COLUMNS)
    write_csv(root / "auto_output" / "equity_snapshot_auto.csv", snapshot, SNAPSHOT_COLUMNS)

    schema_rows = validate_manifest(manifest)
    schema_rows.extend(
        [
            {
                "check": "认缴Auto记录数",
                "status": "PASS" if len(subscription) > 0 else "FAIL",
                "detail": f"subscription_auto={len(subscription)}",
            },
            {
                "check": "转让Auto候选数",
                "status": "PASS" if len(transfer) > 0 else "REVIEW",
                "detail": f"transfer_auto={len(transfer)}; 转让候选需要人工筛选",
            },
            {
                "check": "股权快照Auto记录数",
                "status": "PASS" if len(snapshot) > 0 else "FAIL",
                "detail": f"equity_snapshot_auto={len(snapshot)}",
            },
        ]
    )
    write_csv(root / "validation" / "schema_result.csv", schema_rows, ["check", "status", "detail"])

    cross = build_cross_check(subscription, snapshot)
    write_csv(root / "validation" / "cross_check.csv", cross, ["check_type", "stock_code", "record_id", "status", "metric", "detail"])

    review = []
    review.extend(build_review_queue(subscription, "subscription"))
    review.extend(build_review_queue(transfer, "transfer"))
    review.extend(build_review_queue(snapshot, "equity_snapshot"))
    write_csv(root / "validation" / "review_queue.csv", review, ["table_name", "record_id", "stock_code", "pdf_page", "review_reason", "source_evidence", "review_status"])

    auto_gold = []
    auto_gold.extend(compare_auto_gold(root, "subscription", "subscriber_name"))
    auto_gold.extend(compare_auto_gold(root, "transfer", "transferee_name"))
    auto_gold.extend(compare_auto_gold(root, "equity_snapshot", "shareholder_name"))
    write_csv(root / "validation" / "auto_vs_gold.csv", auto_gold, ["table_name", "metric", "status", "detail"])

    hash_rows = []
    for path in sorted((root / "data").rglob("*")):
        if path.is_file():
            hash_rows.append(
                {
                    "file": str(path.relative_to(root)),
                    "size_bytes": path.stat().st_size,
                    "sha256": file_sha256(path),
                }
            )
    write_csv(root / "logs" / "file_hashes.csv", hash_rows, ["file", "size_bytes", "sha256"])

    run_log = [
        {
            "run_time": datetime.now().isoformat(timespec="seconds"),
            "manifest": str(manifest_path.relative_to(root)),
            "raw_response_dir": str(raw_dir.relative_to(root)),
            "raw_records": len(records),
            "subscription_auto": len(subscription),
            "transfer_auto": len(transfer),
            "equity_snapshot_auto": len(snapshot),
            "note": "Auto starts from data/raw_response and generated data/raw_text; manual_gold/final are not read before Auto generation.",
        }
    ]
    write_csv(root / "logs" / "run_log.csv", run_log, ["run_time", "manifest", "raw_response_dir", "raw_records", "subscription_auto", "transfer_auto", "equity_snapshot_auto", "note"])

    print(f"Week 6 pipeline completed: {root}")
    print(f"Auto rows: subscription={len(subscription)}, transfer={len(transfer)}, snapshot={len(snapshot)}")


if __name__ == "__main__":
    main()
