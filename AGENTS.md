# AGENTS.md (`agent-cli-spec`)

- Keep `SPEC.md`, `spec/spec.json`, `schema/cli-spec.schema.json`, and `packages/{go,python,rust}` synchronized whenever module contracts or versions change.
- All CLI reference packages MUST remain zero-external-dependency (stdlib only).
- Run `pytest`, `go test ./...`, and `cargo test` before committing changes.
