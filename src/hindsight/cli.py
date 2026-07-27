from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path

from hindsight.detectors import verify_temporal_cutoff
from hindsight.engine import audit_case
from hindsight.fixtures import run_fixture_replay
from hindsight.models import AuditCase
from hindsight.phase0.preflight import write_preflight
from hindsight.validation import run_credit_validation
from hindsight.workflow import run_demo_audit
from hindsight.writeback import publish_audit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hindsight")
    commands = parser.add_subparsers(dest="command", required=True)

    audit = commands.add_parser("audit-fixture", help="Audit one deterministic JSON case")
    audit.add_argument("case", type=Path)
    audit.add_argument("--output", type=Path)

    preflight = commands.add_parser("preflight", help="Check Phase 0 machine prerequisites")
    preflight.add_argument(
        "--output", type=Path, default=Path("evidence/phase0/preflight.local.json")
    )
    validate = commands.add_parser(
        "validate-credit", help="Run the frozen point-in-time credit validation"
    )
    validate.add_argument(
        "--scenario",
        type=Path,
        default=Path("scenarios/credit_default/scenario.json"),
    )
    validate.add_argument("--output", type=Path, default=Path("evaluations/results.local.json"))
    verify = commands.add_parser("verify-sql", help="Verify a temporal cutoff in SQL")
    verify.add_argument("sql", type=Path)
    verify.add_argument("--post-outcome-table", required=True)
    verify.add_argument("--available-column", default="available_at")
    verify.add_argument("--prediction-column", default="prediction_time")
    verify.add_argument("--dialect")
    verify.add_argument("--output", type=Path)
    demo = commands.add_parser("demo-audit", help="Run the complete offline evidence workflow")
    demo.add_argument(
        "--scenario", type=Path, default=Path("scenarios/credit_default/scenario.json")
    )
    demo.add_argument("--transformation", type=Path, default=Path("examples/leaky_feature.sql"))
    demo.add_argument("--remediation", type=Path, default=Path("examples/remediation.sql"))
    demo.add_argument("--post-outcome-table", default="payment_events_after_decision")
    demo.add_argument("--output", type=Path, default=Path("evidence/demo-audit.local.json"))
    publish = commands.add_parser(
        "publish-audit", help="Publish the demo audit through the approval gate"
    )
    publish.add_argument("--target-urn", required=True)
    publish.add_argument("--server", default=os.getenv("DATAHUB_GMS_URL", "http://localhost:8080"))
    publish.add_argument("--token", default=os.getenv("DATAHUB_GMS_TOKEN"))
    publish.add_argument("--approve-writeback", action="store_true")
    publish.add_argument("--output", type=Path, default=Path("evidence/publish-audit.local.json"))
    serve = commands.add_parser("serve", help="Start the judge-facing evidence console")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8100)
    replay = commands.add_parser("replay-fixture", help="Replay a hash-verified offline fixture")
    replay.add_argument("--fixture", type=Path, default=Path("fixtures/credit_default"))
    replay.add_argument(
        "--output", type=Path, default=Path("evaluations/fixture-replay.local.json")
    )
    live_fixture = commands.add_parser(
        "verify-fixture-live", help="Compare fixture semantics with a live DataHub asset"
    )
    live_fixture.add_argument("--fixture", type=Path, default=Path("fixtures/credit_default"))
    live_fixture.add_argument("--target-urn", required=True)
    live_fixture.add_argument(
        "--server", default=os.getenv("DATAHUB_GMS_URL", "http://localhost:8080")
    )
    live_fixture.add_argument("--token", default=os.getenv("DATAHUB_GMS_TOKEN"))
    live_fixture.add_argument(
        "--output", type=Path, default=Path("evidence/fixture-live.local.json")
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "preflight":
        report = write_preflight(args.output)
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "ready" else 2

    if args.command == "validate-credit":
        report = run_credit_validation(args.scenario)
        rendered = json.dumps(report, indent=2) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 0 if report["status"] == "passed" else 2

    if args.command == "verify-sql":
        result = verify_temporal_cutoff(
            args.sql.read_text(encoding="utf-8"),
            post_outcome_table=args.post_outcome_table,
            available_column=args.available_column,
            prediction_column=args.prediction_column,
            dialect=args.dialect,
        )
        rendered = json.dumps(result.to_dict(), indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return result.exit_code

    if args.command == "demo-audit":
        report = run_demo_audit(
            scenario_path=args.scenario,
            transformation_path=args.transformation,
            remediation_path=args.remediation,
            post_outcome_table=args.post_outcome_table,
        )
        rendered = json.dumps(report, indent=2) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return report["exit_code"]

    if args.command == "publish-audit":
        bundle = run_demo_audit(
            scenario_path=Path("scenarios/credit_default/scenario.json"),
            transformation_path=Path("examples/leaky_feature.sql"),
            remediation_path=Path("examples/remediation.sql"),
            post_outcome_table="payment_events_after_decision",
        )
        report = publish_audit(
            bundle,
            target_urn=args.target_urn,
            server=args.server,
            token=args.token,
            approved=args.approve_writeback,
        )
        rendered = json.dumps(report, indent=2) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 0 if report["status"] == "published" else 2

    if args.command == "serve":
        import uvicorn

        from hindsight.web import create_app

        uvicorn.run(create_app(), host=args.host, port=args.port)
        return 0

    if args.command == "replay-fixture":
        report = run_fixture_replay(args.fixture)
        rendered = json.dumps(report, indent=2) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return report["exit_code"]

    if args.command == "verify-fixture-live":
        from hindsight.fixtures.live import verify_live_fixture

        report = verify_live_fixture(
            args.fixture,
            target_urn=args.target_urn,
            server=args.server,
            token=args.token,
        )
        rendered = json.dumps(report, indent=2) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 0 if report["status"] == "passed" else 2

    payload = json.loads(args.case.read_text(encoding="utf-8"))
    result = audit_case(AuditCase.from_dict(payload))
    rendered = json.dumps(result.to_dict(), indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
