from datetime import date

from mtg_rules_etl.models import RuleGroup, RuleSection, RulesDocument
from mtg_rules_etl.repository import DuckDBRulesRepository


def sample_document() -> RulesDocument:
    return RulesDocument(
        effective_date=date(2026, 2, 27),
        title="Magic: The Gathering Comprehensive Rules",
        introduction="This document is the ultimate authority.",
        changes_notice="Changes may have been made.",
        groups=(RuleGroup(id=100, name="Game Concepts", chapter_number=1),),
        sections=(
            RuleSection(
                id=100,
                group_id=100,
                name="General",
                rule_text="100.1.\nThese Magic rules apply.",
            ),
        ),
        source_url=None,
    )


def test_repository_load_is_idempotent_for_same_effective_date(tmp_path):
    repository = DuckDBRulesRepository(tmp_path / "rules.duckdb")
    repository.initialize()

    repository.save_document(sample_document())
    repository.save_document(sample_document())

    assert repository.latest_effective_date() == date(2026, 2, 27)
    assert repository.count_rows("rule_groups") == 1
    assert repository.count_rows("rules") == 1
