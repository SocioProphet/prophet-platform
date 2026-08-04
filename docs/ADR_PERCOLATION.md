# ADR percolation — retrospective + the two-firewall (second-derivative) fix

## The failure (2026-08-04)

An ADR was recorded on 08-02: **migrate `source-os` / the Nix estate → Guix (+nonguix)**. It shipped
prose (a memory), a parity checklist (`guix/NIX_BASELINE.md`), and spike branches (`source-os#314/#315`).
Two days later an agent, directing platform work, told a sub-task to author a **new `.nix` package**
(`packages/sourceos-shell/default.nix`) — re-growing the very Nix surface the ADR is retiring. Nothing
stopped it. On the current `source-os` checkout there are **55 `.nix` files, 0 `.scm`, no `guix/` dir**;
the Guix spike is stranded off the branch new work forks from, so *100% of new work sees a pure-Nix
world*. Zero enforcement exists in any workflow.

The operator's diagnosis, verbatim and correct: **"when an ADR happens there needs to be a dependency
graph built"** — and, per failure mode, we must name the **meta-** and **meta-meta-**failure, which is
what yields *two* firewalls (a second-derivative dynamic), not one.

## The failure carried up its levels

| Level | Name | This case |
|---|---|---|
| **L0** | failure (position) | a new `.nix` authored inside an active Nix→Guix swap scope |
| **L1** | meta-failure (1st derivative) | the ADR built **no dependency graph and no gate** — no control *could* catch L0. Declared, never enforced |
| **L2** | meta-meta-failure (2nd derivative) | **nothing ensures every ADR builds its L1 control** — control-generation is optional, so its absence is invisible |

## The two firewalls

- **Firewall #1 — `adr_dependency_graph.py`** (answers L1). When an ADR is recorded it MUST build the
  blast-radius graph of the swap: every FROM-side artifact in scope as a node, reference edges between
  them (topologically ordered), each node's port status vs TO. From that graph:
  - **Wave 1 — PREVENT (fail-closed):** a gate over changed files. A new FROM artifact in scope,
    unwaived, is a violation. *This is the control that would have stopped R3* — verified against the
    real `source-os`: it blocks `packages/sourceos-shell/default.nix`.
  - **Wave 2 — DETECT→HEAL:** enumerate the residual FROM artifacts, order them leaves-first, emit a
    **sealed remediation plan** — the actionable port backlog (55 items here), because detect ≠ heal.

- **Firewall #2 — `adr_conformance_sentinel.py`** (answers L2). The **control-of-controls**: it audits
  *every* ADR and fails closed on any that lacks its Firewall #1 — so a decision can never again be
  carried without its graph + waves. It also measures the **second derivative**: let
  `gap = decisions − controls`; if `d²(gap)/dt² > 0` the estate is minting decisions *faster* than
  their controls — the meta-meta alarm. Run against the estate as-is, it correctly reports
  `ADR-0001-nix-to-guix` **unguarded** with an **accelerating** gap.

## Capping the regress (why two firewalls suffice)

Who guards Firewall #2? The tower would recurse (L3, L4, …). We cap it with a **fixpoint**: the
control-of-controls must appear in its *own* guarded registry (`self_governed`). A Firewall #2 that
governs itself needs no third firewall. The `failure_taxonomy.py` registry enforces that at least one
fixpoint entry (`firewall_1 == firewall_2`) exists, so the model is closed by construction.

## What now percolates

`governance/adr/ADR-0001-nix-to-guix.json` makes the Guix swap a **first-class object** the reasoning
consumes. The pattern is generic (library A→B, tool A→B) — Nix→Guix is instance one. Remaining work is
honest and named: wire Firewall #1 into `source-os` CI as a required check (so new `.nix` is blocked at
the PR), register every existing ADR in the sentinel, and land the guix scaffold on mainline so new
work forks from a world where Guix is visible.
