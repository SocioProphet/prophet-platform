import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.models import AcademyRecordHeader, LearningSearchRecord
from app.policy import AcademyPolicyContext, HttpPolicyFabricEvaluator, LocalVisibilityPolicyEvaluator


def record() -> LearningSearchRecord:
    return LearningSearchRecord(
        header=AcademyRecordHeader(object_id="lsr_http_policy_0001", object_type="LearningSearchRecord"),
        source="ALEXANDRIAN_ACADEMY",
        entity_type="LEARNING_ACTION_EXPLANATION",
        title="Why recommended",
        text="Policy Fabric checked explanation.",
        target_ref="llr_http_policy_0001",
        final_score=1.0,
    )


class FakePolicyHandler(BaseHTTPRequestHandler):
    response_payload = {
        "policy_decision_id": "academy_visibility_decision_http_0001",
        "request_id": "academy_visibility_request_http_0001",
        "subject_ref": "academy://search-record/lsr_http_policy_0001",
        "action_ref": "action://academy/search/read",
        "decision": "allow",
        "required_gates": ["actor_gate"],
        "reason": "fake policy allow",
        "validation_evidence": ["fake"],
    }
    received = None

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        FakePolicyHandler.received = json.loads(self.rfile.read(length).decode("utf-8"))
        body = json.dumps(FakePolicyHandler.response_payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def start_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakePolicyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_http_policy_fabric_evaluator_uses_remote_allow_decision() -> None:
    FakePolicyHandler.received = None
    FakePolicyHandler.response_payload = {
        "policy_decision_id": "academy_visibility_decision_http_allow",
        "request_id": "academy_visibility_request_http_allow",
        "subject_ref": "academy://search-record/lsr_http_policy_0001",
        "action_ref": "action://academy/search/read",
        "decision": "allow",
        "required_gates": ["actor_gate"],
        "reason": "fake policy allow",
        "validation_evidence": ["fake"],
    }
    server, thread = start_server()
    try:
        evaluator = HttpPolicyFabricEvaluator(f"http://127.0.0.1:{server.server_port}/decide")
        decision = evaluator.decide(record(), AcademyPolicyContext(actor_id="user-1"))
    finally:
        server.shutdown()
        thread.join(timeout=5)
    assert decision.allowed
    assert decision.decision_ref == "policy-fabric://decision/academy_visibility_decision_http_allow"
    assert FakePolicyHandler.received["action"] == "academy.search.read"


def test_http_policy_fabric_evaluator_uses_remote_deny_decision() -> None:
    FakePolicyHandler.response_payload = {
        "policy_decision_id": "academy_visibility_decision_http_deny",
        "request_id": "academy_visibility_request_http_deny",
        "subject_ref": "academy://search-record/lsr_http_policy_0001",
        "action_ref": "action://academy/search/read",
        "decision": "deny",
        "required_gates": ["actor_gate"],
        "reason": "fake policy deny",
        "validation_evidence": ["fake"],
    }
    server, thread = start_server()
    try:
        evaluator = HttpPolicyFabricEvaluator(f"http://127.0.0.1:{server.server_port}/decide")
        decision = evaluator.decide(record(), AcademyPolicyContext(actor_id="user-1"))
    finally:
        server.shutdown()
        thread.join(timeout=5)
    assert not decision.allowed
    assert decision.reason == "fake policy deny"


def test_http_policy_fabric_evaluator_falls_back_on_connection_failure() -> None:
    evaluator = HttpPolicyFabricEvaluator(
        "http://127.0.0.1:1/decide",
        fallback=LocalVisibilityPolicyEvaluator(),
        timeout_seconds=0.01,
    )
    decision = evaluator.decide(record(), AcademyPolicyContext(actor_id="user-1"))
    assert decision.allowed
    assert decision.reason == "no visibility constraints"
