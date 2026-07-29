

# jsonschema treats `format` as an ANNOTATION unless a checker is supplied, so the
# validator never enforced the schema's "format": "date-time". A structurally-valid event
# carrying "not-a-timestamp" passed the gate this module calls "schema-validated per
# event, fail-closed".


def test_date_time_format_is_actually_enforced():
    from market_replay.contract import VALIDATOR, build_event
    from market_replay.generator import Tick

    ev = build_event(Tick(symbol="SP:AAA", seq=1, price=1.0, volume=1), "2026-07-29T00:00:00Z")
    assert not list(VALIDATOR.iter_errors(ev)), "a well-formed event must still validate"

    broken = dict(ev)
    broken["wallTime"] = "not-a-timestamp"
    errs = list(VALIDATOR.iter_errors(broken))
    assert errs, "a malformed date-time must be REJECTED, not annotated"
    assert any("date-time" in str(e.message) or "format" in str(e.message) for e in errs), \
        f"the rejection must cite the format, got: {[e.message for e in errs]}"


def test_the_format_checker_is_not_silently_a_noop():
    """The trap this fix had to avoid.

    Draft202012Validator.FORMAT_CHECKER only carries a date-time entry when
    rfc3339-validator is installed. Passing the checker without the dependency turns the
    fix back into the no-op it replaces — silently, and only in whichever environment
    lacks the package. contract.py refuses to import in that state; this asserts the
    condition directly so the reason is visible rather than inferred from an ImportError.
    """
    from market_replay.contract import _FORMAT_CHECKER

    assert "date-time" in _FORMAT_CHECKER.checkers, \
        "date-time checking unavailable — install rfc3339-validator; format would be unenforced"
