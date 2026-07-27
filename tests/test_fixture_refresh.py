import shutil
from pathlib import Path

from hindsight.fixtures.refresh import refresh_fixture_hashes
from hindsight.fixtures.replay import run_fixture_replay


def test_fixture_hash_refresh_requires_explicit_approval(tmp_path: Path) -> None:
    copied = tmp_path / "fixture"
    shutil.copytree(Path("fixtures/credit_default"), copied)
    lineage = copied / "responses/lineage.json"
    lineage.write_text(lineage.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    preview = refresh_fixture_hashes(copied)
    assert preview["status"] == "preview"
    assert preview["mutation_performed"] is False
    assert preview["changes"]
    assert run_fixture_replay(copied)["status"] == "integrity_failed"

    refreshed = refresh_fixture_hashes(copied, approved=True)
    assert refreshed["status"] == "refreshed"
    assert refreshed["mutation_performed"] is True
    assert run_fixture_replay(copied)["status"] == "passed"
