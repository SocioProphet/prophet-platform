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

    response := buildValidateChangeResponse(req)
    if err := writeJSONResponse(c, binding.ValidateChangeService, binding.ValidateChangeRes, response, key); err != nil {
        log.Printf("write validate_change response: %v", err)
    }
}

func buildValidateChangeResponse(req map[string]any) map[string]any {
    evidenceState := "missing_evidence"
    evidenceStatus := "missing"
    responseStatus := "environment_requested"
    responseID := "environment:validate-change-v2-response:requested:api-stub"
    receiptRefs := []string{}
    receiptDigests := []string{}
    failureCodes := []string{"validation_observation_missing"}
    warnings := []string{"validation_observation_missing", "environment_execution_not_observed"}
    nextAction := "agentplane_synthetic_sandbox_run"
    executionStatus := "requested"
    sandboxRunRef := "agentplane:sandbox-run:pending:api-stub"
    evidenceRefs := []string{}
    readinessState := "blocked"
    mergeAllowed := false
    blockingReasons := []string{"validation_observation_missing", "verified_receipt_required"}
    readinessSummary := "Selected validation plans are not sufficient for PR readiness without observed receipt-backed evidence."
    nonCertifiedClaims := []string{
        "Plans were selected but no execution evidence was observed.",
        "No validation success is certified.",
        "No merge readiness is certified.",
    }

    if receipt, ok := req["exported_sociosphere_receipt"].(map[string]any); ok {
        receiptID := stringValue(receipt, "receipt_id", "")
        runRef := stringValue(receipt, "run_ref", "agentplane:sandbox-run:exported-sociosphere-receipt")
        verification := mapValue(receipt, "verification")
        verificationStatus := stringValue(verification, "status", "")
        receiptRefs = appendIfNonEmpty(receiptRefs, receiptID)
        if digest := digestString(receipt, "run_digest"); digest != "" {
            receiptDigests = append(receiptDigests, digest)
        }
        sandboxRunRef = runRef
        evidenceRefs = appendIfNonEmpty(evidenceRefs, "evidence://sociosphere/svf/exported-receipt/"+receiptSuffix(receiptID))

        switch verificationStatus {
        case "verified":
            evidenceState = "verified_receipt"
            evidenceStatus = "observed"
            responseStatus = "environment_observed"
            responseID = "environment:validate-change-v2-response:observed:api-stub"
            failureCodes = []string{}
            warnings = []string{}
            nextAction = "none_for_verified_receipt"
            executionStatus = "observed"
            readinessState = "ready"
            mergeAllowed = true
            blockingReasons = []string{}
            readinessSummary = "Readiness is allowed only because a verified Sociosphere SVF receipt reference is present."
            nonCertifiedClaims = []string{
                "Prophet Platform consumes the receipt but does not issue it.",
                "Verified local receipt does not certify production readiness.",
            }
        case "failed":
            evidenceState = "failed_receipt"
            evidenceStatus = "failed"
            responseStatus = "environment_failed"
            responseID = "environment:validate-change-v2-response:failed:api-stub"
            failureCodes = []string{"svf_receipt_failed"}
            warnings = []string{"environment_validation_failed", "validation_receipt_failed"}
            nextAction = "remediate_and_rerun_environment_validation"
            executionStatus = "failed"
            blockingReasons = []string{"svf_receipt_failed", "verified_receipt_required"}
            readinessSummary = "Failed receipt evidence blocks PR readiness. Inspect diagnostics, patch the failure, and rerun the selected SVF plan before merge readiness can be claimed."
            nonCertifiedClaims = []string{
                "Failed receipt blocks validation success.",
                "Failed receipt does not certify production readiness.",
                "Failed receipt requires repair and rerun before PR readiness.",
            }
        case "stale":
            evidenceState = "stale_receipt"
            evidenceStatus = "stale"
            responseStatus = "environment_failed"
            responseID = "environment:validate-change-v2-response:stale-receipt:api-stub"
            failureCodes = []string{"svf_receipt_stale"}
            warnings = []string{"validation_receipt_stale"}
            nextAction = "rerun_selected_svf_plan"
            executionStatus = "failed"
            blockingReasons = []string{"svf_receipt_stale", "verified_receipt_required"}
            readinessSummary = "Stale receipt evidence blocks PR readiness for the current change set. Rerun the selected SVF plan before readiness can be claimed."
            nonCertifiedClaims = []string{
                "Stale receipt does not certify the current change set.",
                "Stale receipt does not certify production readiness.",
                "Stale receipt requires rerun before PR readiness.",
            }
        }
    }

    evidenceSummary := map[string]any{
        "evidence_status": evidenceStatus,
        "validation_evidence_state": evidenceState,
        "receipt_refs": receiptRefs,
        "receipt_digests": receiptDigests,
        "failure_codes": failureCodes,
        "non_certified_claims": nonCertifiedClaims,
    }

    return map[string]any{
        "schema_version": "1.0",
        "request_id": stringValue(req, "request_id", "environment:validate-change-v2-request:unknown"),
        "response_id": responseID,
        "status": responseStatus,
        "repo": stringValue(req, "repo", "unknown/unknown"),
        "sociosphere_refs": req["sociosphere_refs"],
        "selected_plans": req["selected_plans"],
        "environment": req["environment_request"],
        "agentplane_execution": map[string]any{
            "executor_plane": "AgentPlane",
            "sandbox_run_ref": sandboxRunRef,
            "execution_status": executionStatus,
            "evidence_refs": evidenceRefs,
        },
        "evidence_summary": evidenceSummary,
        "pr_readiness": map[string]any{
            "readiness_state": readinessState,
            "merge_allowed": mergeAllowed,
            "required_evidence_state": "verified_receipt",
            "observed_evidence_state": evidenceState,
            "blocking_reason_codes": blockingReasons,
            "summary": readinessSummary,
            "non_claims": []string{
                "Readiness is derived from exported Sociosphere receipt state.",
                "Readiness block or allowance does not execute validation in Prophet Platform.",
            },
        },
        "warnings": warnings,
        "next_required_action": nextAction,
        "non_claims": []string{
            "API stub does not execute live sandbox infrastructure.",
            "API stub does not certify Signadot-style runtime parity.",
            "API stub consumes exported Sociosphere receipt state only.",
            "API stub cannot report merge readiness without verified receipt evidence.",
        },
    }
}

func writeJSONResponse(c net.Conn, service string, method string, payload any, key [32]byte) error {
    respNonce, respFrame, err := binding.MarshalJSONFrame(service, method, payload, key)
    if err != nil {
        return err
    }
    return binding.WriteRecord(c, respNonce, respFrame)
}

func mapValue(m map[string]any, key string) map[string]any {
    if value, ok := m[key].(map[string]any); ok {
        return value
    }
    return map[string]any{}
}

func digestString(m map[string]any, key string) string {
    record := mapValue(m, key)
    algorithm := stringValue(record, "algorithm", "")
    digest := stringValue(record, "digest", "")
    if algorithm == "" || digest == "" {
        return ""
    }
    return algorithm + ":" + digest
}

func appendIfNonEmpty(values []string, value string) []string {
    if strings.TrimSpace(value) == "" {
        return values
    }
    return append(values, value)
}

func receiptSuffix(receiptID string) string {
    suffix := strings.TrimPrefix(receiptID, "svf:receipt:")
    suffix = strings.ReplaceAll(suffix, ":", "-")
    suffix = strings.ReplaceAll(suffix, "/", "-")
    if suffix == "" {
        return "unknown"
    }
    return suffix
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
