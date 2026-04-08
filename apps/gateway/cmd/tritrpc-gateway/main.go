package main

import (
    "encoding/json"
    "fmt"
    "log"
    "net/http"
    "os"
    "strings"
    "time"

    "github.com/SocioProphet/prophet-platform/libs/go/tritrpcbridge/binding"
)

const defaultUnixSocket = "/tmp/socioprophet.sock"

func main() {
    key, err := binding.ResolveSharedKey(os.Getenv("TRITRPC_KEY_HEX"), os.Getenv("TRITRPC_ALLOW_INSECURE_DEV_KEY") == "1")
    if err != nil {
        log.Fatalf("shared key: %v", err)
    }

    target := firstNonEmpty(os.Getenv("TRITRPC_TARGET_ADDR"), legacySockAddr())
    port := getenv("GATEWAY_PORT", "8080")

    http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
        pong, err := ping(target, key)
        if err != nil {
            log.Printf("health ping error: %v", err)
            w.WriteHeader(http.StatusBadGateway)
            _ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": err.Error()})
            return
        }
        _ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "pong": pong.Pong, "service": pong.Service})
    })

    log.Printf("Gateway listening on :%s (TriTRPC v1 → %s)", port, target)
    log.Fatal(http.ListenAndServe(":"+port, nil))
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
