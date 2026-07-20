"""
최초 1회 실행: 브라우저 창을 띄워 네이버/다음에 '직접' 로그인한다.
로그인하면 쿠키가 user-data/ 폴더에 저장되어, 이후 main.py 가 그 세션으로
자동 크롤링한다. (아이디/비밀번호를 코드나 파일에 저장하지 않음)

    python login.py
"""
from __future__ import annotations

from notifier.scrapers.base import launch_context

LOGIN_URLS = {
    "네이버": "https://nid.naver.com/nidlogin.login",
    "다음": "https://logins.daum.net/accounts/loginform.do",
}


def main() -> None:
    print("=" * 60)
    print(" 로그인 세션 만들기")
    print("=" * 60)
    print("브라우저 창이 열립니다. 아래 순서로 진행하세요:")
    print("  1) 네이버 로그인 → 완료")
    print("  2) 새 탭 주소창에 다음(Daum) 로그인 주소를 열어 로그인")
    print(f"     ({LOGIN_URLS['다음']})")
    print("  3) 두 곳 모두 로그인했으면 이 터미널로 돌아와 Enter 를 누르세요.")
    print("-" * 60)

    pw, context = launch_context(headless=False)
    try:
        page = context.new_page()
        page.goto(LOGIN_URLS["네이버"], wait_until="domcontentloaded")
        # 다음 로그인 페이지도 미리 새 탭으로 열어준다.
        page2 = context.new_page()
        page2.goto(LOGIN_URLS["다음"], wait_until="domcontentloaded")

        input("\n두 사이트 로그인을 마쳤으면 Enter 를 누르세요... ")
        print("세션을 저장하고 브라우저를 닫습니다.")
    finally:
        context.close()
        pw.stop()

    print("✅ 완료! 이제 `python main.py --once --debug` 로 동작을 확인해보세요.")


if __name__ == "__main__":
    main()
