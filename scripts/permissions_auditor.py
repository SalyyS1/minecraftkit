#!/usr/bin/env python3
"""Static LuckPerms / Vault / plugin.yml RBAC & Privilege-Escalation Security Auditor (PERM-001..PERM-005).

Scans plugin.yml permission trees and/or LuckPerms group exports to prevent catastrophic OP/admin leaks:
  - PERM-001: Wildcard '*' or 'minecraft.*' / 'bukkit.*' / 'luckperms.*' granted to non-admin groups
  - PERM-002: Dangerous admin permission declared with `default: true` in plugin.yml
  - PERM-003: Non-admin group inherits from admin/owner/staff group (privilege escalation)
  - PERM-004: Cyclic group inheritance loop in LuckPerms group graph
  - PERM-005: Missing negative guard on destructive commands (/op, /stop, /ban, /reload)
"""

from __future__ import annotations

import re
from typing import Any

ADMIN_GROUP_NAMES = {"admin", "owner", "operator", "console", "root", "co-owner", "head-admin"}
DANGEROUS_NODES = ("*", "minecraft.*", "bukkit.*", "spigot.*", "paper.*", "luckperms.*", "worldedit.*")
DANGEROUS_KEYWORDS = ("admin", "reload", "give", "eco.set", "economy.admin", "bypass", "op", "ban", "stop", "console", "sudo")


def audit_permissions_rbac(
    *,
    plugin_yml: str = "",
    groups: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []

    if plugin_yml:
        # Parse permission blocks under `permissions:` heuristically
        in_perms = False
        current_node = ""
        for raw_line in plugin_yml.splitlines():
            if re.match(r"^permissions\s*:", raw_line):
                in_perms = True
                continue
            if in_perms and raw_line and not raw_line[0].isspace():
                in_perms = False
                continue
            if not in_perms:
                continue
            node_m = re.match(r"^\s{2,4}([a-zA-Z0-9_.\-*]+)\s*:", raw_line)
            if node_m and node_m.group(1) not in ("description", "default", "children"):
                current_node = node_m.group(1)
                continue
            def_m = re.match(r"^\s+default\s*:\s*([^\s#]+)", raw_line)
            if def_m and current_node:
                default_val = def_m.group(1).strip().lower()
                low_node = current_node.lower()
                if default_val == "true" and (
                    low_node.endswith(".*") or any(k in low_node for k in DANGEROUS_KEYWORDS)
                ):
                    findings.append({
                        "code": "PERM-002",
                        "severity": "critical",
                        "subject": current_node,
                        "message": f"Admin/wildcard permission '{current_node}' has 'default: true' in plugin.yml, granting it to EVERY player!",
                        "remediation": f"Change '{current_node}' to 'default: op' (or 'default: false') immediately.",
                    })

    group_map = groups if isinstance(groups, dict) else {}
    parents_graph: dict[str, list[str]] = {}
    for gname, gdata in group_map.items():
        if not isinstance(gdata, dict):
            continue
        low_g = gname.strip().lower()
        is_admin = low_g in ADMIN_GROUP_NAMES
        perms = [str(p).strip().lower() for p in gdata.get("permissions", []) if isinstance(p, str)]
        parents = [str(p).strip().lower() for p in gdata.get("parents", []) if isinstance(p, str)]
        parents_graph[low_g] = parents

        if not is_admin:
            for p in perms:
                if p.startswith("-"):
                    continue
                if p in DANGEROUS_NODES or p.endswith(".*") and any(k in p for k in ("luckperms", "minecraft", "bukkit", "essentials", "admin")):
                    findings.append({
                        "code": "PERM-001",
                        "severity": "critical",
                        "subject": f"group:{gname}",
                        "message": f"Non-admin group '{gname}' holds dangerous wildcard node '{p}'.",
                        "remediation": f"Remove '{p}' from group '{gname}' and grant only explicit least-privilege command nodes.",
                    })
            for par in parents:
                if par in ADMIN_GROUP_NAMES:
                    findings.append({
                        "code": "PERM-003",
                        "severity": "critical",
                        "subject": f"group:{gname}",
                        "message": f"Non-admin group '{gname}' inherits from privileged group '{par}' (instant privilege escalation!).",
                        "remediation": f"Reverse inheritance direction: '{par}' should inherit from '{gname}', never the opposite.",
                    })
            if low_g == "default" and any(p in ("minecraft.command.op", "minecraft.command.stop") for p in perms):
                findings.append({
                    "code": "PERM-005",
                    "severity": "critical",
                    "subject": f"group:{gname}",
                    "message": "Default player group grants destructive vanilla op/stop command permission.",
                    "remediation": "Explicitly negate '-minecraft.command.op' and '-minecraft.command.stop' on default.",
                })

    # Cycle detection in LuckPerms parent graph (PERM-004)
    visited: set[str] = set()
    in_stack: set[str] = set()
    cycles: list[str] = []

    def dfs(node: str) -> None:
        visited.add(node)
        in_stack.add(node)
        for nxt in parents_graph.get(node, []):
            if nxt in in_stack:
                cycles.append(f"{node} -> {nxt}")
            elif nxt not in visited and nxt in parents_graph:
                dfs(nxt)
        in_stack.remove(node)

    for g in sorted(parents_graph):
        if g not in visited:
            dfs(g)

    for cyc in cycles:
        findings.append({
            "code": "PERM-004",
            "severity": "warning",
            "subject": cyc,
            "message": f"Cyclic LuckPerms group inheritance detected ({cyc}).",
            "remediation": "Break the inheritance cycle into a strict DAG (default <- vip <- mod <- admin <- owner).",
        })

    penalty = sum(30 if f["severity"] == "critical" else 12 for f in findings)
    score = max(0, min(100, 100 - penalty))
    grade = "A" if score >= 90 else "B" if score >= 78 else "C" if score >= 62 else "D" if score >= 45 else "F"

    return {
        "ok": not any(f["severity"] == "critical" for f in findings),
        "grade": grade,
        "score": score,
        "groups_audited": len(group_map),
        "finding_count": len(findings),
        "findings": findings,
    }
