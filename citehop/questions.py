"""Validate frozen draft labels against the exact acquired corpus (no model calls)."""

import argparse
import sys
from collections import Counter

from citehop.acquire import digest, read


def eligible(article, filters, articles):
    allowed = {"category", "min_length_chars", "max_length_chars", "linked_from"}
    if set(filters) - allowed:
        raise ValueError("unknown filter")
    for key in ("min_length_chars", "max_length_chars"):
        if key in filters and (type(filters[key]) is not int or filters[key] < 0):
            raise ValueError("length filters must be nonnegative integers")
    if filters.get("min_length_chars", 0) > filters.get("max_length_chars", float("inf")):
        raise ValueError("inverted length bounds")
    if "category" in filters and not isinstance(filters["category"], str):
        raise ValueError("category must be a string")
    if "linked_from" in filters and filters["linked_from"] not in articles:
        raise ValueError("linked_from does not resolve")
    return (
        ("category" not in filters or filters["category"] in article["categories"])
        and article["length_chars"] >= filters.get("min_length_chars", 0)
        and article["length_chars"] <= filters.get("max_length_chars", float("inf"))
        and (
            "linked_from" not in filters
            or article["title"] in articles[filters["linked_from"]]["internal_links"]
        )
    )


def validate(document, corpus):
    if document["corpus_id"] != corpus["corpus_id"]:
        raise ValueError("questions/corpus version mismatch")
    questions = document["questions"]
    if len(questions) != 30 or Counter(q["split"] for q in questions) != {"dev": 10, "test": 20}:
        raise ValueError("expected 10 dev and 20 test questions")
    if len({q["id"] for q in questions}) != 30:
        raise ValueError("duplicate question IDs")
    if document["labels_sha256"] != digest(semantic_labels(questions)):
        raise ValueError("frozen labels changed; explicitly version the question set")
    articles = {a["article_id"]: a for a in corpus["articles"]}
    for q in questions:
        if not q["id"] or not q["question"].strip() or type(q["answerable"]) is not bool:
            raise ValueError("invalid question identity/text/answerability")
        review = q["review"]
        if review["status"] not in {"unreviewed", "approved", "needs_changes"}:
            raise ValueError(f"{q['id']}: invalid review status")
        if review["status"] != "unreviewed" and not (review["reviewer"] and review["reviewed_at"]):
            raise ValueError("review needs a team member and timestamp")
        if review["status"] == "unreviewed" and (review["reviewer"] or review["reviewed_at"]):
            raise ValueError("unreviewed draft cannot carry signoff")
        relevant = q["relevant_article_ids"]
        if len(set(relevant)) != len(relevant) or set(relevant) - articles.keys():
            raise ValueError(f"{q['id']}: duplicate/unknown relevant article")
        # Validate filters even on unanswerable cases with no relevant articles.
        admitted = {
            aid for aid, article in articles.items() if eligible(article, q["filters"], articles)
        }
        if not set(relevant) <= admitted:
            raise ValueError(f"{q['id']}: filters exclude labeled sources")
        if bool(q["filters"]) != ("filtered" in q["tags"]):
            raise ValueError("filtered cases must be separately tagged")
        if q["answerable"]:
            if not relevant or "unanswerable" in q["tags"] or not q["expected_answer"]:
                raise ValueError("answerable question needs labels and draft answer")
            if {e["article_id"] for e in q["evidence"]} != set(relevant):
                raise ValueError("each relevant article needs supporting evidence")
        elif (
            relevant
            or q["evidence"]
            or q["expected_answer"] is not None
            or "unanswerable" not in q["tags"]
            or not q["unanswerable_reason"]
        ):
            raise ValueError("unanswerable case needs separate tag/reason and no positive labels")
        for e in q["evidence"] + q.get("scope_evidence", []):
            a = articles[e["article_id"]]
            start, end = e["start_char"], e["end_char"]
            if (
                e["revision_id"] != a["revision_id"]
                or e["text_sha256"] != a["text_sha256"]
                or not 0 <= start < end <= len(a["text"])
                or a["text"][start:end] != e["passage"]
            ):
                raise ValueError(f"{q['id']}: evidence does not match pinned text")
    for split in ("dev", "test"):
        cases = [q for q in questions if q["split"] == split]
        if not any(q["filters"] for q in cases) or not any(not q["answerable"] for q in cases):
            raise ValueError("each split needs filtered and unanswerable cases")
    return {
        "questions": 30,
        "splits": {"dev": 10, "test": 20},
        "answerable": sum(q["answerable"] for q in questions),
        "filtered": sum(bool(q["filters"]) for q in questions),
        "review_status": dict(Counter(q["review"]["status"] for q in questions)),
        "final_claims_allowed": all(q["review"]["status"] == "approved" for q in questions),
    }


def semantic_labels(questions):
    """Review metadata is mutable; questions, splits, filters and evidence are frozen."""
    return [{k: v for k, v in q.items() if k != "review"} for q in questions]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", default="eval/questions.json")
    parser.add_argument("--corpus", default="data/wikipedia/full.json")
    args = parser.parse_args()
    try:
        print(validate(read(args.questions), read(args.corpus)))
    except (KeyError, OSError, ValueError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
