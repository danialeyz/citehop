# Corpus snapshot and evaluation questions

## Files

| File | Tracked | Contents |
| --- | --- | --- |
| `article_titles.txt` | yes | 100 canonical English Wikipedia titles; the first 10 are the smoke subset. |
| `corpus.json` | yes | Pinned manifest: page ID, revision ID/timestamp, smoke flag, raw and extracted-record SHA-256 per article; `corpus_id` hashes all pins. |
| `questions.json` | yes | 30 frozen draft questions (10 dev, 20 test) tied to `corpus_id`. |
| `data/wikipedia/raw/<revision_id>.json` | no (cache) | MediaWiki `action=parse` output for the pinned revision. |
| `data/wikipedia/{smoke,full}.json` | no (cache) | Extracted records: title, URL, revision URL, text, categories, internal links, provenance. |

## Commands

```bash
python -m citehop.acquire pin                       # once; refuses to overwrite eval/corpus.json
python -m citehop.acquire fetch --subset smoke      # 10 articles; downloads only missing revisions
python -m citehop.acquire fetch --subset full       # 100 articles
python -m citehop.acquire fetch --offline           # cache only, never touches the network
python -m citehop.questions                         # validate questions against data/wikipedia/full.json
```

`pin` fails and writes no manifest if any title is missing, a redirect, or not in the article namespace. It never substitutes another page. Redirects are replaced by hand in `article_titles.txt`. `fetch` requests only `oldid=<pinned revision>` and rejects any response whose hash differs from the pin. If MediaWiki re-renders an old revision and only volatile HTML changes (the parser report comment), the extracted record must still equal the pin; it is accepted and listed under `rerendered` in the report. Any content change (for example after a template change) fails the run with a report. Restore the original cache or pin a new corpus version. Set `WIKIPEDIA_USER_AGENT` to identify yourself to Wikimedia.

## Provenance and attribution

Article text comes from English Wikipedia and is licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Each record stores its source URL, permanent revision URL, history URL (authors), license URL, and the attribution line "<title> — Wikipedia contributors". Modification: the rendered HTML was converted to plain text, and navigation boxes, references, edit links, styles, and math markup were removed. Anything that shows or redistributes passages must link the revision URL and the license. The graph uses the article's own internal links and categories. These are not scholarly citations or inferred relationships.

## Question set

Each question has `id`, `split`, `question`, `answerable`, `filters` (`category`, `min_length_chars`, `max_length_chars`, `linked_from` article ID), `tags`, `relevant_article_ids`, `evidence` (exact character spans of the pinned text), `expected_answer`, `unanswerable_reason`, and `review`. Filtered cases carry the `filtered` tag. Unanswerable cases carry `unanswerable`, a reason, and no positive labels. Some also have `scope_evidence`, which shows nearby text that does *not* answer the question.

`labels_sha256` freezes everything except `review`. Changing a question, filter, or label after tuning has started requires a new versioned question set, not an edit.

## Human review checklist

Drafts were written by an AI agent and are `unreviewed`. A team member other than the author checks each question and then sets `review.status` to `approved` or `needs_changes`, with `reviewer` (name) and `reviewed_at` (ISO date). Validation rejects sign-off without both.

1. Open the revision URL and confirm the evidence passage says what the expected answer claims.
2. The question is answerable from the evidence alone, without outside knowledge, and does not copy the passage verbatim.
3. No other corpus article is an equally good answer that is missing from `relevant_article_ids`.
4. Filtered: the filter is meaningful for the question and still admits every relevant article. The validator checks admission.
5. Unanswerable: the corpus really lacks the answer (search the full text for key terms), and the reason is accurate.
6. Note problems in `review.notes`. Do not edit frozen fields during review.
7. Run `python -m citehop.questions`. Final metrics need `final_claims_allowed: true`.
