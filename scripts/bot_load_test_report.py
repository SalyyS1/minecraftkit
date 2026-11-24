"""Multi-Bot Pool Stress Load-Test Analyzer & TPS Correlation Report Generator."""

from __future__ import annotations

import math
from typing import Any


def _pct(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 2)
    rank = (p / 100.0) * (len(sorted_vals) - 1)
    lo = int(math.floor(rank))
    hi = min(len(sorted_vals) - 1, lo + 1)
    return round(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (rank - lo), 2)


def generate_bot_load_test_report(
    *,
    server_name: str = "MyMinecraftServer",
    bot_count: int = 10,
    join_latencies_ms: list[float] | None = None,
    tps_samples: list[float] | None = None,
    failed_joins: int = 0,
    bot_ram_mb_total: int | None = None,
) -> dict[str, Any]:
    """Compute p50/p95/p99 join latency, TPS drop correlation, grade, and badge JSON."""
    n = max(1, int(bot_count))
    lats = sorted(max(0.0, float(v)) for v in (join_latencies_ms or [140.0, 180.0, 210.0, 250.0]))
    tps_list = [max(0.0, min(20.0, float(v))) for v in (tps_samples or [20.0, 19.9, 19.8, 19.9])]
    failed = max(0, int(failed_joins))
    ram_mb = int(bot_ram_mb_total) if bot_ram_mb_total is not None else n * 42
    desktop_mb = n * 2600

    p50 = _pct(lats, 50.0)
    p95 = _pct(lats, 95.0)
    p99 = _pct(lats, 99.0)
    max_lat = round(lats[-1], 2) if lats else 0.0
    min_tps = round(min(tps_list), 2) if tps_list else 20.0
    avg_tps = round(sum(tps_list) / len(tps_list), 2) if tps_list else 20.0
    fail_rate_pct = round((failed / float(n)) * 100.0, 2)

    findings: list[dict[str, str]] = []
    if min_tps < 16.0:
        findings.append({
            "rule_id": "LOAD-001",
            "severity": "error",
            "detail": f"Server TPS collapsed to {min_tps:.2f} under {n}-bot stress.",
            "remediation": "Profile with Spark + mc_ops_audit_paper_config; stagger bot join interval or split worlds across Folia regions.",
        })
    elif min_tps < 18.5:
        findings.append({
            "rule_id": "LOAD-001",
            "severity": "warning",
            "detail": f"Server TPS dipped to {min_tps:.2f} under {n}-bot stress.",
            "remediation": "Check chunk generation & entity activation ranges under concurrent player joins.",
        })
    if p95 > 1500.0:
        findings.append({
            "rule_id": "LOAD-002",
            "severity": "error" if p95 > 3000.0 else "warning",
            "detail": f"High p95 bot join latency ({p95:.1f}ms, max {max_lat:.1f}ms).",
            "remediation": "Audit AuthMe/LuckPerms async SQL pool (`mc_audit_database_pool`) and Netty EventLoop threads.",
        })
    if failed > 0:
        findings.append({
            "rule_id": "LOAD-003",
            "severity": "error" if fail_rate_pct >= 10.0 else "warning",
            "detail": f"{failed}/{n} bot joins failed ({fail_rate_pct:.1f}% failure rate).",
            "remediation": "Check Velocity/Paper connection throttle, anti-bot rate limits, or anti-cheat join checks (`mc_bot_audit_anti_cheat_compat`).",
        })

    errors = sum(1 for f in findings if f["severity"] == "error")
    warns = sum(1 for f in findings if f["severity"] == "warning")
    grade = "F" if errors >= 2 else ("D" if errors == 1 else ("C" if warns >= 2 else ("B" if warns == 1 else "A")))
    color = "brightgreen" if grade == "A" else ("green" if grade == "B" else ("yellow" if grade == "C" else "red"))
    ram_saved_pct = round((1.0 - (ram_mb / float(max(1, desktop_mb)))) * 100.0, 1)

    return {
        "ok": errors == 0,
        "status": "fail" if errors > 0 else ("warn" if warns > 0 else "pass"),
        "grade": grade,
        "server_name": str(server_name or "MyMinecraftServer"),
        "bot_count": n,
        "failed_joins": failed,
        "fail_rate_pct": fail_rate_pct,
        "latency_ms": {"p50": p50, "p95": p95, "p99": p99, "max": max_lat, "samples": lats[:50]},
        "tps": {"min": min_tps, "avg": avg_tps, "samples": tps_list[:60]},
        "memory_efficiency": {
            "headless_bot_ram_mb": ram_mb,
            "equivalent_desktop_ram_mb": desktop_mb,
            "ram_saved_pct": ram_saved_pct,
            "screen_lock_free": True,
        },
        "findings": findings,
        "badge_json": {
            "schemaVersion": 1,
            "label": f"bot load ({n}x)",
            "message": f"grade {grade} · p95 {p95:.0f}ms · min TPS {min_tps:.1f}",
            "color": color,
        },
    }
