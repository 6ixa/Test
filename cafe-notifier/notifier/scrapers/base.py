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
USER_DATA_DIR = ROOT / "user-data"        # (구) 영속 프로필 위치
STATE_FILE = ROOT / "auth_state.json"     # 로그인 상태(쿠키+로컬스토리지) 저장 파일

# 브라우저 헤드리스에서 자동화 탐지를 줄이기 위한 UA(실사용 크롬과 유사).
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

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


def launch_context(headless: bool = True, load_state: bool = True) -> tuple[object, BrowserContext]:
    """
    브라우저 컨텍스트를 연다. (playwright, context) 반환.

    로그인 상태는 auth_state.json(storage_state) 로 저장/복원한다.
    영속 프로필(user-data)보다 세션 쿠키까지 확실히 유지되어 안정적이다.
    """
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    kwargs = dict(
        viewport={"width": 1280, "height": 900},
        locale="ko-KR",
        user_agent=USER_AGENT,
    )
    if load_state and STATE_FILE.exists():
        kwargs["storage_state"] = str(STATE_FILE)
    context = browser.new_context(**kwargs)
    return pw, context


def save_state(context) -> None:
    """현재 로그인 상태를 auth_state.json 으로 저장."""
    context.storage_state(path=str(STATE_FILE))


def _collect_anchors(page) -> tuple[list[tuple[str, str]], list[str]]:
    """현재 페이지 + 모든 프레임에서 (href, text) 전체와 프레임 URL 목록을 수집."""
    anchors: list[tuple[str, str]] = []
    frame_urls: list[str] = []
    frames = [page.main_frame, *page.frames]
    seen_frames = set()
    for frame in frames:
        if id(frame) in seen_frames:
            continue
        seen_frames.add(id(frame))
        try:
            frame_urls.append(frame.url)
        except Exception:
            pass
        try:
            got = frame.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => [e.href, (e.textContent||'').trim()])",
            )
        except Exception:
            continue
        for href, text in got:
            if href:
                anchors.append((href, text))
    return anchors, frame_urls


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


def _load_page_anchors(context, url: str) -> tuple[list[tuple[str, str]], list[str]]:
    page = context.new_page()
    try:
        page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
        # SPA/추가 로딩 대기: 네트워크가 잠잠해질 때까지 (실패해도 진행).
        try:
            page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT_MS)
        except Exception:
            pass
        page.wait_for_timeout(1500)
        # 무한 스크롤/지연 로딩(모바일 다음 등) 대비: 높이가 안 늘 때까지 스크롤.
        try:
            prev_h = 0
            for _ in range(8):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1200)
                h = page.evaluate("document.body.scrollHeight") or 0
                if h <= prev_h:
                    break
                prev_h = h
        except Exception:
            pass
        return _collect_anchors(page)
    finally:
        page.close()


def _dump_diagnostics(name: str, anchors: list[tuple[str, str]], frame_urls: list[str]) -> None:
    """링크가 안 잡혔을 때 실제 페이지 구조를 진단용으로 출력."""
    print(f"   🔬 [진단] 페이지에서 발견된 전체 링크: {len(anchors)}개")
    if frame_urls:
        print(f"   🔬 [진단] 프레임 {len(frame_urls)}개:")
        for u in frame_urls[:8]:
            print(f"        · {u}")
    # 중복 제거한 href 샘플(글 링크의 실제 형식을 파악하기 위함)
    seen, sample = set(), []
    for href, _text in anchors:
        if href not in seen:
            seen.add(href)
            sample.append(href)
        if len(sample) >= 25:
            break
    print("   🔬 [진단] href 샘플(이 형식을 보고 link_pattern 을 맞춥니다):")
    for h in sample:
        print(f"        {h}")
    if not anchors:
        print("   🔬 [진단] 링크가 0개 → 로그인 필요/페이지 미로딩/봇 차단 가능성.")


def scrape_site(context: BrowserContext, name: str, url: str, link_pattern: str,
                pages: int = 1, page_param: str = "", debug: bool = False) -> list[Article]:
    link_re = re.compile(link_pattern)

    articles: dict[str, Article] = {}
    total_anchors = 0
    last_anchors: list[tuple[str, str]] = []
    last_frames: list[str] = []
    for p in range(1, max(1, pages) + 1):
        if p == 1:
            page_url = url
        elif page_param:
            page_url = url + page_param.format(page=p)
        else:
            break  # 페이지네이션 파라미터가 없으면 1페이지만
        try:
            anchors, frame_urls = _load_page_anchors(context, page_url)
        except Exception as exc:  # noqa: BLE001
            if debug:
                print(f"   ⚠️  {name} {p}페이지 로드 실패: {exc}")
            continue
        total_anchors += len(anchors)
        last_anchors, last_frames = anchors, frame_urls
        for href, text in anchors:
            if not link_re.search(href):
                continue
            full = urljoin(page_url, href)
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
        print(f"[DEBUG] {name}(DOM): {max(1, pages)}페이지 · 전체 링크 {total_anchors}개 "
              f"→ 글 {len(result)}개 추출")
        for a in result[:20]:
            print(f"   - ({a.article_id}) {a.title[:50]} | {a.url}")
        if not result:
            print("   ⚠️  글이 추출되지 않았습니다. 아래 진단으로 link_pattern 을 확인하세요.")
        # 진단: 실제 href 형식을 항상 일부 보여줌(정규식/구조 확인용).
        _dump_diagnostics(name, last_anchors, last_frames)
    return result
