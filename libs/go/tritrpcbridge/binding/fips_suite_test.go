package binding

import (
	"testing"

	"github.com/SocioProphet/prophet-platform/libs/go/tritrpcbridge/tritrpcv1"
)

func fipsFrame(t *testing.T, key [32]byte, nonce [24]byte, payload string) []byte {
	t.Helper()
	frame, _, err := tritrpcv1.EnvelopeWithTagMode(tritrpcv1.ModeHMACSHA256, HealthService, HealthPingReq, []byte(payload), nil, key, nonce)
	if err != nil {
		t.Fatalf("encode fips frame: %v", err)
	}
	return frame
}

// The FIPS suite (HMAC-SHA256) round-trips, decodes as Mode 1, and carries a 32-byte tag.
func TestFIPSSuiteRoundTrip(t *testing.T) {
	key := DefaultDevKey()
	var nonce [24]byte
	for i := range nonce {
		nonce[i] = byte(i + 1)
	}
	frame := fipsFrame(t, key, nonce, `{"ts_unix_ms":7}`)
	env, err := VerifyEnvelope(frame, nonce, key)
	if err != nil {
		t.Fatalf("verify fips: %v", err)
	}
	mode, err := tritrpcv1.CryptoMode(env)
	if err != nil || mode != tritrpcv1.ModeHMACSHA256 {
		t.Fatalf("expected mode %d, got %d (err %v)", tritrpcv1.ModeHMACSHA256, mode, err)
	}
	if len(env.Tag) != 32 {
		t.Fatalf("expected 32-byte HMAC-SHA256 tag, got %d", len(env.Tag))
	}
	if env.Service != HealthService || env.Method != HealthPingReq {
		t.Fatalf("unexpected route: %s %s", env.Service, env.Method)
	}
}

// Any tamper in the authenticated envelope fails verification (fail-closed).
func TestFIPSSuiteTamperRejected(t *testing.T) {
	key := DefaultDevKey()
	var nonce [24]byte
	frame := fipsFrame(t, key, nonce, `{"a":1}`)
	frame[len(frame)/2] ^= 0xFF
	if _, err := VerifyEnvelope(frame, nonce, key); err == nil {
		t.Fatal("expected tampered fips frame to be rejected")
	}
}

// A different shared key fails verification.
func TestFIPSSuiteWrongKeyRejected(t *testing.T) {
	key := DefaultDevKey()
	var other [32]byte
	for i := range other {
		other[i] = byte(255 - i)
	}
	var nonce [24]byte
	frame := fipsFrame(t, key, nonce, `{"a":1}`)
	if _, err := VerifyEnvelope(frame, nonce, other); err == nil {
		t.Fatal("expected wrong key to be rejected")
	}
}

// The transmitted record-header nonce is authenticated: flipping it fails verification.
func TestFIPSSuiteNonceAuthenticated(t *testing.T) {
	key := DefaultDevKey()
	var nonce [24]byte
	frame := fipsFrame(t, key, nonce, `{"a":1}`)
	var wrong [24]byte
	wrong[0] = 0x01
	if _, err := VerifyEnvelope(frame, wrong, key); err == nil {
		t.Fatal("expected altered record nonce to be rejected (nonce is authenticated)")
	}
}

// The classic suite still round-trips and reports Mode 0 (regression: default unchanged).
func TestClassicSuiteUnchanged(t *testing.T) {
	key := DefaultDevKey()
	var nonce [24]byte
	for i := range nonce {
		nonce[i] = byte(i)
	}
	frame, _, err := tritrpcv1.EnvelopeWithTag(HealthService, HealthPingReq, []byte(`{"x":1}`), nil, key, nonce)
	if err != nil {
		t.Fatalf("encode classic: %v", err)
	}
	env, err := VerifyEnvelope(frame, nonce, key)
	if err != nil {
		t.Fatalf("verify classic: %v", err)
	}
	if mode, _ := tritrpcv1.CryptoMode(env); mode != tritrpcv1.ModeXChaCha20Poly1305 {
		t.Fatalf("classic suite should be mode 0, got %d", mode)
	}
	if len(env.Tag) != 16 {
		t.Fatalf("expected 16-byte Poly1305 tag, got %d", len(env.Tag))
	}
}

// $TRITRPC_SUITE selects the outbound suite; default stays classic.
func TestCryptoSuiteModeSelection(t *testing.T) {
	t.Setenv("TRITRPC_SUITE", "")
	if CryptoSuiteMode() != tritrpcv1.ModeXChaCha20Poly1305 {
		t.Fatal("default suite must be classic (mode 0)")
	}
	t.Setenv("TRITRPC_SUITE", "fips")
	if CryptoSuiteMode() != tritrpcv1.ModeHMACSHA256 {
		t.Fatal("TRITRPC_SUITE=fips must select HMAC-SHA256 (mode 1)")
	}
	t.Setenv("TRITRPC_SUITE", "classic")
	if CryptoSuiteMode() != tritrpcv1.ModeXChaCha20Poly1305 {
		t.Fatal("TRITRPC_SUITE=classic must select mode 0")
	}
}
