"""
최초 1회(또는 세션 만료 시) 실행: 브라우저 창을 띄워 네이버/다음에 '직접'
로그인한다. 로그인하면 쿠키가 user-data/ 에 저장되어 이후 자동 크롤링에 쓰인다.
(아이디/비밀번호를 코드나 파일에 저장하지 않음)

    python login.py

두 카페의 '실제 게시판'을 열어주므로, 로그인 후 **일반 글 목록이 보이는지**
직접 확인하세요. 특히 다음(Daum)은 회원 전용이라 로그인 + 카페 가입이 안 되어
있으면 공지만 보입니다.
"""
from __future__ import annotations

import re

from notifier.config import load_config
from notifier.scrapers.base import launch_context

LOGIN_URLS = {
    "naver": "https://nid.naver.com/nidlogin.login",
    "daum": "https://logins.daum.net/accounts/loginform.do",
}


def _verify(context, cfg) -> None:
    """로그인/가입 상태를 게시판에서 직접 확인해 출력한다."""
    print("\n" + "=" * 64)
    print(" 로그인 상태 확인")
    print("=" * 64)
    for site in cfg.sites:
        page = context.new_page()
        try:
            page.goto(site.url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
            hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
        except Exception as exc:  # noqa: BLE001
            print(f"  [{site.type}] {site.name}: 확인 실패({exc})")
            page.close()
            continue
        page.close()

        login_links = [h for h in hrefs if "loginform.do" in h or "nidlogin.login" in h]
        member_links = [h for h in hrefs if "_newmember" in h]
        if site.type == "naver":
            # 네이버는 API 로 동작하므로 DOM 글 링크는 참고만.
            note = "❌ 로그인 안 됨" if login_links else "✅ 로그인된 것으로 보임(API 사용)"
            print(f"  [naver] {site.name}: {note}")
            continue

        arts = [h for h in hrefs if re.search(r"/dongarry/[A-Za-z0-9]+/\d+", h)
                and "IVII" not in h]  # IVII = 공지 게시판
        if login_links:
            print(f"  [daum] {site.name}: ❌ 아직 로그인 안 됨 → 이 창에서 다시 로그인 필요")
        elif member_links:
            print(f"  [daum] {site.name}: ⚠️ 카페 미가입으로 보임 → '동아리농구방' 가입 필요")
        else:
            print(f"  [daum] {site.name}: ✅ 로그인/가입 정상으로 보임 "
                  f"(글 링크 {len(arts)}개 발견)")


def main() -> None:
    cfg = load_config()

    print("=" * 64)
    print(" 로그인 세션 만들기")
    print("=" * 64)
    print("브라우저 창이 열립니다. 각 탭에서 로그인한 뒤, 그 카페 게시판 탭에서")
    print("**일반 게스트 글 목록이 보이는지** 꼭 확인하세요.")
    print("  · 네이버: 로그인하면 글이 보입니다.")
    print("  · 다음:  로그인 + '동아리농구방' 카페 가입이 되어 있어야 글이 보입니다.")
    print("           (공지만 보이면 = 아직 로그인/가입 안 된 상태)")
    print("-" * 64)

    pw, context = launch_context(headless=False)
    try:
        # 각 사이트의 로그인 페이지 + 실제 게시판을 함께 열어준다.
        opened_login = set()
        for site in cfg.sites:
            login_url = LOGIN_URLS.get(site.type)
            if login_url and site.type not in opened_login:
                context.new_page().goto(login_url, wait_until="domcontentloaded")
                opened_login.add(site.type)
            try:
                context.new_page().goto(site.url, wait_until="domcontentloaded")
            except Exception as exc:  # noqa: BLE001
                print(f"  ({site.name} 게시판 열기 실패: {exc})")

        print("\n각 카페에 로그인하고, 게시판 탭에서 일반 글이 보이는지 확인했으면")
        input("이 터미널로 돌아와 Enter 를 누르세요... ")
        _verify(context, cfg)
        print("\n세션을 저장하고 브라우저를 닫습니다.")
    finally:
        context.close()
        pw.stop()

    print("✅ 완료! 이제 `python diagnose.py` 로 두 카페가 잘 읽히는지 확인해보세요.")


if __name__ == "__main__":
    main()
