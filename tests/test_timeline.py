"""The cutoff timeline is an evidence graphic, so its geometry must be checked.

A drawing that says "this feature reached past the decision" is a claim. If the
bar stops short of the cutoff, or the safe control crosses it, the picture is
lying about the audit it illustrates.
"""

from pathlib import Path

from hindsight.web.timeline import CUTOFF_PCT, build_timeline

SCENARIO = {"prediction_time": "2026-01-10T09:00:00Z"}


def _timeline(bundle: dict | None = None):
    return build_timeline(bundle or {}, SCENARIO)


def test_every_track_starts_before_the_cutoff() -> None:
    for track in _timeline().tracks:
        assert track.start_pct < CUTOFF_PCT, track.label


def test_only_the_leaked_feature_crosses_the_cutoff() -> None:
    timeline = _timeline()
    crossing = [t for t in timeline.tracks if t.crosses]
    assert len(crossing) == 1
    assert crossing[0].kind == "leak"
    assert crossing[0].reach_pct > CUTOFF_PCT


def test_the_safe_control_stops_exactly_at_the_cutoff() -> None:
    """If the control appeared to cross, the graphic would contradict the verdict."""
    safe = next(t for t in _timeline().tracks if t.kind == "safe")
    assert safe.end_pct == CUTOFF_PCT
    assert not safe.crosses
    assert safe.reach_pct == 0.0


def test_all_positions_stay_inside_the_drawing() -> None:
    for track in _timeline().tracks:
        assert 0.0 <= track.start_pct <= 100.0, track.label
        assert 0.0 <= track.end_pct <= 100.0, track.label
        assert track.end_pct > track.start_pct, track.label
        if track.crosses:
            assert track.reach_pct <= 100.0, track.label


def test_violation_size_is_taken_from_the_audit_not_hardcoded() -> None:
    bundle = {"sql_verification": {"days_after": 12}}
    leak = next(t for t in build_timeline(bundle, SCENARIO).tracks if t.kind == "leak")
    assert leak.days_after == 12
    assert "12 days" in leak.note


def test_axis_marks_the_cutoff() -> None:
    ticks = _timeline().ticks
    cutoff_ticks = [t for t in ticks if t["is_cutoff"]]
    assert len(cutoff_ticks) == 1
    assert cutoff_ticks[0]["label"] == "decision"
    assert abs(cutoff_ticks[0]["pct"] - CUTOFF_PCT) < 0.5


def test_a_malformed_prediction_time_still_renders() -> None:
    timeline = build_timeline({}, {"prediction_time": "not-a-date"})
    assert timeline.tracks
    assert timeline.cutoff_label


def test_every_track_carries_a_text_note_so_colour_is_never_alone() -> None:
    for track in _timeline().tracks:
        assert track.note, track.label


def test_rendered_timeline_has_a_table_view_twin() -> None:
    from fastapi.testclient import TestClient

    from hindsight.web import create_app
    from hindsight.web.runs import record_run

    client = TestClient(create_app(Path.cwd()))
    run = record_run(Path.cwd(), client.get("/api/audit").json())
    text = client.get(f"/audits/{run['run_id']}").text

    assert "Table view of the timeline" in text
    assert "Knowable at decision time" in text
    assert "Did not exist yet" in text
    assert "Prediction cutoff" in text
