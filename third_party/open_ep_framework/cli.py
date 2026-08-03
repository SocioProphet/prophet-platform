import argparse
import json
from pathlib import Path

from .associated_surplus import run_associated_surplus
from .audit import write_audit_pack
from .breakeven import economic_profit_for_rate, solve_break_even_rate
from .capital import capital_charge
from .causal_identification import scenario_from_document
from .domain import CapitalStack, ExpectedLossInputs, FTPStack, PricingContext, RecoverySurfaceInputs
from .expected_loss import expected_loss_amount
from .ftp import ftp_rate
from .heller_mesh import run_heller_mesh
from .impact_vdt import run_impact_vdt
from .object_graph import ObjectGraph, lineage_aware_output
from .policy_simulation import run_policy_simulation_profile
from .policy_simulation_uvmc import run_policy_simulation_measured_entity
from .product_objects import build_instrument_context
from .recovery import market_implied_recovery, planning_recovery, recovery_wedge
from .relationship import RelationshipEffects, relationship_required_rate
from .settlement import run_settlement
from .validation import validate_json_file
from .vdt import run_vdt


def load_context(path: str):
    data = json.loads(Path(path).read_text())
    ftp_stack = FTPStack(**data["ftp_stack"])
    el = ExpectedLossInputs(**data["expected_loss"])
    recovery = RecoverySurfaceInputs(**data["recovery_surface"])
    capital = CapitalStack(**data["capital_stack"])
    context = PricingContext(
        balance=data["balance"],
        fee_income=data.get("fee_income", 0.0),
        expense=data.get("expense", 0.0),
        tax_rate=data.get("tax_rate", 0.0),
        funding_credits=data.get("funding_credits", 0.0),
        horizon_years=float(data.get("horizon_years", 1.0)),
    )
    return data, context, ftp_stack, el, recovery, capital


def _instrument_components(path: str) -> dict:
    validate_json_file(path, "schemas/synthetic_run.schema.json")
    data, context, ftp_stack, el, recovery, capital = load_context(path)
    hurdle_rate = float(data.get("hurdle_rate", 0.12))
    break_even_rate = solve_break_even_rate(context, ftp_stack, el, capital, recovery, hurdle_rate)
    ep_at_break_even = economic_profit_for_rate(break_even_rate, context, ftp_stack, el, capital, recovery, hurdle_rate)

    return {
        "ftp_rate": ftp_rate(ftp_stack),
        "expected_loss": expected_loss_amount(el),
        "planning_recovery": planning_recovery(recovery),
        "market_implied_recovery": market_implied_recovery(recovery),
        "recovery_wedge": recovery_wedge(recovery),
        "capital_charge": capital_charge(capital, hurdle_rate),
        "break_even_rate": break_even_rate,
        "economic_profit_at_break_even": ep_at_break_even,
    }


def run_example(path: str) -> dict:
    return _instrument_components(path)


def _relationship_items_to_transactions(items: list[dict]) -> list[dict]:
    return [
        {
            "transaction_id": item["id"],
            "balance": item["balance"],
            "break_even_rate": item["rate"],
            "capital": item["capital"],
            "expected_loss": item["loss"],
            "utilization": item["util"],
            "collateral_set_id": item["collateral"],
        }
        for item in items
    ]


def _relationship_calculation(path: str) -> dict:
    validate_json_file(path, "schemas/relationship.schema.json")
    data = json.loads(Path(path).read_text())
    effects = RelationshipEffects(**data["effects"])
    txs = _relationship_items_to_transactions(data["items"])
    outputs = relationship_required_rate(txs, effects)
    outputs["relationship_id"] = data["relationship_id"]
    return outputs


def run_relationship(path: str) -> dict:
    return _relationship_calculation(path)


def run_relationship_context(path: str, graph_path: str, relationship_object_id: str) -> dict:
    graph = ObjectGraph.from_json_file(graph_path, validate=True)
    calculation = _relationship_calculation(path)
    lineage = graph.lineage(relationship_object_id)
    if lineage.get("relationship_id") and lineage["relationship_id"] != calculation["relationship_id"]:
        raise ValueError("relationship fixture does not match object graph lineage")
    return {
        "calculation": calculation,
        "relationship_context": {
            "lineage": lineage,
        },
    }


def run_object_graph(path: str, object_id: str) -> dict:
    graph = ObjectGraph.from_json_file(path, validate=True)
    return lineage_aware_output(object_id, graph, {"economic_profit": 0.0})


def run_object_context(args) -> dict:
    return build_instrument_context(
        graph_path=args.graph,
        graph_object_id=args.object_id,
        account_path=args.account,
        instrument_path=args.instrument,
        transaction_event_path=args.event,
        collateral_path=args.collateral,
        funding_path=args.funding,
        hedge_path=args.hedge,
    )


def run_instrument_context(args) -> dict:
    return {
        "calculation": _instrument_components(args.example),
        "object_context": run_object_context(args),
    }


def _derive_audit_identity(inputs: dict, args) -> tuple[str, str]:
    if not isinstance(inputs, dict):
        return args.object_id, "base"
    if "audit_receipt" in inputs:
        receipt = inputs.get("audit_receipt", {})
        return receipt.get("run_id", args.object_id), inputs.get("scenario", {}).get("scenario_id", "base")
    if "calculation_receipt" in inputs:
        receipt = inputs.get("calculation_receipt", {})
        context = inputs.get("measurement_context", {})
        return receipt.get("run_id", args.object_id), context.get("scenario_ref", "base")
    run_id = inputs.get("run_id") or inputs.get("relationship_id") or args.object_id
    scenario = inputs.get("scenario", "base")
    return run_id, scenario


def main():
    p = argparse.ArgumentParser(prog="oepf")
    p.add_argument(
        "--mode",
        choices=[
            "instrument",
            "instrument-context",
            "relationship",
            "relationship-context",
            "object-graph",
            "object-context",
            "heller-mesh",
            "associated-surplus",
            "policy-simulation",
            "policy-simulation-uvmc",
            "vdt",
            "vdt-impact",
            "causal-scenario",
            "settlement",
        ],
        default="instrument",
    )
    p.add_argument("--example", default="examples/synthetic_run.json")
    p.add_argument("--audit", default="audit.json")
    p.add_argument("--object-id", default="instrument-loan-001")
    p.add_argument("--relationship-object-id", default="rel-synthetic-001")
    p.add_argument("--graph", default="examples/object_graph.json")
    p.add_argument("--account", default="examples/account.json")
    p.add_argument("--instrument", default="examples/instrument.json")
    p.add_argument("--event", default="examples/transaction_event.json")
    p.add_argument("--collateral", default="examples/collateral_set.json")
    p.add_argument("--funding", default="examples/funding_source.json")
    p.add_argument("--hedge", default="examples/hedge_set.json")
    args = p.parse_args()

    if args.mode == "relationship":
        outputs = run_relationship(args.example)
        inputs = json.loads(Path(args.example).read_text())
    elif args.mode == "relationship-context":
        outputs = run_relationship_context(args.example, args.graph, args.relationship_object_id)
        inputs = {"relationship_input": json.loads(Path(args.example).read_text()), "graph": args.graph, "relationship_object_id": args.relationship_object_id}
    elif args.mode == "object-graph":
        outputs = run_object_graph(args.example, args.object_id)
        inputs = json.loads(Path(args.example).read_text())
    elif args.mode == "object-context":
        outputs = run_object_context(args)
        inputs = {
            "graph": args.graph,
            "object_id": args.object_id,
            "account": args.account,
            "instrument": args.instrument,
            "event": args.event,
            "collateral": args.collateral,
            "funding": args.funding,
            "hedge": args.hedge,
        }
    elif args.mode == "instrument-context":
        outputs = run_instrument_context(args)
        inputs = {
            "instrument_input": json.loads(Path(args.example).read_text()),
            "graph": args.graph,
            "object_id": args.object_id,
            "account": args.account,
            "instrument": args.instrument,
            "event": args.event,
            "collateral": args.collateral,
            "funding": args.funding,
            "hedge": args.hedge,
        }
    elif args.mode == "heller-mesh":
        outputs = run_heller_mesh(args.example)
        inputs = outputs["measurement"]
    elif args.mode == "associated-surplus":
        outputs = run_associated_surplus(args.example)
        inputs = outputs["measurement"]
    elif args.mode == "policy-simulation":
        outputs = run_policy_simulation_profile(args.example)
        inputs = outputs["profile"]
    elif args.mode == "policy-simulation-uvmc":
        outputs = run_policy_simulation_measured_entity(args.example)
        inputs = outputs["profile"]
    elif args.mode == "vdt":
        outputs = run_vdt(args.example)
        inputs = outputs["profile"]
    elif args.mode == "vdt-impact":
        outputs = run_impact_vdt(args.example)
        inputs = outputs["profile"]
    elif args.mode == "settlement":
        # Conservation-law settlement (IC-1): rejects non-conserving ledgers.
        example = args.example
        if example == "examples/synthetic_run.json":
            example = "examples/conservation_settlement_balanced.json"
        outputs = run_settlement(example)
        inputs = json.loads(Path(example).read_text())
    elif args.mode == "causal-scenario":
        # The global --example default is an instrument doc, not a causal scenario;
        # fall back to the causal example when the user hasn't overridden it.
        example = args.example
        if example == "examples/synthetic_run.json":
            example = "examples/causal_scenario.json"
        inputs = json.loads(Path(example).read_text())
        outputs = scenario_from_document(inputs)
    else:
        outputs = run_example(args.example)
        inputs = json.loads(Path(args.example).read_text())

    run_id, scenario = _derive_audit_identity(inputs, args)
    write_audit_pack(args.audit, run_id, scenario, "0.1.0", {"input": inputs}, outputs)
    print(json.dumps(outputs, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
