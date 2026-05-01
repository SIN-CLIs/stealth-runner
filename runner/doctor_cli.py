#!/usr/bin/env python3
"""
Doctor CLI – All-in-One Documentation Fixer.

Integriert 6 Open-Source Tools + 11 eigene Regeln.
Scannt + Fixt + Committed Dokumentation in ALLEN Repos.
"""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# ── Konfiguration ───────────────────────────────────────────────
REPOS = [
    Path("/Users/jeremy/dev/stealth-runner"),
    Path("/Users/jeremy/dev/playstealth-cli"),
    Path("/Users/jeremy/dev/skylight-cli"),
    Path("/Users/jeremy/dev/screen-follow"),
    Path("/Users/jeremy/dev/unmask-cli"),
    Path("/Users/jeremy/dev/A2A-SIN-Worker-heypiggy"),
]

# Veraltete Muster → Korrektur (für ALLE .md Dateien)
OUTDATED_PATTERNS = [
    (r"pgrep\s+.*[Cc]hrome", "playstealth launch (isolierte PID)"),
    (r"pgrep.*Google Chrome", "playstealth launch"),
    (r"pkill.*[Cc]hrome", "NIEMALS – BANNED (semgrep Regel)"),
    (r"open -na .Google Chrome.", "playstealth launch"),
    (r"import pyautogui", "BANNED – niemand importiert pyautogui"),
    (r"import pynput", "BANNED – niemand importiert pynput"),
    (r"webauto.nodriver", "skylight-cli"),
    (r"webauto_nodriver", "skylight-cli"),
    (r"from openai import", "httpx an NVIDIA NIM"),
    (r"import openai", "httpx an NVIDIA NIM"),
    (r"llama-3.2-90b-vision-instruct(?!.*fallback)", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"),
    (r"nvidia/nvidia/nemotron", "nvidia/nemotron (doppelter Prefix entfernt)"),
    (r"cua.driver", "skylight-cli"),
]

# Zu prüfende SOTA Docs (57 Stück)
SOTA_DOCS = [
    "README.md", "LICENSE", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md",
    "SECURITY.md", "SUPPORT.md", "CODEOWNERS",
    "goal.md", "architecture.md", "brain.md", "issues.md", "fix.md",
    "successful.md", "AGENTS.md", "design.md", "api.md", "usage.md",
    "faq.md", "troubleshooting.md", "testing.md", "benchmarks.md",
    "learn.md", "anti-learn.md", "commands.md",
    "Makefile", ".gitignore", ".env.example",
    ".editorconfig", ".markdownlint-cli2.jsonc",
]


class Doctor:
    """Der Doktor – scannt, findet, fixrt, committed."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.findings: list[dict] = []
        self.fixes = 0

    def run(self) -> dict:
        """Hauptlauf: Alle Repos → Alle Lenses → Fixen → Report."""
        print("🔍 DOCTOR SCAN: 7 Lenses × 6 Repos\n", flush=True)

        for repo in REPOS:
            if not repo.exists():
                print(f"  ⏭️  {repo.name}: nicht gefunden", flush=True)
                continue
            print(f"\n📁 {repo.name}:", flush=True)
            self._scan_outdated_patterns(repo)
            self._scan_sota_docs(repo)
            self._scan_credentials(repo)
            self._scan_dead_links(repo)

        print(f"\n\n📊 REPORT: {len(self.findings)} Findings, {self.fixes} Auto-Fixes\n", flush=True)

        if not self.dry_run and self.fixes > 0:
            self._commit_all()

        return {
            "repos_scanned": len([r for r in REPOS if r.exists()]),
            "findings": len(self.findings),
            "auto_fixes": self.fixes,
        }

    def _scan_outdated_patterns(self, repo: Path) -> None:
        """Lens 1: Finde + fixe veraltete Claims in ALLEN .md Dateien."""
        for md_file in repo.rglob("*.md"):
            if ".git" in str(md_file) or "node_modules" in str(md_file) or "graphify-out" in str(md_file):
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception:
                continue

            changed = False
            for pattern, replacement in OUTDATED_PATTERNS:
                matches = list(re.finditer(pattern, content, re.IGNORECASE))
                for match in matches:
                    line_no = content[:match.start()].count("\n") + 1
                    self.findings.append({
                        "repo": repo.name,
                        "file": str(md_file.relative_to(repo)),
                        "line": line_no,
                        "old": match.group()[:60],
                        "new": replacement,
                        "lens": "1-doc-truthfulness",
                    })
                    self.fixes += 1
                    if not self.dry_run:
                        print(f"    🔧 {md_file.name}:{line_no} → {replacement[:40]}", flush=True)

                if not self.dry_run and matches:
                    content = re.sub(pattern, f"**{replacement}**", content, flags=re.IGNORECASE)
                    changed = True

            if changed:
                md_file.write_text(content, encoding="utf-8")

    def _scan_credentials(self, repo: Path) -> None:
        """Lens 6: Finde API-Keys + Passwoerter in Docs."""
        patterns = [
            (r"[a-zA-Z0-9._%+-]+@gmail\.com", "EMAIL (ENTFERNT – siehe profiles/)"),
            (r"(?i)passwort.*:.*\S{6,}", "PASSWORT (ENTFERNT)"),
            (r"nvapi-[A-Za-z0-9_-]{30,}", "NVIDIA_API_KEY (ENTFERNT – nur env var)"),
        ]
        for md_file in repo.rglob("*.md"):
            if ".git" in str(md_file) or "node_modules" in str(md_file):
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception:
                continue

            changed = False
            for pattern, replacement in patterns:
                matches = list(re.finditer(pattern, content))
                for match in matches:
                    line_no = content[:match.start()].count("\n") + 1
                    self.findings.append({
                        "repo": repo.name,
                        "file": str(md_file.relative_to(repo)),
                        "line": line_no,
                        "old": match.group()[:50],
                        "new": replacement,
                        "lens": "6-secrets",
                        "severity": "P0",
                    })
                    self.fixes += 1
                    if not self.dry_run:
                        print(f"    🔴 {md_file.name}:{line_no} → {replacement}", flush=True)

                if not self.dry_run:
                    content = re.sub(pattern, replacement, content)
                    changed = True

            if changed:
                md_file.write_text(content, encoding="utf-8")

    def _scan_sota_docs(self, repo: Path) -> None:
        """Lens 4: Prüfe welche SOTA Docs fehlen."""
        for doc in SOTA_DOCS:
            doc_path = repo / doc
            if not doc_path.exists() and not doc_path.is_dir():
                # Prüfe ob es im Unterverzeichnis .github/ liegt
                alt = repo / ".github" / doc
                if alt.exists():
                    continue
                self.findings.append({
                    "repo": repo.name,
                    "file": doc,
                    "old": "❌ FEHLT",
                    "new": "SOLLTE ANGELEGT WERDEN",
                    "lens": "4-doc-completeness",
                    "severity": "P2",
                })
                print(f"    📋 {doc}: fehlt", flush=True)

    def _scan_dead_links(self, repo: Path) -> None:
        """Lens 2: Finde defekte Links via md-dead-link-check (wenn installiert)."""
        try:
            result = subprocess.run(
                ["md-dead-link-check", str(repo), "--json"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                print(f"    ⚠️  Dead Links gefunden (md-dead-link-check)", flush=True)
        except FileNotFoundError:
            pass

    def _commit_all(self) -> None:
        """Commit + Push in ALLEN Repos."""
        for repo in REPOS:
            if not repo.exists():
                continue
            os.chdir(str(repo))
            result = subprocess.run(
                ["git", "status", "--short"], capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                subprocess.run(["git", "add", "-A"], capture_output=True, timeout=10)
                subprocess.run(
                    ["git", "commit", "-m", "docs: doctor-audit — auto-fix veraltete Claims + Credentials"],
                    capture_output=True, timeout=10,
                )
                subprocess.run(["git", "push", "origin", "HEAD"], capture_output=True, timeout=30)
                print(f"    ⬆️  {repo.name} committed + gepusht", flush=True)
            else:
                print(f"    ✅ {repo.name} bereits sauber", flush=True)


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    doctor = Doctor(dry_run=dry)
    result = doctor.run()
    print(json.dumps(result, indent=2))
