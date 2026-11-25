# `agent-cli-spec`

A modular, versioned specification, JSON Schema, multi-language reference toolkit (`clikit` for Go, Python, and Rust), and conformance validator (`agent-cli-validate`) for building human- and AI-agent-friendly CLI tools.

Merges and supersedes `help-agent-spec` (`-ha` / `--help-agent`).

---

## 1. Capability Profiles & Versioned Modules

Tools declare compliance either with a named profile (e.g. `full@1.0.0`, `agent-friendly@1.0.0`, `core@1.0.0`) or by opting into individual versioned capability modules via `cli-spec.json` (or `.agents/cli-spec.json`):

| Module | Version | Summary | Validator Check |
| :--- | :--- | :--- | :--- |
| `core` | `1.0.0` | `-ha`/`--help-agent` (plain UTF-8, ≤500 chars, flag parity with `-h`), `-h`/`--help`, `--version`, exit codes `0,1,2,6` | Automated (`agent-cli-validate`) |
| `json-output` | `1.0.0` | `--json` emits pure JSON to `stdout`; logs/notices go to `stderr` only | Automated (`json_probe_args`) |
| `xdg-dirs` | `1.0.0` | Cross-platform XDG + `agent-stack` config/data/state/cache dirs | Library / unit test |
| `tty-update-check` | `1.0.0` | 24h-cached update check, `stderr`-only in interactive TTYs | Library / unit test |
| `tty-tui-guard` | `1.0.0` | Interactive TTY precondition (`stdin` + `stdout`); fail-fast exit `2` in non-TTY/agent runs | Automated (`tui_probe_args`) |
| `path-install` | `1.0.0` | Installable into `~/.local/bin` (never repo path in `PATH`) | Packaging / install check |

---

## 2. Quick Start

### Declare a Non-Full Profile (`cli-spec.json`)
```json
{
  "spec_version": "1.0.0",
  "profile": "custom",
  "binary": "my-cli",
  "modules": {
    "core": "1.0.0",
    "json-output": "1.0.0",
    "tty-tui-guard": "1.0.0"
  },
  "tui_probe_args": ["tui"]
}
```

### Run the Validator
```sh
uv tool install --force --editable .
agent-cli-validate --cmd "agent-conv" --profile full@1.0.0 --tui-args tui --json-args "adapters --json"
```

---

## 3. Repository Layout
- `SPEC.md` — Normative specification (merged `help-agent-spec` + capability modules)
- `spec/spec.json` — Machine-readable versioned profile & module definitions
- `schema/cli-spec.schema.json` — JSON Schema Draft 2020-12 for `cli-spec.json`
- `packages/go/clikit/` — Zero-dependency Go reference package
- `packages/python/` — Zero-dependency Python (`agent-clikit`) reference package with `argparse` `-ha` generator
- `packages/rust/` — Zero-dependency Rust (`agent-clikit`) reference crate
- `src/agent_cli_spec/` — `agent-cli-validate` conformance validator CLI
- `skills/help-agent/SKILL.md` — Agent skill for `-ha` / `agent-cli-spec`
- `llms.txt` — Terse summary for AI coding agents
