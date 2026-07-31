package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"
)

// fakeContainment returns a ContainmentProofArtifact; proved controls verified vs pending.
func fakeContainment(proved bool) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		level, status, contained := "empirical", "PROVED", 3
		if !proved {
			level, status, contained = "speculative", "INCONCLUSIVE", 0
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"schemaVersion": "0.1.0", "source": "vvv-648e9d56f1a", "severedScope": r.URL.Query().Get("scope"),
			"epistemicLevel": level, "status": status, "containedCount": contained,
			"baselineReachableCount": 4, "residualReachableCount": 4 - contained,
		})
	}))
}

// capturingLedger records posted receipts and applies the block<=>denied invariant.
type capturingLedger struct {
	srv  *httptest.Server
	mu   sync.Mutex
	recs []executionReceipt
}

func newCapturingLedger(t *testing.T) *capturingLedger {
	cl := &capturingLedger{}
	cl.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var rec executionReceipt
		if err := json.NewDecoder(r.Body).Decode(&rec); err != nil {
			w.WriteHeader(http.StatusBadRequest)
			return
		}
		if (rec.Decision.Verdict == "block") != (rec.Verdict.State == "denied") {
			t.Errorf("gateway emitted INV3-violating receipt: verdict=%s state=%s", rec.Decision.Verdict, rec.Verdict.State)
		}
		if rec.ReceiptHash == "" {
			t.Errorf("gateway emitted receipt with no receipt_hash")
		}
		cl.mu.Lock()
		cl.recs = append(cl.recs, rec)
		cl.mu.Unlock()
		w.WriteHeader(http.StatusCreated)
		_ = json.NewEncoder(w).Encode(map[string]any{"accepted": true, "receipt_hash": rec.ReceiptHash})
	}))
	return cl
}

func (cl *capturingLedger) last() executionReceipt {
	cl.mu.Lock()
	defer cl.mu.Unlock()
	if len(cl.recs) == 0 {
		return executionReceipt{}
	}
	return cl.recs[len(cl.recs)-1]
}

func a4Lease() lease {
	now := time.Now().UTC()
	return lease{
		LeaseID: "lease_test", Sub: "agent:containment", Act: "user:responder",
		Aud:    json.RawMessage(`"mcp://gbrg-containment"`),
		Scope:  []string{"containment:sever:full"},
		CaseID: "CASE-INC-1", TaskID: "TASK-1", ApprovalID: "APR-INC-1", RiskClass: "A4",
		NotBefore: now.Add(-time.Minute).Format(time.RFC3339),
		ExpiresAt: now.Add(25 * time.Second).Format(time.RFC3339),
	}
}

func severTool() toolReq {
	return toolReq{Name: "sever_endpoint", Audience: "mcp://gbrg-containment", RequiredScope: "containment:sever:full"}
}

func invoke(t *testing.T, s *server, body invokeReq) *httptest.ResponseRecorder {
	t.Helper()
	b, _ := json.Marshal(body)
	req := httptest.NewRequest(http.MethodPost, "/mcp/invoke", bytes.NewReader(b))
	rr := httptest.NewRecorder()
	s.mux().ServeHTTP(rr, req)
	return rr
}

func newTestServer(cont, ledger string) *server {
	return newServer(config{containmentURL: cont, ledgerURL: ledger, authServer: "https://auth.test/realms/wordops", resource: "https://agents.test/mcp"})
}

func TestAllowSeverProducesVerifiedReceipt(t *testing.T) {
	cont := fakeContainment(true)
	defer cont.Close()
	led := newCapturingLedger(t)
	defer led.srv.Close()
	s := newTestServer(cont.URL, led.srv.URL)

	rr := invoke(t, s, invokeReq{Lease: a4Lease(), Tool: severTool(), Params: map[string]any{"scope": "full"}})
	if rr.Code != http.StatusOK {
		t.Fatalf("want 200, got %d: %s", rr.Code, rr.Body.String())
	}
	var out map[string]any
	_ = json.Unmarshal(rr.Body.Bytes(), &out)
	if out["admitted"] != true || out["verdict"] != "verified" {
		t.Fatalf("want admitted+verified, got %v", out)
	}
	if led.last().Decision.Verdict != "allow" || led.last().Verdict.State != "verified" {
		t.Fatalf("ledger did not record an allow/verified receipt: %+v", led.last())
	}
	if rr.Header().Get("MCP-Session-Id") == "" {
		t.Fatalf("gateway must return an MCP-Session-Id")
	}
}

func TestNoOpSeverIsPendingNotVerified(t *testing.T) {
	cont := fakeContainment(false) // INCONCLUSIVE
	defer cont.Close()
	led := newCapturingLedger(t)
	defer led.srv.Close()
	s := newTestServer(cont.URL, led.srv.URL)

	rr := invoke(t, s, invokeReq{Lease: a4Lease(), Tool: severTool(), Params: map[string]any{"scope": "full"}})
	var out map[string]any
	_ = json.Unmarshal(rr.Body.Bytes(), &out)
	if out["verdict"] != "pending" {
		t.Fatalf("a no-op sever must be pending, got %v", out["verdict"])
	}
}

func TestDenials(t *testing.T) {
	cont := fakeContainment(true)
	defer cont.Close()

	mk := func(mut func(lease) lease) invokeReq {
		return invokeReq{Lease: mut(a4Lease()), Tool: severTool(), Params: map[string]any{"scope": "full"}}
	}
	cases := map[string]invokeReq{
		"containment below A4": mk(func(l lease) lease { l.RiskClass = "A2"; return l }),
		"expired lease":        mk(func(l lease) lease { l.ExpiresAt = time.Now().UTC().Add(-time.Second).Format(time.RFC3339); return l }),
		"audience mismatch":    mk(func(l lease) lease { l.Aud = json.RawMessage(`"mcp://openproject"`); return l }),
		"scope not covered":    mk(func(l lease) lease { l.Scope = []string{"read:executions"}; return l }),
		"missing case binding": mk(func(l lease) lease { l.CaseID = ""; return l }),
	}
	for name, req := range cases {
		t.Run(name, func(t *testing.T) {
			led := newCapturingLedger(t)
			defer led.srv.Close()
			s := newTestServer(cont.URL, led.srv.URL)
			rr := invoke(t, s, req)
			if rr.Code != http.StatusForbidden {
				t.Fatalf("%s: want 403, got %d: %s", name, rr.Code, rr.Body.String())
			}
			// Denial must be audited as a block/denied receipt (teeth both ways).
			if led.last().Decision.Verdict != "block" || led.last().Verdict.State != "denied" {
				t.Fatalf("%s: denial not audited as block/denied: %+v", name, led.last())
			}
		})
	}
}

func TestSessionTeardown(t *testing.T) {
	s := newTestServer("http://unused", "http://unused")
	s.sessions["mcp-sess-x"] = "agent:y"
	req := httptest.NewRequest(http.MethodDelete, "/mcp/session", nil)
	req.Header.Set("MCP-Session-Id", "mcp-sess-x")
	rr := httptest.NewRecorder()
	s.mux().ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("want 200, got %d", rr.Code)
	}
	if _, ok := s.sessions["mcp-sess-x"]; ok {
		t.Fatalf("session was not torn down")
	}
}

func TestProtectedResourceMetadata(t *testing.T) {
	s := newTestServer("http://unused", "http://unused")
	req := httptest.NewRequest(http.MethodGet, "/.well-known/oauth-protected-resource", nil)
	rr := httptest.NewRecorder()
	s.mux().ServeHTTP(rr, req)
	var out map[string]any
	if err := json.Unmarshal(rr.Body.Bytes(), &out); err != nil {
		t.Fatalf("bad json: %v", err)
	}
	if out["authorization_servers"] == nil || out["resource"] == nil {
		t.Fatalf("PRM missing required fields: %v", out)
	}
}
