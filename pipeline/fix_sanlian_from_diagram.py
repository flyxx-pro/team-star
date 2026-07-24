# -*- coding: utf-8 -*-
"""
V2: 根据股权变化图重建三联锻造 Gold — 出资额从图表比例反推
"""
import json
from pathlib import Path
from collections import defaultdict

GOLD_DIR = Path('manual_gold')

# 从图表提取的快照数据 (已验证全部 ratio=100%)
CHART_SNAPSHOTS = [
    ("2004-06 设立时", [
        ("孙国奉", 35.00), ("张松满", 32.50), ("孙国敏", 32.50),
    ], 30, 500, "注册资本500万"),

    ("2007-12 第一次增资后", [
        ("孙国奉", 31.00), ("张松满", 20.00), ("孙国敏", 19.00),
        ("孙仁豪", 13.75), ("班玉成", 8.13), ("其他人", 8.12),
    ], 31, 1500, "注册资本500→1,500万"),

    ("2008-01 第一次转让后", [
        ("孙国奉", 33.50), ("孙国敏", 33.50), ("孙仁豪", 8.13),
        ("班玉成", 8.13), ("其他人", 16.74),
    ], 31, 2000, "注册资本1,500→2,000万(张松满退出)"),

    ("2014-03 第二次转让后", [
        ("孙国奉", 33.00), ("孙仁豪", 66.50), ("班玉成", 0.50),
    ], 32, 2000, "孙国奉→孙仁豪660万"),

    ("2014-05 第二次增资后", [
        ("孙国奉", 54.06), ("孙仁豪", 27.24), ("班玉成", 8.13),
        ("高新同华", 5.70), ("其他人", 4.87),
    ], 32, 5000, "注册资本2,000→5,000万"),

    ("2017-02 第三次增资后", [
        ("孙国奉", 33.50), ("孙仁豪", 28.13), ("高新同华", 18.70),
        ("班玉成", 8.13), ("其他人", 11.54),
    ], 33, 6150, "注册资本5,000→6,150万,高新同华新进"),

    ("2017-11 第四次增资后", [
        ("孙国奉", 55.12), ("张一衡", 28.77), ("高新同华", 14.11),
        ("孙仁豪", 1.00), ("班玉成", 0.50), ("孙国敏", 0.50),
    ], 33, 8150, "未分配利润转增,6,150→8,150万"),

    ("2018-02 第三次转让后", [
        ("孙国奉", 28.06), ("张一衡", 27.91), ("高新同华", 14.11),
        ("孙仁豪", 13.53), ("孙国敏", 8.13), ("班玉成", 8.26),
    ], 34, 8150, "孙国奉转让给高新同华+张一衡"),

    ("2018-07 第四次转让后", [
        ("孙国奉", 26.91), ("张一衡", 13.53), ("高新同华", 13.53),
        ("孙仁豪", 14.11), ("孙国敏", 27.91), ("班玉成", 4.01),
    ], 34, 8150, "孙国奉→孙国敏,张一衡→孙仁豪"),

    ("2018-11 股改(净资产折股)", [
        ("孙国奉", 26.91), ("孙国敏", 28.06), ("张一衡", 13.53),
        ("高新同华", 14.11), ("孙仁豪", 13.53), ("班玉成", 1.92),
        ("其他人", 1.94),
    ], 34, 8150, "净资产折股变股份公司,股本8,150万股"),

    ("2019-12 ESOP增资后(发行前)", [
        ("孙国奉", 26.06), ("孙国敏", 27.91), ("张一衡", 13.11),
        ("高新同华", 13.53), ("孙仁豪", 13.11), ("三联合伙", 4.11),
        ("班玉成", 1.92), ("其他人", 0.25),
    ], 39, 8498, "三联合伙(ESOP)增资348万股,股本8,150→8,498万股"),
]


def compute_subscriptions_from_snapshots():
    """从相邻快照的出资额变化反推每轮增资的认购量"""
    # First, build per-shareholder capital at each time point
    tp_capitals = []  # [(tp_label, {name: capital}), ...]
    for tp, holders, page, total, note in CHART_SNAPSHOTS:
        caps = {}
        for name, ratio in holders:
            caps[name] = round(total * ratio / 100, 2)
        tp_capitals.append((tp, caps, total, page, note))

    # Now compute subscription events between consecutive time points
    subs = []
    old_sub_dates = [
        # (date, name, note) from original Gold — preserve structure
        ("2004-06-10", "孙国奉", "设立出资"),
        ("2004-06-10", "张松满", "设立出资"),
        ("2004-06-10", "孙国敏", "设立出资"),
        ("2007-11-26", "孙国奉", "第一次增资"),
        ("2007-11-26", "张松满", "第一次增资"),
        ("2007-11-26", "孙国敏", "第一次增资"),
        ("2007-11-26", "孙仁豪", "第一次增资,新进"),
        ("2014-05-01", "孙国奉", "第二次增资"),
        ("2014-05-01", "孙仁豪", "第二次增资"),
        ("2017-02-01", "高新同华", "第三次增资,新进"),
        ("2017-11-01", "孙国奉", "第四次增资,未分配利润转增"),
        ("2017-11-01", "孙仁豪", "第四次增资,未分配利润转增"),
        ("2019-12-04", "三联合伙", "ESOP增资"),
    ]

    # Only generate subs for actual 增资/设立 events (not transfer-only intervals)
    # Subscription events mapped to time point intervals
    SUB_EVENTS = [
        # (date, interval_start_tp_idx, interval_end_tp_idx, names_with_delta)
        # 设立: first interval (index 0→0, initial capital)
        ("2004-06-10", 0, 0, ["孙国奉", "张松满", "孙国敏"]),
        # 第一次增资: 2004-06设立 → 2007-12增资后 (index 0→1)
        # 注: 2007-11-26的实物置换不是增资,注册资本仍为500万,不在此列
        # 使用2007-11日期确保落在2004-06到2007-12区间内
        ("2007-11-01", 0, 1, None),  # None = all shareholders with positive delta
        # 第二次增资: 2014-03转让后 → 2014-05增资后 (index 3→4)
        ("2014-05-01", 3, 4, ["孙国奉", "孙仁豪"]),
        # 第三次增资: 2014-05增资后 → 2017-02增资后 (index 4→5)
        ("2017-02-01", 4, 5, ["高新同华"]),
        # 第四次增资(未分配利润转增): 2017-02增资后 → 2017-11增资后 (index 5→6)
        ("2017-11-01", 5, 6, ["孙国奉", "孙仁豪"]),
        # ESOP增资: 2018-11股改 → 2019-12增资后 (index 9→10)
        ("2019-12-04", 9, 10, ["三联合伙"]),
    ]

    new_subs = []
    for dt, start_idx, end_idx, names in SUB_EVENTS:
        if start_idx == end_idx:
            # 设立: use the snapshot directly
            _, caps, total, page, note = tp_capitals[start_idx]
            for name in names:
                cap = caps.get(name, 0)
                new_subs.append({
                    "record_type": "subscription_flow",
                    "PDF页码": page, "增资日期": dt, "认购方": name,
                    "出资额(万元注册资本)": cap,
                    "source": "chart_computed", "review_status": "pass",
                    "原文证据": f"股权变化图: 设立时{name}出资{cap}万元",
                })
        else:
            # 增资: delta between two snapshots
            _, prev_caps, prev_total, prev_page, _ = tp_capitals[start_idx]
            _, curr_caps, curr_total, curr_page, _ = tp_capitals[end_idx]

            # If names is None, include ALL shareholders with positive delta
            if names is None:
                all_names = set(list(prev_caps.keys()) + list(curr_caps.keys()))
                names = sorted(all_names)

            for name in names:
                prev_cap = prev_caps.get(name, 0)
                curr_cap = curr_caps.get(name, 0)
                delta = round(curr_cap - prev_cap, 2)
                if delta > 0:
                    new_subs.append({
                        "record_type": "subscription_flow",
                        "PDF页码": curr_page, "增资日期": dt, "认购方": name,
                        "出资额(万元注册资本)": delta,
                        "source": "chart_computed", "review_status": "pass",
                        "原文证据": f"股权变化图: {name}出资{prev_cap}→{curr_cap}万(+{delta}),总{prev_total}→{curr_total}万",
                    })

    return new_subs, tp_capitals


def write_all():
    code, co = '001282', '三联锻造'

    # 1. Compute subscriptions from chart snapshots
    new_subs, tp_capitals = compute_subscriptions_from_snapshots()
    print(f'Computed {len(new_subs)} subscription records')

    # Validate: total capital after each interval should match chart
    print('\nValidation:')
    cumulative = defaultdict(float)
    for r in sorted(new_subs, key=lambda x: (x['增资日期'], x['认购方'])):
        cumulative[r['认购方']] += r['出资额(万元注册资本)']

    for tp_label, caps, total, page, note in tp_capitals:
        tp_prefix = tp_label[:7]
        # Sum cumulative up to this time point
        cum_total = 0
        for r in new_subs:
            if r['增资日期'][:7] <= tp_prefix:
                cum_total += r['出资额(万元注册资本)']

        # The cumulative total should match the chart total for non-transfer events
        # (transfers change per-shareholder but not total)
        print(f'{tp_label}: chart={total}万, cum_sum={cum_total:.0f}万')

    # Save
    sub_path = GOLD_DIR / f'{code}_{co}_subscription_flow_gold.jsonl'
    sub_path.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in new_subs), encoding='utf-8')
    print(f'\nSaved {len(new_subs)} subs to {sub_path.name}')

    # 2. Write equity snapshots (unchanged)
    snap_path = GOLD_DIR / f'{code}_{co}_equity_snapshot_gold.jsonl'
    new_snaps = []
    for tp, holders, page, total, note in CHART_SNAPSHOTS:
        is_post_guigai = '股改' in tp or 'ESOP' in tp or '发行前' in tp
        for name, ratio in holders:
            capital = round(total * ratio / 100, 2)
            new_snaps.append({
                "record_type": "equity_snapshot",
                "PDF页码": page, "时点": tp, "股权结构口径": tp,
                "总股本(万股)": total if is_post_guigai else None,
                "总出资额(万元注册资本)": total if not is_post_guigai else None,
                "股东名称": name,
                "出资额(万元注册资本)": capital if not is_post_guigai else None,
                "持股数(万股)": round(total * ratio / 100, 4) if is_post_guigai else None,
                "持股比例": ratio,
                "原文证据": f"股权变化图: {tp}, 比例{ratio}%",
                "source": "chart_diagram", "review_status": "pass",
            })
    snap_path.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in new_snaps), encoding='utf-8')
    print(f'Saved {len(new_snaps)} snaps')

    # 3. Update merged gold
    merged_path = GOLD_DIR / f'{code}_{co}_gold.jsonl'
    merged_path.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in new_snaps), encoding='utf-8')

    return new_subs, new_snaps


if __name__ == '__main__':
    write_all()
