package main

import (
	"bytes"
	"crypto"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"math/big"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func testBroker(t *testing.T) *broker {
	t.Helper()
	k, err := loadOrGenerateKey()
	if err != nil {
		t.Fatal(err)
	}
	return &broker{key: k, kid: jwkThumbprint(&k.PublicKey)}
}

func a4IssueReq() issueRequest {
	var r issueRequest
	r.User.ID = "user:responder"
	r.User.Roles = []string{"responder"}
	r.Agent.ID = "agent:containment"
	r.Request.Aud = "mcp://gbrg-containment"
	r.Request.Scope = []string{"containment:sever:full"}
	r.Request.RiskClass = "A4"
	r.Request.CaseID = "CASE-INC-1"
	r.Request.TaskID = "TASK-1"
	r.Request.TTLSeconds = 30
	r.Request.ApprovalID = "APR-INC-1"
	r.Request.StepUpSatisfied = true
	r.Request.DPoPJKT = "thumb-abc"
	return r
}

func TestAllowIssueMatrix(t *testing.T) {
	ok := func(mut func(*issueRequest)) bool {
		r := a4IssueReq()
		mut(&r)
		allow, _ := allowIssue(r)
		return allow
	}
	if !ok(func(r *issueRequest) {}) {
		t.Fatal("valid A4 must issue")
	}
	if ok(func(r *issueRequest) { r.Request.RiskClass = "A2" }) {
		t.Fatal("containment below A4 must be denied")
	}
	if ok(func(r *issueRequest) { r.Request.TTLSeconds = 31 }) {
		t.Fatal("A4 ttl over 30 must be denied")
	}
	if ok(func(r *issueRequest) { r.Request.ApprovalID = ""; r.Request.BreakGlass = false }) {
		t.Fatal("A4 without approval or break-glass must be denied")
	}
	if !ok(func(r *issueRequest) {
		r.Request.ApprovalID = ""
		r.Request.BreakGlass = true
		r.Request.BreakGlassPolicyRef = "policy://break-glass/v1"
	}) {
		t.Fatal("A4 break-glass with policy ref must issue")
	}
	if ok(func(r *issueRequest) { r.User.Roles = []string{"intern"} }) {
		t.Fatal("A4 without responder role must be denied")
	}
	if ok(func(r *issueRequest) { r.Request.CaseID = "" }) {
		t.Fatal("missing case binding must be denied")
	}
}

// verifyWithJWKS reconstructs the RSA key from the broker's JWKS and verifies the JWT.
func verifyWithJWKS(t *testing.T, b *broker, token string) map[string]any {
	t.Helper()
	jwks := httptest.NewRecorder()
	b.mux().ServeHTTP(jwks, httptest.NewRequest(http.MethodGet, "/.well-known/jwks.json", nil))
	var ks struct {
		Keys []struct{ N, E, Kid string } `json:"keys"`
	}
	if err := json.Unmarshal(jwks.Body.Bytes(), &ks); err != nil || len(ks.Keys) == 0 {
		t.Fatalf("bad jwks: %v", err)
	}
	nb, _ := base64.RawURLEncoding.DecodeString(ks.Keys[0].N)
	eb, _ := base64.RawURLEncoding.DecodeString(ks.Keys[0].E)
	pub := &rsa.PublicKey{N: new(big.Int).SetBytes(nb), E: int(new(big.Int).SetBytes(eb).Int64())}

	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		t.Fatalf("token not a JWS: %q", token)
	}
	sum := sha256.Sum256([]byte(parts[0] + "." + parts[1]))
	sig, _ := base64.RawURLEncoding.DecodeString(parts[2])
	if err := rsa.VerifyPKCS1v15(pub, crypto.SHA256, sum[:], sig); err != nil {
		t.Fatalf("signature does NOT verify against JWKS: %v", err)
	}
	cb, _ := base64.RawURLEncoding.DecodeString(parts[1])
	var claims map[string]any
	_ = json.Unmarshal(cb, &claims)
	return claims
}

func TestLeaseMintedTokenVerifies(t *testing.T) {
	b := testBroker(t)
	body, _ := json.Marshal(a4IssueReq())
	rr := httptest.NewRecorder()
	b.mux().ServeHTTP(rr, httptest.NewRequest(http.MethodPost, "/lease", bytes.NewReader(body)))
	if rr.Code != http.StatusCreated {
		t.Fatalf("want 201, got %d: %s", rr.Code, rr.Body.String())
	}
	var out struct {
		Issued     bool   `json:"issued"`
		LeaseToken string `json:"lease_token"`
	}
	_ = json.Unmarshal(rr.Body.Bytes(), &out)
	if !out.Issued || out.LeaseToken == "" {
		t.Fatalf("no token issued: %s", rr.Body.String())
	}
	claims := verifyWithJWKS(t, b, out.LeaseToken)
	if claims["aud"] != "mcp://gbrg-containment" || claims["risk_class"] != "A4" || claims["dpop_jkt"] != "thumb-abc" {
		t.Fatalf("claims wrong: %v", claims)
	}
	if claims["case_id"] != "CASE-INC-1" {
		t.Fatalf("case binding lost: %v", claims)
	}
}

func TestLeaseDeniedBelowA4(t *testing.T) {
	b := testBroker(t)
	r := a4IssueReq()
	r.Request.RiskClass = "A2"
	body, _ := json.Marshal(r)
	rr := httptest.NewRecorder()
	b.mux().ServeHTTP(rr, httptest.NewRequest(http.MethodPost, "/lease", bytes.NewReader(body)))
	if rr.Code != http.StatusForbidden {
		t.Fatalf("want 403, got %d", rr.Code)
	}
}
