"""
카페 게스트 구인글 → 텔레그램 알림.

사용 예:
    python main.py --test            # 텔레그램 연결만 확인(테스트 메시지 전송)
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
from notifier.telegram import Telegram


def _run_test(cfg) -> None:
    """봇 토큰 + chat_id 로 테스트 메시지를 보내 연결을 확인한다."""
    if not cfg.telegram_token:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN 이 설정되지 않았습니다. .env 파일에 봇 토큰을 넣으세요.\n"
            "  (예: cp .env.example .env 후 편집)"
        )
    if not cfg.telegram_chat_id:
        raise SystemExit(
            "chat_id 가 없습니다. config.yaml 의 telegram.chat_id 또는 "
            ".env 의 TELEGRAM_CHAT_ID 를 확인하세요."
        )
    tg = Telegram(cfg.telegram_token, cfg.telegram_chat_id, cfg.disable_web_page_preview)
    print(f"chat_id={cfg.telegram_chat_id} 로 테스트 메시지 전송 중...")
    tg.send(
        "✅ <b>카페 알림 봇 연결 성공</b>\n"
        "이 메시지가 보이면 토큰과 chat_id 설정이 정상입니다."
    )
    print("전송 완료! 텔레그램에 메시지가 도착했는지 확인하세요.")


def main() -> None:
    parser = argparse.ArgumentParser(description="카페 게스트 구인글 텔레그램 알림")
    parser.add_argument("--test", action="store_true", help="텔레그램 연결 확인(테스트 메시지 전송)")
    parser.add_argument("--once", action="store_true", help="한 번만 확인하고 종료")
    parser.add_argument("--debug", action="store_true", help="추출 링크/글을 자세히 출력")
    parser.add_argument("--dry-run", action="store_true", help="텔레그램 전송 없이 테스트")
    parser.add_argument("--headful", action="store_true", help="브라우저 창을 보이게 실행")
    args = parser.parse_args()

    cfg = load_config()
    headless = not args.headful

    if args.test:
        _run_test(cfg)
        return

    # 스크래핑 경로에서만 Playwright 를 불러온다(--test 는 브라우저 불필요).
    from notifier.runner import run_once

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
