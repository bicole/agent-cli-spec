package clikit

import (
	"encoding/json"
	"flag"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"time"
)

const (
	SpecVersion    = "1.0.0"
	updateCacheTTL = 24 * time.Hour
)

// HelpSpec describes a CLI for automatic -ha/--help-agent rendering.
type HelpSpec struct {
	Name        string
	Version     string
	Description string
	Synopsis    string
	Commands    [][2]string
	ExitCodes   string
}

// RenderHelpAgent formats a compact, plain UTF-8 -ha synopsis and optionally appends
// flags discovered from a Go *flag.FlagSet.
func RenderHelpAgent(spec HelpSpec, fs *flag.FlagSet) string {
	var flags []string
	if fs != nil {
		fs.VisitAll(func(f *flag.Flag) {
			if len(f.Name) == 1 {
				flags = append(flags, "-"+f.Name)
			} else {
				flags = append(flags, "--"+f.Name)
			}
		})
		sort.Strings(flags)
	}
	var b strings.Builder
	fmt.Fprintf(&b, "%s v%s — %s\n", spec.Name, spec.Version, spec.Description)
	syn := spec.Synopsis
	if len(flags) > 0 {
		syn += " [" + strings.Join(flags, " ") + "]"
	}
	fmt.Fprintf(&b, "synopsis: %s\n", syn)
	if len(spec.Commands) > 0 {
		b.WriteString("commands:\n")
		for _, c := range spec.Commands {
			fmt.Fprintf(&b, "  %s: %s\n", c[0], c[1])
		}
	}
	exits := spec.ExitCodes
	if exits == "" {
		exits = "0=ok | 1=error | 2=usage_error"
	}
	fmt.Fprintf(&b, "exit_codes: %s", exits)
	return b.String()
}

// IsTerminal reports whether f is connected to an interactive character device.
func IsTerminal(f *os.File) bool {
	if f == nil {
		return false
	}
	info, err := f.Stat()
	if err != nil {
		return false
	}
	return (info.Mode() & os.ModeCharDevice) != 0
}

// IsCI reports whether the current process is running in a CI environment.
func IsCI() bool {
	for _, key := range []string{"CI", "GITHUB_ACTIONS", "GITLAB_CI", "TF_BUILD", "BUILDKITE", "CIRCLECI"} {
		if v := strings.TrimSpace(os.Getenv(key)); v != "" && !strings.EqualFold(v, "false") && v != "0" {
			return true
		}
	}
	return false
}

// IsInteractiveTTY reports whether stdin and stdout are both interactive TTYs.
func IsInteractiveTTY() bool {
	if IsCI() || strings.EqualFold(strings.TrimSpace(os.Getenv("TERM")), "dumb") {
		return false
	}
	return IsTerminal(os.Stdin) && IsTerminal(os.Stdout)
}

func hasSuppressFlag(args []string) bool {
	for _, a := range args {
		switch a {
		case "--json", "-ha", "--help-agent", "--version", "-V", "-h", "--help":
			return true
		}
	}
	return false
}

// CanNotifyUpdate reports whether update checks/notices are permitted on stderr.
func CanNotifyUpdate(args []string) bool {
	if IsCI() || strings.EqualFold(strings.TrimSpace(os.Getenv("TERM")), "dumb") {
		return false
	}
	if strings.TrimSpace(os.Getenv("NO_UPDATE_NOTIFIER")) != "" {
		return false
	}
	if hasSuppressFlag(args) {
		return false
	}
	return IsTerminal(os.Stderr)
}

func homeDir() string {
	h, err := os.UserHomeDir()
	if err != nil || strings.TrimSpace(h) == "" {
		return "."
	}
	return h
}

func XDGConfigDir(app string) string {
	if v := strings.TrimSpace(os.Getenv("XDG_CONFIG_HOME")); v != "" {
		return filepath.Join(v, app)
	}
	switch runtime.GOOS {
	case "windows":
		if v := strings.TrimSpace(os.Getenv("APPDATA")); v != "" {
			return filepath.Join(v, app)
		}
	case "darwin":
		return filepath.Join(homeDir(), "Library", "Application Support", app)
	}
	return filepath.Join(homeDir(), ".config", app)
}

func XDGDataDir(app string) string {
	if v := strings.TrimSpace(os.Getenv("XDG_DATA_HOME")); v != "" {
		return filepath.Join(v, app)
	}
	switch runtime.GOOS {
	case "windows":
		if v := strings.TrimSpace(os.Getenv("LOCALAPPDATA")); v != "" {
			return filepath.Join(v, app)
		}
	case "darwin":
		return filepath.Join(homeDir(), "Library", "Application Support", app)
	}
	return filepath.Join(homeDir(), ".local", "share", app)
}

func XDGStateDir(app string) string {
	if v := strings.TrimSpace(os.Getenv("XDG_STATE_HOME")); v != "" {
		return filepath.Join(v, app)
	}
	if runtime.GOOS == "windows" {
		if v := strings.TrimSpace(os.Getenv("LOCALAPPDATA")); v != "" {
			return filepath.Join(v, app, "state")
		}
	}
	return filepath.Join(homeDir(), ".local", "state", app)
}

func XDGCacheDir(app string) string {
	if v := strings.TrimSpace(os.Getenv("XDG_CACHE_HOME")); v != "" {
		return filepath.Join(v, app)
	}
	switch runtime.GOOS {
	case "windows":
		if v := strings.TrimSpace(os.Getenv("TEMP")); v != "" {
			return filepath.Join(v, app)
		}
	case "darwin":
		return filepath.Join(homeDir(), "Library", "Caches", app)
	}
	return filepath.Join(homeDir(), ".cache", app)
}

func ParseSemver(v string) [3]int {
	clean := strings.TrimSpace(strings.TrimPrefix(v, "v"))
	if idx := strings.IndexAny(clean, "+-"); idx >= 0 {
		clean = clean[:idx]
	}
	parts := strings.Split(clean, ".")
	var out [3]int
	for i := 0; i < len(parts) && i < 3; i++ {
		n, err := strconv.Atoi(parts[i])
		if err != nil {
			break
		}
		out[i] = n
	}
	return out
}

func IsNewerVersion(latest, current string) bool {
	if strings.TrimSpace(latest) == "" || strings.TrimSpace(current) == "" {
		return false
	}
	l := ParseSemver(latest)
	c := ParseSemver(current)
	for i := 0; i < 3; i++ {
		if l[i] > c[i] {
			return true
		}
		if l[i] < c[i] {
			return false
		}
	}
	return false
}

type updateCacheEntry struct {
	CheckedAt     int64  `json:"checked_at"`
	LatestVersion string `json:"latest_version"`
}

type UpdateOptions struct {
	App            string
	CurrentVersion string
	GitHubRepo     string
	UpgradeHint    string
	Args           []string
	APIBaseURL     string
	ForceTTY       bool
}

func MaybeNotifyUpdate(opts UpdateOptions) {
	if !opts.ForceTTY && !CanNotifyUpdate(opts.Args) {
		return
	}
	envOverride := strings.ToUpper(strings.ReplaceAll(opts.App, "-", "_")) + "_NO_UPDATE_CHECK"
	if strings.TrimSpace(os.Getenv(envOverride)) != "" {
		return
	}
	if opts.GitHubRepo == "" || opts.CurrentVersion == "" {
		return
	}
	cacheFile := filepath.Join(XDGCacheDir(opts.App), "update-check.json")
	latest := readFreshCache(cacheFile, time.Now().Unix())
	if latest == "" {
		base := opts.APIBaseURL
		if base == "" {
			base = "https://api.github.com"
		}
		latest = fetchLatestGitHubVersion(base, opts.GitHubRepo)
		if latest != "" {
			writeCache(cacheFile, updateCacheEntry{CheckedAt: time.Now().Unix(), LatestVersion: latest})
		}
	}
	if IsNewerVersion(latest, opts.CurrentVersion) {
		hint := opts.UpgradeHint
		if hint == "" {
			hint = fmt.Sprintf("Update %s via your package manager or repo installer.", opts.App)
		}
		fmt.Fprintf(os.Stderr, "[update] %s %s available (current: %s). %s\n", opts.App, latest, opts.CurrentVersion, hint)
	}
}

func readFreshCache(path string, nowUnix int64) string {
	raw, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	var entry updateCacheEntry
	if err := json.Unmarshal(raw, &entry); err != nil {
		return ""
	}
	if nowUnix-entry.CheckedAt > int64(updateCacheTTL.Seconds()) {
		return ""
	}
	return entry.LatestVersion
}

func writeCache(path string, entry updateCacheEntry) {
	_ = os.MkdirAll(filepath.Dir(path), 0755)
	raw, err := json.Marshal(entry)
	if err != nil {
		return
	}
	_ = os.WriteFile(path, raw, 0644)
}

func fetchLatestGitHubVersion(baseURL, repo string) string {
	client := &http.Client{Timeout: 1500 * time.Millisecond}
	if tag := fetchTagFromURL(client, fmt.Sprintf("%s/repos/%s/releases/latest", strings.TrimRight(baseURL, "/"), repo), false); tag != "" {
		return tag
	}
	return fetchTagFromURL(client, fmt.Sprintf("%s/repos/%s/tags?per_page=1", strings.TrimRight(baseURL, "/"), repo), true)
}

func fetchTagFromURL(client *http.Client, url string, isArray bool) string {
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return ""
	}
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("User-Agent", "agent-cli-update-check")
	resp, err := client.Do(req)
	if err != nil {
		return ""
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return ""
	}
	if !isArray {
		var rel struct {
			TagName string `json:"tag_name"`
		}
		if err := json.NewDecoder(resp.Body).Decode(&rel); err == nil {
			return strings.TrimSpace(rel.TagName)
		}
		return ""
	}
	var tags []struct {
		Name string `json:"name"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&tags); err == nil && len(tags) > 0 {
		return strings.TrimSpace(tags[0].Name)
	}
	return ""
}
