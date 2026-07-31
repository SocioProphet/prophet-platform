// agent-activity-ledger — the governed Executions Ledger service (Go, stdlib-only).
//
// Serves the agent-execution receipt spine behind the cockpit's Executions Ledger
// surface. Each record is a verdict + a receipt warrant conforming to the
// prophet-core-contracts ExecutionReceipt schema — never a bare boolean.
//
// Endpoints (bind 0.0.0.0:$PORT, default 8080):
//
//	GET  /healthz     — liveness/readiness (chart probe path)
//	GET  /executions  — the ledger (trailing window); shape mirrors ExecutionReceipt
//	POST /executions  — append a receipt (used by the WordOps MCP gateway); the
//	                    ledger is the DURABLE sink, so governed side effects land
//	                    here, not in a Matrix room. Malformed / self-contradictory
//	                    receipts are rejected (the ledger has teeth).
//
// Store is in-memory for now (a persistent system-of-record is the follow-on);
// POSTed receipts are hash-chained onto the fixture spine so the cockpit renders
// REAL warrants against a live service.
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"sync"
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
	Blast              *blast   `json:"blast,omitempty"`
	PreviousHash       string   `json:"previous_receipt_hash,omitempty"`
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
type blast struct {
	TargetNode     string `json:"target_node"`
	ReachableCount int    `json:"reachable_count"`
	Hops           int    `json:"hops"`
}

var (
	mu     sync.RWMutex
	ledger = []executionReceipt{
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
)

var (
	validVerdict   = map[string]bool{"allow": true, "block": true, "require_approval": true, "degrade": true, "transform": true}
	validState     = map[string]bool{"verified": true, "pending": true, "denied": true}
	validAuthority = map[string]bool{"observe": true, "recommend": true, "queue": true, "execute_local": true, "execute_remote": true, "admin_override": true}
)

// validate enforces the ExecutionReceipt required fields, the critical enums, and
// the contract's semantic invariants (the same ones the prophet-core-contracts
// validator rejects). Returns a non-nil error naming the first violation.
func validate(r executionReceipt) error {
	switch {
	case r.SchemaVersion != "0.1.0":
		return fmt.Errorf("schema_version must be 0.1.0")
	case r.ExecutionReceiptID == "":
		return fmt.Errorf("execution_receipt_id is required")
	case r.ExecutedAt == "":
		return fmt.Errorf("executed_at is required")
	case r.Agent.Name == "" || r.Agent.Version == "":
		return fmt.Errorf("agent.name and agent.version are required")
	case r.Input.Type == "":
		return fmt.Errorf("input.type is required")
	case !validVerdict[r.Decision.Verdict]:
		return fmt.Errorf("decision.verdict %q is not a valid policy decision", r.Decision.Verdict)
	case !validAuthority[r.Decision.AuthorityBand]:
		return fmt.Errorf("decision.authority_band %q is not a valid authority band", r.Decision.AuthorityBand)
	case !validState[r.Verdict.State]:
		return fmt.Errorf("verdict.state %q is not verified|pending|denied", r.Verdict.State)
	case r.ProofArtifact.SHA256 == "":
		return fmt.Errorf("proof_artifact.sha256 is required")
	case r.ReceiptHash == "":
		return fmt.Errorf("receipt_hash is required")
	}
	// INV1: capabilities_used must be a subset of capabilities_held.
	held := map[string]bool{}
	for _, c := range r.CapabilitiesHeld {
		held[c] = true
	}
	for _, c := range r.CapabilitiesUsed {
		if !held[c] {
			return fmt.Errorf("capabilities_used %q not in capabilities_held (INV1)", c)
		}
	}
	// INV2: a verified verdict must be backed by a replayable artifact.
	if r.Verdict.State == "verified" && !r.ProofArtifact.Replayable {
		return fmt.Errorf("verified verdict requires a replayable proof_artifact (INV2)")
	}
	// INV3: block <=> denied.
	if (r.Decision.Verdict == "block") != (r.Verdict.State == "denied") {
		return fmt.Errorf("decision.verdict=block iff verdict.state=denied (INV3)")
	}
	// INV4: require_approval => pending.
	if r.Decision.Verdict == "require_approval" && r.Verdict.State != "pending" {
		return fmt.Errorf("require_approval requires verdict.state=pending (INV4)")
	}
	return nil
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}

func handleExecutions(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		mu.RLock()
		snapshot := make([]executionReceipt, len(ledger))
		copy(snapshot, ledger)
		mu.RUnlock()
		writeJSON(w, http.StatusOK, map[string]any{
			"generated_at": time.Now().UTC().Format(time.RFC3339),
			"count":        len(snapshot),
			"receipts":     snapshot,
		})
	case http.MethodPost:
		var rec executionReceipt
		if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<20)).Decode(&rec); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid JSON: " + err.Error()})
			return
		}
		if err := validate(rec); err != nil {
			writeJSON(w, http.StatusUnprocessableEntity, map[string]any{"error": err.Error(), "accepted": false})
			return
		}
		mu.Lock()
		if rec.PreviousHash == "" && len(ledger) > 0 {
			rec.PreviousHash = ledger[len(ledger)-1].ReceiptHash // hash-chain onto the tip
		}
		ledger = append(ledger, rec)
		count := len(ledger)
		mu.Unlock()
		writeJSON(w, http.StatusCreated, map[string]any{
			"accepted":     true,
			"receipt_hash": rec.ReceiptHash,
			"count":        count,
		})
	default:
		w.Header().Set("Allow", "GET, POST")
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{"error": "method not allowed"})
	}
}

func newMux() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		mu.RLock()
		n := len(ledger)
		mu.RUnlock()
		writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "service": "agent-activity-ledger", "receipts": n})
	})
	mux.HandleFunc("/executions", handleExecutions)
	return mux
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	log.Printf("agent-activity-ledger serving on :%s (GET/POST /executions, /healthz)", port)
	if err := http.ListenAndServe("0.0.0.0:"+port, newMux()); err != nil {
		log.Fatal(err)
	}
}
