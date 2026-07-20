"""
Playwright 로그인 세션을 이용해 카페 게시판에서 글 목록을 긁어온다.

특정 카페의 HTML 구조에 강하게 의존하지 않도록, 페이지 안의 모든 <a> 링크 중
'글 상세 링크 패턴(link_pattern)'에 맞는 것을 골라 (제목, URL, 글ID)를 추출한다.
이렇게 하면 카페 UI 가 조금 바뀌어도 대체로 동작하며, 안 맞을 때는
config.yaml 의 link_pattern 만 조정하면 된다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import BrowserContext, sync_playwright

ROOT = Path(__file__).resolve().parent.parent.parent
USER_DATA_DIR = ROOT / "user-data"  # 로그인 세션(쿠키) 저장 위치

# 네이버 새 카페는 iframe 없이 SPA 로 뜨지만, 혹시 모를 프레임까지 훑기 위한 대기 시간.
PAGE_TIMEOUT_MS = 30_000


@dataclass
class Article:
    site: str
    article_id: str
    title: str
    url: str


def _extract_id(url: str) -> str:
    """URL 끝쪽의 숫자 묶음을 글 ID 로 사용."""
    nums = re.findall(r"\d+", url)
    return nums[-1] if nums else url


def launch_context(headless: bool = True) -> tuple[object, BrowserContext]:
    """영속 컨텍스트(로그인 세션 유지)를 연다. (playwright, context) 반환."""
    pw = sync_playwright().start()
    context = pw.chromium.launch_persistent_context(
        user_data_dir=str(USER_DATA_DIR),
        headless=headless,
        viewport={"width": 1280, "height": 900},
        locale="ko-KR",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
    )
    return pw, context


def _collect_links(page, link_re: re.Pattern) -> list[tuple[str, str]]:
    """현재 페이지 + 모든 프레임에서 (href, text) 목록 수집."""
    results: list[tuple[str, str]] = []
    frames = [page.main_frame, *page.frames]
    seen_frames = set()
    for frame in frames:
        if id(frame) in seen_frames:
            continue
        seen_frames.add(id(frame))
        try:
            anchors = frame.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => [e.href, (e.textContent||'').trim()])",
            )
        except Exception:
            continue
        for href, text in anchors:
            if href and link_re.search(href):
                results.append((href, text))
    return results


def fetch_body(context: BrowserContext, url: str, body_selector: str = "",
               debug: bool = False) -> str:
    """글 상세 페이지를 열어 본문 텍스트를 반환한다.

    body_selector 가 지정되면 그 영역만, 없거나 못 찾으면 페이지 전체 텍스트를
    사용한다(키워드 존재 여부만 보므로 넓게 잡아도 무방).
    """
    page = context.new_page()
    try:
        page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT_MS)
        except Exception:
            pass
        page.wait_for_timeout(1500)

        text = ""
        if body_selector:
            try:
                loc = page.locator(body_selector).first
                if loc.count() > 0:
                    text = loc.inner_text(timeout=5000)
            except Exception:
                text = ""
        if not text.strip():
            # 프레임까지 포함해 가장 긴 본문 후보를 사용(네이버는 iframe 가능).
            candidates = []
            for frame in [page.main_frame, *page.frames]:
                try:
                    candidates.append(frame.inner_text("body"))
                except Exception:
                    continue
            text = max(candidates, key=len) if candidates else ""
        if debug:
            print(f"      [DEBUG] 본문 {len(text)}자 수집: {url}")
        return text
    finally:
        page.close()


def scrape_site(context: BrowserContext, name: str, url: str, link_pattern: str,
                debug: bool = False) -> list[Article]:
    link_re = re.compile(link_pattern)
    page = context.new_page()
    try:
        page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
        # SPA/추가 로딩 대기: 네트워크가 잠잠해질 때까지 (실패해도 진행).
        try:
            page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT_MS)
        except Exception:
            pass
        page.wait_for_timeout(2000)

        pairs = _collect_links(page, link_re)
    finally:
        page.close()

    articles: dict[str, Article] = {}
    for href, text in pairs:
        full = urljoin(url, href)
        aid = _extract_id(full)
        title = " ".join(text.split())
        if not title:
            continue
        # 같은 글의 여러 링크(썸네일 등) 중 제목이 가장 긴 것을 채택.
        prev = articles.get(aid)
        if prev is None or len(title) > len(prev.title):
            articles[aid] = Article(site=name, article_id=aid, title=title, url=full)

    result = list(articles.values())
    if debug:
        print(f"[DEBUG] {name}: {len(pairs)}개 링크 후보 → {len(result)}개 글 추출")
        for a in result[:20]:
            print(f"   - ({a.article_id}) {a.title[:50]} | {a.url}")
        if not result:
            print("   ⚠️  추출된 글이 없습니다. link_pattern 을 확인하거나,")
            print("       로그인 세션이 유효한지(login.py 재실행) 점검하세요.")
    return result
