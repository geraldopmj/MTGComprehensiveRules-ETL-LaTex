from __future__ import annotations

import re
from datetime import datetime

from .models import RuleGroup, RuleSection, RulesDocument, RulesParseError


EFFECTIVE_DATE_RE = re.compile(
    r"These rules are effective as of\s+([A-Za-z]+ \d{1,2}, \d{4})\.",
    re.IGNORECASE,
)
CHAPTER_RE = re.compile(r"^([1-9])\. (.+)$")
SECTION_RE = re.compile(r"^([1-9]\d{2})\. (.+)$")
TOP_LEVEL_RULE_WITH_TEXT_RE = re.compile(r"^(\d{3}\.\d+\.)\s+(.+)$")
LEGACY_CHAPTER_RE = re.compile(r"^\\chapter\{(.+)\}$")
LEGACY_SETCOUNTER_RE = re.compile(r"^\\setcounter\{section\}\{(\d+)\}$")
LEGACY_SECTION_RE = re.compile(r"^\\section\{(.+)\}$")
LEGACY_SUBSECTION_RE = re.compile(r"^\\subsection\*\{([^}]+)\}$")


def parse_official_rules_txt(text: str, source_url: str | None = None) -> RulesDocument:
    normalized = _normalize_text(text)
    lines = [line.strip() for line in normalized.splitlines()]
    effective_date = _extract_effective_date(normalized)
    title = _first_non_empty(lines)
    introduction, changes_notice = _parse_official_intro(lines)
    body_start, body_end = _find_official_body(lines)
    groups, sections = _parse_official_body(lines[body_start:body_end])
    document = RulesDocument(
        effective_date=effective_date,
        title=title,
        introduction=introduction,
        changes_notice=changes_notice,
        groups=tuple(groups),
        sections=tuple(sections),
        source_url=source_url,
    )
    _validate_document(document)
    return document


def parse_legacy_rules_tex(text: str, source_url: str | None = None) -> RulesDocument:
    normalized = _normalize_text(text)
    lines = [line.rstrip() for line in normalized.splitlines()]
    effective_date = _extract_effective_date(normalized)
    introduction, changes_notice = _parse_legacy_intro(lines)
    groups, sections = _parse_legacy_body(lines)
    document = RulesDocument(
        effective_date=effective_date,
        title="Magic: The Gathering Comprehensive Rules",
        introduction=introduction,
        changes_notice=changes_notice,
        groups=tuple(groups),
        sections=tuple(sections),
        source_url=source_url,
    )
    _validate_document(document)
    return document


def _normalize_text(text: str) -> str:
    return text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")


def _extract_effective_date(text: str):
    match = EFFECTIVE_DATE_RE.search(text)
    if not match:
        raise RulesParseError("Could not find the effective date phrase.")
    return datetime.strptime(match.group(1), "%B %d, %Y").date()


def _first_non_empty(lines: list[str]) -> str:
    for line in lines:
        if line.strip():
            return line.strip()
    raise RulesParseError("Source is empty.")


def _parse_official_intro(lines: list[str]) -> tuple[str, str]:
    intro_idx = _find_line(lines, "Introduction")
    contents_idx = _find_line(lines, "Contents", start=intro_idx + 1)
    intro_block = [line for line in lines[intro_idx + 1 : contents_idx] if line]
    if not intro_block:
        raise RulesParseError("Official source has no introduction block.")

    changes_idx = next(
        (i for i, line in enumerate(intro_block) if line.startswith("Changes may have been made")),
        None,
    )
    if changes_idx is None:
        return _join_paragraphs(intro_block), ""
    introduction = _join_paragraphs(intro_block[:changes_idx])
    changes_notice = _join_paragraphs(intro_block[changes_idx:])
    return introduction, changes_notice


def _find_official_body(lines: list[str]) -> tuple[int, int]:
    contents_idx = _find_line(lines, "Contents")
    credits_idx = _find_line(lines, "Credits", start=contents_idx + 1)
    body_start = next(
        (i for i in range(credits_idx + 1, len(lines)) if CHAPTER_RE.match(lines[i])),
        None,
    )
    if body_start is None:
        raise RulesParseError("Could not find the numbered rules body.")
    body_end = next(
        (i for i in range(body_start + 1, len(lines)) if lines[i] == "Glossary"),
        len(lines),
    )
    return body_start, body_end


def _parse_official_body(lines: list[str]) -> tuple[list[RuleGroup], list[RuleSection]]:
    groups: list[RuleGroup] = []
    sections: list[RuleSection] = []
    current_group: RuleGroup | None = None
    current_section_id: int | None = None
    current_section_name: str | None = None
    current_section_group_id: int | None = None
    buffer: list[str] = []

    def flush_section() -> None:
        nonlocal current_section_id, current_section_name, current_section_group_id, buffer
        if current_section_id is None or current_section_name is None:
            buffer = []
            return
        rule_text = "\n".join(buffer).strip()
        sections.append(
            RuleSection(
                id=current_section_id,
                group_id=current_section_group_id or (current_section_id // 100) * 100,
                name=current_section_name,
                rule_text=rule_text,
            )
        )
        current_section_id = None
        current_section_name = None
        current_section_group_id = None
        buffer = []

    for raw_line in lines:
        line = raw_line.strip()
        chapter_match = CHAPTER_RE.match(line)
        if chapter_match:
            flush_section()
            chapter_number = int(chapter_match.group(1))
            current_group = RuleGroup(
                id=chapter_number * 100,
                name=chapter_match.group(2).strip(),
                chapter_number=chapter_number,
            )
            groups.append(current_group)
            continue

        section_match = SECTION_RE.match(line)
        if section_match:
            flush_section()
            current_section_id = int(section_match.group(1))
            current_section_name = section_match.group(2).strip()
            current_section_group_id = current_group.id if current_group else (current_section_id // 100) * 100
            continue

        if current_section_id is not None:
            _append_official_rule_line(buffer, line)

    flush_section()
    return groups, sections


def _parse_legacy_intro(lines: list[str]) -> tuple[str, str]:
    introduction = ""
    changes_notice = ""
    for line in lines:
        stripped = line.strip()
        if "\\lettrine" in stripped:
            introduction = re.sub(
                r"^\\lettrine\[.*?\]\{T\}\{\s*\}\s*his",
                "This",
                stripped,
            )
            introduction = EFFECTIVE_DATE_RE.sub("", introduction).strip()
        elif stripped.startswith("Changes may have been made"):
            changes_notice = _unescape_latex_text(stripped)
        if introduction and changes_notice:
            break
    if not introduction:
        raise RulesParseError("Legacy LaTeX source has no introduction.")
    return _unescape_latex_text(introduction), changes_notice


def _parse_legacy_body(lines: list[str]) -> tuple[list[RuleGroup], list[RuleSection]]:
    groups_by_id: dict[int, RuleGroup] = {}
    group_order: list[int] = []
    sections: list[RuleSection] = []
    pending_group_name: str | None = None
    current_section_name: str | None = None
    current_section_id: int | None = None
    section_counter: int | None = None
    buffer: list[str] = []

    def ensure_group(group_id: int, name: str | None) -> None:
        if group_id in groups_by_id:
            return
        groups_by_id[group_id] = RuleGroup(
            id=group_id,
            name=name or f"Rules {group_id}",
            chapter_number=group_id // 100,
        )
        group_order.append(group_id)

    def flush_section() -> None:
        nonlocal current_section_name, current_section_id, buffer
        if current_section_id is not None and current_section_name is not None:
            group_id = (current_section_id // 100) * 100
            ensure_group(group_id, pending_group_name)
            sections.append(
                RuleSection(
                    id=current_section_id,
                    group_id=group_id,
                    name=current_section_name,
                    rule_text="\n".join(buffer).strip(),
                )
            )
        current_section_name = None
        current_section_id = None
        buffer = []

    for raw_line in lines:
        line = raw_line.strip()
        chapter_match = LEGACY_CHAPTER_RE.match(line)
        if chapter_match:
            flush_section()
            pending_group_name = _unescape_latex_text(chapter_match.group(1).strip())
            continue

        counter_match = LEGACY_SETCOUNTER_RE.match(line)
        if counter_match:
            section_counter = int(counter_match.group(1))
            continue

        section_match = LEGACY_SECTION_RE.match(line)
        if section_match:
            flush_section()
            current_section_name = _unescape_latex_text(section_match.group(1).strip())
            if section_counter is not None:
                section_counter += 1
                current_section_id = section_counter
            continue

        subsection_match = LEGACY_SUBSECTION_RE.match(line)
        if subsection_match and current_section_name:
            heading = subsection_match.group(1).strip()
            if current_section_id is None:
                current_section_id = int(heading.split(".", 1)[0])
                section_counter = current_section_id
            buffer.append(heading)
            continue

        if current_section_name is not None:
            buffer.append(_unescape_latex_text(line))

    flush_section()
    return [groups_by_id[group_id] for group_id in group_order], sections


def _find_line(lines: list[str], expected: str, start: int = 0) -> int:
    for i in range(start, len(lines)):
        if lines[i].strip() == expected:
            return i
    raise RulesParseError(f"Could not find line: {expected}")


def _join_paragraphs(lines: list[str]) -> str:
    return "\n\n".join(line.strip() for line in lines if line.strip())


def _append_official_rule_line(buffer: list[str], line: str) -> None:
    match = TOP_LEVEL_RULE_WITH_TEXT_RE.match(line)
    if not match:
        buffer.append(line)
        return
    buffer.append(match.group(1))
    buffer.append(match.group(2))


def _unescape_latex_text(text: str) -> str:
    return (
        text.replace(r"\&", "&")
        .replace(r"\%", "%")
        .replace(r"\#", "#")
        .replace(r"\_", "_")
    )


def _validate_document(document: RulesDocument) -> None:
    if not document.groups:
        raise RulesParseError("Parsed document has no rule groups.")
    if not document.sections:
        raise RulesParseError("Parsed document has no rule sections.")
    group_ids = {group.id for group in document.groups}
    for section in document.sections:
        if section.group_id not in group_ids:
            raise RulesParseError(f"Rule section {section.id} references missing group {section.group_id}.")
