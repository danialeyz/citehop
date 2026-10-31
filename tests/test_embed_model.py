"""Real BGE tokenizer/model checks. Needs the `ml` extra and the cached pinned model."""

import math

import pytest

from citehop.chunking import chunk_article, windows
from citehop.embed import DIMENSIONS, MAX_INPUT_TOKENS, ModelLimitError, model_inputs

pytestmark = pytest.mark.model
pytest.importorskip("transformers")

TEXT = ("Backpropagation computes the gradient of a loss function with respect to the "
        "weights of a multilayer perceptron, e.g. GPT-4-style transformers (1986–2024). ") * 40


@pytest.fixture(scope="module")
def embedder():
    from citehop.embed import Embedder

    try:
        return Embedder()
    except OSError as exc:  # not downloaded and no network
        pytest.skip(f"pinned model unavailable: {exc}")


def test_real_chunks_retokenize_to_their_window_length(embedder):
    article = {"article_id": 1, "revision_id": 1, "text_sha256": "s" * 64, "text": TEXT}
    tokens = embedder.tokenize(TEXT)
    spans = windows(tokens)
    chunks = chunk_article(article, embedder.tokenize, "c", count=embedder.count)
    assert len(chunks) > 2 and all(c.token_count <= 300 for c in chunks)
    assert [c.token_count for c in chunks] == [end - start for start, end in spans]
    for (_, end), (start, _) in zip(spans, spans[1:], strict=False):
        assert 50 <= end - start < 60
    _, lengths = model_inputs("Backpropagation", chunks, embedder.input_length)
    assert max(lengths) <= 300 + 2 + embedder.count("Backpropagation\n\n")


def test_real_model_limit_is_enforced_not_truncated(embedder):
    article = {"article_id": 1, "revision_id": 1, "text_sha256": "s" * 64, "text": TEXT}
    chunks = chunk_article(article, embedder.tokenize, "c", count=embedder.count)
    with pytest.raises(ModelLimitError):
        model_inputs("word " * 250, chunks, embedder.input_length)
    with pytest.raises(ModelLimitError):
        embedder.embed(["token " * MAX_INPUT_TOKENS])


def test_vectors_are_finite_normalized_and_deterministic(embedder):
    first = embedder.embed(["Perceptron\n\nThe perceptron is a linear classifier.", "x"])
    again = embedder.embed(["Perceptron\n\nThe perceptron is a linear classifier.", "x"])
    assert first == again and len(first[0]) == DIMENSIONS
    assert all(math.isfinite(v) for v in first[0])
    assert math.isclose(sum(v * v for v in first[0]), 1.0, rel_tol=1e-5)
    query = embedder.embed_query("what is a perceptron")
    assert len(query) == DIMENSIONS
