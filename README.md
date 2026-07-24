# team-star — 招股书股本结构自动化抽取

**小组**: C组（科创板） | **成员**: 刘宇轩、苏宇垚 | **指导老师**: 闫海洲、汪小圈

---

## Week 6 完成状态

### 完成项

| 任务 | 状态 | 说明 |
|------|------|------|
| Gold/Auto/Final 分离 | Done | manual_gold/, auto_output/, final/ 三个独立目录 |
| rowspan/colspan 展开 | Done | table_parser.py 已验证（赛分 2021-04 rowspan=4, 2021-11 rowspan=10） |
| Cross-check 区间匹配 | Done | 逐事件区间匹配，每对前后快照只连接该区间内的认购事件 |
| 逐股东核对 | Done | 全量逐股东 cross_check |
| 统一流水线 | Done | pipeline/unified_pipeline.py（0 token 正则 + rowspan 展开） |
| Auto-vs-Gold 对比 | Done | pipeline/validate_and_compare.py（TP/FP/FN + Precision/Recall/F1） |
| 融资分析报告 | Done | report/week6_report.md |
| 8家公司齐全 | Done | 8/8 Gold + Auto + Final + Excel |

### 已知问题

1. Auto 正则提取对非标准表格结构的覆盖率有限，依赖人工复核补充
2. 部分公司 Gold 的时点标签使用描述性文本（如"报告期初 | 设立时"），区间匹配需人工标注
3. 赛分科技 2021-12 第三次增资表仅 1 个投资者，rowspan 不适用但需要确认金额

---

## 统一运行命令

```bash
# Step 1: 运行全量流水线（0 token 正则提取 + rowspan展开 + cross-check）
py pipeline/unified_pipeline.py

# Step 2: 运行验证和Auto-vs-Gold对比
py pipeline/validate_and_compare.py

# Step 3: 测试rowspan/colspan展开
py pipeline/table_parser.py
```

**输入**: MinerU_Output/*.md（8家公司的Markdown解析文件） + manual_gold/*_gold.jsonl（人工Gold标准）

**输出**: auto_output/*_auto.jsonl（未经人工修改的Auto三表）、validation/*_validation.json（cross-check + Auto-vs-Gold对比）、validation/pipeline_summary.csv

**人工介入位置**: manual_gold/（人工Gold）、final/（人工及组内复核后的三表和Excel）

---

## 目录结构

```
team-star/
├── README.md                          # 本文件
├── requirements.txt                   # 依赖版本
├── manual_gold/                       # 人工Gold标准（不要求代码生成）
│   ├── *_gold.jsonl                   # 8家公司合并Gold（含三表）
│   ├── *_subscription_flow_gold.jsonl # 分表Gold
│   ├── *_equity_snapshot_gold.jsonl
│   └── *_share_transfer_flow_gold.jsonl
├── auto_output/                       # 未人工修改的Auto三表
│   └── *_auto.jsonl
├── final/                             # 人工及组内复核后的三表和Excel
│   ├── *_final.jsonl
│   └── *_三表抽取.xlsx
├── pipeline/                          # 完整自动提取代码和统一入口
│   ├── table_parser.py                # rowspan/colspan展开 + HTML表格解析
│   ├── unified_pipeline.py            # 统一流水线（正则0 token + cross-check）
│   └── validate_and_compare.py        # Auto-vs-Gold对比 + Cross-check
├── validation/                        # schema、Cross-check、Auto-vs-Gold
│   ├── *_validation.json              # 逐公司验证结果
│   ├── auto_vs_gold_summary.csv       # 汇总对比
│   └── pipeline_summary.csv           # 流水线输出汇总
├── report/                            # 上市前融资分析报告
│   └── week6_report.md
├── review/                            # 组内互查
│   └── week3_intra_group_review.csv
├── prompts/                           # Prompt、模型参数和调用记录
│   ├── system_prompt.md
│   ├── user_prompt_template.md
│   ├── llc_specific_prompt.md
│   └── prompt_sensitivity.md
├── MinerU_Output/                     # MinerU Markdown解析输出（8家）
├── code/                              # 历史代码（Week1-5）
│   ├── 07_markdown_pipeline/
│   └── 08_week5_batch/
├── source_notes/                      # 技术总结与教训
├── weekly_reports/                    # 周报
└── logs/                              # 运行记录
```

---

## 流水线说明

```
MinerU Markdown → table_parser(rowspan/colspan展开) → 正则表格提取(0 token)
→ subscription_flow + equity_snapshot → Cross-check(逐事件区间匹配)
→ Auto-vs-Gold(TP/FP/FN) → Excel三表输出
```

**核心改进（Week 6）**：
- rowspan/colspan 展开：修复赛分科技 2021-04 (rowspan=4) 和 2021-11 (rowspan=10) 价格列偏移
- Cross-check 区间匹配：每对前后快照只连接该区间内的认购事件，不再把所有认购合计套用
- Gold/Auto/Final 分离：三目录独立，每条记录保留 source 字段

---

## 8家公司数据总览

| 公司 | 认缴 | 存量 | 转让 | 关键投资者 |
|------|------|------|------|-----------|
| 友升股份 | 13 | 28 | 5 | 达晨系、金浦系、杉晖 |
| 云汉芯城 | 15 | 87 | 8 | 多轮VC/产业资本 |
| 黄山谷捷 | 3 | 24 | 0 | 产业背景 |
| 赛分科技 | 15 | 184 | 3 | 高瓴、国药、夏尔巴、源峰 |
| 影石创新 | 2 | 65 | 1 | 早期VC |
| 三协电机 | 3 | 37 | 10 | 产业背景 |
| 三联锻造 | 12 | 16 | 0 | 产业资本 |
| 星图测控 | 3 | 7 | 0 | 中科星图控股、幸福二期 |
| **合计** | **66** | **448** | **27** | |

---

## 技术资产

| 文档 | 内容 |
|------|------|
| source_notes/technical_summary.md | 完整九步流水线 + 常见问题解法 |
| source_notes/技术教训与错误清单.md | rowspan/colspan等13条踩坑教训 |
| source_notes/标准化提取流程.md | JSON+Markdown双模提取SOP |
| source_notes/50家扩展检查清单.md | 从8家到50家的扩展路径 |
| report/week6_report.md | 上市前融资分析报告 |
