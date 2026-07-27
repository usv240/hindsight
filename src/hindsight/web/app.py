from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from hindsight.demo import run_judge_demo
from hindsight.web.activity import build_activity
from hindsight.web.glossary import GLOSSARY
from hindsight.workflow import run_demo_audit
from hindsight.writeback import publish_audit

WEB_ROOT = Path(__file__).parent


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


def _audit(root: Path) -> dict[str, Any]:
    bundle = run_demo_audit(
        scenario_path=root / "scenarios/credit_default/scenario.json",
        transformation_path=root / "examples/leaky_feature.sql",
        remediation_path=root / "examples/remediation.sql",
        post_outcome_table="payment_events_after_decision",
    )
    judge_demo = run_judge_demo(root)
    bundle["ablation_contrast"] = judge_demo["ablation_contrast"]
    bundle["demo_disclosures"] = judge_demo["disclosures"]
    return bundle


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
