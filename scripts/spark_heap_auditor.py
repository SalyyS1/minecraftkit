"""Offline Spark `/spark heapsummary` Memory-Leak & Retainer Auditor.

Detects the 5 most common Paper/Folia plugin memory leaks from Spark heap summary text:
  - HEAP-001 (error): Leaked CraftPlayer / ServerPlayer instances (retained > 2x online players)
  - HEAP-002 (error): Single class/array retainer consuming > 35% of live heap (unbounded cache)
  - HEAP-003 (warning): Excessive LevelChunk / RegionFile retention (> 5,000 chunks)
  - HEAP-004 (warning): Entity / ArmorStand / ItemDisplay / ModelEngine leak (> 10,000 instances)
  - HEAP-005 (warning): Unclosed JDBC / Hikari ResultSet / PreparedStatement accumulation
"""

from __future__ import annotations

import re
from typing import Any


_ROW_RE = re.compile(
    r"(?P<instances>\d[\d,]*)\s+(?P<bytes>\d+(?:\.\d+)?)\s*(?P<unit>B|KB|KiB|MB|MiB|GB|GiB)?\s+(?P<cls>[A-Za-z0-9_.$;\[\]/]+)",
    re.IGNORECASE,
)


def _to_mb(val: float, unit: str | None) -> float:
    u = (unit or "B").lower()
    if u in ("gb", "gib"):
        return val * 1024.0
    if u in ("mb", "mib"):
        return val
    if u in ("kb", "kib"):
        return val / 1024.0
    return val / (1024.0 * 1024.0)


def audit_spark_heap_summary(
    heap_text: str,
    *,
    online_players: int = 20,
    total_heap_mb: float = 4096.0,
) -> dict[str, Any]:
    """Audit Spark `/spark heapsummary` text offline and emit findings, grade & badge JSON."""
    if not isinstance(heap_text, str) or not heap_text.strip():
        raise ValueError("'heap_text' must be a non-empty Spark heapsummary output string.")

    entries: list[dict[str, Any]] = []
    for line in heap_text.splitlines():
        m = _ROW_RE.search(line)
        if not m:
            continue
        inst = int(m.group("instances").replace(",", ""))
        mb = round(_to_mb(float(m.group("bytes")), m.group("unit")), 2)
        cls = m.group("cls")
        entries.append({"class_name": cls, "instances": inst, "size_mb": mb})

    heap_cap = max(128.0, float(total_heap_mb))
    players = max(1, int(online_players))
    findings: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(rule_id: str, severity: str, title: str, detail: str, remediation: str) -> None:
        if rule_id in seen:
            return
        seen.add(rule_id)
        findings.append({
            "rule_id": rule_id,
            "severity": severity,
            "title": title,
            "detail": detail,
            "remediation": remediation,
        })

    for e in entries:
        cls_l = e["class_name"].lower()
        inst = e["instances"]
        mb = e["size_mb"]

        if ("craftplayer" in cls_l or "serverplayer" in cls_l) and inst > max(players * 2, players + 15):
            add(
                "HEAP-001",
                "error",
                "Leaked CraftPlayer / ServerPlayer references retained after PlayerQuitEvent",
                f"{e['class_name']} has {inst:,} live instances vs {players} online players ({mb:.1f} MB).",
                "Never store `Player` as keys/values in static Maps/Sets; store `UUID` and remove entries on `PlayerQuitEvent`.",
            )

        if mb / heap_cap > 0.35:
            add(
                "HEAP-002",
                "error",
                "Single heap retainer consumes > 35% of configured JVM heap",
                f"{e['class_name']} retains {mb:.1f} MB ({(mb / heap_cap) * 100.0:.1f}% of {heap_cap:.0f} MB heap).",
                "Capture a filtered histogram or Caffeine bounded cache (`maximumSize` + `expireAfterAccess`) to stop unbounded memory growth.",
            )

        if ("levelchunk" in cls_l or "regionfile" in cls_l) and inst > 5000:
            add(
                "HEAP-003",
                "warning",
                "Excessive chunk/region objects retained in heap",
                f"{e['class_name']} has {inst:,} instances ({mb:.1f} MB).",
                "Audit plugin chunk tickets (`addPluginChunkTicket`) and lower `view-distance` / `delay-chunk-unloads-by`.",
            )

        if any(k in cls_l for k in ("armorstand", "itemdisplay", "textdisplay", "activemodel", "modeledentity")) and inst > 10000:
            add(
                "HEAP-004",
                "warning",
                "Hologram / Display / ModelEngine entity accumulation detected",
                f"{e['class_name']} has {inst:,} live instances ({mb:.1f} MB).",
                "Ensure temporary holograms/displays/models are despawned on chunk unload and mob death.",
            )

        if any(k in cls_l for k in ("resultset", "preparedstatement", "hikariproxyconnection")) and inst > 500:
            add(
                "HEAP-005",
                "warning",
                "Accumulated unclosed JDBC / HikariCP objects indicate connection/statement leaks",
                f"{e['class_name']} has {inst:,} instances ({mb:.1f} MB).",
                "Wrap every `Connection`, `PreparedStatement`, and `ResultSet` in Java `try-with-resources` or Kotlin `.use {}`.",
            )

    errors = sum(1 for f in findings if f["severity"] == "error")
    warns = sum(1 for f in findings if f["severity"] == "warning")
    grade = "F" if errors >= 2 else ("D" if errors == 1 else ("C" if warns >= 2 else ("B" if warns == 1 else "A")))
    color = "brightgreen" if grade == "A" else ("green" if grade == "B" else ("yellow" if grade == "C" else "red"))

    return {
        "ok": errors == 0,
        "status": "fail" if errors > 0 else ("warn" if warns > 0 else "pass"),
        "grade": grade,
        "parsed_classes": len(entries),
        "online_players": players,
        "total_heap_mb": heap_cap,
        "error_count": errors,
        "warning_count": warns,
        "findings": findings,
        "badge_json": {
            "schemaVersion": 1,
            "label": "spark heap",
            "message": f"grade {grade} · {errors} leaks · {warns} warnings",
            "color": color,
        },
    }
