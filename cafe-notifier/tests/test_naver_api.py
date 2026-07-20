"""네이버 글 목록 API 파서 검증 (네트워크 불필요).

    python tests/test_naver_api.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from notifier.scrapers.naver_api import parse_article_list, parse_ids_from_url  # noqa: E402

URL = "https://cafe.naver.com/f-e/cafes/10586238/menus/34"

# 일반 글 + 공지 + 광고가 섞인 가짜 응답
SAMPLE = json.dumps({
    "message": {"status": "200", "result": {
        "articleList": [
            {"type": "ARTICLE", "item": {"articleId": 1779689,
             "subject": "[경기모임] [시흥시 대야동] 07월26(일) 오전7~9시 게스트 모집"}},
            {"type": "ARTICLE", "item": {"articleId": 1779688,
             "subject": "일반 잡담 글입니다"}},
            {"type": "ARTICLE", "item": {"articleId": 500, "headArticle": True,
             "subject": "필독 카페 이용규칙"}},          # 공지 표식 → 제외
            {"type": "LINE_AD", "item": {"articleId": 999,
             "subject": "광고입니다"}},                    # 광고 → 제외
            {"type": "ARTICLE", "item": {"articleId": 501,
             "subject": "[공지] 정기모임 안내"}},          # 제목에 공지 → 제외
        ],
        "notices": [
            {"item": {"articleId": 1, "subject": "상단 고정 공지"}},  # notices 배열 → 애초에 안 읽음
        ],
    }},
})


def main():
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(("✅" if cond else "❌"), msg)
        ok = ok and cond

    club, menu = parse_ids_from_url(URL)
    check((club, menu) == ("10586238", "34"), f"URL 파싱: clubid={club}, menuid={menu}")

    arts = parse_article_list(SAMPLE, club, menu, "네이버 농심 카페",
                              skip_title_contains=["공지", "필독"])
    ids = sorted(a.article_id for a in arts)
    titles = [a.title for a in arts]
    print("  추출된 글:", [(a.article_id, a.title) for a in arts])

    check(ids == ["1779688", "1779689"], "일반 글 2개만 추출(공지/필독/광고/notices 제외)")
    check(all("공지" not in t and "필독" not in t for t in titles), "공지/필독 제목 없음")
    check(any("게스트 모집" in t for t in titles), "타깃 게스트 모집글 포함")
    check(arts[0].url.startswith("https://cafe.naver.com/f-e/cafes/10586238/articles/"),
          "글 URL 형식 정상")

    print("---")
    print("전체 통과 ✅" if ok else "실패 ❌")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
