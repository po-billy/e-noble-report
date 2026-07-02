"""
Claude API를 이용해 월간 광고 성과 분석 코멘트를 자동 생성하는 모듈.
기존 보고서 3개의 실제 코멘트를 few-shot 예시로 활용한다.
"""
import os

import anthropic
from dotenv import load_dotenv

from collectors.base import ClientReport, MediaStats, MonthlyStats

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def _is_brand_search(s: MonthlyStats) -> bool:
    """브랜드검색 계정 여부: 광고비 0원이고 노출/클릭 데이터 있음"""
    return s.spend == 0 and s.impressions > 0


def _fmt_stat(s: MonthlyStats) -> str:
    ctr_pct = round(s.ctr * 100, 2) if s.ctr < 1 else round(s.ctr, 2)
    if _is_brand_search(s):
        return (
            f"노출수: {s.impressions:,}회 / 클릭수: {s.clicks:,}건 / "
            f"CTR: {ctr_pct}% / 전환매출: {s.revenue:,}원"
        )
    return (
        f"노출수: {s.impressions:,}회 / 클릭수: {s.clicks:,}건 / "
        f"CTR: {ctr_pct}% / 광고비: {s.spend:,}원 / 전환수: {s.conversions}건 / "
        f"전환매출: {s.revenue:,}원 / ROAS: {s.roas:.2f}"
    )


def _fmt_media(m: MediaStats) -> str:
    rank = f" 평균순위: {m.avg_rank:.1f}" if m.avg_rank else ""
    if m.spend == 0:
        return (
            f"  [{m.media_name}] 노출 {m.impressions:,} / 클릭 {m.clicks:,} / "
            f"전환매출 {m.revenue:,}원{rank}"
        )
    return (
        f"  [{m.media_name}] 노출 {m.impressions:,} / 클릭 {m.clicks:,} / "
        f"광고비 {m.spend:,}원 / 전환 {m.conversions}건 / "
        f"전환매출 {m.revenue:,}원 / ROAS {m.roas:.2f}{rank}"
    )


def _build_data_summary(report: ClientReport) -> str:
    h = report.monthly_history
    cur = h[-1] if h else report.monthly_total
    prev = h[-2] if len(h) >= 2 else None
    oldest = h[0] if len(h) >= 3 else None

    brand_search = _is_brand_search(cur)
    lines = [f"클라이언트: {report.client_name}", f"보고 기간: {cur.year}년 {cur.month}월"]
    if brand_search:
        lines.append("※ 브랜드검색 계정 (고정비 계약, 광고비/ROAS 미제공)")

    lines.append("\n■ 당월 전체 실적")
    lines.append(_fmt_stat(cur))

    if oldest and oldest is not prev:
        lines.append(f"\n■ 3개월 트렌드")
        for m in h:
            lines.append(f"  {m.year}년 {m.month}월: {_fmt_stat(m)}")

    if prev:
        imp_diff = cur.impressions - prev.impressions
        clk_diff = cur.clicks - prev.clicks
        rev_diff = cur.revenue - prev.revenue
        imp_pct = round(imp_diff / prev.impressions * 100, 1) if prev.impressions else 0
        clk_pct = round(clk_diff / prev.clicks * 100, 1) if prev.clicks else 0
        rev_pct = round(rev_diff / prev.revenue * 100, 1) if prev.revenue else 0
        lines.append(f"\n■ 전월 대비 변화 ({prev.year}년 {prev.month}월 기준)")
        lines.append(
            f"  노출수 {prev.impressions:,} → {cur.impressions:,} ({imp_diff:+,} / {imp_pct:+.1f}%)\n"
            f"  클릭수 {prev.clicks:,} → {cur.clicks:,} ({clk_diff:+,} / {clk_pct:+.1f}%)\n"
            f"  전환매출 {prev.revenue:,} → {cur.revenue:,}원 ({rev_diff:+,} / {rev_pct:+.1f}%)"
        )
        if not brand_search:
            spend_diff = cur.spend - prev.spend
            lines.append(
                f"  광고비 {prev.spend:,} → {cur.spend:,}원 ({spend_diff:+,})\n"
                f"  ROAS {prev.roas:.2f} → {cur.roas:.2f}"
            )

    if report.media_breakdown:
        lines.append("\n■ 캠페인별 실적 (전환매출 상위 5개)")
        for m in report.media_breakdown[:5]:
            lines.append(_fmt_media(m))

    next_month = cur.month % 12 + 1
    next_year = cur.year + (1 if cur.month == 12 else 0)
    lines.append(f"\n다음 달: {next_year}년 {next_month}월")

    return "\n".join(lines)


_FEW_SHOT_EXAMPLES = [
    {
        "data": """클라이언트: 위폭스 / 2026년 5월
당월: 노출수 680,596 / 클릭수 8,472 / 광고비 3,105,133원 / 전환수 191건 / 전환매출 13,384,690원 / ROAS 4.31
전월(4월): 노출수 608,309 / 클릭수 7,364 / 광고비 2,592,140원 / 전환수 159건 / 전환매출 12,012,770원 / ROAS 4.63
매체별: 쇼핑검색 ROAS 3.80 / GFA 카탈로그 ROAS 7.14 / GFA 애드부스트 ROAS 4.51""",
        "comment": """전월 대비 노출수는 608,309회 → 680,596회로 증가하였으며,
클릭수 또한 7,364건 → 8,472건으로 증가하였습니다.

밤 시간대에도 광고 노출을 지속적으로 유지하기 위해
쇼핑검색 모바일의 일예산을 3만원 → 5만원으로 증액하여 운영하였으며,
그에 따라 광고비는 2,592,140원 → 3,105,133원으로 증가하였습니다.
다만 전환매출액 또한 12,012,770원 → 13,384,690원으로 함께 증가하며
전반적으로 안정적인 광고수익률을 유지한 것으로 확인되었습니다.

매체별로는 애드부스트 광고수익률이 714% → 451%로 감소한 반면,
카탈로그 캠페인의 광고수익률은 343% → 714%로 크게 증가하며
전체 효율을 일부 보완한 것으로 판단됩니다.

6월에는 전환 효율이 우수한 핵심 상품 중심으로 예산 운영을 집중하고,
쇼핑검색 모바일 내 성과가 우수한 상품군의 노출 확대를 통해
구매전환 및 광고수익률 개선에 집중할 예정입니다.""",
    },
    {
        "data": """클라이언트: TWW / 2026년 5월
당월: 노출수 859,343 / 클릭수 3,199 / 광고비 4,467,636원 / 전환수 85건 / 전환매출 5,406,085원 / ROAS 1.21
전월(4월): 노출수 944,055 / 클릭수 3,689 / 광고비 4,664,874원 / 전환수 154건 / 전환매출 10,510,647원 / ROAS 2.25
매체별: 쇼핑검색 ROAS 1.60 / GFA 애드부스트 ROAS 1.40 / GFA 카탈로그 ROAS 2.34 / 브랜드검색 ROAS 19.58""",
        "comment": """전월 대비 노출수는 944,055회 → 859,343회,
클릭수는 3,689건 → 3,199건, 전환수는 154건 → 85건으로
감소하였습니다.

클릭당비용(CPC)은 1,265원 → 1,397원으로 소폭 증가하였으며,
광고수익률(ROAS)은 225% → 121%로 감소하였습니다.
이는 프로모션 기간 동안 주문량이 단기간 집중되며
광고 효율이 일시적으로 하락한 영향으로 판단됩니다.

매체별로는 쇼핑검색 전환수가 31건 → 14건으로 감소하였으며,
GFA의 경우에도 애드부스트 광고수익률이 264% → 140%,
카탈로그 캠페인 광고수익률이 350% → 234%로 감소하며
전반적인 효율 하락이 확인되었습니다.

6월에는 프로모션 이후 전환 데이터 및 상품 반응을 기반으로
효율이 우수한 상품 중심으로 광고 운영을 재정비하고,
광고수익률 회복 및 전환 안정화에 집중할 예정입니다.""",
    },
    {
        "data": """클라이언트: 저스트그린 / 2026년 5월
당월: 노출수 174,748 / 클릭수 1,495 / 광고비 1,949,661원 / 전환수 97건 / 전환매출 6,446,270원 / ROAS 3.31
전월(4월): 노출수 373,639 / 클릭수 2,270 / 광고비 2,687,173원 / 전환수 79건 / 전환매출 3,185,090원 / ROAS 1.19
매체별: 쇼핑검색 ROAS 2.16 / GFA 애드부스트 ROAS 4.08""",
        "comment": """노출수 373,639회 → 174,748회,
클릭수 2,270건 → 1,495건으로
5월에는 광고비가 전월 대비 약 73만원 감소함에 따라 노출 및 클릭이 함께 감소하였습니다.
클릭당비용(CPC)은 1,184원 → 1,304원으로 상승하였으나,
전환수는 79건 → 97건으로 약 18건 증가하며 효율적인 전환 성과를 확인하였습니다.

특히 전월 대비 GFA 애드부스트의 구매전환이
30건 → 50건으로 크게 증가하였으며,
4주식단 상품에서 총 38건의 구매전환이 발생해 가장 높은 성과를 보였습니다.

총 광고수익률은 119% → 331%로 전월 대비 크게 상승하였으며,
운영 규모가 일부 축소되었음에도 구매전환이 안정적으로 발생하며
전체 광고 효율이 개선된 것으로 확인됩니다.

6월에는 광고수익률이 우수하게 나타나고 있는 핵심 상품 중심으로
광고를 적극 운영하고, 여름 시즌 진입에 맞춰 구매전환 중심의 효율 운영을 통해
매출 확대를 목표로 진행하겠습니다.""",
    },
]


def _build_few_shot_messages() -> list[dict]:
    messages = []
    for ex in _FEW_SHOT_EXAMPLES:
        messages.append({"role": "user", "content": ex["data"]})
        messages.append({"role": "assistant", "content": ex["comment"]})
    return messages


_SYSTEM_PROMPT = """\
당신은 네이버 광고를 운영하는 디지털 마케팅 에이전시의 광고 운영 전문가입니다.
클라이언트에게 전달하는 월간 광고 성과 보고서의 '월간 코멘트'를 작성합니다.

작성 규칙:
1. 전월 대비 주요 지표(노출수, 클릭수, 광고비, 전환수, ROAS)의 변화를 수치와 함께 서술
2. 변화의 원인 또는 배경을 간략히 분석 (운영 변경, 시장 환경 등)
3. 매체별 특이사항 또는 주목할 성과를 구체적으로 언급
4. 다음 달 운영 방향과 개선 계획을 제시
5. 문체는 경어체(~하였습니다, ~예정입니다), 전문적이고 간결하게
6. 길이: 300~600자 내외
7. 코멘트 텍스트만 출력 (설명이나 제목 불필요)
8. 브랜드검색 계정의 경우: 광고비/ROAS 대신 CTR(클릭률), 전환매출, 캠페인별 성과 중심으로 서술
"""


def generate_comment(report: ClientReport) -> str:
    """ClientReport를 받아 한국어 월간 코멘트를 생성하고 반환"""
    data_summary = _build_data_summary(report)
    few_shot = _build_few_shot_messages()

    messages = few_shot + [{"role": "user", "content": data_summary}]

    response = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=messages,
    )
    return response.content[0].text.strip()
