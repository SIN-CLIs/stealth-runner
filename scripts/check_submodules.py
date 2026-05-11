#!/usr/bin/env python3
"""Pre-Commit Hook: Validate all submodules have proper configuration (SR-73, 2026-05-11).

Spec (aus AGENTS.md §11.9):
  - Jede 160000-Zeile von `git ls-tree HEAD` muss durch
    `git config -f .gitmodules submodule.<name>.url` aufgelöst werden
  - Exit 0 nur wenn alle Submodule korrekt konfiguriert
  - Exit 1 wenn .gitmodules fehlt ODER Submodule ohne URL

Module Status: PRODUCTION (SR-73, 2026-05-11)
Wire-up: .pre-commit-config.yaml + CI Step in .github/workflows/ci.yml (§13.8.4)
"""

import subprocess
import sys
import os
from pathlib import Path


def get_tree_submodules() -> list[str]:
    """Get all submodule entries from git ls-tree (160000 mode = gitlink)."""
    try:
        result = subprocess.run(
            ["git", "ls-tree", "HEAD"],
            capture_output=True, text=True, check=True
        )
        submodules = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            # Format: <mode> <type> <hash>\t<path>
            parts = line.split("\t")
            if len(parts) >= 2:
                mode_type = parts[0].split()
                if len(mode_type) >= 2 and mode_type[1] == "commit":  # 160000 = commit (submodule)
                    submodules.append(parts[1])
        return submodules
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] git ls-tree failed: {e.stderr}", file=sys.stderr)
        return []


def check_gitmodules_exists() -> bool:
    """Check if .gitmodules file exists."""
    return Path(".gitmodules").exists()


def get_submodule_url(name: str) -> str | None:
    """Get submodule URL from .gitmodules config."""
    try:
        result = subprocess.run(
            ["git", "config", "-f", ".gitmodules", f"submodule.{name}.url"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except subprocess.CalledProcessError:
        return None


def main():
    """Main validation logic."""
    # Get all submodules from tree
    tree_submodules = get_tree_submodules()

    # If no submodules in tree, we pass (valid state per §11.9 Option B)
    if not tree_submodules:
        print("[✓] No submodules in git tree (valid per §11.9 Option B)")
        return 0

    # If submodules exist, .gitmodules MUST exist and have URLs for each
    gitmodules_exists = check_gitmodules_exists()

    if not gitmodules_exists:
        print(
            f"[✗] FAIL: {len(tree_submodules)} submodule(s) in git tree but .gitmodules missing:",
            file=sys.stderr
        )
        for name in tree_submodules:
            print(f"    - {name}", file=sys.stderr)
        print("\nFix: Either remove submodules (git rm --cached) or create .gitmodules", file=sys.stderr)
        return 1

    # Validate each submodule has a URL in .gitmodules
    failed = []
    for name in tree_submodules:
        url = get_submodule_url(name)
        if not url:
            failed.append(name)
            print(f"[✗] Submodule '{name}' has no URL in .gitmodules", file=sys.stderr)

    if failed:
        print(
            f"\n[✗] FAIL: {len(failed)} submodule(s) missing URL configuration",
            file=sys.stderr
        )
        return 1

    print(f"[✓] All {len(tree_submodules)} submodule(s) properly configured")
    return 0


if __name__ == "__main__":
    sys.exit(main())
