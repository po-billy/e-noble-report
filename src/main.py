"""
월간 광고 보고서 자동화 파이프라인 메인 실행 파일.

사용법:
  python main.py                  # 현재 디렉터리의 모든 xlsx 처리
  python main.py <파일.xlsx>      # 특정 파일 처리
  python main.py --dir <경로>     # 특정 디렉터리의 모든 xlsx 처리
"""
import argparse
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

_SRC_DIR = Path(__file__).parent
sys.path.insert(0, str(_SRC_DIR))

from comment_generator import generate_comment
from excel_generator import generate_report
from excel_reader import read_report


def process_file(xlsx_path: Path) -> Path | None:
    print(f"\n{'='*50}")
    print(f"처리 중: {xlsx_path.name}")

    # 1. 데이터 읽기
    print("  [1/3] Excel 데이터 파싱...")
    report = read_report(xlsx_path)
    print(
        f"       클라이언트: {report.client_name} / "
        f"{report.year}년 {report.month}월 / "
        f"히스토리 {len(report.monthly_history)}개월"
    )

    # 2. 코멘트 생성
    print("  [2/3] Claude API로 코멘트 생성 중...")
    comment = generate_comment(report)
    report.comment = comment
    preview = comment.replace("\n", " ")[:80]
    print(f"       미리보기: {preview}...")

    # 3. Excel 생성
    print("  [3/3] 보고서 Excel 생성...")
    out_path = generate_report(
        report=report,
        template_path=xlsx_path,
        output_dir=xlsx_path.parent / "output",
    )
    print(f"       저장 완료: {out_path.name}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="월간 광고 보고서 자동화")
    parser.add_argument("files", nargs="*", help="처리할 xlsx 파일 경로")
    parser.add_argument("--dir", help="xlsx 파일이 있는 디렉터리")
    args = parser.parse_args()

    if args.files:
        targets = [Path(f) for f in args.files]
    elif args.dir:
        targets = sorted(Path(args.dir).glob("*.xlsx"))
    else:
        # 기본: 스크립트 상위 디렉터리의 xlsx 파일
        base_dir = _SRC_DIR.parent
        targets = [
            p for p in sorted(base_dir.glob("*.xlsx"))
            if not p.name.startswith("~")  # 열려 있는 임시 파일 제외
        ]

    if not targets:
        print("처리할 xlsx 파일이 없습니다.")
        return

    print(f"총 {len(targets)}개 파일 처리 시작")
    results = []
    for p in targets:
        try:
            out = process_file(p)
            if out:
                results.append(out)
        except Exception as e:
            print(f"  [오류] {p.name}: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n완료: {len(results)}/{len(targets)}개 생성됨")
    for r in results:
        print(f"  → {r}")


if __name__ == "__main__":
    main()
