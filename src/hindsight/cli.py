from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path

from hindsight.config import AuditConfig, AuditConfigError
from hindsight.demo import render_judge_demo, run_judge_demo
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

    golden = commands.add_parser("demo", help="Start here: run the complete judge demo")
    golden.add_argument("--json", action="store_true")
    golden.add_argument("--output", type=Path)

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
    demo.add_argument("--audit", type=Path, help="Audit config describing what to audit")
    demo.add_argument("--scenario", type=Path)
    demo.add_argument("--transformation", type=Path)
    demo.add_argument("--remediation", type=Path)
    demo.add_argument("--post-outcome-table")
    demo.add_argument("--output", type=Path, default=Path("evidence/demo-audit.local.json"))
    publish = commands.add_parser(
        "publish-audit", help="Publish an audit through the approval gate"
    )
    publish.add_argument("--audit", type=Path, help="Audit config describing what to audit")
    publish.add_argument("--target-urn", required=True)
    publish.add_argument("--server", default=os.getenv("DATAHUB_GMS_URL", "http://localhost:8080"))
    publish.add_argument("--token", default=os.getenv("DATAHUB_GMS_TOKEN"))
    publish.add_argument("--approve-writeback", action="store_true")
    publish.add_argument(
        "--allow-urn-mismatch",
        action="store_true",
        help="Publish even though the audit config names a different asset",
    )
    publish.add_argument("--output", type=Path, default=Path("evidence/publish-audit.local.json"))
    serve = commands.add_parser("serve", help="Start the judge-facing evidence console")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8100)
    serve.add_argument("--audit", type=Path, help="Audit config the console should report on")
    serve.add_argument(
        "--target-urn",
        help="Bind console write-back to this exact DataHub asset URN",
    )
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


def _is_loopback(host: str) -> bool:
    return host in {"127.0.0.1", "localhost", "::1", ""}


def _resolve_audit_config(args: argparse.Namespace) -> AuditConfig:
    """Build the audit target from --audit, then let explicit flags override it."""
    root = Path.cwd()
    if getattr(args, "audit", None):
        config = AuditConfig.load(args.audit, root)
    else:
        config = AuditConfig.default(root)

    overrides: dict[str, object] = {}
    if getattr(args, "scenario", None):
        overrides["scenario_path"] = args.scenario
    if getattr(args, "transformation", None):
        overrides["transformation_path"] = args.transformation
    if getattr(args, "remediation", None):
        overrides["remediation_path"] = args.remediation
    if getattr(args, "post_outcome_table", None):
        overrides["post_outcome_table"] = args.post_outcome_table
    if not overrides:
        return config

    from dataclasses import replace

    updated = replace(config, **overrides)  # type: ignore[arg-type]
    updated.validate()
    return updated


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        report = run_judge_demo(Path.cwd())
        rendered = json.dumps(report, indent=2) + "\n" if args.json else render_judge_demo(report)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(rendered, end="")
        return report["exit_code"]

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
        try:
            config = _resolve_audit_config(args)
        except AuditConfigError as error:
            print(f"error: {error}")
            return 2
        report = run_demo_audit(
            scenario_path=config.scenario_path,
            transformation_path=config.transformation_path,
            remediation_path=config.remediation_path,
            post_outcome_table=config.post_outcome_table,
            available_column=config.available_column,
            prediction_column=config.prediction_column,
            subject=config.subject,
        )
        report["audit_config"] = config.to_dict()
        rendered = json.dumps(report, indent=2) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return report["exit_code"]

    if args.command == "publish-audit":
        try:
            config = _resolve_audit_config(args)
        except AuditConfigError as error:
            print(f"error: {error}")
            return 2

        # Evidence must describe the asset it is written to. Without this an
        # operator can tag any URN in the catalog with an unrelated verdict.
        if (
            args.approve_writeback
            and not config.describes(args.target_urn)
            and not args.allow_urn_mismatch
        ):
            print(
                "error: refusing to publish.\n"
                f"  audit '{config.name}' describes {config.target_urn}\n"
                f"  but --target-urn is        {args.target_urn}\n"
                "  Writing this verdict to an asset it does not describe would put false\n"
                "  evidence in your catalog. Pass --allow-urn-mismatch only if you are sure."
            )
            return 2

        bundle = run_demo_audit(
            scenario_path=config.scenario_path,
            transformation_path=config.transformation_path,
            remediation_path=config.remediation_path,
            post_outcome_table=config.post_outcome_table,
            available_column=config.available_column,
            prediction_column=config.prediction_column,
            subject=config.subject,
        )
        bundle["audit_config"] = config.to_dict()
        report = publish_audit(
            bundle,
            target_urn=args.target_urn,
            server=args.server,
            token=args.token,
            approved=args.approve_writeback,
        )
        report["audit_config"] = config.to_dict()
        if (
            args.approve_writeback
            and not config.describes(args.target_urn)
            and args.allow_urn_mismatch
        ):
            report["urn_mismatch_override"] = True
        rendered = json.dumps(report, indent=2) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 0 if report["status"] == "published" else 2

    if args.command == "serve":
        import uvicorn

        from hindsight.web import create_app

        if not _is_loopback(args.host):
            print(
                f"warning: binding to {args.host}, not loopback.\n"
                "  The console can write to your DataHub catalog and has no authentication.\n"
                "  Put it behind an authenticating proxy before exposing it."
            )
        if args.audit:
            os.environ["HINDSIGHT_AUDIT"] = str(args.audit)
        if args.target_urn:
            os.environ["HINDSIGHT_TARGET_URN"] = args.target_urn
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
