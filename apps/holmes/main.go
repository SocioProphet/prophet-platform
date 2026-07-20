package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// hellgraphBase is the canonical knowledge graph Holmes reasons over (the deduction engine's evidence
// store). Override with HOLMES_HELLGRAPH.
func hellgraphBase() string {
	if v := os.Getenv("HOLMES_HELLGRAPH"); v != "" {
		return v
	}
	return "http://127.0.0.1:8090"
}

var httpClient = &http.Client{Timeout: 12 * time.Second}

// searchGraph runs a real GraphRAG retrieval against HellGraph and returns the grounding + a count of
// evidence facts found. This is the sherlock-search engine, wired.
func searchGraph(query string) (map[string]any, int, error) {
	u := hellgraphBase() + "/api/graph/ground?q=" + url.QueryEscape(query) + "&hops=2"
	resp, err := httpClient.Get(u)
	if err != nil {
		return nil, 0, err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != 200 {
		return nil, 0, fmt.Errorf("hellgraph %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}
	var out map[string]any
	if err := json.Unmarshal(body, &out); err != nil {
		return nil, 0, err
	}
	return out, countEvidence(out), nil
}

// countEvidence tallies the retrieved facts/citations regardless of the exact grounding shape.
func countEvidence(g map[string]any) int {
	n := 0
	for _, k := range []string{"facts", "citations", "nodes", "grounding", "results", "edges", "seeds", "paths"} {
		if arr, ok := g[k].([]any); ok {
			n += len(arr)
		}
	}
	return n
}

var stopWords = map[string]bool{"the": true, "and": true, "for": true, "with": true, "that": true, "will": true,
	"are": true, "across": true, "about": true, "this": true, "from": true, "into": true, "total": true,
	"expected": true, "estimated": true, "covered": true, "providers": true}

// evidenceText flattens ONLY the retrieved-evidence fields (never "question"/"query"), so a claim
// can't be "verified" by its own echoed text.
func evidenceText(g map[string]any) string {
	var b strings.Builder
	for _, k := range []string{"facts", "citations", "nodes", "grounding", "results", "edges", "seeds", "paths"} {
		if v, ok := g[k]; ok {
			j, _ := json.Marshal(v)
			b.Write(j)
			b.WriteByte(' ')
		}
	}
	return strings.ReplaceAll(strings.ToLower(b.String()), "-", " ")
}

// wordSet tokenizes evidence text into a whole-word set (lowercase alphanumerics) to avoid
// substring false-positives ("real" matching inside another word).
func wordSet(s string) map[string]bool {
	set := map[string]bool{}
	for _, w := range strings.FieldsFunc(s, func(r rune) bool {
		return !((r >= 'a' && r <= 'z') || (r >= '0' && r <= '9'))
	}) {
		if len(w) >= 3 {
			set[w] = true
		}
	}
	return set
}

// contentWords keeps the salient (≥4-char, non-stopword) tokens of a claim.
func contentWords(s string) []string {
	out := []string{}
	for _, w := range strings.Fields(strings.ToLower(s)) {
		w = strings.Trim(w, ".,;:!?()$\"'—")
		if len(w) >= 4 && !stopWords[w] {
			out = append(out, w)
		}
	}
	return out
}

// verifyClaim retrieves grounding and requires the claim's OWN vocabulary to appear in the evidence —
// so an unrelated claim can't ride a default neighbourhood to a false "supported". This is the
// deduction engine: a verdict is only as good as term-grounded evidence.
func verifyClaim(claim string) map[string]any {
	g, n, err := searchGraph(claim)
	if err != nil {
		return map[string]any{"claim": claim, "verdict": "unreachable", "evidence_count": 0, "error": err.Error(), "evidenceId": stableID("verify:" + claim)}
	}
	evWords := wordSet(evidenceText(g)) // ONLY the retrieved evidence — never the echoed query
	words := contentWords(claim)
	hits := []string{}
	for _, w := range words {
		if evWords[w] { // whole-word, not substring
			hits = append(hits, w)
		}
	}
	ratio := 0.0
	if len(words) > 0 {
		ratio = float64(len(hits)) / float64(len(words))
	}
	verdict := "unverified"
	if len(hits) >= 2 && ratio >= 0.5 {
		verdict = "supported"
	} else if len(hits) >= 1 {
		verdict = "weakly-supported"
	}
	return map[string]any{"claim": claim, "verdict": verdict, "matched_terms": hits,
		"evidence_count": n, "evidenceId": stableID("verify:" + claim), "grounding": g}
}

var (
	version = "0.1.0-dev"
	commit  = "unknown"
	date    = "unknown"
)

type evidence struct {
	Tool      string         `json:"tool"`
	Version   string         `json:"version"`
	Commit    string         `json:"commit"`
	BuildDate string         `json:"buildDate"`
	Repo      string         `json:"repo"`
	Command   string         `json:"command"`
	Status    string         `json:"status"`
	Details   map[string]any `json:"details,omitempty"`
}

type analysisRecord struct {
	Tool        string   `json:"tool"`
	Version     string   `json:"version"`
	Status      string   `json:"status"`
	Path        string   `json:"path"`
	Bytes       int      `json:"bytes"`
	SHA256      string   `json:"sha256"`
	Lines       int      `json:"lines"`
	Words       int      `json:"words"`
	Components  []string `json:"components"`
	EvidenceRef string   `json:"evidenceRef"`
}

func usage() {
	fmt.Fprintf(os.Stderr, `holmes %s

Usage:
  holmes --version
  holmes doctor
  holmes self-test
  holmes emit-evidence
  holmes analyze <path>
  holmes search <query>
  holmes serve                 (HTTP: /search /verify /analyze /healthz)
  holmes graph <path>
  holmes govern <path>

`, version)
}

func main() {
	if len(os.Args) == 1 {
		usage()
		os.Exit(2)
	}
	if os.Args[1] == "--version" || os.Args[1] == "version" {
		fmt.Printf("holmes %s commit=%s date=%s\n", version, commit, date)
		return
	}

	switch os.Args[1] {
	case "doctor":
		runDoctor()
	case "self-test":
		runSelfTest()
	case "emit-evidence":
		runEvidence("emit-evidence", "ok", map[string]any{"surface": "language-intelligence", "mode": "local"})
	case "analyze":
		requireArgs(os.Args, 3)
		runAnalyze(os.Args[2])
	case "search":
		requireArgs(os.Args, 3)
		runSearch(strings.Join(os.Args[2:], " "))
	case "serve":
		runServe()
	case "graph":
		requireArgs(os.Args, 3)
		runGraph(os.Args[2])
	case "govern":
		requireArgs(os.Args, 3)
		runGovern(os.Args[2])
	default:
		usage()
		os.Exit(2)
	}
}

func requireArgs(args []string, n int) {
	if len(args) < n {
		usage()
		os.Exit(2)
	}
}

func runDoctor() {
	details := map[string]any{
		"components": []string{"sherlock-search", "221b", "mycroft-router", "moriarty-bench", "irene-shield", "the-canon", "deduction-engine"},
		"wired":      []string{},
		"pending":    []string{"sherlock-search", "221b", "mycroft-router", "moriarty-bench", "irene-shield", "the-canon", "deduction-engine"},
	}
	runEvidence("doctor", "not-yet-wired", details)
}

func runSelfTest() {
	if _, err := os.Stat("examples/holmes-surface.json"); err != nil {
		runEvidence("self-test", "failed", map[string]any{"error": err.Error()})
		os.Exit(1)
	}
	runEvidence("self-test", "ok", map[string]any{"example": "examples/holmes-surface.json"})
}

func runAnalyze(path string) {
	record, err := analyzeFile(path)
	if err != nil {
		printJSON(map[string]any{"status": "failed", "error": err.Error(), "path": path})
		os.Exit(1)
	}
	printJSON(record)
}

func runSearch(query string) {
	g, n, err := searchGraph(query)
	if err != nil {
		printJSON(map[string]any{"tool": "holmes", "version": version, "status": "error", "query": query, "engine": "sherlock-search→hellgraph", "error": err.Error()})
		os.Exit(1)
	}
	printJSON(map[string]any{
		"tool": "holmes", "version": version, "status": "ok", "query": query,
		"engine": "sherlock-search→hellgraph", "evidence_count": n, "grounding": g,
		"evidenceId": stableID("search:" + query),
	})
}

// runServe exposes Holmes as a real HTTP service so the cockpit can call it.
func runServe() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8091"
	}
	mux := http.NewServeMux()
	cors := func(w http.ResponseWriter) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "content-type")
		w.Header().Set("content-type", "application/json")
	}
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		cors(w)
		json.NewEncoder(w).Encode(map[string]any{"ok": true, "service": "holmes", "version": version, "hellgraph": hellgraphBase()})
	})
	mux.HandleFunc("/search", func(w http.ResponseWriter, r *http.Request) {
		cors(w)
		if r.Method == http.MethodOptions {
			return
		}
		q := r.URL.Query().Get("q")
		g, n, err := searchGraph(q)
		if err != nil {
			w.WriteHeader(502)
			json.NewEncoder(w).Encode(map[string]any{"status": "error", "query": q, "error": err.Error()})
			return
		}
		json.NewEncoder(w).Encode(map[string]any{"status": "ok", "query": q, "engine": "sherlock-search→hellgraph", "evidence_count": n, "grounding": g})
	})
	mux.HandleFunc("/verify", func(w http.ResponseWriter, r *http.Request) {
		cors(w)
		if r.Method == http.MethodOptions {
			return
		}
		var req struct {
			Claims []string `json:"claims"`
		}
		body, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(body, &req)
		results := make([]map[string]any, 0, len(req.Claims))
		for _, c := range req.Claims {
			results = append(results, verifyClaim(c))
		}
		json.NewEncoder(w).Encode(map[string]any{"status": "ok", "engine": "deduction-engine", "results": results})
	})
	mux.HandleFunc("/analyze", func(w http.ResponseWriter, r *http.Request) {
		cors(w)
		if r.Method == http.MethodOptions {
			return
		}
		var req struct {
			Text string `json:"text"`
		}
		body, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(body, &req)
		sum := sha256.Sum256([]byte(req.Text))
		json.NewEncoder(w).Encode(map[string]any{"status": "ok", "tool": "holmes",
			"bytes": len(req.Text), "lines": countLines(req.Text), "words": len(strings.Fields(req.Text)),
			"sha256": hex.EncodeToString(sum[:]), "evidenceRef": "evidence://holmes/" + stableID(hex.EncodeToString(sum[:]))})
	})
	log.Printf("holmes serve on :%s → hellgraph %s", port, hellgraphBase())
	// Bind all interfaces (":port"), not 127.0.0.1: in-cluster the kubelet probe hits the pod IP, so a
	// localhost-only bind fails the liveness probe → SIGKILL → CrashLoop (the sherlock-engine lesson).
	if err := http.ListenAndServe(":"+port, mux); err != nil {
		log.Fatal(err)
	}
}

var _ = bytes.NewReader // retain import for future POST bodies

func runGraph(path string) {
	record, err := analyzeFile(path)
	if err != nil {
		printJSON(map[string]any{"status": "failed", "error": err.Error(), "path": path})
		os.Exit(1)
	}
	printJSON(map[string]any{
		"tool":       "holmes",
		"version":    version,
		"status":     "not-yet-wired",
		"path":       record.Path,
		"sha256":     record.SHA256,
		"target":     "language.graph.v1/ToSemanticGraph",
		"message":    "Semantic graph conversion is declared but not wired in this CLI skeleton.",
		"evidenceId": stableID("graph:" + record.SHA256),
	})
}

func runGovern(path string) {
	record, err := analyzeFile(path)
	if err != nil {
		printJSON(map[string]any{"status": "failed", "error": err.Error(), "path": path})
		os.Exit(1)
	}
	printJSON(map[string]any{
		"tool":       "holmes",
		"version":    version,
		"status":     "not-yet-wired",
		"path":       record.Path,
		"sha256":     record.SHA256,
		"target":     "language.govern.v1/Evaluate",
		"message":    "Governance/eval binding is declared but not wired in this CLI skeleton.",
		"evidenceId": stableID("govern:" + record.SHA256),
	})
}

func analyzeFile(path string) (analysisRecord, error) {
	clean := filepath.Clean(path)
	bytes, err := os.ReadFile(clean)
	if err != nil {
		return analysisRecord{}, err
	}
	text := string(bytes)
	sum := sha256.Sum256(bytes)
	record := analysisRecord{
		Tool:       "holmes",
		Version:    version,
		Status:     "demo-analysis",
		Path:       clean,
		Bytes:      len(bytes),
		SHA256:     hex.EncodeToString(sum[:]),
		Lines:      countLines(text),
		Words:      len(strings.Fields(text)),
		Components: []string{"ingestion", "linguistic-primitives", "evidence"},
	}
	record.EvidenceRef = "evidence://holmes/" + stableID(record.SHA256)
	return record, nil
}

func countLines(text string) int {
	if text == "" {
		return 0
	}
	count := strings.Count(text, "\n")
	if !strings.HasSuffix(text, "\n") {
		count++
	}
	return count
}

func runEvidence(command, status string, details map[string]any) {
	printJSON(evidence{
		Tool:      "holmes",
		Version:   version,
		Commit:    commit,
		BuildDate: date,
		Repo:      "SocioProphet/holmes",
		Command:   command,
		Status:    status,
		Details:   details,
	})
}

func stableID(value string) string {
	sum := sha256.Sum256([]byte(value))
	return hex.EncodeToString(sum[:])[:16]
}

func printJSON(value any) {
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(value); err != nil {
		panic(errors.New("failed to encode JSON: " + err.Error()))
	}
}
