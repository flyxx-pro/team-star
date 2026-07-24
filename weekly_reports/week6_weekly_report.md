# 第六周周报 — 刘宇轩

> 2026-07-22 至 2026-07-24

---

## 一、本周完成任务

### 1. PostgreSQL 数据库存储

- 本地安装 PostgreSQL 17，创建 `student` 数据库
- 建表 `lyx_subscription_flow`、`lyx_equity_snapshot`、`lyx_share_transfer_flow`
- 导入 8 家公司 598 条 Gold 数据
- 同步上传至远程服务器 `175.27.211.229:5433`

### 2. 小组互查（第三组）

#### 2.1 与霍泓锟互查

- 8 家公司三表对比：认缴一致率 2/8，快照一致率 0/8
- 代码级根因分析：AI 自动分类转让/增资不分 + rowspan 展开后列偏移
- 输出：`给霍泓锟/` 代码参考包（table_parser.py + 4 个示范 Excel + README）

**关键发现**：
| 差异 | 根因 | 谁正确 |
|------|------|:--:|
| 云汉 35 vs 15 | AI 把转让/ESOP 误分为认缴 | 刘 |
| 三协 17 vs 3 | AI 把 10 次转让误分为增资 | 刘 |
| 赛分 10 vs 15 | rowspan 展开后列偏移 + 漏段落 | 刘 |

#### 2.2 与陈雨昂互查

- 8 家公司逐条对比、逐差异 PDF 原文确认
- 裁决：陈占优 4 家，刘占优 1 家（赛分），一致 2 家，待核实 1 家
- 输出：`review/互查裁决报告_刘宇轩vs陈雨昂.md`、`review/互查反馈报告_陈雨昂.md`

**裁决结果**：
| 公司 | 以谁为准 | 关键原因 |
|------|:--:|------|
| 三联锻造 | 陈 | 正文数据源比股权变化图可靠 |
| 友升股份 | 陈 | 4 位精度、CC 详尽、工商全称 |
| 云汉芯城 | 陈 | 35 条覆盖全部增资轮次 |
| 赛分科技 | **刘** | rowspan 修复 + 段落提取，陈版单位/轮次错误 |
| 影石创新 | 一致 | 三表完全一致 |

### 3. 数据修正（基于互查反馈）

| # | 问题 | 修正 |
|---|------|------|
| 1 | 云汉芯城 t0-t5 自动记录持股数偏误 | 过滤 auto 源，仅用合并 Gold |
| 2 | 黄山谷捷认购金额缺失 | 认购数量×价格 = 金额，3 条全部补填 |
| 3 | 星图测控缺失 2016 设立期 | 补充 3 条设立出资记录 |
| 4 | 精度统一为 4 位小数 | V5 重建全部 Excel |
| 5 | Cross-check 增强 | 认购价格验算 + 各时点持股比例合计 |

### 4. 论文评述

- 阅读并翻译 "Venture Capital and the Financialization of Chinese Firms"
- 输出：`weekly_reports/VC与企业金融化_中文翻译.docx` + `paper_review_vc_financialization.md`

---

## 二、交付文件清单

| 类别 | 文件 | 状态 |
|------|------|:--:|
| 三表 Excel | `final/*_三表抽取.xlsx` (8 份) | ✅ |
| Gold 数据 | `manual_gold/*_gold.jsonl` + `*_subscription_flow_gold.jsonl` 等 | ✅ |
| Auto 数据 | `auto_output/*_auto.jsonl` (8 份) | ✅ |
| 数据库 SQL | `pipeline/lyx_import.sql` | ✅ |
| 互查报告 | `review/互查反馈报告_陈雨昂.md`、`互查裁决报告_刘宇轩vs陈雨昂.md`、`互查报告_刘宇轩vs霍泓锟.md`、`互查报告_根因分析.md` | ✅ |
| 论文 | `weekly_reports/VC与企业金融化_中文翻译.docx`、`paper_review_vc_financialization.md` | ✅ |
| 代码 | `pipeline/rebuild_final_excel_v5.py`、`pipeline/compare_with_huo.py` 等 | ✅ |
| 周报 | `weekly_reports/week6_weekly_report.md` | ✅ |

---

## 三、经验与反思

### 学到的东西

1. **Rowspan 是表格提取中最容易出错的点**。赛分科技 2021-11 轮 rowspan=10，不展开就丢 9 条记录。霍泓锟和陈雨昂都受此影响。
2. **AI 自动分类不可靠**。霍泓锟靠 AI 的 `record_type` 分类，把云汉芯城的转让和 ESOP 都归入认缴。规则过滤 + 人工复核是更好的策略。
3. **互查比自己检查有效得多**。陈雨昂发现了我们自己没注意到的云汉芯城快照列错位问题，我们也发现了他的赛分单位错误。
4. **数据源选择影响可靠性**。三联锻造用正文 vs 股权变化图，同一轮增资的股东分配比例不同，正文更可靠。

### 待改进

- 云汉芯城认缴仅 15 条，遗漏 2009-2015 早期 5 轮增资（陈版有 35 条）—— 但这是 Gold 文件本身的覆盖范围问题，非提取错误
- 三协电机二批增资日期和总量与陈版不一致，需 PDF 原文裁决

---

## 四、GitHub 提交记录

- `22ed6b9` Week6: Gold/Auto/Final separation, rowspan expansion function verified
- 本次提交：数据修正 + 互查报告 + 论文评述 + PostgreSQL 导入
