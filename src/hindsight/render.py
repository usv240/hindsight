"""Terminal summaries for the two commands that used to print only JSON.

A judge who runs a documented command should see the answer, not 131 lines of
record. Both commands still write the full JSON to ``--output``, and ``--json``
puts it back on stdout, so nothing that consumed the machine-readable form
changes. This module only decides what a human sees first.

Deliberately ASCII. These strings reach Windows consoles on legacy code pages,
where a check mark raises UnicodeEncodeError and turns a passing run into a
traceback.
"""

from __future__ import annotations

from typing import Any


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_point_in_time(report: dict[str, Any]) -> str:
    """One screen: what the feature looked worth, and what it was worth."""
    if report.get("status") == "invalid_input":
        return f"INVALID INPUT\n  {report.get('error', 'unknown error')}\n"

    leak = report["leakage_case"]
    safe = report["safe_control"]
    recon = report["reconstruction"]
    verdict = report["verdicts"]["leakage_case"]["verdict"]

    lines = [
        f"POINT-IN-TIME RECONSTRUCTION - {report['scenario']}",
        "=" * 58,
        "",
        "SUSPECT FEATURE",
        f"  baseline, honest features only   {leak['baseline_auc']:.3f} AUC",
        f"  with the suspect feature         {leak['observed_auc']:.3f}",
        f"  rebuilt as of the decision       {leak['point_in_time_auc']:.3f}",
        f"  advantage retained               {_pct(leak['advantage_retained']):>6}",
        f"  post-cutoff records excluded     {recon['excluded_post_cutoff_records']}",
        "",
        (
            f"  It looked worth {leak['observed_advantage']:.3f} AUC. "
            f"Once records that did not exist at the"
        ),
        f"  decision were removed, it was worth {leak['point_in_time_advantage']:.4f}.",
        "",
        "LEGITIMATE CONTROL (audited the same way, must stay clean)",
        f"  observed {safe['observed_auc']:.3f} -> point-in-time {safe['point_in_time_auc']:.3f}",
        f"  advantage retained               {_pct(safe['advantage_retained']):>6}",
        f"  collapsed                        {safe['collapsed']}",
        "",
        f"VERDICT: {verdict}",
        f"status: {report['status']}   rows: {report['rows']}   seed: {report['seed']}",
        "",
        "Full evidence record written to the --output path. Add --json to print it.",
        "",
    ]
    return "\n".join(lines)


def render_sweep(report: dict[str, Any]) -> str:
    """A ranked table, with the disclosure that a ranking is not a verdict."""
    if report.get("status") == "invalid_input":
        return f"INVALID INPUT\n  {report.get('error', 'unknown error')}\n"

    findings = report.get("findings", [])
    lines = [
        f"FEATURE SWEEP - {report.get('scenario', '?')}",
        "=" * 58,
        "",
        f"{'feature':<28}{'obs AUC':>9}{'pit AUC':>9}{'adv lost':>10}  collapsed",
    ]
    for item in findings:
        if item.get("status") != "evaluated":
            lines.append(f"{item['feature']:<28}{'could not evaluate':>28}")
            continue
        lines.append(
            f"{item['feature']:<28}"
            f"{item['observed_auc']:>9.4f}"
            f"{item['point_in_time_auc']:>9.4f}"
            f"{item['advantage_lost']:>10.4f}"
            f"  {item['collapsed']}"
        )

    flagged = report.get("flagged", [])
    lines += [
        "",
        f"FLAGGED ({len(flagged)}): {', '.join(flagged) if flagged else 'none'}",
        "",
        "Ranking is triage, not a verdict. Confirming a defect still requires the",
        "deterministic routes, one feature at a time. Ranking by importance instead",
        "would put the legitimate control near the top.",
        "",
        "Full evidence record written to the --output path. Add --json to print it.",
        "",
    ]
    return "\n".join(lines)
