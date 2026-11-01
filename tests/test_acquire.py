from copy import deepcopy
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import pytest

from citehop.acquire import (
    FORMAT,
    ArticleText,
    acquire,
    digest,
    load_article,
    pin_snapshot,
    read,
    record,
    retry_after,
    write,
)


def source(pid=1):
    return {
        "parse": {
            "pageid": pid,
            "revid": pid + 1000,
            "title": f"Article {pid}",
            "text": (
                '<p>Evidence about <a href="/wiki/Learning#History">learning</a>.</p>'
                '<p>Second <a href="/wiki/Talk:Learning">paragraph</a>.</p>'
                '<div class="navbox"><a href="/wiki/Navigation_only">Nav</a></div>'
            ),
            "wikitext": "Evidence about learning.",
            "categories": [{"category": "Machine_learning"}],
            "links": [
                {"ns": 0, "title": "Learning"},
                {"ns": 1, "title": "Talk:Learning"},
                {"ns": 0, "title": "Navigation only"},
            ],
        }
    }


def fixture_manifest(tmp_path):
    pins = []
    for pid in range(1, 101):
        raw = source(pid)
        pin = {
            "article_id": pid,
            "revision_id": pid + 1000,
            "title": f"Article {pid}",
            "smoke": pid <= 10,
        }
        pin.update(raw_sha256=digest(raw), record_sha256=digest(record(raw, pin)))
        pins.append(pin)
        write(tmp_path / "raw" / f"{pid + 1000}.json", raw)
    return {"corpus_id": digest(pins), "extraction": FORMAT, "articles": pins}


def no_network(**kwargs):
    pytest.fail("cache rerun made a network request")


def test_offline_smoke_and_full_identical_subset(tmp_path):
    manifest = fixture_manifest(tmp_path)
    report = acquire(manifest, tmp_path, subset="smoke", offline=True, fetch=no_network)
    assert report["records"] == report["cache_hits"] == 10
    smoke = read(tmp_path / "smoke.json")
    acquire(manifest, tmp_path, offline=True, fetch=no_network)
    assert smoke["articles"] == read(tmp_path / "full.json")["articles"][:10]
    assert report == acquire(manifest, tmp_path, subset="smoke", fetch=no_network)


def test_download_uses_only_pinned_revision(tmp_path):
    manifest = fixture_manifest(tmp_path)
    (tmp_path / "raw/1001.json").unlink()
    calls = []

    def fetch(**params):
        calls.append(params)
        return source()

    assert acquire(manifest, tmp_path, "smoke", fetch=fetch)["downloaded"] == 1
    assert calls[0]["oldid"] == 1001
    assert "page" not in calls[0]


def test_corruption_fails_without_refetch(tmp_path):
    manifest = fixture_manifest(tmp_path)
    write(tmp_path / "raw/1001.json", source(2))
    with pytest.raises(ValueError, match="hash mismatch"):
        acquire(manifest, tmp_path, "smoke", fetch=no_network)
    assert not (tmp_path / "smoke.json").exists()
    assert read(tmp_path / "smoke-report.json")["failures"][0]["title"] == "Article 1"


def test_rendering_drift_is_not_accepted(tmp_path):
    manifest = fixture_manifest(tmp_path)
    (tmp_path / "raw/1001.json").unlink()
    with pytest.raises(ValueError, match="source rendering changed"):
        acquire(manifest, tmp_path, "smoke", fetch=lambda **_: source(2))
    assert not (tmp_path / "raw/1001.json").exists()


def test_volatile_rerender_keeps_pinned_record(tmp_path):
    manifest = fixture_manifest(tmp_path)
    original = load_article(manifest["articles"][0], tmp_path)
    (tmp_path / "raw/1001.json").unlink()
    rerendered = source(1)
    rerendered["parse"]["text"] += "<!-- Parsed by another host; Cached time: 20261031 -->"
    report = acquire(manifest, tmp_path, "smoke", fetch=lambda **_: deepcopy(rerendered))
    assert report["rerendered"] == ["Article 1"] and not report["failures"]
    assert read(tmp_path / "smoke.json")["articles"][0] == original
    assert acquire(manifest, tmp_path, "smoke", offline=True)["rerendered"] == []


def test_revision_mismatch_and_text_config_invalidate(tmp_path):
    manifest = fixture_manifest(tmp_path)
    pin = deepcopy(manifest["articles"][0])
    pin["revision_id"] = 1002
    with pytest.raises(ValueError, match="identity mismatch"):
        record(source(), pin)
    pin = deepcopy(manifest["articles"][0])
    pin["record_sha256"] = "wrong"
    with pytest.raises(ValueError, match="extracted snapshot hash"):
        load_article(pin, tmp_path)


def live_source(**params):
    """Fake API: title 'Article N' resolves to page N at revision N + 1000."""
    if params["action"] == "query":
        pid = int(params["titles"].split()[-1])
        page = {"pageid": pid, "ns": 0, "title": params["titles"]}
        page["revisions"] = [{"revid": pid + 1000, "timestamp": "2026"}]
        return {"query": {"pages": [page]}}
    return source(params["oldid"] - 1000)


def test_bad_progress_entry_is_repinned(tmp_path):
    titles = [f"Article {i}" for i in range(1, 101)]
    pin_snapshot(titles, tmp_path / "first.json", tmp_path, fetch=live_source)
    (tmp_path / "raw/1001.json").unlink()
    write(tmp_path / "raw/1002.json", source(3))
    calls = []

    def fetch(**params):
        calls.append(params.get("titles") or params["oldid"])
        return live_source(**params)

    manifest = pin_snapshot(titles, tmp_path / "second.json", tmp_path, fetch=fetch)
    assert sorted(calls, key=str) == [1001, 1002, "Article 1", "Article 2"]
    assert manifest["corpus_id"] == read(tmp_path / "first.json")["corpus_id"]
    assert pin_snapshot(titles, tmp_path / "third.json", tmp_path, fetch=no_network)


def test_retry_after_seconds_and_dates():
    assert retry_after({"Retry-After": "26"}) == 26
    assert retry_after({}) == retry_after({"Retry-After": "soon"}) == 0
    later = format_datetime(datetime.now(UTC) + timedelta(seconds=90), usegmt=True)
    assert 80 <= retry_after({"Retry-After": later}) <= 90
    assert retry_after({"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"}) == 0


def test_missing_pages_reported_no_manifest(tmp_path):
    def missing(**params):
        return {"query": {"pages": [{"title": params["titles"], "missing": True}]}}

    with pytest.raises(ValueError, match="incomplete"):
        pin_snapshot(
            [f"Absent {i}" for i in range(100)], tmp_path / "corpus.json", tmp_path, fetch=missing
        )
    assert len(read(tmp_path / "pin-report.json")["failures"]) == 100
    assert not (tmp_path / "corpus.json").exists()


def test_redirect_not_silently_followed(tmp_path):
    def redirect(**params):
        if params["action"] == "query":
            return {
                "query": {
                    "pages": [
                        {
                            "pageid": 1,
                            "ns": 0,
                            "title": params["titles"],
                            "revisions": [{"revid": 1001, "timestamp": "2026"}],
                        }
                    ]
                }
            }
        raw = source()
        raw["parse"]["wikitext"] = "#REDIRECT [[Other]]"
        return raw

    with pytest.raises(ValueError, match="incomplete"):
        pin_snapshot(
            [f"Redirect {i}" for i in range(100)],
            tmp_path / "corpus.json",
            tmp_path,
            fetch=redirect,
        )
    assert all(
        "redirect title" in f["error"] for f in read(tmp_path / "pin-report.json")["failures"]
    )


def test_text_and_metadata():
    parser = ArticleText()
    parser.feed(
        "<style>bad</style><p>A &amp; B<sup>1</sup>.</p>"
        '<div class="navbox"><p>Navigation</p></div><p>Next.</p>'
    )
    assert parser.text() == "A & B.\nNext."
    parser = ArticleText()
    parser.feed(
        '<table class="sidebar"><tr><td>Series</td></tr></table><p>Body.</p>'
        '<div class="mw-heading mw-heading2"><h2 id="Applications">Applications</h2></div>'
        '<p>Use.</p><div class="mw-heading mw-heading2"><h2 id="See_also">See also</h2></div>'
        '<ul><li>Other</li></ul><h2 id="References">References</h2><p>Cite.</p>'
    )
    assert parser.text() == "Body.\nApplications\nUse."
    article = record(source(), {"article_id": 1, "revision_id": 1001, "title": "Article 1"})
    assert article["categories"] == ["Machine learning"]
    assert article["internal_links"] == ["Learning"]
    assert "oldid=1001" in article["revision_url"]
    assert article["provenance"]["attribution"] == "Article 1 — Wikipedia contributors"
