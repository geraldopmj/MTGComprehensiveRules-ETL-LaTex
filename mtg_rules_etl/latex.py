from __future__ import annotations

import re
from datetime import date

from .models import RulesDocument


STANDALONE_RULE_HEADING_RE = re.compile(r"^\d{3}\.\d+[a-z]?\.$")
EFFECTIVE_AS_OF_RE = re.compile(
    r"Effective as of [A-Za-z]+ \d{1,2}, \d{4}",
)
MONTH_NAMES = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}


def render_rules_tex(document: RulesDocument) -> str:
    lines: list[str] = [
        "\t\\chapter*{Introduction}",
        "\\addcontentsline{toc}{chapter}{Introduction}",
        (
            "\\lettrine[lines=3, depth=0]{T}{ } his "
            f"{_drop_initial_this(_escape_latex_text(document.introduction))} "
            f"These rules are effective as of {_format_effective_date(document.effective_date)}."
        ),
        "",
    ]
    if document.changes_notice:
        lines.extend([_escape_latex_text(document.changes_notice), ""])

    sections_by_group = {
        group.id: [section for section in document.sections if section.group_id == group.id]
        for group in document.groups
    }
    for group in document.groups:
        lines.append(f"\\chapter{{{_escape_latex_text(group.name)}}}")
        lines.append(f"\\setcounter{{section}}{{{group.id - 1}}}")
        for section in sections_by_group.get(group.id, []):
            lines.append(f"\\section{{{_escape_latex_text(section.name)}}}")
            for rule_line in section.rule_text.splitlines():
                rendered_line = _render_rule_line(rule_line)
                lines.append(rendered_line)
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def update_cover_effective_date(cover_tex: str, effective_date: date) -> str:
    replacement = f"Effective as of {_format_effective_date(effective_date)}"
    updated, count = EFFECTIVE_AS_OF_RE.subn(replacement, cover_tex)
    if count == 0:
        raise ValueError("No cover effective-date text was found.")
    return updated


def _render_rule_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""
    if STANDALONE_RULE_HEADING_RE.match(stripped):
        return f"\\subsection*{{{stripped}}}"
    return _escape_latex_text(stripped)


def _escape_latex_text(text: str) -> str:
    return (
        text.replace("&", r"\&")
        .replace("%", r"\%")
        .replace("#", r"\#")
        .replace("_", r"\_")
    )


def _drop_initial_this(text: str) -> str:
    if text.startswith("This "):
        return text[5:]
    return text


def _format_effective_date(value: date) -> str:
    return f"{MONTH_NAMES[value.month]} {value.day}, {value.year}"
