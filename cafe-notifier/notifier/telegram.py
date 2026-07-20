"""텔레그램 봇으로 알림 메시지를 전송한다."""
from __future__ import annotations

import html

import requests

API = "https://api.telegram.org/bot{token}/sendMessage"


class Telegram:
    def __init__(self, token: str, chat_id: str, disable_preview: bool = False):
        self.token = token
        self.chat_id = chat_id
        self.disable_preview = disable_preview

    def send(self, text: str) -> None:
        resp = requests.post(
            API.format(token=self.token),
            json={
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": self.disable_preview,
            },
            timeout=20,
        )
        resp.raise_for_status()

    def send_post(self, site_name: str, title: str, url: str) -> None:
        safe_title = html.escape(title)
        safe_site = html.escape(site_name)
        text = (
            f"🔔 <b>새 게스트 구인글</b>\n"
            f"📍 {safe_site}\n"
            f"📝 {safe_title}\n"
            f"🔗 {html.escape(url)}"
        )
        self.send(text)
