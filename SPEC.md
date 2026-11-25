# `agent-cli-spec` Normative Specification (`v1.0.0`)

This specification merges and extends `help-agent-spec` into a modular, versioned standard for CLI tools consumed by both humans and AI coding agents.

---

## 1. Profile & Capability Declaration

A CLI tool MAY adopt the full spec (`full@1.0.0`) or opt into specific versioned modules.

### 1.1 `cli-spec.json` (or `.agents/cli-spec.json`)
Tools opting into a subset or full profile SHOULD place a `cli-spec.json` file at repository root (or `.agents/cli-spec.json`), conforming to `schema/cli-spec.schema.json`:
```json
{
  "spec_version": "1.0.0",
  "profile": "custom",
  "binary": "my-tool",
  "modules": {
    "core": "1.0.0",
    "tty-tui-guard": "1.0.0"
  },
  "json_probe_args": ["list", "--json"],
  "tui_probe_args": ["tui"]
}
```
Named profiles:
- `core@1.0.0`: `["core@1.0.0"]`
- `agent-friendly@1.0.0`: `["core@1.0.0", "json-output@1.0.0", "tty-tui-guard@1.0.0"]`
- `full@1.0.0`: `["core@1.0.0", "json-output@1.0.0", "xdg-dirs@1.0.0", "tty-update-check@1.0.0", "tty-tui-guard@1.0.0", "path-install@1.0.0"]`

Tools distributed as standalone binaries MAY also expose `--cli-spec` printing the same JSON object to `stdout` and exiting `0`.

---

## 2. Capability Modules

### 2.1 `core@1.0.0` (Merged `help-agent-spec`)
- **`-ha` / `--help-agent`**:
  - MUST accept both `-ha` and `--help-agent` and exit `0`.
  - MUST emit plain UTF-8 text (no ANSI escape sequences) with **≤ 500 characters** (and < 500 tokens).
  - Grammar:
    ```text
    <name> v<semver> — <1-line description>
    synopsis: <command> [-ha|--help-agent] [-h|--help] [--version] [--json] <subcommands/args>
    commands:
      <cmd>: <compact usage>
    exit_codes: 0=ok | 1=error | 2=usage_error | 6=empty_or_skipped
    ```
  - **Flag Parity**: Every CLI flag documented in `-h`/`--help` MUST also be represented in `-ha`/`--help-agent` (and vice versa).
- **`-h` / `--help`**: MUST print human-readable help and exit `0`.
- **`--version` / `-V`**: MUST print `<name> v<semver>` (or `<name> <semver>`) and exit `0`.
- **Exit Codes**: `0`=OK, `1`=Error/Conflict, `2`=Usage/Environment Error, `6`=Empty/Idempotent skip.

### 2.2 `json-output@1.0.0`
- Structured query/list/status/validate commands MUST support `--json`.
- When `--json` is active, `stdout` MUST contain pure, valid JSON only; diagnostics, logs, and update notices MUST go to `stderr`.

### 2.3 `xdg-dirs@1.0.0`
- Resolve config, data, state, and cache directories cross-platform without hardcoded backslashes:
  1. Explicit flag / tool env var
  2. `$XDG_CONFIG_HOME/agent-stack/config.yml` (where applicable)
  3. `$XDG_*_HOME/<app>` -> OS-native fallback (`%APPDATA%`/`%LOCALAPPDATA%`/`%TEMP%` on Windows, `~/Library/...` on macOS, `~/.config`/`~/.local/...`/`~/.cache` on Linux).

### 2.4 `tty-update-check@1.0.0`
- Check for updates ONLY when `stderr` is an interactive TTY, and `CI`, `NO_UPDATE_NOTIFIER`, `<APP>_NO_UPDATE_CHECK`, `TERM=dumb`, `--json`, `-ha`, and `--version` are not active.
- Cache result in `$XDG_CACHE_HOME/<app>/update-check.json` with a 24h TTL (`86400s`).
- Use short timeouts (≤ 1.5s–2.0s), fail silently on errors, and print notices to `stderr` only.

### 2.5 `tty-tui-guard@1.0.0`
- TUI commands and interactive pickers MUST verify `isatty(stdin) && isatty(stdout)` (and `!CI`, `TERM != dumb`, no `--no-interactive`/`--non-interactive`).
- Explicit TUI subcommands invoked in non-TTY/agent contexts MUST fail fast with exit code `2` and print actionable non-interactive CLI alternatives to `stderr`.

### 2.6 `path-install@1.0.0`
- User-facing CLIs MUST be installable into `~/.local/bin` (via `uv tool install`, `go build`, or copied binary/shim), never by adding a repository directory to `PATH`.

---

## 3. Auto-Generating `-ha` (Doxygen-Style Contract)
To prevent drift between `-h` and `-ha`:
- **Parser Introspection**: Reference libraries (`agent-clikit` for Python `argparse`, `clikit` for Go `flag.FlagSet`) introspect the live parser tree to render `-ha` automatically from registered flags/subcommands.
- **Structured Annotations**: Custom/shell CLIs SHOULD annotate flags with `# @ha-flag <flag> <desc>` / `# @ha-cmd <cmd> <desc>` or generate `-h` and `-ha` from a single spec struct.
