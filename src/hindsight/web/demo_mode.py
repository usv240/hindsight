"""Public read-only mode for the hosted demo.

The console is normally a local tool: you point it at your own DataHub, run
audits, and approve write-back. On a public URL none of that is safe. Running an
audit retrains a model, so an open ``POST /audits/run`` is a CPU tarpit anyone
can pull on, and ``POST /publish`` mutates a catalog.

Rather than bolt authentication onto a demo, this mode removes the ability
entirely. Set ``HINDSIGHT_PUBLIC_DEMO=1`` and the server serves only what was
already recorded:

  * both mutating routes refuse with 403 before doing any work
  * the run buttons become links into the runs that already exist, so a visitor
    still reaches every scenario - they just do not get to spend the CPU
  * the write-back form is replaced by an explanation of what it would do

That is a smaller product, and it is deliberately the honest one to expose: the
evidence a visitor reads is the same evidence the tool produced locally, not a
staged copy.
"""

from __future__ import annotations

import os
from typing import Any

ENV_VAR = "HINDSIGHT_PUBLIC_DEMO"

_TRUTHY = {"1", "true", "yes", "on"}

REFUSAL = (
    "This is the public read-only demo. Running an audit trains a model and "
    "publishing writes to a DataHub catalog, so both are disabled here. Clone "
    "the repository and run `uv run hindsight serve` to do either."
)


def enabled() -> bool:
    """Whether this process is serving the public demo.

    Read at request time rather than cached at import, so a test can toggle it
    with monkeypatch and so a container can be restarted into the other mode
    without rebuilding.
    """
    return os.getenv(ENV_VAR, "").strip().lower() in _TRUTHY


def scenario_links(runs: list[dict[str, Any]]) -> dict[str, str]:
    """Most recent recorded run id for each scenario.

    ``runs`` arrives newest first, so the first sighting of a scenario wins.
    A scenario with no recorded run is absent from the mapping; the caller is
    expected to fall back rather than link somewhere that 404s.
    """
    latest: dict[str, str] = {}
    for run in runs:
        slug = run.get("scenario")
        run_id = run.get("run_id")
        if slug and run_id and slug not in latest:
            latest[slug] = run_id
    return latest
