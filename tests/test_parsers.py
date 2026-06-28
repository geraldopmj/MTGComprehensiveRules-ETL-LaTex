from datetime import date

from mtg_rules_etl.parsers import parse_legacy_rules_tex, parse_official_rules_txt


OFFICIAL_SAMPLE = """\ufeffMagic: The Gathering Comprehensive Rules

These rules are effective as of June 19, 2026.

Introduction

This document is the ultimate authority for Magic: The Gathering competitive game play.

Changes may have been made to this document since its publication.

Contents

1. Game Concepts
100. General
101. The Magic Golden Rules
2. Parts of a Card
200. General
Glossary
Credits

1. Game Concepts
100. General
100.1. These Magic rules apply to any Magic game.

100.1a A two-player game begins with only two players.

101. The Magic Golden Rules
101.1. Whenever a card's text directly contradicts these rules, the card takes precedence.

2. Parts of a Card
200. General
200.1. The parts of a card are name, mana cost, illustration, and text box.

6. Spells, Abilities, and Effects
600. General

Glossary
"""


LEGACY_SAMPLE = r"""	\chapter*{Introduction}
\addcontentsline{toc}{chapter}{Introduction}
\lettrine[lines=3, depth=0]{T}{ } his document is the ultimate authority for Magic: The Gathering competitive game play. These rules are effective as of February 27, 2026.

Changes may have been made to this document since its publication.

\chapter{Game Concepts}
\setcounter{section}{99}
\section{General}
\subsection*{100.1.}
These Magic rules apply to any Magic game.

100.1a A two-player game begins with only two players.

\section{The Magic Golden Rules}
\subsection*{101.1.}
Whenever a card's text directly contradicts these rules, the card takes precedence.

\chapter{Spells, Abilities, and Effects}
\setcounter{section}{599}
\section{General}
\section{Casting Spells}
\subsection*{601.1.}
Previously, the action of casting a spell was referred to as playing that spell.
"""


def test_parse_official_txt_extracts_date_groups_and_sections():
    document = parse_official_rules_txt(OFFICIAL_SAMPLE, source_url="https://media.wizards.com/rules.txt")

    assert document.effective_date == date(2026, 6, 19)
    assert [(group.id, group.name) for group in document.groups] == [
        (100, "Game Concepts"),
        (200, "Parts of a Card"),
        (600, "Spells, Abilities, and Effects"),
    ]
    assert [(section.id, section.group_id, section.name) for section in document.sections] == [
        (100, 100, "General"),
        (101, 100, "The Magic Golden Rules"),
        (200, 200, "General"),
        (600, 600, "General"),
    ]
    assert document.sections[0].rule_text.startswith("100.1.\nThese Magic rules apply")
    assert "100.1a A two-player game" in document.sections[0].rule_text
    assert document.sections[-1].rule_text == ""


def test_parse_legacy_rules_tex_seeds_current_latex_rules():
    document = parse_legacy_rules_tex(LEGACY_SAMPLE)

    assert document.effective_date == date(2026, 2, 27)
    assert [(group.id, group.name) for group in document.groups] == [
        (100, "Game Concepts"),
        (600, "Spells, Abilities, and Effects"),
    ]
    assert [(section.id, section.group_id, section.name) for section in document.sections] == [
        (100, 100, "General"),
        (101, 100, "The Magic Golden Rules"),
        (600, 600, "General"),
        (601, 600, "Casting Spells"),
    ]
    assert "These Magic rules apply to any Magic game." in document.sections[0].rule_text
    assert document.sections[2].rule_text == ""
