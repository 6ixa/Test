"""한 번의 확인 사이클.

2단계 필터:
  1단계(제목) — title_require(지역+날짜) 를 만족하는 '새 글'만 추린다.
  2단계(본문) — 그 글의 상세 페이지를 열어 제목+본문에 body_require
               (게스트·구인·주말·지역·시간) 가 모두 있으면 텔레그램 전송.
"""
from __future__ import annotations

import time
from datetime import datetime

from .config import Config
from .matcher import matches_full, matches_title, resolve_for_date
from .scrapers import fetch_body, scrape_site
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

    # 이번 사이클의 요일 기준으로 '오늘'/'내일' 주말 키워드를 확정한다.
    rules = resolve_for_date(cfg.match, datetime.now().date())

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

            body_fetches = 0
            for art in articles:
                if store.is_seen(site.name, art.article_id):
                    continue
                # 1단계: 제목에 지역+날짜가 없으면 본문을 열지 않는다.
                if not matches_title(art.title, rules):
                    continue

                if rules.scan_body:
                    if body_fetches >= cfg.max_body_fetches:
                        if debug:
                            print("   ⏭️  본문 조회 상한 도달 — 나머지는 다음 사이클에")
                        break
                    print(f"   🔎 본문 확인: {art.title}")
                    try:
                        body = fetch_body(
                            context, art.url, site.body_selector, debug=debug
                        )
                    except Exception as exc:  # noqa: BLE001
                        print(f"      ⚠️  본문 조회 실패(다음에 재시도): {exc}")
                        continue  # seen 처리 안 함 → 다음 사이클 재시도
                    body_fetches += 1
                    combined = f"{art.title}\n{body}"
                    # 요청 간 간격 두기(차단 방지)
                    if cfg.body_delay_ms > 0:
                        time.sleep(cfg.body_delay_ms / 1000)
                else:
                    combined = art.title

                # 2단계: 최종 판정
                if not matches_full(combined, rules):
                    if debug:
                        print("      → 본문 기준 불충족(제외)")
                    store.add(site.name, art.article_id)  # 재확인 불필요, seen 처리
                    continue

                print(f"   ✅ 최종 일치: {art.title}")
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

    if not dry_run:
        store.save()  # dry-run 은 seen 을 저장하지 않아 반복 테스트가 가능
    print(f"[{_now()}] 완료 — 새 알림 {notified}건")
    return notified
