from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

from .latex import render_rules_tex, update_cover_effective_date
from .parsers import parse_legacy_rules_tex, parse_official_rules_txt
from .repository import DuckDBRulesRepository
from .source import FetchedRules


LOGGER = logging.getLogger(__name__)


class RulesSource(Protocol):
    def fetch_latest_rules_txt(self) -> FetchedRules:
        raise NotImplementedError


@dataclass(frozen=True)
class PipelineResult:
    status: str
    previous_effective_date: date | None
    current_effective_date: date
    seeded_database: bool
    groups_loaded: int
    rules_loaded: int
    latex_updated: bool
    cover_updated: bool


class RulesEtlPipeline:
    def __init__(
        self,
        repository: DuckDBRulesRepository,
        source: RulesSource,
        latex_path: str | Path,
        cover_path: str | Path | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.repository = repository
        self.source = source
        self.latex_path = Path(latex_path)
        self.cover_path = Path(cover_path) if cover_path else None
        self.logger = logger or LOGGER

    def run(self) -> PipelineResult:
        run_id = uuid.uuid4().hex
        started = time.perf_counter()
        self._log("pipeline_started", run_id=run_id, stage="start")
        try:
            self.repository.initialize()
            seeded = self._seed_database_if_needed(run_id)
            previous_effective_date = self.repository.latest_effective_date()
            fetched = self.source.fetch_latest_rules_txt()
            self._log("source_downloaded", run_id=run_id, stage="extract", source_url=fetched.url)
            remote_document = parse_official_rules_txt(fetched.text, source_url=fetched.url)
            self._log(
                "source_parsed",
                run_id=run_id,
                stage="transform",
                effective_date=str(remote_document.effective_date),
                groups=len(remote_document.groups),
                rules=len(remote_document.sections),
            )

            if previous_effective_date == remote_document.effective_date:
                cover_updated = self._update_cover_if_needed(remote_document.effective_date)
                result = PipelineResult(
                    status="skipped",
                    previous_effective_date=previous_effective_date,
                    current_effective_date=remote_document.effective_date,
                    seeded_database=seeded,
                    groups_loaded=0,
                    rules_loaded=0,
                    latex_updated=False,
                    cover_updated=cover_updated,
                )
                self._log_finished(run_id, result, started)
                return result

            self.repository.save_document(remote_document)
            rendered = render_rules_tex(remote_document)
            _atomic_write_text(self.latex_path, rendered)
            cover_updated = self._update_cover_if_needed(remote_document.effective_date)
            result = PipelineResult(
                status="updated",
                previous_effective_date=previous_effective_date,
                current_effective_date=remote_document.effective_date,
                seeded_database=seeded,
                groups_loaded=len(remote_document.groups),
                rules_loaded=len(remote_document.sections),
                latex_updated=True,
                cover_updated=cover_updated,
            )
            self._log_finished(run_id, result, started)
            return result
        except Exception as exc:
            self.logger.exception(
                "pipeline_failed",
                extra={"run_id": run_id, "stage": "failed", "error_type": type(exc).__name__},
            )
            raise

    def _seed_database_if_needed(self, run_id: str) -> bool:
        if not self.repository.is_empty():
            return False
        legacy_text = self.latex_path.read_text(encoding="utf-8-sig")
        legacy_document = parse_legacy_rules_tex(legacy_text, source_url=str(self.latex_path))
        self.repository.save_document(legacy_document)
        self._log(
            "database_seeded",
            run_id=run_id,
            stage="load",
            effective_date=str(legacy_document.effective_date),
            groups=len(legacy_document.groups),
            rules=len(legacy_document.sections),
        )
        return True

    def _update_cover_if_needed(self, effective_date: date) -> bool:
        if not self.cover_path or not self.cover_path.exists():
            return False
        cover_text = self.cover_path.read_text(encoding="utf-8-sig")
        updated_cover_text = update_cover_effective_date(cover_text, effective_date)
        if updated_cover_text == cover_text:
            return False
        _atomic_write_text(self.cover_path, updated_cover_text)
        return True

    def _log_finished(self, run_id: str, result: PipelineResult, started: float) -> None:
        self._log(
            "pipeline_finished",
            run_id=run_id,
            stage="finish",
            status=result.status,
            current_effective_date=str(result.current_effective_date),
            previous_effective_date=str(result.previous_effective_date),
            groups_loaded=result.groups_loaded,
            rules_loaded=result.rules_loaded,
            latex_updated=result.latex_updated,
            cover_updated=result.cover_updated,
            duration_seconds=round(time.perf_counter() - started, 3),
        )

    def _log(self, message: str, **fields) -> None:
        self.logger.info(message, extra=fields)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary_path.write_text(text, encoding="utf-8", newline="\n")
    temporary_path.replace(path)
