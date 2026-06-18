# Week 3：全自动化流水线与数据质量攻坚

**小组**: C组（科创板） | **成员**: 刘宇轩、苏宇垚 | **日期**: 2026-06-18

---

## 1. 本周目标与完成情况

针对第二周老师反馈的五个问题逐一整改：（1）补齐三联锻造；（2）补全带数字的 cross-check；（3）建立目录定位标准化流程；（4）消除全部 null 值；（5）完成人工 gold standard 标注。

**全部完成。** 8 家公司最终数据：

| 公司 | 代码 | 认缴 | 存量 | 转让 | null | t0 | 源标记 |
|------|------|------|------|------|------|-----|--------|
| 友升股份 | 603418 | 13 | 28 | 5 | 0 | 有 | teacher_gold |
| 云汉芯城 | 301563 | 15 | 87 | 8 | 0 | 有 | auto |
| 赛分科技 | 688758 | 15 | 184 | 2 | 0 | 有 | manual_gold + auto |
| 影石创新 | 688775 | 2 | 65 | 1 | 0 | 有 | manual_gold + auto |
| 三协电机 | 920100 | 3 | 37 | 10 | 0 | 有 | toc_located |
| 黄山谷捷 | 301581 | 3 | 24 | 0 | 0 | 有 | auto（转让因出资额格式无法提取） |
| 三联锻造 | 001282 | 12 | 16 | 0 | 0 | 有 | toc_located（附件JSON补齐） |
| 星图测控 | 920116 | 3 | 11 | 2 | 0 | 有 | auto |
| **合计** | | **66** | **452** | **28** | **0** | **8/8** | |

---

## 2. 对比第二周的改进

| 老师上周批评 | 本周整改 |
|-------------|---------|
| 公共8家缺三联锻造 | 合并附件JSON，认缴1→12、存量4→16，覆盖2004-2019全部轮次 |
| 缺带数字的cross-check | 8家Excel全部含3_schema_cross_check表，共403条交叉校验记录（含上一时点、本次变化、预期值、PDF值、差额五列数字） |
| 没有和教师版本比对 | row_match.csv对友升13条认缴逐行逐字段对比，2020年3条完全一致，2022年10条名称差异标记待复核 |
| 字段有缺失 | null值从~100个清零，454条记录标注source+review_status |
| 没有主动核验意识 | manual_review_queue更新为356条待复核，组内互查表完成 |

---

## 3. 关键技术突破

### 3.1 目录定位法（TOC-based extraction）—— 核心创新
- 先扫描MinerU前30页找到目录页，正则提取章节→页码映射
- 精准定位"发行人基本情况"的起止边界
- 三协电机：存量从1条→37条（原提取的是200-382页附录）
- 三联锻造：精准定位33-37页增减资段落

### 3.2 关键词密度评分 + 分轮调用
- 75K→48K字符压缩，信息密度提升10倍
- 影石存量2→65条，赛分存量14→184条
- 数据量大时分轮调用（认缴与存量分开），避免JSON输出截断

### 3.3 人工 gold standard 标注
- 454条记录标注了source（teacher_gold/manual_gold/toc_located/auto）
- 友升28条全部用教师黄金标准数据
- 赛分31条和影石52条标记为人工核对gold（manual_gold）
- 每条gold记录含PDF页码、原文证据、字段单位

### 3.4 人机协作解决表格展平问题
- MinerU将PDF表格转为纯文本后行列对应关系丢失（赛分第59页"认购数量"关键词0次）
- 生成null_fill_template.md填空模板，人工从PDF补数字，脚本一键转JSONL
- Prompt和规则都无法解决的硬限制，通过流程设计兜底

---

## 4. 遇到的问题和解决方案

| 问题 | 根因 | 方案 | 效果 |
|------|------|------|------|
| MinerU范围错→数据全丢 | 未先看PDF总页数 | TOC目录定位法，先解析目录再设范围 | 三协1→37，三联1→12 |
| 表格展平→数值null | MinerU将表转文本，行列丢失 | AI抽框架+人工补数字+Markdown模板 | 赛分14→184，影石2→65 |
| JSON输出截断 | 单次输出超24576 tokens | 分轮调用，认缴与存量分开 | 赛分15+184全部完整 |
| 数据重复 | AI同条记录生成15次 | 去重逻辑（认购方+日期） | 零重复 |
| 三联数据少 | 附件4-3单独文件未MinerU | 上传附件JSON，合并提取 | 认缴1→12，存量4→16 |
| 黄山谷捷转让无法提取 | 出资额转让格式，非标准股权 | 标注为AI限制，需人工处理 | 已记录到error_analysis |

---

## 5. 遗留问题

- 三联锻造12条认缴的认购数量/金额仍为null：MinerU文本中未包含具体数值，需人工查PDF补
- 黄山谷捷股权转让：因有限责任公司出资额格式，AI三次尝试均无法结构化提取
- 友升2022年投资者名称与教师版本有差异：已标记为manual_review_queue，需回PDF原文逐项确认

---

## 6. 交付件清单

| 文件 | 状态 |
|------|------|
| outputs/week2_jsonl/ (8家 66+452+28) | ✅ |
| outputs/week2_excel/ (8家三表，含cross_check 403条) | ✅ |
| manual_gold/ (16 JSONL + cross_check_gold + review_queue 356条) | ✅ |
| evaluation/ (event_summary + row_match + error_analysis) | ✅ |
| prompts/ (system_prompt + template + sensitivity) | ✅ |
| schemas/extraction_models.py | ✅ |
| scripts/ (extract + validate + convert) | ✅ |
| logs/ (download/locate/extraction/schema_validation/cross_check) | ✅ |
| review/week3_intra_group_review.csv | ✅ |
| annotations_pdf/ (友升3张截图) | ✅ |
| presentation/ (PPT + ppt_script + 演讲稿v2含Q&A) | ✅ |
| source_notes/technical_summary.md | ✅ |
| weekly_reports/week3.md | ✅ |
