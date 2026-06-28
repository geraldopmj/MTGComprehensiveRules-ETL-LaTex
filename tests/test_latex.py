from datetime import date

from mtg_rules_etl.latex import render_rules_tex, update_cover_effective_date
from mtg_rules_etl.models import RuleGroup, RuleSection, RulesDocument


def test_render_rules_tex_preserves_existing_structure():
    document = RulesDocument(
        effective_date=date(2026, 6, 19),
        title="Magic: The Gathering Comprehensive Rules",
        introduction="This document is the ultimate authority for Magic: The Gathering competitive game play.",
        changes_notice="Changes may have been made to this document since its publication.",
        groups=(RuleGroup(id=100, name="Game Concepts", chapter_number=1),),
        sections=(
            RuleSection(
                id=100,
                group_id=100,
                name="General",
                rule_text="100.1.\nThese Magic rules apply to any Magic game.\n\n100.1a A two-player game begins with only two players & no teams.",
            ),
        ),
        source_url="https://media.wizards.com/rules.txt",
    )

    rendered = render_rules_tex(document)

    assert "\\chapter*{Introduction}" in rendered
    assert "These rules are effective as of June 19, 2026." in rendered
    assert "\\chapter{Game Concepts}" in rendered
    assert "\\setcounter{section}{99}" in rendered
    assert "\\section{General}" in rendered
    assert "\\subsection*{100.1.}" in rendered
    assert "two players \\& no teams" in rendered


def test_update_cover_effective_date_preserves_cover_formatting():
    cover = r"""\begin{center}
		{\Large \textbf{Magic: The Gathering}}\\[4pt]
		{\large Comprehensive Rules}\\[6pt]
		Effective as of February 27, 2026
	\end{center}

	{\large\textsc{Effective as of February 27, 2026}}\par
"""

    updated = update_cover_effective_date(cover, date(2026, 6, 19))

    assert "Effective as of February 27, 2026" not in updated
    assert "\t\tEffective as of June 19, 2026" in updated
    assert r"{\large\textsc{Effective as of June 19, 2026}}\par" in updated
    assert updated.count("Effective as of June 19, 2026") == 2
