// gbrg-containment — governed containment / blast-radius service (Go, stdlib-only).
//
// Front door for the GBRG sever/residual read behind the cockpit's Containment
// surface. It computes residual reachability over a topology using the SAME
// semantics as the authoritative Rust engine (gbrg-core::containment in
// sociosphere) and returns a ContainmentProofArtifact — a no-op sever is
// downgraded to epistemicLevel=speculative, never presented as clean containment.
//
// Endpoints (bind 0.0.0.0:$PORT, default 8080):
//   GET /healthz                      — liveness/readiness (chart probe path)
//   GET /containment?scope=full|selective  — sever the demo foothold, return the artifact
//
// Topology is fixture-backed here; wiring to the Rust engine over a live graph is
// the follow-on (the Rust crate is the source of truth for the algorithm).
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"sort"
)

type edge struct{ from, to, label string }

// demo topology: a compromised foothold, an SMB chain to a high-value DC + file
// server, an RDP path, and the allow-listed EDR channel.
var (
	source   = "vvv-648e9d56f1a"
	allow    = map[string]bool{"edr-epp": true}
	keepSel  = map[string]bool{"RDP": true, "EDR": true}
	edges    = []edge{
		{"vvv-648e9d56f1a", "wks-2970", "SMB"},
		{"wks-2970", "dc-01", "SMB"},
		{"dc-01", "file-srv", "SMB"},
		{"vvv-648e9d56f1a", "wks-0d06", "RDP"},
		{"vvv-648e9d56f1a", "edr-epp", "EDR"},
	}
)

func outEdges(n string) []edge {
	var out []edge
	for _, e := range edges {
		if e.from == n {
			out = append(out, e)
		}
	}
	return out
}

func reachable(from string) []string {
	seen := map[string]bool{from: true}
	var out []string
	q := []string{from}
	for len(q) > 0 {
		d := q[0]
		q = q[1:]
		for _, e := range outEdges(d) {
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
func severResidual(scope string) (baseline, residual, contained []string) {
	baseline = reachable(source)
	cut := map[string]bool{source: true}
	seen := map[string]bool{source: true}
	q := []string{source}
	for len(q) > 0 {
		d := q[0]
		q = q[1:]
		out := outEdges(d)
		if cut[d] {
			for _, e := range out { // allow-listed neighbours are terminal-reachable
				if allow[e.to] && !seen[e.to] {
					seen[e.to] = true
					residual = append(residual, e.to)
				}
			}
		}
		for _, e := range out {
			keep := !cut[d] || (scope == "selective" && keepSel[e.label])
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

func containmentArtifact(scope string) map[string]any {
	if scope != "selective" {
		scope = "full"
	}
	baseline, residual, contained := severResidual(scope)
	level, status := "empirical", "PROVED"
	if len(contained) == 0 { // no-op sever is never a clean containment
		level, status = "speculative", "INCONCLUSIVE"
	}
	if residual == nil {
		residual = []string{}
	}
	return map[string]any{
		"schemaVersion":          "0.1.0",
		"proofId":                "proof-gbrg-containment-" + source,
		"claimType":              "scope_bound",
		"statement":              "containment of " + source + " (" + scope + " scope)",
		"epistemicLevel":         level,
		"status":                 status,
		"source":                 source,
		"severedScope":           scope,
		"baselineReachableCount": len(baseline),
		"residualReachableCount": len(residual),
		"containedCount":         len(contained),
		"residualReachable":      residual,
		"derivation":             "observed over the fixture topology; residual mirrors gbrg-core sever_residual",
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
		writeJSON(w, http.StatusOK, containmentArtifact(r.URL.Query().Get("scope")))
	})

	log.Printf("gbrg-containment serving on :%s (/healthz /containment)", port)
	if err := http.ListenAndServe("0.0.0.0:"+port, mux); err != nil {
		log.Fatal(err)
	}
}
