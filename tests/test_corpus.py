from copy import deepcopy

import pytest
from corpus_fixtures import article, corpus, revise

from citehop.corpus import content_hash, prepare


def test_prepare_drops_orphans_self_links_and_duplicates():
    snapshot, manifest = corpus()
    articles, categories, links, subset, report = prepare(snapshot, manifest)
    assert subset == "full"
    assert [a["article_id"] for a in articles] == [1, 2, 3]
    assert [a["is_smoke"] for a in articles] == [True, True, False]
    assert (1, "Learning") in categories
    assert categories.count((1, "Machine learning")) == 1
    assert report == {"orphan_links": 1, "self_links": 1, "duplicate_categories": 1}
    assert links == [(1, 2), (1, 3), (2, 1), (2, 3), (3, 2)]


def test_smoke_subset_is_recognised_and_partial_snapshots_rejected():
    snapshot, manifest = corpus()
    smoke = {"corpus_id": snapshot["corpus_id"], "articles": snapshot["articles"][:2]}
    assert prepare(smoke, manifest)[3] == "smoke"
    # Links into articles outside the loaded subset become orphans.
    assert prepare(smoke, manifest)[4]["orphan_links"] == 3
    partial = {"corpus_id": snapshot["corpus_id"], "articles": snapshot["articles"][1:]}
    with pytest.raises(ValueError, match="neither"):
        prepare(partial, manifest)


@pytest.mark.parametrize("change, message", [
    (lambda s, m: s["articles"][0].update(text="tampered"), "hash mismatch"),
    (lambda s, m: s["articles"][1].update(title="Machine learning"), "duplicate title"),
    (lambda s, m: s["articles"][2].update(article_id=1), "distinct article_id"),
    (lambda s, m: m["articles"][0].update(revision_id=99), "differs from manifest"),
    (lambda s, m: s.update(corpus_id="x"), "corpus_id"),
    (lambda s, m: s["articles"][0].pop("categories"), "missing"),
])
def test_invalid_snapshots_are_rejected(change, message):
    snapshot, manifest = corpus()
    change(snapshot, manifest)
    with pytest.raises(ValueError, match=message):
        prepare(snapshot, manifest)


def test_content_hash_is_stable_and_tracks_revisions():
    snapshot, manifest = corpus()
    shuffled = deepcopy(snapshot)
    shuffled["articles"].reverse()
    first = content_hash(*prepare(snapshot, manifest)[:3])
    assert first == content_hash(*prepare(shuffled, manifest)[:3])
    assert first != content_hash(*prepare(*revise(snapshot, manifest, 3, "New text."))[:3])


def test_fixture_helper_matches_c02_hashing():
    record = article(9, "X", "abc")
    assert record["length_chars"] == 3 and len(record["text_sha256"]) == 64
