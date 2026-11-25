"""Profile and capability-module validator (`agent-cli-validate`) for agent-cli-spec."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from agent_cli_spec import __version__

SPEC_FILE = Path(__file__).resolve().parents[2] / "spec" / "spec.json"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
FLAG_RE = re.compile(r"(?<![A-Za-z0-9_])(--[A-Za-z][A-Za-z0-9_-]*|-[A-Za-z]{1,2})(?![A-Za-z0-9_-])")


def load_spec_registry() -> dict[str, Any]:
    return json.loads(SPEC_FILE.read_text(encoding="utf-8"))


def extract_flags(text: str) -> set[str]:
    """Extract normalized CLI flags from help text, normalizing -h/-ha aliases."""
    raw = set(FLAG_RE.findall(text))
    # Remove single-letter noise from prose like '-a' if needed; keep standard flags
    normalized: set[str] = set()
    for f in raw:
        if f in ("-h", "--help"):
            normalized.add("--help")
        elif f in ("-ha", "--help-agent"):
            normalized.add("--help-agent")
        elif f in ("-V", "--version"):
            normalized.add("--version")
        else:
            normalized.add(f)
    return normalized


def _run_cmd(cmd: list[str], *, env_extra: dict[str, str] | None = None, timeout: float = 5.0) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["NO_UPDATE_NOTIFIER"] = "1"
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def resolve_modules(
    *,
    profile: str | None,
    modules: list[str] | None,
    manifest_modules: dict[str, str] | None,
    registry: dict[str, Any],
) -> set[str]:
    if manifest_modules:
        return {f"{k}@{v}" for k, v in manifest_modules.items()}
    if modules:
        return set(modules)
    prof = profile or "full@1.0.0"
    profiles = registry.get("profiles", {})
    if prof not in profiles:
        raise ValueError(f"Unknown profile '{prof}'. Available: {', '.join(sorted(profiles))}")
    return set(profiles[prof])


def validate_cli(
    cmd: list[str],
    *,
    active_modules: set[str],
    max_ha_chars: int = 500,
    json_probe_args: list[str] | None = None,
    tui_probe_args: list[str] | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": ok, "detail": detail})
        if not ok:
            errors.append(f"{name}: {detail}")

    if any(m.startswith("core@") for m in active_modules):
        # 1. -ha and --help-agent
        rc_ha, out_ha, err_ha = _run_cmd([*cmd, "-ha"])
        rc_long, out_long, _ = _run_cmd([*cmd, "--help-agent"])
        record("core.ha_exit_zero", rc_ha == 0 and rc_long == 0, f"-ha={rc_ha}, --help-agent={rc_long}")
        record("core.ha_no_ansi", not ANSI_RE.search(out_ha), "plain UTF-8 without ANSI codes")
        record(
            "core.ha_max_chars",
            len(out_ha.strip()) <= max_ha_chars,
            f"len={len(out_ha.strip())} (max={max_ha_chars})",
        )
        has_grammar = "synopsis:" in out_ha and "exit_codes:" in out_ha
        record("core.ha_grammar", has_grammar, "requires 'synopsis:' and 'exit_codes:'")

        # 2. -h / --help and flag parity
        rc_h, out_h, _ = _run_cmd([*cmd, "-h"])
        record("core.help_exit_zero", rc_h == 0, f"-h exit={rc_h}")
        flags_h = extract_flags(out_h)
        flags_ha = extract_flags(out_ha)
        missing_in_ha = sorted(flags_h - flags_ha)
        record(
            "core.flag_parity",
            len(missing_in_ha) == 0,
            "all -h flags present in -ha" if not missing_in_ha else f"missing in -ha: {', '.join(missing_in_ha)}",
        )

        # 3. --version
        rc_ver, out_ver, err_ver = _run_cmd([*cmd, "--version"])
        ver_text = (out_ver or err_ver).strip()
        record("core.version_flag", rc_ver == 0 and bool(ver_text), f"exit={rc_ver}, out={ver_text!r}")

    if any(m.startswith("json-output@") for m in active_modules) and json_probe_args:
        rc_j, out_j, _ = _run_cmd([*cmd, *json_probe_args])
        valid_json = False
        if rc_j == 0:
            try:
                json.loads(out_j)
                valid_json = True
            except Exception:
                valid_json = False
        record("json_output.valid", valid_json, f"exit={rc_j}, probe={' '.join(json_probe_args)}")

    if any(m.startswith("tty-tui-guard@") for m in active_modules) and tui_probe_args:
        try:
            rc_t, _, err_t = _run_cmd([*cmd, *tui_probe_args], env_extra={"CI": "1"}, timeout=5.0)
            ok_tui = rc_t == 2 and bool(err_t.strip())
            record("tty_tui_guard.non_tty_exit_2", ok_tui, f"exit={rc_t}, stderr_len={len(err_t.strip())}")
        except subprocess.TimeoutExpired:
            record("tty_tui_guard.non_tty_exit_2", False, "timed out (hung waiting for TTY)")

    return {
        "ok": len(errors) == 0,
        "command": cmd,
        "modules": sorted(active_modules),
        "checks": checks,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if "-ha" in raw_args or "--help-agent" in raw_args:
        print(
            f"agent-cli-validate v{__version__} — Validate CLI tools against agent-cli-spec profiles\n"
            "synopsis: agent-cli-validate [-ha|--help-agent] [-h|--help] [--version] [--json] [--cmd CMD] [--manifest FILE] [--profile P] [--modules M] [--max-ha-chars N] [--json-args A] [--tui-args A]\n"
            "exit_codes: 0=valid | 1=validation_failed | 2=usage_error"
        )
        return 0

    parser = argparse.ArgumentParser(description="Validate a CLI tool against agent-cli-spec profiles.")
    parser.add_argument("-ha", "--help-agent", action="store_true", help="Compact agent synopsis")
    parser.add_argument("-V", "--version", action="version", version=f"agent-cli-validate v{__version__}")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--cmd", default=None, help="Target CLI command (e.g. 'agent-conv' or 'python tool.py')")
    parser.add_argument("--manifest", type=Path, default=None, help="Path to cli-spec.json manifest")
    parser.add_argument("--profile", default=None, help="Spec profile (e.g. full@1.0.0, core@1.0.0)")
    parser.add_argument("--modules", default=None, help="Comma-separated versioned modules (e.g. core@1.0.0,tty-tui-guard@1.0.0)")
    parser.add_argument("--max-ha-chars", type=int, default=None, help="Maximum -ha character count (default: 500)")
    parser.add_argument("--json-args", default=None, help="Args for json-output probe (e.g. 'adapters --json')")
    parser.add_argument("--tui-args", default=None, help="Args for tty-tui-guard probe (e.g. 'tui')")
    args = parser.parse_args(raw_args)

    registry = load_spec_registry()
    manifest_data: dict[str, Any] = {}
    if args.manifest:
        manifest_data = json.loads(args.manifest.read_text(encoding="utf-8"))

    cmd_str = args.cmd or manifest_data.get("binary")
    if not cmd_str:
        print("ERROR: --cmd or --manifest with 'binary' is required.", file=sys.stderr)
        return 2

    cmd = shlex.split(cmd_str)
    mod_list = [m.strip() for m in args.modules.split(",") if m.strip()] if args.modules else None
    active_modules = resolve_modules(
        profile=args.profile or manifest_data.get("profile"),
        modules=mod_list,
        manifest_modules=manifest_data.get("modules") if not args.profile and not mod_list else None,
        registry=registry,
    )
    max_ha = args.max_ha_chars or int(manifest_data.get("max_ha_chars", 500))
    json_args = shlex.split(args.json_args) if args.json_args else manifest_data.get("json_probe_args")
    tui_args = shlex.split(args.tui_args) if args.tui_args else manifest_data.get("tui_probe_args")

    result = validate_cli(
        cmd,
        active_modules=active_modules,
        max_ha_chars=max_ha,
        json_probe_args=json_args,
        tui_probe_args=tui_args,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for c in result["checks"]:
            mark = "OK" if c["ok"] else "FAIL"
            print(f"[{mark}] {c['check']}: {c['detail']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
