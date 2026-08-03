#!/usr/bin/env python3
"""Enforce that every Argo Rollouts AnalysisTemplate metric is FAIL-CLOSED on no data.

A canary SLO metric that declares only ``failureCondition: result[0] >= X`` treats an
EMPTY Prometheus result — a service that does not export the queried recording rule — as
"not a failure": the step scores Successful and the rollout promotes a release that nothing
measured. Prometheus "no data" is not the same as "healthy". The estate shipped exactly this
shape (slo-gate, wired to hellgraph-service, which exports no metrics), so an unguarded gate
would let a broken canary graduate.

This check requires, for every metric whose success/failure condition thresholds on
``result[...]``, BOTH:

  * a successCondition that requires the series to EXIST   — ``len(result) > 0`` (or ``>= 1``), and
  * a failureCondition that fires when the series is ABSENT — ``len(result) == 0`` (or ``< 1``),

so that a missing series ABORTS the canary instead of promoting it.

Runs in the validate-target-diagnostics gate (``make canary-slo-gate-check``). It is proven
able to go red by tools/tests/test_check_canary_slo_gate.py, which feeds it a positive
(fail-closed) and a negative (failureCondition-only) fixture — a gate that has only ever
passed proves nothing.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]

ANALYSIS_KINDS = {"AnalysisTemplate", "ClusterAnalysisTemplate"}

# A metric is subject to the no-data trap when any of its conditions threshold on result[...].
_RESULT_REF = re.compile(r"\bresult\s*\[")
# Data-presence guard accepted forms: len(result) > 0  |  len(result) >= 1
_PRESENCE = re.compile(r"len\s*\(\s*result\s*\)\s*(?:>\s*0|>=\s*1)")
# Absent-data clause accepted forms: len(result) == 0  |  len(result) < 1  |  len(result) <= 0
_ABSENCE = re.compile(r"len\s*\(\s*result\s*\)\s*(?:==\s*0|<\s*1|<=\s*0)")


def _load_docs(text: str) -> tuple[list[dict[str, Any]], str | None]:
    """Parse every YAML doc. Returns (docs, error_name). Fail-closed: a parse error is
    surfaced to the caller, never swallowed — a manifest that will not parse cannot be
    certified fail-closed (swallowing it would let a malformed gate pass silently)."""
    try:
        return [d for d in yaml.safe_load_all(text) if isinstance(d, dict)], None
    except yaml.YAMLError as e:
        return [], type(e).__name__


def metric_violations(metric: dict[str, Any], where: str) -> list[str]:
    name = metric.get("name", "<unnamed>")
    succ = str(metric.get("successCondition", "") or "")
    fail = str(metric.get("failureCondition", "") or "")
    # Only metrics that threshold on a result value can silently pass on an empty series.
    if not (_RESULT_REF.search(succ) or _RESULT_REF.search(fail)):
        return []
    out: list[str] = []
    if not _PRESENCE.search(succ):
        out.append(
            f"{where}: metric '{name}' has no data-presence guard — add a successCondition "
            f"requiring len(result) > 0 so an empty series is not scored as healthy "
            f"(successCondition={succ!r})"
        )
    if not _ABSENCE.search(fail):
        out.append(
            f"{where}: metric '{name}' does not fail on absent data — add len(result) == 0 to "
            f"the failureCondition so a missing series ABORTS the canary "
            f"(failureCondition={fail!r})"
        )
    return out


def template_violations(doc: dict[str, Any], where: str) -> list[str]:
    md_name = (doc.get("metadata") or {}).get("name", "?")
    metrics = (doc.get("spec") or {}).get("metrics")
    out: list[str] = []
    if metrics is None or (isinstance(metrics, list) and not metrics):
        out.append(f"{where}: AnalysisTemplate '{md_name}' declares no metrics")
        return out
    if not isinstance(metrics, list):
        # Fail-closed on a malformed template: a non-list `spec.metrics` (e.g. a
        # mapping) would otherwise be iterated as keys and pass with zero violations.
        out.append(
            f"{where}: AnalysisTemplate '{md_name}' has a non-list `spec.metrics` "
            f"({type(metrics).__name__}) — cannot verify it fails closed"
        )
        return out
    for m in metrics:
        if isinstance(m, dict):
            out.extend(metric_violations(m, where))
    return out


def _canary_steps_of(doc: dict[str, Any]) -> Any:
    """The canary steps of a Rollout manifest, or of a Helm values file whose
    rollout.steps block the shared chart renders raw into a Rollout."""
    if doc.get("kind") == "Rollout":
        strat = ((doc.get("spec") or {}).get("strategy") or {}).get("canary") or {}
        return strat.get("steps")
    ro = doc.get("rollout")
    if isinstance(ro, dict):
        return ro.get("steps")
    return None


def analysis_step_violations(
    steps: Any, where: str, template_kinds: dict[str, str] | None = None
) -> list[str]:
    """A canary step's ``analysis`` takes a LIST of templates. A bare
    ``templateName`` is schema-invalid: ArgoCD server-side-apply rejects the whole
    Rollout (".spec.strategy.canary.steps[N].analysis.templateName: field not
    declared in schema"), so the Rollout is never created and the canary never runs
    — silently, because the app can still report Healthy from its other objects.

    Also checks ``clusterScope`` consistency against every AnalysisTemplate /
    ClusterAnalysisTemplate kind declared elsewhere in the repo (``template_kinds``,
    from ``collect_template_kinds``). A step referencing a ClusterAnalysisTemplate
    without ``clusterScope: true`` makes Argo Rollouts look for a namespaced
    AnalysisTemplate instead, find none, and reject the Rollout as InvalidSpec
    forever — the bug that outlived PR #1229 (which promoted slo-gate to
    cluster-scoped but left this reference unset), keeping hellgraph-service at
    zero pods after the fix everyone thought had already closed the outage."""
    out: list[str] = []
    if not isinstance(steps, list):
        return out
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        analysis = step.get("analysis")
        if not isinstance(analysis, dict):
            continue
        templates = analysis.get("templates")
        if not isinstance(templates, list) or not templates:
            if "templateName" in analysis:
                out.append(
                    f"{where}: canary step[{i}].analysis uses a bare `templateName` — the Argo "
                    f"Rollouts schema requires `templates: [{{templateName: ...}}]`. Server-side "
                    f"apply rejects a bare templateName, so the Rollout is never created and the "
                    f"canary never runs (a control that cannot fire)."
                )
            else:
                out.append(
                    f"{where}: canary step[{i}].analysis has no non-empty `templates` list "
                    f"(missing or empty) — nothing gates this step."
                )
            continue
        if not template_kinds:
            continue
        for t in templates:
            if not isinstance(t, dict):
                continue
            name = t.get("templateName")
            kind = template_kinds.get(name)
            if kind is None:
                continue
            cluster_scope = bool(t.get("clusterScope", False))
            if kind == "ClusterAnalysisTemplate" and not cluster_scope:
                out.append(
                    f"{where}: canary step[{i}] references '{name}', declared as a "
                    f"ClusterAnalysisTemplate, without `clusterScope: true` — Argo Rollouts "
                    f"will look for a namespaced AnalysisTemplate instead, find none, and "
                    f"reject the Rollout as InvalidSpec with zero pods."
                )
            elif kind == "AnalysisTemplate" and cluster_scope:
                out.append(
                    f"{where}: canary step[{i}] references '{name}' with `clusterScope: true`, "
                    f"but it is declared as a namespaced AnalysisTemplate, not a "
                    f"ClusterAnalysisTemplate — Argo Rollouts will look in the wrong scope "
                    f"and reject the Rollout as InvalidSpec."
                )
    return out


def collect_template_kinds(root: Path) -> dict[str, str]:
    """Map every AnalysisTemplate/ClusterAnalysisTemplate name declared anywhere in
    the repo to its kind, so canary steps can be checked for clusterScope
    consistency against the real declaration instead of trusting the reference."""
    kinds: dict[str, str] = {}
    for path in sorted(root.rglob("*.y*ml")):
        s = str(path)
        if "/node_modules/" in s or "/vendor/" in s or "/.git/" in s:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if not any(k in text for k in ANALYSIS_KINDS):
            continue
        docs, err = _load_docs(text)
        if err is not None:
            if any(m in text for m in _HELM_TEMPLATE_MARKERS):
                continue
            continue  # unparseable + no Helm markers: not our concern here, scan_text flags it
        for doc in docs:
            if doc.get("kind") in ANALYSIS_KINDS:
                name = (doc.get("metadata") or {}).get("name")
                if isinstance(name, str):
                    kinds[name] = doc["kind"]
    return kinds


_HELM_TEMPLATE_MARKERS = ("{{-", "{{.Values", "{{ .Values", "{{include", "{{ include", "{{toYaml", "{{ toYaml", "{{if", "{{ if", "{{range", "{{ range", "{{end", "{{ end")


def scan_text(
    text: str, where: str, template_kinds: dict[str, str] | None = None
) -> list[str]:
    docs, err = _load_docs(text)
    if err is not None:
        # A real Helm/go-template file breaks plain YAML parsing by design — it is
        # validated by rendering, not here. But Argo Rollouts' OWN `{{args.x}}`
        # metric-templating syntax (used inside quoted strings in AnalysisTemplate
        # queries) does NOT break YAML parsing, so a bare `{{`/`}}` substring check
        # here would (and for years silently did) skip the real shipped slo-gate
        # AnalysisTemplate entirely — a false negative that made
        # test_shipped_repo_is_clean pass for the wrong reason. Only skip when the
        # parse actually failed AND the text carries a real Helm control-flow
        # marker; otherwise a file that names these kinds and won't parse is
        # flagged, never silently skipped.
        if any(m in text for m in _HELM_TEMPLATE_MARKERS):
            return []
        # Fail CLOSED: a file that names a Rollout/AnalysisTemplate but will not parse
        # cannot be certified fail-closed — flag it, never silently skip it.
        return [
            f"{where}: names a Rollout/AnalysisTemplate but is not valid YAML ({err}) "
            f"— cannot verify it fails closed on no-data"
        ]
    out: list[str] = []
    for doc in docs:
        if doc.get("kind") in ANALYSIS_KINDS:
            out.extend(template_violations(doc, where))
        steps = _canary_steps_of(doc)
        if steps is not None:
            out.extend(analysis_step_violations(steps, where, template_kinds))
    return out


def scan_repo(root: Path) -> list[str]:
    template_kinds = collect_template_kinds(root)
    out: list[str] = []
    for path in sorted(root.rglob("*.y*ml")):
        s = str(path)
        if "/node_modules/" in s or "/vendor/" in s or "/.git/" in s:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        # Cheap prefilter — the kind/shape checks inside scan_text are authoritative.
        if not any(k in text for k in ("AnalysisTemplate", "Rollout", "rollout:")):
            continue
        out.extend(scan_text(text, str(path.relative_to(root)), template_kinds))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Enforce fail-closed Argo Rollouts SLO gates")
    ap.add_argument("--root", default=str(ROOT), type=Path, help="repo root to scan")
    args = ap.parse_args(argv)
    violations = scan_repo(Path(args.root))
    if violations:
        print("canary-slo-gate-check: FAIL — SLO AnalysisTemplate(s) are not fail-closed on no-data:")
        for v in violations:
            print(f"  - {v}")
        print(
            "\nWhy: an empty Prometheus series must ABORT a canary, not promote it "
            "('no data' != 'healthy'). See infra/k8s/rollouts/base/analysistemplate-slo.yaml."
        )
        return 1
    print("canary-slo-gate-check: OK — every AnalysisTemplate metric fails closed on absent data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
