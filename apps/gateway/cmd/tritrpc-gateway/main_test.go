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

    mux := newMux("tcp://127.0.0.1:9", [32]byte{}, upstream.URL, "", upstream.Client())
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

    mux := newMux("tcp://127.0.0.1:9", [32]byte{}, upstream.URL, "", upstream.Client())
    rr := httptest.NewRecorder()
    req := httptest.NewRequest(http.MethodGet, "/v1/evidence/receipts/eval-fabric-api/corr-123?verbose=1", nil)
    mux.ServeHTTP(rr, req)

    if rr.Code != http.StatusOK {
        t.Fatalf("unexpected status: %d", rr.Code)
    }
}

func TestConsoleFrontierProxy(t *testing.T) {
    upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        if r.URL.Path != "/v1/console/frontier" {
            t.Fatalf("unexpected path: %s", r.URL.Path)
        }
        _ = json.NewEncoder(w).Encode(map[string]any{"frontier": map[string]any{"ok": true}})
    }))
    defer upstream.Close()

    mux := newMux("tcp://127.0.0.1:9", [32]byte{}, "", upstream.URL, upstream.Client())
    rr := httptest.NewRecorder()
    req := httptest.NewRequest(http.MethodGet, "/v1/console/frontier", nil)
    mux.ServeHTTP(rr, req)

    if rr.Code != http.StatusOK {
        t.Fatalf("unexpected status: %d", rr.Code)
    }
}

func TestConsoleModelProxyPathAndQuery(t *testing.T) {
    upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        if r.URL.Path != "/v1/console/models/model.semantic-stack.2026-04-05" {
            t.Fatalf("unexpected path: %s", r.URL.Path)
        }
        if got := r.URL.Query().Get("limit"); got != "9" {
            t.Fatalf("missing query param, got %q", got)
        }
        _ = json.NewEncoder(w).Encode(map[string]any{"model_release_id": "model.semantic-stack.2026-04-05"})
    }))
    defer upstream.Close()

    mux := newMux("tcp://127.0.0.1:9", [32]byte{}, "", upstream.URL, upstream.Client())
    rr := httptest.NewRecorder()
    req := httptest.NewRequest(http.MethodGet, "/v1/console/models/model.semantic-stack.2026-04-05?limit=9", nil)
    mux.ServeHTTP(rr, req)

    if rr.Code != http.StatusOK {
        t.Fatalf("unexpected status: %d", rr.Code)
    }
}

func TestConsoleUIProxy(t *testing.T) {
    upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        if r.URL.Path != "/console/evidence" {
            t.Fatalf("unexpected path: %s", r.URL.Path)
        }
        _, _ = w.Write([]byte("<html>Evidence Console</html>"))
    }))
    defer upstream.Close()

    mux := newMux("tcp://127.0.0.1:9", [32]byte{}, "", upstream.URL, upstream.Client())
    rr := httptest.NewRecorder()
    req := httptest.NewRequest(http.MethodGet, "/console/evidence", nil)
    mux.ServeHTTP(rr, req)

    if rr.Code != http.StatusOK {
        t.Fatalf("unexpected status: %d", rr.Code)
    }
}

func TestEvidenceProxyDisabledReturns404(t *testing.T) {
    mux := newMux("tcp://127.0.0.1:9", [32]byte{}, "", "", http.DefaultClient)
    rr := httptest.NewRecorder()
    req := httptest.NewRequest(http.MethodGet, "/v1/evidence/services", nil)
    mux.ServeHTTP(rr, req)

    if rr.Code != http.StatusNotFound {
        t.Fatalf("expected 404 when evidence proxy disabled, got %d", rr.Code)
    }
}

func TestConsoleProxyDisabledReturns404(t *testing.T) {
    mux := newMux("tcp://127.0.0.1:9", [32]byte{}, "", "", http.DefaultClient)
    rr := httptest.NewRecorder()
    req := httptest.NewRequest(http.MethodGet, "/v1/console/frontier", nil)
    mux.ServeHTTP(rr, req)

    if rr.Code != http.StatusNotFound {
        t.Fatalf("expected 404 when console proxy disabled, got %d", rr.Code)
    }
}
