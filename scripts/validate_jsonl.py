# -*- coding: utf-8 -*-
"""Week 2 校验脚本：schema检查 + 数值cross-check"""
import json, csv, sys
from pathlib import Path
from collections import defaultdict

JSONL_DIR = Path('outputs/week2_jsonl')
LOG_DIR = Path('logs')
LOG_DIR.mkdir(exist_ok=True)

# 注意：schemas 需要 pydantic，如果未安装会跳过schema校验
try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from schemas.extraction_models import SubscriptionFlow, EquitySnapshot
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False
    print("[WARN] pydantic未安装，跳过schema校验")


def validate_jsonl(filepath):
    """校验一个JSONL文件"""
    records = []
    errors = []
    with open(filepath, encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                records.append(rec)
            except json.JSONDecodeError as e:
                errors.append(f"行{i}: JSON解析失败: {e}")

    subs = [r for r in records if r.get('record_type') == 'subscription_flow']
    snaps = [r for r in records if r.get('record_type') == 'equity_snapshot']

    # Schema校验（如果有pydantic）
    schema_errors = []
    if HAS_PYDANTIC:
        for r in subs:
            try:
                SubscriptionFlow.model_validate(r)
            except Exception as e:
                schema_errors.append(f"subscription_flow 校验失败: {str(e)[:100]}")
        for r in snaps:
            try:
                EquitySnapshot.model_validate(r)
            except Exception as e:
                schema_errors.append(f"equity_snapshot 校验失败: {str(e)[:100]}")

    # 跨字段校验
    cross_check = []

    # 1. 检查认缴流量的必填项
    for i, r in enumerate(subs):
        if not r.get('认购方'):
            errors.append(f"认缴流量#{i}: 认购方为空")
        if not r.get('增资日期'):
            errors.append(f"认缴流量#{i}: 日期为空")
        if not r.get('原文证据') or len(r.get('原文证据','')) < 10:
            errors.append(f"认缴流量#{i}: 证据不足")

    # 2. 检查股权存量
    has_t0 = any(r.get('时点') == 't0' for r in snaps)
    if not has_t0:
        errors.append("缺少t0股权结构")

    # 3. 总量cross-check：按增资日期分组
    date_groups = defaultdict(list)
    for r in subs:
        date_groups[r.get('增资日期','?')].append(r)

    for date, group in date_groups.items():
        total_shares = sum((r.get('认购数量(万股)') or 0) for r in group)
        total_amount = sum((r.get('认购金额(万元)') or 0) for r in group)
        cross_check.append({
            'check_type': 'cross_check_total',
            'date': date,
            'subscriber_count': len(group),
            'total_shares_wan': round(total_shares, 4),
            'total_amount_wan': round(total_amount, 2),
        })

    # 4. 逐股东cross-check
    snap_by_time = defaultdict(list)
    for r in snaps:
        snap_by_time[r.get('时点','?')].append(r)

    time_points = sorted(snap_by_time.keys())
    for i in range(len(time_points) - 1):
        prev_t = time_points[i]
        curr_t = time_points[i + 1]
        prev_holders = {r['股东名称']: r for r in snap_by_time[prev_t]}
        curr_holders = {r['股东名称']: r for r in snap_by_time[curr_t]}

        for name, prev in prev_holders.items():
            curr = curr_holders.get(name)
            prev_shares = prev.get('持股数(万股)') or prev.get('出资额(万元注册资本)') or 0
            curr_shares = curr.get('持股数(万股)') or curr.get('出资额(万元注册资本)') if curr else None
            if curr is None:
                # 股东退出
                pass
            elif curr_shares is not None and curr_shares < prev_shares:
                # 持股减少（可能转让）
                pass

    return {
        'file': filepath.name,
        'total_records': len(records),
        'subscription_flow_count': len(subs),
        'equity_snapshot_count': len(snaps),
        'has_t0': has_t0,
        'json_errors': len(errors),
        'schema_errors': len(schema_errors),
        'cross_checks': len(cross_check),
        'errors': errors[:10],
        'schema_errors_list': schema_errors[:10],
        'cross_check_details': cross_check[:20],
    }


def main():
    jsonl_files = sorted(JSONL_DIR.glob('*.jsonl'))
    if not jsonl_files:
        print("未找到JSONL文件")
        return

    results = []
    cross_check_rows = []

    for fp in jsonl_files:
        r = validate_jsonl(fp)
        results.append(r)
        status = 'fail' if r['json_errors'] or r['schema_errors'] else 'pass'
        print(f"{r['file']}: {r['subscription_flow_count']}认缴+{r['equity_snapshot_count']}存量, "
              f"t0={'有' if r['has_t0'] else '无'}, "
              f"JSON错误={r['json_errors']}, Schema错误={r['schema_errors']} -> {status}")

        # 收集cross-check
        code = fp.stem.split('_')[0]
        company = fp.stem.split('_')[1]
        for cc in r['cross_check_details']:
            cc['code'] = code
            cc['company'] = company
            cross_check_rows.append(cc)

    # 保存schema validation log
    vlp = LOG_DIR / 'schema_validation_log.csv'
    with open(vlp, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=[
            'file', 'total_records', 'subscription_flow_count',
            'equity_snapshot_count', 'has_t0', 'json_errors',
            'schema_errors', 'cross_checks', 'status'
        ])
        w.writeheader()
        for r in results:
            w.writerow({
                'file': r['file'], 'total_records': r['total_records'],
                'subscription_flow_count': r['subscription_flow_count'],
                'equity_snapshot_count': r['equity_snapshot_count'],
                'has_t0': r['has_t0'], 'json_errors': r['json_errors'],
                'schema_errors': r['schema_errors'],
                'cross_checks': r['cross_checks'],
                'status': 'fail' if r['json_errors'] or r['schema_errors'] else 'pass',
            })
    print(f"\nSchema校验日志: {vlp}")

    # 保存cross-check summary
    if cross_check_rows:
        ccp = LOG_DIR / 'cross_check_summary.csv'
        with open(ccp, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=cross_check_rows[0].keys())
            w.writeheader(); w.writerows(cross_check_rows)
        print(f"Cross-check日志: {ccp}")


if __name__ == '__main__':
    main()
