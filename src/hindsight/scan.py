"""Scan a directory of SQL for post-outcome sources used without a time guard.

Point-in-time reconstruction can map external CSV or Parquet snapshots, but it does
not query arbitrary warehouse engines directly yet. The *transformation* check needs
no data adapter: it is pure SQL analysis, and it is the half of the evidence
that produces a deterministic proof rather than a statistical signal.

So this exists to be genuinely usable on day one. Point it at a dbt `models/`
directory, name the tables whose rows only appear after the decision, and it
reports every transformation that reads one without an availability cutoff.

It reports what it cannot parse rather than passing it silently. A file that was
never checked is not a file that passed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hindsight.detectors import verify_temporal_cutoff

# dbt models are Jinja templates, not SQL. Running this against dbt-labs/jaffle-shop
# showed every model parsing to zero tables, which the scanner then reported as
# "no post-outcome source" - a false negative dressed as a pass. Resolve the two
# constructs that name a table, and drop the rest of the templating.
_REF = re.compile(r"\{\{\s*ref\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}")
_REF_PROJECT = re.compile(
    r"\{\{\s*ref\s*\(\s*['\"][^'\"]+['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}"
)
_SOURCE = re.compile(
    r"\{\{\s*source\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}"
)
_JINJA_BLOCK = re.compile(r"\{%.*?%\}", re.DOTALL)
_JINJA_EXPR = re.compile(r"\{\{.*?\}\}", re.DOTALL)
_JINJA_COMMENT = re.compile(r"\{#.*?#\}", re.DOTALL)
# Statement-level macros carry no value into the query and must be deleted, not
# substituted: an identifier left before SELECT makes the whole file unparseable.
_STATEMENT_MACROS = re.compile(
    r"\{\{\s*(config|docs|snapshot|materialization)\s*\(.*?\)\s*\}\}", re.DOTALL | re.IGNORECASE
)


def resolve_templating(sql: str) -> str:
    """Turn a dbt model into something a SQL parser can read.

    `{{ ref('stg_orders') }}` becomes `stg_orders`; `{{ source('raw', 'events') }}`
    becomes `raw.events`. Remaining Jinja is replaced with a placeholder rather
    than deleted, so surrounding syntax stays intact.
    """
    resolved = _JINJA_COMMENT.sub(" ", sql)
    resolved = _STATEMENT_MACROS.sub(" ", resolved)
    resolved = _JINJA_BLOCK.sub(" ", resolved)
    resolved = _SOURCE.sub(r"\1.\2", resolved)
    resolved = _REF_PROJECT.sub(r"\1", resolved)
    resolved = _REF.sub(r"\1", resolved)
    # Anything left is a macro or variable, not a table name.
    return _JINJA_EXPR.sub("_hindsight_jinja", resolved)


SQL_SUFFIXES = (".sql",)
# Directories that never contain first-party transformations.
SKIP_DIRS = frozenset({".git", "node_modules", "target", "dbt_packages", "venv", ".venv"})


@dataclass
class ScanResult:
    scanned: int = 0
    violations: list[dict[str, Any]] = field(default_factory=list)
    safe: list[str] = field(default_factory=list)
    unparseable: list[dict[str, str]] = field(default_factory=list)
    not_applicable: list[str] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        if self.violations:
            return 3
        # Files we could not read are an unknown, not a pass.
        return 2 if self.unparseable else 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "scanned": self.scanned,
            "violations": self.violations,
            "safe": self.safe,
            "unparseable": self.unparseable,
            "not_applicable": self.not_applicable,
            "summary": {
                "violations": len(self.violations),
                "safe": len(self.safe),
                "unparseable": len(self.unparseable),
                "did_not_reference_a_post_outcome_source": len(self.not_applicable),
            },
            "exit_code": self.exit_code,
        }


def scan_directory(
    root: Path,
    *,
    post_outcome_tables: list[str],
    available_column: str = "available_at",
    prediction_column: str = "prediction_time",
    dialect: str | None = None,
) -> ScanResult:
    """Check every SQL file under ``root`` against each post-outcome table."""
    result = ScanResult()
    if not post_outcome_tables:
        raise ValueError("At least one post-outcome table is required.")

    base = Path(root)
    for path in sorted(_sql_files(base)):
        result.scanned += 1
        # Report paths relative to what was scanned; absolute temp paths are noise.
        try:
            relative = path.relative_to(base).as_posix()
        except ValueError:
            relative = path.name
        try:
            sql = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            result.unparseable.append({"path": relative, "reason": str(error)})
            continue

        sql = resolve_templating(sql)
        worst: dict[str, Any] | None = None
        referenced = False
        indeterminate = False
        for table in post_outcome_tables:
            try:
                check = verify_temporal_cutoff(
                    sql,
                    post_outcome_table=table,
                    available_column=available_column,
                    prediction_column=prediction_column,
                    dialect=dialect,
                )
            except Exception as error:  # noqa: BLE001 - a parse failure is a finding
                result.unparseable.append({"path": relative, "reason": f"{type(error).__name__}"})
                worst = None
                referenced = True
                break

            # A query the parser could not understand has not been checked. It
            # must never fall through to "clean" - that is a false negative
            # wearing a pass, which is the failure this whole tool exists to stop.
            if check.status == "indeterminate":
                indeterminate = True
                continue

            # The single-file detector returns "safe" when the table is simply
            # absent, which is true but useless in a report: a repo of 500 models
            # would show 497 "clean" when they merely never touch this source.
            # Decide applicability from what the query actually references.
            if not _references(check.referenced_tables, table):
                continue
            referenced = True
            if check.status == "violation":
                worst = {
                    "path": relative,
                    "post_outcome_table": table,
                    "reason": check.reason,
                }
                break

        already_unparseable = any(u["path"] == relative for u in result.unparseable)
        if worst:
            result.violations.append(worst)
        elif already_unparseable:
            pass
        elif indeterminate and not referenced:
            result.unparseable.append(
                {"path": relative, "reason": "the parser could not read this query"}
            )
        elif referenced:
            result.safe.append(relative)
        else:
            result.not_applicable.append(relative)

    return result


def _references(referenced: tuple[str, ...] | list[str], table: str) -> bool:
    """Whether a query actually reads ``table``.

    Warehouses qualify names inconsistently - `events`, `raw.events`,
    `prod.raw.events` - so compare on the final component, case-insensitively.
    """
    wanted = table.rsplit(".", 1)[-1].strip('"`[] ').lower()
    return any(name.rsplit(".", 1)[-1].strip('"`[] ').lower() == wanted for name in referenced)


def _sql_files(root: Path):
    if root.is_file():
        yield root
        return
    for path in root.rglob("*"):
        if path.suffix.lower() not in SQL_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def render(result: ScanResult, root: Path) -> str:
    """A short report for a terminal."""
    lines = [
        f"Scanned {result.scanned} SQL file(s) under {root}",
        "",
    ]
    if result.violations:
        lines.append(f"VIOLATIONS ({len(result.violations)}) - post-outcome data with no cutoff:")
        for item in result.violations:
            lines.append(f"  {item['path']}")
            lines.append(f"    reads {item['post_outcome_table']} without an availability guard")
        lines.append("")
    if result.unparseable:
        lines.append(f"COULD NOT CHECK ({len(result.unparseable)}) - treat as unknown, not safe:")
        for item in result.unparseable:
            lines.append(f"  {item['path']}  ({item['reason']})")
        lines.append("")

    summary = result.to_dict()["summary"]
    lines.append(
        f"clean: {summary['safe']}   "
        f"violations: {summary['violations']}   "
        f"unchecked: {summary['unparseable']}   "
        f"no post-outcome source: {summary['did_not_reference_a_post_outcome_source']}"
    )
    return "\n".join(lines) + "\n"
