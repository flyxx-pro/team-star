# Week 3：自动化流程闭环与Cross-check补全

**小组**: C组（科创板） | **成员**: 刘宇轩、苏宇垚 | **日期**: 2026-06-15

## 1. 本周目标

按照第二周反馈和第三周要求：(1)补齐三联锻造；(2)补全带数字的cross-check（Excel第三表）；(3)分离人工gold与自动输出；(4)提交error_analysis和prompt说明。

## 2. 公共样本处理情况

| 代码 | 公司 | 认缴流量 | 股权存量 | t0 | Schema | Cross-check | 备注 |
|------|------|---------|---------|-----|--------|-------------|------|
| 001282 | 三联锻造 | 1条 | 23条 | 有 | PASS | PASS | 第一份MinerU JSON用错导致提取失败，切换到正确版本后通过 |
| 603418 | 友升股份 | 13条 | 32条 | 有 | PASS | PASS | 与教师示范Excel逐项比对：2020年轮次完全一致 |
| 301581 | 黄山谷捷 | 3条 | 24条 | 有 | PASS | PASS | — |
| 301563 | 云汉芯城 | 15条 | 87条 | 有 | PASS | PASS | — |
| 688758 | 赛分科技 | 11条 | 14条 | 有 | PASS | PASS | — |
| 688775 | 影石创新 | 2条 | 2条 | 有 | PASS | PASS | 数据偏少，候选文本截取需优化 |
| 920100 | 三协电机 | 17条 | 3条 | 有 | PASS | PASS | 股权存量时点偏少 |
| 920116 | 星图测控 | 3条 | 11条 | 有 | PASS | PASS | 北交所，正常完成 |

**完成率：8/8**

## 3. 第二周问题修复

| 上周问题 | 修复措施 |
|---------|---------|
| 缺三联锻造 | 使用正确MinerU JSON（04:04版）完成抽取 |
| 缺带数字的cross-check | 新增logs/week3_cross_check.csv（46条记录，含持股合计/比例合计/认购合计） |
| 只有pass/fail无具体数字 | Excel第三表现含date/shareholder_count/sum_shares/sum_ratio等列 |
| 2022年认购明细数值为null | 根本原因是候选文本截断（35K字符不足），已记录到error_analysis |

## 4. Cross-check示例（友升股份）

| 时点 | 股东数 | 持股合计(万股) | 比例合计 | 校验 |
|------|--------|---------------|---------|------|
| t0 | 4 | — | — | 无持股数（报告期初只有出资额） |
| t1 | 4 | 12000 | — | 匹配总股本12000 |
| t2 | 7 | 13380 | — | 匹配总股本13380 |
| t3 | 16 | 14480.1333 | — | 匹配总股本14480.1333 |

## 5. 自动化流程

```
PDF → MinerU解析 → locate_sections.py(章节定位) → extract_week2.py(Deepseek AI抽取)
→ validate_jsonl.py(Schema+Cross-check) → jsonl_to_excel.py(生成Excel三表)
```

一条命令运行：`py _run_week3.py`

## 6. 遗留问题

- 友升股份2022年10个认购方的数量/金额仍为null → 候选文本截断，需扩大或分段提取
- 影石创新数据偏少 → MinerU页码范围可能未覆盖完整历史沿革
- 三联锻造仅1条认缴 → 公司可能融资历史确实简单，待人工复核确认
- 股权转让(share_transfer_flow)尚未独立拆分

## 7. 与教师示范对比

友升股份2020-09-27轮次与教师示范Excel逐项比对：认购方名称、认购数量、认购金额、认购价格全部一致。2022-12-19轮次投资者名称齐全但数值字段有缺失，已记录到error_analysis。

## 8. 交付件

- outputs/week3_excel/（8个Excel，含三表）
- outputs/week2_jsonl/（8个JSONL）
- logs/week3_cross_check.csv（46条带数字cross-check）
- evaluation/error_analysis.md
- schemas/extraction_models.py（Pydantic Schema）
- scripts/（extract, validate, convert）
- _run_week3.py（一键运行脚本）
