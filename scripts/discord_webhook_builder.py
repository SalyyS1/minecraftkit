"""Secret-Redacted Discord Webhook Rich Embed Builder for MinecraftKit Bot QA & Ops."""

from __future__ import annotations

import re
from typing import Any


_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(/(?:login|l|register|reg|changepassword|cpw)\s+)\S+(?:\s+\S+)?", re.IGNORECASE), r"\1[REDACTED_PASSWORD]"),
    (re.compile(r"\bptl[ac]_[A-Za-z0-9_-]{12,}\b"), "[REDACTED_PANEL_KEY]"),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._-]{10,}", re.IGNORECASE), r"\1[REDACTED_TOKEN]"),
    (re.compile(r"((?:password|secret|token|totp_seed|api_key)\s*[:=]\s*)\S+", re.IGNORECASE), r"\1[REDACTED]"),
)


def _scrub(raw: str) -> str:
    out = str(raw or "")
    for pat, repl in _SECRET_PATTERNS:
        out = pat.sub(repl, out)
    return out


def build_discord_qa_webhook(
    *,
    server_name: str = "MyMinecraftServer",
    verdict: str = "PASS",
    passed_stages: int = 0,
    total_stages: int = 0,
    tps: float | None = None,
    mspt_ms: float | None = None,
    bot_ram_mb: int = 42,
    stage_lines: list[str] | None = None,
    report_url: str = "",
    fail_mention_role_id: str = "",
) -> dict[str, Any]:
    """Generate a secret-redacted Discord Webhook Rich Embed payload for QA/CI alerts."""
    norm_verdict = str(verdict or "PASS").strip().upper()
    if norm_verdict not in {"PASS", "WARN", "FAIL"}:
        norm_verdict = "FAIL" if passed_stages < total_stages else "PASS"

    color_map = {"PASS": 0x22C55E, "WARN": 0xF59E0B, "FAIL": 0xEF4444}
    emoji_map = {"PASS": "[PASS]", "WARN": "[WARN]", "FAIL": "[FAIL]"}

    clean_server = _scrub(server_name)[:80] or "MyMinecraftServer"
    clean_stages = [_scrub(s)[:140] for s in (stage_lines or [])[:12]]

    fields: list[dict[str, Any]] = [
        {"name": "Verdict", "value": f"{emoji_map[norm_verdict]} `{norm_verdict}`", "inline": True},
        {"name": "Stages", "value": f"`{int(passed_stages)}/{int(total_stages)}` passed", "inline": True},
        {"name": "Bot Footprint", "value": f"`{max(1, int(bot_ram_mb))} MB` (0 GUI)", "inline": True},
    ]
    if tps is not None:
        tps_val = f"`{float(tps):.2f}`" + (f" ({float(mspt_ms):.1f}ms MSPT)" if mspt_ms is not None else "")
        fields.append({"name": "Server TPS / MSPT", "value": tps_val, "inline": True})
    if clean_stages:
        fields.append({
            "name": "Stage Summary",
            "value": "\n".join(f"- {line}" for line in clean_stages)[:1000],
            "inline": False,
        })

    embed: dict[str, Any] = {
        "title": f"MinecraftKit QA · {clean_server}",
        "color": color_map[norm_verdict],
        "fields": fields,
        "footer": {"text": "MinecraftKit Autonomous Bot QA · Screen-Lock Free · Secrets Redacted"},
    }
    if report_url and report_url.strip().startswith(("https://", "http://")):
        embed["url"] = _scrub(report_url.strip())

    content = ""
    if norm_verdict == "FAIL" and re.fullmatch(r"\d{15,22}", str(fail_mention_role_id or "").strip()):
        content = f"<@&{fail_mention_role_id.strip()}> MinecraftKit QA regression detected on **{clean_server}**!"

    webhook_payload: dict[str, Any] = {
        "username": "MinecraftKit QA Bot",
        "allowed_mentions": {"parse": ["roles"] if content else []},
        "embeds": [embed],
    }
    if content:
        webhook_payload["content"] = content

    return {
        "ok": True,
        "verdict": norm_verdict,
        "secrets_redacted": True,
        "webhook_payload": webhook_payload,
    }
