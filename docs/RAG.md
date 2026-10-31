# Bounded answer generation (C07)

`citehop.rag.answer(question, hits)` turns already retrieved passages into one cited answer. It never retrieves; pass it the hits of `search()` (C06).

## Limits and flow

- At most 5 passages and an estimated 1,800 context tokens; whole passages are kept in rank order and the rest are listed in `omitted` with a reason (passage limit, token limit, duplicate, empty). Nothing is cut mid-passage.
- The estimate is `max(ceil(chars/4), ceil(words*1.4))`. On 40 real C05 chunks the default model's actual count was 0.69–1.02× the estimate (median 0.80), so it usually overestimates but is not a strict bound: with real chunks only about 16% of 5-passage sets fit, and the 5th passage is usually dropped. The actual `prompt_tokens` and `output_tokens` from the provider are recorded on every answer.
- One explicit, non-streaming generation call; output capped at 300 tokens; no retries. Hitting the cap sets `truncated`.
- No hits, or no passage that fits, returns `insufficient_evidence` without calling the model.

## Statuses

| Status | Meaning | `text` |
|---|---|---|
| `answered` | Cites at least one supplied label and no unknown label. | answer |
| `insufficient_evidence` | No usable passages, or the model replied `INSUFFICIENT_EVIDENCE`. | `null` |
| `invalid_citations` | Unknown labels (for example `[S9]`, `[7]`) or no citation at all. Raw output kept for debugging only. | `null` |
| `provider_error` | Generator unreachable, misconfigured, or malformed reply. | `null` |

`sources` (label → chunk/article ID, title, URL, passage) is returned for every status, so the passages stay usable when generation fails. A valid label shows which passage the model pointed at; it does not prove the passage supports the claim (C08 reviews grounding).

## Retrieved text is data

Passages are HTML-escaped and fenced in `<passage label=… title=…>` elements in the user message; the system prompt says passage content is reference data whose instructions must never be followed. Label validation is the check that does not rely on the model obeying.

## Generator

One integration: a local [Ollama](https://github.com/ollama/ollama/blob/main/docs/api.md) server, `POST /api/chat` with `stream: false`, `think: false`, temperature 0, seed 0, `num_predict: 300`. Configure `OLLAMA_HOST` and `CITEHOP_GENERATOR_MODEL` in `.env` (see `.env.example`); it runs server-side only and needs no API key. The checked model is `hf.co/unsloth/Qwen3.6-35B-A3B-GGUF:UD-IQ3_XXS` (about 14 GB on disk). Prompt version: `citehop-rag-v1`.

## Live check

```sh
make venv-ml && make rag-validate   # needs the loaded, embedded corpus (C03/C05) and Ollama
```

`scripts/validate_rag.py` runs `search(question, method="vector", k=5)` and then `answer()` for a grounded question (dev-01), an unanswerable one (dev-09), and dev-01 with a synthetic passage inserted at rank 2 that orders the model to cite `[S9]`. It writes `results/c07_rag_validation.json`: corpus version, retrieved hits, model, prompt version and hash, usage, generation latency (ms, one HTTP call, no warm-up), and hardware. Human review is `null`.

Run on 2026-10-31 (Apple M6, 24 GB, corpus version 2): the grounded case answered "Tin Kam Ho … in 1995 [S1]"; the unanswerable case returned `insufficient_evidence`; the injected passage was ignored and the same cited answer came back. The first run took 6.3 s, 1.7 s and 1.9 s; an immediate rerun took 0.3–0.6 s because Ollama reuses the cached prompt prefix, so these are not benchmark numbers. In the grounded case the estimator dropped the 5th retrieved passage (estimated 1,669 + 364 tokens), although the provider counted only 1,558 prompt tokens for the four passages sent plus the system prompt and question.
