"""글 제목/미리보기 텍스트가 알림 조건에 맞는지 판별한다."""
from __future__ import annotations

from .config import MatchRules


def _normalize(text: str) -> str:
    # 공백 제거 + 소문자화 → "게스트 구인" 과 "게스트구인" 을 동일 취급
    return "".join(text.split()).lower()


def matches(text: str, rules: MatchRules) -> bool:
    """
    조건: 모든 그룹(all_groups)에서 각각 최소 1개 단어가 포함되고,
          제외 단어(exclude)는 하나도 없어야 한다.
    """
    norm = _normalize(text)

    for word in rules.exclude:
        if _normalize(word) in norm:
            return False

    for group in rules.all_groups:
        if not any(_normalize(word) in norm for word in group):
            return False

    # 그룹이 하나도 없으면(설정 실수) 무분별 알림을 막기 위해 False.
    return bool(rules.all_groups)
