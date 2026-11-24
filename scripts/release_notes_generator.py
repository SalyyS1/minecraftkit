#!/usr/bin/env python3
"""Bilingual (EN/VI) Modrinth / Hangar / SpigotMC / Discord Plugin Release Notes & QA Proof Generator."""

from __future__ import annotations

from typing import Any


def generate_plugin_release_notes(
    *,
    plugin_name: str,
    version: str,
    mc_versions: list[str] | None = None,
    platforms: list[str] | None = None,
    highlights: list[str] | None = None,
    fixes: list[str] | None = None,
    qa_passed_stages: int = 0,
    qa_total_stages: int = 0,
    folia_ready: bool = True,
    exploit_audit_grade: str = "A",
    language: str = "bilingual",
) -> dict[str, Any]:
    name = (plugin_name or "MyPlugin").strip() or "MyPlugin"
    ver = (version or "1.0.0").strip() or "1.0.0"
    vers = ", ".join(mc_versions or ["1.21.4", "1.21.11", "26.3"])
    plats = ", ".join(platforms or ["Paper", "Folia", "Purpur"])
    hi = highlights or ["Improved stability and autonomous QA coverage."]
    fx = fixes or ["Fixed edge cases verified by headless bot regression stages."]
    lang = (language or "bilingual").strip().lower()

    qa_badge = (
        f"Verified `{qa_passed_stages}/{qa_total_stages}` Autonomous Bot Stages · "
        f"Folia: `{'READY' if folia_ready else 'PAPER-ONLY'}` · Anti-Exploit Grade: `{exploit_audit_grade}`"
    )

    en_lines = [
        f"## {name} v{ver}",
        f"**Supported Platforms:** {plats} | **Minecraft:** {vers}",
        f"> **MinecraftKit QA Proof:** {qa_badge}",
        "",
        "### Highlights",
        *[f"- {item}" for item in hi],
        "",
        "### Bug Fixes & Hardening",
        *[f"- {item}" for item in fx],
    ]

    vi_lines = [
        f"## {name} v{ver} (Tiếng Việt)",
        f"**Nền tảng hỗ trợ:** {plats} | **Minecraft:** {vers}",
        f"> **Chứng nhận kiểm thử tự động MinecraftKit:** {qa_badge}",
        "",
        "### Điểm nổi bật",
        *[f"- {item}" for item in hi],
        "",
        "### Sửa lỗi & Tối ưu",
        *[f"- {item}" for item in fx],
    ]

    if lang == "en":
        md = "\n".join(en_lines) + "\n"
    elif lang == "vi":
        md = "\n".join(vi_lines) + "\n"
    else:
        md = "\n".join(en_lines) + "\n\n---\n\n" + "\n".join(vi_lines) + "\n"

    discord_announcement = (
        f"🚀 **{name} v{ver} is live!** ({plats} · MC {vers})\n"
        f"✅ QA Proof: {qa_badge}\n"
        + "\n".join(f"• {item}" for item in hi[:5])
    )

    return {
        "ok": True,
        "plugin_name": name,
        "version": ver,
        "language": lang,
        "qa_proof_line": qa_badge,
        "markdown": md,
        "discord_announcement": discord_announcement,
    }
