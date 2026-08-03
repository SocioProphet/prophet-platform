from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .object_graph import ObjectGraph
from .validation import validate_json_file


@dataclass(frozen=True)
class Account:
    account_id: str
    relationship_id: str
    legal_entity_id: str
    line_of_business_id: str
    as_of: str
    cadence: str
    currency: str = ""
    balances: dict[str, Any] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Instrument:
    instrument_id: str
    account_id: str
    relationship_id: str
    legal_entity_id: str
    line_of_business_id: str
    as_of: str
    cadence: str
    product_type: str
    currency: str = ""
    notional: float = 0.0
    rate: float = 0.0
    maturity_date: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TransactionEvent:
    event_id: str
    instrument_id: str
    account_id: str
    relationship_id: str
    legal_entity_id: str
    line_of_business_id: str
    event_time: str
    event_type: str
    delta_balance: float = 0.0
    delta_exposure: float = 0.0
    delta_fee: float = 0.0
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CollateralSet:
    collateral_set_id: str
    as_of: str
    currency: str
    market_value: float = 0.0
    haircut: float = 0.0
    eligible_value: float = 0.0
    assets: list[Any] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FundingSource:
    funding_source_id: str
    as_of: str
    curve_name: str
    currency: str
    tenors: list[Any] = field(default_factory=list)
    rates: list[Any] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HedgeSet:
    hedge_set_id: str
    as_of: str
    currency: str
    instruments: list[Any] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)


def _load_validated(path: str, schema_path: str) -> dict:
    validate_json_file(path, schema_path)
    return json.loads(Path(path).read_text())


def load_account(path: str) -> Account:
    return Account(**_load_validated(path, "schemas/account.schema.json"))


def load_instrument(path: str) -> Instrument:
    return Instrument(**_load_validated(path, "schemas/instrument.schema.json"))


def load_transaction_event(path: str) -> TransactionEvent:
    return TransactionEvent(**_load_validated(path, "schemas/transaction_event.schema.json"))


def load_collateral_set(path: str) -> CollateralSet:
    return CollateralSet(**_load_validated(path, "schemas/collateral_set.schema.json"))


def load_funding_source(path: str) -> FundingSource:
    return FundingSource(**_load_validated(path, "schemas/funding_source.schema.json"))


def load_hedge_set(path: str) -> HedgeSet:
    return HedgeSet(**_load_validated(path, "schemas/hedge_set.schema.json"))


def _assert_equal(left: str, right: str, message: str) -> None:
    if left and right and left != right:
        raise ValueError(message)


def build_instrument_context(
    graph_path: str,
    graph_object_id: str,
    account_path: str,
    instrument_path: str,
    transaction_event_path: str | None = None,
    collateral_path: str | None = None,
    funding_path: str | None = None,
    hedge_path: str | None = None,
) -> dict:
    graph = ObjectGraph.from_json_file(graph_path, validate=True)
    account = load_account(account_path)
    instrument = load_instrument(instrument_path)
    event = load_transaction_event(transaction_event_path) if transaction_event_path else None
    collateral = load_collateral_set(collateral_path) if collateral_path else None
    funding = load_funding_source(funding_path) if funding_path else None
    hedge = load_hedge_set(hedge_path) if hedge_path else None

    lineage = graph.lineage(graph_object_id)
    _assert_equal(lineage.get("instrument_id", ""), instrument.instrument_id, "instrument fixture does not match object graph lineage")
    _assert_equal(lineage.get("account_id", ""), account.account_id, "account fixture does not match object graph lineage")
    _assert_equal(account.relationship_id, instrument.relationship_id, "account and instrument relationship mismatch")
    _assert_equal(account.legal_entity_id, instrument.legal_entity_id, "account and instrument legal entity mismatch")
    _assert_equal(account.line_of_business_id, instrument.line_of_business_id, "account and instrument LOB mismatch")

    if event:
        _assert_equal(event.instrument_id, instrument.instrument_id, "event and instrument mismatch")
        _assert_equal(event.account_id, account.account_id, "event and account mismatch")
        _assert_equal(event.relationship_id, instrument.relationship_id, "event and relationship mismatch")
        _assert_equal(event.legal_entity_id, instrument.legal_entity_id, "event and legal entity mismatch")
        _assert_equal(event.line_of_business_id, instrument.line_of_business_id, "event and LOB mismatch")

    return {
        "lineage": lineage,
        "account": account.__dict__,
        "instrument": instrument.__dict__,
        "transaction_event": event.__dict__ if event else None,
        "collateral_set": collateral.__dict__ if collateral else None,
        "funding_source": funding.__dict__ if funding else None,
        "hedge_set": hedge.__dict__ if hedge else None,
    }
