// gbrg-containment — governed containment / blast-radius service (Go, stdlib-only).
//
// Front door for the GBRG sever/residual read behind the cockpit's Containment
// surface. It computes residual reachability over a topology using the SAME
// semantics as the authoritative Rust engine (gbrg-core::containment in
// sociosphere) and returns a ContainmentProofArtifact — a no-op sever is
// downgraded to epistemicLevel=speculative, never presented as clean containment.
//
// This Go computation is PINNED to the authoritative Rust engine by a conformance
// test (main_test.go): shared topologies in testdata/topologies are severed here
// and compared field-for-field against golden artifacts the Rust `gbrg-containment`
// CLI produced (testdata/golden). If the two ever disagree, the test fails — so the
// Go front-door cannot silently drift from the engine that owns the algorithm.
//
// Endpoints (bind 0.0.0.0:$PORT, default 8080):
//
//	GET /healthz                            — liveness/readiness (chart probe path)
//	GET /containment?scope=full|selective   — sever the demo foothold, return the artifact
//
// Topology is fixture-backed at the HTTP surface; the topology is now a first-class
// parameter (parseTopology), which is what an over-the-wire live graph feeds.
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"sort"
)

type edge struct{ from, to, label string }

// topology is the graph a sever is computed over. It is a parameter now, not a
// package global, so the same engine serves the demo fixture, the conformance
// vectors, and (later) a live graph.
type topology struct {
	source     string
	edges      []edge
	allow      map[string]bool // allow-listed terminal nodes (EDR/EPP + exclusions)
	keepLabels map[string]bool // labels kept traversable under selective scope
}

// demoTopo: a compromised foothold, an SMB chain to a high-value DC + file server,
// an RDP path, and the allow-listed EDR channel.
var demoTopo = topology{
	source:     "vvv-648e9d56f1a",
	allow:      map[string]bool{"edr-epp": true},
	keepLabels: map[string]bool{"RDP": true, "EDR": true},
	edges: []edge{
		{"vvv-648e9d56f1a", "wks-2970", "SMB"},
		{"wks-2970", "dc-01", "SMB"},
		{"dc-01", "file-srv", "SMB"},
		{"vvv-648e9d56f1a", "wks-0d06", "RDP"},
		{"vvv-648e9d56f1a", "edr-epp", "EDR"},
	},
}

// topoInput is the on-the-wire topology (the same JSON the Rust CLI reads).
type topoInput struct {
	Source     string   `json:"source"`
	Scope      string   `json:"scope"`
	KeepLabels []string `json:"keep_labels"`
	Allow      []string `json:"allow"`
	Edges      []struct {
		From  string `json:"from"`
		To    string `json:"to"`
		Label string `json:"label"`
	} `json:"edges"`
}

// parseTopology parses the shared topology JSON into a topology + its scope.
func parseTopology(b []byte) (topology, string, error) {
	var in topoInput
	if err := json.Unmarshal(b, &in); err != nil {
		return topology{}, "", err
	}
	t := topology{source: in.Source, allow: map[string]bool{}, keepLabels: map[string]bool{}}
	for _, s := range in.Allow {
		t.allow[s] = true
	}
	for _, l := range in.KeepLabels {
		t.keepLabels[l] = true
	}
	for _, e := range in.Edges {
		t.edges = append(t.edges, edge{e.From, e.To, e.Label})
	}
	scope := in.Scope
	if scope != "selective" {
		scope = "full"
	}
	return t, scope, nil
}

func (t topology) outEdges(n string) []edge {
	var out []edge
	for _, e := range t.edges {
		if e.from == n {
			out = append(out, e)
		}
	}
	return out
}

func (t topology) reachable(from string) []string {
	seen := map[string]bool{from: true}
	var out []string
	q := []string{from}
	for len(q) > 0 {
		d := q[0]
		q = q[1:]
		for _, e := range t.outEdges(d) {
			if !seen[e.to] {
				seen[e.to] = true
				out = append(out, e.to)
				q = append(q, e.to)
			}
		}
	}
	sort.Strings(out)
	return out
}

// severResidual mirrors gbrg-core::containment::sever_residual: cut nodes keep no
// traversable edge under "full" (except allow-listed terminals) or only kept-label
// edges under "selective".
func (t topology) severResidual(scope string) (baseline, residual, contained []string) {
	baseline = t.reachable(t.source)
	cut := map[string]bool{t.source: true}
	seen := map[string]bool{t.source: true}
	q := []string{t.source}
	for len(q) > 0 {
		d := q[0]
		q = q[1:]
		out := t.outEdges(d)
		if cut[d] {
			for _, e := range out { // allow-listed neighbours are terminal-reachable
				if t.allow[e.to] && !seen[e.to] {
					seen[e.to] = true
					residual = append(residual, e.to)
				}
			}
		}
		for _, e := range out {
			// Selective keeps kept-label edges, but never expands THROUGH an allow-listed
			// endpoint (it is terminal — recorded above, never a pivot).
			keep := !cut[d] || (scope == "selective" && t.keepLabels[e.label] && !t.allow[e.to])
			if keep && !seen[e.to] {
				seen[e.to] = true
				residual = append(residual, e.to)
				q = append(q, e.to)
			}
		}
	}
	sort.Strings(residual)
	resSet := map[string]bool{}
	for _, r := range residual {
		resSet[r] = true
	}
	for _, b := range baseline {
		if !resSet[b] {
			contained = append(contained, b)
		}
	}
	sort.Strings(contained)
	return
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}

func containmentArtifact(t topology, scope string) map[string]any {
	if scope != "selective" {
		scope = "full"
	}
	baseline, residual, contained := t.severResidual(scope)
	level, status := "empirical", "PROVED"
	if len(contained) == 0 { // no-op sever is never a clean containment
		level, status = "speculative", "INCONCLUSIVE"
	}
	if residual == nil {
		residual = []string{}
	}
	return map[string]any{
		"schemaVersion":          "0.1.0",
		"proofId":                "proof-gbrg-containment-" + t.source,
		"claimType":              "scope_bound",
		"statement":              "containment of " + t.source + " (" + scope + " scope)",
		"epistemicLevel":         level,
		"status":                 status,
		"source":                 t.source,
		"severedScope":           scope,
		"baselineReachableCount": len(baseline),
		"residualReachableCount": len(residual),
		"containedCount":         len(contained),
		"residualReachable":      residual,
		"derivation":             "observed over the topology; residual mirrors gbrg-core sever_residual",
		"declaredBy":             "agent-registry://gbrg-containment",
	}
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "service": "gbrg-containment"})
	})
	mux.HandleFunc("/containment", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, containmentArtifact(demoTopo, r.URL.Query().Get("scope")))
	})

	log.Printf("gbrg-containment serving on :%s (/healthz /containment)", port)
	if err := http.ListenAndServe("0.0.0.0:"+port, mux); err != nil {
		log.Fatal(err)
	}
}
