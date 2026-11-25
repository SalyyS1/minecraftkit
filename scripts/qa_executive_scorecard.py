"""100th MCP Tool: Unified Executive Release-Readiness Scorecard Aggregator."""

from __future__ import annotations

from typing import Any


_GRADE_POINTS: dict[str, int] = {"A": 100, "B": 85, "C": 70, "D": 50, "F": 20}


def generate_executive_scorecard(
    *,
    release_name: str = "Server Release",
    checks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Aggregate multiple MinecraftKit audit/bot QA checks into a GO / NO-GO executive scorecard."""
    items = [c for c in (checks or []) if isinstance(c, dict) and c.get("name")]
    if not items:
        raise ValueError("'checks' must be a non-empty list of {name, grade, detail?} objects.")

    normalized: list[dict[str, Any]] = []
    blockers: list[str] = []
    score_sum = 0
    for c in items:
        name = str(c["name"]).strip()
        grade = str(c.get("grade", "A")).strip().upper()[:1]
        if grade not in _GRADE_POINTS:
            grade = "C"
        pts = _GRADE_POINTS[grade]
        score_sum += pts
        detail = str(c.get("detail", "")).strip()
        status = "FAIL" if grade in ("D", "F") else ("WARN" if grade == "C" else "PASS")
        if status == "FAIL":
            blockers.append(f"{name} (Grade {grade})")
        normalized.append({
            "name": name,
            "grade": grade,
            "score": pts,
            "status": status,
            "detail": detail,
        })

    overall_score = round(score_sum / len(normalized), 1)
    if blockers:
        overall_grade = "F" if len(blockers) >= 2 else "D"
        decision = "NO-GO"
    elif overall_score >= 92.0:
        overall_grade = "A"
        decision = "GO"
    elif overall_score >= 80.0:
        overall_grade = "B"
        decision = "GO"
    else:
        overall_grade = "C"
        decision = "CONDITIONAL-GO"

    color = "brightgreen" if overall_grade == "A" else ("green" if overall_grade == "B" else ("yellow" if overall_grade == "C" else "red"))
    md_lines = [
        f"## Release Readiness Scorecard — {release_name}",
        f"**Decision:** `{decision}` · **Overall Grade:** `{overall_grade}` ({overall_score}/100) · **Checks:** {len(normalized)}",
        "",
        "| Check | Grade | Status | Detail |",
        "| :--- | :---: | :---: | :--- |",
    ]
    for row in normalized:
        md_lines.append(f"| {row['name']} | **{row['grade']}** | `{row['status']}` | {row['detail'] or '—'} |")

    return {
        "ok": decision != "NO-GO",
        "release_name": str(release_name),
        "decision": decision,
        "overall_grade": overall_grade,
        "overall_score": overall_score,
        "check_count": len(normalized),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "checks": normalized,
        "markdown_summary": "\n".join(md_lines),
        "badge_json": {
            "schemaVersion": 1,
            "label": "release readiness",
            "message": f"{decision} · Grade {overall_grade} ({overall_score:.0f}/100)",
            "color": color,
        },
    }
