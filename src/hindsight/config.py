"""Audit configuration: what Hindsight is auditing, and which asset it describes.

Before this existed the console and the publish command were hard-wired to the
seeded credit-default scenario, which meant two things that are fine in a demo
and wrong anywhere else: you could not point Hindsight at your own feature
pipeline, and ``publish-audit --target-urn`` would happily write the
credit-default verdict onto an unrelated asset.

An audit config binds the evidence to the asset it is actually about.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_AUDIT_PATH = Path("audits/credit_default.json")


class AuditConfigError(ValueError):
    """Raised when an audit config is missing, malformed, or points at nothing."""


@dataclass(frozen=True)
class AuditConfig:
    """One thing to audit: the data, the SQL that built it, and the asset it is."""

    name: str
    scenario_path: Path
    transformation_path: Path
    remediation_path: Path
    post_outcome_table: str
    target_urn: str | None = None
    available_column: str = "available_at"
    prediction_column: str = "prediction_time"
    synthetic: bool = True
    # Which feature this audit is about. "leaked" audits the suspect feature;
    # "safe_control" audits a legitimate one - the case where a reviewer asks
    # about a feature that turns out to be fine, and the tool must say so.
    subject: str = "leaked"
    source_path: Path | None = None

    @classmethod
    def load(cls, path: Path, project_root: Path | None = None) -> AuditConfig:
        path = Path(path)
        if not path.exists():
            raise AuditConfigError(f"Audit config not found: {path}")
        try:
            payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise AuditConfigError(f"Audit config is not valid JSON: {path} ({error})") from error

        root = Path(project_root) if project_root else path.parent.parent
        required = ("scenario", "transformation_sql", "remediation_sql", "post_outcome_table")
        missing = [key for key in required if not payload.get(key)]
        if missing:
            raise AuditConfigError(f"{path} is missing required keys: {', '.join(missing)}")

        config = cls(
            name=payload.get("name", path.stem),
            scenario_path=_resolve(root, payload["scenario"]),
            transformation_path=_resolve(root, payload["transformation_sql"]),
            remediation_path=_resolve(root, payload["remediation_sql"]),
            post_outcome_table=payload["post_outcome_table"],
            target_urn=payload.get("target_urn"),
            available_column=payload.get("available_column", "available_at"),
            prediction_column=payload.get("prediction_column", "prediction_time"),
            synthetic=bool(payload.get("synthetic", True)),
            subject=payload.get("subject", "leaked"),
            source_path=path,
        )
        config.validate()
        return config

    @classmethod
    def default(cls, project_root: Path) -> AuditConfig:
        """The seeded demo audit, used when no config is supplied."""
        configured = project_root / DEFAULT_AUDIT_PATH
        if configured.exists():
            return cls.load(configured, project_root)
        return cls(
            name="credit_default",
            scenario_path=project_root / "scenarios/credit_default/scenario.json",
            transformation_path=project_root / "examples/leaky_feature.sql",
            remediation_path=project_root / "examples/remediation.sql",
            post_outcome_table="payment_events_after_decision",
        )

    def validate(self) -> None:
        for label, path in (
            ("scenario", self.scenario_path),
            ("transformation_sql", self.transformation_path),
            ("remediation_sql", self.remediation_path),
        ):
            if not path.exists():
                raise AuditConfigError(f"{label} path does not exist: {path}")
        for label, value in (
            ("available_column", self.available_column),
            ("prediction_column", self.prediction_column),
        ):
            if not isinstance(value, str) or not value.strip():
                raise AuditConfigError(f"{label} must be a non-empty column name")
        if self.target_urn is not None and not self.target_urn.startswith("urn:li:"):
            raise AuditConfigError("target_urn must be a DataHub URN beginning with urn:li:")

    def describes(self, urn: str) -> bool:
        """Whether this audit's evidence is actually about ``urn``."""
        return self.target_urn is not None and self.target_urn == urn

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "scenario": str(self.scenario_path),
            "transformation_sql": str(self.transformation_path),
            "remediation_sql": str(self.remediation_path),
            "post_outcome_table": self.post_outcome_table,
            "available_column": self.available_column,
            "prediction_column": self.prediction_column,
            "target_urn": self.target_urn,
            "synthetic": self.synthetic,
            "subject": self.subject,
        }


def _resolve(root: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else (root / candidate)
