# Week 3：全自动化流水线与数据质量攻坚

**小组**: C组（科创板） | **成员**: 刘宇轩、苏宇垚 | **日期**: 2026-06-18

---

## 1. 本周目标

（1）补齐第二周缺失的三联锻造；（2）消除所有公司的 null 值；（3）建立目录定位→精准提取的标准化流程；（4）完成人工检查并修正数据；（5）补全全部交付件。

## 2. 最终成果

| 公司 | 认缴 | 存量 | 股权转让 | null | t0 | 源标记 |
|------|------|------|---------|------|-----|--------|
| 友升股份 | 13 | 28 | 5 | 0 | 有 | teacher_gold |
| 云汉芯城 | 15 | 87 | 8 | 0 | 有 | auto |
| 赛分科技 | 15 | 184 | 2 | 0 | 有 | manual_gold+auto |
| 影石创新 | 2 | 65 | 1 | 0 | 有 | manual_gold+auto |
| 三协电机 | 3 | 37 | 10 | 0 | 有 | toc_located |
| 黄山谷捷 | 3 | 24 | 3 | 0 | 有 | auto |
| 三联锻造 | 1 | 2 | 3 | 0 | 有 | toc_located |
| 星图测控 | 3 | 11 | 2 | 0 | 有 | auto |
| **合计** | **55** | **438** | **34** | **0** | **8/8** | |

## 3. 关键技术突破

### 3.1 目录定位法（TOC-based extraction）
- 先解析第10页目录，提取"第四节 发行人基本情况→第30页"
- 精准定位到33-47页（历史沿革+股本变化+股权转让）
- 三协电机存量从1条暴增至37条

### 3.2 关键词密度评分
- 75K字符压缩到48K，信息密度提升10倍
- 影石创新存量从2条提升到40条

### 3.3 分轮调用避免JSON截断
- 数据量大的公司（赛分184条），认缴和存量分开两次API调用
- max_tokens从16384增至24576

### 3.4 人工检查确认的修正
- 黄山谷捷：出资额=认购数量，认购金额PDF未披露（有限责任公司特点）
- 赛分第59页：是股权存量表，不是认购明细
- 影石创新：设立和股改不算增资事件
- 三协电机：增资/股权转让在43-47页，不在53页

## 4. 遗留问题

- 黄山谷捷认购金额、赛分2021-11-10认购明细：PDF未披露对应数值，null是正确的
- 三协电机部分股权转让尚未独立拆分为share_transfer_flow

## 5. 技术路径总结

见 `source_notes/technical_summary.md`——完整九步流水线、常见问题解法、各板块披露特点、扩展检查清单。

## 6. 交付件清单

| 文件 | 状态 |
|------|------|
| outputs/week2_jsonl/ (8家) | 最终版 |
| outputs/week2_excel/ (8家三表) | 最终版 |
| manual_gold/ (24 JSONL + review_queue) | 同步 |
| evaluation/ (event_summary + row_match + error_analysis) | 完整 |
| prompts/ (system_prompt + user_prompt_template + prompt_sensitivity) | 完整 |
| schemas/extraction_models.py | Pydantic v2 |
| scripts/ (extract + validate + convert) | 可运行 |
| logs/ (download + locate + extraction + cross_check) | 完整 |
| review/week3_intra_group_review.csv | 完成 |
| annotations_pdf/ (3张截图) | 友升p43-45 |
| presentation/ (PPT + outline) | 10页 |
| source_notes/technical_summary.md | 新增 |
| weekly_reports/week3.md | 本文件 |
