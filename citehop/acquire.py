"""Small, explicit Wikipedia snapshot CLI; no database or model dependencies."""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urlencode
from urllib.request import Request, urlopen

API = "https://en.wikipedia.org/w/api.php"
FORMAT = "wikipedia-html-text-v2"
# Trailing back-matter sections; extraction stops at the first of these headings.
BACK_MATTER = {
    "See_also",
    "Notes",
    "References",
    "Sources",
    "Citations",
    "Footnotes",
    "Bibliography",
    "Literature",
    "Further_reading",
    "External_links",
}
LICENSE = "https://creativecommons.org/licenses/by-sa/4.0/"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temp.replace(path)


class ArticleText(HTMLParser):
    """Strip presentation, references, navigation and back matter; keep prose/list/table text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.stack = []
        self.done = False
        self.links = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h2" and attrs.get("id") in BACK_MATTER:
            self.done = True
        classes = set(attrs.get("class", "").split())
        skip = (
            tag in {"script", "style", "sup", "math"}
            or bool(
                classes
                & {
                    "navbox",
                    "vertical-navbox",
                    "sidebar",
                    "infobox",
                    "navbar",
                    "ambox",
                    "side-box",
                    "references",
                    "mw-references-wrap",
                    "refbegin",
                    "metadata",
                    "reference",
                    "reflist",
                    "mw-editsection",
                    "shortdescription",
                    "hatnote",
                    "toc",
                    "noprint",
                }
            )
            or "display:none" in attrs.get("style", "").replace(" ", "")
        )
        hidden = skip or (self.stack and self.stack[-1][1])
        href = attrs.get("href") or ""
        if tag == "a" and not hidden and not self.done and href.startswith("/wiki/"):
            self.links.add(unquote(href[6:]).split("#")[0].replace("_", " "))
        if tag not in {
            "br",
            "hr",
            "img",
            "meta",
            "link",
            "input",
            "wbr",
            "source",
            "area",
            "base",
            "col",
            "embed",
            "param",
            "track",
        }:
            self.stack.append((tag, bool(hidden)))
        if not hidden and not self.done and tag in {"p", "div", "li", "tr", "h2", "h3", "h4", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break
        if tag in {"p", "div", "li", "tr", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.done:
            return
        if not self.stack or not self.stack[-1][1]:
            self.parts.append(data)

    def text(self):
        return "\n".join(
            line for part in "".join(self.parts).splitlines() if (line := " ".join(part.split()))
        )


def retry_after(headers):
    """Seconds requested by a Retry-After header (delay or HTTP date); 0 if absent/invalid."""
    value = (headers.get("Retry-After") or "").strip()
    if value.isdigit():
        return int(value)
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return 0
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0, int((when - datetime.now(UTC)).total_seconds()))


def api(**params):
    url = API + "?" + urlencode({"format": "json", "formatversion": 2, **params})
    request = Request(
        url,
        headers={
            "User-Agent": os.environ.get(
                "WIKIPEDIA_USER_AGENT",
                "CiteHopCourse/0.1 (https://github.com/danialeyz/citehop; educational snapshot)",
            )
        },
    )
    attempts = 6
    for attempt in range(attempts):
        time.sleep(1)
        try:
            with urlopen(request, timeout=45) as response:
                result = json.load(response)
            if "error" in result:
                raise ValueError(f"Wikipedia {result['error']['code']}: {result['error']['info']}")
            return result
        except HTTPError as exc:
            if attempt == attempts - 1 or exc.code not in {429, 502, 503, 504}:
                raise
            time.sleep(min(max(retry_after(exc.headers), 2 ** (attempt + 1)), 120))
        except (OSError, HTTPException) as exc:
            # Truncated chunked responses raise IncompleteRead, an HTTPException.
            if attempt == attempts - 1:
                raise OSError(f"Wikipedia request failed: {exc!r}") from exc
            time.sleep(2**attempt)


def record(raw, pin):
    parsed = raw["parse"]
    if (parsed["pageid"], parsed["revid"]) != (pin["article_id"], pin["revision_id"]):
        raise ValueError("source page/revision identity mismatch")
    parser = ArticleText()
    parser.feed(parsed["text"])
    text = parser.text()
    if not text:
        raise ValueError("empty article text")
    title = pin["title"]
    url = "https://en.wikipedia.org/wiki/" + quote(title.replace(" ", "_"))
    return {
        "article_id": pin["article_id"],
        "title": title,
        "revision_id": pin["revision_id"],
        "source_url": url,
        "revision_url": f"https://en.wikipedia.org/w/index.php?oldid={pin['revision_id']}",
        "text": text,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "length_chars": len(text),
        "categories": sorted({c["category"].replace("_", " ") for c in parsed["categories"]}),
        # Article-namespace links that appear in the kept body text, not navboxes/sidebars.
        "internal_links": sorted(
            {link["title"] for link in parsed["links"] if link["ns"] == 0} & parser.links
        ),
        "provenance": {
            "api": API,
            "extraction": FORMAT,
            "raw_sha256": digest(raw),
            "license_url": LICENSE,
            "attribution": f"{title} — Wikipedia contributors",
            "history_url": url + "?action=history",
            "changes": (
                "HTML converted to text; navigation, infobox/sidebar, references, styles and "
                "back-matter sections (See also onward) removed."
            ),
        },
    }


def pinned_record(raw, pin):
    """Extract `raw` and check it against the pinned record.

    MediaWiki re-parses an old revision when its parser cache expires; the HTML then differs in
    volatile comments (parser host, timings), so the raw hash changes. Such a re-render is accepted
    only when the extracted record (text, categories, links, URLs) is identical to the pin, and it
    keeps the pinned raw hash so the corpus content hash does not change.
    """
    result = record(raw, pin)
    result["provenance"]["raw_sha256"] = pin["raw_sha256"]
    if digest(result) != pin["record_sha256"]:
        raise ValueError(f"extracted snapshot hash mismatch: {pin['title']}")
    return result


def load_article(pin, cache):
    raw = read(Path(cache) / "raw" / f"{pin['revision_id']}.json")
    try:
        return pinned_record(raw, pin)
    except ValueError:
        if digest(raw) != pin["raw_sha256"]:
            raise ValueError(f"raw snapshot hash mismatch: {pin['title']}") from None
        raise


def pin_snapshot(titles, manifest_path, cache, fetch=api):
    if Path(manifest_path).exists():
        raise ValueError("manifest exists; choose a new path to create a new corpus version")
    if len(titles) != 100 or len(set(titles)) != 100:
        raise ValueError("expected exactly 100 distinct titles")
    progress_path = Path(cache) / "pin-progress.json"
    progress = read(progress_path) if progress_path.exists() else {}
    pins, failures = [], []
    for index, title in enumerate(titles):
        try:
            if title in progress:
                pin = progress[title]
                try:
                    load_article(pin, cache)
                except (KeyError, OSError, ValueError) as exc:
                    # Drop the unusable entry so this run (and later ones) pin the title afresh.
                    print(f"Re-pinning {title}: {exc}", flush=True)
                    del progress[title]
                    write(progress_path, progress)
                else:
                    pin["smoke"] = index < 10
                    pins.append(pin)
                    continue
            page = fetch(action="query", titles=title, prop="revisions", rvprop="ids|timestamp")[
                "query"
            ]["pages"][0]
            if "missing" in page or page.get("ns") != 0:
                raise ValueError("missing page or non-article namespace; no substitution")
            revision = page["revisions"][0]
            pin = {
                "requested_title": title,
                "title": page["title"],
                "article_id": page["pageid"],
                "revision_id": revision["revid"],
                "revision_timestamp": revision["timestamp"],
                "smoke": index < 10,
            }
            raw = fetch(
                action="parse",
                oldid=pin["revision_id"],
                prop="text|categories|links|revid|wikitext",
                disableeditsection=1,
            )
            if raw["parse"]["wikitext"].lstrip().lower().startswith("#redirect"):
                raise ValueError("redirect title; select its canonical title explicitly")
            article = record(raw, pin)
            pin.update(raw_sha256=digest(raw), record_sha256=digest(article))
            write(Path(cache) / "raw" / f"{pin['revision_id']}.json", raw)
            pins.append(pin)
            progress[title] = pin
            write(progress_path, progress)
            print(f"Pinned {len(pins)}/100: {pin['title']}", flush=True)
        except (KeyError, OSError, ValueError) as exc:
            failures.append({"title": title, "error": str(exc)})
            print(f"FAILED {title}: {exc}", flush=True)
    write(Path(cache) / "pin-report.json", {"failures": failures, "pinned": len(pins)})
    if failures or len({p["article_id"] for p in pins}) != 100:
        raise ValueError("snapshot incomplete; see pin-report.json; no manifest published")
    manifest = {
        "schema_version": 1,
        "language": "en",
        "extraction": FORMAT,
        "created_at": datetime.now(UTC).isoformat(),
        "articles": pins,
    }
    manifest["corpus_id"] = digest(pins)
    write(manifest_path, manifest)
    return manifest


def acquire(manifest, cache, subset="full", offline=False, fetch=api):
    pins = manifest["articles"]
    if manifest["corpus_id"] != digest(pins) or manifest["extraction"] != FORMAT:
        raise ValueError("manifest version/hash mismatch")
    if len(pins) != 100 or sum(p["smoke"] for p in pins) != 10:
        raise ValueError("manifest must contain 100 articles and 10 smoke articles")
    selected = [p for p in pins if subset == "full" or p["smoke"]]
    articles, failures, rerendered, downloaded = [], [], [], 0
    for pin in selected:
        try:
            path = Path(cache) / "raw" / f"{pin['revision_id']}.json"
            if not path.exists():
                if offline:
                    raise ValueError("snapshot absent in offline mode")
                raw = fetch(
                    action="parse",
                    oldid=pin["revision_id"],
                    prop="text|categories|links|revid|wikitext",
                    disableeditsection=1,
                )
                if digest(raw) != pin["raw_sha256"]:
                    try:
                        pinned_record(raw, pin)
                    except ValueError:
                        raise ValueError(
                            "source rendering changed; restore original cache or pin NEW snapshot"
                        ) from None
                    rerendered.append(pin["title"])
                write(path, raw)
                downloaded += 1
            articles.append(load_article(pin, cache))
        except (OSError, ValueError, KeyError) as exc:
            failures.append({"title": pin["title"], "error": str(exc)})
    report = {
        "corpus_id": manifest["corpus_id"],
        "subset": subset,
        "expected": len(selected),
        "records": len(articles),
        "downloaded": downloaded,
        "cache_hits": len(articles) - downloaded,
        "rerendered": rerendered,
        "failures": failures,
    }
    write(Path(cache) / f"{subset}-report.json", report)
    if failures:
        raise ValueError(f"acquisition incomplete: {failures}")
    write(
        Path(cache) / f"{subset}.json", {"corpus_id": manifest["corpus_id"], "articles": articles}
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["pin", "fetch"])
    parser.add_argument("--manifest", default="eval/corpus.json")
    parser.add_argument("--titles", default="eval/article_titles.txt")
    parser.add_argument("--cache", default="data/wikipedia")
    parser.add_argument("--subset", choices=["smoke", "full"], default="full")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "pin":
            pin_snapshot(Path(args.titles).read_text().splitlines(), args.manifest, args.cache)
        else:
            print(json.dumps(acquire(read(args.manifest), args.cache, args.subset, args.offline)))
    except (OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
