package clikit

import (
	"flag"
	"strings"
	"testing"
)

func TestRenderHelpAgentFromFlagSet(t *testing.T) {
	fs := flag.NewFlagSet("demo", flag.ContinueOnError)
	fs.Bool("json", false, "JSON output")
	fs.Bool("dry-run", false, "Dry run")

	out := RenderHelpAgent(HelpSpec{
		Name:        "demo",
		Version:     "1.0.0",
		Description: "Demo CLI",
		Synopsis:    "demo",
	}, fs)
	if !strings.Contains(out, "--json") || !strings.Contains(out, "--dry-run") {
		t.Fatalf("expected flags in output: %s", out)
	}
	if len(out) > 500 {
		t.Fatalf("expected <=500 chars, got %d", len(out))
	}
}

func TestIsNewerVersion(t *testing.T) {
	if !IsNewerVersion("v1.2.0", "1.1.0") {
		t.Fatal("expected v1.2.0 > 1.1.0")
	}
	if IsNewerVersion("1.0.0", "1.0.0") {
		t.Fatal("expected equal versions not newer")
	}
}
