"""Zero-dependency Python reference library for agent-cli-spec (`agent-clikit`)."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
import urllib.request
from pathlib import Path

SPEC_VERSION = "1.0.0"
UPDATE_CACHE_TTL_SECONDS = 86400
_CI_ENV_VARS = ("CI", "GITHUB_ACTIONS", "GITLAB_CI", "TF_BUILD", "BUILDKITE", "CIRCLECI")
_SUPPRESS_FLAGS = frozenset({"--json", "-ha", "--help-agent", "--version", "-V", "-h", "--help"})


def render_help_agent(
    parser: argparse.ArgumentParser,
    *,
    name: str | None = None,
    version: str = "1.0.0",
    description: str | None = None,
    exit_codes: str = "0=ok | 1=error | 2=usage_error",
) -> str:
    """Introspect an argparse.ArgumentParser and render compact <=500 char -ha output."""
    prog = name or parser.prog or "cli"
    desc = description or parser.description or prog
    opts: list[str] = []
    subcmds: list[str] = []

    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for cmd_name in action.choices:
                subcmds.append(cmd_name)
        elif action.option_strings:
            # Prefer longest option string for compactness, keep -ha/-h visible
            if "-ha" in action.option_strings:
                opts.append("-ha|--help-agent")
            elif "-h" in action.option_strings:
                opts.append("-h|--help")
            else:
                opts.append(max(action.option_strings, key=len))

    opt_str = " ".join(f"[{o}]" for o in opts)
    cmd_str = f" <{'|'.join(subcmds)}>" if subcmds else ""
    lines = [
        f"{prog} v{version} — {desc}",
        f"synopsis: {prog} {opt_str}{cmd_str}".strip(),
        f"exit_codes: {exit_codes}",
    ]
    return "\n".join(lines)


def is_ci() -> bool:
    for key in _CI_ENV_VARS:
        val = os.environ.get(key, "").strip()
        if val and val.lower() not in ("0", "false"):
            return True
    return False


def is_interactive_tty() -> bool:
    if is_ci() or os.environ.get("TERM", "").strip().lower() == "dumb":
        return False
    return bool(sys.stdin.isatty() and sys.stdout.isatty())


def can_notify_update(argv: list[str] | None = None) -> bool:
    if is_ci() or os.environ.get("TERM", "").strip().lower() == "dumb":
        return False
    if os.environ.get("NO_UPDATE_NOTIFIER", "").strip():
        return False
    if argv and any(arg in _SUPPRESS_FLAGS for arg in argv):
        return False
    return bool(sys.stderr.isatty())


def xdg_cache_dir(app: str) -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME", "").strip()
    if xdg:
        return Path(xdg) / app
    system = platform.system().lower()
    if system == "windows":
        temp = os.environ.get("TEMP", "").strip()
        if temp:
            return Path(temp) / app
    elif system == "darwin":
        return Path.home() / "Library" / "Caches" / app
    return Path.home() / ".cache" / app


def parse_semver(version_str: str) -> tuple[int, ...]:
    clean = version_str.strip().lstrip("v").split("+")[0].split("-")[0]
    parts: list[int] = []
    for p in clean.split("."):
        if p.isdigit():
            parts.append(int(p))
        else:
            break
    return tuple(parts)


def is_newer_version(latest: str, current: str) -> bool:
    if not latest.strip() or not current.strip():
        return False
    return parse_semver(latest) > parse_semver(current)


def maybe_notify_update(
    app: str,
    current_version: str,
    github_repo: str,
    upgrade_hint: str = "",
    argv: list[str] | None = None,
    *,
    api_base: str = "https://api.github.com",
    force_tty: bool = False,
) -> None:
    if not force_tty and not can_notify_update(argv):
        return
    env_override = app.upper().replace("-", "_") + "_NO_UPDATE_CHECK"
    if os.environ.get(env_override, "").strip():
        return
    if not github_repo or not current_version:
        return

    cache_file = xdg_cache_dir(app) / "update-check.json"
    now = int(time.time())
    latest = ""
    try:
        if cache_file.is_file():
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if now - int(cached.get("checked_at", 0)) <= UPDATE_CACHE_TTL_SECONDS:
                latest = str(cached.get("latest_version", "")).strip()
    except Exception:
        latest = ""

    if not latest:
        base = api_base.rstrip("/")
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "agent-cli-update-check"}
        for url, is_array in (
            (f"{base}/repos/{github_repo}/releases/latest", False),
            (f"{base}/repos/{github_repo}/tags?per_page=1", True),
        ):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    if resp.status != 200:
                        continue
                    data = json.loads(resp.read().decode("utf-8"))
                    if not is_array and isinstance(data, dict):
                        latest = str(data.get("tag_name", "")).strip()
                    elif is_array and isinstance(data, list) and data:
                        latest = str(data[0].get("name", "")).strip()
                    if latest:
                        break
            except Exception:
                continue
        if latest:
            try:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps({"checked_at": now, "latest_version": latest}), encoding="utf-8")
            except Exception:
                pass

    if latest and is_newer_version(latest, current_version):
        hint = upgrade_hint or f"Run 'uv tool upgrade {app}' to update."
        print(f"[update] {app} {latest} available (current: {current_version}). {hint}", file=sys.stderr)
