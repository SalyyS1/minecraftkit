"""Bounded Multi-Bot Headless Protocol Stress & Handshake Latency Benchmark.

Runs N concurrent lightweight pure-Python Minecraft Java Edition SLP or offline-login
probes (strictly capped at <= 25 concurrent sockets to protect host CPU/RAM and never
hijack desktop focus), reporting p50/p95/p99 latency, success rate, and estimated server
tick headroom.
"""

from __future__ import annotations

import concurrent.futures
import math
import time
from typing import Any

import bot_engine
import mc_proto_client


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 2)
    idx = (pct / 100.0) * (len(sorted_vals) - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return round(sorted_vals[lo], 2)
    frac = idx - lo
    return round(sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac, 2)


def run_bot_stress_benchmark(
    *,
    host: str,
    port: int = 25565,
    bot_count: int = 5,
    mode: str = "slp",
    protocol_version: int = 769,
    timeout_seconds: float = 3.0,
) -> dict[str, Any]:
    """Execute a bounded concurrent pure-Python protocol benchmark against a test server."""
    if not host or not isinstance(host, str):
        raise ValueError("'host' must be a non-empty string.")
    if not (1 <= int(port) <= 65535):
        raise ValueError("'port' must be between 1 and 65535.")
    n = max(1, min(25, int(bot_count)))
    m = mode.strip().lower()
    if m not in ("slp", "offline_login"):
        raise ValueError("'mode' must be 'slp' or 'offline_login'.")

    def _one(idx: int) -> dict[str, Any]:
        t0 = time.monotonic()
        if m == "slp":
            res = bot_engine.ping_minecraft_server(host, int(port), timeout_seconds=timeout_seconds)
            ok = bool(res.get("reachable", False))
            lat = float(res.get("latency_ms") or round((time.monotonic() - t0) * 1000.0, 2))
            err = str(res.get("error", "")) if not ok else ""
        else:
            res = mc_proto_client.probe_offline_login_handshake(
                host,
                int(port),
                username=f"MCKitBench{idx:02d}",
                protocol_version=int(protocol_version),
                timeout_seconds=timeout_seconds,
            )
            ok = bool(res.get("ok", False))
            lat = float(res.get("latency_ms") or round((time.monotonic() - t0) * 1000.0, 2))
            err = str(res.get("disconnect_reason", "")) if not ok else ""
        return {"bot_index": idx, "ok": ok, "latency_ms": lat, "error": err}

    wall_t0 = time.monotonic()
    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(n, 12)) as pool:
        futs = [pool.submit(_one, i + 1) for i in range(n)]
        for fut in concurrent.futures.as_completed(futs):
            results.append(fut.result())
    wall_ms = round((time.monotonic() - wall_t0) * 1000.0, 2)

    results.sort(key=lambda r: r["bot_index"])
    latencies = sorted(r["latency_ms"] for r in results if r["ok"])
    ok_count = sum(1 for r in results if r["ok"])
    fail_count = n - ok_count
    p50 = _percentile(latencies, 50.0)
    p95 = _percentile(latencies, 95.0)
    p99 = _percentile(latencies, 99.0)

    headroom = "EXCELLENT" if fail_count == 0 and p95 < 150.0 else ("DEGRADED" if ok_count > 0 else "UNREACHABLE")
    return {
        "ok": fail_count == 0,
        "host": host,
        "port": int(port),
        "mode": m,
        "bot_count": n,
        "anti_oom_cap": 25,
        "estimated_total_ram_mb": n * 18,
        "screen_lock_free": True,
        "succeeded": ok_count,
        "failed": fail_count,
        "success_rate_pct": round((ok_count / n) * 100.0, 2),
        "wall_elapsed_ms": wall_ms,
        "latency_ms": {"p50": p50, "p95": p95, "p99": p99},
        "server_headroom": headroom,
        "samples": results[:25],
    }
