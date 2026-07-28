from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from hindsight.config import AuditConfig
from hindsight.demo import run_judge_demo
from hindsight.scenarios import get_scenario, list_scenarios
from hindsight.web.activity import build_activity
from hindsight.web.explain import explain
from hindsight.web.glossary import GLOSSARY
from hindsight.web.health import datahub_health
from hindsight.web.runs import get_run, list_runs, record_run
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
    app.mount("/static", StaticFiles(directory=WEB_ROOT / "static"), name="static")

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
            context=_shell(root, "audits", runs) | {"runs": runs},
        )

    @app.post("/audits/run")
    def run_audit(request: Request, scenario: Annotated[str, Form()] = "") -> RedirectResponse:
        bundle = _audit(root, scenario or None)
        run = record_run(root, bundle, scenario=scenario or None)
        suffix = f"?scenario={scenario}" if scenario else ""
        return RedirectResponse(url=f"/audits/{run['run_id']}{suffix}", status_code=303)

    @app.get("/audits/latest", response_class=HTMLResponse)
    def latest_audit(request: Request) -> Any:
        runs = list_runs(root)
        if runs:
            return RedirectResponse(url=f"/audits/{runs[0]['run_id']}", status_code=303)
        bundle = _audit(root)
        run = record_run(root, bundle)
        return RedirectResponse(url=f"/audits/{run['run_id']}", status_code=303)

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
        slug = scenario or run.get("scenario")
        return _render_detail(templates, request, root, run=run, scenario_slug=slug)

    @app.get("/evidence", response_class=HTMLResponse)
    def evidence(request: Request) -> HTMLResponse:
        runs = list_runs(root)
        return templates.TemplateResponse(
            request=request,
            name="evidence.html",
            context=_shell(root, "evidence", runs) | {"runs": runs},
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
        server: Annotated[str, Form()] = "http://localhost:8080",
        approve_writeback: Annotated[bool, Form()] = False,
    ) -> HTMLResponse:
        config = _audit_config(root)
        if not config.describes(target_urn):
            publication = {
                "status": "error",
                "message": (
                    f"Refusing to publish: this audit describes {config.target_urn}, "
                    f"not {target_urn}. Writing the verdict to an asset it does not "
                    "describe would put false evidence in the catalog."
                ),
                "mutation_performed": False,
            }
            return _render_detail(
                templates,
                request,
                root,
                publication=publication,
                target_urn=target_urn,
                server=server,
            )
        try:
            publication = publish_audit(
                _audit(root),
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
        record_run(root, _audit(root), publication=publication)
        return _render_detail(
            templates,
            request,
            root,
            publication=publication,
            target_urn=target_urn,
            server=server,
        )

    return app


# ---- Rendering ----------------------------------------------------------


def _shell(root: Path, active: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Context every page needs: nav state, glossary, and honest connection state."""
    return {
        "active": active,
        "glossary": GLOSSARY,
        "health": datahub_health(),
        "run_count": len(runs),
    }


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
    bundle = _audit(root, scenario_slug)
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
            "timeline": build_timeline(bundle, scenario_data),
            "leakage": leakage,
            "safe": safe,
            "publication": publication,
            "target_urn": target_urn,
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
    """Resolve which audit to run, honouring an explicit scenario choice."""
    if scenario_slug:
        scenario = get_scenario(scenario_slug)
        candidate = root / scenario.audit_config
        if candidate.exists():
            return AuditConfig.load(candidate, root)
    configured = os.getenv("HINDSIGHT_AUDIT")
    if configured:
        return AuditConfig.load(Path(configured), root)
    return AuditConfig.default(root)


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
    )
    judge_demo = run_judge_demo(root)
    bundle["ablation_contrast"] = judge_demo["ablation_contrast"]
    bundle["demo_disclosures"] = judge_demo["disclosures"]
    bundle["audit_config"] = config.to_dict()

    _AUDIT_CACHE[fingerprint] = bundle
    return bundle


def _fingerprint(config: AuditConfig) -> tuple[Any, ...]:
    """Invalidate the cache when any input file changes on disk."""
    stamps = []
    for path in (config.scenario_path, config.transformation_path, config.remediation_path):
        try:
            stamps.append((str(path), path.stat().st_mtime_ns))
        except OSError:
            stamps.append((str(path), None))
    return (config.name, config.post_outcome_table, tuple(stamps))


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
