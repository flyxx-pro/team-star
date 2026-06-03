# team-star — 科创板招股书 PE/VC 投资信息提取

**小组**: C组（科创板） | **成员**: 刘宇轩、苏宇垚

## 项目简介

从科创板上市公司招股说明书中提取上市前 PE/VC 投资信息，形成结构化 JSON 数据。

## 流水线

```
PDF下载(cninfo_spider) → MinerU解析 → 章节定位 → 候选文本截取 → Deepseek AI提取 → Schema校验 → 人工复核
```

## 目录结构

```
team-star/
  README.md
  cninfo_spider.py              # 巨潮资讯爬虫
  company_lists/                # 企业清单
  source_notes/                 # 数据来源说明
  code/                         # 处理脚本
    05_locate_relevant_sections/
    06_extract_pevc_info/
  outputs/                      # 输出结果
    week1_sample_json/          # Week 1 JSON
  logs/                         # 运行日志
  weekly_reports/               # 周报
```

## 快速开始

```bash
# 1. 下载招股书
python cninfo_spider.py

# 2. MinerU 解析（网页端上传 PDF）

# 3. 章节定位
python code/05_locate_relevant_sections/locate_sections.py

# 4. AI 提取
python code/06_extract_pevc_info/extract_pevc.py
```

## Week 1 成果

- 8/8 家公共样本完整闭环
- 17 个融资事件、72 个投资者
- 0 Schema 校验错误
- 人工复核通过率 100%
