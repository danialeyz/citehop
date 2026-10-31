"""Chunking and embedding logic with a fake tokenizer and embedder (no model, no database)."""

import re

import pytest

from citehop.chunking import chunk_article, chunk_id, windows
from citehop.embed import (
    MAX_INPUT_TOKENS,
    ModelLimitError,
    check_vector,
    configs,
    is_current,
    model_inputs,
)

VERSIONS = {"torch": "t", "transformers": "x", "tokenizers": "k"}


def tokenize(text):
    """Words and punctuation; words split into 4-character pieces sharing one word ID."""
    tokens = []
    for word, match in enumerate(re.finditer(r"\w+|[^\w\s]", text)):
        for start in range(match.start(), match.end(), 4):
            tokens.append((start, min(start + 4, match.end()), word))
    return tokens


def article(text, aid=7, revision=70, sha="s" * 64):
    return {"article_id": aid, "revision_id": revision, "text_sha256": sha, "text": text}


def words(n):
    return " ".join(f"w{i}" for i in range(n))


def test_empty_and_whitespace_text_yield_no_chunks():
    assert chunk_article(article(""), tokenize, "c") == []
    assert chunk_article(article(" \n\t "), tokenize, "c") == []
    assert windows([]) == []


def test_short_text_is_one_chunk_with_exact_span():
    text = "  Short text, here.  "
    [chunk] = chunk_article(article(text), tokenize, "c")
    assert (chunk.ordinal, chunk.text, chunk.token_count) == (0, "Short text, here.", 6)
    assert text[chunk.char_start:chunk.char_end] == chunk.text


def test_windows_cover_all_tokens_with_nominal_overlap():
    tokens = tokenize(words(1000))  # one token per word
    spans = windows(tokens, 300, 50)
    assert spans[0] == (0, 300) and spans[-1][1] == len(tokens)
    for (start, end), (next_start, _) in zip(spans, spans[1:], strict=False):
        assert end - start == 300 and end - next_start == 50


def test_boundaries_snap_to_word_starts_and_overlap_is_at_least_nominal():
    text = " ".join("abcdefghij" if i % 7 == 0 else f"w{i}" for i in range(900))
    tokens = tokenize(text)
    spans = windows(tokens, 30, 5)
    for start, end in spans:
        assert end - start <= 30
        assert start == 0 or tokens[start][2] != tokens[start - 1][2]
        assert end == len(tokens) or tokens[end][2] != tokens[end - 1][2]
    for (_, end), (next_start, _) in zip(spans, spans[1:], strict=False):
        assert 5 <= end - next_start < 5 + 3  # longest word has three pieces
    chunks = chunk_article(article(text), tokenize, "c", 30, 5)
    assert all(c.token_count == e - s for c, (s, e) in zip(chunks, spans, strict=True))


def test_word_longer_than_window_is_cut_at_tokens_and_terminates():
    tokens = tokenize("x" * 400 + " tail")  # 100 pieces of one word, then one word
    spans = windows(tokens, 30, 5)
    assert spans[0] == (0, 30) and spans[-1][1] == len(tokens)
    assert all(end - start <= 30 for start, end in spans)


def test_invalid_overlap_is_rejected():
    with pytest.raises(ValueError):
        windows(tokenize("a b"), 10, 10)


def test_ids_are_stable_and_change_with_text_or_config():
    text = words(700)
    first = chunk_article(article(text), tokenize, "c")
    assert [c.chunk_id for c in first] == [c.chunk_id for c in
                                           chunk_article(article(text), tokenize, "c")]
    assert len({c.chunk_id for c in first}) == len(first) == 3
    assert all(len(c.chunk_id) == 64 for c in first)
    other_config = chunk_article(article(text), tokenize, "d")
    other_text = chunk_article(article(text, sha="t" * 64), tokenize, "c")
    other_revision = chunk_article(article(text, revision=71), tokenize, "c")
    for changed in (other_config, other_text, other_revision):
        assert not {c.chunk_id for c in changed} & {c.chunk_id for c in first}
    assert chunk_id(7, 70, "s" * 64, "c", 0) == first[0].chunk_id


def test_config_hashes_track_every_setting():
    base = configs(VERSIONS)
    assert configs(VERSIONS) == base
    assert configs(VERSIONS, chunk_tokens=200)[0] != base[0]
    assert configs(VERSIONS, overlap_tokens=40)[0] != base[0]
    assert configs({**VERSIONS, "tokenizers": "k2"})[0] != base[0]
    # Embedding-only changes keep the chunk hash but change the embedding hash.
    for changed in (configs(VERSIONS, device="mps"), configs({**VERSIONS, "torch": "t2"})):
        assert changed[0] == base[0] and changed[1] != base[1]
    record = base[2]["embedding"]
    assert record["model_revision"] and record["normalization"] == "l2"
    assert record["passage_format"] == "{title}\n\n{passage}" and record["truncation"] is False


def test_model_inputs_include_title_and_reject_overflow():
    chunks = chunk_article(article(words(10)), tokenize, "c")
    texts, lengths = model_inputs("Perceptron", chunks, lambda t: len(tokenize(t)) + 2)
    assert texts == ["Perceptron\n\n" + chunks[0].text] and lengths == [15]  # title: 3 pieces
    long_title = "T" * 4 * (MAX_INPUT_TOKENS - 10)  # title alone nearly fills the model limit
    with pytest.raises(ModelLimitError, match="exceed the model limit"):
        model_inputs(long_title, chunks, lambda t: len(tokenize(t)) + 2)


def test_is_current_requires_exact_ids_and_configs():
    chunks = chunk_article(article(words(700)), tokenize, "c")
    rows = {(c.chunk_id, "c", "e") for c in chunks}
    assert is_current(rows, chunks, "c", "e")
    assert not is_current(rows, chunks, "c", "e2")  # embedding settings changed
    assert not is_current(set(list(rows)[:-1]), chunks, "c", "e")  # interrupted/partial
    assert not is_current(rows | {("x" * 64, "old", "e")}, chunks, "c", "e")  # leftovers
    assert is_current(set(), [], "c", "e")


def test_check_vector_rejects_wrong_dimension_and_non_finite():
    assert check_vector([0.5] * 768).startswith("[0.5, ")
    for bad in ([0.0] * 767, [float("nan")] + [0.0] * 767, [float("inf")] * 768):
        with pytest.raises(ValueError):
            check_vector(bad)


def test_cli_reports_missing_ml_extra_instead_of_traceback(monkeypatch, capsys):
    from contextlib import contextmanager
    from importlib.metadata import PackageNotFoundError

    import citehop.db
    import citehop.embed as embed

    @contextmanager
    def connect():
        yield None

    def missing():
        raise PackageNotFoundError("torch")

    monkeypatch.setattr(citehop.db, "connect", connect)
    monkeypatch.setattr(embed, "installed_versions", missing)
    monkeypatch.setattr("sys.argv", ["citehop.embed", "status"])
    assert embed.main() == 1
    assert "make venv-ml" in capsys.readouterr().err
