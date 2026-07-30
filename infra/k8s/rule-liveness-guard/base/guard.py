#!/usr/bin/env python3
"""Rule-liveness guard: finds alert rules that are incapable of firing.

The defect
----------
`KubePersistentVolumeFillingUp` was loaded in Prometheus with `health=ok`,
`lastError=none`, `state=inactive`. It queried
`kubelet_volume_stats_available_bytes{job="kubelet"}` against a Prometheus with
no kubelet scrape job. Both metrics resolved to zero series, so the rule
evaluated an empty set forever and reported `inactive` — which on every
dashboard is indistinguishable from "the volumes are fine". The disk hit 100%.

This is not one bad rule. It is a whole class: any rule whose inputs do not
exist is a rule that cannot fail, and a control that cannot fail is not a
control. A first scan of this estate found 28 of them.

The signature
-------------
"Rule returns nothing" is the WRONG test — `up == 0` correctly returns nothing
when everything is up. The distinguishing question is whether the rule's INPUTS
exist:

    up == 0                                  -> `up` has 14 series      -> LIVE
    kubelet_volume_stats_available_bytes{..} -> selector has 0 series   -> DEAD

So this guard parses each rule expression into its vector selectors and asks
Prometheus whether each selector matches any series over a lookback window. A
rule whose every selector is empty cannot fire, no matter what happens in the
cluster.

Rules built on absent()/absent_over_time() are exempt by construction: reacting
to emptiness is their entire purpose.

Exemptions are declared, justified, and they expire
---------------------------------------------------
Some selectors are legitimately absent — this cluster has no RAID arrays, so
`node_md_disks` will never exist. Those are declared in policy.json. Every
exemption must carry a `reason`, an `expires` date, and — where the underlying
risk is still real — a `compensating_control` naming what covers it instead.
An expired exemption ALERTS. An undeclared dead rule ALERTS. That keeps the
allowlist from quietly becoming the place dead controls go to be forgotten.

This guard does not exempt itself: its own alerts are ordinary rules and are
scanned like everything else.

Failure is loud
---------------
Every abnormal outcome raises or alerts — an unparseable expression, an empty
rule list, an unreachable Prometheus, an unreachable Alertmanager. Silently
skipping what it cannot evaluate is the exact defect it exists to find.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

PROM = os.environ.get("PROM_URL", "http://kube-prometheus-stack-prometheus.observability.svc:9090")
ALERTMANAGER = os.environ.get(
    "ALERTMANAGER_URL", "http://kube-prometheus-stack-alertmanager.observability.svc:9093"
)
POLICY_PATH = os.environ.get("POLICY_PATH", "/etc/guard/policy.json")
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "7"))
DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
SERVICE_REF = "infra/k8s/rule-liveness-guard"
VERSION = "0.1"

# --------------------------------------------------------------------------- #
# PromQL vector-selector extraction
# --------------------------------------------------------------------------- #
FUNCTIONS = {
    "abs", "absent", "absent_over_time", "ceil", "changes", "clamp", "clamp_max",
    "clamp_min", "day_of_month", "day_of_week", "day_of_year", "days_in_month",
    "delta", "deriv", "exp", "floor", "histogram_avg", "histogram_count",
    "histogram_fraction", "histogram_quantile", "histogram_stddev",
    "histogram_stdvar", "histogram_sum", "holt_winters",
    "double_exponential_smoothing", "hour", "idelta", "increase", "info",
    "irate", "label_join", "label_replace", "ln", "log2", "log10",
    "mad_over_time", "minute", "month", "pi", "predict_linear", "rate",
    "resets", "round", "scalar", "sgn", "sort", "sort_desc", "sort_by_label",
    "sort_by_label_desc", "sqrt", "time", "timestamp", "vector", "year",
    "avg_over_time", "min_over_time", "max_over_time", "sum_over_time",
    "count_over_time", "quantile_over_time", "stddev_over_time",
    "stdvar_over_time", "last_over_time", "present_over_time",
    "acos", "acosh", "asin", "asinh", "atan", "atanh", "cos", "cosh", "sin",
    "sinh", "tan", "tanh", "deg", "rad",
}
AGGREGATIONS = {
    "sum", "min", "max", "avg", "group", "stddev", "stdvar", "count",
    "count_values", "bottomk", "topk", "quantile", "limitk", "limit_ratio",
}
KEYWORDS = {
    "by", "without", "on", "ignoring", "group_left", "group_right", "offset",
    "bool", "and", "or", "unless", "start", "end", "atan2", "inf", "nan",
}
LABEL_LIST_KEYWORDS = {"by", "without", "on", "ignoring", "group_left", "group_right"}
ABSENCE_FUNCS = {"absent", "absent_over_time"}

IDENT_START = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_:")
IDENT_CHAR = IDENT_START | set("0123456789")


class ParseError(Exception):
    pass


def _skip_string(expr, i):
    quote = expr[i]
    i += 1
    while i < len(expr):
        c = expr[i]
        if c == "\\" and quote != "`":
            i += 2
            continue
        if c == quote:
            return i + 1
        i += 1
    raise ParseError("unterminated string literal")


def _match(expr, i, opener, closer):
    depth = 0
    while i < len(expr):
        c = expr[i]
        if c in "\"'`":
            i = _skip_string(expr, i)
            continue
        if c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ParseError("unbalanced %s %s" % (opener, closer))


def _peek(expr, i):
    while i < len(expr) and expr[i] in " \t\n\r":
        i += 1
    return i


def extract_selectors(expr):
    """Return (selectors, uses_absence_func). Raises ParseError on anything odd."""
    selectors = []
    uses_absence = False
    i, n = 0, len(expr)
    while i < n:
        c = expr[i]
        if c == "#":
            while i < n and expr[i] != "\n":
                i += 1
            continue
        if c in "\"'`":
            i = _skip_string(expr, i)
            continue
        if c == "[":  # range / subquery: durations, not metrics
            i = _match(expr, i, "[", "]")
            continue
        if c == "{":  # bare {__name__="x"} selector
            end = _match(expr, i, "{", "}")
            selectors.append(expr[i:end])
            i = end
            continue
        if c in IDENT_START:
            j = i
            while j < n and expr[j] in IDENT_CHAR:
                j += 1
            word = expr[i:j]
            nxt = _peek(expr, j)
            if word in ABSENCE_FUNCS:
                uses_absence = True
            if word in FUNCTIONS or word in AGGREGATIONS:
                i = j
                continue
            if word in KEYWORDS:
                if word in LABEL_LIST_KEYWORDS and nxt < n and expr[nxt] == "(":
                    i = _match(expr, nxt, "(", ")")
                    continue
                i = j
                continue
            if nxt < n and expr[nxt] == "(":
                # Unknown identifier used as a function. Do not guess.
                raise ParseError("unknown function %r" % word)
            sel, k = word, j
            nk = _peek(expr, k)
            if nk < n and expr[nk] == "{":
                end = _match(expr, nk, "{", "}")
                sel, k = word + expr[nk:end], end
            selectors.append(sel)
            i = k
            continue
        i += 1
    return selectors, uses_absence


# --------------------------------------------------------------------------- #
# Receipts (contracts/EvidenceReceipt.v0.1.json)
# --------------------------------------------------------------------------- #
def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def emit(obj):
    sys.stdout.write(canonical(obj) + "\n")
    sys.stdout.flush()


def receipt(action, status, subject_ref, body, **extra):
    h = sha256(canonical(body))
    r = {
        "version": VERSION,
        "receipt_id": "evr-%s-%s" % (action, h[:32]),
        "created_at": utc_now(),
        "service_ref": SERVICE_REF,
        "action": action,
        "status": status,
        "subject_ref": subject_ref,
        "hash": h,
        "hash_algo": "sha256",
    }
    r.update(extra)
    return r


# --------------------------------------------------------------------------- #
# Prometheus / Alertmanager
# --------------------------------------------------------------------------- #
def http_json(url, timeout=45):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def prom_rules():
    d = http_json(PROM + "/api/v1/rules")
    if d.get("status") != "success":
        raise RuntimeError("prometheus /rules returned status=%s" % d.get("status"))
    groups = d["data"]["groups"]
    total = sum(len(g["rules"]) for g in groups)
    # An empty rule corpus is a broken scrape/config, never an all-clear.
    if total == 0:
        raise RuntimeError("prometheus reports ZERO rules loaded — refusing to report all-clear")
    return groups


def selector_series(selector, start, end):
    """How many series this selector matched over the window. -1 on error."""
    url = PROM + "/api/v1/series?" + urllib.parse.urlencode(
        {"match[]": selector, "start": start, "end": end}
    )
    try:
        d = http_json(url)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError):
        return -1
    if d.get("status") != "success":
        return -1
    return len(d.get("data") or [])


def split_selector(selector):
    """('metric_name', 'job="x"') -> bare name and the job matcher value if any."""
    name = selector.split("{", 1)[0].strip()
    job = None
    if "{" in selector:
        inner = selector[selector.index("{") + 1: selector.rindex("}")]
        for part in inner.split(","):
            part = part.strip()
            if part.startswith("job=") and "=~" not in part and "!=" not in part:
                job = part[4:].strip().strip('"').strip("'")
    return name, job


def diagnose(selector, start, end, cache):
    """Why does this selector match nothing? The cause changes what to do.

    DEAD-NO-TARGET     the job it names is not scraped at all, so no scraper will
                       ever produce this series. Structural. Critical.
    DEAD-LABEL-MISMATCH the bare metric DOES exist but the label matchers exclude
                       everything. Almost always a real bug -- a renamed label or
                       a selector copied from a different topology. Critical.
    DORMANT            the metric name has never appeared, but its target is up.
                       Usually a counter that is only created on first occurrence
                       (e.g. *_failures_total), or a disabled collector. Warning:
                       needs a human decision, not an automatic verdict.
    """
    name, job = split_selector(selector)

    if job is not None:
        key = 'up{job="%s"}' % job
        if key not in cache:
            cache[key] = selector_series(key, start, end)
        if cache[key] == 0:
            return "DEAD-NO-TARGET", "no scrape target with job=%r" % job

    if "{" in selector:
        if name not in cache:
            cache[name] = selector_series(name, start, end)
        if cache[name] > 0:
            return "DEAD-LABEL-MISMATCH", (
                "metric %s has %d series but the label matchers exclude all of them"
                % (name, cache[name])
            )

    return "DORMANT", "metric %s has never been reported" % name


def post_alerts(alerts):
    body = json.dumps(alerts).encode("utf-8")
    req = urllib.request.Request(
        ALERTMANAGER + "/api/v2/alerts",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status


def alert(name, severity, summary, description, **labels):
    a = {
        "labels": {
            "alertname": name,
            "severity": severity,
            "namespace": "observability",
            "service": "rule-liveness-guard",
        },
        "annotations": {"summary": summary, "description": description},
        "startsAt": utc_now(),
    }
    a["labels"].update({k: str(v) for k, v in labels.items()})
    return a


# --------------------------------------------------------------------------- #
# Policy
# --------------------------------------------------------------------------- #
def load_policy():
    with open(POLICY_PATH, "r", encoding="utf-8") as fh:
        p = json.load(fh)
    exempt = {}
    for e in p.get("expected_absent", []):
        for field in ("rule", "reason", "expires"):
            if field not in e:
                raise RuntimeError("policy exemption missing %r: %r" % (field, e))
        exempt[e["rule"]] = e
    return p, exempt


def main():
    started = time.time()
    policy, exempt = load_policy()
    now = int(time.time())
    start = now - LOOKBACK_DAYS * 86400

    groups = prom_rules()

    live, dead, exempted, expired, unparseable, absence_based = [], [], [], [], [], []
    cache = {}
    checked = 0

    for g in groups:
        for r in g["rules"]:
            if r.get("type") != "alerting":
                continue
            checked += 1
            name = r["name"]
            key = "%s/%s" % (g["name"], name)
            try:
                sels, uses_absence = extract_selectors(r["query"])
            except ParseError as exc:
                unparseable.append((key, str(exc)))
                continue
            if uses_absence:
                absence_based.append(key)
                continue
            if not sels:
                continue

            counts = []
            for s in sels:
                if s not in cache:
                    cache[s] = selector_series(s, start, end=now)
                counts.append((s, cache[s]))

            errored = [s for s, c in counts if c < 0]
            if errored:
                unparseable.append((key, "series lookup failed for %s" % errored[0][:80]))
                continue

            empty = [s for s, c in counts if c == 0]
            if len(empty) != len(counts):
                live.append(key)
                continue

            # Every input is empty. WHY it is empty decides what to do about it.
            kind, why = diagnose(empty[0], start, now, cache)
            ex = exempt.get(name) or exempt.get(key)
            if ex:
                if ex["expires"] < utc_now()[:10]:
                    expired.append((key, ex))
                else:
                    exempted.append((key, ex))
            else:
                dead.append((key, name, empty, kind, why))

    # ---------------- report ----------------
    alerts = []
    # DORMANT is a warning, not a verdict: the target is up and the metric may
    # simply not have been created yet (counters like *_failures_total appear on
    # first occurrence). The other two kinds are structural and cannot self-heal.
    severity_for = {
        "DEAD-NO-TARGET": "critical",
        "DEAD-LABEL-MISMATCH": "critical",
        "DORMANT": "warning",
    }
    for key, name, empty, kind, why in dead:
        alerts.append(
            alert(
                # Deliberately a DIFFERENT alertname per severity.
                #
                # The first live run of this guard emitted all nine findings as
                # `AlertRuleDead` and Alertmanager suppressed six of them: the
                # stack's default inhibit_rules drop severity=warning when a
                # severity=critical shares the same (namespace, alertname), and
                # every finding here carries namespace=observability. Six real
                # findings were swallowed by a control that reported success —
                # this guard reproducing, in its own delivery path, exactly the
                # defect it was written to detect.
                #
                # Distinct alertnames make the two classes uninhibitable by each
                # other. Do not merge them back into one name.
                "AlertRuleDead" if severity_for.get(kind) == "critical" else "AlertRuleDormant",
                severity_for.get(kind, "critical"),
                "Alert rule %s cannot fire (%s)" % (name, kind),
                "Rule %s evaluates against selectors that matched no series in the last %dd — %s. "
                "It reports inactive forever regardless of cluster state, which on a dashboard is "
                "indistinguishable from healthy. Fix the query or the scrape, delete the rule, or "
                "declare it in infra/k8s/rule-liveness-guard/base/policy.json with a reason, an "
                "expiry and a compensating control. Empty selectors: %s"
                % (key, LOOKBACK_DAYS, why, ", ".join(e[:100] for e in empty[:3])),
                rule=key,
                kind=kind,
                dead_selectors=str(len(empty)),
            )
        )
    for key, exc in unparseable:
        alerts.append(
            alert(
                "AlertRuleUnscannable",
                "warning",
                "Rule %s could not be checked for liveness" % key,
                "The liveness guard could not evaluate %s (%s). An unscannable rule is treated as "
                "a finding, not skipped — otherwise this guard would have the same blind spot it "
                "exists to remove." % (key, exc),
                rule=key,
            )
        )
    for key, ex in expired:
        alerts.append(
            alert(
                "AlertRuleExemptionExpired",
                "warning",
                "Dead-rule exemption for %s expired on %s" % (key, ex["expires"]),
                "This rule is still dead and its declared exemption (%s) has expired. Re-justify "
                "it or fix it." % ex["reason"],
                rule=key,
            )
        )

    summary = {
        "checked": checked,
        "live": len(live),
        "dead": len(dead),
        "exempted": len(exempted),
        "expired": len(expired),
        "unscannable": len(unparseable),
        "absence_based": len(absence_based),
        "selectors_tested": len(cache),
        "lookback_days": LOOKBACK_DAYS,
    }

    body = {
        "summary": summary,
        "dead_rules": sorted("%s [%s]" % (k, kind) for k, _n, _e, kind, _w in dead),
        "unscannable_rules": sorted(k for k, _ in unparseable),
        "expired_exemptions": sorted(k for k, _ in expired),
        "prometheus": PROM,
    }
    status = "succeeded" if not (dead or unparseable or expired) else "partial"

    delivered = None
    if alerts and not DRY_RUN:
        try:
            post_alerts(alerts)
            delivered = len(alerts)
        except Exception as exc:  # noqa: BLE001 - must never be silent
            emit(
                receipt(
                    "rule-liveness-scan",
                    "failed",
                    "prometheus/observability",
                    {"error": "alertmanager delivery failed: %s" % exc, **body},
                )
            )
            print("FATAL: could not deliver %d alerts: %s" % (len(alerts), exc), file=sys.stderr)
            raise SystemExit(2)

    emit(
        receipt(
            "rule-liveness-scan",
            status,
            "prometheus/observability",
            body,
            metrics={**summary, "alerts_delivered": delivered or 0,
                     "duration_s": round(time.time() - started, 2)},
            policy_refs=["%s/policy.json" % SERVICE_REF],
            evidence_refs=[PROM + "/api/v1/rules"],
        )
    )

    # Human-readable tail for `kubectl logs`.
    print("checked=%(checked)d live=%(live)d DEAD=%(dead)d exempt=%(exempted)d "
          "expired=%(expired)d unscannable=%(unscannable)d" % summary, file=sys.stderr)
    for key, _name, empty, kind, why in dead:
        print("  %-20s %s  <- %s" % (kind, key, why), file=sys.stderr)
    for key, exc in unparseable:
        print("  UNSCANNABLE  %s  (%s)" % (key, exc), file=sys.stderr)
    for key, ex in expired:
        print("  EXPIRED-EXEMPTION  %s  (%s)" % (key, ex["expires"]), file=sys.stderr)

    # Exit 0 on a completed scan, EVEN WITH FINDINGS.
    #
    # The first in-cluster run exited 1 because it found dead rules, which
    # tripped backoffLimit and left the Job in BackoffLimitExceeded. That would
    # have meant the CronJob failed every hour for as long as any dead rule
    # existed — a permanently-red Job that everyone learns to ignore, and
    # RuleLivenessGuardFailing rendered meaningless.
    #
    # Findings travel by ALERT, which is the channel built for them and which is
    # now actually delivered. A non-zero exit is reserved for the guard itself
    # being broken: unreachable Prometheus, an empty rule corpus, or undelivered
    # alerts (all of which raise above). "Found problems" is a successful scan.
    return


if __name__ == "__main__":
    main()
