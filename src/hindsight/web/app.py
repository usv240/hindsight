from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from hindsight.config import AuditConfig
from hindsight.demo import run_judge_demo
from hindsight.web.activity import build_activity
from hindsight.web.glossary import GLOSSARY
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

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/audit")
    def audit_api() -> dict[str, Any]:
        return _audit(root)

    @app.get("/api/activity")
    def activity_api() -> dict[str, Any]:
        """The backend log the console replays, so visitors can watch the work."""
        return {"activity": build_activity(root, _audit(root))}

    @app.get("/api/glossary")
    def glossary_api() -> dict[str, Any]:
        return {"glossary": GLOSSARY}

    @app.get("/", response_class=HTMLResponse)
    def console(request: Request) -> HTMLResponse:
        return _render(templates, request, _audit(root))

    @app.post("/publish", response_class=HTMLResponse)
    def publish(
        request: Request,
        target_urn: Annotated[str, Form()],
        server: Annotated[str, Form()] = "http://localhost:8080",
        approve_writeback: Annotated[bool, Form()] = False,
    ) -> HTMLResponse:
        bundle = _audit(root)
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
            return _render(
                templates,
                request,
                bundle,
                publication=publication,
                target_urn=target_urn,
                server=server,
            )
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
        return _render(
            templates,
            request,
            bundle,
            publication=publication,
            target_urn=target_urn,
            server=server,
        )

    return app


def _render(
    templates: Jinja2Templates,
    request: Request,
    bundle: dict[str, Any],
    *,
    publication: dict[str, Any] | None = None,
    target_urn: str = "",
    server: str = "http://localhost:8080",
) -> HTMLResponse:
    leakage = bundle["validation"]["leakage_case"]
    safe = bundle["validation"]["safe_control"]
    root = Path(request.app.state.project_root)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "bundle": bundle,
            "leakage": leakage,
            "safe": safe,
            "publication": publication,
            "target_urn": target_urn,
            "server": server,
            "glossary": GLOSSARY,
            "activity": build_activity(root, bundle, publication),
            "advantage_lost": round((1 - leakage["advantage_retained"]) * 100, 1),
            "safe_retained": round(safe["advantage_retained"] * 100),
            "observed_width": round(leakage["observed_auc"] * 100, 1),
            "reconstructed_width": round(leakage["point_in_time_auc"] * 100, 1),
            "safe_width": round(safe["observed_auc"] * 100, 1),
        },
    )


def _audit_config(root: Path) -> AuditConfig:
    configured = os.getenv("HINDSIGHT_AUDIT")
    if configured:
        return AuditConfig.load(Path(configured), root)
    return AuditConfig.default(root)


def _audit(root: Path) -> dict[str, Any]:
    """Run the audit, reusing the last result while its inputs are unchanged.

    The audit trains models and runs a DuckDB reconstruction. Recomputing that on
    every page load, and again for each API call the page makes, is wasteful and
    makes the console feel broken under any real traffic.
    """
    config = _audit_config(root)
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

    _AUDIT_CACHE.clear()
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
