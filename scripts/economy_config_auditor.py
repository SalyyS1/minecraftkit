"""Offline EssentialsX / ShopGUI+ / AuctionHouse Economy Arbitrage & Anti-Dupe Config Auditor.

Catches infinite-money loops and economy dupe misconfigurations offline:
  - ECO-001 (error): Shop item arbitrage loop where buyPrice <= sellPrice (infinite money!)
  - ECO-002 (error): Negative tax/min-price or unsafe max-money (> 1e13 float precision loss)
  - ECO-003 (warning): High starting-balance (> 50,000) enabling alt-account currency farming
  - ECO-004 (warning): economy-log-enabled: false or pay-minimum <= 0 hiding dupe trails
  - ECO-005 (warning): Zero/missing purchase or auction cooldown (`cooldown: 0`) inviting packet races
"""

from __future__ import annotations

import re
from typing import Any


_BUY_RE = re.compile(r"\bbuy[-_]?price\s*:\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)
_SELL_RE = re.compile(r"\bsell[-_]?price\s*:\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)
_NEG_ECO_RE = re.compile(r"\b(?:tax|fee|min[-_]?price|listing[-_]?fee|pay[-_]?minimum)\s*:\s*(-\d+(?:\.\d+)?)", re.IGNORECASE)
_MAX_MONEY_RE = re.compile(r"\bmax[-_]?money\s*:\s*(\d+(?:\.\d+)?(?:e\+\d+)?)", re.IGNORECASE)
_START_BAL_RE = re.compile(r"\bstarting[-_]?balance\s*:\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_LOG_OFF_RE = re.compile(r"\beconomy[-_]?log[-_]?enabled\s*:\s*false\b", re.IGNORECASE)
_ZERO_CD_RE = re.compile(r"\b(?:purchase[-_]?cooldown|auction[-_]?cooldown|cooldown)\s*:\s*0(?:\.0+)?\b", re.IGNORECASE)


def audit_economy_config(config_text: str) -> dict[str, Any]:
    """Audit EssentialsX / ShopGUI+ / AuctionHouse YAML configs offline."""
    if not isinstance(config_text, str) or not config_text.strip():
        raise ValueError("'config_text' must be a non-empty economy/shop YAML configuration string.")

    findings: list[dict[str, str]] = []

    # Pair buyPrice/sellPrice occurrences in order within items
    buys = [float(m.group(1)) for m in _BUY_RE.finditer(config_text)]
    sells = [float(m.group(1)) for m in _SELL_RE.finditer(config_text)]
    arbitrage_hits = [
        (b, s) for b, s in zip(buys, sells)
        if b > 0 and s > 0 and b <= s
    ]
    if arbitrage_hits:
        b0, s0 = arbitrage_hits[0]
        findings.append({
            "rule_id": "ECO-001",
            "severity": "error",
            "title": "Infinite-money shop arbitrage loop detected (buyPrice <= sellPrice)",
            "detail": f"Found {len(arbitrage_hits)} item(s) where buyPrice ({b0}) <= sellPrice ({s0}).",
            "remediation": "Enforce `buyPrice >= sellPrice * 1.25` (or disable sellPrice=-1) and validate with `mc_bot_simulate_economy_stress`.",
        })

    neg_hit = _NEG_ECO_RE.search(config_text)
    max_m = _MAX_MONEY_RE.search(config_text)
    huge_max = bool(max_m and float(max_m.group(1)) > 1e13)
    if neg_hit or huge_max:
        findings.append({
            "rule_id": "ECO-002",
            "severity": "error",
            "title": "Dangerous negative economy fee or IEEE-754 max-money overflow risk",
            "detail": (
                f"Flagged `{neg_hit.group(0)}`" if neg_hit else f"max-money exceeds 10 trillion ({max_m.group(1)})"
            ),
            "remediation": "Keep all fees/taxes >= 0 and cap `max-money` at `10000000000` (10B) to prevent double-precision rounding exploits.",
        })

    sb = _START_BAL_RE.search(config_text)
    if sb and float(sb.group(1)) > 50000.0:
        findings.append({
            "rule_id": "ECO-003",
            "severity": "warning",
            "title": "High `starting-balance` encourages alt-account money farming",
            "detail": f"Configured starting-balance is {float(sb.group(1)):,.0f} (> 50,000).",
            "remediation": "Lower `starting-balance` to <= 500-2,500 and gate starter rewards behind playtime or anti-alt IP/UUID checks.",
        })

    if _LOG_OFF_RE.search(config_text):
        findings.append({
            "rule_id": "ECO-004",
            "severity": "warning",
            "title": "Economy transaction audit logging is disabled (`economy-log-enabled: false`)",
            "detail": "Without transaction logs, admins cannot trace or roll back dupe rings.",
            "remediation": "Enable `economy-log-enabled: true` (or async SQL ledger logging).",
        })

    if _ZERO_CD_RE.search(config_text):
        findings.append({
            "rule_id": "ECO-005",
            "severity": "warning",
            "title": "Zero shop/auction cooldown allows rapid-click packet race dupe attempts",
            "detail": "Detected `cooldown: 0` in shop or auction config.",
            "remediation": "Set a minimum 500ms-2s cooldown and test concurrent buys with `mc_bot_simulate_economy_stress`.",
        })

    errors = sum(1 for f in findings if f["severity"] == "error")
    warns = sum(1 for f in findings if f["severity"] == "warning")
    grade = "F" if errors >= 2 else ("D" if errors == 1 else ("C" if warns >= 2 else ("B" if warns == 1 else "A")))
    color = "brightgreen" if grade == "A" else ("green" if grade == "B" else ("yellow" if grade == "C" else "red"))

    return {
        "ok": errors == 0,
        "status": "fail" if errors > 0 else ("warn" if warns > 0 else "pass"),
        "grade": grade,
        "error_count": errors,
        "warning_count": warns,
        "findings": findings,
        "badge_json": {
            "schemaVersion": 1,
            "label": "economy audit",
            "message": f"grade {grade} · {errors} errors · {warns} warnings",
            "color": color,
        },
    }
