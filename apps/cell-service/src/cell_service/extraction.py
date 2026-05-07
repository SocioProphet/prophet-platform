from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


class ExtractionError(ValueError):
    """Raised when a watch pattern cannot be compiled or applied."""


@dataclass(frozen=True)
class ExtractionResult:
    pattern_id: str | None
    pattern_kind: str
    matched: bool
    extractions: dict[str, str]
    confidence_score: float


VARIABLE_TYPES = {
    "word",
    "text",
    "time",
    "date",
    "number",
    "money",
    "entity",
    "url",
    "email",
    "location",
    "custom",
}

# Conservative token patterns. The extractor is deterministic and deliberately
# modest; richer NLP belongs behind a later adapter.
TYPE_PATTERNS = {
    "word": r"\w+",
    "text": r".+?",
    "time": r"[A-Za-z0-9: ]+(?:AM|PM|am|pm)?",
    "date": r"[A-Za-z]+\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}",
    "number": r"[+-]?(?:\d+(?:,\d{3})*|\d+)(?:\.\d+)?",
    "money": r"\$?\d+(?:,\d{3})*(?:\.\d{2})?",
    "entity": r".+?",
    "url": r"https?://[^\s]+",
    "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "location": r".+?",
    "custom": r".+?",
}

SUPPORTED_KINDS = {"typed_template", "claim_template", "phrase"}
LOCATION_TEMPORAL_SUFFIX = re.compile(
    r"\s+(?:this\s+week|this\s+month|this\s+year|today|tonight|tomorrow|next\s+week|next\s+month)$",
    flags=re.IGNORECASE,
)


def extract_from_pattern(pattern: dict[str, Any], text: str) -> ExtractionResult:
    """Apply a deterministic watch pattern to text.

    Supported now: typed_template, claim_template, and phrase. Phrase only emits
    matched=true/false. Template kinds emit variable extractions.
    """

    if not isinstance(text, str) or not text:
        raise ExtractionError("text must be non-empty string")
    kind = pattern.get("pattern_kind")
    if kind not in SUPPORTED_KINDS:
        raise ExtractionError(f"unsupported deterministic extraction pattern kind: {kind}")
    raw_expression = pattern.get("raw_expression")
    if not isinstance(raw_expression, str) or not raw_expression:
        raise ExtractionError("raw_expression must be non-empty string")

    if kind == "phrase":
        matched = raw_expression.lower() in text.lower()
        return ExtractionResult(
            pattern_id=pattern.get("id"),
            pattern_kind=kind,
            matched=matched,
            extractions={},
            confidence_score=1.0 if matched else 0.0,
        )

    variables = _variables(pattern)
    compiled = _compile_template(raw_expression, variables)
    match = compiled.search(text.strip())
    if not match:
        return ExtractionResult(
            pattern_id=pattern.get("id"),
            pattern_kind=kind,
            matched=False,
            extractions={},
            confidence_score=0.0,
        )

    extracted = {
        name: _clean(match.group(name), spec["type"])
        for name, spec in variables.items()
        if match.groupdict().get(name)
    }
    required = {name for name, spec in variables.items() if spec.get("required") is True}
    missing_required = sorted(required - set(extracted))
    if missing_required:
        return ExtractionResult(
            pattern_id=pattern.get("id"),
            pattern_kind=kind,
            matched=False,
            extractions=extracted,
            confidence_score=0.0,
        )
    confidence = min(1.0, 0.5 + 0.1 * len(extracted) + 0.1 * len(required))
    return ExtractionResult(
        pattern_id=pattern.get("id"),
        pattern_kind=kind,
        matched=True,
        extractions=extracted,
        confidence_score=confidence,
    )


def extract_with_patterns(patterns: list[dict[str, Any]], text: str) -> ExtractionResult:
    """Return the highest-confidence deterministic extraction across patterns."""

    if not patterns:
        raise ExtractionError("at least one pattern is required")
    results = [extract_from_pattern(pattern, text) for pattern in patterns]
    return max(results, key=lambda result: (result.matched, result.confidence_score, len(result.extractions)))


def _variables(pattern: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_variables = pattern.get("variables", [])
    if not isinstance(raw_variables, list):
        raise ExtractionError("variables must be a list")
    variables: dict[str, dict[str, Any]] = {}
    for variable in raw_variables:
        if not isinstance(variable, dict):
            raise ExtractionError("variable must be object")
        name = variable.get("name")
        vtype = variable.get("type")
        if not isinstance(name, str) or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            raise ExtractionError(f"invalid variable name: {name!r}")
        if vtype not in VARIABLE_TYPES:
            raise ExtractionError(f"invalid variable type for {name}: {vtype!r}")
        variables[name] = variable
    return variables


def _compile_template(expression: str, variables: dict[str, dict[str, Any]]) -> re.Pattern[str]:
    parts: list[str] = []
    cursor = 0
    variable_matches = list(re.finditer(r"\$([A-Za-z_][A-Za-z0-9_]*)", expression))
    if not variable_matches:
        return re.compile(re.escape(expression), flags=re.IGNORECASE)

    for index, match in enumerate(variable_matches):
        name = match.group(1)
        if name not in variables:
            raise ExtractionError(f"template references undeclared variable: {name}")
        literal = expression[cursor:match.start()]
        parts.append(_literal_to_regex(literal))
        if index + 1 < len(variable_matches):
            next_literal = expression[match.end() : variable_matches[index + 1].start()]
        else:
            next_literal = expression[match.end() :]
        variable_pattern = _bounded_variable_pattern(variables[name], next_literal)
        parts.append(f"(?P<{name}>{variable_pattern})")
        cursor = match.end()
    parts.append(_literal_to_regex(expression[cursor:]))
    return re.compile("".join(parts), flags=re.IGNORECASE)


def _literal_to_regex(literal: str) -> str:
    # Template spaces should tolerate arbitrary whitespace and simple punctuation.
    # When the original literal has surrounding whitespace, require at least one
    # whitespace character on that side to prevent keyword separators like " in "
    # from matching mid-word occurrences such as "build*ing*".
    leading_space = literal and literal[0].isspace()
    trailing_space = literal and literal[-1].isspace()
    escaped = re.escape(literal.strip())
    escaped = escaped.replace(r"\ ", r"\s+")
    if escaped:
        prefix = r"\s+" if leading_space else r"\s*"
        suffix = r"\s+" if trailing_space else r"\s*"
        return prefix + escaped + suffix
    return r"\s*"


def _bounded_variable_pattern(variable: dict[str, Any], next_literal: str) -> str:
    vtype = variable["type"]
    base = TYPE_PATTERNS[vtype]
    if next_literal.strip():
        return base
    if vtype in {"text", "entity", "location", "custom", "time"}:
        return r".+"
    return base


def _clean(value: str, variable_type: str) -> str:
    cleaned = value.strip(" \t\n\r.,;:")
    if variable_type == "location":
        cleaned = LOCATION_TEMPORAL_SUFFIX.sub("", cleaned).strip(" \t\n\r.,;:")
    return cleaned
