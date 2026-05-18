"""
Tests for stealth_captcha._playwright_compat (CEO-WAVE-1).

Mirror of survey-cli's compat tests, plus a check on
`subprocess_import_block()` since this package needs the subprocess-side
import logic for the Angular CDK drag-drop solver.
"""

from __future__ import annotations

import sys
import types

import pytest


def _force_reimport(
    monkeypatch: pytest.MonkeyPatch,
    *,
    install: dict[str, types.ModuleType] | None,
) -> object:
    install = install or {}
    for blocked in ("patchright", "patchright.async_api", "playwright", "playwright.async_api"):
        monkeypatch.delitem(sys.modules, blocked, raising=False)
    for name, mod in install.items():
        monkeypatch.setitem(sys.modules, name, mod)
    monkeypatch.delitem(sys.modules, "stealth_captcha._playwright_compat", raising=False)
    import importlib

    return importlib.import_module("stealth_captcha._playwright_compat")


def _fake_backend(name: str) -> dict[str, types.ModuleType]:
    pkg = types.ModuleType(name)
    pkg.__path__ = []
    submod = types.ModuleType(f"{name}.async_api")
    sentinel = object()
    submod.async_playwright = sentinel  # type: ignore[attr-defined]
    return {name: pkg, f"{name}.async_api": submod, "_sentinel": sentinel}  # type: ignore[dict-item]


def test_imports_cleanly_without_either_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _force_reimport(monkeypatch, install=None)
    assert mod.BACKEND_NAME == "none"


def test_subprocess_block_works_without_either_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The drag-drop solver may be imported on hosts where neither browser
    library is present yet. The subprocess block is a pure string and must
    not depend on either being installed."""
    mod = _force_reimport(monkeypatch, install=None)
    block = mod.subprocess_import_block()
    assert "patchright" in block
    assert "playwright" in block
    assert "except ImportError" in block


@pytest.mark.parametrize("indent", [0, 4, 8, 12])
def test_subprocess_block_indent_is_uniform_and_compiles(monkeypatch: pytest.MonkeyPatch, indent: int) -> None:
    """The block is inlined inside a function body. Every non-empty line
    must start with exactly `indent` spaces, and the resulting Python
    must compile under any of the common nesting depths."""
    mod = _force_reimport(monkeypatch, install=None)
    block = mod.subprocess_import_block(indent=indent)
    pad = " " * indent
    for line in block.splitlines():
        if line.strip():
            assert line.startswith(pad), f"line not padded with {indent} spaces: {line!r}"

    # Wrap in a function to make the inlined block a legal piece of code,
    # then make sure it parses. We can't actually exec it (no browser
    # libraries here) but compile() is enough to catch indentation bugs.
    src = "def _wrap():\n" + ("    pass\n" if indent == 0 else "")
    if indent == 0:
        # block sits at module level, separate test
        src = block + "\n"
    else:
        src = "def _wrap():\n" + block
    compile(src, "<test>", "exec")


def test_get_async_playwright_raises_when_neither_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _force_reimport(monkeypatch, install=None)
    with pytest.raises(ImportError) as exc:
        mod.get_async_playwright()
    msg = str(exc.value).lower()
    assert "patchright" in msg and "playwright" in msg


def test_prefers_patchright(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes_p = _fake_backend("patchright")
    fakes_pw = _fake_backend("playwright")
    install = {k: v for k, v in fakes_p.items() if not k.startswith("_")} | {
        k: v for k, v in fakes_pw.items() if not k.startswith("_")
    }
    mod = _force_reimport(monkeypatch, install=install)
    assert mod.BACKEND_NAME == "patchright"
    assert mod.get_async_playwright() is fakes_p["_sentinel"]


def test_falls_back_to_playwright(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes_pw = _fake_backend("playwright")
    install = {k: v for k, v in fakes_pw.items() if not k.startswith("_")}
    mod = _force_reimport(monkeypatch, install=install)
    assert mod.BACKEND_NAME == "playwright"
    assert mod.get_async_playwright() is fakes_pw["_sentinel"]
