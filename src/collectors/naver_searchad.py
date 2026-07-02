"""
Naver SearchAd API + GFA API 클라이언트.
API 키가 없거나 NAVER_MOCK=true 이면 mock 데이터를 반환한다.
"""
import base64
import hashlib
import hmac
import os
import time
from datetime import date, timedelta

import urllib.request
import urllib.error
import json

from dotenv import load_dotenv

load_dotenv()

from pathlib import Path

BASE_URL = "https://api.searchad.naver.com"
_ROOT = Path(__file__).resolve().parents[2]   # ad-report/

# 레거시 단일 계정(.env) — accounts.json 이 없을 때 폴백으로만 사용
_ENV_KEY    = os.getenv("NAVER_API_KEY", "")
_ENV_SECRET = os.getenv("NAVER_API_SECRET", "")
_ENV_CID    = os.getenv("NAVER_CUSTOMER_ID", "")
_ENV_NAME   = os.getenv("NAVER_ACCOUNT_NAME", "")


def _load_accounts() -> list[dict]:
    """여러 네이버 광고주 계정을 등록 목록으로 로드.
    우선순위: accounts.json → (없으면) .env 단일 계정.
    각 계정은 고유의 api_key/api_secret/customer_id 를 가진다."""
    accts: list[dict] = []
    path = _ROOT / "accounts.json"
    if path.exists():
        try:
            for a in json.loads(path.read_text(encoding="utf-8")):
                cid = str(a.get("customer_id") or a.get("customerId") or "").strip()
                key = (a.get("api_key") or "").strip()
                sec = (a.get("api_secret") or "").strip()
                if cid and key and sec:
                    accts.append({
                        "customer_id": cid, "api_key": key, "api_secret": sec,
                        "name": (a.get("name") or f"광고주 {cid}").strip(),
                        "group": (a.get("group") or "").strip(),
                        "media": (a.get("media") or "").strip(),
                        "agency": bool(a.get("agency")),   # 대행사 마스터 계정 여부
                    })
        except Exception:
            pass
    if not accts and _ENV_KEY and _ENV_SECRET and _ENV_CID:
        accts.append({
            "customer_id": str(_ENV_CID), "api_key": _ENV_KEY, "api_secret": _ENV_SECRET,
            "name": _ENV_NAME or f"광고주 {_ENV_CID}", "group": "", "media": "",
        })
    return accts


_ACCOUNTS    = _load_accounts()
_ACCT_BY_ID  = {a["customer_id"]: a for a in _ACCOUNTS}
_DEFAULT_ACCT = _ACCOUNTS[0] if _ACCOUNTS else None
CUSTOMER_ID  = _DEFAULT_ACCT["customer_id"] if _DEFAULT_ACCT else ""   # 하위 호환


def register_account(customer_id, api_key, api_secret,
                     name: str = "", media: str = "", group: str = "",
                     agency: bool = False) -> dict | None:
    """런타임에 계정(키 세트)을 등록/갱신한다.
    웹 UI에서 팀장이 입력한 키를 수집기가 즉시 쓸 수 있게 하는 브리지.

    핵심: `_ACCT_BY_ID` 는 v2_report 가 import 시 참조를 공유하는 dict 이므로
    **in-place 로 갱신**해야 생성기에서도 보인다(재바인딩 금지).
    """
    cid = str(customer_id or "").strip()
    key = str(api_key or "").strip()
    sec = str(api_secret or "").strip()
    if not (cid and key and sec):
        return None
    acct = {
        "customer_id": cid, "api_key": key, "api_secret": sec,
        "name": (name or f"광고주 {cid}").strip(), "group": (group or "").strip(),
        "media": (media or "").strip(), "agency": bool(agency),
    }
    _ACCT_BY_ID[cid] = acct                       # in-place (공유 dict)
    global _ACCOUNTS, _DEFAULT_ACCT, CUSTOMER_ID
    _ACCOUNTS = [a for a in _ACCOUNTS if a.get("customer_id") != cid] + [acct]
    if _DEFAULT_ACCT is None:
        _DEFAULT_ACCT = acct
        CUSTOMER_ID = cid
    return acct


def _build_groups() -> dict:
    """group 이름 → 소속 계정 목록 (입력 순서 유지)"""
    groups: dict[str, list] = {}
    for a in _ACCOUNTS:
        g = a.get("group")
        if g:
            groups.setdefault(g, []).append(a)
    return groups


_GROUPS = _build_groups()
_AGENCIES = [a for a in _ACCOUNTS if a.get("agency")]
# 대행사 하위 광고주 customer_id → 그 광고주를 관할하는 대행사 계정
_SUBCLIENT_AGENCY: dict[str, dict] = {}


def _media_tag(account: dict) -> str:
    """매체 구분 라벨. media 필드 우선, 없으면 이름 괄호 안, 그것도 없으면 이름."""
    if account.get("media"):
        return account["media"]
    name = account.get("name", "")
    if "(" in name and ")" in name:
        return name[name.index("(") + 1:name.index(")")]
    return name or account.get("customer_id", "")

MOCK_MODE = os.getenv("NAVER_MOCK", "true").lower() == "true" or not _ACCOUNTS


# ── 인증 ─────────────────────────────────────────────────
def _resolve(customer_id: str | None) -> dict | None:
    """customer_id 로 계정(키 세트)을 찾는다.
    1) 직접 등록된 계정  2) 대행사 하위 광고주(대행사 키 + X-Customer)  3) 기본 계정."""
    if customer_id is not None:
        cid = str(customer_id)
        a = _ACCT_BY_ID.get(cid)
        if a:
            return a
        # 대행사 하위 광고주: 대행사 키로 서명하고 X-Customer 만 해당 광고주로 지정
        ag = _SUBCLIENT_AGENCY.get(cid) or (_AGENCIES[0] if _AGENCIES else None)
        if ag:
            return {"api_key": ag["api_key"], "api_secret": ag["api_secret"],
                    "customer_id": cid, "name": cid, "via_agency": True}
    return _DEFAULT_ACCT


# 로컬 PC 시계가 네이버 서버와 어긋나면 "Invalid Timestamp(만료)" 403 이 난다.
# 응답 Date 헤더로 서버와의 시차를 측정해 타임스탬프에 보정한다.
_CLOCK_OFFSET = 0.0     # (서버시각 - 로컬시각) 초
_clock_synced = False


def _sync_clock() -> None:
    """네이버 응답의 Date 헤더로 서버-로컬 시차를 측정해 _CLOCK_OFFSET 갱신."""
    global _CLOCK_OFFSET, _clock_synced
    import email.utils
    try:
        urllib.request.urlopen(urllib.request.Request(BASE_URL + "/ncc/campaigns"), timeout=10)
    except urllib.error.HTTPError as e:
        d = e.headers.get("Date")
        if d:
            server = email.utils.parsedate_to_datetime(d).timestamp()
            _CLOCK_OFFSET = server - time.time()
            _clock_synced = True
    except Exception:
        pass


def _now_ms() -> str:
    return str(int((time.time() + _CLOCK_OFFSET) * 1000))


def _make_signature(timestamp: str, method: str, path: str, secret: str) -> str:
    message = f"{timestamp}.{method}.{path}"
    return base64.b64encode(
        hmac.new(bytes(secret, "utf-8"), bytes(message, "utf-8"), hashlib.sha256).digest()
    ).decode()


def _headers(path: str, method: str, account: dict) -> dict:
    ts = _now_ms()
    return {
        "X-Timestamp": ts,
        "X-API-KEY": account["api_key"],
        "X-Signature": _make_signature(ts, method, path, account["api_secret"]),
        "X-Customer": str(account["customer_id"]),
        "Content-Type": "application/json; charset=UTF-8",
    }


def _get(path: str, customer_id: str | None = None, _retry: bool = True) -> dict | list:
    account = _resolve(customer_id)
    if not account:
        raise RuntimeError("네이버 API 계정이 설정되지 않았습니다 (accounts.json 또는 .env 확인)")
    # 서명은 쿼리스트링 제외한 경로로 계산
    sign_path = path.split("?")[0]
    url = BASE_URL + path
    req = urllib.request.Request(url, headers=_headers(sign_path, "GET", account))
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return json.loads(res.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        # 시계 어긋남(만료) → 서버시각 동기화 후 1회 재시도
        if e.code == 403 and "timestamp" in body.lower() and _retry:
            _sync_clock()
            return _get(path, customer_id, _retry=False)
        raise RuntimeError(f"Naver API {e.code} {e.reason}: {body}")


# ── Mock 데이터 ────────────────────────────────────────────
_MOCK_CUSTOMERS = [
    {"customerId": "1001", "customerName": "위폭스", "status": "OPERATING"},
    {"customerId": "1002", "customerName": "TWW",   "status": "OPERATING"},
    {"customerId": "1003", "customerName": "저스트그린", "status": "OPERATING"},
    {"customerId": "1004", "customerName": "(샘플) 클라이언트 D", "status": "OPERATING"},
    {"customerId": "1005", "customerName": "(샘플) 클라이언트 E", "status": "OPERATING"},
]


# ── Public API ────────────────────────────────────────────
def is_connected() -> bool:
    """등록된 네이버 광고주 계정이 하나라도 있는지 반환"""
    return bool(_ACCOUNTS)


def get_accounts() -> list[dict]:
    """등록된 계정 메타(키 제외) 목록"""
    return [{"customer_id": a["customer_id"], "name": a["name"], "media": _media_tag(a)} for a in _ACCOUNTS]


def account_media_map() -> dict:
    """customer_id → {media, name} 매핑 (보고서 화면에서 매체 라벨 표시용)"""
    return {a["customer_id"]: {"media": _media_tag(a), "name": a["name"]} for a in _ACCOUNTS}


def get_account_status() -> list[dict]:
    """등록 계정별 연동 현황 (조회 전용): 연결 여부 · 캠페인 수/유형 · 비즈머니 잔액."""
    _TP_LABEL = {
        "WEB_SITE": "파워링크", "SHOPPING": "쇼핑검색", "BRAND_SEARCH": "브랜드검색",
        "POWER_CONTENTS": "파워컨텐츠", "PLACE": "플레이스",
    }
    out = []
    for a in _ACCOUNTS:
        cid = a["customer_id"]
        info = {
            "customer_id": cid, "name": a["name"], "media": _media_tag(a),
            "connected": False, "campaign_count": 0, "campaign_types": [],
            "bizmoney": None, "error": None,
        }
        try:
            camps = _get("/ncc/campaigns", customer_id=cid)
            info["connected"] = True
            info["campaign_count"] = len(camps)
            tps = sorted({c.get("campaignTp") for c in camps if c.get("campaignTp")})
            info["campaign_types"] = [_TP_LABEL.get(t, t) for t in tps]
        except Exception as e:
            info["error"] = str(e)
        try:
            bm = _get("/billing/bizmoney", customer_id=cid)
            if isinstance(bm, dict) and bm.get("bizmoney") is not None:
                info["bizmoney"] = int(round(float(bm["bizmoney"])))
        except Exception:
            pass
        out.append(info)
    return out


def get_customers() -> list[dict]:
    """광고주 목록 조회.
    · 대행사(agency) 계정: /customer-links 로 하위 광고주를 자동으로 끌어온다.
    · group 으로 묶인 직접 계정: 하나의 광고주(여러 매체 합산, customerId='2043134+4273')로 반환.
    · 그 외 직접 계정: 개별 광고주로 반환."""
    if MOCK_MODE:
        return _MOCK_CUSTOMERS

    out = []

    # 1) 대행사 하위 광고주 (대행사 키 하나로 전부 조회)
    _SUBCLIENT_AGENCY.clear()
    for ag in _AGENCIES:
        try:
            res = _get("/customer-links?type=MYCLIENTS", customer_id=ag["customer_id"])
            items = res if isinstance(res, list) else res.get("items", [])
        except Exception:
            items = []
        for it in items:
            scid = str(it.get("customerId") or it.get("linkedCustomerId") or "").strip()
            if not scid:
                continue
            sname = (it.get("customerName") or it.get("linkedCustomerName") or f"광고주 {scid}").strip()
            _SUBCLIENT_AGENCY[scid] = ag
            out.append({"customerId": scid, "customerName": sname,
                        "status": it.get("status", "OPERATING")})

    # 2) group 으로 묶인 직접 계정 (매체 합산)
    for gname, accts in _GROUPS.items():
        out.append({
            "customerId": "+".join(a["customer_id"] for a in accts),
            "customerName": gname,
            "status": "OPERATING",
        })

    # 3) 그룹·대행사에 속하지 않은 개별 직접 계정
    for a in _ACCOUNTS:
        if a.get("group") or a.get("agency"):
            continue
        out.append({"customerId": a["customer_id"], "customerName": a["name"], "status": "OPERATING"})

    return out


# /stats 로 조회할 지표 필드 (조회 전용 — 절대 수정/생성 호출 아님)
#   impCnt 노출수 · clkCnt 클릭수 · salesAmt 광고비(지출,VAT별도) · ctr 클릭률 · cpc 클릭당비용
#   avgRnk 평균순위 · ccnt 전환수 · crto 전환율 · convAmt 전환매출 · ror 수익률 · cpConv 전환당비용
_STAT_FIELDS = [
    "impCnt", "clkCnt", "salesAmt", "ctr", "cpc",
    "avgRnk", "ccnt", "crto", "convAmt", "ror", "cpConv",
]


def _batch_stats(ids: list, time_range: dict, time_increment: str = "allDays",
                 customer_id: str | None = None) -> list:
    """ID 목록을 배치로 나눠 통계 조회 (URL 길이 제한 대응). 캠페인/키워드 ID 모두 가능."""
    import json as _json, urllib.parse as _up
    FIELDS = _json.dumps(_STAT_FIELDS)
    BATCH, result = 10, []
    for i in range(0, len(ids), BATCH):
        batch = ids[i:i + BATCH]
        path = (
            "/stats?ids=" + _up.quote(",".join(batch))
            + "&fields=" + _up.quote(FIELDS)
            + "&timeRange=" + _up.quote(_json.dumps(time_range))
            + f"&timeIncrement={time_increment}"
        )
        try:
            r = _get(path, customer_id=customer_id)
            result.extend(r.get("data", []))
        except Exception:
            pass
    return result


def _row_metrics(d: dict) -> dict:
    """단일 /stats data 행(캠페인/키워드)을 보고서 지표 dict로 변환."""
    imp   = int(d.get("impCnt", 0) or 0)
    clk   = int(d.get("clkCnt", 0) or 0)
    spend = int(d.get("salesAmt", 0) or 0)      # 광고비(지출, VAT 별도)
    conv  = int(d.get("ccnt", 0) or 0)          # 전환수
    rev   = int(d.get("convAmt", 0) or 0)       # 전환매출
    return {
        "impressions": imp,
        "clicks": clk,
        "ctr": round(clk / imp, 4) if imp else 0,
        "cpc": round(spend / clk) if clk else 0,
        "spend": spend,
        "avg_rank": round(float(d.get("avgRnk", 0) or 0), 1),
        "conversions": conv,
        "conversion_rate": round(conv / clk, 4) if clk else 0,
        "revenue": rev,
        "cpa": round(spend / conv) if conv else 0,
        "roas": round(rev / spend, 2) if spend else 0,
    }


def _agg_stats(data: list, year: int, month: int) -> dict:
    """API 응답 리스트를 monthly_total 포맷으로 집계 (합계 기준 재계산)"""
    imp = clk = spend = conv = rev = 0
    rank_weighted = 0.0
    for d in data:
        di = _row_metrics(d)
        imp   += di["impressions"]
        clk   += di["clicks"]
        spend += di["spend"]
        conv  += di["conversions"]
        rev   += di["revenue"]
        rank_weighted += di["avg_rank"] * di["impressions"]

    return {
        "year": year, "month": month,
        "impressions": imp,
        "clicks": clk,
        "ctr":  round(clk / imp, 4) if imp else 0,
        "cpc":  round(spend / clk) if clk else 0,
        "spend": spend,
        "avg_rank": round(rank_weighted / imp, 1) if imp else 0,
        "conversions": conv,
        "conversion_rate": round(conv / clk, 4) if clk else 0,
        "revenue": rev,
        "cpa":  round(spend / conv) if conv else 0,
        "roas": round(rev / spend, 2) if spend else 0,
    }


def get_monthly_stats(customer_id: str, year: int, month: int) -> dict:
    """월간 통계 조회 (디스패처).
    customer_id 가 '+'로 이어진 복수 계정이면 각 계정을 조회해 하나로 합산한다.
    반환값: {monthly_total, monthly_history, media_breakdown, daily_stats, keyword_stats}
    """
    if MOCK_MODE:
        return _mock_stats(customer_id, year, month)

    ids = [c for c in str(customer_id).split("+") if c]
    if len(ids) <= 1:
        return _single_account_stats(ids[0] if ids else customer_id, year, month)

    # 복수 계정 → 매체 합산
    results = []
    for cid in ids:
        try:
            results.append((cid, _single_account_stats(cid, year, month)))
        except Exception:
            pass   # 한 계정이 실패해도 나머지로 보고서 생성
    if not results:
        raise RuntimeError(f"Naver API 통계 조회 실패 (customers={customer_id})")
    return _merge_accounts(results, year, month)


def _single_account_stats(
    customer_id: str,
    year: int,
    month: int,
) -> dict:
    """단일 광고주 계정의 월간 통계 조회."""
    import calendar as _cal
    from concurrent.futures import ThreadPoolExecutor
    last_day = _cal.monthrange(year, month)[1]

    try:
        # 해당 계정의 전체 캠페인 목록 조회 (GET — 조회 전용)
        campaigns = _get("/ncc/campaigns", customer_id=customer_id)
        camp_ids  = [c["nccCampaignId"] for c in campaigns]
        camp_name = {c["nccCampaignId"]: c.get("name", c["nccCampaignId"]) for c in campaigns}

        if not camp_ids:
            raise RuntimeError("캠페인이 없습니다")

        # 당월 통계
        cur_range = {"since": f"{year}-{month:02d}-01", "until": f"{year}-{month:02d}-{last_day:02d}"}
        cur_data  = _batch_stats(camp_ids, cur_range, customer_id=customer_id)
        monthly   = _agg_stats(cur_data, year, month)

        # 직전 12개월 통계 (최근 13개월 히스토리) — 병렬 조회
        def _fetch_hist(delta):
            m2, y2 = month - delta, year
            while m2 <= 0:
                m2 += 12; y2 -= 1
            ld2 = _cal.monthrange(y2, m2)[1]
            h_range = {"since": f"{y2}-{m2:02d}-01", "until": f"{y2}-{m2:02d}-{ld2:02d}"}
            try:
                return _agg_stats(_batch_stats(camp_ids, h_range, customer_id=customer_id), y2, m2)
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=6) as _hex:
            hist_results = list(_hex.map(_fetch_hist, range(12, 0, -1)))
        history = [r for r in hist_results if r]
        history.append(monthly)

        # 캠페인별 매체 브레이크다운 (전 지표)
        media_breakdown = []
        for d in sorted(cur_data, key=lambda x: -int(x.get("salesAmt", 0) or x.get("convAmt", 0) or 0)):
            m = _row_metrics(d)
            m["media_name"] = camp_name.get(d.get("id"), d.get("id", ""))
            media_breakdown.append(m)

        # 일별 추이 (timeIncrement=1 → 날짜별 집계)
        daily_stats = _collect_daily(camp_ids, cur_range, year, month, customer_id=customer_id)

        # 키워드 TOP — 광고비/노출 상위 캠페인으로 한정해 호출량을 제한(성능)
        top_camp_ids = [
            d.get("id") for d in sorted(
                cur_data, key=lambda x: -int(x.get("salesAmt", 0) or x.get("impCnt", 0) or 0)
            ) if d.get("id")
        ][:15]
        # GET /ncc/keywords → GET /stats?ids=키워드 (조회 전용, POST 없음)
        keyword_stats = _collect_keywords(top_camp_ids or camp_ids, cur_range, customer_id=customer_id)

        # 브랜드검색 계정: adgroup 수준 PC/MO 분리
        bs_adgroup_pc, bs_adgroup_mo = [], []
        if any(c.get("campaignTp") == "BRAND_SEARCH" for c in campaigns[:5]):
            camps_with_data = [d.get("id") for d in cur_data if d.get("id")]
            bs_adgroup_pc, bs_adgroup_mo = _collect_bs_device_stats(
                camps_with_data or camp_ids, cur_range, customer_id=customer_id
            )

        # 시간대별 통계 (최근 7일, breakdown=hh24)
        hourly_stats, hourly_since, hourly_until = _collect_hourly(
            camp_ids, customer_id=customer_id
        )

        return {
            "monthly_total":   monthly,
            "monthly_history": history,
            "media_breakdown": media_breakdown,
            "daily_stats":     daily_stats,
            "keyword_stats":   keyword_stats,
            "bs_adgroup_pc":   bs_adgroup_pc,
            "bs_adgroup_mo":   bs_adgroup_mo,
            "hourly_stats":    hourly_stats,
            "hourly_since":    hourly_since,
            "hourly_until":    hourly_until,
        }

    except Exception as e:
        raise RuntimeError(f"Naver API 통계 조회 실패 (customer={customer_id}): {e}")


def _recompute_total(acc: list, year: int, month: int) -> dict:
    """[imp, clk, spend, conv, rev, rank_weighted] 합계로 월 지표를 재계산."""
    imp, clk, spend, conv, rev, rankw = acc
    return {
        "year": year, "month": month,
        "impressions": imp, "clicks": clk,
        "ctr": round(clk / imp, 4) if imp else 0,
        "cpc": round(spend / clk) if clk else 0,
        "spend": spend,
        "avg_rank": round(rankw / imp, 1) if imp else 0,
        "conversions": conv,
        "conversion_rate": round(conv / clk, 4) if clk else 0,
        "revenue": rev,
        "cpa": round(spend / conv) if conv else 0,
        "roas": round(rev / spend, 2) if spend else 0,
    }


def _merge_accounts(results: list, year: int, month: int) -> dict:
    """여러 계정(매체)의 통계를 하나의 보고서 데이터로 합산.
    results: [(customer_id, raw_dict), ...]"""
    def _tag(cid):
        a = _ACCT_BY_ID.get(str(cid))
        return _media_tag(a) if a else str(cid)

    def _acc(stat):
        imp = stat.get("impressions", 0) or 0
        return [imp, stat.get("clicks", 0) or 0, stat.get("spend", 0) or 0,
                stat.get("conversions", 0) or 0, stat.get("revenue", 0) or 0,
                (stat.get("avg_rank", 0) or 0) * imp]

    # 월 합계
    tot = [0, 0, 0, 0, 0, 0.0]
    for _cid, raw in results:
        a = _acc(raw.get("monthly_total", {}))
        tot = [tot[i] + a[i] for i in range(6)]
    monthly_total = _recompute_total(tot, year, month)

    # 월별 히스토리 (연·월 키로 합산)
    hist_acc: dict = {}
    for _cid, raw in results:
        for h in raw.get("monthly_history", []):
            k = (h.get("year"), h.get("month"))
            cur = hist_acc.setdefault(k, [0, 0, 0, 0, 0, 0.0])
            a = _acc(h)
            hist_acc[k] = [cur[i] + a[i] for i in range(6)]
    history = [_recompute_total(hist_acc[k], k[0], k[1]) for k in sorted(hist_acc)]
    if not history:
        history = [monthly_total]

    # 캠페인별: 매체 태그를 접두로 붙여 구분
    media = []
    for cid, raw in results:
        t = _tag(cid)
        for m in raw.get("media_breakdown", []):
            mm = dict(m)
            mm["media_name"] = f"[{t}] {m.get('media_name', '')}"
            media.append(mm)
    media.sort(key=lambda x: -(x.get("spend", 0) or x.get("impressions", 0) or 0))

    # 일별 (날짜 키로 합산 — 둘 다 비면 [])
    daily_acc: dict = {}
    for _cid, raw in results:
        for dd in raw.get("daily_stats", []):
            k = dd.get("date")
            cur = daily_acc.setdefault(k, {"date": dd.get("date"), "weekday": dd.get("weekday", ""),
                                           "impressions": 0, "clicks": 0, "spend": 0,
                                           "conversions": 0, "revenue": 0})
            for f in ("impressions", "clicks", "spend", "conversions", "revenue"):
                cur[f] += dd.get(f, 0) or 0
    daily = [daily_acc[k] for k in sorted(daily_acc)]

    # 키워드: 합쳐서 노출수 상위 30 + 파워링크 전용 키워드 분리
    keywords = []
    pl_keywords = []
    for cid, raw in results:
        keywords.extend(raw.get("keyword_stats", []))
        if _tag(cid) == "파워링크":
            pl_keywords.extend(raw.get("keyword_stats", []))
    keywords.sort(key=lambda x: -(x.get("impressions", 0) or 0))
    pl_keywords.sort(key=lambda x: -(x.get("impressions", 0) or 0))

    # 브랜드검색 adgroup PC/MO
    bs_pc, bs_mo = [], []
    for _cid, raw in results:
        bs_pc.extend(raw.get("bs_adgroup_pc", []))
        bs_mo.extend(raw.get("bs_adgroup_mo", []))
    bs_pc.sort(key=lambda x: -(x.get("impressions", 0) or 0))
    bs_mo.sort(key=lambda x: -(x.get("impressions", 0) or 0))

    # 시간대별: 계정 간 같은 hour 합산
    hourly_acc: dict[str, dict] = {}
    hourly_since = hourly_until = ""
    for _cid, raw in results:
        if not hourly_since:
            hourly_since = raw.get("hourly_since", "")
            hourly_until = raw.get("hourly_until", "")
        for h in raw.get("hourly_stats", []):
            hour = h.get("hour", "")
            if not hour:
                continue
            cur = hourly_acc.setdefault(hour, {
                "hour": hour, "impressions": 0, "clicks": 0, "spend": 0,
                "conversions": 0, "revenue": 0, "rank_w": 0.0,
            })
            imp = h.get("impressions", 0) or 0
            cur["impressions"]  += imp
            cur["clicks"]       += h.get("clicks", 0) or 0
            cur["spend"]        += h.get("spend", 0) or 0
            cur["conversions"]  += h.get("conversions", 0) or 0
            cur["revenue"]      += h.get("revenue", 0) or 0
            cur["rank_w"]       += (h.get("avg_rank", 0) or 0) * imp
    order = [f"{h:02d}시~{(h+1)%24:02d}시" for h in range(24)]
    hourly = []
    for h in order:
        ag = hourly_acc.get(h, {"hour": h, "impressions": 0, "clicks": 0, "spend": 0,
                                 "conversions": 0, "revenue": 0, "rank_w": 0.0})
        imp = ag["impressions"]; clk = ag["clicks"]; sp = ag["spend"]
        cv  = ag["conversions"]; rv  = ag["revenue"]
        hourly.append({
            "hour": h, "impressions": imp, "clicks": clk,
            "ctr": round(clk / imp, 4) if imp else 0,
            "cpc": round(sp / clk) if clk else 0,
            "spend": sp,
            "avg_rank": round(ag["rank_w"] / imp, 1) if imp else 0,
            "conversions": cv,
            "conversion_rate": round(cv / clk, 4) if clk else 0,
            "revenue": rv,
        })

    return {
        "monthly_total": monthly_total,
        "monthly_history": history,
        "media_breakdown": media,
        "daily_stats": daily,
        "keyword_stats": keywords[:30],
        "keyword_stats_pl": pl_keywords[:30],
        "bs_adgroup_pc": bs_pc,
        "bs_adgroup_mo": bs_mo,
        "hourly_stats": hourly,
        "hourly_since": hourly_since,
        "hourly_until": hourly_until,
    }


def _collect_bs_device_stats(camp_ids: list, time_range: dict,
                             customer_id: str | None = None) -> tuple:
    """브랜드검색 광고그룹 통계를 PC/MO로 분리.
    adgroup 이름에 _PC_ 포함 → PC, 그 외(주로 _MO_) → MO.
    반환: (pc_list, mo_list) — 각 항목은 _row_metrics() + media_name."""
    from concurrent.futures import ThreadPoolExecutor

    # 데이터 있는 캠페인의 활성 adgroup 조회
    all_groups = []
    for i in range(0, len(camp_ids), 5):
        batch = camp_ids[i:i + 5]
        try:
            grps = _get(f"/ncc/adgroups?campaignIds={','.join(batch)}", customer_id=customer_id)
            all_groups.extend(g for g in grps if g.get("status") == "ELIGIBLE")
        except Exception:
            pass

    if not all_groups:
        return [], []

    ag_ids = [g["nccAdgroupId"] for g in all_groups]
    ag_name = {g["nccAdgroupId"]: g.get("name", "") for g in all_groups}

    # 배치 병렬 통계 조회
    batches = [ag_ids[i:i + 10] for i in range(0, len(ag_ids), 10)]

    def _fetch(batch):
        try:
            return _batch_stats(batch, time_range, customer_id=customer_id)
        except Exception:
            return []

    stats_rows = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for rows in ex.map(_fetch, batches):
            stats_rows.extend(rows)

    pc_list, mo_list = [], []
    for row in stats_rows:
        m = _row_metrics(row)
        if not m["impressions"] and not m["clicks"]:
            continue
        gname = ag_name.get(row.get("id", ""), row.get("id", ""))
        m["media_name"] = gname
        if "_PC_" in gname or gname.endswith("_PC"):
            pc_list.append(m)
        else:
            mo_list.append(m)

    def _dedup(lst):
        merged = {}
        for ag in lst:
            name = ag.get("media_name", "")
            if name not in merged:
                merged[name] = dict(ag)
            else:
                for k in ("impressions", "clicks", "spend", "conversions", "revenue"):
                    merged[name][k] = (merged[name].get(k, 0) or 0) + (ag.get(k, 0) or 0)
        result = list(merged.values())
        result.sort(key=lambda x: -(x.get("impressions", 0) or 0))
        return result

    return _dedup(pc_list), _dedup(mo_list)


def _collect_daily(camp_ids: list, time_range: dict, year: int, month: int,
                   customer_id: str | None = None) -> list:
    """일별 통계: 하루씩 병렬 쿼리 (Naver SearchAd API는 timeIncrement=1 미지원).
    ThreadPoolExecutor(8) 으로 ~16초 내 완료."""
    import calendar
    from concurrent.futures import ThreadPoolExecutor
    from datetime import date as _date

    weekdays = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    last_day = calendar.monthrange(year, month)[1]

    def fetch_day(day: int):
        ds = f"{year}-{month:02d}-{day:02d}"
        try:
            rows = _batch_stats(camp_ids, {"since": ds, "until": ds}, customer_id=customer_id)
            if not rows:
                return None
            imp = clk = spend = conv = rev = 0
            for d in rows:
                m = _row_metrics(d)
                imp   += m["impressions"]
                clk   += m["clicks"]
                spend += m["spend"]
                conv  += m["conversions"]
                rev   += m["revenue"]
            if not imp and not spend:
                return None
            return {
                "date": ds,
                "weekday": weekdays[_date(year, month, day).weekday()],
                "impressions": imp, "clicks": clk,
                "spend": spend, "conversions": conv, "revenue": rev,
            }
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(fetch_day, range(1, last_day + 1)))
    return [r for r in results if r]


def _collect_hourly(camp_ids: list, customer_id: str | None = None) -> list:
    """시간대별 통계 (breakdown=hh24, 최근 7일 제약).
    캠페인 목록에 대해 24개 시간대별 합산 데이터를 반환."""
    import json as _json, urllib.parse as _up
    from datetime import date as _date, timedelta as _td

    today = _date.today()
    since = (today - _td(days=6)).isoformat()
    until = today.isoformat()
    tr = {"since": since, "until": until}
    FIELDS = _json.dumps(["impCnt", "clkCnt", "salesAmt", "ccnt", "convAmt", "avgRnk"])

    hourly: dict[str, dict] = {}
    BATCH = 10
    for i in range(0, len(camp_ids), BATCH):
        batch = camp_ids[i:i + BATCH]
        path = ("/stats?ids=" + _up.quote(",".join(batch))
                + "&fields=" + _up.quote(FIELDS)
                + "&timeRange=" + _up.quote(_json.dumps(tr))
                + "&breakdown=hh24")
        try:
            r = _get(path, customer_id=customer_id)
            data = r.get("data", []) if isinstance(r, dict) else r
            for row in data:
                for bd in (row.get("breakdowns") or []):
                    h = bd.get("name", "")
                    if not h:
                        continue
                    if h not in hourly:
                        hourly[h] = {"impressions": 0, "clicks": 0, "spend": 0,
                                     "conversions": 0, "revenue": 0, "rank_w": 0.0}
                    imp = int(bd.get("impCnt", 0) or 0)
                    hourly[h]["impressions"]  += imp
                    hourly[h]["clicks"]       += int(bd.get("clkCnt", 0) or 0)
                    hourly[h]["spend"]        += int(bd.get("salesAmt", 0) or 0)
                    hourly[h]["conversions"]  += int(bd.get("ccnt", 0) or 0)
                    hourly[h]["revenue"]      += int(bd.get("convAmt", 0) or 0)
                    hourly[h]["rank_w"]       += float(bd.get("avgRnk", 0) or 0) * imp
        except Exception:
            pass

    # 00시~01시 … 23시~00시 순서 정렬
    order = [f"{h:02d}시~{(h+1)%24:02d}시" for h in range(24)]
    result = []
    for h in order:
        ag = hourly.get(h)
        if not ag:
            result.append({"hour": h, "impressions": 0, "clicks": 0, "ctr": 0,
                           "cpc": 0, "spend": 0, "avg_rank": 0,
                           "conversions": 0, "conversion_rate": 0, "revenue": 0})
            continue
        imp = ag["impressions"]; clk = ag["clicks"]; sp = ag["spend"]
        cv  = ag["conversions"]; rv  = ag["revenue"]
        result.append({
            "hour": h, "impressions": imp, "clicks": clk,
            "ctr": round(clk / imp, 4) if imp else 0,
            "cpc": round(sp / clk) if clk else 0,
            "spend": sp,
            "avg_rank": round(ag["rank_w"] / imp, 1) if imp else 0,
            "conversions": cv,
            "conversion_rate": round(cv / clk, 4) if clk else 0,
            "revenue": rv,
        })
    return result, since, until


def _collect_keywords(camp_ids: list, time_range: dict, customer_id: str | None = None,
                      top_n: int = 30) -> list:
    """키워드별 성과 수집 (조회 전용). 광고그룹→키워드 ID 수집 후 /stats 배치 조회.
    브랜드검색 캠페인엔 키워드가 없어 자동으로 건너뛴다(파워링크 계정에서 의미 있음)."""
    MAX_KEYWORDS = 800   # 호출 폭주 방지 상한
    kw_name: dict[str, str] = {}
    try:
        for cid in camp_ids:
            if len(kw_name) >= MAX_KEYWORDS:
                break
            try:
                adgroups = _get(f"/ncc/adgroups?nccCampaignId={cid}", customer_id=customer_id)
            except Exception:
                continue
            for ag in adgroups:
                if len(kw_name) >= MAX_KEYWORDS:
                    break
                agid = ag.get("nccAdgroupId")
                if not agid:
                    continue
                try:
                    kws = _get(f"/ncc/keywords?nccAdgroupId={agid}", customer_id=customer_id)
                except Exception:
                    continue
                for kw in kws:
                    kid = kw.get("nccKeywordId")
                    if kid:
                        kw_name[kid] = kw.get("keyword", kid)
    except Exception:
        return []

    if not kw_name:
        return []

    rows = _batch_stats(list(kw_name.keys()), time_range, customer_id=customer_id)
    result = []
    for d in rows:
        m = _row_metrics(d)
        if m["impressions"] == 0 and m["clicks"] == 0:
            continue
        m["keyword"] = kw_name.get(d.get("id"), d.get("id", ""))
        result.append(m)

    result.sort(key=lambda x: -x["impressions"])
    return result[:top_n]


def _mock_stats(customer_id: str, year: int, month: int) -> dict:
    """Mock 통계 데이터 - 샘플 보고서 수치 기반"""
    import calendar, random
    random.seed(int(customer_id) * 100 + month)

    last_day = calendar.monthrange(year, month)[1]
    base_spend = random.randint(1_500_000, 4_500_000)
    base_roas  = round(random.uniform(1.5, 5.5), 2)
    impressions = random.randint(150_000, 900_000)
    clicks      = random.randint(1_200, 8_500)
    conversions = random.randint(40, 200)
    revenue     = int(base_spend * base_roas)

    daily = []
    days_spend = base_spend // last_day
    for d in range(1, last_day + 1):
        dt = date(year, month, d)
        weekdays = ["월요일","화요일","수요일","목요일","금요일","토요일","일요일"]
        daily.append({
            "date": str(dt),
            "weekday": weekdays[dt.weekday()],
            "impressions": impressions // last_day + random.randint(-500, 500),
            "clicks": clicks // last_day + random.randint(-10, 10),
            "spend": days_spend + random.randint(-50000, 50000),
            "conversions": conversions // last_day,
        })

    def _media(name, imp, clk, sp, cv, rv):
        return {
            "media_name": name,
            "impressions": imp, "clicks": clk,
            "ctr": round(clk / imp, 4) if imp else 0,
            "cpc": round(sp / clk) if clk else 0,
            "spend": sp,
            "avg_rank": round(random.uniform(1.5, 4.5), 1),
            "conversions": cv,
            "conversion_rate": round(cv / clk, 4) if clk else 0,
            "revenue": rv,
            "cpa": round(sp / cv) if cv else 0,
            "roas": round(rv / sp, 2) if sp else 0,
        }

    media_breakdown = [
        _media("네이버 쇼핑검색", int(impressions*0.45), int(clicks*0.48), int(base_spend*0.55), int(conversions*0.42), int(revenue*0.40)),
        _media("GFA 애드부스트", int(impressions*0.40), int(clicks*0.30), int(base_spend*0.30), int(conversions*0.35), int(revenue*0.38)),
        _media("GFA 카탈로그",   int(impressions*0.15), int(clicks*0.22), int(base_spend*0.15), int(conversions*0.23), int(revenue*0.22)),
    ]

    # 키워드 TOP (mock)
    kw_samples = ["브랜드명", "브랜드명 추천", "강아지 사료", "반려견 간식", "유기농 사료",
                  "수제 간식", "대형견 사료", "퍼피 사료", "관절 영양제", "치석 제거",
                  "강아지 영양제", "노견 사료", "습식 사료", "사료 추천", "강아지 용품"]
    keyword_stats = []
    for i, kw in enumerate(kw_samples):
        share = random.uniform(0.02, 0.14)
        k_imp = max(1, int(impressions * share))
        k_clk = max(1, int(clicks * share * random.uniform(0.8, 1.2)))
        k_sp  = int(base_spend * share)
        k_cv  = int(conversions * share * random.uniform(0.7, 1.3))
        k_rv  = int(revenue * share)
        keyword_stats.append({
            "keyword": kw,
            "impressions": k_imp, "clicks": k_clk,
            "ctr": round(k_clk / k_imp, 4),
            "cpc": round(k_sp / k_clk) if k_clk else 0,
            "spend": k_sp,
            "avg_rank": round(random.uniform(1.0, 5.0), 1),
            "conversions": k_cv,
            "conversion_rate": round(k_cv / k_clk, 4) if k_clk else 0,
            "revenue": k_rv,
            "cpa": round(k_sp / k_cv) if k_cv else 0,
            "roas": round(k_rv / k_sp, 2) if k_sp else 0,
        })
    keyword_stats.sort(key=lambda x: -x["impressions"])

    # 월별 히스토리 (직전 2개월 + 당월)
    monthly_total = {
        "year": year, "month": month,
        "impressions": impressions, "clicks": clicks,
        "ctr": round(clicks / impressions, 4),
        "cpc": round(base_spend / max(clicks, 1)),
        "spend": base_spend,
        "avg_rank": round(random.uniform(2.0, 4.5), 1),
        "conversions": conversions,
        "conversion_rate": round(conversions / max(clicks, 1), 4),
        "revenue": revenue,
        "cpa": round(base_spend / max(conversions, 1)),
        "roas": base_roas,
    }
    history = []
    for delta in (2, 1):
        m2, y2 = month - delta, year
        if m2 <= 0:
            m2 += 12; y2 -= 1
        f = random.uniform(0.78, 0.97)
        h_imp = int(impressions * f); h_clk = int(clicks * f)
        h_sp = int(base_spend * f); h_cv = int(conversions * f); h_rv = int(revenue * f)
        history.append({
            "year": y2, "month": m2,
            "impressions": h_imp, "clicks": h_clk,
            "ctr": round(h_clk / h_imp, 4) if h_imp else 0,
            "cpc": round(h_sp / h_clk) if h_clk else 0,
            "spend": h_sp,
            "avg_rank": round(random.uniform(2.0, 4.5), 1),
            "conversions": h_cv,
            "conversion_rate": round(h_cv / h_clk, 4) if h_clk else 0,
            "revenue": h_rv,
            "cpa": round(h_sp / h_cv) if h_cv else 0,
            "roas": round(h_rv / h_sp, 2) if h_sp else 0,
        })
    history.append(monthly_total)

    return {
        "monthly_total": monthly_total,
        "monthly_history": history,
        "media_breakdown": media_breakdown,
        "daily_stats": daily,
        "keyword_stats": keyword_stats,
    }


def _parse_stats(raw: dict, year: int, month: int) -> dict:
    """실제 API 응답을 내부 포맷으로 변환 (API 키 연동 후 구현)"""
    # TODO: Naver API 응답 구조에 맞게 파싱
    raise NotImplementedError("실제 API 파싱은 키 연동 후 구현")
