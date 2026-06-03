# Week 1：公共样本最小闭环报告

**小组**: C组（科创板） | **成员**: 刘宇轩、苏宇垚 | **日期**: 2026-06-03

---

## 1. 本周目标

- 目标：处理8个公共样本，跑通至少1家公司从PDF到JSON的完整闭环
- 实际完成：**8家公司全部跑通**，PDF下载 → MinerU解析 → 章节定位 → 候选文本截取 → AI JSON提取 → Schema校验 → 人工复核

---

## 2. 公共样本处理情况

| sample_id | 公司 | 代码 | 板块 | 下载 | 解析 | 章节定位 | 候选文本 | JSON输出 | 融资事件 | PE/VC投资者 | 复核 |
|-----------|------|------|------|------|------|---------|---------|---------|---------|-----------|------|
| STAR001 | 赛分科技 | 688758 | 科创板 | OK | OK | 6个章节 | 106→50页 | OK | 4 | 17 | PASS |
| STAR002 | 影石创新 | 688775 | 科创板 | OK | OK | 5个章节 | 131→49页 | OK | 1 | 12 | PASS |
| MB001 | 天和磁材 | 603072 | 主板 | OK | OK | 8个章节 | 105→47页 | OK | 3 | 3 | PASS |
| MB002 | 友升股份 | 603418 | 主板 | OK | OK | 6个章节 | 104→60页 | OK | 2 | 13 | PASS |
| GEM001 | 黄山谷捷 | 301581 | 创业板 | OK | OK | 5个章节 | 126→45页 | OK | 2 | 3 | PASS |
| GEM002 | 云汉芯城 | 301563 | 创业板 | OK | OK | 6个章节 | 142→49页 | OK | 3 | 20 | PASS |
| BSE001 | 三协电机 | 920100 | 北交所 | OK | OK | 6个章节 | 136→35页 | OK | 1 | 2 | PASS |
| BSE002 | 大鹏工业 | 920091 | 北交所 | OK | OK | 6个章节 | 124→44页 | OK | 1 | 2 | PASS |

---

## 3. 招股说明书来源

- 使用网站：巨潮资讯网 (cninfo.com.cn)
- 检索路径：POST http://www.cninfo.com.cn/new/hisAnnouncement/query，searchkey="{公司名} 招股说明书"，不加column参数
- 文件筛选规则：`_is_target_prospectus()`排除上市公告书、提示性公告、问询回复等；`_select_best_version()`按正式稿 > 注册稿 > 申报稿 > 上会稿优先级选择
- 下载脚本：`cninfo_spider.py`，含Session Cookie获取、UA轮换、随机延时(2-5s)、文件完整性校验(≥100KB)、3次重试、断点续爬

---

## 4. 代码说明

| 步骤 | 脚本路径 | 功能 |
|------|---------|------|
| PDF下载 | cninfo_spider.py | 巨潮API搜索+下载，8家全成功 |
| PDF解析 | (MinerU API) | 8家×200页=1600页解析 |
| 章节定位 | code/05_locate_relevant_sections/locate_sections.py | 从MinerU JSON定位VC章节，截取候选文本 |
| AI抽取 | code/06_extract_pevc_info/extract_pevc.py | Deepseek API提取结构化JSON |
| 校验 | (内置simple_validate) | 字段完整性+持股比例超100%检查 |

运行方式：
```bash
# 1. 下载
python cninfo_spider.py

# 2. MinerU解析（网页端上传PDF，按页码范围解析）

# 3. 章节定位
python code/05_locate_relevant_sections/locate_sections.py

# 4. AI提取
python code/06_extract_pevc_info/extract_pevc.py
```

---

## 5. JSON样例

- 文件路径：outputs/week1_sample_json/
- 字段完整性：8家全部包含company + financing_events + processing三层结构
- 证据文本：每个融资事件均含evidence_text和source_page/source_section
- 示例：云汉芯城(301563)提取3轮融资(2018年C轮→2020年D轮→2020年E轮)，估值从13.5亿→21亿→25.2亿，20个投资者中PE/VC占12个，自然人6个，政府基金2个

---

## 6. 失败案例

| 公司 | 环节 | 问题 | 当前处理 |
|------|------|------|---------|
| 全部 | AI提取第一版 | 候选文本14K截断+前一半后一半策略导致中间VC核心内容丢失，6/8返回0事件 | 改用关键词密度评分智能截取(28K)，按VC关键词命中数排序选页，8/8全部成功 |

---

## 7. 本周形成的规则

- **文件识别规则**：标题含"招股说明书"且不含"上市公告书""提示性公告""问询回复"等排除词
- **章节定位规则**：搜索"发行人基本情况""历史沿革""股本结构""股东情况""前十名股东"等关键词，前50页始终保留
- **关键词列表**（密度评分用）：增资/股权转让/出资/认购/入股/投资者/私募/创投/持股比例/股东名称/持股数量/估值/每股价格
- **JSON字段规则**：严格按任务书Schema，含company/financing_events/processing三层；融资事件含evidence_text和source_page；投资者含is_pevc标记
- **AI参数**：Deepseek-chat, Temperature=0.1, max_tokens=8192
- **校验规则**：evidence_text非空检查、event_type非空检查、investors非空检查、持股比例合计≤100%检查

---

## 8. 人工复核结果

抽查3家公司（云汉芯城、赛分科技、大鹏工业），合计验证13项关键数据：
- 云汉芯城：8/8通过（3项表面不匹配是MinerU数字格式差异，非AI幻觉）
- 赛分科技：3/3通过
- 大鹏工业：2/2通过
- 投资者分类准确性：自然人/VC/PE分类正确（如大鹏工业"蒋子先"标为自然人，"融汇工创"标为VC）
- evidence_text完整性：全部可在MinerU原文中找到对应段落

---

## 9. 下一步

- Week 2准备：按科创板分工，获取2025年科创板上市公司完整清单，批量下载招股书
- MinerU流程优化：当前手动上传网页端，后续可探索API批量调用
- JSON字段完善：部分公司的listing_date和prospectus_date为空，需从PDF封面补充
- 与苏宇垚互查：交换JSON文件，交叉验证投资者清单
