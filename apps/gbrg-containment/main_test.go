package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"
	"time"
)

func testClient() *http.Client { return &http.Client{Timeout: 2 * time.Second} }

// TestUsesEngineWhenAvailable: when GBRG_ENGINE_URL is set and healthy, the
// front-door returns the AUTHORITATIVE engine's artifact verbatim.
func TestUsesEngineWhenAvailable(t *testing.T) {
	var gotBody string
	engine := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		gotBody = string(b)
		_ = json.NewEncoder(w).Encode(map[string]any{"epistemicLevel": "empirical", "source": "from-engine", "containedCount": 99})
	}))
	defer engine.Close()

	got := resolveArtifact(testClient(), engine.URL, demoTopo, "full")
	if got["source"] != "from-engine" || got["containedCount"].(float64) != 99 {
		t.Fatalf("did not return the engine's artifact: %v", got)
	}
	// The front-door must send the topology in the shared wire format.
	if !strings.Contains(gotBody, "vvv-648e9d56f1a") || !strings.Contains(gotBody, `"scope":"full"`) {
		t.Fatalf("engine did not receive the topology JSON: %s", gotBody)
	}
}

// TestFallsBackWhenEngineDown: an unreachable engine must not break the service —
// it falls back to the local (conformance-pinned) computation.
func TestFallsBackWhenEngineDown(t *testing.T) {
	got := resolveArtifact(testClient(), "http://127.0.0.1:0", demoTopo, "full")
	if got["epistemicLevel"] != "empirical" || got["source"] != "vvv-648e9d56f1a" {
		t.Fatalf("fallback did not produce the local artifact: %v", got)
	}
}

// TestFallsBackOnEngineError: a 5xx from the engine also falls back.
func TestFallsBackOnEngineError(t *testing.T) {
	engine := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer engine.Close()
	got := resolveArtifact(testClient(), engine.URL, demoTopo, "full")
	if got["source"] != "vvv-648e9d56f1a" {
		t.Fatalf("5xx should fall back to local: %v", got)
	}
}

// semantic is the subset of a ContainmentProofArtifact that MUST agree between the
// Go front-door and the authoritative Rust engine. Non-semantic prose (proofId,
// statement, derivation, declaredBy) is allowed to differ; the containment RESULT
// is not.
type semantic struct {
	SeveredScope      string   `json:"severedScope"`
	Baseline          int      `json:"baselineReachableCount"`
	Residual          int      `json:"residualReachableCount"`
	Contained         int      `json:"containedCount"`
	ResidualReachable []string `json:"residualReachable"`
	EpistemicLevel    string   `json:"epistemicLevel"`
	Status            string   `json:"status"`
}

func normalize(s *semantic) {
	sort.Strings(s.ResidualReachable)
	if s.ResidualReachable == nil {
		s.ResidualReachable = []string{}
	}
}

func toSemantic(t *testing.T, v any) semantic {
	t.Helper()
	b, err := json.Marshal(v)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	var s semantic
	if err := json.Unmarshal(b, &s); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	normalize(&s)
	return s
}

// TestConformanceWithRustEngine pins the Go computation to the authoritative Rust
// engine: for every shared topology, the Go artifact's containment result must
// equal the golden artifact the Rust `gbrg-containment` CLI produced. Regenerate
// golden with: for t in net-full net-selective noop; do
//
//	gbrg-containment testdata/topologies/$t.json > testdata/golden/$t.json; done
func TestConformanceWithRustEngine(t *testing.T) {
	topos, err := filepath.Glob("testdata/topologies/*.json")
	if err != nil || len(topos) == 0 {
		t.Fatalf("no topology fixtures found: %v", err)
	}
	for _, tp := range topos {
		name := filepath.Base(tp)
		t.Run(name, func(t *testing.T) {
			raw, err := os.ReadFile(tp)
			if err != nil {
				t.Fatal(err)
			}
			topo, scope, err := parseTopology(raw)
			if err != nil {
				t.Fatalf("parseTopology: %v", err)
			}
			got := toSemantic(t, containmentArtifact(topo, scope))

			goldenRaw, err := os.ReadFile(filepath.Join("testdata/golden", name))
			if err != nil {
				t.Fatalf("missing golden for %s: %v", name, err)
			}
			var want semantic
			if err := json.Unmarshal(goldenRaw, &want); err != nil {
				t.Fatalf("golden unmarshal: %v", err)
			}
			normalize(&want)

			if !reflect.DeepEqual(got, want) {
				t.Fatalf("Go DRIFTED from the authoritative Rust engine for %s:\n  go   = %+v\n  rust = %+v", name, got, want)
			}
		})
	}
}

// TestDemoEndpointStillWorks guards the fixture path the cockpit reads.
func TestDemoEndpointStillWorks(t *testing.T) {
	full := toSemantic(t, containmentArtifact(demoTopo, "full"))
	if full.EpistemicLevel != "empirical" || full.Contained == 0 {
		t.Fatalf("demo full sever should contain something: %+v", full)
	}
	noop := toSemantic(t, containmentArtifact(topology{source: "x", allow: map[string]bool{}, keepLabels: map[string]bool{}}, "full"))
	if noop.EpistemicLevel != "speculative" {
		t.Fatalf("no-op sever must be speculative: %+v", noop)
	}
}
