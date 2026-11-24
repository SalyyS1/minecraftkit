#!/usr/bin/env python3
"""Static Minecraft 1.21.4+ / 26.3 Vanilla Core Shader & Iris/OptiFine Shader Pack Auditor."""

from __future__ import annotations

import re
from typing import Any


def audit_shader_source(
    *,
    source: str,
    filename: str = "rendertype_entity_cutout.fsh",
    target_mc_version: str = "1.21.4",
) -> dict[str, Any]:
    src = source or ""
    fname = (filename or "shader.fsh").strip()
    findings: list[dict[str, Any]] = []

    ver_m = re.search(r"(?m)^\s*#version\s+(\d+)", src)
    glsl_version = int(ver_m.group(1)) if ver_m else None
    if glsl_version is None:
        findings.append({
            "code": "SHD-001",
            "severity": "error",
            "message": f"{fname} is missing a '#version' directive (Minecraft 1.21+ requires '#version 150' or '#version 330 core').",
            "remediation": "Add `#version 150` (vanilla core) or `#version 330 core` at line 1.",
        })
    elif glsl_version < 150:
        findings.append({
            "code": "SHD-001",
            "severity": "warning",
            "message": f"Legacy GLSL #version {glsl_version} fails on macOS/modern OpenGL 3.2+ core profiles.",
            "remediation": "Upgrade to `#version 150` or `#version 330 core` and replace attribute/varying/texture2D with in/out/texture.",
        })

    if re.search(r"\b(gl_ModelViewMatrix|gl_ProjectionMatrix|gl_Vertex|gl_MultiTexCoord0|texture2D)\b", src):
        findings.append({
            "code": "SHD-002",
            "severity": "error",
            "message": "Deprecated OpenGL 2.x built-ins (gl_ModelViewMatrix / gl_Vertex / texture2D) detected; incompatible with Minecraft 1.21+ Core Profile.",
            "remediation": "Use Minecraft uniform blocks (ModelViewMat, ProjMat) and GLSL `texture(Sampler0, uv)`.",
        })

    if fname.endswith(".fsh") and re.search(r"\bdiscard\s*;", src) and "alpha" not in src.lower():
        findings.append({
            "code": "SHD-003",
            "severity": "note",
            "message": "Fragment shader calls `discard;` without an explicit alpha threshold guard; verify cutout transparency behavior.",
            "remediation": "Guard with `if (color.a < 0.1) { discard; }` to prevent accidental invisible geometry.",
        })

    # Check std140 vec3 alignment pitfall inside layout(std140) uniform blocks
    if "std140" in src and re.search(r"\bvec3\s+[A-Za-z_]\w*\s*;\s*\n\s*(?:float|int|vec2|vec3|vec4)\b", src):
        findings.append({
            "code": "SHD-004",
            "severity": "warning",
            "message": "std140 uniform block declares `vec3` followed by another member; std140 pads vec3 to 16-byte alignment (common UBO offset mismatch bug).",
            "remediation": "Use `vec4` (or explicit `float _pad;` after `vec3`) so CPU Java/ByteBuffer offsets match GPU std140 layout.",
        })

    if re.search(r"for\s*\([^)]*;\s*[^;]*<\s*(\d{3,})", src):
        findings.append({
            "code": "SHD-005",
            "severity": "warning",
            "message": "High-iteration loop (>=100 steps) inside fragment/vertex shader can crater FPS on integrated GPUs and headless Mesa containers.",
            "remediation": "Cap raymarch/blur loop bounds (<= 32 iterations) or downsample via multi-pass post-processing.",
        })

    penalty = sum(25 if f["severity"] == "error" else 12 if f["severity"] == "warning" else 4 for f in findings)
    score = max(0, min(100, 100 - penalty))
    grade = "A" if score >= 90 else "B" if score >= 78 else "C" if score >= 62 else "D" if score >= 45 else "F"

    return {
        "ok": not any(f["severity"] == "error" for f in findings),
        "grade": grade,
        "score": score,
        "filename": fname,
        "target_mc_version": target_mc_version,
        "glsl_version": glsl_version,
        "finding_count": len(findings),
        "findings": findings,
    }
