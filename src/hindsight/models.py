from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class Verdict(StrEnum):
    INSUFFICIENT_METADATA = "insufficient_metadata"
    NEEDS_REVIEW = "needs_review"
    HIGH_CONFIDENCE = "high_confidence"
    CONFIRMED = "confirmed"
    CLEAR_FOR_RELEASE = "clear_for_release"


BLOCKING_VERDICTS = {Verdict.HIGH_CONFIDENCE, Verdict.CONFIRMED}


@dataclass(frozen=True)
class AuditCase:
    case_id: str
    model_urn: str
    feature_urn: str
    lineage_path: tuple[str, ...] = ()
    source_kind: str | None = None
    source_available_at: datetime | None = None
    prediction_time: datetime | None = None
    metadata_complete: bool = True
    suspicious_common_ancestry: bool = False
    deterministic_cutoff_proof: bool = False
    point_in_time_advantage_collapsed: bool = False
    ablation_delta: float | None = None
    notes: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AuditCase:
        data = dict(payload)
        data["lineage_path"] = tuple(data.get("lineage_path", ()))
        data["notes"] = tuple(data.get("notes", ()))
        for key in ("source_available_at", "prediction_time"):
            if isinstance(data.get(key), str):
                data[key] = datetime.fromisoformat(data[key].replace("Z", "+00:00"))
        return cls(**data)


@dataclass(frozen=True)
class AuditResult:
    case_id: str
    verdict: Verdict
    reasons: tuple[str, ...]
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def exit_code(self) -> int:
        if self.verdict is Verdict.CLEAR_FOR_RELEASE:
            return 0
        if self.verdict in BLOCKING_VERDICTS:
            return 3
        return 2

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["verdict"] = self.verdict.value
        payload["exit_code"] = self.exit_code
        return payload
