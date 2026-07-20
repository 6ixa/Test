"""한 번의 확인 사이클: 각 카페를 긁고 → 조건 매칭 → 새 글만 텔레그램 전송."""
from __future__ import annotations

from datetime import datetime

from .config import Config
from .matcher import matches
from .scrapers import scrape_site
from .scrapers.base import launch_context
from .store import SeenStore
from .telegram import Telegram


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run_once(cfg: Config, headless: bool = True, debug: bool = False,
             dry_run: bool = False) -> int:
    """새로 알린 글 개수를 반환."""
    store = SeenStore()
    telegram = None
    if not dry_run:
        if not cfg.telegram_token or not cfg.telegram_chat_id:
            raise SystemExit(
                "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 설정되지 않았습니다. "
                ".env 파일을 확인하세요. (테스트만 하려면 --dry-run 사용)"
            )
        telegram = Telegram(
            cfg.telegram_token, cfg.telegram_chat_id, cfg.disable_web_page_preview
        )

    notified = 0
    pw, context = launch_context(headless=headless)
    try:
        for site in cfg.sites:
            print(f"[{_now()}] '{site.name}' 확인 중...")
            try:
                articles = scrape_site(
                    context, site.name, site.url, site.link_pattern, debug=debug
                )
            except Exception as exc:  # noqa: BLE001
                print(f"   ⚠️  '{site.name}' 크롤링 실패: {exc}")
                continue

            for art in articles:
                if not matches(art.title, cfg.match):
                    continue
                if store.is_seen(site.name, art.article_id):
                    continue

                print(f"   ✅ 조건 일치: {art.title}")
                if dry_run:
                    print(f"      (dry-run) {art.url}")
                else:
                    try:
                        telegram.send_post(site.name, art.title, art.url)
                    except Exception as exc:  # noqa: BLE001
                        print(f"      ⚠️  텔레그램 전송 실패: {exc}")
                        continue  # 실패 시 seen 처리하지 않아 다음에 재시도

                store.add(site.name, art.article_id)
                notified += 1
    finally:
        context.close()
        pw.stop()

    store.save()
    print(f"[{_now()}] 완료 — 새 알림 {notified}건")
    return notified
