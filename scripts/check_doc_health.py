#!/usr/bin/env python3
"""
Stealth Suite SOTA Doc‑Health Auditor
======================================
Prüft ALLE Stealth-Suite Repos auf ALLE Pflichtdateien,
UPPERCASE-Verstöße und fehlende Registry-Files.

Usage:
    python3 scripts/check_doc_health.py              # Alle Repos
    python3 scripts/check_doc_health.py --repo X     # Ein Repo
    python3 scripts/check_doc_health.py --json       # JSON Output
    python3 scripts/check_doc_health.py --violations # Nur UPPERCASE-Verstöße
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# --- Konfiguration ---
SIN_CLIS_REPOS = [
    "stealth-runner",
    "playstealth-cli",
    "cua-touch",
    "macos-ax-cli",
    "screen-follow",
    "unmask-cli",
    "stealth-captcha",
    "secret-manager-cli",
    "stealth-memory",
    "stealth-skills",
    "stealth-guardian",
    "stealth-axiom",
    "stealth-core",
    "stealth-dynamic",
    "stealth-session",
    "stealth-sota",
    "stealth-config",
    "stealth-cache",
    "stealth-compressor",
    "stealth-optimizer",
    "stealth-batch",
    "stealth-cost",
    "stealth-lora",
]

# Tier 1: Core (MUSS in JEDEM Repo vorhanden sein)
REQUIRED_CORE = [
    "sinrules.md", "agents.md", "brain.md", "fix.md",
    "successful.md", "learn.md", "anti-learn.md", "banned.md",
    "history.md", "registry.md", "issues.md", "changelog.md",
    "goal.md", "roadmap.md",
]

# Tier 2: Extra (sollte vorhanden sein)
REQUIRED_EXTRA = [
    "readme.md", "architecture.md", "api.md", "usage.md",
    "testing.md", "benchmarks.md", "plan.md", "faq.md",
    "security.md", "contributing.md", "troubleshooting.md",
    "support.md", "design.md", "commands.md",
]

# Tier 3: Registry (Katalog-Dateien)
REQUIRED_REGISTRY = [
    "registry-perception.md", "registry-actuation.md",
    "registry-graphify.md", "registry-skills.md",
    "registry-credentials.md",
]

# Tier 4: Spezifisch (projektabhängig)
REQUIRED_SPECIFIC = [
    "graphify.md", "graph-report.md", "infisical.md",
    "tool-registry.md", "tool-manifest.md", "opencode.md", "state.md",
]

# Tier 5: Extended Registry + Infra (6 files)
REQUIRED_EXTENDED = [
    "registry-google.md", "registry-surveys.md", "registry-macos.md",
    "graph.json", "manifest.json", ".opencode/opencode.json",
]

# UPPERCASE violations (existieren in lowercase? wenn ja → in Ordnung, sonst → violation)
UPPERCASE_VIOLATIONS = [
    "AGENTS.md", "README.md", "CHANGELOG.md", "SECURITY.md",
    "CONTRIBUTING.md", "SUPPORT.md", "CODE_OF_CONDUCT.md",
    "GRAPH_REPORT.md", "INFISICAL_ENV_VARS.md",
]

ALL_REQUIRED = REQUIRED_CORE + REQUIRED_EXTRA + REQUIRED_REGISTRY + REQUIRED_SPECIFIC + REQUIRED_EXTENDED

DEV_ROOT = Path("/Users/jeremy/dev")


def find_repo(name: str) -> Path | None:
    """Find repo dir by name in /Users/jeremy/dev."""
    # Some repos have different directory names
    mappings = {
        "stealth-runner": "stealth-runner",
        "playstealth-cli": "playstealth-cli",
        "cua-touch": "cua-touch",
        "macos-ax-cli": "macos-ax-cli",
        "screen-follow": "screen-follow",
        "unmask-cli": "unmask-cli",
        "stealth-captcha": "stealth-captcha",
        "secret-manager-cli": "secret-manager-cli",
        "stealth-memory": "stealth-memory",
    }
    dir_name = mappings.get(name, name)
    path = DEV_ROOT / dir_name
    if path.is_dir():
        return path
    # Try find
    result = subprocess.run(
        ["find", str(DEV_ROOT), "-maxdepth", "3", "-name", name, "-type", "d"],
        capture_output=True, text=True, timeout=5
    )
    for line in result.stdout.strip().split('\n'):
        p = Path(line)
        if p.is_dir() and '.git' not in str(p) and 'node_modules' not in str(p):
            return p
    return None


def check_repo(repo_path: Path) -> dict:
    """SOTA Audit: check ALL required files + UPPERCASE violations."""
    result = {
        "repo": str(repo_path),
        "core_found": [], "core_missing": [],
        "extra_found": [], "extra_missing": [],
        "registry_found": [], "registry_missing": [],
        "specific_found": [], "specific_missing": [],
        "extended_found": [], "extended_missing": [],
        "uppercase_violations": [],
    }
    # Tier 1: Core
    for f in REQUIRED_CORE:
        if (repo_path / f).exists():
            result["core_found"].append(f)
        else:
            result["core_missing"].append(f)
    # Tier 2: Extra
    for f in REQUIRED_EXTRA:
        if (repo_path / f).exists():
            result["extra_found"].append(f)
        else:
            result["extra_missing"].append(f)
    # Tier 3: Registry
    for f in REQUIRED_REGISTRY:
        if (repo_path / f).exists():
            result["registry_found"].append(f)
        else:
            result["registry_missing"].append(f)
    # Tier 4: Specific
    for f in REQUIRED_SPECIFIC:
        if (repo_path / f).exists():
            result["specific_found"].append(f)
        else:
            result["specific_missing"].append(f)
    # Tier 5: Extended
    for f in REQUIRED_EXTENDED:
        if (repo_path / f).exists():
            result["extended_found"].append(f)
        else:
            result["extended_missing"].append(f)
    # UPPERCASE violations check
    for f in UPPERCASE_VIOLATIONS:
        upper = repo_path / f
        if upper.exists():
            lower_name = f.lower()
            lower = repo_path / lower_name
            if not lower.exists():
                result["uppercase_violations"].append(f)
    # Scoring
    total_found = (
        len(result["core_found"]) + len(result["extra_found"]) +
        len(result["registry_found"]) + len(result["specific_found"]) +
        len(result["extended_found"])
    )
    total_required = len(ALL_REQUIRED)
    result["score"] = total_found
    result["max_score"] = total_required
    result["pct"] = round(100 * total_found / total_required, 1) if total_required else 0
    result["violation_count"] = len(result["uppercase_violations"])
    return result


def main():
    json_mode = "--json" in sys.argv
    repo_filter = None
    for i, arg in enumerate(sys.argv):
        if arg == "--repo" and i + 1 < len(sys.argv):
            repo_filter = sys.argv[i + 1]

    repos_to_check = [repo_filter] if repo_filter else SIN_CLIS_REPOS
    violations_only = "--violations" in sys.argv
    results = []
    for name in repos_to_check:
        path = find_repo(name)
        if not path:
            continue
        r = check_repo(path)
        results.append(r)
        if json_mode:
            continue
        total = r["score"]
        max_s = r["max_score"]
        pct = r["pct"]
        v = r["violation_count"]
        status = "🟢" if pct >= 90 else "🟡" if pct >= 50 else "🔴"
        vflag = f" ⚠️{v}UPPER" if v > 0 else ""
        if violations_only and v == 0:
            continue
        print(f"  {status} {name}: {pct}% ({total}/{max_s}){vflag}")
        if r["core_missing"]:
            print(f"     CORE missing: {', '.join(r['core_missing'][:4])}" +
                  (f" +{len(r['core_missing'])-4}" if len(r['core_missing']) > 4 else ""))
        if r["uppercase_violations"]:
            print(f"     UPPER violations: {', '.join(r['uppercase_violations'])}")
    if json_mode:
        print(json.dumps(results, indent=2, default=str))
    else:
        total_found = sum(r["score"] for r in results)
        total_max = sum(r["max_score"] for r in results)
        total_v = sum(r["violation_count"] for r in results)
        print(f"\n  📊 SOTA: {total_found}/{total_max} ({round(100*total_found/total_max,1)}%) | {total_v} UPPERCASE | {len(results)} repos")


if __name__ == "__main__":
    main()
