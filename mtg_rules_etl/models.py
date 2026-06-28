from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class RuleGroup:
    id: int
    name: str
    chapter_number: int


@dataclass(frozen=True)
class RuleSection:
    id: int
    group_id: int
    name: str
    rule_text: str


@dataclass(frozen=True)
class RulesDocument:
    effective_date: date
    title: str
    introduction: str
    changes_notice: str
    groups: tuple[RuleGroup, ...]
    sections: tuple[RuleSection, ...]
    source_url: str | None = None


class RulesParseError(ValueError):
    """Raised when a rules source cannot be parsed into the expected contract."""

