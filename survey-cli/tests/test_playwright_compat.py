"""
Tests for survey.daemon._playwright_compat (CEO-WAVE-1).

What we verify:
  - Module imports cleanly even without patchright OR playwright present.
  - BACKEND_NAME is one of {"patchright", "playwright", "none"}.
  - get_async_playwright() raises ImportError with actionable message
    when neither backend is installed.
  - get_async_playwright() returns whatever the importable backend
    exposes as `async_playwright`.

These tests intentionally do NOT spin up a real browser. The goal is to
prove the SHIM behaves correctly under all three install postures, not to
re-test playwright's own contract.
"""

from __future__ import annotations

import sys
import types

import pytest


def _force_reimport(monkeypatch: pytest.MonkeyPatch, *, install: dict[str, types.ModuleType] | None) -> object:
    """Reload the compat module under a controlled set of fake browser
    packages installed in sys.modules. Returns the freshly-loaded module.
    """
    install = install or {}

    # Drop any cached real-world imports of patchright / playwright so the
    # shim's `try: import patchright; except ImportError` actually exercises
    # our injected ImportErrors.
    for blocked in ("patchright", "patchright.async_api", "playwright", "playwright.async_api"):
        monkeypatch.delitem(sys.modules, blocked, raising=False)

    # Inject the requested fakes.
    for name, mod in install.items():
        monkeypatch.setitem(sys.modules, name, mod)

    # Drop and re-import the module under test.
    monkeypatch.delitem(sys.modules, "survey.daemon._playwright_compat", raising=False)

    import importlib

    return importlib.import_module("survey.daemon._playwright_compat")


def _fake_async_playwright() -> object:
    """A sentinel that we can identity-check on the way back out."""
    return object()


def _fake_backend(name: str) -> dict[str, types.ModuleType]:
    """Build a sys.modules dict that fakes either patchright.async_api or
    playwright.async_api, exposing `async_playwright = <sentinel>`."""
    pkg = types.ModuleType(name)
    pkg.__path__ = []  # mark as package so submodule import works
    submod = types.ModuleType(f"{name}.async_api")
    sentinel = _fake_async_playwright()
    submod.async_playwright = sentinel  # type: ignore[attr-defined]
    return {name: pkg, f"{name}.async_api": submod, "_sentinel": sentinel}  # type: ignore[dict-item]


def test_imports_cleanly_without_either_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _force_reimport(monkeypatch, install=None)
    assert mod.BACKEND_NAME == "none"


def test_get_async_playwright_raises_when_neither_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _force_reimport(monkeypatch, install=None)
    with pytest.raises(ImportError) as exc:
        mod.get_async_playwright()
    msg = str(exc.value).lower()
    assert "patchright" in msg
    assert "playwright" in msg
    assert "install" in msg


def test_prefers_patchright_when_both_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes_p = _fake_backend("patchright")
    fakes_pw = _fake_backend("playwright")
    install = {k: v for k, v in fakes_p.items() if not k.startswith("_")} | {
        k: v for k, v in fakes_pw.items() if not k.startswith("_")
    }
    mod = _force_reimport(monkeypatch, install=install)
    assert mod.BACKEND_NAME == "patchright"
    assert mod.get_async_playwright() is fakes_p["_sentinel"]


def test_falls_back_to_playwright_when_patchright_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes_pw = _fake_backend("playwright")
    install = {k: v for k, v in fakes_pw.items() if not k.startswith("_")}
    mod = _force_reimport(monkeypatch, install=install)
    assert mod.BACKEND_NAME == "playwright"
    assert mod.get_async_playwright() is fakes_pw["_sentinel"]


def test_backend_name_is_one_of_known_values(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _force_reimport(monkeypatch, install=None)
    assert mod.BACKEND_NAME in {"patchright", "playwright", "none"}
