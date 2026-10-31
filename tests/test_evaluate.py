"""citehop.evaluate with hand-scored fixtures and fakes; no database, model or network."""

import json

import pytest

from citehop import evaluate as ev
from citehop.rag import Generation


def hits(*article_ids):
    """Chunk hits in rank order; repeated article IDs model several chunks of one article."""
    return [{"chunk_id": f"a{a}-c{i}", "article_id": a, "rank": i, "score": 1 - i / 100,
             "title": f"T{a}", "source_url": f"https://x/{a}", "passage": f"text {a}",
             "method": "vector"} for i, a in enumerate(article_ids, 1)]


# ---------- hand-scored recall ----------


def test_repeated_article_chunks_dedupe_by_best_rank_before_cutoff():
    # chunk ranks: 1 A, 2 A, 3 B, 4 A, 5 C, 6 D, 7 E, 8 F
    ranking = ev.article_ranking(hits(1, 1, 2, 1, 3, 4, 5, 6))
    assert ranking == [{"article_id": 1, "best_chunk_rank": 1},
                       {"article_id": 2, "best_chunk_rank": 3},
                       {"article_id": 3, "best_chunk_rank": 5},
                       {"article_id": 4, "best_chunk_rank": 6},
                       {"article_id": 5, "best_chunk_rank": 7},
                       {"article_id": 6, "best_chunk_rank": 8}]
    assert ev.recall_at_k(ranking, [5]) == 1.0  # 5th distinct article despite chunk rank 7
    assert ev.recall_at_k(ranking, [6]) == 0.0  # 6th distinct article is past the cutoff


def test_best_rank_ignores_input_order():
    shuffled = list(reversed(hits(1, 2, 1)))
    assert ev.article_ranking(shuffled)[0] == {"article_id": 1, "best_chunk_rank": 1}


def test_multiple_relevant_articles_give_partial_recall():
    ranking = ev.article_ranking(hits(10, 11, 10, 12, 13, 14, 15))
    assert ev.recall_at_k(ranking, [11, 14, 15]) == pytest.approx(2 / 3)
    assert ev.recall_at_k(ranking, [10, 11]) == 1.0


def test_zero_hits_score_zero_and_unanswerable_is_none():
    assert ev.recall_at_k(ev.article_ranking([]), [7]) == 0.0
    assert ev.recall_at_k(ev.article_ranking(hits(7)), []) is None


def test_short_list_scores_what_exists():
    ranking = ev.article_ranking(hits(1, 2, 2, 3))
    assert len(ranking) == 3
    assert ev.recall_at_k(ranking, [3, 9]) == 0.5


# ---------- candidate depth ----------


def fake_depth_search(article_ids):
    calls = []

    def run(depth):
        calls.append(depth)
        return hits(*article_ids)[:depth]
    return run, calls


def test_deepens_until_five_distinct_articles():
    run, calls = fake_depth_search([1] * 60 + [2, 3, 4, 5] + [6] * 50)
    _, ranking, info = ev.retrieve_articles(run, depths=(50, 100))
    assert calls == [50, 100] and len(ranking) == 6 and info["cutoff_reached"]
    assert not info["exhausted"] and len(info["attempts"]) == 2


def test_stops_when_eligible_rows_are_exhausted():
    run, calls = fake_depth_search([1, 1, 2, 3])
    _, ranking, info = ev.retrieve_articles(run, depths=(50, 100))
    assert calls == [50] and info["exhausted"] and not info["cutoff_reached"]
    assert info["articles_found"] == 3


def test_reports_unresolved_cutoff_at_max_depth():
    run, calls = fake_depth_search([1] * 200)
    _, _, info = ev.retrieve_articles(run, depths=(50, 100))
    assert calls == [50, 100] and not info["exhausted"] and not info["cutoff_reached"]


# ---------- statistics ----------


def test_latency_median_p95_and_null_when_empty():
    assert ev.latency([]) == {"n": 0, "unit": "ms", "median": None, "p95": None}
    stats = ev.latency(list(range(1, 21)) + [None])
    assert stats["n"] == 20 and stats["median"] == 10.5 and stats["p95"] == 19


# ---------- end-to-end with fakes ----------


QUESTIONS = [
    {"id": "dev-01", "split": "dev", "question": "q1", "answerable": True, "filters": {},
     "relevant_article_ids": [2], "expected_answer": "a"},
    {"id": "dev-02", "split": "dev", "question": "q2", "answerable": True,
     "filters": {"category": "C"}, "relevant_article_ids": [9], "expected_answer": "a"},
    {"id": "dev-03", "split": "dev", "question": "q3", "answerable": False, "filters": {},
     "relevant_article_ids": [], "expected_answer": None},
    {"id": "test-01", "split": "test", "question": "q4", "answerable": True, "filters": {},
     "relevant_article_ids": [1, 3], "expected_answer": "a"},
    {"id": "test-02", "split": "test", "question": "zero", "answerable": True, "filters": {},
     "relevant_article_ids": [4], "expected_answer": "a"},
    {"id": "test-03", "split": "test", "question": "q6", "answerable": False, "filters": {},
     "relevant_article_ids": [], "expected_answer": None},
]


class FakeGenerator:
    name = "fake:model"

    def __init__(self):
        self.calls = 0

    def generate(self, system, user, max_tokens):
        self.calls += 1
        return Generation("Answer [S1].", 100, 5, "stop")


def fake_search(calls):
    def search_fn(query, method, filters, k, vector):
        calls.append((query, method, k))
        if query == "zero" and method == "keyword":
            return []
        if filters:
            return hits(9, 9)[:k]  # filter admits one article with two chunks
        ids = [1, 1, 2, 5, 6, 7] if method != "vector" else [1, 2, 2, 5, 6, 7]
        return hits(*ids)[:k]
    return search_fn


def test_evaluate_records_repeats_methods_answers_and_summary(tmp_path):
    calls, embeds, gen = [], [], FakeGenerator()
    records, answers = ev.evaluate(
        QUESTIONS, search_fn=fake_search(calls), embed_fn=lambda q: embeds.append(q) or [1.0],
        generator=gen)
    # warm-up first, untimed; then one embedding per question repetition
    assert embeds[0] == ev.WARMUP_QUERY and len(embeds) == 1 + 3 + 3 + 3 + 1
    assert [c[1] for c in calls[:3]] == ["keyword", "vector", "exact"]
    by_id = {}
    for r in records:
        by_id.setdefault(r["question_id"], []).append(r)
    assert [len(by_id[i]) for i in sorted(by_id)] == [1, 1, 1, 3, 3, 1]
    assert set(by_id["dev-01"][0]["methods"]) == {"keyword", "vector", "exact"}
    assert set(by_id["test-01"][0]["methods"]) == {"keyword", "vector"}
    assert "passage" not in by_id["dev-01"][0]["methods"]["vector"]["hits"][0]

    s = ev.summarize(records, answers)
    dev_kw = s["retrieval"]["dev"]["keyword"]
    assert dev_kw["unfiltered"] == {"n": 1, "recall_at_5": 1.0, "zero_hit": 0, "short_list": 0}
    assert dev_kw["filtered"] == {"n": 1, "recall_at_5": 1.0, "zero_hit": 0, "short_list": 1}
    test_kw = s["retrieval"]["test"]["keyword"]["all_answerable"]
    # test-01: articles 1,2,5,6,7 -> recall 1/2; test-02 zero hits -> 0, still counted
    assert test_kw == {"n": 2, "recall_at_5": 0.25, "zero_hit": 1, "short_list": 1}
    assert s["retrieval"]["test"]["vector"]["rankings_identical_across_repeats"]
    assert s["unanswerable"]["test"]["keyword"]["n"] == 1
    ann = s["ann_vs_exact"]["dev"]
    assert ann["n"] == 3 and ann["n_unfiltered"] == 2
    assert ann["mean_chunk_overlap_at_5_unfiltered"] == pytest.approx(0.8)
    assert ann["mean_article_overlap_at_5"] == 1.0
    assert s["ann_vs_exact"]["test"] is None
    assert s["latency"]["test"]["samples"] == {"questions": 3, "records": 7}
    assert s["latency"]["test"]["embedding_ms"]["n"] == 7
    assert s["latency"]["dev"]["retrieval_ms_vector_filtered"]["n"] == 1
    assert s["latency"]["dev"]["retrieval_ms_vector_unfiltered"]["n"] == 2

    # answers: test split only, one generator call each, reviews null
    assert [a["question_id"] for a in answers] == ["test-01", "test-02", "test-03"]
    assert gen.calls == 1 + 3 and all(a["review"]["grounded"] is None for a in answers)
    assert s["generation"]["answers"] == 3 and s["generation"]["generation_ms"]["n"] == 3
    assert s["answer_review"] == {"prepared": 3, "reviewed": 0, "grounded": None,
                                  "denominator": None}
    json.dumps({"records": records, "answers": answers, "summary": s})


def test_no_generator_leaves_generation_null():
    records, answers = ev.evaluate(QUESTIONS, search_fn=fake_search([]), embed_fn=lambda q: [1.0],
                                   splits=("dev",), warm_up=False)
    s = ev.summarize(records, answers)
    assert answers == [] and s["generation"]["statuses"] is None
    assert s["generation"]["generation_ms"]["median"] is None
    assert s["answer_review"]["grounded"] is None


def test_review_selection_is_deterministic_and_stratified():
    questions = [{"id": f"test-{i:02d}", "split": "test", "answerable": i not in (3, 8, 9, 12)}
                 for i in range(1, 15)] + [{"id": "dev-01", "split": "dev", "answerable": True}]
    picked = ev.review_selection(questions, n=10, unanswerable=3)
    ids = [q["id"] for q in picked]
    assert len(ids) == 10 and "dev-01" not in ids and ids == sorted(ids)
    assert sum(not q["answerable"] for q in picked) == 3 and "test-12" not in ids
