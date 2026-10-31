# CiteHop chunks and embeddings (C05)

Code: [`citehop/chunking.py`](../citehop/chunking.py) (pure chunker) and [`citehop/embed.py`](../citehop/embed.py) (model, MariaDB writes, CLI). Rows go into `chunks` ([data model](DATA_MODEL.md)); the full settings behind each hash go into `embedding_configs`.

## Commands

```bash
make venv-ml                                    # uv sync --locked --extra ml (torch, transformers)
python -m citehop.corpus --snapshot data/wikipedia/smoke.json   # C03 load first
python -m citehop.embed run --subset smoke      # make embed-smoke: 10 smoke articles
python -m citehop.embed run                     # make embed: every loaded article
python -m citehop.embed run --limit 3           # first 3 articles by ID (quick smoke batch)
python -m citehop.embed status                  # make embed-status: coverage and stale rows
make test-model                                 # real tokenizer/model tests
```

`make venv` without the extra removes torch/transformers again. The model (`BAAI/bge-base-en-v1.5`, MIT license, ~440 MB) downloads once into the Hugging Face cache (`~/.cache/huggingface`, or `HF_HOME`), outside the repository. No API key is needed; `HF_TOKEN` only raises anonymous rate limits. `requirements-ml.txt` is the hashed pip export of the runtime plus the `ml` extra.

## Chunking

- Tokenizer: the model's own WordPiece tokenizer at the pinned model revision. Counts exclude `[CLS]`/`[SEP]`.
- Windows hold at most **300** tokens. The next window starts **50** tokens before the previous end. Boundaries snap back to the start of a word (`word_ids`), so a chunk never starts or ends inside a word and the overlap is at least 50 tokens (observed 50–54). A single word longer than a window would be cut at token boundaries.
- Chunk text is the exact character span `articles.text[char_start:char_end]`. `token_count` is the actual length of that text re-tokenized; on the real corpus it equals the window length for all 1,776 chunks.
- Empty or whitespace-only text gives no chunks. A short article gives one chunk.
- `chunk_id = sha256("article_id:revision_id:text_sha256:chunk_config:ordinal")`. The same text and settings give the same IDs; any change gives new ones.

## Model input

| Setting | Value |
|---|---|
| Model / revision | `BAAI/bge-base-en-v1.5` @ `a5beb1e3e68b9ab74eb54cfd186867f64f240e1a` |
| Passage input | `"{title}\n\n{passage}"` (no instruction) |
| Query input (C06) | `"Represent this sentence for searching relevant passages: " + query` (`Embedder.embed_query`) |
| Pooling / normalization | `[CLS]` token, L2-normalized, float32, 768 dimensions |
| Limit | 512 tokens including the title and special tokens; `truncation=False` |

Every formatted passage is measured before embedding. Anything over 512 tokens raises `ModelLimitError`; nothing is truncated. Real maximum: 310 input tokens (300 passage + title + separators + 2 special tokens). Vectors are checked for 768 finite values before insert.

## Configuration hashes and invalidation

`chunk_config` hashes tokenizer, revision, `tokenizers`/`transformers` versions, size, overlap, and the boundary rule. `embedding_config` hashes `chunk_config`, model and revision, `torch` version, device, dtype, pooling, normalization, both input formats, and the limit. The JSON behind both is stored in `embedding_configs`.

Per article, the run compares stored `(chunk_id, chunk_config, embedding_config)` rows with the expected set:

- equal: skipped (no model call);
- different (new text, revision, chunking, model, format, library, or device), or partial: all chunk rows of that article are deleted and the new rows inserted in one transaction.

Each article commits separately, so an interrupted run keeps finished articles and resumes with the rest. The write rechecks the article's revision and text hash under a row lock. C03 already deletes chunks when a revision changes or an article is removed. The table therefore holds one active configuration per embedded article; `status` counts rows of any other configuration as `stale_chunks`.

## Measured run (2026-10-31, Apple M6, 24 GB, CPU, torch 2.15.0, MariaDB 11.8.9)

| Run | Articles embedded / skipped | Chunks written | Embedding time | Wall time |
|---|---|---|---|---|
| Smoke (`--subset smoke`, first run) | 10 / 0 | 269 | 13.4 s | 17.9 s, peak 0.73 GB |
| Smoke rerun | 0 / 10 | 0 | 0 s | 2.6 s |
| Full after smoke | 90 / 10 | 1,507 | 83.5 s | 90.2 s |
| Full rerun | 0 / 100 | 0 | 0 s | 2.8 s |

Totals: smoke 269 chunks; full corpus **1,776 chunks** over 100 articles (3–59 per article), passage lengths 51–300 tokens. All 1,776 stored vectors have 768 finite values with norm 1 ± 1e-6. Embedding the whole corpus from scratch on this machine therefore takes about 100 s of model time. Wall times include Python and tokenizer start-up; the first run also loaded the cached weights.
