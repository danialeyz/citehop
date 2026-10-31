"""Tiny C02-shaped snapshots for corpus tests."""

import hashlib
from copy import deepcopy


def article(aid, title, text, categories=(), links=(), revision=None):
    return {
        "article_id": aid,
        "title": title,
        "revision_id": revision or aid * 10,
        "source_url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
        "revision_url": f"https://en.wikipedia.org/w/index.php?oldid={revision or aid * 10}",
        "text": text,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "length_chars": len(text),
        "categories": list(categories),
        "internal_links": list(links),
        "provenance": {
            "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
            "attribution": f"{title} — Wikipedia contributors",
        },
    }


def corpus():
    articles = [
        article(1, "Machine learning", "Machine learning studies algorithms.",
                ["Machine learning", "Machine learning", "  Learning   "],
                ["Deep learning", "Perceptron", "Statistics", "Machine learning"]),
        article(2, "Deep learning", "Deep learning uses neural networks.",
                ["Machine learning", "Neural networks"], ["Machine learning", "Perceptron"]),
        article(3, "Perceptron", "The perceptron is a linear classifier.",
                ["Neural networks", "Classification algorithms"], ["Deep learning"]),
    ]
    return snapshot_of(articles, smoke=lambda aid: aid < 3)


def snapshot_of(articles, smoke=lambda aid: False):
    """Snapshot and matching manifest for the given records."""
    manifest = {
        "corpus_id": "c" * 64,
        "articles": [
            {"article_id": a["article_id"], "revision_id": a["revision_id"],
             "revision_timestamp": "2026-10-01T12:00:00Z", "smoke": smoke(a["article_id"])}
            for a in articles
        ],
    }
    return {"corpus_id": manifest["corpus_id"], "articles": articles}, manifest


def revise(snapshot, manifest, aid, text):
    """Copy of the pair where article `aid` has a new revision with new text."""
    snapshot, manifest = deepcopy(snapshot), deepcopy(manifest)
    for record in snapshot["articles"]:
        if record["article_id"] == aid:
            record["revision_id"] += 1
            record["text"] = text
            record["text_sha256"] = hashlib.sha256(text.encode()).hexdigest()
            record["length_chars"] = len(text)
            revision = record["revision_id"]
    for pin in manifest["articles"]:
        if pin["article_id"] == aid:
            pin["revision_id"] = revision
    return snapshot, manifest
