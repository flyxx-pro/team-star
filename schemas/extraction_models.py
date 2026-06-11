# -*- coding: utf-8 -*-
"""
Pydantic Schema: 招股书股本结构抽取
====================================
定义两类事实记录的字段、类型和必填项
"""
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator


class SubscriptionFlow(BaseModel):
    """认缴流量 —— 谁在什么时候认购了多少、多少钱、什么价格"""
    record_type: Literal["subscription_flow"] = "subscription_flow"

    pdf_page: int = Field(..., alias="PDF页码", description="PDF 页码")
    sub_date: str = Field(..., alias="增资日期", description="YYYY-MM-DD")
    subscriber: str = Field(..., alias="认购方", min_length=1, description="认购方名称")
    shares_wan: Optional[float] = Field(None, alias="认购数量(万股)", description="认购数量(万股)")
    amount_wan: Optional[float] = Field(None, alias="认购金额(万元)", description="认购金额(万元)")
    price_per_share: Optional[float] = Field(None, alias="认购价格(元/股)", description="认购价格(元/股)")
    evidence: str = Field(..., alias="原文证据", min_length=10, description="招股书原文证据")

    @field_validator("sub_date")
    @classmethod
    def check_date(cls, v):
        import re
        if not re.match(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError(f"日期格式错误: {v}")
        return v


class EquitySnapshot(BaseModel):
    """股权结构存量 —— 某个时点股东结构"""
    record_type: Literal["equity_snapshot"] = "equity_snapshot"

    pdf_page: int = Field(..., alias="PDF页码", description="PDF 页码")
    time_point: str = Field(..., alias="时点", description="t0/t1/t2... 或具体日期")
    snapshot_scope: str = Field(..., alias="股权结构口径", description="如 '报告期初公司股权结构'")
    total_shares_wan: Optional[float] = Field(None, alias="总股本(万股)")
    total_capital_wan: Optional[float] = Field(None, alias="总出资额(万元注册资本)")
    shareholder: str = Field(..., alias="股东名称", min_length=1)
    shares_held_wan: Optional[float] = Field(None, alias="持股数(万股)")
    capital_wan: Optional[float] = Field(None, alias="出资额(万元注册资本)")
    ratio_pct: Optional[float] = Field(None, alias="持股比例", description="持股比例(%)")
    evidence: str = Field(..., alias="原文证据", min_length=10)

    @field_validator("ratio_pct")
    @classmethod
    def check_ratio(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError(f"持股比例超出0-100: {v}")
        return v
