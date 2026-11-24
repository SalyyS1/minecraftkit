#!/usr/bin/env python3
"""Static Spark / Paper Timings Bottleneck & Tick-Lag Root-Cause Auditor."""

from __future__ import annotations

import re
from typing import Any


def audit_spark_profile(
    *,
    profile_text: str,
    tps: float = 20.0,
    mspt: float = 25.0,
) -> dict[str, Any]:
    text = profile_text or ""
    low = text.lower()
    findings: list[dict[str, Any]] = []

    if tps < 18.0 or mspt > 50.0:
        findings.append({
            "code": "TICK-OVERLOAD",
            "severity": "critical",
            "message": f"Server tick loop is overloaded (TPS={tps:.2f}, MSPT={mspt:.1f}ms > 50ms budget).",
            "remediation": "Inspect top self-time frames below and lower simulation-distance / entity activation ranges.",
        })

    if any(k in low for k in ("tickentities", "pathfinder", "brain.tick", "villager", "livingentity.aitick")):
        findings.append({
            "code": "TICK-ENTITY",
            "severity": "high",
            "message": "Entity AI / pathfinding / villager brain ticks appear as a hot frame in the profile.",
            "remediation": "Tune spigot.yml entity-activation-range (animals: 16, monsters: 24, villagers: 16) and paper-world-defaults.yml tick-rates.behavior.",
        })

    if any(k in low for k in ("chunkgenerator", "chunkmap", "getchunk", "loadchunk", "sync-chunk", "regionfile")):
        findings.append({
            "code": "TICK-CHUNK",
            "severity": "high",
            "message": "Synchronous chunk generation or disk region I/O detected on the server tick thread.",
            "remediation": "Pre-generate world borders with Chunky, set sync-chunk-writes=false, and replace getChunkAt with getChunkAtAsync().",
        })

    if any(k in low for k in ("gc pause", "g1 evacuation", "full gc", "humongous", "stw")):
        findings.append({
            "code": "TICK-GC",
            "severity": "high",
            "message": "JVM Garbage Collection stop-the-world or humongous allocation pauses detected.",
            "remediation": "Match -Xms and -Xmx, use Aikar's G1GC flags (or Java 21 Generational ZGC for >=12GB heaps), and avoid huge per-tick byte[] allocations.",
        })

    if any(k in low for k in ("jdbc", "mysql", "sqlite", "hikaricp", "httpurlconnection", "socketinputstream", "okhttp")):
        findings.append({
            "code": "TICK-BLOCKING-IO",
            "severity": "critical",
            "message": "Blocking SQL/HTTP network I/O detected inside main/region server tick frames!",
            "remediation": "Move all database & web calls onto Paper AsyncScheduler (or CompletableFuture.supplyAsync) and never call .join()/.get() on tick threads.",
        })

    # Extract plugin-looking hotspot percentages like `MyPlugin.jar (24.5%)` or `com.example.foo 18.2%`
    hotspots: list[dict[str, Any]] = []
    for m in re.finditer(r"([A-Za-z0-9_.\-/]+\.(?:jar|java)|[a-z]+(?:\.[a-z0-9_]+){2,})[^\n]{0,40}?(\d{1,2}(?:\.\d+)?)\s*%", text):
        pct = float(m.group(2))
        if pct >= 5.0:
            hotspots.append({"symbol": m.group(1), "tick_share_pct": pct})
    hotspots.sort(key=lambda h: h["tick_share_pct"], reverse=True)

    if any(h["tick_share_pct"] >= 20.0 for h in hotspots):
        top = hotspots[0]
        findings.append({
            "code": "TICK-PLUGIN",
            "severity": "high",
            "message": f"Single hotspot '{top['symbol']}' consumes {top['tick_share_pct']:.1f}% of tick time.",
            "remediation": f"Profile '{top['symbol']}' with `/spark profiler --thread * --only-ticks-over 50` and cache expensive lookups.",
        })

    penalty = sum(28 if f["severity"] == "critical" else 15 for f in findings)
    score = max(0, min(100, 100 - penalty))
    grade = "A" if score >= 90 else "B" if score >= 78 else "C" if score >= 62 else "D" if score >= 45 else "F"

    return {
        "ok": not any(f["severity"] == "critical" for f in findings),
        "grade": grade,
        "score": score,
        "tps": tps,
        "mspt": mspt,
        "hotspot_count": len(hotspots),
        "top_hotspots": hotspots[:10],
        "finding_count": len(findings),
        "findings": findings,
    }
