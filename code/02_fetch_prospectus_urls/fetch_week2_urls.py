# -*- coding: utf-8 -*-
"""
Week 2 Step 2: 根据企业清单批量获取招股书下载链接
================================================
输入：company_lists/week2_2025_company_list.csv
输出：company_lists/week2_2025_company_list.csv（补充prospectus_url字段）
"""
import sys; sys.path.insert(0, '.')
import csv, time, random, requests
from pathlib import Path

API_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
INPUT_CSV = Path("company_lists/week2_2025_company_list.csv")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
]


def fetch_urls():
    if not INPUT_CSV.exists():
        print(f"[ERROR] 找不到 {INPUT_CSV}，请先运行 build_2025_kcb_list.py")
        return

    # 读取已有清单
    rows = []
    with open(INPUT_CSV, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    print(f"读取 {len(rows)} 家公司，开始获取招股书链接...")

    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json",
        "Referer": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
    })
    try:
        s.get("http://www.cninfo.com.cn/new/index", timeout=15)
    except:
        pass

    updated = 0
    for i, row in enumerate(rows):
        code = row.get("stock_code", "")
        name = row.get("company_name", "")

        # 如果已有链接就跳过
        if row.get("prospectus_url") and row.get("prospectus_url").startswith("http"):
            print(f"  [{i+1}/{len(rows)}] {name} ({code}) - 已有链接，跳过")
            continue

        print(f"  [{i+1}/{len(rows)}] {name} ({code}) - 搜索中...")
        params = {
            "searchkey": f"{name} 招股说明书",
            "pageNum": 1, "pageSize": 10,
        }
        try:
            resp = s.post(API_URL, data=params, timeout=30)
            anns = resp.json().get("announcements") or []

            # 找最佳版本
            best = None
            for a in anns:
                t = a.get("announcementTitle", "")
                if "招股说明书" in t and "上市公告书" not in t and "提示性公告" not in t:
                    adj = a.get("adjunctUrl", "")
                    if adj:
                        best = {
                            "title": t,
                            "date": str(a.get("announcementDate", ""))[:10],
                            "url": f"http://static.cninfo.com.cn/{adj}",
                        }
                        # 正式版优先
                        if "注册稿" not in t and "申报稿" not in t and "上会稿" not in t:
                            break

            if best:
                row["prospectus_title"] = best["title"]
                row["prospectus_date"] = best["date"]
                row["prospectus_url"] = best["url"]
                row["source_platform"] = "巨潮资讯"
                updated += 1
                print(f"    -> {best['title'][:60]}")
            else:
                print(f"    -> 未找到招股书链接")

        except Exception as e:
            print(f"    -> 出错: {e}")

        time.sleep(random.uniform(1, 2))

    # 保存更新后的清单
    with open(INPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n完成: 更新了 {updated} 条链接")


if __name__ == "__main__":
    fetch_urls()
