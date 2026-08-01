// wordops-mcp-gateway — the WordOps lease-enforcing MCP gateway (Go, stdlib-only).
//
// Front door for privileged agent tool calls in the WordOps Matrix fabric. It is
// the enforcement point named in the reference pack ("the gateway enforces
// audience, scope, case, task, expiry"; "durable workflow state lives outside
// MCP"). Matrix rooms are collaboration context — they are NOT the authorization
// ledger. This gateway is where a capability-lease is checked and where the
// durable ExecutionReceipt is written to the ledger.
//
// Reference flow for a containment action:
//
//	incident room  ->  broker mints an A4 capability-lease  ->  POST /mcp/invoke
//	   -> gateway authorizes the lease (audience/scope/case/task/expiry; a
//	      containment sever is intrinsically risk_class A4)
//	   -> on ALLOW: call gbrg-containment, build a governed ExecutionReceipt,
//	      POST it to agent-activity-ledger, return a room-safe summary
//	   -> on DENY: fail closed AND still write a denied ExecutionReceipt (A4 is
//	      heavily audited — teeth fire both ways).
//
// Endpoints (bind 0.0.0.0:$PORT, default 8080):
//
//	GET    /healthz                              — liveness/readiness
//	GET    /.well-known/oauth-protected-resource — Protected Resource Metadata (RFC 9728)
//	POST   /mcp/invoke                           — privileged tool call under a lease
//	DELETE /mcp/session                          — explicit session teardown (MCP-Session-Id)
//
// SECURITY: the gateway verifies the lease's cryptographic authenticity BEFORE
// enforcing its claims. A lease is a broker-signed RS256 JWT (`lease_token`),
// verified against the broker JWKS by kid, with issuer + nbf/exp checked. A
// DPoP-bound lease (`dpop_jkt`) additionally requires a valid DPoP proof header
// (RFC 9449) proving the caller holds the bound key. Only then are the claims
// (audience/scope/case/task, containment⇒A4) enforced. See jose.go.
package main

import (
	"bytes"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"sync"
	"time"
)

// ---------------------------------------------------------------------------
// capability-lease (the estate's canonical shape; aud may be string or []string)
// ---------------------------------------------------------------------------

type lease struct {
	LeaseID    string          `json:"lease_id"`
	Sub        string          `json:"sub"`
	Act        string          `json:"act"`
	Aud        json.RawMessage `json:"aud"`
	Scope      []string        `json:"scope"`
	CaseID     string          `json:"case_id"`
	TaskID     string          `json:"task_id"`
	ApprovalID string          `json:"approval_id"`
	RiskClass  string          `json:"risk_class"`
	NotBefore  string          `json:"not_before"`
	ExpiresAt  string          `json:"expires_at"`
	JTI        string          `json:"jti"`
}

func (l lease) audiences() []string {
	if len(l.Aud) == 0 {
		return nil
	}
	var one string
	if err := json.Unmarshal(l.Aud, &one); err == nil {
		return []string{one}
	}
	var many []string
	_ = json.Unmarshal(l.Aud, &many)
	return many
}

func (l lease) activeAt(now time.Time) bool {
	nb, err1 := time.Parse(time.RFC3339, l.NotBefore)
	exp, err2 := time.Parse(time.RFC3339, l.ExpiresAt)
	if err1 != nil || err2 != nil {
		return false // unparseable window => fail closed
	}
	return !now.Before(nb) && now.Before(exp)
}

type toolReq struct {
	Name          string `json:"name"`
	Audience      string `json:"audience"`
	RequiredScope string `json:"required_scope"`
}

func contains(xs []string, want string) bool {
	for _, x := range xs {
		if x == want {
			return true
		}
	}
	return false
}

func isContainment(scope string) bool { return len(scope) >= 17 && scope[:17] == "containment:sever" }

// authorize mirrors OPA wordops.authz.allow_action plus expiry and case/task
// binding. Returns (false, reason) on the first failed check so denials are legible.
func (l lease) authorize(t toolReq, now time.Time) (bool, string) {
	switch {
	case !l.activeAt(now):
		return false, "lease not active (expired, not yet valid, or malformed window)"
	case !contains(l.audiences(), t.Audience):
		return false, "audience mismatch: lease not scoped to " + t.Audience
	case !contains(l.Scope, t.RequiredScope):
		return false, "scope not covered: lease lacks " + t.RequiredScope
	case l.CaseID == "" || l.TaskID == "":
		return false, "case/task binding required"
	case isContainment(t.RequiredScope) && l.RiskClass != "A4":
		return false, "containment sever is intrinsically risk_class A4"
	}
	return true, ""
}

// ---------------------------------------------------------------------------
// ExecutionReceipt (mirrors prophet-core-contracts/schemas/execution-receipt)
// ---------------------------------------------------------------------------

type executionReceipt struct {
	SchemaVersion      string   `json:"schema_version"`
	ExecutionReceiptID string   `json:"execution_receipt_id"`
	ExecutedAt         string   `json:"executed_at"`
	Agent              agentRec `json:"agent"`
	Input              inputRec `json:"input"`
	Decision           decRec   `json:"decision"`
	Verdict            verRec   `json:"verdict"`
	CapabilitiesHeld   []string `json:"capabilities_held"`
	CapabilitiesUsed   []string `json:"capabilities_used"`
	ProofArtifact      proofRec `json:"proof_artifact"`
	ReceiptHash        string   `json:"receipt_hash"`
}
type agentRec struct {
	Name     string `json:"name"`
	Version  string `json:"version"`
	Category string `json:"category,omitempty"`
}
type inputRec struct {
	Type string `json:"type"`
	Ref  string `json:"ref,omitempty"`
}
type decRec struct {
	Verdict       string `json:"verdict"`
	AuthorityBand string `json:"authority_band"`
	LatencyMs     int    `json:"latency_ms,omitempty"`
}
type verRec struct {
	State          string `json:"state"`
	EpistemicLevel string `json:"epistemic_level,omitempty"`
}
type proofRec struct {
	SHA256     string `json:"sha256"`
	SignedBy   string `json:"signed_by,omitempty"`
	Replayable bool   `json:"replayable"`
}

func sha256Hex(b []byte) string { s := sha256.Sum256(b); return hex.EncodeToString(s[:]) }

func sealReceipt(r *executionReceipt) {
	r.ProofArtifact.SignedBy = "wordops-mcp-gateway"
	r.ProofArtifact.Replayable = true
	canon, _ := json.Marshal(struct {
		ID   string   `json:"id"`
		At   string   `json:"at"`
		Dec  decRec   `json:"dec"`
		Ver  verRec   `json:"ver"`
		Used []string `json:"used"`
		P    string   `json:"p"`
	}{r.ExecutionReceiptID, r.ExecutedAt, r.Decision, r.Verdict, r.CapabilitiesUsed, r.ProofArtifact.SHA256})
	r.ReceiptHash = "sha256:" + sha256Hex(canon)
}

// ---------------------------------------------------------------------------
// server
// ---------------------------------------------------------------------------

type config struct {
	containmentURL string
	ledgerURL      string
	authServer     string // Keycloak realm issuer for Protected Resource Metadata
	resource       string
	brokerJWKSURL  string // where the lease-signing broker publishes its verify keys
	brokerIssuer   string // expected `iss` on a lease token ("" = skip issuer check)
	invokePath     string // htu suffix a DPoP proof must bind to
}

type server struct {
	cfg      config
	client   *http.Client
	jwks     *jwksCache
	mu       sync.Mutex
	sessions map[string]string // session-id -> subject (sessions are NOT authentication)
}

func newServer(cfg config) *server {
	if cfg.invokePath == "" {
		cfg.invokePath = "/mcp/invoke"
	}
	client := &http.Client{Timeout: 5 * time.Second}
	return &server{cfg: cfg, client: client, jwks: newJWKSCache(cfg.brokerJWKSURL, client), sessions: map[string]string{}}
}

// leaseFromClaims maps verified lease-token claims onto the internal lease shape so
// the existing claim-authorization (audience/scope/case/task/expiry, containment⇒A4)
// runs unchanged.
func leaseFromClaims(cl *leaseClaims) lease {
	return lease{
		LeaseID: cl.JTI, Sub: cl.Sub, Act: cl.Act,
		Aud:    json.RawMessage(fmt.Sprintf("%q", cl.Aud)),
		Scope:  cl.Scope,
		CaseID: cl.CaseID, TaskID: cl.TaskID, ApprovalID: cl.ApprovalID, RiskClass: cl.RiskClass,
		NotBefore: time.Unix(cl.Nbf, 0).UTC().Format(time.RFC3339),
		ExpiresAt: time.Unix(cl.Exp, 0).UTC().Format(time.RFC3339),
		JTI:       cl.JTI,
	}
}

func newID(prefix string) string {
	b := make([]byte, 12)
	_, _ = rand.Read(b)
	return prefix + hex.EncodeToString(b)
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}

// callContainment invokes gbrg-containment and returns the ContainmentProofArtifact.
func (s *server) callContainment(scope string) (map[string]any, error) {
	if scope != "selective" {
		scope = "full"
	}
	resp, err := s.client.Get(s.cfg.containmentURL + "/containment?scope=" + scope)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("containment engine returned %d", resp.StatusCode)
	}
	var art map[string]any
	if err := json.Unmarshal(body, &art); err != nil {
		return nil, err
	}
	return art, nil
}

// emit posts a receipt to the durable ledger. Best-effort: a ledger outage must
// not turn a DENY into an ALLOW, so the caller's decision already stands.
func (s *server) emit(r executionReceipt) (bool, error) {
	body, _ := json.Marshal(r)
	resp, err := s.client.Post(s.cfg.ledgerURL+"/executions", "application/json", bytes.NewReader(body))
	if err != nil {
		return false, err
	}
	defer resp.Body.Close()
	_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, 1<<16))
	return resp.StatusCode == http.StatusCreated, nil
}

func (s *server) sessionFor(r *http.Request, sub string) string {
	sid := r.Header.Get("MCP-Session-Id")
	s.mu.Lock()
	defer s.mu.Unlock()
	if sid != "" {
		if _, ok := s.sessions[sid]; ok {
			return sid
		}
	}
	sid = newID("mcp-sess-")
	s.sessions[sid] = sub // bound to the authenticated caller (session != auth)
	return sid
}

type invokeReq struct {
	LeaseToken string         `json:"lease_token"`
	Tool       toolReq        `json:"tool"`
	Params     map[string]any `json:"params"`
}

// denyReceipt builds (and the caller emits) a governed block/denied receipt so every
// refused attempt is audited — teeth fire both ways.
func denyReceipt(caseRef string, heldScopes []string, reason string, latencyMs int, now time.Time) executionReceipt {
	rec := executionReceipt{
		SchemaVersion: "0.1.0", ExecutionReceiptID: newID("exec_deny_"), ExecutedAt: now.Format(time.RFC3339),
		Agent:            agentRec{Name: "WordOps Containment Agent", Version: "0.1.0", Category: "response"},
		Input:            inputRec{Type: "detection", Ref: caseRef},
		Decision:         decRec{Verdict: "block", AuthorityBand: "observe", LatencyMs: latencyMs},
		Verdict:          verRec{State: "denied", EpistemicLevel: "rejected"},
		CapabilitiesHeld: heldScopes,
		CapabilitiesUsed: []string{},
		ProofArtifact:    proofRec{SHA256: "sha256:" + sha256Hex([]byte("deny:"+reason))},
	}
	sealReceipt(&rec)
	return rec
}

func (s *server) handleInvoke(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.Header().Set("Allow", "POST")
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{"error": "method not allowed"})
		return
	}
	start := time.Now()
	var req invokeReq
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<20)).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid JSON: " + err.Error()})
		return
	}
	now := time.Now().UTC()

	// 1. Verify the lease is a genuine, unexpired broker-signed token.
	claims, err := s.jwks.verifyLeaseToken(req.LeaseToken, s.cfg.brokerIssuer, now)
	if err != nil {
		rec := denyReceipt("", nil, "lease-token invalid: "+err.Error(), int(time.Since(start).Milliseconds()), now)
		emitted, _ := s.emit(rec)
		writeJSON(w, http.StatusUnauthorized, map[string]any{
			"admitted": false, "reason": "lease-token invalid: " + err.Error(),
			"receipt_hash": rec.ReceiptHash, "ledger_recorded": emitted,
		})
		return
	}

	// 2. If the lease is sender-constrained, the caller must prove key possession.
	if claims.DPoPJKT != "" {
		if err := verifyDPoP(r.Header.Get("DPoP"), claims.DPoPJKT, http.MethodPost, s.cfg.invokePath, now); err != nil {
			rec := denyReceipt(claims.CaseID, claims.Scope, "DPoP verification failed: "+err.Error(), int(time.Since(start).Milliseconds()), now)
			emitted, _ := s.emit(rec)
			writeJSON(w, http.StatusUnauthorized, map[string]any{
				"admitted": false, "reason": "DPoP verification failed: " + err.Error(),
				"receipt_hash": rec.ReceiptHash, "ledger_recorded": emitted,
			})
			return
		}
	}

	lease := leaseFromClaims(claims)
	sid := s.sessionFor(r, lease.Sub)
	w.Header().Set("MCP-Session-Id", sid)

	// 3. Enforce the (now-authentic) claims.
	ok, reason := lease.authorize(req.Tool, now)
	if !ok {
		rec := denyReceipt(lease.CaseID, lease.Scope, reason, int(time.Since(start).Milliseconds()), now)
		emitted, _ := s.emit(rec)
		writeJSON(w, http.StatusForbidden, map[string]any{
			"admitted": false, "reason": reason, "session_id": sid,
			"receipt_hash": rec.ReceiptHash, "ledger_recorded": emitted,
		})
		return
	}

	// ALLOW: execute the tool. Only sever_endpoint is wired today.
	if req.Tool.Name != "sever_endpoint" {
		writeJSON(w, http.StatusNotImplemented, map[string]any{"error": "unknown tool: " + req.Tool.Name, "session_id": sid})
		return
	}
	scope, _ := req.Params["scope"].(string)
	art, err := s.callContainment(scope)
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]any{"error": "containment backend: " + err.Error(), "session_id": sid})
		return
	}

	// Honest verdict mapping: a no-op sever (INCONCLUSIVE / speculative) is PENDING,
	// never a verified containment.
	level, _ := art["epistemicLevel"].(string)
	status, _ := art["status"].(string)
	state := "pending"
	if status == "PROVED" {
		state = "verified"
	}
	artBytes, _ := json.Marshal(art)
	rec := executionReceipt{
		SchemaVersion: "0.1.0", ExecutionReceiptID: newID("exec_sever_"), ExecutedAt: now.Format(time.RFC3339),
		Agent:            agentRec{Name: "WordOps Containment Agent", Version: "0.1.0", Category: "response"},
		Input:            inputRec{Type: "detection", Ref: lease.CaseID},
		Decision:         decRec{Verdict: "allow", AuthorityBand: "execute_remote", LatencyMs: int(time.Since(start).Milliseconds())},
		Verdict:          verRec{State: state, EpistemicLevel: level},
		CapabilitiesHeld: lease.Scope,
		CapabilitiesUsed: []string{req.Tool.RequiredScope},
		ProofArtifact:    proofRec{SHA256: "sha256:" + sha256Hex(artBytes)},
	}
	sealReceipt(&rec)
	emitted, emitErr := s.emit(rec)
	if emitErr != nil {
		log.Printf("ledger emit failed (decision stands): %v", emitErr)
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"admitted":        true,
		"session_id":      sid,
		"verdict":         state,
		"summary":         fmt.Sprintf("severed %s scope on %v; %v of %v reachable nodes contained", art["severedScope"], art["source"], art["containedCount"], art["baselineReachableCount"]),
		"receipt_hash":    rec.ReceiptHash,
		"ledger_recorded": emitted,
		"containment": map[string]any{
			"severedScope":           art["severedScope"],
			"containedCount":         art["containedCount"],
			"residualReachableCount": art["residualReachableCount"],
			"epistemicLevel":         level,
		},
	})
}

func (s *server) handleSessionDelete(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		w.Header().Set("Allow", "DELETE")
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{"error": "method not allowed"})
		return
	}
	sid := r.Header.Get("MCP-Session-Id")
	s.mu.Lock()
	_, existed := s.sessions[sid]
	delete(s.sessions, sid)
	s.mu.Unlock()
	writeJSON(w, http.StatusOK, map[string]any{"closed": existed, "session_id": sid})
}

func (s *server) handlePRM(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"resource":                 s.cfg.resource,
		"authorization_servers":    []string{s.cfg.authServer},
		"scopes_supported":         []string{"containment:sever:full", "containment:sever:selective", "read:executions"},
		"bearer_methods_supported": []string{"header"},
	})
}

func (s *server) mux() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "service": "wordops-mcp-gateway"})
	})
	mux.HandleFunc("/.well-known/oauth-protected-resource", s.handlePRM)
	mux.HandleFunc("/mcp/invoke", s.handleInvoke)
	mux.HandleFunc("/mcp/session", s.handleSessionDelete)
	return mux
}

func env(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func main() {
	port := env("PORT", "8080")
	s := newServer(config{
		containmentURL: env("GBRG_CONTAINMENT_URL", "http://gbrg-engine:8080"),
		ledgerURL:      env("LEDGER_URL", "http://agent-activity-ledger:8080"),
		authServer:     env("AUTH_SERVER", "https://auth.socioprophet.ai/realms/wordops"),
		resource:       env("RESOURCE_URL", "https://agents.socioprophet.ai/mcp/wordops"),
		brokerJWKSURL:  env("BROKER_JWKS_URL", "http://wordops-capability-broker:8080/.well-known/jwks.json"),
		brokerIssuer:   env("BROKER_ISSUER", "https://auth.socioprophet.ai/realms/wordops/wordops-capability-broker"),
		invokePath:     "/mcp/invoke",
	})
	log.Printf("wordops-mcp-gateway serving on :%s (containment=%s ledger=%s)", port, s.cfg.containmentURL, s.cfg.ledgerURL)
	if err := http.ListenAndServe("0.0.0.0:"+port, s.mux()); err != nil {
		log.Fatal(err)
	}
}
