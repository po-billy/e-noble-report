"""버전B(파워링크) 보고서 로컬 생성 테스트.

사용법:
    # mock 데이터로 생성 (API 호출 없음, 포맷 확인용)
    python test_v2.py 2026 5 테스트

    # 실제 네이버 API로 생성 (accounts.json 계정 필요)
    python test_v2.py 2026 5 에듀윌 --live --customer 1234567

인자:
    year month name  : 보고 연/월, 클라이언트 이름
    --live           : 실 API 사용 (기본은 mock)
    --customer <id>  : 네이버 customer_id (여러 개는 + 로 연결)
"""
import os
import sys
from pathlib import Path

# --live 없으면 mock 강제 (반드시 v2_report import 전에 설정)
if "--live" not in sys.argv:
    os.environ["NAVER_MOCK"] = "true"

sys.path.insert(0, str(Path(__file__).parent / "src"))

from v2_report import generate_v2_report, MOCK_MODE  # noqa: E402


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    year = int(args[0]) if len(args) > 0 else 2026
    month = int(args[1]) if len(args) > 1 else 5
    name = args[2] if len(args) > 2 else "테스트"

    customer = "mock"
    if "--customer" in sys.argv:
        customer = sys.argv[sys.argv.index("--customer") + 1]

    mode = "실 API" if not MOCK_MODE else "MOCK"
    print(f"[{mode}] {year}년 {month}월 · {name} · customer={customer}")
    out = generate_v2_report(customer, year, month, client_name=name)
    print(f"✅ 생성 완료: {out}")


if __name__ == "__main__":
    main()
