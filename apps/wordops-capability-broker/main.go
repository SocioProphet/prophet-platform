// wordops-capability-broker — mints down-scoped, signed capability-leases (Go, stdlib-only).
//
// The issuance side of the WordOps lease fabric. It runs the A0–A4 approval-to-lease
// policy (allow_issue — the estate's own autonomy ladder, mirroring
// infra/wordops/opa/lease_policy.rego) and, on allow, mints a short-lived RS256-signed
// capability-lease JWT. The wordops-mcp-gateway verifies these against this broker's
// JWKS, so a lease can no longer be spoofed by hand-crafting JSON.
//
// Endpoints (bind 0.0.0.0:$PORT, default 8080):
//
//	GET  /healthz              — liveness/readiness
//	GET  /.well-known/jwks.json — public verify key(s) (RFC 7517)
//	POST /lease                — run allow_issue; on allow, mint a signed lease JWT
//
// Signing key: WORDOPS_BROKER_SIGNING_KEY (PEM PKCS#8 or PKCS#1 RSA private key). If
// unset, an ephemeral key is generated at boot (dev only — the JWKS still lets the
// gateway verify within the process lifetime). Production mounts a Secret.
package main

import (
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"log"
	"math/big"
	"net/http"
	"os"
	"time"
)

const issuer = "https://auth.socioprophet.ai/realms/wordops/wordops-capability-broker"

// ---------------------------------------------------------------------------
// A0–A4 issuance policy (mirror of wordops.authz.allow_issue)
// ---------------------------------------------------------------------------

type issueRequest struct {
	User struct {
		ID    string   `json:"id"`
		Roles []string `json:"roles"`
	} `json:"user"`
	Agent struct {
		ID string `json:"id"`
	} `json:"agent"`
	Request struct {
		Aud                 string   `json:"aud"`
		Scope               []string `json:"scope"`
		RiskClass           string   `json:"risk_class"`
		CaseID              string   `json:"case_id"`
		TaskID              string   `json:"task_id"`
		TTLSeconds          int      `json:"ttl_seconds"`
		ApprovalID          string   `json:"approval_id"`
		StepUpSatisfied     bool     `json:"step_up_satisfied"`
		BreakGlass          bool     `json:"break_glass"`
		BreakGlassPolicyRef string   `json:"break_glass_policy_ref"`
		DPoPJKT             string   `json:"dpop_jkt"`
	} `json:"request"`
}

var ttlCeiling = map[string]int{"A0": 900, "A1": 900, "A2": 120, "A3": 60, "A4": 30}

func hasRole(roles []string, allowed map[string]bool) bool {
	for _, r := range roles {
		if allowed[r] {
			return true
		}
	}
	return false
}

func allPrefixed(scopes []string, prefixes ...string) bool {
	for _, s := range scopes {
		ok := false
		for _, p := range prefixes {
			if len(s) >= len(p) && s[:len(p)] == p {
				ok = true
				break
			}
		}
		if !ok {
			return false
		}
	}
	return len(scopes) > 0
}

func isContainmentScope(scopes []string) bool {
	for _, s := range scopes {
		if len(s) >= 17 && s[:17] == "containment:sever" {
			return true
		}
	}
	return false
}

// allowIssue returns (true,"") when the broker may mint, else (false, reason).
func allowIssue(r issueRequest) (bool, string) {
	rc := r.Request.RiskClass
	ceil, known := ttlCeiling[rc]
	if !known {
		return false, "unknown risk_class " + rc
	}
	if r.Request.TTLSeconds <= 0 || r.Request.TTLSeconds > ceil {
		return false, fmt.Sprintf("ttl_seconds must be 1..%d for %s", ceil, rc)
	}
	if isContainmentScope(r.Request.Scope) && rc != "A4" {
		return false, "containment sever is intrinsically risk_class A4"
	}
	switch rc {
	case "A0":
		if !allPrefixed(r.Request.Scope, "read:") {
			return false, "A0 permits only read: scopes"
		}
	case "A1":
		if !allPrefixed(r.Request.Scope, "draft:", "propose:") {
			return false, "A1 permits only draft:/propose: scopes"
		}
	case "A2":
		if !hasRole(r.User.Roles, map[string]bool{"ops-operator": true, "ops-admin": true}) {
			return false, "A2 requires ops-operator/ops-admin"
		}
	case "A3":
		if !hasRole(r.User.Roles, map[string]bool{"change-approver": true, "ops-admin": true}) {
			return false, "A3 requires change-approver/ops-admin"
		}
		if r.Request.ApprovalID == "" || !r.Request.StepUpSatisfied {
			return false, "A3 requires approval_id and satisfied step-up"
		}
	case "A4":
		if !hasRole(r.User.Roles, map[string]bool{"responder": true, "incident-commander": true, "ops-admin": true}) {
			return false, "A4 requires responder/incident-commander/ops-admin"
		}
		authorized := r.Request.ApprovalID != "" || (r.Request.BreakGlass && r.Request.BreakGlassPolicyRef != "")
		if !authorized || !r.Request.StepUpSatisfied {
			return false, "A4 requires approval_id (or documented break-glass) and satisfied step-up"
		}
	}
	if r.Request.CaseID == "" || r.Request.TaskID == "" {
		return false, "case_id and task_id binding required"
	}
	return true, ""
}

// ---------------------------------------------------------------------------
// JOSE (RS256) — stdlib
// ---------------------------------------------------------------------------

func b64url(b []byte) string { return base64.RawURLEncoding.EncodeToString(b) }

// jwkThumbprint is the RFC 7638 SHA-256 thumbprint of an RSA public key.
func jwkThumbprint(pub *rsa.PublicKey) string {
	e := big.NewInt(int64(pub.E)).Bytes()
	canon := fmt.Sprintf(`{"e":%q,"kty":"RSA","n":%q}`, b64url(e), b64url(pub.N.Bytes()))
	sum := sha256.Sum256([]byte(canon))
	return b64url(sum[:])
}

func publicJWK(pub *rsa.PublicKey, kid string) map[string]any {
	e := big.NewInt(int64(pub.E)).Bytes()
	return map[string]any{
		"kty": "RSA", "use": "sig", "alg": "RS256", "kid": kid,
		"n": b64url(pub.N.Bytes()), "e": b64url(e),
	}
}

func signJWT(key *rsa.PrivateKey, kid string, claims map[string]any) (string, error) {
	header := map[string]any{"alg": "RS256", "typ": "JWT", "kid": kid}
	hb, _ := json.Marshal(header)
	cb, _ := json.Marshal(claims)
	signingInput := b64url(hb) + "." + b64url(cb)
	sum := sha256.Sum256([]byte(signingInput))
	sig, err := rsa.SignPKCS1v15(rand.Reader, key, crypto.SHA256, sum[:])
	if err != nil {
		return "", err
	}
	return signingInput + "." + b64url(sig), nil
}

// ---------------------------------------------------------------------------
// server
// ---------------------------------------------------------------------------

type broker struct {
	key *rsa.PrivateKey
	kid string
}

func loadOrGenerateKey() (*rsa.PrivateKey, error) {
	pemStr := os.Getenv("WORDOPS_BROKER_SIGNING_KEY")
	if pemStr == "" {
		log.Printf("WARNING: no WORDOPS_BROKER_SIGNING_KEY set — generating an EPHEMERAL dev key")
		return rsa.GenerateKey(rand.Reader, 2048)
	}
	block, _ := pem.Decode([]byte(pemStr))
	if block == nil {
		return nil, fmt.Errorf("WORDOPS_BROKER_SIGNING_KEY is not valid PEM")
	}
	if k, err := x509.ParsePKCS1PrivateKey(block.Bytes); err == nil {
		return k, nil
	}
	k, err := x509.ParsePKCS8PrivateKey(block.Bytes)
	if err != nil {
		return nil, fmt.Errorf("unsupported private key: %w", err)
	}
	rk, ok := k.(*rsa.PrivateKey)
	if !ok {
		return nil, fmt.Errorf("signing key must be RSA")
	}
	return rk, nil
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}

func (b *broker) handleJWKS(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{"keys": []map[string]any{publicJWK(&b.key.PublicKey, b.kid)}})
}

func (b *broker) handleLease(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.Header().Set("Allow", "POST")
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{"error": "method not allowed"})
		return
	}
	var req issueRequest
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<20)).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid JSON: " + err.Error()})
		return
	}
	if ok, reason := allowIssue(req); !ok {
		writeJSON(w, http.StatusForbidden, map[string]any{"issued": false, "reason": reason})
		return
	}
	now := time.Now().UTC()
	exp := now.Add(time.Duration(req.Request.TTLSeconds) * time.Second)
	jti := newJTI()
	claims := map[string]any{
		"iss": issuer, "sub": req.Agent.ID, "act": req.User.ID,
		"aud": req.Request.Aud, "scope": req.Request.Scope,
		"case_id": req.Request.CaseID, "task_id": req.Request.TaskID,
		"risk_class": req.Request.RiskClass, "approval_id": req.Request.ApprovalID,
		"nbf": now.Unix(), "exp": exp.Unix(), "iat": now.Unix(), "jti": jti,
	}
	if req.Request.DPoPJKT != "" {
		claims["dpop_jkt"] = req.Request.DPoPJKT // bind the lease to the caller's DPoP key
	}
	token, err := signJWT(b.key, b.kid, claims)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "sign failed"})
		return
	}
	writeJSON(w, http.StatusCreated, map[string]any{
		"issued": true, "lease_token": token, "jti": jti,
		"expires_at": exp.Format(time.RFC3339), "risk_class": req.Request.RiskClass,
	})
}

func newJTI() string {
	var b [12]byte
	_, _ = rand.Read(b[:])
	var n uint64
	n = binary.BigEndian.Uint64(b[:8])
	return "lease_" + fmt.Sprintf("%x", n)
}

func (b *broker) mux() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "service": "wordops-capability-broker", "kid": b.kid})
	})
	mux.HandleFunc("/.well-known/jwks.json", b.handleJWKS)
	mux.HandleFunc("/lease", b.handleLease)
	return mux
}

func main() {
	key, err := loadOrGenerateKey()
	if err != nil {
		log.Fatal(err)
	}
	b := &broker{key: key, kid: jwkThumbprint(&key.PublicKey)}
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	log.Printf("wordops-capability-broker serving on :%s (kid=%s)", port, b.kid)
	if err := http.ListenAndServe("0.0.0.0:"+port, b.mux()); err != nil {
		log.Fatal(err)
	}
}
