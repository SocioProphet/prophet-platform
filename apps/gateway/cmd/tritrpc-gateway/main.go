package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io"
    "log"
    "net/http"
    "net/url"
    "os"
    "strings"
    "time"

    "github.com/SocioProphet/prophet-platform/libs/go/tritrpcbridge/binding"
)

const defaultUnixSocket = "/tmp/socioprophet.sock"
const defaultWorkroomReportJSON = "tests/fixtures/workroom/reports/devsecops-workroom-report.v0.1.json"
const defaultWorkroomReportMarkdown = "tests/fixtures/workroom/reports/devsecops-workroom-report.v0.1.md"

func main() {
    key, err := binding.ResolveSharedKey(os.Getenv("TRITRPC_KEY_HEX"), os.Getenv("TRITRPC_ALLOW_INSECURE_DEV_KEY") == "1")
    if err != nil {
        log.Fatalf("shared key: %v", err)
    }

    target := firstNonEmpty(os.Getenv("TRITRPC_TARGET_ADDR"), legacySockAddr())
    port := getenv("GATEWAY_PORT", "8080")
    evidenceBase := strings.TrimRight(strings.TrimSpace(os.Getenv("EVIDENCE_RECEIPTS_BASE_URL")), "/")
    consoleBase := strings.TrimRight(strings.TrimSpace(os.Getenv("EVIDENCE_CONSOLE_BASE_URL")), "/")
    client := &http.Client{Timeout: 5 * time.Second}

    mux := newMux(target, key, evidenceBase, consoleBase, client)
    log.Printf("Gateway listening on :%s (TriTRPC v1 -> %s, evidence -> %s, console -> %s)", port, target, evidenceBase, consoleBase)
    log.Fatal(http.ListenAndServe(":"+port, mux))
}

func newMux(target string, key [32]byte, evidenceBase string, consoleBase string, client *http.Client) *http.ServeMux {
    mux := http.NewServeMux()

    mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
        pong, err := ping(target, key)
        if err != nil {
            log.Printf("health ping error: %v", err)
            w.WriteHeader(http.StatusBadGateway)
            _ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": err.Error()})
            return
        }
        _ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "pong": pong.Pong, "service": pong.Service})
    })

    mux.HandleFunc("/v1/validate-change", func(w http.ResponseWriter, r *http.Request) {
        resp, err := validateChange(target, key, r)
        if err != nil {
            log.Printf("validate_change error: %v", err)
            w.WriteHeader(http.StatusBadGateway)
            _ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": err.Error()})
            return
        }
        w.Header().Set("Content-Type", "application/json")
        _, _ = w.Write(resp)
    })

    mux.HandleFunc("/v1/workroom/report", serveStaticReport(
        getenv("WORKROOM_REPORT_JSON_PATH", defaultWorkroomReportJSON),
        "application/json",
        true,
    ))
    mux.HandleFunc("/v1/workroom/report.md", serveStaticReport(
        getenv("WORKROOM_REPORT_MARKDOWN_PATH", defaultWorkroomReportMarkdown),
        "text/markdown; charset=utf-8",
        false,
    ))

    if evidenceBase != "" {
        mux.HandleFunc("/v1/evidence/services", proxyGET(client, evidenceBase, "/v1/services"))
        mux.HandleFunc("/v1/evidence/receipts/recent", proxyGET(client, evidenceBase, "/v1/receipts/recent"))
        mux.HandleFunc("/v1/evidence/catalog/recent", proxyGET(client, evidenceBase, "/v1/catalog/recent"))
        mux.HandleFunc("/v1/evidence/receipts/", proxyDynamicGET(client, evidenceBase, "/v1/receipts/", "/v1/evidence/receipts/"))
    }

    if consoleBase != "" {
        mux.HandleFunc("/v1/console/frontier", proxyGET(client, consoleBase, "/v1/console/frontier"))
        mux.HandleFunc("/v1/console/coverage", proxyGET(client, consoleBase, "/v1/console/coverage"))
        mux.HandleFunc("/v1/console/fogstack/validation", proxyGET(client, consoleBase, "/v1/console/fogstack/validation"))
        mux.HandleFunc("/v1/console/recent-events", proxyGET(client, consoleBase, "/v1/console/recent-events"))
        mux.HandleFunc("/v1/console/telemetry", proxyGET(client, consoleBase, "/v1/console/telemetry"))
        mux.HandleFunc("/v1/console/models/", proxyDynamicGET(client, consoleBase, "/v1/console/models/", "/v1/console/models/"))
        mux.HandleFunc("/console/evidence", proxyGET(client, consoleBase, "/console/evidence"))
    }

    return mux
}

func serveStaticReport(path string, contentType string, requireValidJSON bool) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        if r.Method != http.MethodGet {
            w.WriteHeader(http.StatusMethodNotAllowed)
            return
        }
        body, err := os.ReadFile(path)
        if err != nil {
            w.WriteHeader(http.StatusNotFound)
            _ = json.NewEncoder(w).Encode(map[string]any{
                "ok": false,
                "error": err.Error(),
                "non_claims": []string{
                    "Workroom report route serves fixture artifacts only.",
                    "Workroom report route does not execute infrastructure.",
                    "Workroom report route does not authorize remediation.",
                    "Workroom report route does not certify Signadot feature parity.",
                },
            })
            return
        }
        if requireValidJSON && !json.Valid(body) {
            w.WriteHeader(http.StatusInternalServerError)
            _ = json.NewEncoder(w).Encode(map[string]any{
                "ok": false,
                "error": "configured Workroom report JSON is invalid",
                "non_claims": []string{
                    "Workroom report route serves fixture artifacts only.",
                    "Workroom report route does not execute infrastructure.",
                    "Workroom report route does not authorize remediation.",
                    "Workroom report route does not certify Signadot feature parity.",
                },
            })
            return
        }
        w.Header().Set("Content-Type", contentType)
        w.Header().Set("X-Workroom-Report-Mode", "fixture")
        w.Header().Set("X-Workroom-Non-Claim", "no-execution-no-remediation-no-signadot-parity")
        _, _ = w.Write(body)
    }
}

func proxyGET(client *http.Client, baseURL, path string) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        target := baseURL + path
        if raw := r.URL.RawQuery; raw != "" {
            target += "?" + raw
        }
        doProxyGET(client, target, w, r)
    }
}

func proxyDynamicGET(client *http.Client, baseURL, upstreamPrefix, routePrefix string) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        suffix := strings.TrimPrefix(r.URL.Path, routePrefix)
        if suffix == r.URL.Path {
            http.NotFound(w, r)
            return
        }
        target := baseURL + upstreamPrefix + suffix
        if raw := r.URL.RawQuery; raw != "" {
            target += "?" + raw
        }
        doProxyGET(client, target, w, r)
    }
}

func doProxyGET(client *http.Client, target string, w http.ResponseWriter, r *http.Request) {
    if r.Method != http.MethodGet {
        w.WriteHeader(http.StatusMethodNotAllowed)
        return
    }
    req, err := http.NewRequestWithContext(r.Context(), http.MethodGet, target, nil)
    if err != nil {
        w.WriteHeader(http.StatusBadGateway)
        _ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": err.Error()})
        return
    }
    resp, err := client.Do(req)
    if err != nil {
        w.WriteHeader(http.StatusBadGateway)
        _ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": err.Error()})
        return
    }
    defer resp.Body.Close()
    for k, vals := range resp.Header {
        for _, v := range vals {
            w.Header().Add(k, v)
        }
    }
    w.WriteHeader(resp.StatusCode)
    _, _ = io.Copy(w, resp.Body)
}

func ping(target string, key [32]byte) (*binding.HealthPingResponse, error) {
    c, resolved, err := binding.Dial(target, defaultUnixSocket)
    if err != nil {
        return nil, err
    }
    defer c.Close()

    req := binding.HealthPingRequest{TsUnixMs: time.Now().UnixMilli()}
    nonce, frame, err := binding.MarshalJSONFrame(binding.HealthService, binding.HealthPingReq, req, key)
    if err != nil {
        return nil, err
    }
    if err := binding.WriteRecord(c, nonce, frame); err != nil {
        return nil, err
    }

    respNonce, respFrame, err := binding.ReadRecord(c)
    if err != nil {
        return nil, err
    }
    env, err := binding.VerifyEnvelope(respFrame, respNonce, key)
    if err != nil {
        return nil, err
    }
    if env.Service != binding.HealthService || env.Method != binding.HealthPingRes {
        return nil, fmt.Errorf("unexpected route from %s: %s %s", resolved, env.Service, env.Method)
    }
    var resp binding.HealthPingResponse
    if err := binding.DecodeJSONPayload(env, &resp); err != nil {
        return nil, err
    }
    return &resp, nil
}

func validateChange(target string, key [32]byte, r *http.Request) ([]byte, error) {
    if r.Method != http.MethodPost {
        return nil, fmt.Errorf("method not allowed: %s", r.Method)
    }
    body, err := io.ReadAll(io.LimitReader(r.Body, binding.MaxFrameBytes))
    if err != nil {
        return nil, err
    }
    if !json.Valid(body) {
        return nil, fmt.Errorf("invalid JSON request body")
    }

    c, resolved, err := binding.Dial(target, defaultUnixSocket)
    if err != nil {
        return nil, err
    }
    defer c.Close()

    var payload map[string]any
    if err := json.NewDecoder(bytes.NewReader(body)).Decode(&payload); err != nil {
        return nil, err
    }
    nonce, frame, err := binding.MarshalJSONFrame(binding.ValidateChangeService, binding.ValidateChangeReq, payload, key)
    if err != nil {
        return nil, err
    }
    if err := binding.WriteRecord(c, nonce, frame); err != nil {
        return nil, err
    }

    respNonce, respFrame, err := binding.ReadRecord(c)
    if err != nil {
        return nil, err
    }
    env, err := binding.VerifyEnvelope(respFrame, respNonce, key)
    if err != nil {
        return nil, err
    }
    if env.Service != binding.ValidateChangeService || env.Method != binding.ValidateChangeRes {
        return nil, fmt.Errorf("unexpected validate_change route from %s: %s %s", resolved, env.Service, env.Method)
    }
    return env.Payload, nil
}

func legacySockAddr() string {
    if sock := strings.TrimSpace(os.Getenv("TRITRPC_SOCK")); sock != "" {
        return "unix://" + sock
    }
    return ""
}

func firstNonEmpty(vs ...string) string {
    for _, v := range vs {
        if strings.TrimSpace(v) != "" {
            return v
        }
    }
    return ""
}

func getenv(k, d string) string {
    if v := os.Getenv(k); v != "" {
        return v
    }
    return d
}

func mustParse(raw string) *url.URL {
    u, err := url.Parse(raw)
    if err != nil {
        panic(err)
    }
    return u
}
