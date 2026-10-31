"""Deterministic token-window chunking with the embedding model's tokenizer.

Windows hold at most `chunk_tokens` tokens and start `overlap_tokens` before the previous
window's end. Boundaries snap to word starts (the tokenizer's `word_ids`), so a chunk never
starts or ends inside a word and re-tokenizing the chunk text yields the same tokens. A
single word longer than a whole window is split at token boundaries instead.

The tokenizer is any callable `tokenize(text) -> [(char_start, char_end, word_id), ...]`
(no special tokens), which keeps this module free of model dependencies for unit tests.
"""

import hashlib
import json
from bisect import bisect_right
from dataclasses import dataclass

CHUNK_TOKENS = 300
OVERLAP_TOKENS = 50
BOUNDARY_RULE = "word-start-snap-v1"


def config_hash(config):
    """SHA-256 of canonical JSON; equal settings always produce equal IDs."""
    payload = json.dumps(config, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    ordinal: int
    char_start: int
    char_end: int
    token_count: int
    text: str


def windows(tokens, chunk_tokens=CHUNK_TOKENS, overlap_tokens=OVERLAP_TOKENS):
    """Token index ranges [start, end) covering all tokens with word-aligned overlap."""
    if not 0 <= overlap_tokens < chunk_tokens:
        raise ValueError("overlap must be >= 0 and smaller than the chunk size")
    n = len(tokens)
    starts = [0] + [i for i in range(1, n) if tokens[i][2] != tokens[i - 1][2]]

    def word_start_at_or_before(index):
        return starts[bisect_right(starts, index) - 1]

    result, start = [], 0
    while n:
        end = min(start + chunk_tokens, n)
        if end < n and word_start_at_or_before(end) > start:
            end = word_start_at_or_before(end)  # else one word fills the window: token cut
        result.append((start, end))
        if end == n:
            break
        # Latest word start at or before end - overlap, so the overlap is never below the
        # nominal size; it must still advance past `start` to guarantee progress.
        target = end - overlap_tokens
        snapped = word_start_at_or_before(target)
        start = snapped if snapped > start else max(start + 1, target)
    return result


def chunk_id(article_id, revision_id, text_sha256, chunk_config, ordinal):
    """Stable ID: same article text and chunking configuration give the same IDs."""
    key = f"{article_id}:{revision_id}:{text_sha256}:{chunk_config}:{ordinal}"
    return hashlib.sha256(key.encode()).hexdigest()


def chunk_article(article, tokenize, chunk_config, chunk_tokens=CHUNK_TOKENS,
                  overlap_tokens=OVERLAP_TOKENS, count=None):
    """Chunks of one article dict (article_id, revision_id, text_sha256, text).

    `count(text)` re-tokenizes each chunk to record its actual length (defaults to
    len(tokenize(text))). Empty or whitespace-only text yields no chunks.
    """
    text = article["text"]
    tokens = tokenize(text)
    count = count or (lambda value: len(tokenize(value)))
    chunks = []
    for ordinal, (start, end) in enumerate(windows(tokens, chunk_tokens, overlap_tokens)):
        char_start, char_end = tokens[start][0], tokens[end - 1][1]
        passage = text[char_start:char_end]
        chunks.append(Chunk(
            chunk_id(article["article_id"], article["revision_id"], article["text_sha256"],
                     chunk_config, ordinal),
            ordinal, char_start, char_end, count(passage), passage))
    return chunks
