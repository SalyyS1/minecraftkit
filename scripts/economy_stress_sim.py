#!/usr/bin/env python3
"""Deterministic Economy Arbitrage, Shop Price-Loop & Concurrent Dupe-Race Stress Planner."""

from __future__ import annotations

from typing import Any


def audit_economy_and_plan_stress(
    *,
    shop_items: list[dict[str, Any]],
    recipes: list[dict[str, Any]] | None = None,
    tax_pct: float = 0.0,
    concurrent_bots: int = 4,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    tax_mult = max(0.0, 1.0 - max(0.0, min(95.0, float(tax_pct))) / 100.0)
    buy_map: dict[str, float] = {}
    sell_map: dict[str, float] = {}

    for item in shop_items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id", "")).strip().lower()
        if not item_id:
            continue
        buy = item.get("buy_price")
        sell = item.get("sell_price")
        if buy is not None:
            bval = float(buy)
            if bval <= 0:
                findings.append({
                    "code": "ECON-NEG-002",
                    "severity": "critical",
                    "item": item_id,
                    "message": f"Item '{item_id}' has non-positive buy_price={bval}; players can mint free items or trigger negative balance overflow.",
                    "remediation": "Require buy_price > 0 or disable buying explicitly.",
                })
            else:
                buy_map[item_id] = bval
        if sell is not None:
            sval = float(sell)
            if sval < 0:
                findings.append({
                    "code": "ECON-NEG-002",
                    "severity": "critical",
                    "item": item_id,
                    "message": f"Item '{item_id}' has negative sell_price={sval}.",
                    "remediation": "Require sell_price >= 0.",
                })
            else:
                sell_map[item_id] = sval

        if item_id in buy_map and item_id in sell_map:
            effective_sell = sell_map[item_id] * tax_mult
            if effective_sell > buy_map[item_id]:
                profit = round(effective_sell - buy_map[item_id], 4)
                findings.append({
                    "code": "ECON-ARB-001",
                    "severity": "critical",
                    "item": item_id,
                    "message": f"Direct infinite-money arbitrage on '{item_id}': buy={buy_map[item_id]} < net sell={effective_sell:.2f} (+{profit} per unit!).",
                    "remediation": f"Lower sell_price below {buy_map[item_id] * 0.7:.2f} or raise buy_price above {effective_sell * 1.25:.2f}.",
                })

    for rec in recipes or []:
        if not isinstance(rec, dict):
            continue
        out_id = str(rec.get("output", "")).strip().lower()
        out_qty = max(1, int(rec.get("output_qty", 1)))
        ingredients = rec.get("ingredients") if isinstance(rec.get("ingredients"), dict) else {}
        if out_id not in sell_map or not ingredients:
            continue
        if all(str(k).strip().lower() in buy_map for k in ingredients):
            craft_cost = sum(buy_map[str(k).strip().lower()] * float(v) for k, v in ingredients.items())
            revenue = sell_map[out_id] * out_qty * tax_mult
            if revenue > craft_cost:
                findings.append({
                    "code": "ECON-ARB-001",
                    "severity": "critical",
                    "item": out_id,
                    "message": f"Crafting arbitrage loop on '{out_id}' (x{out_qty}): ingredient buy cost={craft_cost:.2f} < net output sell={revenue:.2f} (+{revenue - craft_cost:.2f} profit/craft!).",
                    "remediation": f"Cap '{out_id}' sell_price <= {(craft_cost / out_qty) * 0.85:.2f} or remove base ingredients from unlimited admin shop.",
                })

    bots = max(2, min(int(concurrent_bots), 16))
    race_stages = [
        {"name": "1. Join & Auto-Auth", "action": "auto_auth", "bots": bots, "redact_secrets": True},
        {"name": "2. Snapshot Pre-Test Vault Balances", "action": "command", "command": "/bal"},
        {"name": "3. Synchronized Barrier Buy/Sell Burst", "action": "concurrent_burst", "command": "/shop", "bots": bots, "barrier_window_ms": 25},
        {"name": "4. Assert Zero Negative/NaN Balances & Conservation", "action": "assert_bridge", "max_errors": 0},
    ]

    penalty = sum(30 if f["severity"] == "critical" else 12 for f in findings)
    score = max(0, min(100, 100 - penalty))
    grade = "A" if score >= 90 else "B" if score >= 78 else "C" if score >= 62 else "D" if score >= 45 else "F"

    return {
        "ok": len(findings) == 0,
        "grade": grade,
        "score": score,
        "items_audited": len(shop_items),
        "recipes_audited": len(recipes or []),
        "tax_pct": float(tax_pct),
        "finding_count": len(findings),
        "findings": findings,
        "concurrent_race_qa_plan": {
            "bot_count": bots,
            "estimated_ram_mb": bots * 42,
            "screen_lock_free": True,
            "stages": race_stages,
        },
    }
