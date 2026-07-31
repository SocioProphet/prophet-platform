// agent-activity-ledger — the governed Executions Ledger service (Go, stdlib-only).
//
// Serves the agent-execution receipt spine behind the cockpit's Executions Ledger
// surface. Each record is a verdict + a receipt warrant conforming to the
// prophet-core-contracts ExecutionReceipt schema — never a bare boolean.
//
// Endpoints (bind 0.0.0.0:$PORT, default 8080):
//
//	GET /healthz     — liveness/readiness (chart probe path)
//	GET /executions  — the ledger (trailing window); shape mirrors ExecutionReceipt
//
// Fixture-backed for now (system-of-record store is the follow-on): the endpoint
// returns governed, schema-shaped receipts so the cockpit renders REAL warrants
// against a live service rather than a client fixture.
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"time"
)

// executionReceipt mirrors prophet-core-contracts/schemas/execution-receipt.schema.json.
type executionReceipt struct {
	SchemaVersion      string   `json:"schema_version"`
	ExecutionReceiptID string   `json:"execution_receipt_id"`
	ExecutedAt         string   `json:"executed_at"`
	Agent              agent    `json:"agent"`
	Input              input    `json:"input"`
	Decision           decision `json:"decision"`
	Verdict            verdict  `json:"verdict"`
	CapabilitiesHeld   []string `json:"capabilities_held"`
	CapabilitiesUsed   []string `json:"capabilities_used"`
	ProofArtifact      proof    `json:"proof_artifact"`
	ReceiptHash        string   `json:"receipt_hash"`
}
type agent struct {
	Name     string `json:"name"`
	Version  string `json:"version"`
	Category string `json:"category,omitempty"`
}
type input struct {
	Type string `json:"type"`
	Ref  string `json:"ref,omitempty"`
}
type decision struct {
	Verdict       string `json:"verdict"`
	AuthorityBand string `json:"authority_band"`
	LatencyMs     int    `json:"latency_ms,omitempty"`
}
type verdict struct {
	State          string `json:"state"`
	EpistemicLevel string `json:"epistemic_level,omitempty"`
}
type proof struct {
	SHA256     string `json:"sha256"`
	SignedBy   string `json:"signed_by,omitempty"`
	Replayable bool   `json:"replayable"`
}

// ledger is the fixture spine until a persistent system-of-record store lands.
var ledger = []executionReceipt{
	{
		SchemaVersion: "0.1.0", ExecutionReceiptID: "exec_hybrid_investigation_wiz_verified", ExecutedAt: "2026-07-31T15:09:04Z",
		Agent:            agent{Name: "Hybrid Investigation Agent", Version: "1.1.0", Category: "investigation"},
		Input:            input{Type: "external_alert", Ref: "alert_wiz_372688"},
		Decision:         decision{Verdict: "allow", AuthorityBand: "recommend", LatencyMs: 12},
		Verdict:          verdict{State: "verified", EpistemicLevel: "bounded"},
		CapabilitiesHeld: []string{"cap_read_alerts", "cap_read_baseline", "cap_read_reputation"},
		CapabilitiesUsed: []string{"cap_read_alerts", "cap_read_baseline", "cap_read_reputation"},
		ProofArtifact:    proof{SHA256: "sha256:4f8b0c11a2e7d9f0", SignedBy: "warden", Replayable: true},
		ReceiptHash:      "sha256:exec-hybrid-investigation-wiz-verified",
	},
	{
		SchemaVersion: "0.1.0", ExecutionReceiptID: "exec_investigation_agent_denied", ExecutedAt: "2026-07-31T13:38:49Z",
		Agent:            agent{Name: "Investigation Agent", Version: "1.0.2", Category: "investigation"},
		Input:            input{Type: "event", Ref: "event_16517"},
		Decision:         decision{Verdict: "block", AuthorityBand: "observe", LatencyMs: 8},
		Verdict:          verdict{State: "denied", EpistemicLevel: "rejected"},
		CapabilitiesHeld: []string{"cap_read_events"},
		CapabilitiesUsed: []string{},
		ProofArtifact:    proof{SHA256: "sha256:a0f12277b3c4d5e6", SignedBy: "warden", Replayable: true},
		ReceiptHash:      "sha256:exec-investigation-agent-denied",
	},
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "service": "agent-activity-ledger", "receipts": len(ledger)})
	})
	mux.HandleFunc("/executions", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{
			"generated_at": time.Now().UTC().Format(time.RFC3339),
			"count":        len(ledger),
			"receipts":     ledger,
		})
	})

	log.Printf("agent-activity-ledger serving on :%s (/healthz /executions)", port)
	if err := http.ListenAndServe("0.0.0.0:"+port, mux); err != nil {
		log.Fatal(err)
	}
}
