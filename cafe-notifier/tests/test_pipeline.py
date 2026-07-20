"""
네트워크·로그인·텔레그램 토큰 없이 전체 파이프라인을 검증하는 테스트.

크롤링(scrape_site)·본문(fetch_body)·브라우저(launch_context)·텔레그램(Telegram)
경계만 가짜로 바꾸고, 실제 run_once() 를 돌려서 다음을 확인한다:
  - 1단계(제목: 지역+날짜) → 통과한 글만 본문 조회
  - 2단계(제목+본문: 게스트·구인·주말·지역·시간) → 최종 알림
  - '오늘'/'내일' 의 요일 기반 판정
  - 제외어 필터
  - 중복 방지(seen) — 두 번 돌려도 한 번만 알림

    python tests/test_pipeline.py
"""
from __future__ import annotations

import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from notifier import runner  # noqa: E402
from notifier.config import load_config  # noqa: E402
from notifier.scrapers.base import Article  # noqa: E402
from notifier.store import SeenStore  # noqa: E402


# --- 가짜 경계 구현 ------------------------------------------------------

class FakeCtx:
    def close(self):
        pass


class FakePW:
    def stop(self):
        pass


class FakeTelegram:
    """실제 전송 대신 보낸 글 제목을 기록한다."""
    sent: list[str] = []

    def __init__(self, *a, **k):
        pass

    def send_post(self, site_name, title, url):
        FakeTelegram.sent.append(title)


class FakeDateTime:
    """run_once 안의 datetime.now() 를 고정 날짜로 대체."""
    fixed = datetime(2026, 7, 18, 8, 0, 0)  # 2026-07-18 = 토요일

    @classmethod
    def now(cls):
        return cls.fixed

    def strftime(self, *a, **k):
        return self.fixed.strftime(*a, **k)


# 게시판 목록(제목/URL) — 사이트 이름별
ARTICLES = {
    "S1": [
        Article("S1", "1", "부천 주말 게스트 모집합니다", "http://x/1"),   # 1단계 통과 → 본문 확인
        Article("S1", "2", "인천 토요일 정모 안내", "http://x/2"),        # 1단계 통과, 2단계 탈락(구인/게스트/시간X)
        Article("S1", "3", "게스트 구인 7시 급구", "http://x/3"),         # 1단계 탈락(지역 없음) → 본문 안 봄
        Article("S1", "4", "부평 오늘 게스트 구인", "http://x/4"),        # '오늘'=토요일 → 1단계 통과
        Article("S1", "5", "김포 토요일 게스트 구인 마감", "http://x/5"), # 제외어 '마감'
    ],
}

# 상세 페이지 본문 — 글 URL별
BODIES = {
    "http://x/1": "이번주 토요일 오전 7시 부천 상동에서 러닝 게스트 구합니다",   # 전부 충족 → 알림
    "http://x/2": "토요일 오전 10시 인천 정기모임 공지, 회비 안내",              # 시간 6~9X, 구인X → 탈락
    "http://x/4": "오늘 아침 8시 부평 게스트 구해요",                            # 전부 충족 → 알림
    "http://x/5": "토요일 6시 김포 게스트 구인",                                 # 제목에 '마감' → 제외
}

_body_fetch_log: list[str] = []


def fake_collect_articles(context, site, skip_title_contains=None, pages=1, debug=False):
    return ARTICLES.get("S1", [])


def fake_fetch_body(context, url, body_selector="", debug=False):
    _body_fetch_log.append(url)
    return BODIES.get(url, "")


def fake_launch_context(headless=True):
    return FakePW(), FakeCtx()


# --- 테스트 본체 ---------------------------------------------------------

def run_case(tmp_seen: Path):
    # 경계 몽키패치
    runner.collect_articles = fake_collect_articles
    runner.fetch_body = fake_fetch_body
    runner.launch_context = fake_launch_context
    runner.Telegram = FakeTelegram
    runner.datetime = FakeDateTime
    # seen 저장 위치를 임시파일로
    orig_default = SeenStore.__init__

    def patched_init(self, path=tmp_seen):
        orig_default(self, tmp_seen)
    runner.SeenStore = lambda: SeenStore(tmp_seen)

    cfg = load_config()
    cfg.telegram_token = "TEST-TOKEN"  # 가드 통과용(FakeTelegram 은 무시)
    cfg.telegram_chat_id = "0"
    # 사이트를 1개(S1)로 축소
    cfg.sites = [type(cfg.sites[0])(name="S1", type="naver",
                 url="http://x", link_pattern=".*", body_selector="")]

    FakeTelegram.sent.clear()
    _body_fetch_log.clear()

    runner.run_once(cfg, headless=True, debug=False, dry_run=False)
    return list(FakeTelegram.sent), list(_body_fetch_log)


def main():
    with tempfile.TemporaryDirectory() as d:
        seen = Path(d) / "seen.json"

        sent, fetched = run_case(seen)

        ok = True
        def check(cond, msg):
            nonlocal ok
            print(("✅" if cond else "❌"), msg)
            ok = ok and cond

        print("=== 1회차 (토요일 기준) ===")
        print("  알림 전송:", sent)
        print("  본문 조회:", fetched)
        check(sorted(sent) == ["부천 주말 게스트 모집합니다", "부평 오늘 게스트 구인"],
              "정확히 2건만 알림(부천 주말 / 부평 오늘=토요일)")
        check("http://x/3" not in fetched,
              "1단계 탈락(지역 없음) 글은 본문을 조회하지 않음")
        check("http://x/2" in fetched,
              "1단계 통과 글은 본문 조회(인천 토요일) — 단 2단계에서 탈락")
        check("인천 토요일 정모 안내" not in sent,
              "본문 기준 미충족 글은 알림 안 함")
        check("김포 토요일 게스트 구인 마감" not in sent,
              "제외어('마감') 글은 알림 안 함")

        # 2회차: 같은 글 → 중복 알림 없어야 함
        sent2, _ = run_case(seen)
        print("=== 2회차 (동일 글 재확인) ===")
        print("  알림 전송:", sent2)
        check(sent2 == [], "이미 알린 글은 다시 알리지 않음(중복 방지)")

        print("---")
        print("전체 통과 ✅" if ok else "실패 ❌")
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
