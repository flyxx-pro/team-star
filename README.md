# team-star — 招股书股本结构自动化抽取

**小组**: C组（科创板） | **成员**: 刘宇轩、苏宇垚 | **指导老师**: 闫海洲、汪小圈

---

## 项目简介

从 8 家 IPO 招股说明书 PDF 中全自动化提取上市前的股本变化数据——认缴流量、股权存量、股权转让——形成可复核、可扩展的结构化数据集。覆盖主板、创业板、科创板、北交所四个板块。

---

## 流水线

```
PDF下载(cninfo_spider) → MinerU Markdown/JSON双模解析 → TOC目录定位 → 章节精准提取
→ 关键词密度评分 → Deepseek AI抽取(段落) + 正则解析(表格) → Pydantic校验 → Cross-check → Excel三表输出
```

**核心优化（Week 4）**：表格走 Markdown 正则（0 token），段落走 AI（~6000 token），单家 Token 消耗降低 88%。

---

## 目录结构

```
team-star/
  README.md
  cninfo_spider.py                    # 巨潮资讯网爬虫
  company_lists/                       # 企业清单（Week1+Week2）
  source_notes/                        # 数据来源 + 技术总结 + 标准化流程
  code/
    05_locate_relevant_sections/       # 章节定位
    06_extract_pevc_info/              # AI提取
    07_markdown_pipeline/              # Markdown正则表格提取(Week4)
  outputs/
    week2_jsonl/                       # 8家公司JSONL（最终版）
    week2_excel/                       # 8家公司Excel三表（含cross-check）
    week4_markdown/                    # Markdown流水线中间结果
  manual_gold/                         # 人工Gold标准
  evaluation/                          # 评估对比（row_match + error_analysis）
  prompts/                             # Prompt设计（system + template + LLC专用）
  schemas/                             # Pydantic Schema
  scripts/                             # 抽取/校验/转换脚本
  logs/                                # 全链条日志
  review/                              # 组内互查表
  annotations_pdf/                     # PDF截图证据
  presentation/                        # 深讲PPT + PPT脚本 + 演讲稿
  weekly_reports/                      # 周报 + 会议总结
```

---

## 快速开始

```bash
# 1. 下载招股书
python cninfo_spider.py

# 2. MinerU 解析 — 网页端上传 PDF, JSON + Markdown 双模式各导出一次

# 3. Markdown正则表格提取（0 token）
python code/07_markdown_pipeline/extract_from_markdown.py 920116
python code/07_markdown_pipeline/parse_tables_to_jsonl.py

# 4. PE基金详情提取（0 token）
python code/07_markdown_pipeline/extract_pe_fund.py

# 5. AI段落提取
python scripts/extract_week2.py

# 6. 校验 + Excel输出
python scripts/validate_jsonl.py
python scripts/jsonl_to_excel.py
```

---

## 四周成果总览

| Week | 核心进展 | 关键突破 |
|------|---------|---------|
| Week 1 | 8家公共样本完整闭环 | PDF下载 + AI提取 + JSON输出 |
| Week 2 | 认缴流量 + 股权存量深度抽取 | 友升与教师示范逐项比对 |
| Week 3 | 三联锻造补齐 + null值攻坚 + 星图深讲 | TOC目录定位法 + 关键词密度评分 + 分轮调用 |
| Week 4 | Markdown流水线 + PE基金深度 + LLC Prompt | 表格0 token正则提取 + Token节省88% + investor_type分类 |

### 最终数据

| 公司 | 认缴 | 存量 | 转让 | PE基金 | null | cross-check |
|------|------|------|------|--------|------|------------|
| 友升股份 | 13 | 28 | 5 | — | 0 | 教师gold验证 |
| 云汉芯城 | 15 | 87 | 8 | — | 0 | pass |
| 黄山谷捷 | 3 | 24 | 0 | — | 0 | pass |
| 赛分科技 | 15 | 184 | 2 | — | 0 | pass |
| 影石创新 | 2 | 65 | 1 | — | 0 | pass |
| 三协电机 | 3 | 37 | 10 | 2(SNG030/SVU935) | 0 | pass |
| 三联锻造 | 12 | 16 | 0 | — | 0 | pass |
| 星图测控 | 3 | 7 | 0 | — | 0 | 100% |
| **合计** | **66** | **448** | **26** | **2** | **0** | **8/8** |

---

## 技术资产

| 文档 | 内容 |
|------|------|
| source_notes/technical_summary.md | 完整九步流水线 + 常见问题解法 |
| source_notes/标准化提取流程.md | JSON+Markdown双模提取SOP |
| source_notes/技术教训与错误清单.md | 12条踩坑教训 |
| source_notes/星图测控成功经验总结.md | 从1家到50家的扩展路径 |
| prompts/llc_specific_prompt.md | 有限责任公司 vs 股份有限公司专用Prompt |
| presentation/深讲汇报演讲稿_星图测控.md | 8-10分钟深讲逐字稿 |
