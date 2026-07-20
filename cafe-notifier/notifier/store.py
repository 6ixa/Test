"""이미 알림을 보낸 글 ID 를 저장해 중복 알림을 막는다."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "seen.json"

# 사이트별로 최근 N개까지만 기억(파일 무한 증가 방지).
MAX_PER_SITE = 2000


class SeenStore:
    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = path
        self._data: dict[str, list[str]] = {}
        if path.exists():
            try:
                self._data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def is_seen(self, site: str, article_id: str) -> bool:
        return article_id in self._data.get(site, [])

    def add(self, site: str, article_id: str) -> None:
        ids = self._data.setdefault(site, [])
        if article_id not in ids:
            ids.append(article_id)
        if len(ids) > MAX_PER_SITE:
            del ids[: len(ids) - MAX_PER_SITE]

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)
