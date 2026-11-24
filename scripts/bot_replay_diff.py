#!/usr/bin/env python3
"""Bot Stage Run Replay Comparator (Baseline vs Candidate Regression Diff)."""

from __future__ import annotations

from typing import Any


def compare_bot_stage_runs(
    *,
    baseline_stages: list[dict[str, Any]],
    candidate_stages: list[dict[str, Any]],
    max_latency_increase_pct: float = 30.0,
) -> dict[str, Any]:
    base_by_name = {
        str(s.get("name", f"stage-{i}")): s
        for i, s in enumerate(baseline_stages, 1)
        if isinstance(s, dict)
    }
    comparisons: list[dict[str, Any]] = []
    regressions: list[str] = []

    for idx, cand in enumerate(candidate_stages, 1):
        if not isinstance(cand, dict):
            continue
        name = str(cand.get("name", f"stage-{idx}"))
        cand_status = str(cand.get("status", "PASS")).upper()
        cand_ms = float(cand.get("elapsed_ms", 0.0))
        cand_errs = int(cand.get("server_errors", 0))

        base = base_by_name.get(name)
        base_status = str(base.get("status", "PASS")).upper() if base else None
        base_ms = float(base.get("elapsed_ms", 0.0)) if base else None
        base_errs = int(base.get("server_errors", 0)) if base else 0

        delta_ms = round(cand_ms - base_ms, 2) if base_ms is not None else None
        delta_pct = (
            round(((cand_ms - base_ms) / base_ms) * 100.0, 1)
            if base_ms is not None and base_ms > 0
            else None
        )

        stage_regs: list[str] = []
        if base_status == "PASS" and cand_status != "PASS":
            stage_regs.append(f"Status regressed: PASS -> {cand_status}")
        if delta_pct is not None and delta_pct > max_latency_increase_pct:
            stage_regs.append(f"Latency regressed: +{delta_pct}% ({base_ms:.0f}ms -> {cand_ms:.0f}ms)")
        if cand_errs > base_errs:
            stage_regs.append(f"Server errors increased: {base_errs} -> {cand_errs}")

        regressions.extend(f"[{name}] {r}" for r in stage_regs)
        comparisons.append({
            "name": name,
            "baseline_status": base_status,
            "candidate_status": cand_status,
            "baseline_ms": base_ms,
            "candidate_ms": cand_ms,
            "delta_ms": delta_ms,
            "delta_pct": delta_pct,
            "new_server_errors": max(0, cand_errs - base_errs),
            "regressed": bool(stage_regs),
            "reasons": stage_regs,
        })

    md_lines = [
        f"### MinecraftKit Bot QA Replay Diff ({'PASS' if not regressions else f'REGRESSION ({len(regressions)})'})",
        "",
        "| Stage | Baseline | Candidate | Latency Delta | Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for c in comparisons:
        dstr = f"{c['delta_ms']:+.0f}ms ({c['delta_pct']:+.1f}%)" if c["delta_pct"] is not None else "new"
        md_lines.append(
            f"| `{c['name']}` | {c['baseline_status'] or 'new'} | {c['candidate_status']} | {dstr} | {'REGRESSED' if c['regressed'] else 'OK'} |"
        )

    return {
        "ok": len(regressions) == 0,
        "stage_count": len(comparisons),
        "regression_count": len(regressions),
        "regressions": regressions,
        "stages": comparisons,
        "markdown": "\n".join(md_lines) + "\n",
    }
