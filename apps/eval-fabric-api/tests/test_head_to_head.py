from __future__ import annotations

import app.runner.head_to_head as h2h


def test_extract_code_from_fence():
    assert h2h.extract_code("blah\n```python\ndef f():\n    return 1\n```\nend") == "def f():\n    return 1"


def test_extract_code_falls_back_to_raw_def():
    assert h2h.extract_code("def g():\n    return 2").startswith("def g")
    assert h2h.extract_code("just prose, no code") is None


def test_run_hidden_passes_correct_and_fails_wrong():
    p = next(x for x in h2h.PROBLEMS if x.name == "fib") if any(x.name == "fib" for x in h2h.PROBLEMS) else None
    # 'fib' isn't in the bank; use two_sum which is.
    two_sum = next(x for x in h2h.PROBLEMS if x.name == "two_sum")
    good = "def two_sum(nums, target):\n    seen={}\n    for i,n in enumerate(nums):\n        if target-n in seen:\n            return [seen[target-n], i]\n        seen[n]=i"
    bad = "def two_sum(nums, target):\n    return [0, 0]"
    assert h2h.run_hidden(good, two_sum.test) is True
    assert h2h.run_hidden(bad, two_sum.test) is False
    assert h2h.run_hidden("", two_sum.test) is False


def test_build_arms_default_is_sovereign_only(monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "MESH_URL", "MESH_MODEL"):
        monkeypatch.delenv(k, raising=False)
    arms = h2h.build_arms()
    ids = [a.arm_id for a in arms]
    assert ids == ["mesh", "mesh+vr"]
    assert all(a.sovereign for a in arms)
    assert any(a.verify for a in arms)


def test_build_arms_adds_frontier_when_keyed(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    arms = h2h.build_arms()
    ids = {a.arm_id for a in arms}
    assert {"claude", "gpt"} <= ids
    assert any((not a.sovereign) and a.provider_id == "anthropic" for a in arms)
    assert any((not a.sovereign) and a.provider_id == "openai" for a in arms)


def test_persist_writes_reproduced_snapshot_parameterized(monkeypatch):
    captured: list[tuple[str, tuple]] = []
    monkeypatch.setattr(h2h, "pg_execute", lambda stmts: captured.extend(stmts))

    arm = h2h.Arm("mesh", "our mesh — qwen2.5-coder-7b-instruct", "our_platform",
                  "qwen2.5-coder-7b-instruct", sovereign=True, verify=False, gen=lambda p, t: "")
    problems = h2h.PROBLEMS[:2]
    result = h2h.ArmResult(arm, passed=2, total=2, avg_ms=900, errors=0, outcomes=[True, True])
    run_id = h2h.persist(result, problems)

    assert run_id.startswith("run_h2h_mesh_")
    sqls = " ".join(s for s, _ in captured)
    assert "insert into eval_runs" in sqls
    assert "insert into trials" in sqls
    snapshot = [(s, params) for s, params in captured if "competitor_snapshots" in s]
    assert len(snapshot) == 1
    snap_sql, snap_params = snapshot[0]
    # reproduced_by_us is hardcoded true (we ran it); values are %s-parameterized, never interpolated.
    assert "reproduced_by_us" in snap_sql and "true" in snap_sql
    assert "src_internal_eval_runner" in snap_sql
    assert "%s" in snap_sql
    assert arm.model_release_id in snap_params
    # payload is JSON-encoded and carries the pass@1 the API will surface.
    payload = next(p for p in snap_params if isinstance(p, str) and p.startswith("{"))
    assert '"pass_at_1_pct": 100' in payload
