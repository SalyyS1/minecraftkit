"""Offline JVM G1GC / ZGC / Shenandoah GC Log Auditor for Paper & Folia Servers.

Parses Java 17/21 unified `-Xlog:gc*` logs without running a JVM and flags:
  - GC-001: Stop-the-world GC pauses > 50ms (> 1 server tick; critical if >= 150ms)
  - GC-002: Humongous allocation pressure / Evacuation Failure / To-space exhausted
  - GC-003: Full GC or ZGC Allocation Stall causing hard TPS freezes
  - GC-004: Metaspace GC churn (Metadata GC Threshold — plugin reload / classloader leak)
  - GC-005: Elevated GC pause overhead (> 5% of observed uptime window)
"""

from __future__ import annotations

import math
import re
from typing import Any


_PAUSE_RE = re.compile(
    r"(?:GC\(\d+\)\s+)?(?P<kind>Pause\s+[^\r\n]*?|Allocation Stall[^\r\n]*?)\s+(?P<ms>\d+(?:\.\d+)?)ms\b",
    re.IGNORECASE,
)
_UPTIME_RE = re.compile(r"^\[(?P<sec>\d+(?:\.\d+)?)s\]")
_HEAP_MB_RE = re.compile(r"(?P<before>\d+)M->(?P<after>\d+)M\((?P<total>\d+)M\)")


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 2)
    rank = (pct / 100.0) * (len(sorted_vals) - 1)
    lo = int(math.floor(rank))
    hi = min(len(sorted_vals) - 1, lo + 1)
    frac = rank - lo
    return round(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac, 2)


def _detect_gc_engine(log_text: str) -> str:
    lower = log_text.lower()
    if "zgc" in lower or "allocation stall" in lower or "pause mark start" in lower and "g1" not in lower:
        return "ZGC"
    if "shenandoah" in lower:
        return "Shenandoah"
    if "g1" in lower or "evacuation" in lower or "humongous" in lower or "pause young" in lower:
        return "G1GC"
    return "Unknown"


def audit_jvm_gc_log(
    log_text: str,
    *,
    tick_budget_ms: float = 50.0,
) -> dict[str, Any]:
    """Audit unified JVM GC logs and return pause percentiles, findings, grade & badge JSON."""
    if not isinstance(log_text, str) or not log_text.strip():
        raise ValueError("'log_text' must be a non-empty JVM -Xlog:gc* log string.")

    tick_ms = max(10.0, float(tick_budget_ms))
    pauses: list[dict[str, Any]] = []
    uptimes: list[float] = []
    humongous_hits = 0
    evac_fail_hits = 0
    full_gc_hits = 0
    alloc_stall_hits = 0
    metaspace_hits = 0
    max_heap_total_mb = 0
    peak_heap_after_mb = 0

    for line_no, raw_line in enumerate(log_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        up_m = _UPTIME_RE.match(line)
        if up_m:
            uptimes.append(float(up_m.group("sec")))

        lower = line.lower()
        if "humongous" in lower:
            humongous_hits += 1
        if "to-space exhausted" in lower or "evacuation failure" in lower:
            evac_fail_hits += 1
        if "pause full" in lower:
            full_gc_hits += 1
        if "allocation stall" in lower:
            alloc_stall_hits += 1
        if "metadata gc threshold" in lower or "metaspace" in lower and "pause" in lower:
            metaspace_hits += 1

        heap_m = _HEAP_MB_RE.search(line)
        if heap_m:
            after_mb = int(heap_m.group("after"))
            total_mb = int(heap_m.group("total"))
            peak_heap_after_mb = max(peak_heap_after_mb, after_mb)
            max_heap_total_mb = max(max_heap_total_mb, total_mb)

        pm = _PAUSE_RE.search(line)
        if pm:
            ms = float(pm.group("ms"))
            kind = pm.group("kind").strip()
            pauses.append({
                "line": line_no,
                "kind": kind[:64],
                "pause_ms": round(ms, 2),
                "exceeds_tick": ms > tick_ms,
            })

    values = sorted(p["pause_ms"] for p in pauses)
    total_pause_ms = round(sum(values), 2)
    max_pause_ms = round(values[-1], 2) if values else 0.0
    p50_ms = _percentile(values, 50.0)
    p95_ms = _percentile(values, 95.0)
    p99_ms = _percentile(values, 99.0)
    over_tick_count = sum(1 for v in values if v > tick_ms)

    window_sec = round(max(uptimes) - min(uptimes), 2) if len(uptimes) >= 2 and max(uptimes) > min(uptimes) else 0.0
    overhead_pct = round((total_pause_ms / (window_sec * 1000.0)) * 100.0, 2) if window_sec > 0.0 else 0.0

    findings: list[dict[str, Any]] = []
    if max_pause_ms > tick_ms:
        sev = "error" if max_pause_ms >= tick_ms * 3.0 else "warning"
        findings.append({
            "rule_id": "GC-001",
            "severity": sev,
            "title": "Stop-the-world GC pauses exceed 1 server tick",
            "detail": (
                f"{over_tick_count}/{len(pauses)} pauses exceeded {tick_ms:.0f}ms "
                f"(p95={p95_ms:.1f}ms, max={max_pause_ms:.1f}ms)."
            ),
            "remediation": (
                "Switch to Generational ZGC (-XX:+UseZGC -XX:+ZGenerational on Java 21+) or tune G1GC "
                "with -XX:MaxGCPauseMillis=50 -XX:+UnlockExperimentalVMOptions -XX:G1NewSizePercent=30."
            ),
        })

    if humongous_hits > 0 or evac_fail_hits > 0:
        findings.append({
            "rule_id": "GC-002",
            "severity": "error" if evac_fail_hits > 0 else "warning",
            "title": "G1GC humongous allocation or evacuation failure detected",
            "detail": (
                f"Observed {humongous_hits} humongous allocation triggers and "
                f"{evac_fail_hits} to-space exhausted / evacuation failures."
            ),
            "remediation": (
                "Increase -XX:G1HeapRegionSize=16M (or 32M for 16GB+ heaps) and reserve headroom "
                "with -XX:G1ReservePercent=20 so large chunk/packet arrays do not fragment regions."
            ),
        })

    if full_gc_hits > 0 or alloc_stall_hits > 0:
        findings.append({
            "rule_id": "GC-003",
            "severity": "error",
            "title": "Full GC or ZGC Allocation Stall caused hard TPS freeze",
            "detail": (
                f"Detected {full_gc_hits} Full GC cycles and {alloc_stall_hits} Allocation Stalls."
            ),
            "remediation": (
                "Ensure -Xms equals -Xmx, add -XX:+DisableExplicitGC, audit plugins for memory leaks "
                "with Spark heap summary, and leave >=20% RAM headroom outside JVM heap."
            ),
        })

    if metaspace_hits > 0:
        findings.append({
            "rule_id": "GC-004",
            "severity": "warning",
            "title": "Metaspace GC churn indicates classloader or plugin-reload pressure",
            "detail": f"Detected {metaspace_hits} Metadata GC Threshold / Metaspace pause triggers.",
            "remediation": (
                "Avoid runtime plugin reloaders (PlugMan/ServerUtils) in production and pre-size "
                "metaspace with -XX:MetaspaceSize=256M -XX:MaxMetaspaceSize=512M."
            ),
        })

    if overhead_pct > 5.0:
        findings.append({
            "rule_id": "GC-005",
            "severity": "error" if overhead_pct >= 12.0 else "warning",
            "title": "High GC CPU time overhead degrades tick stability",
            "detail": (
                f"Server spent {overhead_pct:.2f}% ({total_pause_ms:.1f}ms over {window_sec:.1f}s) "
                "stopped in GC pauses."
            ),
            "remediation": (
                "Reduce live entity/chunk churn (mc_ops_audit_paper_config) and allocate sufficient "
                "heap headroom so GC cycles run infrequently."
            ),
        })

    error_count = sum(1 for f in findings if f["severity"] == "error")
    warn_count = sum(1 for f in findings if f["severity"] == "warning")
    if error_count >= 2:
        grade = "F"
    elif error_count == 1:
        grade = "D"
    elif warn_count >= 2:
        grade = "C"
    elif warn_count == 1:
        grade = "B"
    else:
        grade = "A"

    gc_engine = _detect_gc_engine(log_text)
    badge_color = "brightgreen" if grade == "A" else ("green" if grade == "B" else ("yellow" if grade == "C" else "red"))
    return {
        "ok": error_count == 0,
        "status": "fail" if error_count > 0 else ("warn" if warn_count > 0 else "pass"),
        "grade": grade,
        "gc_engine": gc_engine,
        "tick_budget_ms": tick_ms,
        "summary": {
            "pause_count": len(pauses),
            "over_tick_count": over_tick_count,
            "p50_ms": p50_ms,
            "p95_ms": p95_ms,
            "p99_ms": p99_ms,
            "max_pause_ms": max_pause_ms,
            "total_pause_ms": total_pause_ms,
            "observed_window_sec": window_sec,
            "gc_overhead_pct": overhead_pct,
            "peak_heap_after_mb": peak_heap_after_mb,
            "max_heap_total_mb": max_heap_total_mb,
            "error_count": error_count,
            "warning_count": warn_count,
        },
        "pauses": pauses[:60],
        "findings": findings,
        "badge_json": {
            "schemaVersion": 1,
            "label": f"jvm gc ({gc_engine.lower()})",
            "message": f"grade {grade} · p95 {p95_ms:.1f}ms · max {max_pause_ms:.1f}ms",
            "color": badge_color,
        },
    }
