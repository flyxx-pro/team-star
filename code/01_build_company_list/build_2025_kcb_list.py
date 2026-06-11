# -*- coding: utf-8 -*-
"""
Week 2 Step 1: 获取2025年科创板上市公司完整清单
==============================================
搜索巨潮资讯网，找出所有2025年科创板IPO公司的招股说明书
输出：company_lists/week2_2025_company_list.csv
"""
import sys; sys.path.insert(0, '.')
import csv, time, random, requests
from pathlib import Path

# 复用cninfo_spider的API逻辑
API_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
OUTPUT_DIR = Path("company_lists")
OUTPUT_DIR.mkdir(exist_ok=True)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

def get_2025_kcb_list():
    """搜索巨潮资讯，获取2025年科创板上市公司清单"""
    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
    })
    try:
        s.get("http://www.cninfo.com.cn/new/index", timeout=15)
    except:
        pass

    companies = {}
    # 搜索科创板招股说明书（2025年）
    for page in range(1, 30):
        params = {
            "searchkey": "首次公开发行股票并在科创板上市招股说明书",
            "pageNum": page,
            "pageSize": 30,
            "seDate": "2025-01-01~2025-12-31",
        }
        try:
            resp = s.post(API_URL, data=params, timeout=30)
            data = resp.json()
            anns = data.get("announcements") or []
            if not anns:
                break

            for a in anns:
                title = a.get("announcementTitle", "")
                code = a.get("secCode", "")
                name = a.get("secName", "")
                date = str(a.get("announcementDate", ""))[:10]
                adj_url = a.get("adjunctUrl", "")

                # 只保留科创板(688)的正式招股说明书
                if (code.startswith("688")
                    and "招股说明书" in title
                    and "上市公告书" not in title
                    and "提示性公告" not in title
                    and "问询回复" not in title
                    and "审核问询" not in title):

                    if code not in companies:
                        companies[code] = {
                            "stock_code": code,
                            "company_name": name,
                            "exchange": "SSE",
                            "board": "科创板",
                            "prospectus_title": title,
                            "prospectus_date": date,
                            "prospectus_url": f"http://static.cninfo.com.cn/{adj_url}" if adj_url else "",
                            "source_platform": "巨潮资讯",
                        }

            print(f"  第{page}页: 累计{len(companies)}家科创板公司")
            time.sleep(random.uniform(1, 2))

        except Exception as e:
            print(f"  第{page}页出错: {e}")
            continue

    return list(companies.values())


def main():
    print("=" * 60)
    print("  Week 2: 构建2025年科创板企业清单")
    print("=" * 60)

    companies = get_2025_kcb_list()
    print(f"\n共找到 {len(companies)} 家2025年科创板上市公司")

    # 按股票代码排序
    companies.sort(key=lambda x: x["stock_code"])

    # 保存CSV
    csv_path = OUTPUT_DIR / "week2_2025_company_list.csv"
    if companies:
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=companies[0].keys())
            writer.writeheader()
            writer.writerows(companies)
        print(f"已保存: {csv_path}")

    # 打印列表
    print(f"\n{"代码":<8} {"公司简称":<16} {"招股书日期"}")
    print("-" * 40)
    for c in companies:
        print(f"{c['stock_code']:<8} {c['company_name']:<16} {c['prospectus_date']}")


if __name__ == "__main__":
    main()
