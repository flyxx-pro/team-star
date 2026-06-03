# 数据来源说明

## 招股说明书获取来源

- **主数据源**: 巨潮资讯网 (cninfo.com.cn) — 中国证监会指定信息披露网站
- **API端点**: POST http://www.cninfo.com.cn/new/hisAnnouncement/query
- **搜索策略**: searchkey="{公司简称} 招股说明书"，不加column参数
- **日期范围**: 2024-01-01~2025-12-31

## 版本筛选规则

1. 排除非招股说明书公告：上市公告书、提示性公告、发行公告、问询回复、审核问询、补充法律意见、审计报告、发行保荐书、上市保荐书、法律意见书、更正、修订版、摘要、预案、结果公告
2. 版本优先级：正式稿 > 注册稿 > 申报稿 > 上会稿 > 招股意向书

## PDF解析工具

- **工具**: MinerU v3.1.11 (API/网页端)
- **解析模式**: hybrid backend, OCR disabled
- **输出格式**: JSON (pdf_info[page].preproc_blocks[].lines[].spans[].content)
- **页码范围**: 每家公司200页（MinerU限制），按VC章节位置选择页码范围
- **页码范围策略**: 1-50页(目录+基本信息) + VC章节区域(发行人基本情况、历史沿革、股本结构等)

## AI提取模型

- **模型**: Deepseek Chat (deepseek-chat)
- **参数**: Temperature=0.1, max_tokens=8192
- **截取策略**: 关键词密度评分，每家公司约28,000字符输入
