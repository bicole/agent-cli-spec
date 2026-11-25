---
name: help-agent
description: Implement and validate --help-agent (-ha) and agent-cli-spec capability profiles in any repository.
---

# `agent-cli-spec` & `--help-agent` (`-ha`) Skill

1. Declare compliance in `cli-spec.json` (`profile: "full@1.0.0"` or `custom` with versioned `modules`).
2. Implement `-ha` / `--help-agent` returning plain UTF-8 text (≤ 500 chars) with `synopsis:`, `exit_codes:`, and flag parity with `-h` / `--help`.
3. Validate with `agent-cli-validate --manifest cli-spec.json --json`.
