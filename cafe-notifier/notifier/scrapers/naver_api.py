"""
네이버 새(f-e) 카페용 글 목록 수집.

DOM 을 긁으면 공지/필독만 먼저 렌더링돼 잡히는 문제가 있어, 카페 웹앱이
실제로 쓰는 글 목록 JSON API 를 로그인 세션으로 직접 호출한다.
  https://apis.naver.com/cafe-web/cafe2/ArticleListV2dot1.json
    ?search.clubid={clubid}&search.menuid={menuid}
    &search.queryType=lastArticle&search.page=1&search.perPage={n}

이 API 응답은 일반 글 목록(articleList)과 공지(notices)를 분리해 주므로,
공지/필독을 자연스럽게 제외할 수 있다. 응답 스키마가 조금 달라도 견디도록
방어적으로 파싱한다. 실패하면 호출측에서 DOM 방식으로 폴백한다.
"""
from __future__ import annotations

import json
import re

from .base import Article, PAGE_TIMEOUT_MS

API = (
    "https://apis.naver.com/cafe-web/cafe2/ArticleListV2dot1.json"
    "?search.clubid={clubid}&search.menuid={menuid}"
    "&search.queryType=lastArticle&search.page=1&search.perPage={n}&ad=false"
)


def parse_ids_from_url(url: str) -> tuple[str, str]:
    """네이버 카페 메뉴 URL 에서 (clubid, menuid) 추출."""
    club = re.search(r"/cafes/(\d+)", url)
    menu = re.search(r"/menus/(\d+)", url)
    return (club.group(1) if club else "", menu.group(1) if menu else "")


def _is_notice(entry: dict, item: dict) -> bool:
    # 여러 스키마 변형을 견디도록 알려진 공지 표식들을 모두 검사.
    if entry.get("type") and str(entry["type"]).upper() not in ("ARTICLE", "COMMENT"):
        return True  # LINE_AD / NOTICE 등 일반 글이 아님
    for key in ("headArticle", "notice", "isNotice", "noticeArticle"):
        if item.get(key) or entry.get(key):
            return True
    return False


def parse_article_list(json_text: str, clubid: str, menuid: str, name: str,
                       skip_title_contains: list[str] | None = None) -> list[Article]:
    """API JSON 문자열 → Article 목록(공지/광고 제외)."""
    skip = [s for s in (skip_title_contains or [])]
    data = json.loads(json_text)

    result = (data.get("message", {}) or {}).get("result", {}) or {}
    raw = result.get("articleList")
    if not isinstance(raw, list):
        raw = data.get("articleList") if isinstance(data.get("articleList"), list) else []

    articles: list[Article] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        item = entry.get("item") if isinstance(entry.get("item"), dict) else entry
        if _is_notice(entry, item):
            continue
        aid = item.get("articleId") or item.get("refArticleId")
        subject = item.get("subject") or item.get("title")
        if not aid or not subject:
            continue
        subject = " ".join(str(subject).split())
        if any(s and s in subject for s in skip):
            continue  # 제목에 공지/필독 표식이 든 글도 제외
        url = f"https://cafe.naver.com/f-e/cafes/{clubid}/articles/{aid}?menuid={menuid}"
        articles.append(Article(site=name, article_id=str(aid), title=subject, url=url))
    return articles


def fetch_naver_articles(context, url: str, name: str,
                         skip_title_contains: list[str] | None = None,
                         per_page: int = 50, debug: bool = False) -> list[Article]:
    """로그인 세션 페이지 안에서 네이버 글 목록 API 를 호출해 파싱한다."""
    clubid, menuid = parse_ids_from_url(url)
    if not clubid or not menuid:
        if debug:
            print(f"      [DEBUG] {name}: URL 에서 clubid/menuid 추출 실패 → DOM 폴백")
        return []

    api_url = API.format(clubid=clubid, menuid=menuid, n=per_page)
    page = context.new_page()
    try:
        # 쿠키/리퍼러 확보를 위해 먼저 해당 카페 페이지를 연다.
        page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
        page.wait_for_timeout(500)
        text = page.evaluate(
            """async (apiUrl) => {
                const r = await fetch(apiUrl, {credentials: 'include',
                    headers: {'referer': location.href, 'x-cafe-product': 'pc'}});
                return await r.text();
            }""",
            api_url,
        )
    except Exception as exc:  # noqa: BLE001
        if debug:
            print(f"      [DEBUG] {name}: API 호출 실패({exc}) → DOM 폴백")
        return []
    finally:
        page.close()

    try:
        articles = parse_article_list(text, clubid, menuid, name, skip_title_contains)
    except Exception as exc:  # noqa: BLE001
        if debug:
            print(f"      [DEBUG] {name}: API 응답 파싱 실패({exc}) → DOM 폴백")
            print(f"      [DEBUG] 응답 앞부분: {text[:200]!r}")
        return []

    if debug:
        print(f"[DEBUG] {name}(API): 일반 글 {len(articles)}개 추출(공지/필독 제외)")
        for a in articles[:20]:
            print(f"   - ({a.article_id}) {a.title[:50]}")
        if not articles:
            print("   ⚠️  API 에서 글이 안 나왔습니다. 로그인 세션/응답을 확인하세요(→ DOM 폴백).")
    return articles
