"""대량 광고주 보고서B 배치 러너.

흐름:  로스터(SoT) → accounts.json 동기화 → 활성 계정마다 보고서B 생성 → 실행로그

사용법:
    # 로스터 전체(활성·키입력된 계정)로 2026년 6월 보고서 생성
    python batch_report.py 2026 6

    # 특정 광고주만 (이름 부분일치, 콤마 구분)
    python batch_report.py 2026 6 --only 린드스트롬,프로디지

    # 동기화 건너뛰고 현재 accounts.json 그대로 사용
    python batch_report.py 2026 6 --no-sync

    # mock 데이터로 포맷만 확인(API 호출 없음)
    python batch_report.py 2026 6 --mock

먼저 로스터를 준비하세요:
    python -m src.roster template   # roster.xlsx 생성(신규 5개 채워짐)
    #  → roster.xlsx 의 api_key/api_secret 칸을 채운 뒤:
    python batch_report.py 2026 6
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))


def _parse_args(argv: list[str]) -> dict:
    pos = [a for a in argv if not a.startswith("--")]
    opts = {a for a in argv if a.startswith("--")}
    only = None
    if "--only" in argv:
        i = argv.index("--only")
        if i + 1 < len(argv):
            only = [s.strip() for s in argv[i + 1].split(",") if s.strip()]
    return {
        "year": int(pos[0]) if len(pos) > 0 else 2026,
        "month": int(pos[1]) if len(pos) > 1 else 6,
        "only": only,
        "no_sync": "--no-sync" in opts,
        "mock": "--mock" in opts,
    }


def main(argv: list[str]) -> int:
    cfg = _parse_args(argv)

    # mock 여부는 반드시 v2_report/naver_searchad import 전에 확정.
    import os
    os.environ["NAVER_MOCK"] = "true" if cfg["mock"] else "false"

    from src.roster import load_roster, sync_accounts_json

    roster = load_roster()

    # 1) 동기화: 로스터 → accounts.json (수집기가 읽는 키 세트)
    if not cfg["mock"] and not cfg["no_sync"]:
        sync_accounts_json(roster)

    # 2) 대상 선정: 활성 + 키 입력된 계정 (+ --only 필터)
    targets = []
    for r in roster:
        if not r.get("active", True):
            continue
        if not cfg["mock"] and not (r.get("api_key") and r.get("api_secret")):
            continue
        if cfg["only"] and not any(o in (r.get("name") or "") or o == r["customer_id"]
                                   for o in cfg["only"]):
            continue
        targets.append(r)

    if not targets:
        print("❌ 대상 계정이 없습니다. 로스터의 활성/키입력/--only 조건을 확인하세요.")
        return 1

    y, m = cfg["year"], cfg["month"]
    mode = "MOCK" if cfg["mock"] else "실 API"
    print(f"\n=== 배치 시작 [{mode}] {y}년 {m}월 · 대상 {len(targets)}개 ===")
    for r in targets:
        print(f"   · {r['customer_id']:>9}  {r.get('name','')}")
    print()

    # 3) 지연 import (accounts.json 동기화 후 로드되어야 계정 키가 반영됨)
    from v2_report import generate_v2_report

    out_root = _ROOT / "output" / f"batch_{y}{m:02d}"
    out_root.mkdir(parents=True, exist_ok=True)

    results = []
    for idx, r in enumerate(targets, 1):
        cid = r["customer_id"]
        name = r.get("name") or cid
        t0 = time.time()
        print(f"[{idx}/{len(targets)}] {name} (customer={cid}) 생성 중...", flush=True)
        try:
            out = generate_v2_report(cid, y, m, client_name=name, output_dir=out_root)
            ok = Path(out).exists() and Path(out).stat().st_size > 0
            results.append({
                "customer_id": cid, "name": name, "status": "ok" if ok else "empty",
                "output": str(out), "marketer": r.get("marketer", ""),
                "email": r.get("email", ""), "seconds": round(time.time() - t0, 1),
            })
            print(f"    ✅ {out}  ({results[-1]['seconds']}s)")
        except Exception as e:
            results.append({
                "customer_id": cid, "name": name, "status": "error",
                "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc(),
                "marketer": r.get("marketer", ""), "email": r.get("email", ""),
                "seconds": round(time.time() - t0, 1),
            })
            print(f"    ❌ 실패: {type(e).__name__}: {e}")

    # 4) 실행 로그 저장 + 요약
    log = {
        "year": y, "month": m, "mode": mode, "total": len(results),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "failed": sum(1 for r in results if r["status"] != "ok"),
        "results": results,
    }
    log_path = out_root / "run_log.json"
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== 배치 완료: 성공 {log['ok']} / 실패 {log['failed']} / 전체 {log['total']} ===")
    for r in results:
        mark = "✅" if r["status"] == "ok" else "❌"
        extra = "" if r["status"] == "ok" else f"  ← {r.get('error','')}"
        print(f"  {mark} {r['name']}{extra}")
    print(f"\n실행 로그: {log_path}")
    print(f"산출물 폴더: {out_root}")
    return 0 if log["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
