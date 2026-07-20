"""
스크래핑 진단 도구.

네이버/다음에서 글 목록을 실제로 어떻게 가져오는지 자세히 출력한다.
로그인 세션이 필요하므로 login.py 를 먼저 실행해 두어야 한다.

    python diagnose.py                # 기본 글번호(1779689) 확인
    python diagnose.py 1779689        # 특정 글번호가 잡히는지 확인

출력 전체를 복사해서 개발자에게 전달하면 원인을 바로 진단할 수 있다.
(응답에 게시판 공개 목록 외 민감정보는 포함되지 않음)
"""
from __future__ import annotations

import sys

from notifier.config import load_config
from notifier.scrapers import collect_articles
from notifier.scrapers.base import launch_context
from notifier.scrapers.naver_api import API, parse_ids_from_url

DEFAULT_TARGET = "1779689"


def _check_login_and_api(ctx, site):
    page = ctx.new_page()
    try:
        try:
            page.goto(site.url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1500)
        except Exception as exc:  # noqa: BLE001
            print(f"   ⚠️  페이지 이동 실패: {exc}")
            return
        # 로그인 상태 추정: 페이지 안에 '로그인 페이지로 가는 링크'가 있으면
        # 로그인 필요(비회원) 상태일 가능성이 높다.
        try:
            login_links = page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => e.href).filter(h => "
                "h.includes('loginform.do') || h.includes('nidlogin.login') "
                "|| h.includes('accounts/loginform'))",
            )
            if login_links:
                print(f"   ⚠️  로그인 안내 링크 발견 → 로그인/가입 필요 가능성 높음")
                print(f"        예: {login_links[0]}")
            else:
                print("   로그인 상태: 로그인 링크 없음(정상일 가능성 높음)")
        except Exception:
            pass
        # 네이버는 원시 API 응답을 확인
        if site.type == "naver":
            club, menu = parse_ids_from_url(site.url)
            api_url = API.format(clubid=club, menuid=menu, page=1, n=10)
            print(f"   API URL: {api_url}")
            raw = page.evaluate(
                """async (u) => {
                    try {
                        const r = await fetch(u, {credentials:'include',
                            headers:{'referer':location.href,'x-cafe-product':'pc'}});
                        const t = await r.text();
                        return r.status + ' | ' + t.slice(0, 700);
                    } catch (e) { return 'FETCH-ERROR ' + e; }
                }""",
                api_url,
            )
            print("   API 응답(status | 앞부분 700자):")
            print("   " + str(raw).replace("\n", " "))
    finally:
        page.close()


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET
    cfg = load_config()
    print(f"확인할 글번호: {target}\npages={cfg.pages}, skip_title_contains={cfg.skip_title_contains}")

    pw, ctx = launch_context(headless=True)
    try:
        for site in cfg.sites:
            print("\n" + "=" * 64)
            print(f"[{site.type}] {site.name}")
            print("URL:", site.url)
            _check_login_and_api(ctx, site)
            print("-" * 64)
            arts = collect_articles(ctx, site, cfg.skip_title_contains,
                                    pages=cfg.pages, debug=True)
            print(f"→ 최종 추출 글 수: {len(arts)}")
            hit = [a for a in arts if a.article_id == target]
            print(f"→ 글번호 {target} 잡힘? {'예 ✅' if hit else '아니오 ❌'}")
            if arts:
                print("→ 추출된 제목 샘플:")
                for a in arts[:10]:
                    print(f"     ({a.article_id}) {a.title[:45]}")
    finally:
        ctx.close()
        pw.stop()
    print("\n완료. 위 출력 전체를 복사해서 전달하세요.")


if __name__ == "__main__":
    main()
