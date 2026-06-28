# MTG Comprehensive Rules ETL Spec

## Context

The workspace contains an unofficial LaTeX typesetting under `latex/`.
The historical source before the first ETL update was effective February 27,
2026; the canonical folder is now `latex/`.
The ETL must keep a DuckDB copy of the rules and update `latex/rules.tex` from
the official Wizards rules page only when the official effective date changes.

The official source page is `https://magic.wizards.com/en/rules`. The ETL must
discover the TXT download from that page instead of hardcoding a dated TXT URL.

## Architecture

Selected pattern: Pipe-and-Filter with Ports and Adapters.

Reason: the job has clear ETL stages: extract the page/TXT, parse and validate
the rules, load DuckDB, and render LaTeX. HTTP and DuckDB are isolated behind
adapters so parsing and rendering can be tested without network or a permanent
database.

Local design pattern: Repository for DuckDB persistence, Adapter for the
official source, and Use Case/Command for one pipeline run.

## Scope

In scope:

- Seed DuckDB from `latex/rules.tex` when the database does not exist or is empty.
- Fetch the current TXT link from the official rules page.
- Parse `These rules are effective as of ...` from the TXT.
- Compare the fetched effective date with the latest date in DuckDB.
- Skip the load and LaTeX update when the dates match.
- Load rule groups and rule sections into DuckDB when the dates differ.
- Update `latex/rules.tex` while preserving the existing chapter/section/subsection
  formatting style.
- Update `latex/mtg_rules.tex` cover/title effective-date text while preserving
  the surrounding LaTeX formatting.

Out of scope unless confirmed later:

- Updating `latex/glossary.tex`, `latex/credits.tex`, or the PDF.
- Creating one physical DuckDB table per 100/200/300 group.
- Adding scheduling, GUI, or cloud deployment.

## Data Contract

Table `rule_groups`:

| Column | Type | Rule |
| --- | --- | --- |
| `id` | INTEGER | Hundred bucket from the rules summary, such as 100, 200, 300. |
| `effective_date` | DATE | Effective date parsed from the source document. |
| `name` | TEXT | Group/chapter name from the summary/body, such as `Game Concepts`. |

Primary key: `(id, effective_date)`.

Table `rules`:

| Column | Type | Rule |
| --- | --- | --- |
| `id` | INTEGER | Rule section number, such as 100, 101, 102. |
| `group_id` | INTEGER | Parent group id, such as 100 for rule sections 100-199. |
| `effective_date` | DATE | Effective date parsed from the source document. |
| `name` | TEXT | Rule section name, such as `The Magic Golden Rules`. |
| `rule_text` | TEXT | Plain rule text for the section, including subsection headings and subrules. May be empty when the official TXT has a placeholder section such as `600. General`. |

Primary key: `(id, effective_date)`.

## Requirements

S-001: When DuckDB is missing or empty, the ETL shall seed it from the current
`latex/rules.tex` before comparing dates.

S-002: The official TXT URL shall be discovered from
`https://magic.wizards.com/en/rules`.

S-003: The parser shall read the effective date from the phrase
`These rules are effective as of ...`.

S-004: If the official effective date equals the latest DuckDB effective date,
the ETL shall skip loading and shall not rewrite `latex/rules.tex`.

S-005: If the official effective date is newer or otherwise different, the ETL
shall load all rule groups and rule sections for that date into DuckDB,
including official placeholder sections with empty `rule_text`.

S-006: The generated `latex/rules.tex` shall preserve the current body format:
intro chapter, numbered `\chapter{}`, `\section{}`, and `\subsection*{...}`
for standalone rule headings.

S-007: Re-running the same document load shall be idempotent for the same
effective date and shall not duplicate rows.

S-008: The ETL shall emit timestamped structured logs with a run id and stage
summaries, without logging every rule row.

S-009: The ETL shall update every `Effective as of ...` cover/title occurrence
in `latex/mtg_rules.tex` to the parsed official effective date without changing
the surrounding LaTeX formatting. This shall also happen on a same-date
`skipped` run if the cover file is stale.

S-010: The CLI default LaTeX paths shall point to the canonical `latex/`
directory: `latex/rules.tex` and `latex/mtg_rules.tex`.

## Security and Privacy

Applicable OWASP risks:

- SSRF / unsafe outbound requests: the source adapter accepts only HTTPS URLs
  under the configured Wizards rules page and TXT host.
- Injection: DuckDB writes use parameterized statements.
- Software and data integrity: the parser validates the effective date, groups,
  sections, and the rule contract before loading. Empty rule text is allowed
  only for official placeholder sections.
- Security logging failures: logs include lifecycle events and avoid full rule
  text.

Not applicable:

- Authentication, authorization, tenant isolation, payments, and personal data
  handling are not part of this local batch job.

LGPD: not applicable. The rules text and operational logs do not contain
personal data. Logs still avoid unnecessary free text by logging counts and safe
URLs only.

## Acceptance Criteria

- A missing/empty database is populated from the existing LaTeX rules.
- The official TXT link extractor finds a TXT href from the rules page HTML.
- The TXT parser returns the effective date, group index, section index, and
  section text.
- A same-date run returns `skipped` and leaves the LaTeX file unchanged.
- A different-date run returns `updated`, inserts rows, and writes new LaTeX.
- A same-date run still updates stale `latex/mtg_rules.tex` cover/title dates.
- Running the same load twice does not duplicate rows for `(id, effective_date)`.

## Traceability

| Spec rule | Test |
| --- | --- |
| S-001 | `tests/test_pipeline.py::test_pipeline_seeds_missing_database_then_skips_same_date` |
| S-002 | `tests/test_source.py::test_extract_txt_link_from_rules_page_html` |
| S-003 | `tests/test_parsers.py::test_parse_official_txt_extracts_date_groups_and_sections` |
| S-004 | `tests/test_pipeline.py::test_pipeline_seeds_missing_database_then_skips_same_date` |
| S-005 | `tests/test_pipeline.py::test_pipeline_updates_database_and_latex_when_date_changes` |
| S-006 | `tests/test_latex.py::test_render_rules_tex_preserves_existing_structure` |
| S-007 | `tests/test_repository.py::test_repository_load_is_idempotent_for_same_effective_date` |
| S-008 | `tests/test_pipeline.py::test_pipeline_updates_database_and_latex_when_date_changes` |
| S-009 | `tests/test_latex.py::test_update_cover_effective_date_preserves_cover_formatting`, `tests/test_pipeline.py::test_pipeline_updates_stale_cover_when_rules_date_is_already_current` |
| S-010 | `tests/test_cli.py::test_cli_defaults_use_latex_directory` |
