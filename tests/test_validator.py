from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "python" / "src"))

from agent_clikit import render_help_agent  # noqa: E402
from agent_cli_spec.validate import load_spec_registry, resolve_modules, validate_cli  # noqa: E402


def test_render_help_agent_introspects_argparse() -> None:
    p = argparse.ArgumentParser(prog="sample", description="Sample CLI")
    p.add_argument("-ha", "--help-agent", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    out = render_help_agent(p, version="1.0.0")
    assert "sample v1.0.0" in out
    assert "--json" in out
    assert "--dry-run" in out
    assert len(out) <= 500


def test_validator_catches_ha_over_500_chars(tmp_path: Path) -> None:
    script = tmp_path / "bad_cli.py"
    script.write_text(
        "import sys\n"
        "if '-ha' in sys.argv or '--help-agent' in sys.argv:\n"
        "    print('synopsis: bad\\n' + 'x'*520 + '\\nexit_codes: 0=ok')\n"
        "elif '-h' in sys.argv:\n"
        "    print('usage: bad [-ha] [-h] [--version]')\n"
        "elif '--version' in sys.argv:\n"
        "    print('bad v1.0.0')\n",
        encoding="utf-8",
    )
    res = validate_cli([sys.executable, str(script)], active_modules={"core@1.0.0"})
    assert not res["ok"]
    assert any("core.ha_max_chars" in e for e in res["errors"])


def test_validator_catches_flag_parity_mismatch(tmp_path: Path) -> None:
    script = tmp_path / "parity_cli.py"
    script.write_text(
        "import sys\n"
        "if '-ha' in sys.argv or '--help-agent' in sys.argv:\n"
        "    print('p v1.0.0\\nsynopsis: p [-ha]\\nexit_codes: 0=ok')\n"
        "elif '-h' in sys.argv:\n"
        "    print('usage: p [-ha] [--secret-flag]')\n"
        "elif '--version' in sys.argv:\n"
        "    print('p v1.0.0')\n",
        encoding="utf-8",
    )
    res = validate_cli([sys.executable, str(script)], active_modules={"core@1.0.0"})
    assert not res["ok"]
    assert any("core.flag_parity" in e and "--secret-flag" in e for e in res["errors"])


def test_validator_tui_guard_passes_on_exit_2(tmp_path: Path) -> None:
    script = tmp_path / "tui_cli.py"
    script.write_text(
        "import sys\n"
        "if 'tui' in sys.argv:\n"
        "    print('ERROR: interactive TTY required', file=sys.stderr)\n"
        "    raise SystemExit(2)\n",
        encoding="utf-8",
    )
    res = validate_cli(
        [sys.executable, str(script)],
        active_modules={"tty-tui-guard@1.0.0"},
        tui_probe_args=["tui"],
    )
    assert res["ok"]


def test_resolve_custom_modules() -> None:
    reg = load_spec_registry()
    mods = resolve_modules(
        profile="custom",
        modules=None,
        manifest_modules={"core": "1.0.0", "tty-tui-guard": "1.0.0"},
        registry=reg,
    )
    assert mods == {"core@1.0.0", "tty-tui-guard@1.0.0"}
