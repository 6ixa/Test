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


@dataclass
class RelativeWeekend:
    """실행 시점 요일에 따라 주말 그룹에 동적으로 추가되는 상대 날짜 키워드."""
    group_index: int
    today: list[str] = field(default_factory=list)
    tomorrow: list[str] = field(default_factory=list)


@dataclass
class MatchRules:
    all_groups: list[list[str]] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    relative_weekend: "RelativeWeekend | None" = None


@dataclass
class Config:
    interval_minutes: int
    telegram_token: str
    telegram_chat_id: str
    disable_web_page_preview: bool
    match: MatchRules
    sites: list[Site]


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
            group_index=int(rel_raw.get("weekend_group_index", 0)),
            today=[str(w) for w in rel_raw.get("today", [])],
            tomorrow=[str(w) for w in rel_raw.get("tomorrow", [])],
        )
    match = MatchRules(
        all_groups=[[str(w) for w in group] for group in match_raw.get("all_groups", [])],
        exclude=[str(w) for w in match_raw.get("exclude", [])],
        relative_weekend=relative,
    )

    sites = [
        Site(
            name=s["name"],
            type=s["type"],
            url=s["url"],
            link_pattern=s["link_pattern"],
        )
        for s in raw.get("sites", [])
    ]

    tele = raw.get("telegram", {}) or {}

    return Config(
        interval_minutes=int(raw.get("interval_minutes", 60)),
        telegram_token=token,
        telegram_chat_id=chat_id,
        disable_web_page_preview=bool(tele.get("disable_web_page_preview", False)),
        match=match,
        sites=sites,
    )
