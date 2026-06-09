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

// sociosphereExportManifestRef is the pinned Sociosphere SVF export manifest
// that downstream receipt consumers (including this API stub) reference for
// exported receipt validation. Prophet consumes this manifest; it does not
// produce or certify it.
const sociosphereExportManifestRef = "SocioProphet/sociosphere@7133223edd7784a36b15e3eee9065f17b49b5451:artifacts/svf/exports/latest/export-manifest.json"

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

// buildValidateChangeResponse constructs the validate_change response.
//
// If the request contains an exported_sociosphere_receipt, the receipt's
// verification.status drives the evidence/readiness projection:
//   - "verified"  → environment_observed / verified_receipt / merge_allowed: true
//   - "failed"    → environment_failed  / failed_receipt   / merge_allowed: false
//   - "stale"     → environment_failed  / stale_receipt    / merge_allowed: false
//
// Absent or unrecognised receipt → default missing-evidence response.
//
// Boundary: Prophet does not execute SVF actions, issue receipts, or act as
// receipt-signing authority. SVF run refs are placed in evidence_summary.run_refs
// only; agentplane_execution.sandbox_run_ref remains an AgentPlane ref.
func buildValidateChangeResponse(req map[string]any) map[string]any {
    requestID := stringValue(req, "request_id", "environment:validate-change-v2-request:unknown")
    repo := stringValue(req, "repo", "unknown/unknown")

    // Inspect exported receipt if present.
    exportedReceipt, hasReceipt := req["exported_sociosphere_receipt"].(map[string]any)
    receiptStatus := ""
    if hasReceipt {
        if ver, ok := exportedReceipt["verification"].(map[string]any); ok {
            receiptStatus = stringValue(ver, "status", "")
        }
    }

    switch receiptStatus {
    case "verified":
        return buildVerifiedReceiptResponse(req, requestID, repo, exportedReceipt)
    case "failed":
        return buildFailedReceiptResponse(req, requestID, repo, exportedReceipt)
    case "stale":
        return buildStaleReceiptResponse(req, requestID, repo, exportedReceipt)
    default:
        return buildMissingEvidenceResponse(req, requestID, repo)
    }
}

func buildVerifiedReceiptResponse(req map[string]any, requestID, repo string, receipt map[string]any) map[string]any {
    runRef := stringValue(receipt, "run_ref", "svf:run:unknown")
    receiptRef := stringValue(receipt, "receipt_ref", "svf:receipt:unknown")
    manifestRef := stringValue(receipt, "export_manifest_ref", "")
    return map[string]any{
        "schema_version": "1.0",
        "request_id": requestID,
        "response_id": "environment:validate-change-v2-response:observed:exported-sociosphere-receipt",
        "status": "environment_observed",
        "repo": repo,
        "sociosphere_refs": req["sociosphere_refs"],
        "selected_plans": req["selected_plans"],
        "environment": req["environment_request"],
        "agentplane_execution": map[string]any{
            "executor_plane": "AgentPlane",
            "sandbox_run_ref": "agentplane:sandbox-run:exported-sociosphere-receipt",
            "execution_status": "observed",
            "evidence_refs": []string{receiptRef},
        },
        "evidence_summary": map[string]any{
            "evidence_status": "verified",
            "validation_evidence_state": "verified_receipt",
            "receipt_refs": []string{receiptRef},
            "run_refs": []string{runRef},
            "export_manifest_ref": manifestRef,
            "failure_codes": []string{},
            "non_certified_claims": []string{
                "Receipt was generated by Sociosphere SVF runner, not a production authority.",
                "Verification does not certify production readiness.",
            },
        },
        "pr_readiness": map[string]any{
            "readiness_state": "allowed",
            "merge_allowed": true,
            "required_evidence_state": "verified_receipt",
            "observed_evidence_state": "verified_receipt",
            "blocking_reason_codes": []string{},
            "summary": "Verified SVF receipt observed. PR readiness gate satisfied.",
            "non_claims": []string{
                "Readiness is based on exported Sociosphere SVF receipt only.",
                "Readiness does not certify production deployment.",
            },
        },
        "workroom_projection": map[string]any{
            "schema_version": "0.1.0",
            "workroom_id": "workroom:devsecops:pre-merge:exported-sociosphere-receipt:verified",
            "lane": "pre_merge_validation",
            "runtime_parity_level": "contract_only",
            "validation_evidence_state": "verified_receipt",
            "source_refs": map[string]any{
                "change_set_ref": "changeset://github/" + repo + "/api-stub",
                "environment_request_ref": requestID,
                "validation_run_ref": runRef,
                "validation_receipt_ref": receiptRef,
                "export_manifest_ref": manifestRef,
                "topology_ref": "topology://svf-local/exported",
            },
            "event_type": "pre_merge_validation_success",
            "decision_state": "allowed",
            "non_claims": []string{
                "Projection is derived from exported Sociosphere SVF receipt.",
                "Projection does not execute live sandbox infrastructure.",
                "Projection does not certify Signadot-style feature parity.",
            },
        },
        "warnings": []string{},
        "next_required_action": "none_for_verified_receipt",
        "non_claims": []string{
            "API stub does not execute live sandbox infrastructure.",
            "API stub does not certify Signadot-style runtime parity.",
            "API stub projects readiness from exported SVF receipt only.",
        },
    }
}

func buildFailedReceiptResponse(req map[string]any, requestID, repo string, receipt map[string]any) map[string]any {
    runRef := stringValue(receipt, "run_ref", "svf:run:unknown")
    receiptRef := stringValue(receipt, "receipt_ref", "svf:receipt:unknown")
    manifestRef := stringValue(receipt, "export_manifest_ref", "")
    return map[string]any{
        "schema_version": "1.0",
        "request_id": requestID,
        "response_id": "environment:validate-change-v2-response:failed:exported-sociosphere-receipt",
        "status": "environment_failed",
        "repo": repo,
        "sociosphere_refs": req["sociosphere_refs"],
        "selected_plans": req["selected_plans"],
        "environment": req["environment_request"],
        "agentplane_execution": map[string]any{
            "executor_plane": "AgentPlane",
            "sandbox_run_ref": "agentplane:sandbox-run:exported-sociosphere-receipt",
            "execution_status": "failed",
            "evidence_refs": []string{receiptRef},
        },
        "evidence_summary": map[string]any{
            "evidence_status": "failed",
            "validation_evidence_state": "failed_receipt",
            "receipt_refs": []string{receiptRef},
            "run_refs": []string{runRef},
            "export_manifest_ref": manifestRef,
            "failure_codes": []string{
                "svf_receipt_failed",
                "verified_receipt_required",
            },
            "non_certified_claims": []string{
                "Receipt is failed. No merge readiness is certified.",
                "Remediate: inspect action-result artifact refs, patch failing change, rerun SVF plan.",
            },
        },
        "pr_readiness": map[string]any{
            "readiness_state": "blocked",
            "merge_allowed": false,
            "required_evidence_state": "verified_receipt",
            "observed_evidence_state": "failed_receipt",
            "blocking_reason_codes": []string{
                "svf_receipt_failed",
                "verified_receipt_required",
            },
            "summary": "Failed SVF receipt observed. PR readiness gate blocked pending remediation and rerun.",
            "non_claims": []string{
                "Readiness block is based on failed SVF receipt state.",
                "Readiness block does not execute validation.",
            },
        },
        "workroom_projection": map[string]any{
            "schema_version": "0.1.0",
            "workroom_id": "workroom:devsecops:pre-merge:exported-sociosphere-receipt:failed",
            "lane": "pre_merge_validation",
            "runtime_parity_level": "contract_only",
            "validation_evidence_state": "failed_receipt",
            "source_refs": map[string]any{
                "change_set_ref": "changeset://github/" + repo + "/api-stub",
                "environment_request_ref": requestID,
                "validation_run_ref": runRef,
                "validation_receipt_ref": receiptRef,
                "export_manifest_ref": manifestRef,
                "topology_ref": "topology://svf-local/exported",
            },
            "event_type": "pre_merge_validation_failure",
            "decision_state": "blocked",
            "non_claims": []string{
                "Projection is derived from exported Sociosphere SVF receipt.",
                "Projection does not execute live sandbox infrastructure.",
                "Projection does not certify Signadot-style feature parity.",
            },
        },
        "warnings": []string{
            "svf_receipt_failed",
            "remediation_required_before_merge",
        },
        "next_required_action": "remediate_and_rerun_environment_validation",
        "non_claims": []string{
            "API stub does not execute live sandbox infrastructure.",
            "API stub does not certify Signadot-style runtime parity.",
            "API stub projects readiness from exported SVF receipt only.",
        },
    }
}

func buildStaleReceiptResponse(req map[string]any, requestID, repo string, receipt map[string]any) map[string]any {
    runRef := stringValue(receipt, "run_ref", "svf:run:unknown")
    receiptRef := stringValue(receipt, "receipt_ref", "svf:receipt:unknown")
    manifestRef := stringValue(receipt, "export_manifest_ref", "")
    return map[string]any{
        "schema_version": "1.0",
        "request_id": requestID,
        "response_id": "environment:validate-change-v2-response:failed:exported-sociosphere-receipt:stale",
        "status": "environment_failed",
        "repo": repo,
        "sociosphere_refs": req["sociosphere_refs"],
        "selected_plans": req["selected_plans"],
        "environment": req["environment_request"],
        "agentplane_execution": map[string]any{
            "executor_plane": "AgentPlane",
            "sandbox_run_ref": "agentplane:sandbox-run:exported-sociosphere-receipt",
            "execution_status": "stale",
            "evidence_refs": []string{receiptRef},
        },
        "evidence_summary": map[string]any{
            "evidence_status": "stale",
            "validation_evidence_state": "stale_receipt",
            "receipt_refs": []string{receiptRef},
            "run_refs": []string{runRef},
            "export_manifest_ref": manifestRef,
            "failure_codes": []string{
                "svf_receipt_stale",
                "verified_receipt_required",
            },
            "non_certified_claims": []string{
                "Receipt is stale. Change set has been updated since receipt was issued.",
                "Remediate: rerun SVF plan against current change, replace stale receipt with verified receipt.",
            },
        },
        "pr_readiness": map[string]any{
            "readiness_state": "blocked",
            "merge_allowed": false,
            "required_evidence_state": "verified_receipt",
            "observed_evidence_state": "stale_receipt",
            "blocking_reason_codes": []string{
                "svf_receipt_stale",
                "verified_receipt_required",
            },
            "summary": "Stale SVF receipt observed. PR readiness gate blocked pending rerun against current change set.",
            "non_claims": []string{
                "Readiness block is based on stale SVF receipt state.",
                "Readiness block does not execute validation.",
            },
        },
        "workroom_projection": map[string]any{
            "schema_version": "0.1.0",
            "workroom_id": "workroom:devsecops:pre-merge:exported-sociosphere-receipt:stale",
            "lane": "pre_merge_validation",
            "runtime_parity_level": "contract_only",
            "validation_evidence_state": "stale_receipt",
            "source_refs": map[string]any{
                "change_set_ref": "changeset://github/" + repo + "/api-stub",
                "environment_request_ref": requestID,
                "validation_run_ref": runRef,
                "validation_receipt_ref": receiptRef,
                "export_manifest_ref": manifestRef,
                "topology_ref": "topology://svf-local/exported",
            },
            "event_type": "pre_merge_validation_failure",
            "decision_state": "blocked",
            "non_claims": []string{
                "Projection is derived from exported Sociosphere SVF receipt.",
                "Projection does not execute live sandbox infrastructure.",
                "Projection does not certify Signadot-style feature parity.",
            },
        },
        "warnings": []string{
            "svf_receipt_stale",
            "rerun_required_before_merge",
        },
        "next_required_action": "rerun_selected_svf_plan",
        "non_claims": []string{
            "API stub does not execute live sandbox infrastructure.",
            "API stub does not certify Signadot-style runtime parity.",
            "API stub projects readiness from exported SVF receipt only.",
        },
    }
}

func buildMissingEvidenceResponse(req map[string]any, requestID, repo string) map[string]any {
    return map[string]any{
        "schema_version": "1.0",
        "request_id": requestID,
        "response_id": "environment:validate-change-v2-response:requested:api-stub",
        "status": "environment_requested",
        "repo": repo,
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
        "workroom_projection": map[string]any{
            "schema_version": "0.1.0",
            "workroom_id": "workroom:devsecops:pre-merge:api-stub-missing-evidence",
            "lane": "pre_merge_validation",
            "runtime_parity_level": "contract_only",
            "validation_evidence_state": "missing_evidence",
            "source_refs": map[string]any{
                "change_set_ref": "changeset://github/" + repo + "/api-stub",
                "environment_request_ref": requestID,
                "validation_run_ref": "agentplane:sandbox-run:pending:api-stub",
                "topology_ref": "topology://api-stub/not-observed",
            },
            "event_type": "pre_merge_validation_failure",
            "decision_state": "blocked",
            "non_claims": []string{
                "Projection is derived from deterministic API stub response only.",
                "Projection does not execute live sandbox infrastructure.",
                "Projection does not certify Signadot-style feature parity.",
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
