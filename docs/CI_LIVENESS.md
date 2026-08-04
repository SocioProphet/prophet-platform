# CI liveness — the dead-man's switch

`tools/ci_liveness_sweep.py` · `python3 tools/ci_liveness_sweep.py owner/repo [...] --fail-on-alarm`

## Why this exists

`SourceOS-Linux/goose-notes` CI reported `startup_failure` in **0s** on every branch from
2026-07-01 to 2026-08-04. A single disallowed action in the workflow meant GitHub refused to start
the run at all. `main` did not compile for five weeks, and nothing said so — because:

> **A red build is information. A build that never runs produces the same observable as a passing
> build: no reported failures.**

No alerting rule fires on that. No self-healing loop triggers either — **healing is downstream of
detection, and this class of failure kills detection itself.** You cannot heal what was never
observed to be sick. The estate's own `sociosphere_self_heal` record reads *"self-heal daemon
DEAD"*, which is the proof: nothing heals its own healing loop.

## What it does differently

It does not wait for red. **It requires green, recently.**

    for every repo, for every active workflow — when did it last COMPLETE SUCCESSFULLY?

Staleness is the alarm, so silence becomes a positive signal instead of a null one. Same shape as
the rest of the estate's fail-closed controls — absence of a marker is not permission, an
undecidable invariant is not a pass, unstated authority is not independence — and here, **no news
is not good news.**

| verdict | meaning | alarms |
|---|---|---|
| `OK` | green inside the window | no |
| `STALE` | succeeded once, not inside the window — abandoned or quietly broken | **yes** |
| `SILENT` | running but *not succeeding* inside the window — **the goose-notes signature** | **yes** |
| `DEAD` | never completed successfully, ever | **yes** |
| `UNUSED` | manual-dispatch workflow never invoked — idle by design | no |

`SILENT` is the one that was invisible. Runs *exist*, so the pipeline looks alive; none of them win.
A checker that only asked *"did it run?"* would have said yes every day for five weeks.

`UNUSED` exists for the opposite reason. A first pass flagged three `(dispatch)` signing workflows
as DEAD; they had simply never been invoked. **A checker that cries wolf gets muted, and a muted
control is exactly the dead control this was built to find** — so precision here is load-bearing,
not politeness.

## Dead or dormant — the distinction the verdicts exist for

A winter garden and a dead garden look the same. The hellebore is how you tell: it flowers in the
dead season, when nothing else does, and its bloom is the proof that the ground is still alive.

That is the whole difficulty here. A repo emitting no signal might be **dormant** — nobody has
pushed, the workflow is manual, the project is between phases — or it might be **dead**. Both look
identical from outside, and the estate spent five weeks unable to tell.

So the verdicts do the telling, and getting the line right is the work:

- `UNUSED` — **dormant**. Manual-dispatch, never invoked. Idle by design, and *not* an alarm.
- `DEAD` — **dead**. It runs automatically, or it has run and failed, and it has never once been green.
- `SILENT` — **the deceptive case**: it is running, so it looks alive, and it never wins.

Calling dormant things dead is how a checker gets muted; calling dead things dormant is how five
weeks pass. The `UNUSED` verdict exists because the first draft of this tool made the first mistake.

## Relationship to `controls_census.py`

The census already names the property: *meta-monitored — something alerts if the control itself
stops (the check checks the checker)*. It applies that to in-cluster CronJobs and to the `tools/`
validators wired into `make validate`. **This is the same doctrine pointed at the CI workflows
themselves**, which the census does not reach and which is where the estate actually lost time.

## The limit, stated plainly

**This sweep cannot watch itself.** Whatever schedules it must be watched by something else, and
the recursion has to bottom out in something trusted *by construction* rather than by monitoring —
a schedule on separate infrastructure, or a human-visible surface. Otherwise this is just one more
daemon that can die quietly, which is the disease and not the cure.
