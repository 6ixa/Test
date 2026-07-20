"""
카페 게스트 구인글 → 텔레그램 알림.

사용 예:
    python main.py --once            # 한 번만 확인
    python main.py --once --debug    # 추출 결과를 자세히 출력(선택자 튜닝용)
    python main.py --once --dry-run  # 텔레그램 전송 없이 매칭만 테스트
    python main.py                   # config.yaml 의 주기(기본 60분)로 계속 실행
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime

from notifier.config import load_config
from notifier.runner import run_once


def main() -> None:
    parser = argparse.ArgumentParser(description="카페 게스트 구인글 텔레그램 알림")
    parser.add_argument("--once", action="store_true", help="한 번만 확인하고 종료")
    parser.add_argument("--debug", action="store_true", help="추출 링크/글을 자세히 출력")
    parser.add_argument("--dry-run", action="store_true", help="텔레그램 전송 없이 테스트")
    parser.add_argument("--headful", action="store_true", help="브라우저 창을 보이게 실행")
    args = parser.parse_args()

    cfg = load_config()
    headless = not args.headful

    if args.once:
        run_once(cfg, headless=headless, debug=args.debug, dry_run=args.dry_run)
        return

    interval = max(1, cfg.interval_minutes) * 60
    print(f"주기 실행 시작: {cfg.interval_minutes}분마다 확인합니다. (Ctrl+C 로 종료)")
    while True:
        try:
            run_once(cfg, headless=headless, debug=args.debug, dry_run=args.dry_run)
        except KeyboardInterrupt:
            print("\n종료합니다.")
            return
        except Exception as exc:  # noqa: BLE001
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 사이클 오류: {exc}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
