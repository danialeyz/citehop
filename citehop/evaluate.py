"""Retrieval and answer-grounding evaluation over the frozen question set (C08).

    python -m citehop.evaluate [--splits dev test] [--repeats 3] [--answers 10] [--no-answers]
                               [--hybrid] [--out results/runs]

Writes results/runs/<run_id>/ with raw per-question retrieval records (retrieval.jsonl), the
answers prepared for human review (answers.json), and a versioned manifest (manifest.json)
with IDs, configuration, denominators, latency boundaries, hardware and review state.

Recall is article-level: chunk hits are deduplicated by each article's best chunk rank, and
Recall@5 counts relevant articles among the first five distinct articles. The search is
deepened until five distinct articles appear or the eligible rows are exhausted. Answerable
questions with zero hits count as zero; unanswerable questions are reported separately.
Results stay provisional until every question label is approved (eval/README.md).
`--hybrid` adds the S01 RRF method to both splits, timed like the others.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = "citehop-eval-v1"
K = 5
CANDIDATE_DEPTHS = (50, 100)  # chunk depths tried in turn; 100 is search.MAX_K
# hybrid fuses fixed top-50 inputs, so 50 fused rows is its whole list (search.RRF_DEPTH);
# fewer means both inputs returned every eligible row
METHOD_DEPTHS = {"hybrid": (50,)}
TEST_REPEATS = 3
REVIEW_ANSWERS = 10
REVIEW_UNANSWERABLE = 3
WARMUP_QUERY = "untimed warm-up query about machine learning"
WARM_UP_POLICY = ("one untimed embedding, one untimed search per method and (with answers) one "
                  "untimed generator call before any timed call; all calls run in one process "
                  "over one open MariaDB connection")
BOUNDARIES = {
    "embedding_ms": "embed_query(question): BGE query instruction, tokenize, CPU forward pass",
    "retrieval_ms": "search() with a precomputed query vector: SQL round trip on an open "
                    "connection including Python client; summed over candidate-depth attempts; "
                    "hybrid includes both of its SQL queries and the fusion",
    "generation_ms": "rag.answer(): one non-streaming Ollama /api/chat call",
}


# ---------- metrics (pure; hand-scored in tests/test_evaluate.py) ----------


def article_ranking(hits):
    """Distinct articles ordered by their best (lowest) chunk rank."""
    best = {}
    for hit in sorted(hits, key=lambda h: h["rank"]):
        best.setdefault(hit["article_id"], hit["rank"])
    return [{"article_id": a, "best_chunk_rank": r} for a, r in best.items()]


def recall_at_k(ranking, relevant, k=K):
    """Share of relevant articles among the first k distinct articles; None if none relevant."""
    relevant = set(relevant)
    if not relevant:
        return None
    return len(relevant & {r["article_id"] for r in ranking[:k]}) / len(relevant)


def retrieve_articles(run_search, k=K, depths=CANDIDATE_DEPTHS):
    """Deepen run_search(depth) until k distinct articles appear or fewer rows than requested
    come back (every eligible row was returned). Returns hits, ranking and attempt metadata."""
    attempts = []
    for depth in depths:
        started = time.perf_counter()
        hits = run_search(depth)
        attempts.append({"candidate_k": depth, "rows": len(hits),
                         "ms": round((time.perf_counter() - started) * 1000, 3)})
        ranking = article_ranking(hits)
        exhausted = len(hits) < depth
        if len(ranking) >= k or exhausted:
            break
    return hits, ranking, {"attempts": attempts, "exhausted": exhausted,
                           "articles_found": len(ranking), "cutoff_reached": len(ranking) >= k,
                           "retrieval_ms": round(sum(a["ms"] for a in attempts), 3)}


def percentile(values, q):
    """Nearest-rank percentile; None for no samples."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q / 100 * len(ordered)) - 1)]


def latency(values):
    values = [v for v in values if v is not None]
    return {"n": len(values), "unit": "ms",
            "median": round(statistics.median(values), 3) if values else None,
            "p95": percentile(values, 95)}


def mean(values):
    return round(statistics.fmean(values), 4) if values else None


# ---------- run ----------


def compact(hit):
    return {"chunk_id": hit["chunk_id"], "article_id": hit["article_id"], "rank": hit["rank"],
            "score": hit["score"]}


def review_selection(questions, n=REVIEW_ANSWERS, unanswerable=REVIEW_UNANSWERABLE):
    """Deterministic answer-review set from the test split: the first `unanswerable` unanswerable
    and the first answerable questions by ID, n in total."""
    test = sorted((q for q in questions if q["split"] == "test"), key=lambda q: q["id"])
    negatives = [q for q in test if not q["answerable"]][:unanswerable]
    positives = [q for q in test if q["answerable"]][:n - len(negatives)]
    return sorted(positives + negatives, key=lambda q: q["id"])


def evaluate(questions, *, search_fn, embed_fn, generator=None, splits=("dev", "test"),
             repeats=TEST_REPEATS, answers=REVIEW_ANSWERS, warm_up=True, log=None,
             extra_methods=()):
    """Raw retrieval records and answers.

    search_fn(query, method, filters, k, query_vector) -> hit dicts with passages;
    embed_fn(query) -> vector. Dev runs keyword, ANN vector and exact once per question; test
    runs keyword and vector, `repeats` times for each answerable question. `extra_methods`
    (e.g. hybrid) run on both splits with the same query vector.
    """
    if warm_up:
        vector = embed_fn(WARMUP_QUERY)
        for method in ("keyword", "vector", "exact", *extra_methods):
            search_fn(WARMUP_QUERY, method, {}, K, vector)
        if generator is not None and answers:
            from citehop.rag import ProviderError

            try:
                generator.generate("Reply OK.", "OK?", 5)
            except ProviderError:
                pass  # each answer then records provider_error; sources stay usable
    records, passages = [], {}
    for q in sorted((q for q in questions if q["split"] in splits), key=lambda q: q["id"]):
        methods = (("keyword", "vector", "exact") if q["split"] == "dev"
                   else ("keyword", "vector")) + tuple(extra_methods)
        reps = repeats if q["split"] == "test" and q["answerable"] else 1
        for rep in range(1, reps + 1):
            started = time.perf_counter()
            vector = embed_fn(q["question"])
            record = {"question_id": q["id"], "split": q["split"], "repetition": rep,
                      "answerable": q["answerable"], "filters": q["filters"],
                      "filtered": bool(q["filters"]),
                      "relevant_article_ids": q["relevant_article_ids"],
                      "embedding_ms": round((time.perf_counter() - started) * 1000, 3),
                      "methods": {}}
            for method in methods:
                hits, ranking, info = retrieve_articles(
                    lambda depth, q=q, m=method, v=vector: search_fn(q["question"], m,
                                                                     q["filters"], depth, v),
                    depths=METHOD_DEPTHS.get(method, CANDIDATE_DEPTHS))
                record["methods"][method] = {
                    **info, "recall_at_5": recall_at_k(ranking, q["relevant_article_ids"]),
                    "article_ranking": ranking, "hits": [compact(h) for h in hits]}
                if rep == 1 and method == "vector":
                    passages[q["id"]] = hits[:K]
            records.append(record)
            if log:
                log(f"{q['id']} rep {rep}: " + ", ".join(
                    f"{m} R@5={v['recall_at_5']}" for m, v in record["methods"].items()))
    prepared = []
    if generator is not None and answers:
        from citehop import rag

        for q in review_selection([q for q in questions if q["id"] in passages], answers):
            result = rag.answer(q["question"], passages[q["id"]], generator)
            prepared.append({
                "question_id": q["id"], "split": q["split"], "question": q["question"],
                "answerable": q["answerable"], "filters": q["filters"],
                "expected_answer": q["expected_answer"],
                "relevant_article_ids": q["relevant_article_ids"],
                "retrieval": {"method": "vector", "k": K, "repetition": 1},
                **result.to_dict(),
                "review": {"status": "unreviewed", "grounded": None, "citations_support": None,
                           "correct_abstention": None, "reviewer": None, "reviewed_at": None,
                           "notes": ""}})
            if log:
                log(f"answer {q['id']}: {result.status} {result.generation_ms} ms")
    return records, prepared


# ---------- summary ----------


def recall_group(rows, method):
    values = [r["methods"][method]["recall_at_5"] for r in rows]
    return {"n": len(values), "recall_at_5": mean(values),
            "zero_hit": sum(not r["methods"][method]["hits"] for r in rows),
            "short_list": sum(not r["methods"][method]["cutoff_reached"] for r in rows)}


def first_chunks(entry, k=K):
    return {h["chunk_id"] for h in entry["hits"][:k]}


def first_articles(entry, k=K):
    return {a["article_id"] for a in entry["article_ranking"][:k]}


def overlap(approx, truth):
    return len(approx & truth) / len(truth) if truth else None


def ann_vs_exact(rows):
    cases = []
    for r in rows:
        ann, exact = r["methods"].get("vector"), r["methods"].get("exact")
        if ann is None or exact is None:
            continue
        cases.append({"question_id": r["question_id"], "filtered": r["filtered"],
                      "chunk_overlap_at_5": overlap(first_chunks(ann), first_chunks(exact)),
                      "article_overlap_at_5": overlap(first_articles(ann),
                                                      first_articles(exact)),
                      "recall_vector": ann["recall_at_5"], "recall_exact": exact["recall_at_5"],
                      "retrieval_ms_vector": ann["retrieval_ms"],
                      "retrieval_ms_exact": exact["retrieval_ms"]})
    if not cases:
        return None

    def mean_of(key, subset):
        return mean([c[key] for c in subset if c[key] is not None])

    unfiltered = [c for c in cases if not c["filtered"]]
    return {"n": len(cases), "n_unfiltered": len(unfiltered),
            "note": "filtered vector search skips the HNSW index, so filtered cases compare an "
                    "exact computation with itself; the unfiltered means are the ANN comparison",
            "mean_chunk_overlap_at_5": mean_of("chunk_overlap_at_5", cases),
            "mean_chunk_overlap_at_5_unfiltered": mean_of("chunk_overlap_at_5", unfiltered),
            "min_chunk_overlap_at_5_unfiltered": min(
                (c["chunk_overlap_at_5"] for c in unfiltered
                 if c["chunk_overlap_at_5"] is not None), default=None),
            "mean_article_overlap_at_5": mean_of("article_overlap_at_5", cases),
            "cases": cases}


def summarize(records, answers):
    summary = {"retrieval": {}, "unanswerable": {}, "ann_vs_exact": {}, "latency": {}}
    for split in sorted({r["split"] for r in records}):
        rows = [r for r in records if r["split"] == split]
        first = [r for r in rows if r["repetition"] == 1]
        methods = list(first[0]["methods"])
        positive = [r for r in first if r["answerable"]]
        negative = [r for r in first if not r["answerable"]]
        summary["retrieval"][split] = {m: {
            "all_answerable": recall_group(positive, m),
            "unfiltered": recall_group([r for r in positive if not r["filtered"]], m),
            "filtered": recall_group([r for r in positive if r["filtered"]], m),
            "rankings_identical_across_repeats": all(
                r["methods"][m]["article_ranking"] == f["methods"][m]["article_ranking"]
                for f in first for r in rows if r["question_id"] == f["question_id"]),
        } for m in methods}
        summary["unanswerable"][split] = {m: {
            "n": len(negative), "filtered": sum(r["filtered"] for r in negative),
            "zero_hit": sum(not r["methods"][m]["hits"] for r in negative),
            "note": "no relevant labels; excluded from recall",
        } for m in methods}
        summary["ann_vs_exact"][split] = ann_vs_exact(first)
        summary["latency"][split] = {
            "samples": {"questions": len(first), "records": len(rows)},
            "embedding_ms": latency([r["embedding_ms"] for r in rows]),
            **{f"retrieval_ms_{m}{suffix}": latency([r["methods"][m]["retrieval_ms"]
                                                     for r in subset])
               for m in methods
               for suffix, subset in (("", rows),
                                      ("_unfiltered", [r for r in rows if not r["filtered"]]),
                                      ("_filtered", [r for r in rows if r["filtered"]]))}}
    statuses = Counter(a["status"] for a in answers)
    reviewed = [a for a in answers if a["review"]["status"] != "unreviewed"]
    summary["generation"] = {
        "answers": len(answers), "statuses": dict(statuses) if answers else None,
        "answerable": sum(a["answerable"] for a in answers),
        "unanswerable": sum(not a["answerable"] for a in answers),
        "unanswerable_abstained": (sum(a["status"] == "insufficient_evidence"
                                       for a in answers if not a["answerable"])
                                   if answers else None),
        "generation_ms": latency([a["generation_ms"] for a in answers]),
        "prompt_tokens": latency([a["usage"].get("prompt_tokens") for a in answers]) | {
            "unit": "tokens"},
    }
    summary["answer_review"] = {
        "prepared": len(answers), "reviewed": len(reviewed),
        "grounded": (sum(bool(a["review"]["grounded"]) for a in reviewed)
                     if reviewed else None),
        "denominator": len(reviewed) if reviewed else None,
    }
    return summary


# ---------- CLI ----------


def git_state():
    def run(*args):
        out = subprocess.run(["git", *args], capture_output=True, text=True)
        return out.stdout.strip() if out.returncode == 0 else None

    commit = run("rev-parse", "HEAD")
    status = run("status", "--porcelain")
    return {"commit": commit, "dirty": bool(status) if status is not None else None}


def hardware():
    chip = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True,
                          text=True).stdout.strip()
    memory = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True,
                            text=True).stdout.strip()
    return {"platform": platform.platform(), "machine": platform.machine(),
            "cpu": chip or None, "memory_bytes": int(memory) if memory.isdigit() else None,
            "database": "MariaDB in local Docker on the same machine"}


def database_state(conn):
    cur = conn.cursor()
    cur.execute("SELECT version_id, content_sha256, source_corpus_id, subset, article_count "
                "FROM corpus_versions ORDER BY version_id DESC LIMIT 1")
    version = cur.fetchone()
    cur.execute("SELECT embedding_config, chunk_config, COUNT(*) FROM chunks "
                "GROUP BY embedding_config, chunk_config")
    configs = cur.fetchall()
    cur.execute("SELECT VERSION(), @@mhnsw_ef_search, @@mhnsw_default_m")
    server, ef_search, m = cur.fetchone()
    return {
        "corpus": None if version is None else {
            "version_id": version[0], "id": f"corpus:{version[0]}",
            "content_sha256": version[1], "source_corpus_id": version[2],
            "subset": version[3], "articles": version[4]},
        "chunk_configs": [{"embedding_config": e, "chunk_config": c, "chunks": n}
                          for e, c, n in configs],
        "mariadb": {"version": server, "mhnsw_ef_search": ef_search, "mhnsw_default_m": m},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m citehop.evaluate")
    parser.add_argument("--questions", type=Path, default=Path("eval/questions.json"))
    parser.add_argument("--splits", nargs="+", choices=("dev", "test"), default=["dev", "test"])
    parser.add_argument("--repeats", type=int, default=TEST_REPEATS)
    parser.add_argument("--answers", type=int, default=REVIEW_ANSWERS)
    parser.add_argument("--no-answers", action="store_true", help="skip generation")
    parser.add_argument("--hybrid", action="store_true",
                        help="also run S01 reciprocal rank fusion (keyword + vector)")
    parser.add_argument("--out", type=Path, default=Path("results/runs"))
    args = parser.parse_args(argv)

    from citehop import rag
    from citehop.db import connect
    from citehop.search import RRF_DEPTH, RRF_INPUTS, RRF_K, default_embedder, search

    document = json.loads(args.questions.read_text())
    questions = document["questions"]
    label_review = Counter(q["review"]["status"] for q in questions)
    final = all(q["review"]["status"] == "approved" for q in questions)
    embed_query, embedding_config = default_embedder()
    generator = None if args.no_answers or "test" not in args.splits else rag.OllamaGenerator()
    created = datetime.now(UTC)

    def log(message):
        print(message, file=sys.stderr)

    with connect() as conn:
        state = database_state(conn)
        if state["corpus"] is None or not state["chunk_configs"]:
            log("no loaded/embedded corpus; run C03/C05 first")
            return 1
        if state["corpus"]["source_corpus_id"] != document["corpus_id"]:
            log("questions were written for a different corpus snapshot")
            return 1

        def search_fn(query, method, filters, k, vector):
            hits = search(query, method, filters, k, connection=conn,
                          query_vector=None if method == "keyword" else vector,
                          embedding_config=embedding_config)
            return [asdict(h) for h in hits]

        records, answers = evaluate(questions, search_fn=search_fn, embed_fn=embed_query,
                                    generator=generator, splits=tuple(args.splits),
                                    repeats=args.repeats, answers=args.answers, log=log,
                                    extra_methods=("hybrid",) if args.hybrid else ())

    from citehop.embed import MODEL_ID, MODEL_REVISION

    config = {
        "k": K, "recall": "article-level; chunks deduplicated by best chunk rank before the "
                          "five-article cutoff",
        "candidate_depths": list(CANDIDATE_DEPTHS), "test_repeats": args.repeats,
        "methods": {"dev": ["keyword", "vector", "exact"] + ["hybrid"] * args.hybrid,
                    "test": ["keyword", "vector"] + ["hybrid"] * args.hybrid},
        **({"hybrid": {"fusion": "reciprocal rank fusion", "rrf_k": RRF_K,
                       "depth_per_list": RRF_DEPTH, "inputs": list(RRF_INPUTS),
                       "candidate_depths": list(METHOD_DEPTHS["hybrid"]),
                       "ties": "chunk_id ascending"}} if args.hybrid else {}),
        "embedding_model": MODEL_ID, "embedding_model_revision": MODEL_REVISION,
        "embedding_config": embedding_config, "mariadb": state["mariadb"],
        "generator": generator.name if generator else None,
        "prompt_version": rag.PROMPT_VERSION if generator else None,
        "system_prompt_sha256": (hashlib.sha256(rag.SYSTEM_PROMPT.encode()).hexdigest()
                                 if generator else None),
        "rag_limits": {"passages": rag.MAX_PASSAGES, "context_tokens": rag.MAX_CONTEXT_TOKENS,
                       "output_tokens": rag.MAX_OUTPUT_TOKENS},
        "answer_passages": "first 5 chunk hits of repetition 1 of the vector search",
    }
    config_id = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    run_id = f"{created:%Y%m%dT%H%M%SZ}-{'-'.join(args.splits)}-{config_id[:8]}"
    out = args.out / run_id
    out.mkdir(parents=True, exist_ok=False)
    with (out / "retrieval.jsonl").open("w") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    (out / "answers.json").write_text(json.dumps(
        {"run_id": run_id, "instructions": "Reviewer (not the author) sets review.status to "
         "approved/needs_changes, grounded/citations_support (answered) or correct_abstention "
         "(unanswerable) to true/false, reviewer and reviewed_at.", "answers": answers},
        indent=2, ensure_ascii=False, default=str) + "\n")
    manifest = {
        "schema": SCHEMA, "card": "S01" if args.hybrid else "C08", "run_id": run_id,
        "created_at": created.isoformat(timespec="seconds"),
        "status": "final" if final else "provisional: question labels are not all approved",
        "final_claims_allowed": final,
        "question_set": {"path": str(args.questions), "corpus_id": document["corpus_id"],
                         "labels_sha256": document["labels_sha256"],
                         "status": document["status"], "label_review": dict(label_review)},
        "splits": {s: sum(q["split"] == s for q in questions) for s in args.splits},
        "corpus": state["corpus"], "chunk_configs": state["chunk_configs"],
        "config_id": config_id, "config": config,
        "warm_up": WARM_UP_POLICY,
        "latency": {"unit": "ms", "boundaries": BOUNDARIES, "statistics": "median and "
                    "nearest-rank p95 over every timed call, including repetitions"},
        "hardware": hardware(), "code": git_state(),
        "files": {"retrieval": "retrieval.jsonl", "answers": "answers.json"},
        "summary": summarize(records, answers),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False,
                                                  default=str) + "\n")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
