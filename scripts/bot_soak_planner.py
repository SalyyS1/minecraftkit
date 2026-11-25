"""Long-Running Autonomous Bot Soak-Test & Memory-Leak Slope Planner."""

from __future__ import annotations

from typing import Any


def plan_bot_soak_test(
    *,
    server_host: str = "127.0.0.1",
    server_port: int = 25565,
    duration_hours: int = 8,
    concurrent_bots: int = 6,
    sample_interval_sec: int = 60,
    max_heap_growth_mb_per_hour: float = 25.0,
    min_tps_floor: float = 19.0,
) -> dict[str, Any]:
    """Plan an anti-OOM overnight/24h headless bot soak test with heap-leak & TPS guardrails."""
    hrs = max(1, min(72, int(duration_hours)))
    bots = max(1, min(25, int(concurrent_bots)))
    interval = max(15, min(600, int(sample_interval_sec)))
    total_samples = (hrs * 3600) // interval
    bot_ram_mb = bots * 42
    desktop_ram_mb = bots * 2600
    ram_saved_pct = round((1.0 - (bot_ram_mb / float(max(1, desktop_ram_mb)))) * 100.0, 1)

    return {
        "ok": True,
        "target": {"host": str(server_host), "port": int(server_port)},
        "schedule": {
            "duration_hours": hrs,
            "concurrent_bots": bots,
            "sample_interval_sec": interval,
            "expected_telemetry_samples": total_samples,
            "auto_reconnect": True,
            "screen_lock_free": True,
        },
        "leak_guardrails": {
            "max_heap_growth_mb_per_hour": round(float(max_heap_growth_mb_per_hour), 2),
            "min_tps_floor": round(float(min_tps_floor), 2),
            "bridge_endpoints": ["/api/v1/memory", "/api/v1/tps-history", "/api/v1/entities", "/api/v1/errors"],
            "post_soak_audit": "mc_ops_audit_spark_heap_summary + mc_ops_audit_jvm_gc_log",
        },
        "memory_efficiency": {
            "headless_bot_ram_mb": bot_ram_mb,
            "equivalent_desktop_ram_mb": desktop_ram_mb,
            "ram_saved_pct": ram_saved_pct,
        },
        "recommended_host": "Oracle Cloud Always-Free ARM64 24 GB ($0/mo) or local Docker with mem_limit",
    }
