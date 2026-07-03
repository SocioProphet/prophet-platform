from __future__ import annotations

from enum import Enum


class Reasoning(str, Enum):
    """
    Provider-agnostic depth hint — mirrors Apple FM's .light/.moderate/.deep/.custom
    and maps onto the agent-execution-model-routing-policy lanes.
    """
    LIGHT    = "light"     # local-cheap lane: smallest fast local model, no fallback
    MODERATE = "moderate"  # standard lane: primary local workhorse
    DEEP     = "deep"      # high-end lane: primary local → hosted fallback if key present
    SOVEREIGN = "sovereign" # local-only regardless of depth; no hosted egress


class RoutePolicy(str, Enum):
    """Hard routing override — takes precedence over Reasoning lane selection."""
    LOCAL_FIRST  = "local-first"   # prefer local; hosted fallback allowed on DEEP
    LOCAL_ONLY   = "local-only"    # never egress to a hosted provider
    HOSTED_OK    = "hosted-ok"     # allow hosted provider at MODERATE+


# Maps Reasoning → (local_model_env_key, hosted_allowed, effort)
_LANE_DEFAULTS: dict[Reasoning, tuple[str, bool, str]] = {
    Reasoning.LIGHT:     ("PROPHET_LIGHT_MODEL",    False, "low"),
    Reasoning.MODERATE:  ("PROPHET_MODERATE_MODEL", False, "medium"),
    Reasoning.DEEP:      ("PROPHET_DEEP_MODEL",     True,  "high"),
    Reasoning.SOVEREIGN: ("PROPHET_MODERATE_MODEL", False, "medium"),
}


def lane_for(reasoning: Reasoning, policy: RoutePolicy | None) -> tuple[str, bool, str]:
    """
    Returns (local_model_env_key, hosted_allowed, effort).
    RoutePolicy.LOCAL_ONLY always disables hosted regardless of reasoning.
    RoutePolicy.HOSTED_OK enables hosted for MODERATE upward.
    """
    env_key, hosted, effort = _LANE_DEFAULTS[reasoning]
    if policy is RoutePolicy.LOCAL_ONLY or reasoning is Reasoning.SOVEREIGN:
        hosted = False
    elif policy is RoutePolicy.HOSTED_OK and reasoning in (Reasoning.MODERATE, Reasoning.DEEP):
        hosted = True
    return env_key, hosted, effort
