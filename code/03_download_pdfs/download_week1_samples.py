# -*- coding: utf-8 -*-
"""
Week 1: 下载8家公共样本招股说明书
从巨潮资讯网 (cninfo.com.cn) 搜索并下载正式招股说明书 PDF
"""
import os
import re
import json
import time
import requests
from pathlib import Path
from urllib.parse import quote

# 8家公共样本
SAMPLES = {
    "MB001": {"code": "603072", "name": "天和磁材", "board": "主板", "exchange": "SSE"},
    "MB002": {"code": "603418", "name": "友升股份", "board": "主板", "exchange": "SSE"},
    "GEM001": {"code": "301581", "name": "黄山谷捷", "board": "创业板", "exchange": "SZSE"},
    "GEM002": {"code": "301563", "name": "云汉芯城", "board": "创业板", "exchange": "SZSE"},
    "STAR001": {"code": "688758", "name": "赛分科技", "board": "科创板", "exchange": "SSE"},
    "STAR002": {"code": "688775", "name": "影石创新", "board": "科创板", "exchange": "SSE"},
    "BSE001": {"code": "920100", "name": "三协电机", "board": "北交所", "exchange": "BSE"},
    "BSE002": {"code": "920091", "name": "大鹏工业", "board": "北交所", "exchange": "BSE"},
}

# 输出目录
OUTPUT_DIR = Path("downloads/prospectus_pdfs")
LOG_DIR = Path("logs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/json",
}


def search_cninfo(stock_code: str, keyword: str = "招股说明书",
                  max_pages: int = 5) -> list:
    """
    在巨潮资讯网搜索指定股票代码的公告
    返回 [(title, pdf_url, pub_date), ...] 列表
    """
    results = []
    search_url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"

    for page in range(1, max_pages + 1):
        params = {
            "pageNum": page,
            "pageSize": 30,
            "column": "szse",
            "tabName": "fulltext",
            "plate": "",
            "stock": f"{stock_code},ORGTEST",
            "searchkey": "",
            "secid": "",
            "category": "",
            "trade": "",
            "seDate": "2024-01-01~2025-12-31",
            "sortName": "declaredate",
            "sortType": "desc",
        }
        try:
            resp = requests.post(search_url, data=params,
                                headers=HEADERS, timeout=30)
            data = resp.json()
            announcements = data.get("announcements") or []
            if not announcements:
                break

            for ann in announcements:
                title = ann.get("announcementTitle", "")
                if keyword in title:
                    adjunct_url = ann.get("adjunctUrl", "")
                    pub_date = ann.get("announcementDate", "")
                    # 构造 PDF 下载链接
                    if adjunct_url:
                        # 去掉相对路径开头的 /
                        if adjunct_url.startswith("/"):
                            adjunct_url = adjunct_url[1:]
                        pdf_url = f"http://static.cninfo.com.cn/{adjunct_url}"
                    else:
                        pdf_url = ""

                    results.append({
                        "title": title.strip(),
                        "pdf_url": pdf_url,
                        "pub_date": str(pub_date)[:10] if pub_date else "",
                        "adjunct_url": adjunct_url,
                    })
        except Exception as e:
            print(f"  [搜索] 第{page}页出错: {e}")
            continue

        time.sleep(0.5)  # 礼貌等待

    return results


def is_target_prospectus(title: str) -> bool:
    """判断是否为正式招股说明书（排除申报稿、上会稿、上市公告书等）"""
    # 排除规则
    exclude_keywords = [
        "上市公告书", "提示性公告", "发行公告", "问询回复",
        "审核问询", "补充法律意见", "审计报告", "发行保荐书",
        "上市保荐书", "法律意见书", "更正", "修订",
        "摘要", "预案", "结果公告",
    ]
    for kw in exclude_keywords:
        if kw in title:
            return False

    # 必须是招股说明书
    if "招股说明书" not in title:
        return False

    return True


def select_best_version(announcements: list) -> dict:
    """
    从搜索结果中选择最佳版本
    优先级：正式稿 > 注册稿 > 申报稿 > 上会稿
    """
    # 按版本优先级排序
    version_order = {
        "招股说明书": 0,        # 正式稿一般直接叫"招股说明书"
        "注册稿": 1,
        "申报稿": 2,
        "上会稿": 3,
        "招股意向书": 4,
    }

    # 先筛出招股说明书
    prospectuses = [a for a in announcements
                    if is_target_prospectus(a.get("title", ""))
                    or "招股说明书" in a.get("title", "")]

    if not prospectuses:
        # 放宽条件，找所有含"招股说明书"的
        prospectuses = [a for a in announcements
                        if "招股说明书" in a.get("title", "")]
    if not prospectuses:
        return {}

    # 按版本优先级排序
    def sort_key(a):
        title = a.get("title", "")
        for version, order in version_order.items():
            if version in title:
                return order
        return 99

    prospectuses.sort(key=sort_key)

    # 返回第一个（最高优先级）
    best = prospectuses[0]
    return best


def download_pdf(url: str, filepath: Path) -> bool:
    """下载 PDF 文件"""
    if not url:
        return False

    try:
        resp = requests.get(url, headers=HEADERS, timeout=120,
                           stream=True)
        if resp.status_code == 200:
            # 检查是否是真正的 PDF
            content_type = resp.headers.get("Content-Type", "")
            if "pdf" not in content_type.lower() and "octet-stream" not in content_type.lower():
                # 有些链接可能不是直接 PDF
                pass

            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            # 验证文件大小
            size_kb = filepath.stat().st_size / 1024
            if size_kb < 50:  # 小于50KB可能不是真正的PDF
                print(f"    警告：文件仅 {size_kb:.0f}KB，可能下载失败")
                return False

            print(f"    成功：{size_kb:.0f} KB")
            return True
        else:
            print(f"    HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"    下载失败：{e}")
        return False


def main():
    log_entries = []

    for sample_id, info in SAMPLES.items():
        code = info["code"]
        name = info["name"]
        board = info["board"]

        print(f"\n{'='*60}")
        print(f"[{sample_id}] {name} ({code}) - {board}")
        print(f"{'='*60}")

        # 1. 搜索巨潮资讯
        print("  搜索巨潮资讯...")
        announcements = search_cninfo(code, keyword="招股说明书")

        if not announcements:
            print("  未找到招股说明书相关公告！")
            log_entries.append({
                "sample_id": sample_id, "company": name,
                "stock_code": code, "board": board,
                "download_status": "fail",
                "error": "未搜索到招股说明书",
            })
            continue

        print(f"  找到 {len(announcements)} 条相关公告：")
        for ann in announcements[:5]:
            print(f"    [{ann['pub_date']}] {ann['title'][:80]}")

        # 2. 选择最佳版本
        best = select_best_version(announcements)
        if not best:
            print("  无法确定目标招股说明书版本！")
            log_entries.append({
                "sample_id": sample_id, "company": name,
                "stock_code": code, "board": board,
                "download_status": "fail",
                "error": "版本筛选失败",
            })
            continue

        print(f"\n  已选择：{best['title'][:100]}")
        print(f"  发布日期：{best.get('pub_date', '未知')}")

        # 3. 下载
        pdf_url = best.get("pdf_url", "")
        if not pdf_url:
            print("  PDF 链接为空！")
            log_entries.append({
                "sample_id": sample_id, "company": name,
                "stock_code": code, "board": board,
                "download_status": "fail",
                "error": "PDF链接为空",
            })
            continue

        # 文件名格式：sample_id_股票代码_公司简称_招股说明书.pdf
        filename = f"{sample_id}_{code}_{name}_招股说明书.pdf"
        filepath = OUTPUT_DIR / filename
        print(f"  正在下载：{pdf_url[:100]}...")
        success = download_pdf(pdf_url, filepath)

        log_entries.append({
            "sample_id": sample_id,
            "company": name,
            "stock_code": code,
            "board": board,
            "prospectus_title": best.get("title", ""),
            "prospectus_date": best.get("pub_date", ""),
            "pdf_url": pdf_url,
            "file_path": str(filepath) if success else "",
            "download_status": "success" if success else "fail",
        })

        time.sleep(1)  # 请求间隔

    # 4. 输出日志
    print(f"\n\n{'='*60}")
    print("下载完成汇总")
    print(f"{'='*60}")

    success_count = sum(1 for l in log_entries
                        if l.get("download_status") == "success")
    fail_count = len(log_entries) - success_count
    print(f"  成功：{success_count}/{len(log_entries)}")
    print(f"  失败：{fail_count}/{len(log_entries)}")

    # 保存日志
    import csv
    log_path = LOG_DIR / "download_log.csv"
    if log_entries:
        with open(log_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=log_entries[0].keys())
            writer.writeheader()
            writer.writerows(log_entries)
        print(f"\n  日志已保存：{log_path}")

    # 打印失败的
    if fail_count > 0:
        print(f"\n  下载失败的样本：")
        for l in log_entries:
            if l.get("download_status") == "fail":
                print(f"    {l['sample_id']} {l['company']} ({l['stock_code']}) - "
                      f"{l.get('error', '未知错误')}")


if __name__ == "__main__":
    main()