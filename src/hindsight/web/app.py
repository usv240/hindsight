from __future__ import annotations

import json
import os
import secrets
from dataclasses import replace
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from hindsight.config import AuditConfig
from hindsight.demo import run_judge_demo
from hindsight.scenarios import SCENARIOS, get_scenario, list_scenarios
from hindsight.web import demo_mode
from hindsight.web.activity import build_activity
from hindsight.web.artifacts import collect as collect_artifacts
from hindsight.web.explain import explain
from hindsight.web.glossary import GLOSSARY
from hindsight.web.health import datahub_health
from hindsight.web.runs import get_run, group_by_scenario, list_runs, record_run
from hindsight.web.subject import describe as describe_subject
from hindsight.web.timeline import build_timeline
from hindsight.workflow import run_demo_audit
from hindsight.writeback import publish_audit

WEB_ROOT = Path(__file__).parent

# Single-entry cache keyed on the audit inputs and their mtimes.
_AUDIT_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}


def create_app(project_root: Path | None = None) -> FastAPI:
    root = project_root or _find_project_root()
    app = FastAPI(
        title="Hindsight Evidence Console",
        description="Evidence-based ML release audits backed by DataHub lineage.",
        version="0.1.0",
    )
    app.state.project_root = root
    templates = Jinja2Templates(directory=WEB_ROOT / "templates")
    csrf_token = secrets.token_urlsafe(32)
    app.state.csrf_token = csrf_token
    templates.env.globals["csrf_token"] = csrf_token
    app.mount("/static", StaticFiles(directory=WEB_ROOT / "static"), name="static")
    templates.env.globals["public_demo"] = demo_mode.enabled

    # ---- API ------------------------------------------------------------

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/health/datahub")
    def datahub_health_api() -> dict[str, Any]:
        """Probed, never asserted. The status pill polls this."""
        return datahub_health()

    @app.get("/api/audit")
    def audit_api() -> dict[str, Any]:
        return _audit(root)

    @app.get("/api/activity")
    def activity_api() -> dict[str, Any]:
        return {"activity": build_activity(root, _audit(root))}

    @app.get("/api/glossary")
    def glossary_api() -> dict[str, Any]:
        return {"glossary": GLOSSARY}

    @app.get("/api/runs")
    def runs_api() -> dict[str, Any]:
        return {"runs": list_runs(root)}

    # ---- Pages ----------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def overview(request: Request) -> HTMLResponse:
        runs = list_runs(root)
        return templates.TemplateResponse(
            request=request,
            name="overview.html",
            context=_shell(root, "overview", runs)
            | {
                "latest": runs[0] if runs else None,
                "scenarios": [s.to_dict() for s in list_scenarios()],
            },
        )

    @app.get("/audits", response_class=HTMLResponse)
    def audits(request: Request) -> HTMLResponse:
        runs = list_runs(root)
        return templates.TemplateResponse(
            request=request,
            name="audits.html",
            context=_shell(root, "audits", runs)
            | {"runs": runs, "groups": group_by_scenario(runs)},
        )

    @app.post("/audits/run")
    def run_audit(
        request: Request,
        csrf_token: Annotated[str, Form()] = "",
        scenario: Annotated[str, Form()] = "",
    ) -> RedirectResponse:
        _refuse_if_public_demo()
        _require_csrf(request, csrf_token)
        if scenario and scenario not in SCENARIOS:
            raise HTTPException(status_code=400, detail="Unknown audit scenario")
        bundle = _audit(root, scenario or None)
        run = record_run(root, bundle, scenario=scenario or None)
        suffix = f"?scenario={scenario}" if scenario else ""
        return RedirectResponse(url=f"/audits/{run['run_id']}{suffix}", status_code=303)

    @app.get("/audits/latest", response_class=HTMLResponse)
    def latest_audit(request: Request) -> Any:
        runs = list_runs(root)
        if runs:
            return RedirectResponse(url=f"/audits/{runs[0]['run_id']}", status_code=303)
        return RedirectResponse(url="/", status_code=303)

    @app.get("/audits/{run_id}", response_class=HTMLResponse)
    def audit_detail(request: Request, run_id: str, scenario: str = "") -> HTMLResponse:
        run = get_run(root, run_id)
        if run is None:
            return templates.TemplateResponse(
                request=request,
                name="not_found.html",
                context=_shell(root, "audits", list_runs(root)) | {"run_id": run_id},
                status_code=404,
            )
        slug = run.get("scenario") or scenario
        return _render_detail(templates, request, root, run=run, scenario_slug=slug)

    @app.get("/evidence", response_class=HTMLResponse)
    def evidence(request: Request) -> HTMLResponse:
        runs = list_runs(root)
        return templates.TemplateResponse(
            request=request,
            name="evidence.html",
            context=_shell(root, "evidence", runs)
            | {"runs": runs, "artifacts": collect_artifacts(root)},
        )

    @app.get("/settings", response_class=HTMLResponse)
    def settings(request: Request) -> HTMLResponse:
        runs = list_runs(root)
        return templates.TemplateResponse(
            request=request,
            name="settings.html",
            context=_shell(root, "settings", runs)
            | {"audit_config": _audit_config(root).to_dict()},
        )

    @app.post("/publish", response_class=HTMLResponse)
    def publish(
        request: Request,
        target_urn: Annotated[str, Form()],
        csrf_token: Annotated[str, Form()] = "",
        server: Annotated[str, Form()] = "http://localhost:8080",
        approve_writeback: Annotated[bool, Form()] = False,
        scenario: Annotated[str, Form()] = "",
    ) -> HTMLResponse:
        _refuse_if_public_demo()
        _require_csrf(request, csrf_token)
        if scenario and scenario not in SCENARIOS:
            raise HTTPException(status_code=400, detail="Unknown audit scenario")
        slug = scenario or None
        config = _audit_config(root, slug)
        if approve_writeback and not config.describes(target_urn):
            described = config.target_urn or "no bound target"
            publication = {
                "status": "error",
                "message": (
                    f"Refusing approved write-back: this audit describes {described}, "
                    f"not {target_urn}. Bind the exact target before publishing."
                ),
                "mutation_performed": False,
            }
            return _render_detail(
                templates,
                request,
                root,
                scenario_slug=slug,
                publication=publication,
                target_urn=target_urn,
                server=server,
            )
        bundle = _audit(root, slug)
        try:
            publication = publish_audit(
                bundle,
                target_urn=target_urn,
                server=server,
                token=os.getenv("DATAHUB_GMS_TOKEN"),
                approved=approve_writeback,
            )
        except (RuntimeError, ValueError) as error:
            publication = {
                "status": "error",
                "message": str(error),
                "mutation_performed": False,
            }
        record_run(root, bundle, publication=publication, scenario=slug)
        return _render_detail(
            templates,
            request,
            root,
            scenario_slug=slug,
            publication=publication,
            target_urn=target_urn,
            server=server,
        )

    return app


def _require_csrf(request: Request, supplied: str) -> None:
    expected = request.app.state.csrf_token
    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=403, detail="Invalid form token")


# ---- Rendering ----------------------------------------------------------


def _shell(root: Path, active: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Context every page needs: nav state, glossary, and honest connection state."""
    return {
        "active": active,
        "glossary": GLOSSARY,
        "health": datahub_health(),
        "run_count": len(runs),
        # In the hosted demo the run buttons become links into recorded runs,
        # so every template that offers one needs the mapping.
        "scenario_links": demo_mode.scenario_links(runs),
    }


def _refuse_if_public_demo() -> None:
    """Stop a mutating route before it costs anything.

    Checked first in the handler, ahead of CSRF and argument validation, so the
    public deployment never trains a model or opens a connection on request.
    """
    if demo_mode.enabled():
        raise HTTPException(status_code=403, detail=demo_mode.REFUSAL)


def _render_detail(
    templates: Jinja2Templates,
    request: Request,
    root: Path,
    *,
    run: dict[str, Any] | None = None,
    scenario_slug: str | None = None,
    publication: dict[str, Any] | None = None,
    target_urn: str = "",
    server: str = "http://localhost:8080",
) -> HTMLResponse:
    stored_bundle = run.get("evidence_bundle") if run else None
    bundle = stored_bundle if isinstance(stored_bundle, dict) else _audit(root, scenario_slug)
    leakage = bundle["validation"]["leakage_case"]
    safe = bundle["validation"]["safe_control"]
    runs = list_runs(root)
    scenario = get_scenario(scenario_slug)
    config = _audit_config(root, scenario_slug)
    scenario_data = _read_json(config.scenario_path)
    return templates.TemplateResponse(
        request=request,
        name="audit_detail.html",
        context=_shell(root, "audits", runs)
        | {
            "bundle": bundle,
            "run": run,
            "scenario": scenario.to_dict(),
            "scenarios": [s.to_dict() for s in list_scenarios()],
            "plain": explain(bundle, scenario.to_dict()),
            # A verdict about "this model" is not an audit record until it says
            # which model, which feature, and as of when.
            "subject": describe_subject(
                root,
                scenario_slug or config.name,
                bundle=bundle,
                run=run,
                subject=config.subject,
            ),
            "timeline": build_timeline(bundle, scenario_data),
            "leakage": leakage,
            "safe": safe,
            "publication": publication,
            "target_urn": target_urn or config.target_urn or "",
            "writeback_bound": config.target_urn is not None,
            "server": server,
            "activity": build_activity(root, bundle, publication),
            "advantage_lost": round((1 - leakage["advantage_retained"]) * 100, 1),
            "safe_retained": round(safe["advantage_retained"] * 100),
            "observed_width": round(leakage["observed_auc"] * 100, 1),
            "reconstructed_width": round(leakage["point_in_time_auc"] * 100, 1),
            "safe_width": round(safe["observed_auc"] * 100, 1),
        },
    )


# ---- Audit --------------------------------------------------------------


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _audit_config(root: Path, scenario_slug: str | None = None) -> AuditConfig:
    """Resolve the audit and optionally bind its exact DataHub target from env."""
    if scenario_slug:
        scenario = get_scenario(scenario_slug)
        candidate = root / scenario.audit_config
        config = (
            AuditConfig.load(candidate, root) if candidate.exists() else AuditConfig.default(root)
        )
    else:
        configured = os.getenv("HINDSIGHT_AUDIT")
        config = (
            AuditConfig.load(Path(configured), root) if configured else AuditConfig.default(root)
        )

    target_urn = os.getenv("HINDSIGHT_TARGET_URN")
    return replace(config, target_urn=target_urn) if target_urn else config


def _audit(root: Path, scenario_slug: str | None = None) -> dict[str, Any]:
    """Run the audit, reusing the last result while its inputs are unchanged.

    The audit trains models and runs a DuckDB reconstruction. Recomputing that on
    every page load, and again for each API call the page makes, is wasteful and
    makes the console feel broken under any real traffic.
    """
    config = _audit_config(root, scenario_slug)
    fingerprint = _fingerprint(config)
    cached = _AUDIT_CACHE.get(fingerprint)
    if cached is not None:
        return cached

    bundle = run_demo_audit(
        scenario_path=config.scenario_path,
        transformation_path=config.transformation_path,
        remediation_path=config.remediation_path,
        post_outcome_table=config.post_outcome_table,
        available_column=config.available_column,
        prediction_column=config.prediction_column,
        subject=config.subject,
    )
    judge_demo = run_judge_demo(root)
    bundle["ablation_contrast"] = judge_demo["ablation_contrast"]
    bundle["demo_disclosures"] = judge_demo["disclosures"]
    bundle["audit_config"] = config.to_dict()

    if len(_AUDIT_CACHE) >= 32:
        _AUDIT_CACHE.clear()
    _AUDIT_CACHE[fingerprint] = bundle
    return bundle


def _fingerprint(config: AuditConfig) -> tuple[Any, ...]:
    """Invalidate cached evidence when any input or binding changes."""
    stamps = []
    paths = [
        config.scenario_path,
        config.transformation_path,
        config.remediation_path,
    ]
    if config.source_path is not None:
        paths.append(config.source_path)
    for path in paths:
        try:
            stamps.append((str(path), path.stat().st_mtime_ns))
        except OSError:
            stamps.append((str(path), None))
    semantics = (
        config.name,
        config.post_outcome_table,
        config.available_column,
        config.prediction_column,
        config.target_urn,
        config.synthetic,
    )
    return semantics + (tuple(stamps),)


def _find_project_root() -> Path:
    configured = os.getenv("HINDSIGHT_PROJECT_ROOT")
    if configured:
        return Path(configured).resolve()
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / "scenarios/credit_default/scenario.json").exists():
            return candidate
    raise RuntimeError(
        "Could not locate Hindsight project root; set HINDSIGHT_PROJECT_ROOT explicitly"
    )
