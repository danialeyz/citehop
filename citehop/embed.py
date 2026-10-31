"""Chunk MariaDB articles and store BGE embeddings, resumably.

    python -m citehop.embed run --subset smoke   # 10 smoke articles
    python -m citehop.embed run                  # every loaded article
    python -m citehop.embed status

Each article is committed in its own transaction together with all its chunks and vectors.
An article whose stored chunk IDs and configuration hashes already match is skipped, so an
interrupted run resumes where it stopped. Any other chunk rows of a processed article (old
text, chunking, model or formatting) are deleted before the new rows are inserted. Inputs that
exceed the model limit raise an error; nothing is truncated.
"""

import argparse
import json
import math
import sys
import time

from citehop.chunking import (
    BOUNDARY_RULE,
    CHUNK_TOKENS,
    OVERLAP_TOKENS,
    chunk_article,
    config_hash,
)

MODEL_ID = "BAAI/bge-base-en-v1.5"
MODEL_REVISION = "a5beb1e3e68b9ab74eb54cfd186867f64f240e1a"  # Hugging Face commit, 2024-02-21
DIMENSIONS = 768
MAX_INPUT_TOKENS = 512  # model position limit, including [CLS] and [SEP]
PASSAGE_FORMAT = "{title}\n\n{passage}"
# BGE v1.5 recommends this instruction for short retrieval queries; passages get none.
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class ModelLimitError(ValueError):
    pass


def configs(versions, device="cpu", chunk_tokens=CHUNK_TOKENS, overlap_tokens=OVERLAP_TOKENS):
    """(chunk_config, embedding_config, record) for the given library versions.

    Library versions and the device are part of the hashes: a different tokenizer build or
    numeric backend may change tokens or vectors, so it must not reuse stored rows.
    """
    chunking = {
        "tokenizer": MODEL_ID, "tokenizer_revision": MODEL_REVISION,
        "tokenizers": versions["tokenizers"], "transformers": versions["transformers"],
        "chunk_tokens": chunk_tokens, "overlap_tokens": overlap_tokens,
        "boundary_rule": BOUNDARY_RULE, "special_tokens_in_count": False,
    }
    chunk_config = config_hash(chunking)
    embedding = {
        "chunk_config": chunk_config, "model": MODEL_ID, "model_revision": MODEL_REVISION,
        "torch": versions["torch"], "device": device, "dtype": "float32",
        "dimensions": DIMENSIONS, "pooling": "cls", "normalization": "l2",
        "passage_format": PASSAGE_FORMAT, "query_instruction": QUERY_INSTRUCTION,
        "max_input_tokens": MAX_INPUT_TOKENS, "truncation": False,
    }
    embedding_config = config_hash(embedding)
    return chunk_config, embedding_config, {"chunking": chunking, "embedding": embedding}


def model_inputs(title, chunks, input_length, limit=MAX_INPUT_TOKENS):
    """Formatted passages and their full model lengths; raise instead of truncating."""
    texts = [PASSAGE_FORMAT.format(title=title, passage=chunk.text) for chunk in chunks]
    lengths = [input_length(text) for text in texts]
    for chunk, length in zip(chunks, lengths, strict=True):
        if length > limit:
            raise ModelLimitError(f"{title!r} chunk {chunk.ordinal}: {length} input tokens "
                                  f"exceed the model limit of {limit}")
    return texts, lengths


def is_current(existing, chunks, chunk_config, embedding_config):
    """True when stored rows are exactly the expected chunks under the active configuration."""
    return existing == {(chunk.chunk_id, chunk_config, embedding_config) for chunk in chunks}


class Embedder:
    """Pinned BGE tokenizer and model. Weights download to the Hugging Face cache and load on
    first use, so a rerun with nothing to embed needs only the tokenizer."""

    def __init__(self, device="cpu"):
        import tokenizers
        import torch
        import transformers

        self.torch, self.transformers, self.device = torch, transformers, device
        self.tokenizer = transformers.AutoTokenizer.from_pretrained(
            MODEL_ID, revision=MODEL_REVISION)
        self._model = None
        self.versions = {"torch": torch.__version__, "transformers": transformers.__version__,
                         "tokenizers": tokenizers.__version__}

    @property
    def model(self):
        if self._model is None:
            model = self.transformers.AutoModel.from_pretrained(
                MODEL_ID, revision=MODEL_REVISION, dtype=self.torch.float32)
            if model.config.hidden_size != DIMENSIONS:
                raise ValueError(f"{MODEL_ID} has {model.config.hidden_size} dimensions")
            self._model = model.to(self.device).eval()
        return self._model

    def tokenize(self, text):
        encoding = self.tokenizer(text, add_special_tokens=False, return_offsets_mapping=True,
                                  truncation=False, verbose=False)
        return [(start, end, word) for (start, end), word
                in zip(encoding["offset_mapping"], encoding.word_ids(), strict=True)]

    def count(self, text):
        return len(self.tokenizer(text, add_special_tokens=False, truncation=False,
                                  verbose=False)["input_ids"])

    def input_length(self, text):
        return len(self.tokenizer(text, truncation=False, verbose=False)["input_ids"])

    def embed(self, texts):
        batch = self.tokenizer(texts, padding=True, truncation=False, return_tensors="pt",
                               verbose=False).to(self.device)
        if batch["input_ids"].shape[1] > MAX_INPUT_TOKENS:
            raise ModelLimitError(f"batch input of {batch['input_ids'].shape[1]} tokens")
        with self.torch.inference_mode():
            cls = self.model(**batch).last_hidden_state[:, 0]
            vectors = self.torch.nn.functional.normalize(cls, p=2, dim=1).cpu()
        if vectors.shape[1] != DIMENSIONS or not bool(self.torch.isfinite(vectors).all()):
            raise ValueError("embedding output is not finite or has the wrong dimension")
        return vectors.tolist()

    def embed_query(self, query):
        return self.embed([QUERY_INSTRUCTION + query])[0]


def check_vector(vector):
    if len(vector) != DIMENSIONS or not all(math.isfinite(value) for value in vector):
        raise ValueError("vector is not finite or has the wrong dimension")
    return json.dumps(vector)


INSERT = ("INSERT INTO chunks (chunk_id, article_id, revision_id, chunk_config, ordinal, "
          "char_start, char_end, token_count, text, embedding, embedding_config) "
          "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, VEC_FromText(?), ?)")


def write_article(connection, article, chunks, vectors, chunk_config, embedding_config,
                  batch_size=16):
    """Replace one article's chunk rows in a single transaction; return rows deleted."""
    cursor = connection.cursor()
    try:
        connection.begin()
        cursor.execute("SELECT revision_id, text_sha256 FROM articles WHERE article_id = ? "
                       "FOR UPDATE", (article["article_id"],))
        if cursor.fetchone() != (article["revision_id"], article["text_sha256"]):
            raise RuntimeError(f"{article['title']!r} changed during embedding; rerun")
        cursor.execute("DELETE FROM chunks WHERE article_id = ?", (article["article_id"],))
        deleted = cursor.rowcount
        rows = [(c.chunk_id, article["article_id"], article["revision_id"], chunk_config,
                 c.ordinal, c.char_start, c.char_end, c.token_count, c.text, check_vector(v),
                 embedding_config) for c, v in zip(chunks, vectors, strict=True)]
        for start in range(0, len(rows), batch_size):
            cursor.executemany(INSERT, rows[start:start + batch_size])
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
    return deleted


def record_config(connection, chunk_config, embedding_config, record):
    cursor = connection.cursor()
    cursor.execute("INSERT IGNORE INTO embedding_configs (embedding_config, chunk_config, "
                   "config_json) VALUES (?, ?, ?)",
                   (embedding_config, chunk_config, json.dumps(record, sort_keys=True)))
    connection.commit()
    cursor.close()


def run(connection, embedder, subset="all", limit=None, batch_size=16, device="cpu",
        log=lambda message: None):
    """Chunk and embed articles; skip those already current. Returns a report dict."""
    began = time.perf_counter()
    chunk_config, embedding_config, record = configs(embedder.versions, device)
    record_config(connection, chunk_config, embedding_config, record)
    cursor = connection.cursor()
    query = "SELECT article_id, title, revision_id, text_sha256 FROM articles"
    if subset == "smoke":
        query += " WHERE is_smoke"
    query += " ORDER BY article_id" + (f" LIMIT {int(limit)}" if limit else "")
    cursor.execute(query)
    names = ("article_id", "title", "revision_id", "text_sha256")
    articles = [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
    cursor.execute("SELECT article_id, chunk_id, chunk_config, embedding_config FROM chunks")
    existing = {}
    for aid, cid, cconf, econf in cursor.fetchall():
        existing.setdefault(aid, set()).add((cid, cconf, econf))

    report = {"chunk_config": chunk_config, "embedding_config": embedding_config,
              "subset": subset, "articles": len(articles), "articles_embedded": 0,
              "articles_skipped": 0, "chunks_written": 0, "chunks_deleted": 0,
              "chunks_current": 0, "token_count_min": None, "token_count_max": None,
              "input_tokens_max": None, "chunks_over_size": 0, "embed_seconds": 0.0}
    lengths, inputs = [], []
    for position, article in enumerate(articles, 1):
        cursor.execute("SELECT text FROM articles WHERE article_id = ?", (article["article_id"],))
        article["text"] = cursor.fetchone()[0]
        chunks = chunk_article(article, embedder.tokenize, chunk_config, count=embedder.count)
        lengths += [c.token_count for c in chunks]
        report["chunks_over_size"] += sum(c.token_count > CHUNK_TOKENS for c in chunks)
        report["chunks_current"] += len(chunks)
        if is_current(existing.get(article["article_id"], set()), chunks, chunk_config,
                      embedding_config):
            report["articles_skipped"] += 1
            continue
        texts, input_lengths = model_inputs(article["title"], chunks, embedder.input_length)
        inputs += input_lengths
        started = time.perf_counter()
        vectors = []
        for start in range(0, len(texts), batch_size):
            vectors += embedder.embed(texts[start:start + batch_size])
        report["embed_seconds"] += time.perf_counter() - started
        report["chunks_deleted"] += write_article(connection, article, chunks, vectors,
                                                  chunk_config, embedding_config)
        report["chunks_written"] += len(chunks)
        report["articles_embedded"] += 1
        log(f"[{position}/{len(articles)}] {article['title']}: {len(chunks)} chunks")
    cursor.close()
    if lengths:
        report["token_count_min"], report["token_count_max"] = min(lengths), max(lengths)
    if inputs:
        report["input_tokens_max"] = max(inputs)
    report["embed_seconds"] = round(report["embed_seconds"], 2)
    report["total_seconds"] = round(time.perf_counter() - began, 2)
    return report


def status(connection, chunk_config=None, embedding_config=None):
    """Chunk counts by configuration and article coverage of the given configuration."""
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*), COALESCE(SUM(is_smoke), 0) FROM articles")
    articles, smoke = cursor.fetchone()
    cursor.execute("SELECT c.chunk_config, c.embedding_config, COUNT(*), "
                   "COUNT(DISTINCT c.article_id), MIN(c.token_count), MAX(c.token_count) "
                   "FROM chunks c GROUP BY c.chunk_config, c.embedding_config")
    groups = [dict(zip(("chunk_config", "embedding_config", "chunks", "articles",
                        "token_count_min", "token_count_max"), row, strict=True))
              for row in cursor.fetchall()]
    cursor.close()
    active = [g for g in groups if (g["chunk_config"], g["embedding_config"])
              == (chunk_config, embedding_config)]
    return {"articles": articles, "smoke_articles": int(smoke),
            "active_chunk_config": chunk_config, "active_embedding_config": embedding_config,
            "covered_articles": active[0]["articles"] if active else 0,
            "active_chunks": active[0]["chunks"] if active else 0,
            "stale_chunks": sum(g["chunks"] for g in groups if g not in active),
            "by_config": groups}


def installed_versions():
    from importlib.metadata import version

    return {name: version(name) for name in ("torch", "transformers", "tokenizers")}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("run", "status"))
    parser.add_argument("--subset", choices=("all", "smoke"), default="all")
    parser.add_argument("--limit", type=int, help="first N articles by ID (smoke batches)")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", default="cpu", help="torch device; part of the config hash")
    args = parser.parse_args()
    from citehop.db import connect  # lazy so unit tests need no driver

    try:
        with connect() as connection:
            if args.command == "status":
                chunk_config, embedding_config, _ = configs(installed_versions(), args.device)
                result = status(connection, chunk_config, embedding_config)
            else:
                result = run(connection, Embedder(args.device), args.subset, args.limit,
                             args.batch_size, args.device,
                             log=lambda message: print(message, file=sys.stderr))
                result["status"] = status(connection, result["chunk_config"],
                                          result["embedding_config"])
    except ImportError as exc:  # includes PackageNotFoundError from installed_versions()
        print(f"ML dependencies missing ({exc}); run `make venv-ml`", file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
