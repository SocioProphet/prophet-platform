"""GRL-mesh — federated reward aggregation (the pure core).

The sovereign, opt-in mesh for LEARNING signals. Each node's Graph-RL loop learns locally; nodes may
opt in to publish gate-redacted reward observations — (policy, action, context-bucket, reward) — and
this aggregates them into a community PRIOR that any node can pull to warm-start its own policy. So the
community gets better together without raw data ever leaving a node: only sufficient statistics travel
(a mean reward + a count per coarse context bucket), carried over the same envelope as the open-chat
commons (token + sovereign-id pseudonym + opt-in).

This is the substrate the mesh transport, new-hope and slash-topics ride on. Pure + in-memory so it is
trivially testable; the HTTP surface + token gate live in server.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Stat:
    reward_sum: float = 0.0
    n: int = 0

    @property
    def mean(self) -> float:
        return self.reward_sum / self.n if self.n else 0.0


@dataclass
class MeshAggregator:
    # (policy, action, context_bucket) -> Stat
    _stats: dict[tuple[str, str, str], Stat] = field(default_factory=dict)
    # per-policy set of sovereign-ids that contributed (privacy: pseudonyms only)
    _contributors: dict[str, set[str]] = field(default_factory=dict)
    published: int = 0

    def publish(self, policy: str, observations: list[dict], sovereign_id: str) -> int:
        """Fold a node's redacted observations into the running community statistics. Returns count accepted."""
        accepted = 0
        for o in observations:
            action = str(o.get("action", "")).strip()
            bucket = str(o.get("context_bucket", "")).strip()
            reward = o.get("reward")
            if not action or bucket == "" or not isinstance(reward, (int, float)):
                continue
            r = max(0.0, min(1.0, float(reward)))
            key = (policy, action, bucket)
            st = self._stats.get(key)
            if st is None:
                st = self._stats[key] = Stat()
            st.reward_sum += r
            st.n += 1
            accepted += 1
        if accepted:
            self._contributors.setdefault(policy, set()).add(sovereign_id)
            self.published += accepted
        return accepted

    def prior(self, policy: str) -> dict:
        """The community prior for a policy: mean reward + support per (action, context-bucket)."""
        priors = [
            {"action": a, "context_bucket": b, "mean_reward": round(st.mean, 4), "n": st.n}
            for (p, a, b), st in self._stats.items() if p == policy
        ]
        priors.sort(key=lambda x: (-x["mean_reward"], x["action"]))
        return {"policy": policy, "priors": priors, "contributors": len(self._contributors.get(policy, ()))}

    def policies(self) -> list[str]:
        return sorted({p for (p, _, _) in self._stats})
