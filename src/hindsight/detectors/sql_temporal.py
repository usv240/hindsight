from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from sqlglot import exp, parse_one
from sqlglot.errors import ParseError


@dataclass(frozen=True)
class SqlVerification:
    status: Literal["safe", "violation", "indeterminate"]
    reason: str
    referenced_tables: tuple[str, ...]
    cutoff_predicates: tuple[str, ...]
    post_outcome_table: str
    available_column: str
    prediction_column: str

    @property
    def exit_code(self) -> int:
        return {"safe": 0, "indeterminate": 2, "violation": 3}[self.status]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["exit_code"] = self.exit_code
        return payload


def verify_temporal_cutoff(
    sql: str,
    *,
    post_outcome_table: str,
    available_column: str = "available_at",
    prediction_column: str = "prediction_time",
    dialect: str | None = None,
) -> SqlVerification:
    """Verify that a query touching a post-outcome table enforces a time cutoff."""
    try:
        tree = parse_one(sql, dialect=dialect)
    except ParseError as error:
        return SqlVerification(
            status="indeterminate",
            reason=f"SQL could not be parsed: {error.errors[0].get('description', 'parse error')}",
            referenced_tables=(),
            cutoff_predicates=(),
            post_outcome_table=post_outcome_table,
            available_column=available_column,
            prediction_column=prediction_column,
        )

    tables = tuple(sorted({_normalized_table(table) for table in tree.find_all(exp.Table)}))
    target = post_outcome_table.casefold()
    target_tables = tuple(
        table
        for table in tree.find_all(exp.Table)
        if _normalized_table(table) == target or _normalized_table(table).endswith(f".{target}")
    )
    touches_post_outcome = bool(target_tables)
    if not touches_post_outcome:
        return SqlVerification(
            status="safe",
            reason="The configured post-outcome source is not referenced by this transformation.",
            referenced_tables=tables,
            cutoff_predicates=(),
            post_outcome_table=post_outcome_table,
            available_column=available_column,
            prediction_column=prediction_column,
        )

    target_aliases = {table.alias_or_name.casefold() for table in target_tables}
    predicates = tuple(
        comparison.sql(dialect=dialect)
        for comparison in tree.walk()
        if _is_cutoff_comparison(comparison, available_column, prediction_column, target_aliases)
    )
    if predicates:
        return SqlVerification(
            status="safe",
            reason="A directional availability cutoff protects the post-outcome source.",
            referenced_tables=tables,
            cutoff_predicates=predicates,
            post_outcome_table=post_outcome_table,
            available_column=available_column,
            prediction_column=prediction_column,
        )

    available_is_present = any(
        column.name.casefold() == available_column.casefold()
        for column in tree.find_all(exp.Column)
    )
    reason = (
        "The post-outcome source is referenced, but no directional "
        f"{available_column} <= {prediction_column} cutoff was found."
    )
    if not available_is_present:
        reason += f" The transformation does not reference {available_column}."
    return SqlVerification(
        status="violation",
        reason=reason,
        referenced_tables=tables,
        cutoff_predicates=(),
        post_outcome_table=post_outcome_table,
        available_column=available_column,
        prediction_column=prediction_column,
    )


def _is_cutoff_comparison(
    expression: exp.Expression,
    available_column: str,
    prediction_column: str,
    target_aliases: set[str],
) -> bool:
    if isinstance(expression, (exp.LTE, exp.LT)):
        return _side_has_target_column(
            expression.left, available_column, target_aliases
        ) and _side_has(expression.right, prediction_column)
    if isinstance(expression, (exp.GTE, exp.GT)):
        return _side_has(expression.left, prediction_column) and _side_has_target_column(
            expression.right, available_column, target_aliases
        )
    return False


def _side_has(expression: exp.Expression, column_name: str) -> bool:
    return any(
        column.name.casefold() == column_name.casefold()
        for column in expression.find_all(exp.Column)
    ) or (
        isinstance(expression, exp.Column) and expression.name.casefold() == column_name.casefold()
    )


def _side_has_target_column(
    expression: exp.Expression, column_name: str, target_aliases: set[str]
) -> bool:
    columns = list(expression.find_all(exp.Column))
    if isinstance(expression, exp.Column):
        columns.append(expression)
    return any(
        column.name.casefold() == column_name.casefold()
        and column.table.casefold() in target_aliases
        for column in columns
    )


def _normalized_table(table: exp.Table) -> str:
    parts = [part for part in (table.catalog, table.db, table.name) if part]
    return ".".join(parts).casefold()
