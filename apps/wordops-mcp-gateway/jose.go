package main

// jose.go — lease-token (JWS) verification against the broker JWKS, plus DPoP
// proof-of-possession (RFC 9449). This is the identity layer that makes the
// gateway's claim enforcement trustworthy: a lease is a broker-signed RS256 JWT,
// and (when the lease is DPoP-bound) the caller must prove possession of the key.
//
// stdlib-only. RSA/RS256 throughout (the estate's broker signs RSA; DPoP proofs
// are RSA here too). EC/ES256 is a mechanical addition if a client needs it.

import (
	"crypto"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"math/big"
	"net/http"
	"strings"
	"sync"
	"time"
)

func b64urlDecode(s string) ([]byte, error) { return base64.RawURLEncoding.DecodeString(s) }
func b64urlEncode(b []byte) string          { return base64.RawURLEncoding.EncodeToString(b) }

type jwk struct {
	Kty string `json:"kty"`
	Kid string `json:"kid"`
	N   string `json:"n"`
	E   string `json:"e"`
}

func (k jwk) rsaPublic() (*rsa.PublicKey, error) {
	if k.Kty != "RSA" {
		return nil, fmt.Errorf("unsupported kty %q", k.Kty)
	}
	nb, err := b64urlDecode(k.N)
	if err != nil {
		return nil, fmt.Errorf("bad n: %w", err)
	}
	eb, err := b64urlDecode(k.E)
	if err != nil {
		return nil, fmt.Errorf("bad e: %w", err)
	}
	return &rsa.PublicKey{N: new(big.Int).SetBytes(nb), E: int(new(big.Int).SetBytes(eb).Int64())}, nil
}

// rfc7638Thumbprint is the SHA-256 JWK thumbprint of an RSA JWK (must match the
// broker's jwkThumbprint and the `dpop_jkt` claim).
func (k jwk) rfc7638Thumbprint() string {
	canon := fmt.Sprintf(`{"e":%q,"kty":"RSA","n":%q}`, k.E, k.N)
	sum := sha256.Sum256([]byte(canon))
	return b64urlEncode(sum[:])
}

func verifyRS256(pub *rsa.PublicKey, signingInput, sigB64 string) error {
	sig, err := b64urlDecode(sigB64)
	if err != nil {
		return fmt.Errorf("bad signature encoding: %w", err)
	}
	sum := sha256.Sum256([]byte(signingInput))
	return rsa.VerifyPKCS1v15(pub, crypto.SHA256, sum[:], sig)
}

func splitJWS(token string) (header, payload, sig string, err error) {
	p := strings.Split(token, ".")
	if len(p) != 3 {
		return "", "", "", fmt.Errorf("not a compact JWS")
	}
	return p[0], p[1], p[2], nil
}

func decodeJSON(seg string, v any) error {
	b, err := b64urlDecode(seg)
	if err != nil {
		return err
	}
	return json.Unmarshal(b, v)
}

// ---------------------------------------------------------------------------
// JWKS cache
// ---------------------------------------------------------------------------

type jwksCache struct {
	url     string
	client  *http.Client
	mu      sync.Mutex
	keys    map[string]*rsa.PublicKey
	fetched time.Time
}

func newJWKSCache(url string, client *http.Client) *jwksCache {
	return &jwksCache{url: url, client: client, keys: map[string]*rsa.PublicKey{}}
}

func (c *jwksCache) refresh() error {
	resp, err := c.client.Get(c.url)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("jwks endpoint returned %d", resp.StatusCode)
	}
	var set struct {
		Keys []jwk `json:"keys"`
	}
	if err := json.Unmarshal(body, &set); err != nil {
		return err
	}
	next := map[string]*rsa.PublicKey{}
	for _, k := range set.Keys {
		if pub, err := k.rsaPublic(); err == nil {
			next[k.Kid] = pub
		}
	}
	c.mu.Lock()
	c.keys, c.fetched = next, time.Now()
	c.mu.Unlock()
	return nil
}

func (c *jwksCache) keyFor(kid string) (*rsa.PublicKey, error) {
	c.mu.Lock()
	pub, ok := c.keys[kid]
	stale := time.Since(c.fetched) > 5*time.Minute
	c.mu.Unlock()
	if ok && !stale {
		return pub, nil
	}
	if err := c.refresh(); err != nil && !ok {
		return nil, err
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	if pub, ok := c.keys[kid]; ok {
		return pub, nil
	}
	return nil, fmt.Errorf("no verify key for kid %q", kid)
}

// ---------------------------------------------------------------------------
// lease-token verification
// ---------------------------------------------------------------------------

type leaseClaims struct {
	Iss        string   `json:"iss"`
	Sub        string   `json:"sub"`
	Act        string   `json:"act"`
	Aud        string   `json:"aud"`
	Scope      []string `json:"scope"`
	CaseID     string   `json:"case_id"`
	TaskID     string   `json:"task_id"`
	RiskClass  string   `json:"risk_class"`
	ApprovalID string   `json:"approval_id"`
	DPoPJKT    string   `json:"dpop_jkt"`
	Nbf        int64    `json:"nbf"`
	Exp        int64    `json:"exp"`
	JTI        string   `json:"jti"`
}

// verifyLeaseToken checks signature (against the broker JWKS by kid), issuer, and
// the nbf/exp window, and returns the verified claims.
func (c *jwksCache) verifyLeaseToken(token, wantIssuer string, now time.Time) (*leaseClaims, error) {
	h, p, s, err := splitJWS(token)
	if err != nil {
		return nil, err
	}
	var hdr struct{ Alg, Kid, Typ string }
	if err := decodeJSON(h, &hdr); err != nil {
		return nil, fmt.Errorf("bad header: %w", err)
	}
	if hdr.Alg != "RS256" {
		return nil, fmt.Errorf("unexpected alg %q (want RS256)", hdr.Alg)
	}
	pub, err := c.keyFor(hdr.Kid)
	if err != nil {
		return nil, err
	}
	if err := verifyRS256(pub, h+"."+p, s); err != nil {
		return nil, fmt.Errorf("lease signature does not verify: %w", err)
	}
	var cl leaseClaims
	if err := decodeJSON(p, &cl); err != nil {
		return nil, fmt.Errorf("bad claims: %w", err)
	}
	if wantIssuer != "" && cl.Iss != wantIssuer {
		return nil, fmt.Errorf("unexpected issuer %q", cl.Iss)
	}
	nowU := now.Unix()
	if cl.Nbf != 0 && nowU < cl.Nbf {
		return nil, fmt.Errorf("lease not yet valid (nbf)")
	}
	if cl.Exp == 0 || nowU >= cl.Exp {
		return nil, fmt.Errorf("lease expired")
	}
	return &cl, nil
}

// ---------------------------------------------------------------------------
// DPoP proof-of-possession (RFC 9449)
// ---------------------------------------------------------------------------

// verifyDPoP checks a DPoP proof header: typ=dpop+jwt, self-signed by the embedded
// JWK, the JWK thumbprint equals wantJKT, htm/htu bind it to THIS request, and iat
// is fresh. Returns nil when the caller has proven possession of the bound key.
func verifyDPoP(proof, wantJKT, htm, htu string, now time.Time) error {
	if proof == "" {
		return fmt.Errorf("DPoP header required: lease is sender-constrained (dpop_jkt)")
	}
	h, p, s, err := splitJWS(proof)
	if err != nil {
		return fmt.Errorf("malformed DPoP proof: %w", err)
	}
	var hdr struct {
		Typ string `json:"typ"`
		Alg string `json:"alg"`
		JWK jwk    `json:"jwk"`
	}
	if err := decodeJSON(h, &hdr); err != nil {
		return fmt.Errorf("bad DPoP header: %w", err)
	}
	if hdr.Typ != "dpop+jwt" {
		return fmt.Errorf("DPoP proof typ must be dpop+jwt")
	}
	if hdr.Alg != "RS256" {
		return fmt.Errorf("DPoP alg %q unsupported (want RS256)", hdr.Alg)
	}
	pub, err := hdr.JWK.rsaPublic()
	if err != nil {
		return fmt.Errorf("bad DPoP jwk: %w", err)
	}
	if err := verifyRS256(pub, h+"."+p, s); err != nil {
		return fmt.Errorf("DPoP proof self-signature invalid: %w", err)
	}
	if got := hdr.JWK.rfc7638Thumbprint(); got != wantJKT {
		return fmt.Errorf("DPoP key thumbprint %q does not match lease dpop_jkt %q", got, wantJKT)
	}
	var cl struct {
		Htm string `json:"htm"`
		Htu string `json:"htu"`
		Iat int64  `json:"iat"`
		Jti string `json:"jti"`
	}
	if err := decodeJSON(p, &cl); err != nil {
		return fmt.Errorf("bad DPoP claims: %w", err)
	}
	if !strings.EqualFold(cl.Htm, htm) {
		return fmt.Errorf("DPoP htm %q != request method %q", cl.Htm, htm)
	}
	if !strings.HasSuffix(cl.Htu, htu) {
		return fmt.Errorf("DPoP htu %q does not bind this endpoint (%q)", cl.Htu, htu)
	}
	if cl.Iat == 0 || abs64(now.Unix()-cl.Iat) > 300 {
		return fmt.Errorf("DPoP proof iat not fresh")
	}
	return nil
}

func abs64(x int64) int64 {
	if x < 0 {
		return -x
	}
	return x
}
