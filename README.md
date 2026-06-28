# MTG Rules ETL

## What It Is

This project maintains an unofficial LaTeX body file for the Magic: The
Gathering Comprehensive Rules and a DuckDB copy of the parsed rule index.

The LaTeX sources live in `latex/`.

The ETL seeds DuckDB from `latex/rules.tex` when the database is missing or empty,
then checks the official Wizards rules page for the latest TXT release. If the
effective date is unchanged, the job reports `skipped`. If the date changed, it
loads the new rule groups and rule sections into DuckDB and rewrites
`latex/rules.tex` with the same chapter/section/subsection style used by the
existing LaTeX file. The job also keeps the cover/title dates in
`latex/mtg_rules.tex` aligned with the parsed official effective date, even on a
same-date `skipped` run.

## How It Works

The entry point is:

```powershell
& D:\code\MTG\.venv\Scripts\python.exe -m mtg_rules_etl.cli --db data\mtg_rules.duckdb --rules-tex latex\rules.tex --cover-tex latex\mtg_rules.tex
```

Default source page: `https://magic.wizards.com/en/rules`.

The ETL discovers the TXT link from the source page. It does not hardcode the
dated TXT URL.

## Architecture and Design Rationale

Pattern: Pipe-and-Filter with Ports and Adapters.

The pipeline is separated into extraction, parsing/validation, persistence, and
LaTeX rendering. HTTP and DuckDB are isolated behind adapters so tests can run
without the network and without a permanent database.

Local patterns:

| Pattern | Code | Purpose |
| --- | --- | --- |
| Source adapter | `mtg_rules_etl/source.py` | Fetch official HTML/TXT and constrain allowed HTTPS hosts. |
| Repository | `mtg_rules_etl/repository.py` | Own DuckDB schema and parameterized writes. |
| Use case | `mtg_rules_etl/pipeline.py` | Orchestrate one ETL run and idempotent update behavior. |
| Renderer | `mtg_rules_etl/latex.py` | Convert parsed rules to the existing LaTeX body format. |

## Specs and Contracts

The SDD spec is in `docs/specs/mtg_rules_etl.md`.

DuckDB tables:

| Table | Key | Purpose |
| --- | --- | --- |
| `rule_groups` | `(id, effective_date)` | Stores group ids such as 100, 200, 300 and their chapter names. |
| `rules` | `(id, effective_date)` | Stores rule section ids such as 100, 101, 102, with `group_id`, `name`, and `rule_text`. |

`rule_text` is plain text. Some official placeholder sections can be empty, for
example `600. General` in the June 19, 2026 rules.

## Data Flow

```mermaid
flowchart LR
  Latex["latex/rules.tex"] --> Seed["Seed DuckDB when empty"]
  Page["Official rules page"] --> Link["Discover TXT link"]
  Link --> Txt["Download TXT"]
  Txt --> Parse["Parse date, groups, sections"]
  Seed --> Compare["Compare effective dates"]
  Parse --> Compare
  Compare -->|Same date| Skip["Report skipped"]
  Compare -->|Different date| Load["Load DuckDB"]
  Load --> Render["Render latex/rules.tex"]
  Compare --> Cover["Update latex/mtg_rules.tex date if stale"]
```

## How To Run

Create the virtual environment and install dependencies:

```powershell
C:\Python312\python.exe -m venv D:\code\MTG\.venv
& D:\code\MTG\.venv\Scripts\python.exe -m pip install -r D:\code\MTG\requirements.txt
```

Run the ETL:

```powershell
& D:\code\MTG\.venv\Scripts\python.exe -m mtg_rules_etl.cli --db data\mtg_rules.duckdb --rules-tex latex\rules.tex --cover-tex latex\mtg_rules.tex
```

## How To Test

The sandbox may not allow pytest to use the default Windows temp folder, so use
a workspace basetemp:

```powershell
New-Item -ItemType Directory -Force D:\code\MTG\.tmp | Out-Null
& D:\code\MTG\.venv\Scripts\python.exe -m pytest -q --basetemp D:\code\MTG\.tmp\pytest
```

## How To Update

| Need to change | Start here | Also check |
| --- | --- | --- |
| DuckDB schema | `mtg_rules_etl/repository.py` | `docs/specs/mtg_rules_etl.md`, repository tests |
| Official source behavior | `mtg_rules_etl/source.py` | source tests, SSRF host allowlist |
| TXT or LaTeX parsing | `mtg_rules_etl/parsers.py` | parser fixtures/tests |
| LaTeX output format and cover date replacement | `mtg_rules_etl/latex.py` | `latex/rules.tex`, `latex/mtg_rules.tex`, renderer tests |
| ETL orchestration | `mtg_rules_etl/pipeline.py` | pipeline tests and logging contract |

## Operations and Troubleshooting

Rerun is safe. The repository deletes and reloads rows for the same
`effective_date` in one transaction, so duplicate rows are not created.

If a network call fails, rerun the same command after connectivity or sandbox
permissions are fixed. A failed run may seed the old LaTeX version first; the
next successful run will continue from that state.

This ETL updates `latex/rules.tex` and the effective-date text in
`latex/mtg_rules.tex`. It does not update `latex/glossary.tex`, `latex/credits.tex`,
or the PDF unless that scope is added.

## Logging and Error Handling

CLI logs are JSON lines on stderr. Each lifecycle event includes UTC timestamp,
level, logger, message, run id, and stage. The pipeline logs start, seed,
download, parse summary, final status, and failure. It logs counts and safe URLs,
not every rule row.

Common final statuses:

| Status | Meaning |
| --- | --- |
| `updated` | The official date differed; DuckDB, `latex/rules.tex`, and stale cover dates were updated. |
| `skipped` | The official date matched the latest DuckDB date; rule loading was skipped, but stale cover dates can still be corrected. |

## Security and Privacy

The source adapter accepts only HTTPS URLs from `magic.wizards.com` for the
rules page and `media.wizards.com` or `magic.wizards.com` for TXT downloads.
DuckDB writes use parameterized statements.

## References

- Official rules page: https://magic.wizards.com/en/rules
- DuckDB Python API: https://duckdb.org/docs/stable/clients/python/overview