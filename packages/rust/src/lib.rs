//! Zero-dependency Rust reference library for `agent-cli-spec`.

use std::env;
use std::io::IsTerminal;
use std::path::PathBuf;

pub const SPEC_VERSION: &str = "1.0.0";

pub struct HelpAgentSpec<'a> {
    pub name: &'a str,
    pub version: &'a str,
    pub description: &'a str,
    pub synopsis: &'a str,
    pub exit_codes: &'a str,
}

impl<'a> HelpAgentSpec<'a> {
    pub fn render(&self) -> String {
        let exits = if self.exit_codes.is_empty() {
            "0=ok | 1=error | 2=usage_error"
        } else {
            self.exit_codes
        };
        format!(
            "{} v{} — {}\nsynopsis: {}\nexit_codes: {}",
            self.name, self.version, self.description, self.synopsis, exits
        )
    }
}

pub fn is_ci() -> bool {
    for key in ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "TF_BUILD", "BUILDKITE", "CIRCLECI"] {
        if let Ok(v) = env::var(key) {
            let trimmed = v.trim();
            if !trimmed.is_empty() && !trimmed.eq_ignore_ascii_case("false") && trimmed != "0" {
                return true;
            }
        }
    }
    false
}

pub fn is_interactive_tty() -> bool {
    if is_ci() || env::var("TERM").map(|v| v.trim().eq_ignore_ascii_case("dumb")).unwrap_or(false) {
        return false;
    }
    std::io::stdin().is_terminal() && std::io::stdout().is_terminal()
}

pub fn can_notify_update(args: &[&str]) -> bool {
    if is_ci() || env::var("TERM").map(|v| v.trim().eq_ignore_ascii_case("dumb")).unwrap_or(false) {
        return false;
    }
    if env::var("NO_UPDATE_NOTIFIER").map(|v| !v.trim().is_empty()).unwrap_or(false) {
        return false;
    }
    for a in args {
        if matches!(*a, "--json" | "-ha" | "--help-agent" | "--version" | "-V" | "-h" | "--help") {
            return false;
        }
    }
    std::io::stderr().is_terminal()
}

pub fn xdg_cache_dir(app: &str) -> PathBuf {
    if let Ok(xdg) = env::var("XDG_CACHE_HOME") {
        if !xdg.trim().is_empty() {
            return PathBuf::from(xdg).join(app);
        }
    }
    #[cfg(target_os = "windows")]
    if let Ok(temp) = env::var("TEMP") {
        if !temp.trim().is_empty() {
            return PathBuf::from(temp).join(app);
        }
    }
    let home = env::var("HOME")
        .or_else(|_| env::var("USERPROFILE"))
        .unwrap_or_else(|_| ".".to_string());
    #[cfg(target_os = "macos")]
    return PathBuf::from(home).join("Library").join("Caches").join(app);
    #[cfg(not(target_os = "macos"))]
    PathBuf::from(home).join(".cache").join(app)
}

pub fn parse_semver(v: &str) -> (u64, u64, u64) {
    let clean = v.trim().trim_start_matches('v');
    let base = clean.split(['+', '-']).next().unwrap_or("");
    let mut parts = base.split('.').filter_map(|p| p.parse::<u64>().ok());
    (
        parts.next().unwrap_or(0),
        parts.next().unwrap_or(0),
        parts.next().unwrap_or(0),
    )
}

pub fn is_newer_version(latest: &str, current: &str) -> bool {
    if latest.trim().is_empty() || current.trim().is_empty() {
        return false;
    }
    parse_semver(latest) > parse_semver(current)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_help_agent_render() {
        let spec = HelpAgentSpec {
            name: "demo",
            version: "1.0.0",
            description: "Demo tool",
            synopsis: "demo [-ha] [--json]",
            exit_codes: "",
        };
        let out = spec.render();
        assert!(out.len() <= 500);
        assert!(out.contains("demo v1.0.0"));
    }

    #[test]
    fn test_semver_compare() {
        assert!(is_newer_version("v1.2.0", "1.1.9"));
        assert!(!is_newer_version("1.0.0", "1.0.0"));
    }

    #[test]
    fn test_suppress_flags() {
        assert!(!can_notify_update(&["--json"]));
        assert!(!can_notify_update(&["-ha"]));
    }
}
