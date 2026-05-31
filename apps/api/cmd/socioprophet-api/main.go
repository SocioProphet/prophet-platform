package main

import (
    "encoding/json"
    "errors"
    "io"
    "log"
    "net"
    "os"
    "strings"

    "github.com/SocioProphet/prophet-platform/libs/go/tritrpcbridge/binding"
    "github.com/SocioProphet/prophet-platform/libs/go/tritrpcbridge/tritrpcv1"
)

const defaultUnixSocket = "/tmp/socioprophet.sock"

func main() {
    key, err := binding.ResolveSharedKey(os.Getenv("TRITRPC_KEY_HEX"), os.Getenv("TRITRPC_ALLOW_INSECURE_DEV_KEY") == "1")
    if err != nil {
        log.Fatalf("shared key: %v", err)
    }

    listenAddr := firstNonEmpty(os.Getenv("TRITRPC_LISTEN_ADDR"), legacySockAddr())
    ln, resolved, err := binding.Listen(listenAddr, defaultUnixSocket)
    if err != nil {
        log.Fatalf("listen error: %v", err)
    }
    defer ln.Close()
    log.Printf("SocioProphet API (TriTRPC v1) listening at %s", resolved)

    for {
        c, err := ln.Accept()
        if err != nil {
            log.Printf("accept error: %v", err)
            continue
        }
        go handle(c, key)
    }
}

func handle(c net.Conn, key [32]byte) {
    defer c.Close()
    nonce, frame, err := binding.ReadRecord(c)
    if err != nil {
        if !errors.Is(err, io.EOF) {
            log.Printf("read record: %v", err)
        }
        return
    }
    env, err := binding.VerifyEnvelope(frame, nonce, key)
    if err != nil {
        log.Printf("verify envelope: %v", err)
        return
    }

    switch {
    case env.Service == binding.HealthService && env.Method == binding.HealthPingReq:
        handleHealth(c, env, key)
    case env.Service == binding.ValidateChangeService && env.Method == binding.ValidateChangeReq:
        handleValidateChange(c, env, key)
    default:
        log.Printf("unexpected route: %s %s", env.Service, env.Method)
    }
}

func handleHealth(c net.Conn, env *tritrpcv1.Envelope, key [32]byte) {
    var req binding.HealthPingRequest
    if err := binding.DecodeJSONPayload(env, &req); err != nil {
        log.Printf("decode health payload: %v", err)
        return
    }

    resp := binding.HealthPingResponse{Ok: true, Pong: "PONG", Service: "socioprophet-api"}
    if err := writeJSONResponse(c, binding.HealthService, binding.HealthPingRes, resp, key); err != nil {
        log.Printf("write health response: %v", err)
    }
    _ = req // reserved for future trace/evidence hooks
}

func handleValidateChange(c net.Conn, env *tritrpcv1.Envelope, key [32]byte) {
    var req map[string]any
    if err := binding.DecodeJSONPayload(env, &req); err != nil {
        log.Printf("decode validate_change payload: %v", err)
        return
    }

    response := map[string]any{
        "schema_version": "1.0",
        "request_id": stringValue(req, "request_id", "environment:validate-change-v2-request:unknown"),
        "response_id": "environment:validate-change-v2-response:requested:api-stub",
        "status": "environment_requested",
        "repo": stringValue(req, "repo", "unknown/unknown"),
        "sociosphere_refs": req["sociosphere_refs"],
        "selected_plans": req["selected_plans"],
        "environment": req["environment_request"],
        "agentplane_execution": map[string]any{
            "executor_plane": "AgentPlane",
            "sandbox_run_ref": "agentplane:sandbox-run:pending:api-stub",
            "execution_status": "requested",
            "evidence_refs": []string{},
        },
        "evidence_summary": map[string]any{
            "evidence_status": "missing",
            "validation_evidence_state": "missing_evidence",
            "receipt_refs": []string{},
            "failure_codes": []string{
                "validation_observation_missing",
            },
            "non_certified_claims": []string{
                "Plans were selected but no execution evidence was observed.",
                "No validation success is certified.",
                "No merge readiness is certified.",
            },
        },
        "pr_readiness": map[string]any{
            "readiness_state": "blocked",
            "merge_allowed": false,
            "required_evidence_state": "verified_receipt",
            "observed_evidence_state": "missing_evidence",
            "blocking_reason_codes": []string{
                "validation_observation_missing",
                "verified_receipt_required",
            },
            "summary": "Selected validation plans are not sufficient for PR readiness without observed receipt-backed evidence.",
            "non_claims": []string{
                "Readiness block is based on missing evidence state.",
                "Readiness block does not execute validation.",
            },
        },
        "warnings": []string{
            "validation_observation_missing",
            "environment_execution_not_observed",
        },
        "next_required_action": "agentplane_synthetic_sandbox_run",
        "non_claims": []string{
            "API stub does not execute live sandbox infrastructure.",
            "API stub does not certify Signadot-style runtime parity.",
            "API stub returns a deterministic environment_requested response only.",
            "API stub cannot report merge readiness without verified receipt evidence.",
        },
    }

    if err := writeJSONResponse(c, binding.ValidateChangeService, binding.ValidateChangeRes, response, key); err != nil {
        log.Printf("write validate_change response: %v", err)
    }
}

func writeJSONResponse(c net.Conn, service string, method string, payload any, key [32]byte) error {
    respNonce, respFrame, err := binding.MarshalJSONFrame(service, method, payload, key)
    if err != nil {
        return err
    }
    return binding.WriteRecord(c, respNonce, respFrame)
}

func stringValue(m map[string]any, key string, fallback string) string {
    if value, ok := m[key].(string); ok && strings.TrimSpace(value) != "" {
        return value
    }
    return fallback
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

var _ = json.Valid
