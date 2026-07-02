from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class DailyStats:
    date: date
    weekday: str
    impressions: int
    clicks: int
    ctr: float
    cpc: float
    spend: int
    avg_rank: float
    conversions: int
    conversion_rate: float
    revenue: int
    cpa: float
    roas: float


@dataclass
class HourlyStats:
    hour: int
    impressions: int
    clicks: int
    ctr: float
    cpc: float
    spend: int
    conversions: int
    conversion_rate: float
    revenue: int
    roas: float


@dataclass
class KeywordStats:
    keyword: str
    impressions: int
    clicks: int
    ctr: float
    cpc: float
    spend: int
    avg_rank: float
    conversions: int
    conversion_rate: float
    revenue: int
    roas: float


@dataclass
class MediaStats:
    media_name: str
    impressions: int
    clicks: int
    ctr: float
    cpc: float
    spend: int
    avg_rank: float
    conversions: int
    conversion_rate: float
    revenue: int
    cpa: float
    roas: float
    daily_stats: list[DailyStats] = field(default_factory=list)
    hourly_stats: list[HourlyStats] = field(default_factory=list)
    keyword_stats: list[KeywordStats] = field(default_factory=list)


@dataclass
class MonthlyStats:
    """전체 월 집계 (모든 매체 합산)"""
    year: int
    month: int
    impressions: int
    clicks: int
    ctr: float
    cpc: float
    spend: int
    avg_rank: float
    conversions: int
    conversion_rate: float
    revenue: int
    cpa: float
    roas: float


@dataclass
class ClientReport:
    """한 클라이언트의 한 달치 전체 보고서 데이터"""
    client_name: str
    homepage: str
    manager: str
    email: str
    phone: str
    year: int
    month: int
    monthly_total: MonthlyStats
    monthly_history: list[MonthlyStats]  # 최근 12~14개월 누적
    media_breakdown: list[MediaStats]
    comment: str = ""
