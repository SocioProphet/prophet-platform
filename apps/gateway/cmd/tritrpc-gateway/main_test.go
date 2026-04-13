package main

import (
    "encoding/json"
    "net/http"
    "net/http/httptest"
    "testing"
)

func TestEvidenceServicesProxy(t *testing.T) {
    upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        if r.URL.Path != "/v1/services" {
            t.Fatalf("unexpected path: %s", r.URL.Path)
        }
        _ = json.NewEncoder(w).Encode(map[string]any{"services": []string{"eval-fabric-api", "lampstand"}})
    }))
    defer upstream.Close()

    mux := newMux("tcp://127.0.0.1:9", [32]byte{}, upstream.URL, upstream.Client())
    rr := httptest.NewRecorder()
    req := httptest.NewRequest(http.MethodGet, "/v1/evidence/services", nil)
    mux.ServeHTTP(rr, req)

    if rr.Code != http.StatusOK {
        t.Fatalf("unexpected status: %d", rr.Code)
    }
    var payload map[string]any
    if err := json.Unmarshal(rr.Body.Bytes(), &payload); err != nil {
        t.Fatalf("decode response: %v", err)
    }
    if _, ok := payload["services"]; !ok {
        t.Fatalf("missing services field")
    }
}

func TestEvidenceReceiptProxyPathAndQuery(t *testing.T) {
    upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        if r.URL.Path != "/v1/receipts/eval-fabric-api/corr-123" {
            t.Fatalf("unexpected path: %s", r.URL.Path)
        }
        if got := r.URL.Query().Get("verbose"); got != "1" {
            t.Fatalf("missing query param, got %q", got)
        }
        _ = json.NewEncoder(w).Encode(map[string]any{"correlation_id": "corr-123"})
    }))
    defer upstream.Close()

    mux := newMux("tcp://127.0.0.1:9", [32]byte{}, upstream.URL, upstream.Client())
    rr := httptest.NewRecorder()
    req := httptest.NewRequest(http.MethodGet, "/v1/evidence/receipts/eval-fabric-api/corr-123?verbose=1", nil)
    mux.ServeHTTP(rr, req)

    if rr.Code != http.StatusOK {
        t.Fatalf("unexpected status: %d", rr.Code)
    }
}

func TestEvidenceProxyDisabledReturns404(t *testing.T) {
    mux := newMux("tcp://127.0.0.1:9", [32]byte{}, "", http.DefaultClient)
    rr := httptest.NewRecorder()
    req := httptest.NewRequest(http.MethodGet, "/v1/evidence/services", nil)
    mux.ServeHTTP(rr, req)

    if rr.Code != http.StatusNotFound {
        t.Fatalf("expected 404 when evidence proxy disabled, got %d", rr.Code)
    }
}
