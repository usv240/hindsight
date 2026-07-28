"""`scan-sql` is the part that works on a stranger's repository on day one.

Point-in-time reconstruction still needs the seeded data shape. SQL analysis does
not, so this is what converts "you can read about it" into "you can run it on your
dbt project this afternoon". It has to be right, and it has to refuse to call a
file safe that it never actually managed to check.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hindsight.cli import main
from hindsight.scan import scan_directory


def test_it_finds_every_planted_violation_in_our_own_sql() -> None:
    result = scan_directory(
        Path("examples"),
        post_outcome_tables=[
            "payment_events_after_decision",
            "disputes_after_authorisation",
            "followup_appointments_after_discharge",
        ],
    )
    violations = {Path(v["path"]).name for v in result.violations}
    assert violations == {
        "leaky_feature.sql",
        "fraud_screening_leaky.sql",
        "hospital_readmission_leaky.sql",
    }
    # And clears every repaired file.
    assert len(result.safe) == 3
    assert result.exit_code == 3


def test_a_guarded_query_is_reported_clean(tmp_path: Path) -> None:
    (tmp_path / "safe.sql").write_text(
        """SELECT a.id, count(e.ts) AS n
           FROM apps AS a
           LEFT JOIN events_after AS e
             ON e.k = a.k AND e.available_at <= a.prediction_time
           GROUP BY a.id;""",
        encoding="utf-8",
    )
    result = scan_directory(tmp_path, post_outcome_tables=["events_after"])
    assert result.violations == []
    assert result.exit_code == 0


def test_files_that_never_touch_a_post_outcome_source_are_not_counted_as_findings(
    tmp_path: Path,
) -> None:
    (tmp_path / "unrelated.sql").write_text("SELECT 1 AS x;", encoding="utf-8")
    result = scan_directory(tmp_path, post_outcome_tables=["events_after"])
    assert result.violations == []
    assert result.not_applicable == ["unrelated.sql"] or result.not_applicable


def test_an_unreadable_file_is_unknown_not_safe(tmp_path: Path) -> None:
    """A file that was never checked has not passed."""
    (tmp_path / "broken.sql").write_bytes(b"\xff\xfe\x00 not valid utf-8 \xff")
    result = scan_directory(tmp_path, post_outcome_tables=["events_after"])
    assert result.unparseable, "expected the unreadable file to be reported"
    assert not result.safe, "an unreadable file must never be listed as clean"
    assert result.exit_code == 2, "unknown is not a pass"


def test_vendored_directories_are_skipped(tmp_path: Path) -> None:
    for folder in ("dbt_packages", "node_modules", ".git", "target"):
        d = tmp_path / folder
        d.mkdir()
        (d / "vendor.sql").write_text("SELECT * FROM events_after;", encoding="utf-8")
    (tmp_path / "mine.sql").write_text("SELECT 1;", encoding="utf-8")
    result = scan_directory(tmp_path, post_outcome_tables=["events_after"])
    assert result.scanned == 1, "third-party SQL must not be reported as the user's problem"


def test_a_single_file_path_also_works(tmp_path: Path) -> None:
    target = tmp_path / "one.sql"
    target.write_text("SELECT * FROM events_after;", encoding="utf-8")
    result = scan_directory(target, post_outcome_tables=["events_after"])
    assert result.scanned == 1


def test_at_least_one_table_is_required(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="post-outcome table"):
        scan_directory(tmp_path, post_outcome_tables=[])


def test_cli_exit_codes_match_the_release_gate_contract(tmp_path: Path) -> None:
    """3 blocks a pull request, 0 lets it through - same contract as an audit."""
    (tmp_path / "bad.sql").write_text("SELECT * FROM events_after;", encoding="utf-8")
    assert main(["scan-sql", str(tmp_path), "--post-outcome-table", "events_after", "--json"]) == 3

    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "ok.sql").write_text("SELECT 1;", encoding="utf-8")
    assert main(["scan-sql", str(clean), "--post-outcome-table", "events_after", "--json"]) == 0


def test_cli_reports_a_missing_path_rather_than_crashing(tmp_path: Path) -> None:
    assert main(["scan-sql", str(tmp_path / "nope"), "--post-outcome-table", "x"]) == 2


@pytest.mark.parametrize(
    ("sql_table", "configured"),
    [
        ("events_after", "events_after"),
        ("raw.events_after", "events_after"),
        ("prod.raw.events_after", "raw.events_after"),
        ("EVENTS_AFTER", "events_after"),
    ],
)
def test_schema_qualified_names_still_match(
    tmp_path: Path, sql_table: str, configured: str
) -> None:
    """Warehouses qualify names inconsistently; a leak must not hide behind a prefix."""
    (tmp_path / "q.sql").write_text(f"SELECT * FROM {sql_table};", encoding="utf-8")
    result = scan_directory(tmp_path, post_outcome_tables=[configured])
    assert result.violations, f"{sql_table} vs {configured} should have matched"


# -- dbt templating ---------------------------------------------------------
# Found by running against dbt-labs/jaffle-shop: every model parsed to zero
# tables, and the scanner reported them as "no post-outcome source" - a false
# negative wearing a pass.


def test_dbt_ref_resolves_to_a_table_name() -> None:
    from hindsight.scan import resolve_templating

    assert "stg_orders" in resolve_templating("select * from {{ ref('stg_orders') }}")
    assert "stg_orders" in resolve_templating('select * from {{ref("stg_orders")}}')
    # Cross-project refs name the model in the second argument.
    assert "stg_orders" in resolve_templating("select * from {{ ref('proj', 'stg_orders') }}")


def test_dbt_source_resolves_to_a_qualified_name() -> None:
    from hindsight.scan import resolve_templating

    assert "raw.events" in resolve_templating("select * from {{ source('raw', 'events') }}")


def test_config_blocks_and_comments_are_removed() -> None:
    from hindsight.scan import resolve_templating

    resolved = resolve_templating(
        "{{ config(materialized='table') }}\n{# a comment #}\nselect * from {{ ref('x') }}"
    )
    assert "config" not in resolved
    assert "comment" not in resolved
    assert "x" in resolved


def test_a_leak_hidden_behind_dbt_templating_is_still_caught(tmp_path: Path) -> None:
    (tmp_path / "model.sql").write_text(
        """{{ config(materialized='table') }}
        select a.id, count(e.id) as n
        from {{ ref('applications') }} as a
        left join {{ ref('events_after') }} as e on e.k = a.k
        group by a.id""",
        encoding="utf-8",
    )
    result = scan_directory(tmp_path, post_outcome_tables=["events_after"])
    assert result.violations, "a dbt ref must not hide a missing guard"


def test_a_guarded_dbt_model_is_clean(tmp_path: Path) -> None:
    (tmp_path / "model.sql").write_text(
        """select a.id, count(e.id) as n
        from {{ ref('applications') }} as a
        left join {{ ref('events_after') }} as e
          on e.k = a.k and e.available_at <= a.prediction_time
        group by a.id""",
        encoding="utf-8",
    )
    result = scan_directory(tmp_path, post_outcome_tables=["events_after"])
    assert not result.violations
    assert result.safe


def test_an_unparseable_query_is_unchecked_never_clean(tmp_path: Path) -> None:
    """The jaffle-shop bug: indeterminate must not fall through to a pass."""
    (tmp_path / "weird.sql").write_text("this is not sql at all !!! ((", encoding="utf-8")
    result = scan_directory(tmp_path, post_outcome_tables=["events_after"])
    assert not result.safe
    assert not result.not_applicable or result.unparseable
