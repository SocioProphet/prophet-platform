"""Feature-ID discovery pass (work order section 5) -- the prerequisite for SAE presets.

Eight of the ten presets refuse to compile without a pinned artifact, because their
defining mechanism limb is expressed through feature steering. This is the pass that
produces it.

Three gates run before anything is written, because a feature artifact is the most
dangerous kind of output this repo produces: it is a list of integers that looks
authoritative, is perfectly reproducible, and carries no visible sign of being wrong.

  1. CONTRAST AUDIT   -- are the prompt sets minimal pairs, or is topic/length
                         confounded with the concept? (provenance.contrasts.audit)
  2. RELIABILITY      -- does the top-N survive being computed on a different half of
                         the prompts? A top-N list exists even on pure noise.
  3. WRITE            -- only then persist, with the contrast hash and per-concept
                         reliability embedded so any preset referencing this artifact
                         can be audited later.

``--force`` writes anyway and records the failures in the artifact rather than
pretending they did not happen.

Usage:
    python -m noetica_impair.experiments.discover_features \\
        --model gemma2-9b --layer 20 --sae-path /weights/gemma-scope-9b-pt-res/layer_20 \\
        --out artifacts/features-gemma2-9b-L20.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..models import loaders
from ..provenance import contrasts as C
from ..provenance.features import (
    CONCEPTS, discover, reliability_report, residual_encoder,
)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="discover-features", description=__doc__)
    ap.add_argument("--model", default="gemma2-9b", help="registry key")
    ap.add_argument("--layer", type=int, required=True, help="residual layer for the SAE")
    ap.add_argument("--sae-path", default=None, help="local Gemma Scope SAE directory")
    ap.add_argument("--sae-release", default=None, help="release id recorded in provenance")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--top-n", type=int, default=32)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--concepts", default=",".join(CONCEPTS))
    ap.add_argument("--min-overlap", type=float, default=0.30,
                    help="split-half overlap below which a concept is judged unstable")
    ap.add_argument("--synthetic-sae", action="store_true",
                    help="dry-run with a random dictionary; NEVER produces a usable artifact")
    ap.add_argument("--lexical-control", action="store_true",
                    help="also run discovery against UNTRAINED weights of the same shape; "
                         "concepts reliable there are lexical artifacts, not features")
    ap.add_argument("--force", action="store_true",
                    help="write despite failed gates, recording the failures")
    ap.add_argument("--device", default=None)
    ap.add_argument("--local-path", default=None, help="weights directory")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    concepts = tuple(c.strip() for c in args.concepts.split(",") if c.strip())

    # ── gate 1: the contrast sets themselves ────────────────────────────────
    audits = {c: C.audit(C.get(c)) for c in concepts}
    dirty = {c: a for c, a in audits.items() if not a.ok}
    print("contrast audit:")
    for c, a in audits.items():
        mark = "ok  " if a.ok else "WARN"
        print(f"  [{mark}] {c:<18} pairs={a.n_pairs} skew={a.length_skew:.2f} "
              f"overlap={a.mean_pair_overlap:.2f}")
        for w in a.warnings:
            print(f"         {w}")
        for n in a.notes:
            print(f"         note: {n}")
    if dirty and not args.force:
        print(f"\nREFUSING: {len(dirty)} contrast set(s) are confounded. A confounded "
              "contrast yields feature ids that steer the confound, not the concept.\n"
              "Fix the pairs, or pass --force to record the confound in the artifact.",
              file=sys.stderr)
        return 2

    # ── load ────────────────────────────────────────────────────────────────
    load_kw = {}
    if args.local_path:
        load_kw["local_path"] = args.local_path
    if args.device:
        load_kw["device"] = args.device
    lm = loaders.load(args.model, seed=args.seed, **load_kw)

    if args.synthetic_sae:
        from ..hooks.sae import SyntheticSAE
        d_model = getattr(lm.model.config, "hidden_size", None) or lm.meta.d_model
        sae = SyntheticSAE(d_model=d_model, d_sae=d_model * 4, layer=args.layer, seed=args.seed)
        print("\n*** SYNTHETIC SAE — a random dictionary has no features. This run can "
              "exercise the pipeline and MUST NOT be used to make a claim. ***")
    else:
        if not args.sae_path:
            print("--sae-path is required (or --synthetic-sae for a dry run)", file=sys.stderr)
            return 2
        from ..hooks.sae import load_gemma_scope
        sae = load_gemma_scope(args.sae_release or "", args.layer, local_path=args.sae_path)

    encode = residual_encoder(lm, args.layer)
    pairs = C.as_pairs(concepts)

    # ── discover + gate 2: reliability ──────────────────────────────────────
    print(f"\ndiscovering {len(concepts)} concepts at layer {args.layer} ...")
    art = discover(
        encode_residuals=encode, sae=sae, layer=args.layer, pairs=pairs,
        model_key=lm.meta.key, sae_release=args.sae_release, top_n=args.top_n,
        seed=args.seed,
    )

    # ── the lexical control ─────────────────────────────────────────────────
    # A concept can score high split-half reliability with NO semantic features present,
    # purely because its marker tokens differ (observed: self_reference at rank_corr
    # +0.93 on a randomly-initialised model, carried by i/my/me vs he/she/their).
    # Reliability proves the ranking is CONSISTENT, not that it found the concept.
    control: dict[str, float] = {}
    if args.lexical_control:
        from ..hooks.sae import SyntheticSAE
        print("\nlexical control (untrained weights — any reliability here is lexical):")
        ctl = loaders.load("toy-dense", seed=args.seed + 977, device="cpu")
        d_ctl = getattr(ctl.model.config, "hidden_size", None) or ctl.meta.d_model
        ctl_sae = SyntheticSAE(d_model=d_ctl, d_sae=d_ctl * 4,
                               layer=min(args.layer, ctl.meta.n_layers - 1),
                               seed=args.seed)
        ctl_encode = residual_encoder(ctl, min(args.layer, ctl.meta.n_layers - 1))
        from ..provenance.features import split_half_reliability
        for c in concepts:
            pres, absent = pairs[c]
            r = split_half_reliability(
                encode_residuals=ctl_encode, sae=ctl_sae, present=list(pres),
                absent=list(absent), top_n=args.top_n, seed=args.seed)
            control[c] = float(r.get("overlap") or 0.0)
            flag = "LEXICAL?" if control[c] >= args.min_overlap else "ok      "
            print(f"  [{flag}] {c:<18} control_overlap={control[c]:.2f}")
        suspect = [c for c, v in control.items() if v >= args.min_overlap]
        if suspect:
            print(f"         {len(suspect)} concept(s) reliable on UNTRAINED weights: "
                  f"{', '.join(suspect)} — their discovered ids likely encode marker "
                  "tokens rather than the concept. Treat any preset steering them as "
                  "unvalidated.")

    ok, problems = reliability_report(art, min_overlap=args.min_overlap)
    print("\nsplit-half reliability:")
    for c in concepts:
        rel = art.concepts.get(c, {}).get("reliability") or {}
        ov = rel.get("overlap")
        corr = rel.get("rank_correlation")
        mark = "ok  " if (ov is not None and ov >= args.min_overlap) else "WARN"
        print(f"  [{mark}] {c:<18} overlap={ov if ov is None else f'{ov:.2f}'} "
              f"rank_corr={corr if corr is None else f'{corr:+.2f}'}")
    for p in problems:
        print(f"         {p}")

    if not ok and not args.force:
        print("\nREFUSING to write: unstable concepts would pin presets to noise.\n"
              "Add more contrast pairs, pick a different layer, or pass --force.",
              file=sys.stderr)
        return 3

    # ── gate 3: write, carrying its own evidence ────────────────────────────
    payload = art.to_dict()
    payload["gates"] = {
        "contrast_audit": {c: {"ok": a.ok, "warnings": list(a.warnings),
                               "length_skew": a.length_skew,
                               "mean_pair_overlap": a.mean_pair_overlap,
                               "lexical_separability": a.lexical_separability,
                               "marker_tokens": list(a.marker_tokens),
                               "notes": list(a.notes)}
                           for c, a in audits.items()},
        "reliability_ok": ok,
        "reliability_problems": problems,
        "min_overlap": args.min_overlap,
        "forced": bool(args.force) and (bool(dirty) or not ok),
        "synthetic_sae": bool(args.synthetic_sae),
        "lexical_control": control or None,
        "lexical_suspects": sorted(c for c, v in control.items()
                                   if v >= args.min_overlap) or None,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(f"\nwrote {args.out}  (version {art.version})")
    if payload["gates"]["forced"]:
        print("*** FORCED: this artifact failed a gate. The failure is recorded in it. ***")
    if args.synthetic_sae:
        print("*** SYNTHETIC: not a usable artifact. ***")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
