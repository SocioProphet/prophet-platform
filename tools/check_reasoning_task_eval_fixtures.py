#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import math
import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable


class FixtureError(AssertionError):
    pass


def _tasks(paths: list[Path]) -> tuple[list[dict[str, Any]], list[str]]:
    files: list[Path] = []
    for path in paths:
        files.extend(sorted(path.glob("*.json")) if path.is_dir() else [path])
    if not files:
        raise FixtureError("no fixture files found")
    out: list[dict[str, Any]] = []
    for file in files:
        payload = json.loads(file.read_text(encoding="utf-8"))
        tasks = payload.get("tasks")
        if not isinstance(tasks, list):
            raise FixtureError(f"{file}: missing tasks list")
        for task in tasks:
            if not isinstance(task, dict):
                raise FixtureError(f"{file}: task must be an object")
            copied = dict(task)
            copied["_fixture_path"] = str(file)
            out.append(copied)
    return out, [str(f) for f in files]


def _shape(task: dict[str, Any]) -> None:
    required = ["task_id", "task_family", "verifier", "answer_status", "input", "expected_answer", "reasoning_operations", "logic_probability_binding"]
    missing = [field for field in required if field not in task]
    if missing:
        raise FixtureError(f"missing fields {missing}")
    if not isinstance(task["reasoning_operations"], list) or not task["reasoning_operations"]:
        raise FixtureError("reasoning_operations must be a non-empty list")
    binding = task["logic_probability_binding"]
    if not isinstance(binding, dict) or not binding.get("kind") or not binding.get("confidence_policy"):
        raise FixtureError("logic_probability_binding requires kind and confidence_policy")


def arithmetic_progression(task: dict[str, Any]) -> None:
    seq = task["input"]["sequence"]
    i = seq.index(None)
    known = [x for x in seq if x is not None]
    diffs = [b - a for a, b in zip(known, known[1:])]
    if not diffs or len(set(diffs)) != 1:
        raise FixtureError("not an arithmetic progression")
    left = next(seq[j] for j in range(i - 1, -1, -1) if seq[j] is not None)
    if left + diffs[0] != task["expected_answer"]:
        raise FixtureError("arithmetic progression answer mismatch")


def affine_recurrence_wrong_term(task: dict[str, Any]) -> None:
    seq = task["input"]["sequence"]
    cur = seq[0]
    inc = task["input"].get("increments_start", 1)
    mult = task["input"]["multiplier"]
    for obs in seq[1:]:
        pred = cur * mult + inc
        if obs != pred:
            if task["expected_answer"] != {"wrong_term": obs, "replacement": pred}:
                raise FixtureError("wrong-term answer mismatch")
            return
        cur = obs
        inc += 1
    raise FixtureError("no wrong term found")


def caesar_shift(task: dict[str, Any]) -> None:
    shift = int(task["input"]["shift"])
    out = []
    for ch in task["input"]["plain"]:
        if "A" <= ch <= "Z":
            out.append(chr(((ord(ch) - 65 + shift) % 26) + 65))
        elif "a" <= ch <= "z":
            out.append(chr(((ord(ch) - 97 + shift) % 26) + 97))
        else:
            out.append(ch)
    if "".join(out) != task["expected_answer"]:
        raise FixtureError("Caesar shift mismatch")


def reverse_alphabet_sum(task: dict[str, Any]) -> None:
    got = sum(27 - (ord(ch.upper()) - 64) for ch in task["input"]["word"])
    if got != task["expected_answer"]:
        raise FixtureError("reverse alphabet sum mismatch")


_ALLOWED_AST = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd, ast.Constant)


def operator_substitution(task: dict[str, Any]) -> None:
    expr = " ".join(task["input"]["operator_map"].get(t, t) for t in task["input"]["expression_tokens"])
    tree = ast.parse(expr, mode="eval")
    if any(not isinstance(node, _ALLOWED_AST) for node in ast.walk(tree)):
        raise FixtureError("unsafe arithmetic expression")
    got = eval(compile(tree, "<expr>", "eval"), {"__builtins__": {}}, {})
    if isinstance(got, float) and math.isclose(got, round(got)):
        got = int(round(got))
    if got != task["expected_answer"]:
        raise FixtureError("operator substitution mismatch")


def underdetermined_constraint(task: dict[str, Any]) -> None:
    if task["answer_status"] != "UNDERDETERMINED" or task["expected_answer"] != "cannot_be_determined":
        raise FixtureError("underdetermined tasks must preserve abstention")


def _db(tables: dict[str, Any]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    for name, spec in tables.items():
        cols = spec["columns"]
        conn.execute(f"CREATE TABLE {name} ({', '.join(c + ' TEXT' for c in cols)})")
        conn.executemany(f"INSERT INTO {name} VALUES ({', '.join('?' for _ in cols)})", spec["rows"])
    return conn


def _sql(program: dict[str, Any]) -> tuple[str, list[Any]]:
    if not program.get("policy", {}).get("read_only", False):
        raise FixtureError("program must be read-only")
    select = []
    for item in program["select"]:
        agg = item.get("agg")
        expr = item.get("expr", "*")
        if agg == "count_distinct":
            select.append(f"COUNT(DISTINCT {expr})")
        elif agg == "count":
            select.append(f"COUNT({expr})")
        elif agg == "sum":
            select.append(f"SUM({expr})")
        elif agg:
            raise FixtureError(f"unsupported aggregation {agg}")
        else:
            select.append(expr)
    query = f"SELECT {', '.join(select)} FROM {program['from']}"
    for join in program.get("joins", []):
        left, right = join["on"]
        query += f" JOIN {join['table']} ON {left} = {right}"
    params: list[Any] = []
    wheres = []
    for pred in program.get("where", []):
        left, right = pred["eq"]
        wheres.append(f"{left} = ?")
        params.append(right)
    if wheres:
        query += " WHERE " + " AND ".join(wheres)
    return query, params


def sql_ast_execution(task: dict[str, Any]) -> None:
    conn = _db(task["input"]["tables"])
    try:
        rows = conn.execute(*_sql(task["input"]["program_ast"])).fetchall()
    finally:
        conn.close()
    expected = task["expected_answer"]
    if isinstance(expected, list):
        got: Any = [row[0] for row in rows] if rows and len(rows[0]) == 1 else rows
    else:
        got = rows[0][0] if rows and len(rows[0]) == 1 else rows
        if isinstance(expected, int) and isinstance(got, str) and got.isdigit():
            got = int(got)
    if got != expected:
        raise FixtureError(f"SQL got {got!r}, expected {expected!r}")


def kb_neighbors_one_hop(task: dict[str, Any]) -> None:
    subject = task["input"]["program"]["args"][0]
    if task["input"]["program"].get("max_hops") != 1:
        raise FixtureError("only one-hop traversal allowed")
    neighbors = set()
    for rel, left, right in task["input"]["facts"]:
        if rel == "borders" and left == subject:
            neighbors.add(right)
        if rel == "borders" and right == subject:
            neighbors.add(left)
    if sorted(neighbors) != sorted(task["expected_answer"]):
        raise FixtureError("neighbor denotation mismatch")


def markov_logic_fixture_shape(task: dict[str, Any]) -> None:
    inp = task["input"]
    for key in ["constants", "predicates", "weighted_formulas", "inference_targets", "grounding_policy"]:
        if not inp.get(key):
            raise FixtureError(f"missing MLN field {key}")
    if not all("formula" in f and "weight" in f for f in inp["weighted_formulas"]):
        raise FixtureError("weighted formulas require formula and weight")


def essential_terms_query_rewrite(task: dict[str, Any]) -> None:
    got = [tok for tok, label in zip(task["input"]["tokens"], task["input"]["essential_labels"]) if int(label) == 1]
    if got != task["expected_answer"]["query_terms"]:
        raise FixtureError("essential terms mismatch")


def retrieval_relevance_marking(task: dict[str, Any]) -> None:
    got = [p["id"] for p in task["input"]["passages"] if p.get("marked_relevant")]
    if got != task["expected_answer"]["relevant_ids"]:
        raise FixtureError("relevance ids mismatch")


def top_k_entailment_resolver(task: dict[str, Any]) -> None:
    top_k = task["input"].get("top_k", 10**9)
    candidates = [x for x in task["input"]["answer_evidence"] if x.get("rank", 1) <= top_k]
    if max(candidates, key=lambda x: x["entailment"])["answer"] != task["expected_answer"]:
        raise FixtureError("top-k resolver mismatch")


def external_knowledge_nli_bridge(task: dict[str, Any]) -> None:
    if task["expected_answer"].get("external_support_is_authoritative") is not False:
        raise FixtureError("external support must not be authoritative")
    if not all(x.get("support_type") == "defeasible" for x in task["input"].get("external_knowledge", [])):
        raise FixtureError("external edges must be defeasible")


def hypothesis_splitting_shape(task: dict[str, Any]) -> None:
    if not task["input"].get("premise_append_question_context") or not task["expected_answer"].get("split_context_preserved"):
        raise FixtureError("hypothesis split context not preserved")


def low_evidence_abstention(task: dict[str, Any]) -> None:
    if max(x["entailment"] for x in task["input"]["answer_evidence"]) >= task["input"]["threshold"]:
        raise FixtureError("evidence is not below threshold")
    if task["answer_status"] != "ABSTAIN" or task["expected_answer"] != "route_to_review":
        raise FixtureError("low evidence must route to review")


def knowledge_reasoning_taxonomy(task: dict[str, Any]) -> None:
    inp = task["input"]
    if not set(inp["knowledge_types"]).issubset(inp["allowed_knowledge_types"]):
        raise FixtureError("invalid knowledge label")
    if not set(inp["reasoning_types"]).issubset(inp["allowed_reasoning_types"]):
        raise FixtureError("invalid reasoning label")


def proofpack_minimum_fields(task: dict[str, Any]) -> None:
    required = ["query_id", "schema_ref", "policy_ref", "grounding_candidates", "chosen_entities", "candidate_root_hash", "program_ast", "verifier_scores", "execution_trace_digest", "result_digest", "signer_set", "replay_nonce"]
    proofpack = task["input"]["proofpack"]
    missing = [x for x in required if x not in proofpack]
    if missing:
        raise FixtureError(f"proofpack missing {missing}")
    for key in ["grammar_valid", "type_valid", "policy_valid", "fixture_pass"]:
        if proofpack["verifier_scores"].get(key) != 1.0:
            raise FixtureError(f"verifier score {key} must be 1.0")


def schema_grounded_dual_ir(task: dict[str, Any]) -> None:
    inp = task["input"]
    if not inp.get("schema_ir") or not inp.get("program_ir"):
        raise FixtureError("schema_ir and program_ir required")
    if inp.get("promotion_requires_both") is not True or inp.get("prediction_mode") != "advisory_only":
        raise FixtureError("dual-IR promotion guard mismatch")


def knowledge_sphere_capability_pipeline(task: dict[str, Any]) -> None:
    required = set(task["expected_answer"]["required_capabilities"])
    if not required.issubset(set(task["input"].get("capabilities", []))):
        raise FixtureError("missing required knowledge capabilities")
    if task["input"].get("sme_involvement") is not True:
        raise FixtureError("SME involvement must be explicit")


def taxonomy_induction_shape(task: dict[str, Any]) -> None:
    terms = set(task["input"].get("terms", []))
    for parent, child in task["input"].get("taxonomy_edges", []):
        if parent not in terms or child not in terms:
            raise FixtureError("taxonomy edge references missing term")
    if task["expected_answer"].get("valid_taxonomy") is not True:
        raise FixtureError("taxonomy expected valid")


def corpus_expansion_governance(task: dict[str, Any]) -> None:
    if task["input"].get("external_content_allowed") is not True or task["input"].get("provenance_required") is not True:
        raise FixtureError("corpus expansion requires explicit allowance and provenance")
    if task["expected_answer"].get("expansion_status") != "allowed_with_provenance":
        raise FixtureError("corpus expansion status mismatch")


def continuous_learning_retention(task: dict[str, Any]) -> None:
    inp = task["input"]
    if not (inp.get("teacher_model") and inp.get("student_model") and inp.get("old_data_retained") is False and inp.get("retention_score", 0) >= inp.get("retention_threshold", 1)):
        raise FixtureError("teacher-student retention contract failed")
    if task["expected_answer"].get("old_task_retained") is not True:
        raise FixtureError("old task retention expected")


def feature_vector_augmentation(task: dict[str, Any]) -> None:
    if task["input"].get("generate") != "feature_vector" or not task["input"].get("category_conditioning"):
        raise FixtureError("feature-vector augmentation must be conditioned")


def data_augmentation_policy_subsampling(task: dict[str, Any]) -> None:
    inp = task["input"]
    if inp.get("selected_fraction", 1.0) > inp.get("max_fraction", 1.0):
        raise FixtureError("selected fraction exceeds budget")
    if inp.get("selection_policy") not in {"high_loss", "high_influence", "hard_augmentation"}:
        raise FixtureError("unsupported selection policy")


def adversarial_augmentation_shape(task: dict[str, Any]) -> None:
    inp = task["input"]
    if not (inp.get("class_preserving") and inp.get("generator_selects_hard_cases") and inp.get("target_trains_on_hard_cases")):
        raise FixtureError("adversarial augmentation loop incomplete")


def semantic_parser_little_supervision(task: dict[str, Any]) -> None:
    required = {"tree_structure", "abstraction", "sketch", "weak_supervision"}
    if not required.issubset(set(task["input"].get("mechanisms", []))):
        raise FixtureError("little-supervision semantic parser mechanisms incomplete")


def key_point_analysis_prevalence(task: dict[str, Any]) -> None:
    counts: dict[str, int] = {}
    for row in task["input"]["sentence_to_key_point"]:
        counts[row["key_point"]] = counts.get(row["key_point"], 0) + 1
    if counts != task["expected_answer"]["key_point_counts"]:
        raise FixtureError("key-point prevalence mismatch")


def key_point_drilldown_mapping(task: dict[str, Any]) -> None:
    key_points = set(task["input"]["key_points"])
    mapped = {m["key_point"] for m in task["input"]["matches"]}
    if not key_points.issubset(mapped):
        raise FixtureError("each key point needs drilldown evidence")


def enterprise_data_lake_governance_architecture(task: dict[str, Any]) -> None:
    required = {"data_sources", "integration", "catalog", "curation", "security", "governance", "analytics_services"}
    if not required.issubset(set(task["input"].get("layers", []))):
        raise FixtureError("missing required EDL layers")


def public_cloud_knowledge_need_routing(task: dict[str, Any]) -> None:
    for key, value in task["expected_answer"]["routes"].items():
        if task["input"]["routes"].get(key) != value:
            raise FixtureError(f"route mismatch for {key}")
    if task["input"].get("slack_is_operational_surface") is not True:
        raise FixtureError("operational chat/help surface must be captured")


def desensitization_risk_taxonomy(task: dict[str, Any]) -> None:
    if not {"singling_out", "linkability", "inference"}.issubset(set(task["input"].get("risks", []))):
        raise FixtureError("missing desensitization risk family")


def high_assurance_desensitization_controls(task: dict[str, Any]) -> None:
    required = {"data_classification", "deterministic_keyed_prf", "hmac_sha256", "collision_resolution", "pk_fk_preservation", "verification_gate", "key_management"}
    if not required.issubset(set(task["input"].get("controls", []))):
        raise FixtureError("missing high-assurance desensitization control")


VERIFIERS: dict[str, Callable[[dict[str, Any]], None]] = {name: obj for name, obj in globals().items() if callable(obj) and name not in {"Any", "Callable", "main"} and not name.startswith("_")}


def check(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    checked: list[str] = []
    families: set[str] = set()
    verifiers: set[str] = set()
    for task in tasks:
        try:
            _shape(task)
            verifier = VERIFIERS.get(task["verifier"])
            if verifier is None:
                raise FixtureError(f"unsupported verifier {task['verifier']}")
            verifier(task)
            checked.append(task["task_id"])
            families.add(task["task_family"])
            verifiers.add(task["verifier"])
        except Exception as exc:
            errors.append(f"{task.get('task_id', '<unknown>')}: {exc}")
    return {
        "kind": "ReasoningTaskEvalFixtureCheck",
        "status": "passed" if not errors else "failed",
        "checked_tasks": checked,
        "checked_task_count": len(checked),
        "checked_families": sorted(families),
        "checked_family_count": len(families),
        "checked_verifiers": sorted(verifiers),
        "checked_verifier_count": len(verifiers),
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate reasoning-task eval fixture packs.")
    parser.add_argument("paths", nargs="*", type=Path, default=[Path("fixtures/reasoning-task-eval")])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary-text", action="store_true")
    args = parser.parse_args(argv)
    try:
        tasks, files = _tasks(args.paths)
        record = check(tasks)
        record["fixture_files"] = files
    except Exception as exc:
        record = {"kind": "ReasoningTaskEvalFixtureCheck", "status": "failed", "checked_tasks": [], "checked_task_count": 0, "checked_families": [], "checked_family_count": 0, "checked_verifiers": [], "checked_verifier_count": 0, "fixture_files": [str(p) for p in args.paths], "errors": [str(exc)]}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.summary_text:
        print(f"Reasoning task fixtures: {record['status']} ({record['checked_task_count']} tasks across {record['checked_family_count']} families)")
        for error in record["errors"]:
            print(f"ERROR: {error}", file=sys.stderr)
    return 0 if record["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
