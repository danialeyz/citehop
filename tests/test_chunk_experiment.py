"""S03 comparison, decision rule and freeze/test ordering with fake runs (no DB or model)."""

import json

import pytest
from test_evaluate import QUESTIONS, fake_search

from citehop import chunk_experiment as cx
from citehop import evaluate as ev


def summary(arm, vector, keyword):
    return {"arm": arm, "recall_at_5": {"vector": {"recall_at_5": vector},
                                        "keyword": {"recall_at_5": keyword}}}


@pytest.mark.parametrize(("base", "candidate", "chosen"), [
    ((1.0, 0.5), (1.0, 1.0), cx.BASELINE),   # vector tie: keyword gain alone never switches
    ((0.9, 0.5), (0.8, 1.0), cx.BASELINE),   # worse primary metric
    ((0.9, 0.5), (1.0, 0.5), cx.CANDIDATE),  # strictly better vector, keyword not lower
])
def test_decision_rule(base, candidate, chosen):
    assert cx.decide(summary(cx.BASELINE, *base), summary(cx.CANDIDATE, *candidate))[0] == chosen


def test_lower_keyword_blocks_a_vector_gain():
    chosen, reason = cx.decide(summary(cx.BASELINE, 0.9, 0.8), summary(cx.CANDIDATE, 1.0, 0.7))
    assert chosen == cx.BASELINE and "keyword" in reason


def test_missing_recall_is_an_error_not_a_tie():
    with pytest.raises(ValueError):
        cx.decide(summary(cx.BASELINE, None, 1.0), summary(cx.CANDIDATE, 1.0, 1.0))


def test_pooled_latency_spans_runs_and_filter_groups():
    rows = [{"embedding_ms": e, "filtered": f, "methods": {"vector": {"retrieval_ms": r}}}
            for e, f, r in ((1, False, 10), (3, True, 30))]
    pooled = cx.pooled_latency([rows[:1], rows[1:]])
    assert pooled["embedding_ms"]["n"] == 2 and pooled["embedding_ms"]["median"] == 2
    assert pooled["retrieval_ms_vector_filtered"]["median"] == 30
    assert pooled["retrieval_ms_vector_unfiltered"]["n"] == 1


def manifest(run_id, split, content="c", labels="l"):
    return {"run_id": run_id, "splits": {split: 1}, "corpus": {"content_sha256": content},
            "question_set": {"labels_sha256": labels, "label_review": {"unreviewed": 3}},
            "config": {"embedding_model": "m", "embedding_model_revision": "r",
                       "embedding_config": "e"},
            "chunk_configs": [{"chunks": 7}], "final_claims_allowed": False,
            "hardware": {}, "warm_up": "w", "latency": {"boundaries": {}}}


def write_run(root, arm, run_id, split, **kw):
    """A dev/test run directory produced by the real evaluator over fake search."""
    records, _ = ev.evaluate(QUESTIONS, search_fn=fake_search([]), embed_fn=lambda q: [0.0],
                             splits=(split,), repeats=1, warm_up=False)
    path = root / arm / "runs" / run_id
    path.mkdir(parents=True)
    data = manifest(run_id, split, **kw) | {"summary": ev.summarize(records, [])}
    (path / "manifest.json").write_text(json.dumps(data))
    (path / "retrieval.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    return path


def test_freeze_then_single_followup_test(tmp_path, monkeypatch):
    for arm in cx.ARMS:
        write_run(tmp_path, arm, f"{arm}-dev1", "dev")
        write_run(tmp_path, arm, f"{arm}-dev2", "dev")
    assert cx.test(tmp_path) == 1  # nothing frozen yet

    assert cx.freeze(tmp_path) == 0
    decision = json.loads((tmp_path / "decision.json").read_text())
    comparison = json.loads((tmp_path / "comparison.json").read_text())
    assert decision["chosen"] == cx.BASELINE  # identical fake arms tie
    assert decision["rule"] == cx.RULE and decision["test_runs_at_freeze"] == 0
    assert decision["evidence"]["comparison.json"] == cx.sha256(tmp_path / "comparison.json")
    base = comparison["arms"][cx.BASELINE]
    assert base["chunks"] == 7 and base["recall_identical_across_runs"] is True
    assert base["latency"]["embedding_ms"]["n"] == 2 * 3  # 3 dev questions, 2 runs
    assert cx.freeze(tmp_path) == 1  # frozen decisions are never rewritten
    assert cx.dev(1, tmp_path) == 1  # no dev runs after the freeze

    calls = []

    def fake_evaluate_arm(arm, split, label, extra=(), root=None):
        calls.append((arm, split, label, tuple(extra)))
        write_run(root, arm, f"{arm}-test", split)
        return 0

    monkeypatch.setattr(cx, "evaluate_arm", fake_evaluate_arm)
    assert cx.test(tmp_path) == 0
    (arm, split, label, extra), = calls
    assert (arm, split, extra) == (cx.BASELINE, "test", ("--no-answers",))
    assert cx.sha256(tmp_path / "decision.json") in label
    followup = json.loads((tmp_path / "followup.json").read_text())
    assert followup["decision_sha256"] == cx.sha256(tmp_path / "decision.json")
    assert cx.test(tmp_path) == 1  # only one follow-up run


def test_freeze_refuses_after_a_test_run_and_on_mismatched_inputs(tmp_path):
    for arm in cx.ARMS:
        write_run(tmp_path, arm, f"{arm}-dev", "dev")
    write_run(tmp_path, cx.CANDIDATE, "late-test", "test")
    assert cx.freeze(tmp_path) == 1 and not (tmp_path / "decision.json").exists()

    other = tmp_path / "other"
    write_run(other, cx.BASELINE, "a", "dev")
    write_run(other, cx.CANDIDATE, "b", "dev", content="different")
    with pytest.raises(ValueError, match="corpus, questions or model"):
        cx.freeze(other)
    assert not (other / "decision.json").exists()
