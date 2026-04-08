package binding

import (
    "bytes"
    "testing"
)

func TestHealthRoundTrip(t *testing.T) {
    key := DefaultDevKey()
    req := HealthPingRequest{TsUnixMs: 123456789}
    nonce, frame, err := MarshalJSONFrame(HealthService, HealthPingReq, req, key)
    if err != nil {
        t.Fatalf("marshal frame: %v", err)
    }
    env, err := VerifyEnvelope(frame, nonce, key)
    if err != nil {
        t.Fatalf("verify: %v", err)
    }
    if env.Service != HealthService || env.Method != HealthPingReq {
        t.Fatalf("unexpected route: %s %s", env.Service, env.Method)
    }
    var out HealthPingRequest
    if err := DecodeJSONPayload(env, &out); err != nil {
        t.Fatalf("decode payload: %v", err)
    }
    if out.TsUnixMs != req.TsUnixMs {
        t.Fatalf("payload mismatch: got %d want %d", out.TsUnixMs, req.TsUnixMs)
    }
}

func TestRecordReadWrite(t *testing.T) {
    key := DefaultDevKey()
    nonce, frame, err := MarshalJSONFrame(HealthService, HealthPingRes, HealthPingResponse{Ok: true, Pong: "PONG", Service: "api"}, key)
    if err != nil {
        t.Fatalf("marshal frame: %v", err)
    }
    var buf bytes.Buffer
    if err := WriteRecord(&buf, nonce, frame); err != nil {
        t.Fatalf("write record: %v", err)
    }
    gotNonce, gotFrame, err := ReadRecord(&buf)
    if err != nil {
        t.Fatalf("read record: %v", err)
    }
    if gotNonce != nonce {
        t.Fatalf("nonce mismatch")
    }
    if !bytes.Equal(gotFrame, frame) {
        t.Fatalf("frame mismatch")
    }
}
