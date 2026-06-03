# -*- coding: utf-8 -*-
"""
cninfo_spider.py — 巨潮资讯网招股说明书批量下载工具
=====================================================
用法：
  python cninfo_spider.py                    # 下载 Week 1 8家公共样本
  python cninfo_spider.py --code 688758      # 下载指定代码
  python cninfo_spider.py --all-kcb           # 搜索科创板全量招股书

依赖：pip install requests
"""
import os, re, sys, json, time, random, argparse, csv
from pathlib import Path

import requests

# 配置
OUTPUT_DIR = Path("PDF_Data")
LOG_DIR = Path("logs")
API_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
PDF_BASE = "http://static.cninfo.com.cn"

# Windows 控制台 UTF-8
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# User-Agent 池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

# Week 1 公共样本
WEEK1_SAMPLES = [
    {"sample_id": "MB001",   "code": "603072", "name": "天和磁材", "board": "主板"},
    {"sample_id": "MB002",   "code": "603418", "name": "友升股份", "board": "主板"},
    {"sample_id": "GEM001",  "code": "301581", "name": "黄山谷捷", "board": "创业板"},
    {"sample_id": "GEM002",  "code": "301563", "name": "云汉芯城", "board": "创业板"},
    {"sample_id": "STAR001", "code": "688758", "name": "赛分科技", "board": "科创板"},
    {"sample_id": "STAR002", "code": "688775", "name": "影石创新", "board": "科创板"},
    {"sample_id": "BSE001",  "code": "920100", "name": "三协电机", "board": "北交所"},
    {"sample_id": "BSE002",  "code": "920091", "name": "大鹏工业", "board": "北交所"},
]


class CninfoSpider:
    """巨潮资讯网爬虫"""

    def __init__(self, output_dir=None):
        self.output_dir = output_dir or OUTPUT_DIR
        self.log_dir = LOG_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.session = self._build_session()
        self.download_log = []

    def _build_session(self):
        s = requests.Session()
        s.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
        })
        try:
            s.get("http://www.cninfo.com.cn/new/index", timeout=15)
        except Exception:
            pass
        return s

    def _rotate_ua(self):
        self.session.headers["User-Agent"] = random.choice(USER_AGENTS)

    def _random_sleep(self, lo=1.0, hi=3.0):
        time.sleep(random.uniform(lo, hi))

    def _valid_pdf(self, path, min_kb=100):
        return path.exists() and path.stat().st_size / 1024 >= min_kb

    def _pick_best(self, results):
        """选择最佳版本：正式稿 > 注册稿 > 申报稿 > 上会稿"""
        def priority(a):
            t = a.get("title", "")
            if "提示性公告" in t or "上市公告书" in t:
                return 99
            if "注册稿" in t: return 2
            if "申报稿" in t: return 3
            if "上会稿" in t: return 4
            return 1
        valid = [r for r in results if "招股说明书" in r.get("title", "")]
        if not valid:
            return {}
        valid.sort(key=priority)
        return valid[0]

    def search(self, company, code="", date_range="2024-01-01~2025-12-31", max_pages=3):
        """搜索招股说明书"""
        all_results = []
        for page in range(1, max_pages + 1):
            params = {
                "searchkey": f"{company} 招股说明书",
                "pageNum": page, "pageSize": 30,
                "seDate": date_range,
            }
            self._rotate_ua()
            try:
                resp = self.session.post(API_URL, data=params, timeout=30)
                data = resp.json()
                anns = data.get("announcements") or []
                if not anns:
                    break
                for a in anns:
                    title = a.get("announcementTitle", "")
                    if "招股说明书" in title:
                        adj = a.get("adjunctUrl", "")
                        all_results.append({
                            "title": title,
                            "pub_date": str(a.get("announcementDate", ""))[:10],
                            "pdf_url": f"{PDF_BASE}/{adj}" if adj else "",
                            "size_kb": a.get("adjunctSize", 0),
                        })
            except Exception as e:
                print(f"    [WARN] 搜索第{page}页出错: {e}")
                continue
            self._random_sleep(0.5, 1.5)
        return all_results

    def download(self, url, filepath, max_retries=3):
        """下载 PDF，带重试和完整性校验"""
        if not url:
            return False
        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                wait = random.uniform(3, 8)
                print(f"    [RETRY] 第{attempt}次, 等待{wait:.0f}秒...")
                time.sleep(wait)
            self._rotate_ua()
            try:
                resp = self.session.get(url, headers={"Referer": "http://www.cninfo.com.cn/"}, timeout=120, stream=True)
                if resp.status_code == 200:
                    with open(filepath, "wb") as f:
                        for chunk in resp.iter_content(8192):
                            f.write(chunk)
                    if self._valid_pdf(filepath):
                        kb = filepath.stat().st_size / 1024
                        print(f"    [OK] {kb:.0f} KB -> {filepath.name}")
                        return True
                    else:
                        kb = filepath.stat().st_size / 1024
                        print(f"    [FAIL] 文件仅{kb:.0f}KB, 疑似反爬, 删除重试")
                        filepath.unlink(missing_ok=True)
                else:
                    print(f"    [FAIL] HTTP {resp.status_code}")
            except Exception as e:
                print(f"    [FAIL] {e}")
        print(f"    [DEAD] 重试{max_retries}次后仍失败")
        return False

    def download_one(self, company, code="", sample_id="", board=""):
        """下载单家公司"""
        sid = f"[{sample_id}] " if sample_id else ""
        print(f"\n{'='*55}")
        print(f"  {sid}{company} ({code}) - {board}")
        print(f"{'='*55}")

        # 去重
        if code:
            existing = list(self.output_dir.glob(f"{code}_*.pdf"))
            if existing and self._valid_pdf(existing[0]):
                kb = existing[0].stat().st_size / 1024
                print(f"  [SKIP] 已存在 ({kb:.0f} KB)")
                self.download_log.append({"company": company, "code": code, "board": board, "status": "skipped", "size_kb": round(kb,1)})
                return True

        # 搜索
        print(f"  [SEARCH] 搜索巨潮资讯...")
        self._random_sleep(1, 2)
        results = self.search(company, code)
        if not results:
            print(f"  [FAIL] 未找到招股说明书")
            self.download_log.append({"company": company, "code": code, "board": board, "status": "fail", "error": "未搜索到"})
            return False

        print(f"  [LIST] 找到 {len(results)} 条")
        best = self._pick_best(results)
        if not best:
            print(f"  [FAIL] 版本筛选无结果")
            self.download_log.append({"company": company, "code": code, "board": board, "status": "fail", "error": "版本筛选失败"})
            return False

        print(f"  [TARGET] [{best['pub_date']}] {best['title'][:80]}")
        print(f"  [WAIT] 正在下载...")
        self._random_sleep(2, 4)

        fname = f"{code}_{company}_招股说明书.pdf"
        fpath = self.output_dir / fname
        ok = self.download(best["pdf_url"], fpath)

        self.download_log.append({
            "company": company, "code": code, "board": board,
            "prospectus_title": best.get("title", ""),
            "prospectus_date": best.get("pub_date", ""),
            "pdf_url": best.get("pdf_url", ""),
            "file": str(fpath) if ok else "",
            "size_kb": round(fpath.stat().st_size/1024,1) if ok else 0,
            "status": "success" if ok else "fail",
        })
        return ok

    def download_batch(self, companies):
        """批量下载"""
        total = len(companies)
        ok = fail = skip = 0
        print(f"\n{'='*55}")
        print(f"  巨潮资讯网招股书批量下载 - {total} 家公司")
        print(f"  输出: {self.output_dir.resolve()}")
        print(f"{'='*55}")

        for i, c in enumerate(companies, 1):
            print(f"\n  > [{i}/{total}]")
            result = self.download_one(c["name"], c.get("code",""), c.get("sample_id",""), c.get("board",""))
            if result:
                ok += 1
            elif self.download_log and self.download_log[-1].get("status") == "skipped":
                skip += 1
            else:
                fail += 1

        print(f"\n\n{'='*55}")
        print(f"  完成: [OK] {ok}  [SKIP] {skip}  [FAIL] {fail}")
        print(f"  目录共 {len(list(self.output_dir.glob('*.pdf')))} 个 PDF")
        print(f"{'='*55}")
        return {"success": ok, "fail": fail, "skipped": skip}

    def save_log(self, name="download_log.csv"):
        if not self.download_log:
            return
        p = self.log_dir / name
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=self.download_log[0].keys())
            w.writeheader(); w.writerows(self.download_log)
        print(f"\n  [LOG] {p}")


def get_kcb_list():
    """搜索科创板招股书列表"""
    print("[SEARCH] 搜索科创板招股书列表...")
    s = requests.Session()
    s.headers.update({"User-Agent": random.choice(USER_AGENTS), "Accept": "application/json"})
    try:
        s.get("http://www.cninfo.com.cn/new/index", timeout=15)
    except Exception:
        pass
    companies = []
    for page in range(1, 15):
        params = {"searchkey": "首次公开发行股票并在科创板上市招股说明书", "pageNum": page, "pageSize": 30, "seDate": "2024-01-01~2025-12-31"}
        try:
            resp = s.post(API_URL, data=params, timeout=30)
            anns = resp.json().get("announcements") or []
            if not anns: break
            for a in anns:
                t = a.get("announcementTitle", "")
                code = a.get("secCode", "")
                name = a.get("secName", "")
                if "招股说明书" in t and "上市公告书" not in t and code.startswith("688"):
                    if not any(c["code"] == code for c in companies):
                        companies.append({"code": code, "name": name, "board": "科创板"})
            print(f"  第{page}页: 累计{len(companies)}家")
            time.sleep(random.uniform(1, 3))
        except Exception as e:
            print(f"  第{page}页出错: {e}")
            continue
    return companies


def main():
    parser = argparse.ArgumentParser(description="巨潮资讯网招股书下载工具")
    parser.add_argument("--code", type=str, default="", help="股票代码(逗号分隔)")
    parser.add_argument("--all-kcb", action="store_true", help="科创板全量")
    parser.add_argument("--output", type=str, default="PDF_Data", help="输出目录")
    args = parser.parse_args()

    spider = CninfoSpider(Path(args.output))

    if args.all_kcb:
        companies = get_kcb_list()
    elif args.code:
        codes = [c.strip() for c in args.code.split(",")]
        companies = [{"code": c, "name": "", "board": ""} for c in codes]
    else:
        companies = WEEK1_SAMPLES
        print("[LIST] Week 1 公共样本 (8家)")

    spider.download_batch(companies)
    spider.save_log()


if __name__ == "__main__":
    main()
