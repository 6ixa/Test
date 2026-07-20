"""텍스트(제목/본문)가 알림 조건에 맞는지 판별한다.

- 각 그룹은 OR(단어 중 하나라도 포함), 요구 그룹들 간에는 AND(모두 만족).
- 1단계는 제목에 title_require 그룹, 2단계는 제목+본문에 body_require 그룹을 적용.
"""
from __future__ import annotations

from datetime import date

from .config import MatchRules


def _normalize(text: str) -> str:
    # 소문자화만 하고 공백은 유지한다.
    # (공백을 제거하면 "부평 일요일" → "부평일요일" 처럼 인접 단어가 붙어
    #  제외어 "평일" 같은 엉뚱한 부분일치가 생기므로 유지한다.)
    return text.lower()


def resolve_for_date(rules: MatchRules, today: date) -> MatchRules:
    """
    상대 날짜 키워드('오늘'/'내일')를 '실행 시점 요일'에 따라 주말 그룹에 넣는다.
      - '오늘'  : 오늘이 토(5)/일(6) 일 때만 주말로 인정
      - '내일'  : 내일이 토/일(=오늘이 금(4)/토(5)) 일 때만 주말로 인정
    조건에 맞지 않으면 상대 키워드를 넣지 않아, 평일에 올라온 '오늘' 글은
    주말 조건을 충족하지 못한다.
    """
    rel = rules.relative_weekend
    if not rel or rel.group not in rules.groups:
        return rules

    weekday = today.weekday()  # 월=0 ... 토=5, 일=6
    extra: list[str] = []
    if weekday in (5, 6):        # 오늘이 주말
        extra += rel.today
    if weekday in (4, 5):        # 내일이 주말 (오늘 금/토)
        extra += rel.tomorrow
    if not extra:
        return rules

    new_groups = {name: list(words) for name, words in rules.groups.items()}
    new_groups[rel.group] = new_groups[rel.group] + extra
    return MatchRules(
        groups=new_groups,
        title_require=list(rules.title_require),
        body_require=list(rules.body_require),
        exclude=list(rules.exclude),
        scan_body=rules.scan_body,
        relative_weekend=rel,
    )


def _has_excluded(norm: str, rules: MatchRules) -> bool:
    return any(_normalize(word) in norm for word in rules.exclude)


def _group_hit(norm: str, rules: MatchRules, group_name: str) -> bool:
    words = rules.groups.get(group_name, [])
    return any(_normalize(word) in norm for word in words)


def matches(text: str, rules: MatchRules, require: list[str]) -> bool:
    """require 에 나열된 모든 그룹이 text 에 있고, 제외어가 없으면 True."""
    if not require:
        return False  # 요구 그룹이 없으면 무분별 알림 방지
    norm = _normalize(text)
    if _has_excluded(norm, rules):
        return False
    return all(_group_hit(norm, rules, g) for g in require)


def matches_title(text: str, rules: MatchRules) -> bool:
    """1단계: 제목 선별."""
    return matches(text, rules, rules.title_require)


def matches_full(text: str, rules: MatchRules) -> bool:
    """2단계: 제목+본문 최종 판정."""
    return matches(text, rules, rules.body_require)
