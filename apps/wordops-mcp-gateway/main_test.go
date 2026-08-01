package main

import (
	"bytes"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"math/big"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"
)

const testIssuer = "https://auth.test/realms/wordops/wordops-capability-broker"

// --- tiny JOSE signer (test-side broker) ---

func be(b []byte) string { return base64.RawURLEncoding.EncodeToString(b) }

func rsaJWK(pub *rsa.PublicKey, kid string) map[string]any {
	e := big.NewInt(int64(pub.E)).Bytes()
	m := map[string]any{"kty": "RSA", "n": be(pub.N.Bytes()), "e": be(e)}
	if kid != "" {
		m["kid"] = kid
	}
	return m
}

func kidOf(pub *rsa.PublicKey) string {
	e := big.NewInt(int64(pub.E)).Bytes()
	canon := fmt.Sprintf(`{"e":%q,"kty":"RSA","n":%q}`, be(e), be(pub.N.Bytes()))
	s := sha256.Sum256([]byte(canon))
	return be(s[:])
}

func signJWS(key *rsa.PrivateKey, header, claims map[string]any) string {
	hb, _ := json.Marshal(header)
	cb, _ := json.Marshal(claims)
	in := be(hb) + "." + be(cb)
	sum := sha256.Sum256([]byte(in))
	sig, _ := rsa.SignPKCS1v15(rand.Reader, key, crypto.SHA256, sum[:])
	return in + "." + be(sig)
}

func mintLease(key *rsa.PrivateKey, kid string, claims map[string]any) string {
	base := map[string]any{"iss": testIssuer, "sub": "agent:containment", "act": "user:responder"}
	for k, v := range claims {
		base[k] = v
	}
	return signJWS(key, map[string]any{"alg": "RS256", "typ": "JWT", "kid": kid}, base)
}

func a4Claims() map[string]any {
	now := time.Now().UTC()
	return map[string]any{
		"aud": "mcp://gbrg-containment", "scope": []string{"containment:sever:full"},
		"case_id": "CASE-INC-1", "task_id": "TASK-1", "risk_class": "A4", "approval_id": "APR-1",
		"nbf": now.Add(-time.Minute).Unix(), "exp": now.Add(25 * time.Second).Unix(), "jti": "lease_test",
	}
}

func dpopProof(key *rsa.PrivateKey, htm, htu string, iat int64) string {
	return signJWS(key,
		map[string]any{"typ": "dpop+jwt", "alg": "RS256", "jwk": rsaJWK(&key.PublicKey, "")},
		map[string]any{"htm": htm, "htu": htu, "iat": iat, "jti": "dpop-1"})
}

// --- backends ---

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
			t.Errorf("gateway emitted INV3-violating receipt: %s/%s", rec.Decision.Verdict, rec.Verdict.State)
		}
		if rec.ReceiptHash == "" {
			t.Errorf("emitted receipt with no receipt_hash")
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

// harness wires a gateway to a broker key + JWKS + containment + ledger.
type harness struct {
	s    *server
	key  *rsa.PrivateKey
	kid  string
	led  *capturingLedger
	jwks *httptest.Server
	cont *httptest.Server
}

func newHarness(t *testing.T, proved bool) *harness {
	key, _ := rsa.GenerateKey(rand.Reader, 2048)
	kid := kidOf(&key.PublicKey)
	jwks := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{"keys": []map[string]any{rsaJWK(&key.PublicKey, kid)}})
	}))
	cont := fakeContainment(proved)
	led := newCapturingLedger(t)
	s := newServer(config{
		containmentURL: cont.URL, ledgerURL: led.srv.URL,
		brokerJWKSURL: jwks.URL, brokerIssuer: testIssuer, invokePath: "/mcp/invoke",
	})
	t.Cleanup(func() { jwks.Close(); cont.Close(); led.srv.Close() })
	return &harness{s: s, key: key, kid: kid, led: led, jwks: jwks, cont: cont}
}

func severTool() toolReq {
	return toolReq{Name: "sever_endpoint", Audience: "mcp://gbrg-containment", RequiredScope: "containment:sever:full"}
}

func (h *harness) invoke(t *testing.T, token, dpop string) *httptest.ResponseRecorder {
	t.Helper()
	b, _ := json.Marshal(invokeReq{LeaseToken: token, Tool: severTool(), Params: map[string]any{"scope": "full"}})
	req := httptest.NewRequest(http.MethodPost, "/mcp/invoke", bytes.NewReader(b))
	if dpop != "" {
		req.Header.Set("DPoP", dpop)
	}
	rr := httptest.NewRecorder()
	h.s.mux().ServeHTTP(rr, req)
	return rr
}

func TestAllowSeverProducesVerifiedReceipt(t *testing.T) {
	h := newHarness(t, true)
	rr := h.invoke(t, mintLease(h.key, h.kid, a4Claims()), "")
	if rr.Code != http.StatusOK {
		t.Fatalf("want 200, got %d: %s", rr.Code, rr.Body.String())
	}
	var out map[string]any
	_ = json.Unmarshal(rr.Body.Bytes(), &out)
	if out["admitted"] != true || out["verdict"] != "verified" {
		t.Fatalf("want admitted+verified, got %v", out)
	}
	if h.led.last().Decision.Verdict != "allow" || h.led.last().Verdict.State != "verified" {
		t.Fatalf("ledger did not record allow/verified: %+v", h.led.last())
	}
}

func TestNoOpSeverIsPendingNotVerified(t *testing.T) {
	h := newHarness(t, false)
	rr := h.invoke(t, mintLease(h.key, h.kid, a4Claims()), "")
	var out map[string]any
	_ = json.Unmarshal(rr.Body.Bytes(), &out)
	if out["verdict"] != "pending" {
		t.Fatalf("no-op sever must be pending, got %v", out["verdict"])
	}
}

func TestUnauthenticatedTokensRejected(t *testing.T) {
	h := newHarness(t, true)
	// wrong signing key
	badKey, _ := rsa.GenerateKey(rand.Reader, 2048)
	// expired
	exp := a4Claims()
	exp["exp"] = time.Now().Add(-time.Second).Unix()
	// wrong issuer
	wi := a4Claims()
	tok := mintLease(h.key, h.kid, wi)
	// tamper: flip last char of signature
	tampered := tok[:len(tok)-1] + map[bool]string{true: "A", false: "B"}[tok[len(tok)-1] != 'A']

	cases := map[string]string{
		"wrong key":    mintLease(badKey, kidOf(&badKey.PublicKey), a4Claims()),
		"expired":      mintLease(h.key, h.kid, exp),
		"tampered sig": tampered,
		"not a jws":    "not-a-token",
	}
	for name, token := range cases {
		t.Run(name, func(t *testing.T) {
			rr := h.invoke(t, token, "")
			if rr.Code != http.StatusUnauthorized {
				t.Fatalf("%s: want 401, got %d: %s", name, rr.Code, rr.Body.String())
			}
			if h.led.last().Verdict.State != "denied" {
				t.Fatalf("%s: invalid token must be audited as denied", name)
			}
		})
	}
}

func TestAuthorizationDenials(t *testing.T) {
	h := newHarness(t, true)
	mut := func(f func(map[string]any)) string {
		c := a4Claims()
		f(c)
		return mintLease(h.key, h.kid, c)
	}
	cases := map[string]string{
		"containment below A4": mut(func(c map[string]any) { c["risk_class"] = "A2" }),
		"audience mismatch":    mut(func(c map[string]any) { c["aud"] = "mcp://openproject" }),
		"scope not covered":    mut(func(c map[string]any) { c["scope"] = []string{"read:executions"} }),
		"missing case binding": mut(func(c map[string]any) { c["case_id"] = "" }),
	}
	for name, token := range cases {
		t.Run(name, func(t *testing.T) {
			rr := h.invoke(t, token, "")
			if rr.Code != http.StatusForbidden {
				t.Fatalf("%s: want 403, got %d: %s", name, rr.Code, rr.Body.String())
			}
			if h.led.last().Decision.Verdict != "block" || h.led.last().Verdict.State != "denied" {
				t.Fatalf("%s: denial not audited: %+v", name, h.led.last())
			}
		})
	}
}

func TestDPoPBinding(t *testing.T) {
	h := newHarness(t, true)
	dpopKey, _ := rsa.GenerateKey(rand.Reader, 2048)
	jkt := kidOf(&dpopKey.PublicKey)
	claims := a4Claims()
	claims["dpop_jkt"] = jkt
	token := mintLease(h.key, h.kid, claims)
	htu := "https://gw.test/mcp/invoke"
	now := time.Now().Unix()

	// no DPoP header → 401
	if rr := h.invoke(t, token, ""); rr.Code != http.StatusUnauthorized {
		t.Fatalf("missing DPoP must 401, got %d", rr.Code)
	}
	// valid DPoP → 200
	if rr := h.invoke(t, token, dpopProof(dpopKey, "POST", htu, now)); rr.Code != http.StatusOK {
		t.Fatalf("valid DPoP must 200, got %d: %s", rr.Code, rr.Body.String())
	}
	// DPoP signed by a DIFFERENT key (thumbprint mismatch) → 401
	otherKey, _ := rsa.GenerateKey(rand.Reader, 2048)
	if rr := h.invoke(t, token, dpopProof(otherKey, "POST", htu, now)); rr.Code != http.StatusUnauthorized {
		t.Fatalf("mismatched DPoP key must 401, got %d", rr.Code)
	}
	// DPoP with stale iat → 401
	if rr := h.invoke(t, token, dpopProof(dpopKey, "POST", htu, now-1000)); rr.Code != http.StatusUnauthorized {
		t.Fatalf("stale DPoP iat must 401, got %d", rr.Code)
	}
}

func TestSessionTeardown(t *testing.T) {
	s := newServer(config{brokerJWKSURL: "http://unused"})
	s.sessions["mcp-sess-x"] = "agent:y"
	req := httptest.NewRequest(http.MethodDelete, "/mcp/session", nil)
	req.Header.Set("MCP-Session-Id", "mcp-sess-x")
	rr := httptest.NewRecorder()
	s.mux().ServeHTTP(rr, req)
	if rr.Code != http.StatusOK {
		t.Fatalf("want 200, got %d", rr.Code)
	}
	if _, ok := s.sessions["mcp-sess-x"]; ok {
		t.Fatal("session not torn down")
	}
}

func TestProtectedResourceMetadata(t *testing.T) {
	s := newServer(config{resource: "https://agents.test/mcp", authServer: "https://auth.test/realms/wordops", brokerJWKSURL: "http://unused"})
	req := httptest.NewRequest(http.MethodGet, "/.well-known/oauth-protected-resource", nil)
	rr := httptest.NewRecorder()
	s.mux().ServeHTTP(rr, req)
	var out map[string]any
	if err := json.Unmarshal(rr.Body.Bytes(), &out); err != nil {
		t.Fatalf("bad json: %v", err)
	}
	if out["authorization_servers"] == nil || out["resource"] == nil {
		t.Fatalf("PRM missing fields: %v", out)
	}
}
