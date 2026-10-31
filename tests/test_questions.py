from copy import deepcopy

import pytest

from citehop.acquire import digest
from citehop.questions import semantic_labels, validate


def corpus():
    texts = {1: "Alpha learns from labels.", 2: "Beta clusters points.", 3: "Gamma links."}
    articles = [
        {
            "article_id": aid,
            "title": f"T{aid}",
            "revision_id": aid + 100,
            "text": text,
            "text_sha256": digest(text),
            "length_chars": len(text),
            "categories": ["Supervised"] if aid == 1 else ["Unsupervised"],
            "internal_links": ["T1", "T2"] if aid == 3 else [],
        }
        for aid, text in texts.items()
    ]
    return {"corpus_id": "c1", "articles": articles}


def evidence(article, passage):
    start = article["text"].index(passage)
    return {
        "article_id": article["article_id"],
        "revision_id": article["revision_id"],
        "text_sha256": article["text_sha256"],
        "start_char": start,
        "end_char": start + len(passage),
        "passage": passage,
    }


def question(i, split, articles, answerable=True, filters=None):
    a = articles[0]
    q = {
        "id": f"{split}-{i:02d}",
        "split": split,
        "question": "What does alpha learn from?",
        "answerable": answerable,
        "filters": filters or {},
        "tags": ["filtered"] if filters else [],
        "relevant_article_ids": [a["article_id"]],
        "evidence": [evidence(a, "learns from labels")],
        "expected_answer": "Labels.",
        "unanswerable_reason": None,
        "review": {"status": "unreviewed", "reviewer": None, "reviewed_at": None, "notes": ""},
    }
    if not answerable:
        q.update(
            relevant_article_ids=[],
            evidence=[],
            expected_answer=None,
            tags=q["tags"] + ["unanswerable"],
            unanswerable_reason="Not stated in the corpus.",
        )
    return q


def document(c):
    articles = c["articles"]
    questions = []
    for split, n in (("dev", 10), ("test", 20)):
        for i in range(n):
            filters = {"category": "Supervised"} if i == 0 else None
            questions.append(question(i, split, articles, answerable=i != 1, filters=filters))
    return {
        "corpus_id": c["corpus_id"],
        "questions": questions,
        "labels_sha256": digest(semantic_labels(questions)),
    }


def refreeze(doc):
    doc["labels_sha256"] = digest(semantic_labels(doc["questions"]))
    return doc


def test_valid_drafts_block_final_claims():
    result = validate(document(corpus()), corpus())
    assert result["review_status"] == {"unreviewed": 30}
    assert result["final_claims_allowed"] is False
    assert result["filtered"] == 2 and result["answerable"] == 28


def test_review_status_is_mutable_but_labels_are_frozen():
    c, doc = corpus(), document(corpus())
    doc["questions"][0]["review"] = {
        "status": "approved",
        "reviewer": "teammate",
        "reviewed_at": "2026-10-31",
        "notes": "",
    }
    assert validate(doc, c)["review_status"]["approved"] == 1
    doc["questions"][0]["question"] = "Changed?"
    with pytest.raises(ValueError, match="frozen labels changed"):
        validate(doc, c)


def test_signoff_requires_reviewer():
    doc = document(corpus())
    doc["questions"][0]["review"]["status"] = "approved"
    with pytest.raises(ValueError, match="team member"):
        validate(doc, corpus())


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda q: q.update(relevant_article_ids=[99]), "unknown relevant"),
        (lambda q: q.update(filters={"category": "Unsupervised"}), "filters exclude"),
        (lambda q: q.update(filters={"linked_from": 2}, tags=["filtered"]), "filters exclude"),
        (lambda q: q.update(filters={"colour": "x"}, tags=["filtered"]), "unknown filter"),
        (lambda q: q["evidence"][0].update(passage="learns from label"), "evidence does not"),
        (lambda q: q.update(tags=[]), "separately tagged"),
    ],
)
def test_bad_labels_rejected(mutate, message):
    c, doc = corpus(), document(corpus())
    mutate(doc["questions"][0])
    with pytest.raises(ValueError, match=message):
        validate(refreeze(doc), c)


def test_linked_from_admits_linked_source():
    c, doc = corpus(), document(corpus())
    doc["questions"][0]["filters"] = {"linked_from": 3}
    assert validate(refreeze(doc), c)["filtered"] == 2


def test_unanswerable_must_not_carry_positive_labels():
    c, doc = corpus(), document(corpus())
    doc["questions"][1]["relevant_article_ids"] = [1]
    with pytest.raises(ValueError, match="unanswerable case"):
        validate(refreeze(doc), c)


def test_corpus_version_mismatch():
    c = deepcopy(corpus())
    c["corpus_id"] = "other"
    with pytest.raises(ValueError, match="version mismatch"):
        validate(document(corpus()), c)
