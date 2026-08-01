package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func validReceipt() executionReceipt {
	return executionReceipt{
		SchemaVersion: "0.1.0", ExecutionReceiptID: "exec_test_ok", ExecutedAt: "2026-07-31T16:00:00Z",
		Agent:            agent{Name: "WordOps MCP Gateway", Version: "0.1.0", Category: "response"},
		Input:            input{Type: "detection", Ref: "CASE-1"},
		Decision:         decision{Verdict: "allow", AuthorityBand: "execute_remote", LatencyMs: 20},
		Verdict:          verdict{State: "verified", EpistemicLevel: "empirical"},
		CapabilitiesHeld: []string{"cap_containment_sever"},
		CapabilitiesUsed: []string{"cap_containment_sever"},
		ProofArtifact:    proof{SHA256: "sha256:abc123", SignedBy: "wordops-mcp-gateway", Replayable: true},
		ReceiptHash:      "sha256:exec-test-ok",
	}
}

func post(t *testing.T, srv http.Handler, r executionReceipt) *httptest.ResponseRecorder {
	t.Helper()
	body, _ := json.Marshal(r)
	req := httptest.NewRequest(http.MethodPost, "/executions", bytes.NewReader(body))
	rr := httptest.NewRecorder()
	srv.ServeHTTP(rr, req)
	return rr
}

func TestPostValidReceiptAccepted(t *testing.T) {
	mux := newMux()
	before := len(ledger)
	rr := post(t, mux, validReceipt())
	if rr.Code != http.StatusCreated {
		t.Fatalf("want 201, got %d: %s", rr.Code, rr.Body.String())
	}
	if len(ledger) != before+1 {
		t.Fatalf("ledger not appended: before=%d after=%d", before, len(ledger))
	}
}

func TestPostRejectsInvariantViolations(t *testing.T) {
	cases := map[string]func(executionReceipt) executionReceipt{
		"INV1 used-not-subset":         func(r executionReceipt) executionReceipt { r.CapabilitiesUsed = []string{"cap_not_held"}; return r },
		"INV2 verified-not-replayable": func(r executionReceipt) executionReceipt { r.ProofArtifact.Replayable = false; return r },
		"INV3 block-not-denied":        func(r executionReceipt) executionReceipt { r.Decision.Verdict = "block"; return r },
		"INV4 approval-not-pending":    func(r executionReceipt) executionReceipt { r.Decision.Verdict = "require_approval"; return r },
		"bad-verdict-enum":             func(r executionReceipt) executionReceipt { r.Verdict.State = "great"; return r },
		"bad-authority-enum":           func(r executionReceipt) executionReceipt { r.Decision.AuthorityBand = "god_mode"; return r },
	}
	for name, mutate := range cases {
		t.Run(name, func(t *testing.T) {
			mux := newMux()
			before := len(ledger)
			rr := post(t, mux, mutate(validReceipt()))
			if rr.Code != http.StatusUnprocessableEntity {
				t.Fatalf("%s: want 422, got %d: %s", name, rr.Code, rr.Body.String())
			}
			if len(ledger) != before {
				t.Fatalf("%s: a rejected receipt must not be appended", name)
			}
		})
	}
}

func TestGetReturnsLedger(t *testing.T) {
	mux := newMux()
	req := httptest.NewRequest(http.MethodGet, "/executions", nil)
	rr := httptest.NewRecorder()
	mux.ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("want 200, got %d", rr.Code)
	}
	var out struct {
		Count    int                `json:"count"`
		Receipts []executionReceipt `json:"receipts"`
	}
	if err := json.Unmarshal(rr.Body.Bytes(), &out); err != nil {
		t.Fatalf("bad json: %v", err)
	}
	if out.Count != len(out.Receipts) || out.Count < 2 {
		t.Fatalf("unexpected count=%d len=%d", out.Count, len(out.Receipts))
	}
}
