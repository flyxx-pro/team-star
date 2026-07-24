# Week 6 改进方案与任务步骤

> 基于第五周个人反馈和第六周要求

---

## 一、第五周反馈：四个要改的点

| 老师反馈 | 当前状态 | 本周改进 |
|---------|---------|---------|
| 分开保存 Gold/规则/LLM/Final，每条记录保留来源 | JSONL 里 source 字段已有但目录结构未分层 | 建 manual_gold/auto_output/final/ 三个独立目录 |
| 重写逐事件 Cross-check：每对前后快照只能连接该区间内的事件 | 当前 cross_check 把所有认缴合计套用到每段变化中 | 按增资日期匹配区间，每个区间只引入属于该区间的认购事件 |
| 真正实现表格 rowspan/colspan 展开 | 赛分 2021-04 的 rowspan=4 导致重复填充，2021-11 的 rowspan=10 价格列偏移 | 编写 rowspan/colspan 展开函数，赛分做修复前后对比测试 |
| 继续做逐股东核对 | 逐股东验证已做但覆盖不全 | 补齐所有时点的逐股东对比 |

---

## 二、第六周任务

### 任务1：目录结构重组

```
team-star/
├── manual_gold/       ← 人工确认的Gold（不要求代码生成）
├── auto_output/       ← 未人工修改的raw和Auto三表
├── final/             ← 人工及组内复核后的三表和Excel
├── validation/        ← schema、Cross-check、Auto-vs-Gold和复核队列
├── review/            ← 组内差异、处理结论和PR/Issue链接
├── report/            ← 上市前融资分析报告
├── pipeline/          ← 完整自动提取代码和统一入口
├── prompts/           ← Prompt、模型参数和调用记录
├── logs/              ← 运行记录
```

### 任务2：组内互查（第三组：刘宇轩、陈雨昂、霍泓锟）

- 交换三表结果，逐公司对比差异
- 差异项回 PDF 原文确认
- 形成一致的结论，记录在 review/
- GitHub PR/Issue 链接

### 任务3：上市前融资分析报告（report/week6_report.md）

**必须回答**：
1. 8 家公司分别经历了多少轮投资？什么类型的公司？
2. 每一轮的投资者是什么情况？（PE/VC/产业资本/员工平台/自然人）
3. 有什么共同特征？有什么不同？
4. 可以总结什么模式？

**数据支撑**：从 final/ 三表中提取统计分析

### 任务4：技术修复

1. rowspan/colspan 展开函数
2. 逐事件 Cross-check 区间匹配
3. Gold/Auto/Final 分离

---

## 三、执行步骤（按优先级）

```
Step 1: 目录重组
  → 建 manual_gold/ auto_output/ final/ validation/ review/ report/

Step 2: Gold/Auto/Final 分离
  → manual_gold/: 友升教师gold + 人工核对过的记录
  → auto_output/: 纯Markdown正则提取(0 token) + AI提取结果
  → final/: 合并Gold + 修复后Auto + 组内复核

Step 3: rowspan/colspan 修复
  → 编写展开函数 → 赛分2021-04和2021-11做修复前后对比 → 验证45条认缴无重复

Step 4: Cross-check 区间匹配
  → 每对前后快照只连接该区间内的认购事件 → 不再把所有认购合计套用

Step 5: 组内互查
  → 与陈雨昂、霍泓锟交换结果 → 逐公司对比 → 差异回PDF确认

Step 6: 融资分析报告
  → 统计分析 → 撰写 report/week6_report.md

Step 7: 提交
  → README更新 → git push
```
