from .base import Article, fetch_body, scrape_site
from .naver_api import fetch_naver_articles, parse_article_list


def _filter_titles(articles, skip_title_contains):
    skip = [s for s in (skip_title_contains or []) if s]
    if not skip:
        return list(articles)
    return [a for a in articles if not any(s in a.title for s in skip)]


def collect_articles(context, site, skip_title_contains=None, debug=False):
    """사이트 종류에 맞춰 글 목록을 수집한다.

    네이버: 글 목록 API 우선(공지/필독 자동 제외), 실패 시 DOM 폴백.
    그 외(다음 등): DOM 링크 추출 후 제목 기반 공지/필독 제외.
    """
    if site.type == "naver":
        arts = fetch_naver_articles(
            context, site.url, site.name, skip_title_contains, debug=debug
        )
        if arts:
            return arts
        if debug:
            print(f"   ↩️  {site.name}: API 결과 없음 → DOM 방식으로 재시도")

    arts = scrape_site(context, site.name, site.url, site.link_pattern, debug=debug)
    return _filter_titles(arts, skip_title_contains)


__all__ = [
    "Article",
    "fetch_body",
    "scrape_site",
    "fetch_naver_articles",
    "parse_article_list",
    "collect_articles",
]
