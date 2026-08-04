package tritrpcv1

import (
	"crypto/hmac"
	"crypto/sha256"
	"errors"
	"fmt"

	"golang.org/x/crypto/chacha20poly1305"
)

var SCHEMA_ID_BYTES = []byte{178, 171, 129, 69, 136, 249, 156, 135, 93, 55, 187, 117, 70, 208, 223, 67, 105, 194, 139, 197, 246, 12, 227, 138, 102, 7, 218, 196, 104, 3, 67, 82}
var CONTEXT_ID_BYTES = []byte{230, 87, 44, 14, 97, 143, 24, 213, 114, 212, 194, 150, 157, 180, 144, 150, 89, 240, 158, 174, 243, 46, 198, 111, 187, 128, 75, 173, 157, 137, 170, 205}
var MAGIC_B2 = []byte{0xF3, 0x2A}
var SCHEMA_ID_32 = []byte{0xb2, 0xab, 0x81, 0x45, 0x88, 0xf9, 0x9c, 0x87, 0x5d, 0x37, 0xbb, 0x75, 0x46, 0xd0, 0xdf, 0x43, 0x69, 0xc2, 0x8b, 0xc5, 0xf6, 0x0c, 0xe3, 0x8a, 0x66, 0x07, 0xda, 0xc4, 0x68, 0x03, 0x43, 0x52}
var CONTEXT_ID_32 = []byte{0xe6, 0x57, 0x2c, 0x0e, 0x61, 0x8f, 0x18, 0xd5, 0x72, 0xd4, 0xc2, 0x96, 0x9d, 0xb4, 0x90, 0x96, 0x59, 0xf0, 0x9e, 0xae, 0xf3, 0x2e, 0xc6, 0x6f, 0xbb, 0x80, 0x4b, 0xad, 0x9d, 0x89, 0xaa, 0xcd}

// Crypto-suite selectors carried in the envelope Mode field. The wire format is identical across
// suites — the payload is always cleartext and the tag is length-prefixed — so only the tag
// algorithm differs and a decoder picks the verifier from the decoded Mode field.
const (
	// ModeXChaCha20Poly1305 is the classic (default) suite: golang.org/x/crypto XChaCha20-Poly1305.
	// NOT FIPS-approved, and x/crypto is never covered by a FIPS crypto module.
	ModeXChaCha20Poly1305 byte = 0
	// ModeHMACSHA256 authenticates the envelope with HMAC-SHA256 over nonce||AAD (FIPS 198-1 +
	// FIPS 180-4) using only the Go standard library, so it is covered by a FIPS crypto module
	// (e.g. BoringCrypto). Same shared key, same cleartext payload; nonce-free construction.
	ModeHMACSHA256 byte = 1
)

func flagsTrits(aead bool, compress bool) []byte {
	var a, c byte
	if aead {
		a = 2
	}
	if compress {
		c = 2
	}
	return []byte{a, c, 0}
}

func lenPrefix(b []byte) []byte {
	return TLEB3EncodeLen(uint64(len(b)))
}

// BuildEnvelope builds a classic (Mode 0) envelope — byte-for-byte unchanged from before.
func BuildEnvelope(service, method string, payload []byte, aux []byte, aeadTag []byte, aeadOn bool, compress bool) []byte {
	return BuildEnvelopeMode(ModeXChaCha20Poly1305, service, method, payload, aux, aeadTag, aeadOn, compress)
}

// BuildEnvelopeMode builds an envelope whose Mode field records the crypto suite `cryptoMode`.
func BuildEnvelopeMode(cryptoMode byte, service, method string, payload []byte, aux []byte, aeadTag []byte, aeadOn bool, compress bool) []byte {
	out := make([]byte, 0)
	out = append(out, lenPrefix(MAGIC_B2)...)
	out = append(out, MAGIC_B2...)

	ver := TritPack243([]byte{1})
	out = append(out, lenPrefix(ver)...)
	out = append(out, ver...)

	mode := TritPack243([]byte{cryptoMode})
	out = append(out, lenPrefix(mode)...)
	out = append(out, mode...)

	flags := TritPack243(flagsTrits(aeadOn, compress))
	out = append(out, lenPrefix(flags)...)
	out = append(out, flags...)

	schema := SCHEMA_ID_32
	context := CONTEXT_ID_32
	out = append(out, lenPrefix(schema)...)
	out = append(out, schema...)
	out = append(out, lenPrefix(context)...)
	out = append(out, context...)

	svc := []byte(service)
	out = append(out, lenPrefix(svc)...)
	out = append(out, svc...)

	m := []byte(method)
	out = append(out, lenPrefix(m)...)
	out = append(out, m...)

	out = append(out, lenPrefix(payload)...)
	out = append(out, payload...)

	if aux != nil {
		out = append(out, lenPrefix(aux)...)
		out = append(out, aux...)
	}
	if aeadTag != nil {
		out = append(out, lenPrefix(aeadTag)...)
		out = append(out, aeadTag...)
	}

	return out
}

// EnvelopeWithTag builds a classic XChaCha20-Poly1305 authenticated envelope (Mode 0).
func EnvelopeWithTag(service, method string, payload, aux []byte, key [32]byte, nonce [24]byte) ([]byte, []byte, error) {
	return EnvelopeWithTagMode(ModeXChaCha20Poly1305, service, method, payload, aux, key, nonce)
}

// EnvelopeWithTagMode builds an authenticated envelope using the crypto suite `cryptoMode`. In
// both suites the payload is carried in cleartext and the tag authenticates the whole envelope
// (AAD); the nonce is authenticated too, so a flipped record-header nonce is rejected.
func EnvelopeWithTagMode(cryptoMode byte, service, method string, payload, aux []byte, key [32]byte, nonce [24]byte) ([]byte, []byte, error) {
	aad := BuildEnvelopeMode(cryptoMode, service, method, payload, aux, nil, true, false)
	tag, err := ComputeTag(cryptoMode, key, nonce, aad)
	if err != nil {
		return nil, nil, err
	}
	frame := BuildEnvelopeMode(cryptoMode, service, method, payload, aux, tag, true, false)
	return frame, tag, nil
}

// ComputeTag produces the authentication tag over an envelope's AAD for the given suite.
func ComputeTag(cryptoMode byte, key [32]byte, nonce [24]byte, aad []byte) ([]byte, error) {
	switch cryptoMode {
	case ModeXChaCha20Poly1305:
		aead, err := chacha20poly1305.NewX(key[:])
		if err != nil {
			return nil, err
		}
		ct := aead.Seal(nil, nonce[:], []byte{}, aad)
		return ct[len(ct)-16:], nil
	case ModeHMACSHA256:
		mac := hmac.New(sha256.New, key[:])
		mac.Write(nonce[:])
		mac.Write(aad)
		return mac.Sum(nil), nil
	default:
		return nil, fmt.Errorf("tritrpcv1: unsupported crypto mode %d", cryptoMode)
	}
}

// VerifyTag checks an envelope tag for the given suite in constant time.
func VerifyTag(cryptoMode byte, key [32]byte, nonce [24]byte, aad, tag []byte) error {
	switch cryptoMode {
	case ModeXChaCha20Poly1305:
		aead, err := chacha20poly1305.NewX(key[:])
		if err != nil {
			return err
		}
		if _, err := aead.Open(nil, nonce[:], tag, aad); err != nil {
			return err
		}
		return nil
	case ModeHMACSHA256:
		want, err := ComputeTag(ModeHMACSHA256, key, nonce, aad)
		if err != nil {
			return err
		}
		if !hmac.Equal(tag, want) {
			return errors.New("tritrpcv1: hmac-sha256 tag mismatch")
		}
		return nil
	default:
		return fmt.Errorf("tritrpcv1: unsupported crypto mode %d", cryptoMode)
	}
}

// CryptoMode returns the crypto-suite selector recorded in a decoded envelope's Mode field.
func CryptoMode(env *Envelope) (byte, error) {
	trits, err := TritUnpack243(env.Mode)
	if err != nil {
		return 0, err
	}
	if len(trits) == 0 {
		return 0, errors.New("tritrpcv1: empty mode field")
	}
	return trits[0], nil
}
