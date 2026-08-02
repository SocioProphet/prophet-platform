# DevSecOps Retrospective and Recovery v0.1

Status: post-mortem + recovery program (design doc with shipped guards)
Plane: Prophet Platform DevSecOps Intelligence Workroom
Umbrella: `SocioProphet/prophet-platform#519`
Companion: the Wave-0 DevSecOps design produced this session (recon + architecture;
live plane `apps/devsecops-intelligence/`, receipts on the
`contracts/EvidenceReceipt.v0.1.json` spine, meta-control = the **Control Teeth
Register**). This document is the reflective half of that work: it names what
broke while the estate was being built and turns each failure into a durable guard.

Prior lineage (committed): `docs/architecture/devsecops-intelligence-workroom-v0.1.md`
and the `docs/architecture/devsecops-workroom-*-v0.1.md` scope notes, closed under
`devsecops-workroom-v0.1-status.md`.

> **Provenance note (a live class-D instance — read this first).** The Wave-0
> design and the Control Teeth Register it defines are, at the time of writing,
> **not committed to `origin/main`**. A content sweep of the whole prophet-platform
> tree (8,471 files, node walker — not shimmed grep) finds zero occurrences of
> "Control Teeth Register" or the path `apps/devsecops-intelligence/`. The design
> that specifies our recovery program is itself single-copy, in-flight work. That
> is not an aside; it is Failure Class D happening to the very artifact meant to
> cure it, and it is why this document cross-links Wave-0 by *intent* rather than
> by a committed SHA. **Proof obligation:** this doc is not "done" until the Wave-0
> design is pushed and this note can be replaced with its commit/PR reference.

## How to read this

This is a post-mortem, not a victory lap. One build cycle produced real
capability and a long tail of silent failures; the failures are the subject here.

Two of the seven classes — **F (verified commands, not artifacts)** and **G
(instruments lied silently)** — are substantially *the operator's own mistakes*:
claims accepted because a command exited zero, conclusions built on a `grep` that
silently returned empty. They are written that way on purpose. A retrospective
that launders operator error into "tooling gaps" learns nothing.

Each class below has the same shape:

- **What happened** — the observed incident(s).
- **Root cause** — the mechanism, not the symptom.
- **Program change + proof obligation** — the durable guard, and the crisp test
  that means it is real: *done when X is observed failing, then passing.* A guard
  with no red-then-green proof is exactly the disease it is meant to cure.

---

## The seven failure classes

### A. Controls that cannot fail — *the keystone*

**What happened.** 22+ instances in one cycle of a control that structurally
could not report the failure it existed to catch:

- an alert with `health=ok` computed over a **zero-length** metric series (no data
  read as healthy);
- a required check that emitted **no verdict for three commits** — six-hour runs
  ending in `cancelled`, which a rollup renders as absent, not failed;
- a provenance checker that **printed its own success line** regardless of what it
  read (a receipt invariant that computed its own sha256, built the string, and
  asserted the string it had just built);
- `assert`-based validation that **vanishes under `python -O`**;
- a `.sourceos/manifest.json` **nothing reads**;
- provider pins **nothing loads**;
- `track-minor` implemented as `track-major`;
- a trust-floor a caller **sets for itself**;
- `tools/validate_manifest_declarations.py`, whose own `KNOWN_UNIMPLEMENTED` string
  literals entered its `git ls-files` corpus at commit time, so **every deferred
  item matched itself** and the check went green the moment it was tracked
  (correct on the authoring branch, silently vacuous forever after merge).

**Root cause.** A check that inspects an *artifact* ("does it import?", "is there a
PROVENANCE.md?", "does the string match?") passes trivially while the *connection*
it was supposed to prove is absent. Only a check of the connection can fail. This
is the estate's first rule — *ask what calls this* — living inside the verification
layer: the guard was built correctly and wired to nothing, and every gate that
inspected the guard reported green.

**Program change + proof obligation.** The **Control Teeth Register** (Wave 2, the
keystone; scoped below, not built here). Every control is an entry with a
mandatory `red_proof`: a committed mutation that makes it fail, exercised on a
cadence. A control with no green→red→green transition on record is `SUSPECT` and
does not count as coverage.
*Done when* a scheduled mutation flips each registered control red and the register
records the transition; a control that cannot be made to fail is quarantined, not
trusted. Cross-ref: `feedback_self_validating_checker`, `feedback_ask_what_calls_this`,
`project_declared_unenforced_register`, `project_blueprint_audit_verdict`.

### B. Substrate ate itself

**What happened.**

- A laptop disk reached **0 bytes**; `ENOSPC` silently killed a `git commit`
  mid-write and hard-blocked every lane (see Class D for what was lost with it).
- An **agent-machine test suite wrote through modules that resolved paths under the
  real `~/.noetica`** and destroyed the operator's live A2A trust ledger —
  *unrecoverably* — leaving **921 residue directories**. The test "passed".
- Registry MinIO hit **100% full** and silently failed image pushes.

**Root cause.** Non-hermetic execution against operator state. Tests and jobs ran
with write authority over the real `$HOME` and shared substrate, and nothing
distinguished "sandbox scratch" from "the live ledger". Disk and quota exhaustion
presented as unrelated command failures instead of a named substrate state.

**Program change + proof obligation.** (1) **Ephemeral cloud execution** for
suites that can mutate substrate (scoped below — its own wave). (2) **Test-
hermeticity gate** — *built this wave*, see `tools/check_test_hermeticity.py`: a
test-reachable module that resolves a non-redirectable **write** path under real
`$HOME` fails the gate. (3) **Backup-before-mutate** for any op that overwrites
operator state (scoped: hook, below).
*Done when* the hermeticity gate flags a planted `Path.home()/…` write and stays
green on the env-redirectable form — **observed both ways this wave** (6/6 selftest
cases). Cross-ref: Noetica #585 (the specific `lib/` fix this generalises).

### C. Budget masqueraded as failure

**What happened.** The GitHub Actions **spend cap** was reached; ~**456 runs
queued**; for hours this read as "runner saturation" and blocked merges. Because a
capped/queued job presents as `action_required` or as an absent verdict — never as
an explicit "you are out of budget" — the required check simply never reported and
PRs blocked *silently*. The proximate burn: **unbounded 6-hour test hangs** that
consumed the allowance and held runners the whole time.

**Root cause.** Two compounding gaps. (1) Billing/quota is not a monitored state,
so exhaustion is indistinguishable from infrastructure failure. (2) **Not one job
in the repo declared a `timeout-minutes` bound**, so any hung step ran to
GitHub's 360-minute (6h) default — a budget bomb on every job.

**Program change + proof obligation.** (1) **Billing/quota as a first-class
monitored state** (scoped below — do not conflate a bill with an outage). (2)
**Runaway-job hard-timeout policy**, enforced by the **timeout auditor** — *built
this wave*, `tools/check_workflow_timeout_bounds.py`. (3) **Absent-verdict
detector**: a required check that reports *nothing* for N commits is treated as
red, not neutral (scoped below).
*Done when* the auditor fails on any unbounded job and the count of unbounded jobs
trends to zero. **Measured today: 122 of 123 jobs across 105 workflows are
unbounded** (the 123rd is a reusable-workflow call, exempt-but-surfaced). See the
guards ledger. Cross-ref: `project_ci_throughput_path_filters` (PR #1045/#1101).

### D. Recovery fragile — single-copy work

**What happened.** **47 + 43 + 33 unpushed commits** across three repos, plus a
`git stash` holding the **sole copy** of the ST018 sovereign-Gitea manifest — all
on the one disk that hit zero (Class B). Work that exists in exactly one place is
one `ENOSPC` from gone. (Estate-wide, a later audit found **184 stranded
branches / 783 commits** with no route to main — though note that `ahead_by` alone
over-counts strandedness ~4×; only a blob-level test is truth. See Class G.)

**Root cause.** No visibility of single-copy work before the disk died, and no
push-early discipline. The cost is asymmetric: pushing is cheap and constant;
reconstructing lost uncommitted work is impossible.

**Program change + proof obligation.** (1) **Unpushed-work / single-copy detector**
— *built this wave*, `tools/detect_unpushed_single_copy.py`: reports commits,
stashes, and dirty worktrees that exist on no remote, across the dev roots. (2)
**Push-early doctrine** + a commit/stop hook that surfaces single-copy work
(scoped: hook, below).
*Done when* the detector flags a planted local-only commit and clears the instant
it is pushed — **observed both ways this wave** (4/4 selftest cases, full
lifecycle). Cross-ref: `project_stranded_work_register`.

### E. Resume-from-intent

**What happened.** Lanes died mid-`chown`, mid-delete, and mid-canary. On resume,
work restarted from the *intended* end state rather than the *actual* partial
state, so operations double-applied — re-running a half-finished `chown`, deleting
what a prior half-run had already moved, promoting a canary that was already half-
promoted. A related shape: an ordered rollback (boot #50 then source-os #305) where
resuming out of order was a silent no-op because the order was load-bearing.

**Root cause.** Operations assumed a clean starting point and were not idempotent.
Recovery read the plan, not the ground.

**Program change + proof obligation.** **Idempotent, state-re-reading ops**: every
recovery step re-derives current state and computes the delta, so re-running is a
no-op, not a double-apply. Ordered sequences carry an explicit precondition check
per step.
*Done when* each recovery runbook step passes a re-entrancy test — run it, kill it
mid-way, run it again, and assert the end state is identical and side-effect-free.
(Design this wave; enforcement scoped.) Cross-ref: `project_rollback_silent_noop`.

### F. Verified the command, not the artifact — *operator error*

**What happened.** Repeatedly this cycle, a claim was accepted because a *command*
succeeded, while the *artifact* told a different story. These were the operator's
own calls, and they are logged as such:

- **"pushed, nothing lost"** — the `git push` ran; the commit it was meant to carry
  had never landed (the `git commit` had died on `ENOSPC`). `git ls-remote` would
  have shown the SHA absent.
- **"Copilot triggered"** — a comment was posted; Copilot was never a *registered
  reviewer* on the PR, so no review ran. A comment is not a reviewer.
- **`0F/8P` read as green** — the required context was *absent* from the rollup, not
  passing; "no failures shown" was read as "no failures".
- **stale memory passed as a live constraint** — a remembered fact was quoted as a
  current blocker without re-checking the artifact it described.

**Root cause.** Confusing an action's *exit status* with its *effect*. A zero exit
proves the command ran, never that the world changed the way intended.

**Program change + proof obligation.** **Every claimed action is verified against
its artifact**, and ChatOps must *show its warrant* rather than report intent:
"pushed" ships the `git ls-remote` line; "reviewer requested" ships the reviewer
list; "green" ships the list of *required* contexts present, not the absence of red.
*Done when* the Workroom report surface refuses to render a claim without its
artifact reference (ties to the `EvidenceReceipt.v0.1.json` spine: a claim with no
`evidence_refs` is not a claim). Cross-ref: `feedback_ask_what_calls_this`,
`feedback_subagent_verification`, `project_copilot_review_backlog`.

### G. Instruments lied silently — *operator error, compounded by shimmed tools*

**What happened.** Load-bearing conclusions were built on tools that returned empty
or wrong *without erroring*. The operator trusted a clean result from an instrument
that could silently return nothing:

- **`grep`/`rg`/`find` are shimmed here.** `rg` runs via a shim (`ARGV0=rg`) that
  inherits gitignore/hidden defaults; `grep` is a shell function routing to a
  `ugrep` shim that honours `.gitignore` (so `dist/`, `target/`, venvs are
  invisible); even real BSD `grep` classifies invalid-UTF-8 files as binary and
  returns **no match, silently**. A whole wrong blocker ("the super-peer deploy is
  blocked on a missing engine symbol") was reported and acted on — worktree torn
  down, a version bump reverted — because `grep` returned empty for a symbol that
  `node -e 'Object.keys(require(p))'` and the Read tool showed was present the
  whole time.
- **`diff -rq` under-reports**; a `zsh` `:a` modifier corrupted a ref; **`RC=$?`
  caught `tail`, not `npm`** (last-command-in-pipeline); stale worktrees gave
  false-clean; `gh` `issues/N/comments` had **~3% recall** and "no new comments"
  carried **25 findings**; a scanner reported "fixed" having read nothing.
- The stranded-work audit itself (Class D) was initially **4× too high** because
  `ahead_by` counts squash-merge residue as loss; and its first blob-audit reported
  *every* branch unique because a `git rev-list --objects` pipe was fed `sha path`
  and resolved nothing — an **empty control set read as "all unique"**.

**Root cause.** Trusting a *clean/empty* result from a tool that can return empty
for reasons unrelated to truth. An empty grep is not evidence of absence; it is
untrusted until a second, independent instrument agrees.

**Program change + proof obligation.** (1) A **tooling-trust register** (see Config
Reoptimization): for each instrument, its known silent-failure mode and the
verified alternative. (2) **Load-bearing scans use verified methods** — a node
walker sanity-checked against a *known positive*, blob-hash comparison with
positive **and** negative controls — never a bare `grep`. (3) Never conclude
absence from one instrument.
*Done when* every load-bearing presence/absence claim in the Workroom is produced
by a method that was first shown to *find the thing it is looking for* on a control
(the walker in this very doc's guards was sanity-checked against a known-positive
string before its zero results were trusted). Cross-ref:
`feedback_grep_false_negatives_verify_with_node`, `project_stranded_work_register`.

---

## Config reoptimization — recommendations (propose; operator applies)

> **These are recommendations, not changes.** Nothing in `~/.claude/`, `CLAUDE.md`,
> `settings.json`, or the permission set has been modified by this work — the
> harness executes hooks and enforces permissions, so an *agent* cannot and must
> not self-authorize them. Each row names **who applies**. This is the durable
> half of the retrospective: memory reminds; hooks and permissions *enforce*.

### Summary table

| Change | Rationale (class) | Who applies |
|---|---|---|
| **CLAUDE.md:** "Prove every gate goes red before you trust it green — push a deliberate failure, watch the required check fail, then fix. An unwired or unfailing gate is worse than none." | A — controls that cannot fail get quoted instead of run | Michael (edit `CLAUDE.md`) |
| **CLAUDE.md:** "Verify the artifact, not the command. `pushed`→`git ls-remote` shows the SHA; `reviewer requested`→the reviewer is listed on the PR; `green`→the *required* contexts are present, not merely un-red." | F — exit status ≠ effect | Michael |
| **CLAUDE.md:** "A control that has never failed is a suspect, not a success. If you cannot make it go red, it cannot go green." | A | Michael |
| **CLAUDE.md tooling-trust list:** `grep`/`rg`/`find` are shimmed and silently return empty → use the node walker (sanity-checked vs a known positive) or Read; when grep and node/Read disagree, node/Read wins. | G | Michael |
| **CLAUDE.md tooling-trust list:** `gh pr list` / `gh api …/comments` truncate and under-report (~3% recall seen) → page explicitly and cross-check counts before concluding "no new comments". | G | Michael |
| **CLAUDE.md tooling-trust list:** pipelines hide failures — `RC=$?` captures the *last* command (`tail`, not `npm`). Use `set -o pipefail` or check `PIPESTATUS`. | G | Michael |
| **CLAUDE.md tooling-trust list:** read `origin/main`, not a worktree — stale worktrees give false-clean. `git fetch` then compare against `origin/<base>`. | E, G | Michael |
| **Hook (PreToolUse/Bash):** block `git commit` when free disk `< 1 GiB` — an `ENOSPC` mid-commit hard-blocks all lanes. | B, D | Michael (merge into `settings.json`) |
| **Hook (PreToolUse/Bash):** before a test-runner command, run `check_test_hermeticity.py`; block if it finds a real-`$HOME` write sink. | B | Michael |
| **Hook (Stop / PostToolUse):** run `detect_unpushed_single_copy.py` and surface single-copy work at session end and after commits. | D | Michael |
| **Permissions:** allowlist read-only recovery diagnostics (`df`, `du`, `git status/log/ls-remote/stash list`, `kubectl get/describe`, `gh pr view`). | B, D, E | Michael (`settings.json` permissions) |
| **Permissions:** allowlist the bounded recovery ops that were classifier-blocked mid-incident (`kubectl patch pvc …`, ownership-restore `chown` on operator paths) so recovery is not blocked when it is most needed. | B, E | Michael (review threat model, then allow) |

### CLAUDE.md — exact lines to add

```md
## Verification discipline (earned, 2026-07)
- Prove every gate goes RED before you trust it green: push a deliberate failure,
  watch the required check fail, then fix. An unwired/unfailing gate is worse than
  none — it gets quoted instead of run.
- A control that has never failed is a SUSPECT, not a success.
- Verify the artifact, not the command: `pushed`→`git ls-remote` shows the SHA;
  `Copilot triggered`→the reviewer is registered on the PR; `green`→the *required*
  contexts are present, not merely absent.
## Tooling trust (instruments that lie silently here)
- grep/rg/find are shimmed and return EMPTY silently → use the node walker
  (sanity-checked against a known positive) or Read; node/Read wins ties.
- gh pr list / gh api …/comments truncate (~3% recall seen) → page + cross-check.
- Pipelines: RC=$? catches the LAST command (tail, not npm) → set -o pipefail.
- Read origin/main, not a worktree (stale worktrees read false-clean).
```

### Hooks — concrete `settings.json` blocks (merge, don't overwrite)

`grep` is avoided inside the hooks themselves (it is shimmed) — matching is done
with shell `case`. A PreToolUse hook that exits non-zero **blocks** the tool call.

```jsonc
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "comment": "Class B/D: refuse git commit under low disk (ENOSPC hard-blocks all lanes).",
            "command": "cmd=$(jq -r '.tool_input.command // \"\"'); case \"$cmd\" in *'git commit'*) avail=$(df -Pk . | awk 'NR==2{print $4}'); if [ \"${avail:-0}\" -lt 1048576 ]; then echo 'BLOCK: <1GiB free — a commit can die on ENOSPC and hard-block every lane (retro class B). Free space first.' >&2; exit 2; fi;; esac"
          },
          {
            "type": "command",
            "comment": "Class B: block a test run if the repo has a real-$HOME write sink.",
            "command": "cmd=$(jq -r '.tool_input.command // \"\"'); case \"$cmd\" in *pytest*|*'python -m pytest'*|*'npm test'*) python3 tools/check_test_hermeticity.py >/tmp/herm.$$ 2>&1 || { echo 'BLOCK: non-hermetic write under real $HOME (retro class B) — see:' >&2; cat /tmp/herm.$$ >&2; exit 2; };; esac"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "comment": "Class D: surface single-copy work at session end.",
            "command": "python3 tools/detect_unpushed_single_copy.py --roots \"$HOME/dev\" || true"
          }
        ]
      }
    ]
  }
}
```

Notes for the operator: PreToolUse `exit 2` blocks the call and shows stderr; the
hermeticity hook assumes the tool is run from a repo that vendors
`tools/check_test_hermeticity.py` (or point it at an absolute path). The `Stop`
hook is advisory (`|| true`) so it informs without blocking session close.

---

## The feedback loop — failures become recurring detectors

The point of this cycle, in Michael's framing: *"make sure the lessons reoptimize
our configurations and learning/feedback loops."* A taxonomy that sits in a
document is a one-time list. The mechanism below makes cycle N's failures
**auto-arm** cycle N+1's guards. It reuses the estate's existing machinery — the
Self-Improving Loop (`project_self_improving_loop`) and the Learning Apparatus
(`project_learning_apparatus`) — rather than inventing a parallel one.

### The register as a living detector set

The **Control Teeth Register** (Wave 2) is not a checklist; it is a table of
**detectors**, each seeded from one of the seven classes and each carrying a
lifecycle state:

```
SEED      — a class from this taxonomy, with an example incident, no detector yet.
SUSPECT   — a detector exists but has never been proven to fire (no red_proof).
PROVEN    — a committed mutation makes it go red, and a normal case keeps it green.
DECAYING  — a PROVEN detector whose red_proof has not been re-exercised this period.
```

Only **PROVEN** counts as coverage. A `SUSPECT` detector is treated exactly like
the Class-A controls that started this document: present, green, and worthless.

### Seeding from this cycle

Each class becomes one or more seed detectors:

| Class | Seed detector | Initial state |
|---|---|---|
| A | "every registered control has a red_proof exercised this period" | SUSPECT → the register bootstraps itself |
| B | `check_test_hermeticity.py` (real-`$HOME` write sinks) | **PROVEN** (shipped this wave) |
| C | `check_workflow_timeout_bounds.py` (unbounded jobs) | **PROVEN** (shipped this wave) |
| C | absent-verdict detector (required check silent N commits = red) | SEED |
| D | `detect_unpushed_single_copy.py` (single-copy work) | **PROVEN** (shipped this wave) |
| E | recovery-step re-entrancy test (kill mid-run, re-run, assert no double-apply) | SEED |
| F | "Workroom claim without `evidence_refs` is rejected" | SEED |
| G | tooling-trust register + "load-bearing scan proven on a known positive" | SUSPECT |

### Append-on-incident

Every new incident closes its own loop:

1. **Classify** the incident into A–G (extend the taxonomy if it fits none — that
   is itself signal).
2. **Append** a detector to the register, seeded from that class, in state
   `SUSPECT`.
3. **Prove it** — add the red_proof (a mutation test, in the shape of the
   `selftest_*` scripts shipped this wave) and promote to `PROVEN`, or the detector
   does not count.
4. The Learning Apparatus records the incident→detector edge; the Self-Improving
   Loop schedules the detector's red_proof into the cadence below.

The timeout auditor is the worked example: it exists *because* an unbounded job
burned the Actions budget this cycle (Class C). The incident seeded the detector;
the detector shipped with a red_proof; the class is now armed for every future
cycle. Cycle N's failure armed cycle N+1's guard — that is the whole loop.

### Cadence

- **Per PR:** PROVEN detectors relevant to the changed paths run as gates.
- **Weekly:** a scheduled **mutation sweep** re-exercises every detector's
  red_proof. Any detector that no longer goes red on its mutation drops to
  `DECAYING` and pages. This is the upgrade path SUSPECT→PROVEN and the decay path
  PROVEN→DECAYING; it is what keeps the register from rotting into Class A.
- **Per cycle (retrospective):** new incidents append seeds; this document's
  taxonomy is the seed corpus, versioned alongside the register.

---

## Guards shipped this wave (Part 2)

All three are **new files** under `tools/`; none edits a contested file. Each ships
with a `selftest_*` that proves it fires **both ways** (red on a planted defect,
green on the clean case) — the Class-A discipline applied to the guards themselves.
Evidence below is **local only** (Actions is spend-capped this cycle; nothing was
run in CI — see wiring note).

### 1. Runaway-job timeout auditor — `tools/check_workflow_timeout_bounds.py` (BUILT)

Fails if any job in `.github/workflows/**` can run unbounded. A job with no
`timeout-minutes` inherits GitHub's 360-minute (6h) default — the exact budget
bomb that burned the Actions allowance (Class C). Parses real YAML (PyYAML, already
a `tools/` dependency), not line-1 regex — the path-filter auditor shipped that
bug (PR #1101). Jobs that call a reusable workflow (`uses:`) may not legally carry
`timeout-minutes`; they are **exempt but surfaced**, never silently assumed. An
empty scan or a parse error is a **failure**, not a pass.

**Prove-it-fires (local):** `selftest_check_workflow_timeout_bounds.py` — **7/7**:
unbounded→RED, bounded→GREEN, `timeout-minutes: 0`→RED, reusable-call→GREEN+listed,
broken YAML→RED (fail-closed), empty dir→RED (no green from nothing), mixed→RED and
names the offender.

**Measured on `origin/main` today (`873433c5`):**

```
scanned_workflows=105  total_jobs=123  bounded_jobs=0
UNBOUNDED_JOBS=122  reusable_exempt=1  parse_errors=0
```

**122 of 123 jobs are unbounded** — every non-exempt job is a 6h budget bomb. This
is the count the class-C policy must drive to zero.

### 2. Unpushed-work / single-copy detector — `tools/detect_unpushed_single_copy.py` (BUILT)

A **local operator tool** (not CI). Across the dev roots it reports git work that
exists on no remote: repos with no remote at all, unpushed commits (`rev-list
--branches --tags --not --remotes`), stashes, and dirty worktrees — including
linked worktrees parked outside the roots (e.g. in `/tmp`). Honest about its
instrument: "on no remote" is judged against remote-tracking refs, which can be
stale; `--fetch` refreshes first, and without it results over-approximate (never
under-report genuinely-local work).

**Prove-it-fires (local):** `selftest_detect_unpushed_single_copy.py` — **4/4**:
a planted local-only commit is flagged and **clears the instant it is pushed**
(full lifecycle); stashes flagged; no-remote repo flagged; a clean pushed clone
reads **zero** (the negative control).

### 3. Test-hermeticity gate — `tools/check_test_hermeticity.py` (BUILT; one part scoped)

Generalises Noetica #585. Fails if importable code writes under the real `$HOME`
without an environment redirect. AST-based (not regex — Class G): it flags
`open(…, 'w')`, `write_text`/`write_bytes`/`touch`, `mkdir`/`os.makedirs`,
`Path.open('w')`, `sqlite3.connect`, and `shutil` destinations whose path derives
from `Path.home()` / `expanduser('~…')` / `os.environ['HOME']` / a `~/` literal —
**unless** the path flows through `os.environ.get(KEY, …)` (KEY≠HOME), the
redirectable idiom already used across the estate that makes a hermetic test point
it at tmp.

**Estate-generic vs per-repo (the task's question):** the **mechanism** is fully
estate-generic — this file carries no Noetica-specific rule and ran clean over
prophet-platform's 416 `tools/` modules. The **policy** — *which* `$HOME`
subdirectories count as sacred operator state — is per-repo; v0.1 takes the strict
default (any non-redirectable real-`$HOME` write is a violation) with an
`--allow-subpath` escape hatch. **Scoped, not built:** true *test-reachability*
(proving a specific test imports the offending module via import-graph tracing) is
a later wave; this guard is a static over-approximation and says so.

**Prove-it-fires (local):** `selftest_check_test_hermeticity.py` — **6/6**: five
distinct raw-`$HOME` write patterns all flagged (RED); env-redirectable, tmp, and
read-under-`$HOME` forms all clean (GREEN), each as an individual negative control.
(The negative controls caught a real bug during development: `os.makedirs(path)`
takes its path as an argument while `Path.mkdir()` takes it as a receiver — the
first version conflated them and missed `os.makedirs`. Fixed; both now covered.)

### Self-tests

Named `selftest_*` (not `test_*`) so no `pytest` run auto-collects them; each is
directly runnable and exits non-zero on failure:

```
python3 tools/selftest_check_workflow_timeout_bounds.py
python3 tools/selftest_detect_unpushed_single_copy.py
python3 tools/selftest_check_test_hermeticity.py
```

### Wiring (recommended, not done)

`tools/` (#1111) and `validate-target-diagnostics.yml` (#1080/#1082) are contested
lanes this cycle, so the auditor ships **standalone** — no existing workflow was
edited, avoiding a collision. Recommended wiring, for the operator to apply when
the lanes settle: add `python tools/check_workflow_timeout_bounds.py` as a step in
an already-required job (it is fast, has no network dependency, and fails closed).
Because the estate runs `strict_required_status_checks_policy: false` with a single
required check (`diagnostics-gate`, held by `validate-target-diagnostics`), wiring
it there makes it enforcing; wiring it into a non-required workflow makes it
advisory only.

---

## Scoped for later waves (designed here, not built)

Per the task, these are real engineering with their own waves — named with proof
obligations, deliberately **not** implemented in this wave:

- **Control Teeth Register (Wave 2 — keystone, Class A).** The living detector set
  above. *Done when* a scheduled mutation makes each registered control go red and
  the register records the transition; SUSPECT controls are quarantined from
  counting as coverage.
- **Billing/quota ingest as a monitored state (Class C).** *Done when* Actions
  budget exhaustion raises a distinct `budget_exhausted` state, visibly different
  from `runner_saturated` and from `check_failed`, so a bill never again reads as
  an outage.
- **Absent-verdict detector (Class C).** *Done when* a required check that reports
  nothing for N commits is surfaced as red, not neutral — a `cancelled`/never-
  reported required check must not render as absence.
- **Ephemeral cloud execution for substrate-mutating suites (Class B).** *Done
  when* the destructive-test class runs with no write authority over the
  operator's real `$HOME`/substrate, proven by running the known-destructive suite
  and observing the operator's `~/.noetica` unchanged.
- **Import-graph test-reachability (Class B, refinement of guard 3).** *Done when*
  the hermeticity gate can attribute a violation to the specific test(s) that
  import the offending module, upgrading the static over-approximation to true
  reachability.
- **Recovery-step re-entrancy harness (Class E).** *Done when* each recovery
  runbook step passes a kill-mid-run-then-rerun test with identical, side-effect-
  free end state.

---

## Cross-reference index

- **Wave-0 DevSecOps design** (this session; live plane `apps/devsecops-intelligence/`,
  Control Teeth Register) — cross-linked by intent; see the provenance note (not yet
  on `origin/main`).
- **Prior committed lineage:** `docs/architecture/devsecops-intelligence-workroom-v0.1.md`,
  `docs/architecture/devsecops-workroom-*-v0.1.md`, `…-v0.1-status.md`; umbrella #519.
- **Receipt spine:** `contracts/EvidenceReceipt.v0.1.json` (a claim needs
  `evidence_refs`; Class F).
- **PRs:** #1045 / #1101 (CI path-filter auditor and its adversarial self-review —
  Class A/C/G), Noetica #585 (test-hermeticity in `lib/` — Class B), #519 (DevSecOps
  Workroom umbrella). `origin/main` at authoring: `873433c5` (#1104).
- **Memory:** `feedback_ask_what_calls_this`, `feedback_self_validating_checker`,
  `feedback_grep_false_negatives_verify_with_node`, `project_stranded_work_register`,
  `project_ci_throughput_path_filters`, `project_rollback_silent_noop`,
  `project_self_improving_loop`, `project_learning_apparatus`,
  `project_declared_unenforced_register`, `project_blueprint_audit_verdict`.
