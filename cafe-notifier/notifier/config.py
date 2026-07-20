"""설정 파일(config.yaml)과 환경변수(.env)를 읽어들인다."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """의존성 없이 간단히 .env 를 읽어 os.environ 에 채운다."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # 이미 실제 환경변수로 지정돼 있으면 그것을 우선한다.
        os.environ.setdefault(key, value)


@dataclass
class Site:
    name: str
    type: str
    url: str
    link_pattern: str
    body_selector: str = ""  # 본문 영역 CSS 선택자(비면 페이지 전체 텍스트 사용)


@dataclass
class RelativeWeekend:
    """실행 시점 요일에 따라 주말 그룹에 동적으로 추가되는 상대 날짜 키워드."""
    group: str  # 상대 키워드를 추가할 그룹 이름
    today: list[str] = field(default_factory=list)
    tomorrow: list[str] = field(default_factory=list)


@dataclass
class MatchRules:
    """
    이름이 붙은 키워드 그룹(groups)과, 각 단계에서 요구할 그룹 이름 목록.
      - title_require : 1단계(제목)에서 모두 만족해야 하는 그룹 이름들
      - body_require  : 2단계(제목+본문)에서 모두 만족해야 하는 그룹 이름들
    각 그룹은 OR(단어 중 하나라도), 그룹 간에는 AND(모든 그룹) 로 판정한다.
    """
    groups: dict[str, list[str]] = field(default_factory=dict)
    title_require: list[str] = field(default_factory=list)
    body_require: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    scan_body: bool = True
    relative_weekend: "RelativeWeekend | None" = None


@dataclass
class Config:
    interval_minutes: int
    telegram_token: str
    telegram_chat_id: str
    disable_web_page_preview: bool
    match: MatchRules
    sites: list[Site]
    max_body_fetches: int  # 사이클·사이트당 본문 조회 상한(차단 방지)
    body_delay_ms: int     # 본문 조회 사이 대기(ms)


def load_config(config_path: Path | None = None) -> Config:
    _load_dotenv(ROOT / ".env")

    config_path = config_path or (ROOT / "config.yaml")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    match_raw = raw.get("match", {}) or {}

    rel_raw = match_raw.get("relative_weekend") or None
    relative = None
    if rel_raw:
        relative = RelativeWeekend(
            group=str(rel_raw.get("group", "")),
            today=[str(w) for w in rel_raw.get("today", [])],
            tomorrow=[str(w) for w in rel_raw.get("tomorrow", [])],
        )

    groups = {
        str(name): [str(w) for w in words]
        for name, words in (match_raw.get("groups", {}) or {}).items()
    }
    match = MatchRules(
        groups=groups,
        title_require=[str(g) for g in match_raw.get("title_require", [])],
        body_require=[str(g) for g in match_raw.get("body_require", [])],
        exclude=[str(w) for w in match_raw.get("exclude", [])],
        scan_body=bool(match_raw.get("scan_body", True)),
        relative_weekend=relative,
    )

    sites = [
        Site(
            name=s["name"],
            type=s["type"],
            url=s["url"],
            link_pattern=s["link_pattern"],
            body_selector=str(s.get("body_selector", "")),
        )
        for s in raw.get("sites", [])
    ]

    tele = raw.get("telegram", {}) or {}
    scraping = raw.get("scraping", {}) or {}

    return Config(
        interval_minutes=int(raw.get("interval_minutes", 60)),
        telegram_token=token,
        telegram_chat_id=chat_id,
        disable_web_page_preview=bool(tele.get("disable_web_page_preview", False)),
        match=match,
        sites=sites,
        max_body_fetches=int(scraping.get("max_body_fetches", 20)),
        body_delay_ms=int(scraping.get("body_delay_ms", 800)),
    )
