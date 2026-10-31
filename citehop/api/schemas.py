"""Request/response models for the HTTP contract; the frontend types are generated from these."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from citehop.library import MAX_TITLE_FILTER_CHARS
from citehop.rag import MAX_PASSAGES, MAX_QUESTION_CHARS
from citehop.search import MAX_K, MAX_QUERY_CHARS

ChunkId = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$", description="64-char hex chunk ID")]
ArticleId = Annotated[int, Field(ge=1, le=4_294_967_295)]
GraphState = Literal["ready", "stale", "rebuilding", "unavailable"]
ServiceState = Literal["ready", "unavailable"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorBody(BaseModel):
    """Every non-2xx response except request-schema errors (FastAPI's 422 detail list)."""

    error: str = Field(description="Stable machine-readable code")
    message: str = Field(description="Safe, human-readable explanation")
    current_corpus_version: str | None = None
    missing_chunk_ids: list[str] | None = None
    graph: GraphStatusOut | None = None


class Health(BaseModel):
    status: Literal["ok"]
    services: dict[str, ServiceState]


# --- search -------------------------------------------------------------------------------

class SearchFilters(Strict):
    category: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    min_length_chars: Annotated[int, Field(ge=0)] | None = None
    max_length_chars: Annotated[int, Field(ge=0)] | None = None
    linked_from: ArticleId | None = Field(None, description="Only articles this article links to")


class SearchRequest(Strict):
    query: Annotated[str, Field(min_length=1, max_length=MAX_QUERY_CHARS)]
    method: Literal["keyword", "vector", "exact"] = "vector"
    filters: SearchFilters = Field(default_factory=SearchFilters)
    k: Annotated[int, Field(ge=1, le=MAX_K)] = 5

    @field_validator("query")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value


class SearchHit(BaseModel):
    chunk_id: str
    article_id: int
    title: str
    source_url: str
    passage: str
    rank: int
    score: float = Field(description="Method-specific; not comparable across methods")
    method: str


class SearchTimings(BaseModel):
    embedding_ms: float | None = Field(description="Query embedding; null for keyword search")
    retrieval_ms: float = Field(description="MariaDB query only")
    total_ms: float


class SearchResponse(BaseModel):
    query: str
    method: str
    k: int
    filters: SearchFilters = Field(description="Effective filters applied in SQL")
    corpus_version: str
    embedding_config: str | None = Field(description="Vector config searched; null for keyword")
    hits: list[SearchHit]
    timings: SearchTimings


# --- answer -------------------------------------------------------------------------------

class AnswerRequest(Strict):
    question: Annotated[str, Field(min_length=1, max_length=MAX_QUESTION_CHARS)]
    chunk_ids: Annotated[list[ChunkId], Field(min_length=1, max_length=MAX_PASSAGES)] = Field(
        description="Chunk IDs from a search response, in rank order; the server reads the text")
    corpus_version: Annotated[str, Field(min_length=1, max_length=64)] = Field(
        description="corpus_version of the search response the chunk IDs came from")

    @field_validator("question")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank")
        return value


class AnswerSource(BaseModel):
    label: str
    chunk_id: str
    article_id: int
    title: str
    source_url: str
    passage: str
    rank: int


class OmittedPassage(BaseModel):
    chunk_id: str | None
    article_id: int | None
    reason: str
    tokens: int | None = None


class AnswerUsage(BaseModel):
    context_tokens_estimated: int | None = None
    token_estimator: str | None = None
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None


class AnswerResponse(BaseModel):
    status: Literal["answered", "insufficient_evidence", "invalid_citations", "provider_error"]
    text: str | None = Field(description="Set only when status is answered; plain text")
    citations: list[str] = Field(description="Labels cited by the answer, in first-use order")
    citation_map: dict[str, str] = Field(description="Cited label -> chunk_id")
    sources: list[AnswerSource]
    reason: str | None
    omitted: list[OmittedPassage]
    model: str | None
    prompt_version: str
    usage: AnswerUsage
    generation_ms: float | None
    truncated: bool
    corpus_version: str


# --- articles -----------------------------------------------------------------------------

class ArticleSummary(BaseModel):
    article_id: int
    title: str
    source_url: str
    length_chars: int
    chunk_count: int
    categories: list[str]


class ArticlePage(BaseModel):
    items: list[ArticleSummary]
    total: int
    page: int
    page_size: int
    corpus_version: str


class Passage(BaseModel):
    chunk_id: str
    ordinal: int
    char_start: int
    char_end: int
    token_count: int
    text: str


class PassagePage(BaseModel):
    items: list[Passage]
    total: int
    page: int
    page_size: int
    chunk_config: str | None
    embedding_config: str | None


class LinkCounts(BaseModel):
    outgoing: int
    incoming: int


class ArticleDetail(BaseModel):
    article_id: int
    title: str
    revision_id: int
    revision_timestamp: str | None
    source_url: str
    revision_url: str
    length_chars: int
    is_smoke: bool
    license_url: str
    attribution: str
    categories: list[str]
    links: LinkCounts
    passages: PassagePage
    corpus_version: str


TitleFilter = Annotated[str, Field(max_length=MAX_TITLE_FILTER_CHARS)]


# --- graph --------------------------------------------------------------------------------

class GraphCounts(BaseModel):
    articles: int | None = None
    categories: int | None = None
    links: int | None = None
    memberships: int | None = None


class GraphStatusOut(BaseModel):
    status: GraphState
    source_version: str | None = Field(description="Current MariaDB corpus version")
    imported_version: str | None = Field(description="Corpus version imported into Neo4j")
    imported_at: str | None
    counts: GraphCounts | None
    detail: str | None


class ArticleNode(BaseModel):
    id: str
    kind: Literal["article"]
    article_id: int
    title: str
    source_url: str
    revision_id: int | None = None
    depth: int | None = None


class CategoryNode(BaseModel):
    id: str
    kind: Literal["category"]
    name: str
    depth: int


GraphNode = Annotated[ArticleNode | CategoryNode, Field(discriminator="kind")]


class GraphEdge(BaseModel):
    source: str
    type: Literal["LINKS_TO", "IN_CATEGORY"]
    target: str


class GraphLimits(BaseModel):
    max_nodes: int
    max_edges: int


class Neighborhood(BaseModel):
    seed: str
    graph_version: str
    status: GraphState
    hops: int
    rel_types: list[Literal["LINKS_TO", "IN_CATEGORY"]]
    limits: GraphLimits
    truncated: bool = Field(description="True when node or edge caps cut the result")
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphPath(BaseModel):
    source: str
    target: str
    directed: bool
    max_links: int
    graph_version: str
    status: GraphState
    found: bool
    message: str | None = Field(None, description='e.g. "No path within 3 links"')
    nodes: list[ArticleNode]
    edges: list[GraphEdge]


# --- stats --------------------------------------------------------------------------------

class EmbeddingCoverage(BaseModel):
    chunk_config: str
    embedding_config: str
    chunks: int
    articles_covered: int
    token_count_min: int | None
    token_count_max: int | None


class CorpusStats(BaseModel):
    corpus_version: str
    articles: int
    smoke_articles: int
    distinct_categories: int
    category_memberships: int
    article_links: int
    chunks: int
    embedding_configs: list[EmbeddingCoverage]


class Stats(BaseModel):
    corpus: CorpusStats = Field(description="Live MariaDB counts")
    graph: GraphStatusOut = Field(description="Neo4j projection, reported separately")


# --- runs ---------------------------------------------------------------------------------

class RunCorpus(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(description='MariaDB corpus version, e.g. "corpus:2"')
    version_id: int | None = None


class RunManifest(BaseModel):
    """C08 manifest (schema citehop-eval-v1). Core fields are typed; the rest (config,
    latency boundaries, hardware, warm-up, summary with denominators) is passed through as
    saved, with nulls kept as null."""

    model_config = ConfigDict(extra="allow")
    schema_: str = Field(alias="schema")
    run_id: str
    created_at: str
    status: str | None = None
    final_claims_allowed: bool | None = None
    splits: dict[str, int]
    corpus: RunCorpus
    config_id: str | None = None
    summary: dict[str, Any] | None = None


class InvalidRun(BaseModel):
    run_id: str
    error: str


class RunList(BaseModel):
    runs: list[RunManifest]
    invalid: list[InvalidRun] = Field(description="Run directories that could not be read")


class RunRow(BaseModel):
    """One question repetition and method; the CSV export has exactly these columns."""

    question_id: str
    split: str | None
    repetition: int | None
    method: str
    answerable: bool | None
    filtered: bool | None
    recall_at_5: float | None
    articles_found: int | None
    exhausted: bool | None
    cutoff_reached: bool | None
    top_article_ids: list[int]
    embedding_ms: float | None = Field(description="Null for keyword rows (no embedding)")
    retrieval_ms: float | None
    answer_status: str | None
    generation_ms: float | None
    review_status: str | None


class RunAnswerSource(BaseModel):
    label: str | None
    chunk_id: str | None
    article_id: int | None
    title: str | None
    source_url: str | None


class RunAnswerReview(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str | None = None
    grounded: bool | None = None
    citations_support: bool | None = None
    correct_abstention: bool | None = None
    reviewer: str | None = None
    reviewed_at: str | None = None


class RunAnswer(BaseModel):
    question_id: str
    split: str | None
    question: str | None
    answerable: bool | None
    expected_answer: str | None
    retrieval: dict[str, Any] | None
    status: str | None
    text: str | None
    citations: list[str] | None
    sources: list[RunAnswerSource]
    reason: str | None
    model: str | None
    prompt_version: str | None
    generation_ms: float | None
    truncated: bool | None
    review: RunAnswerReview | None


class RunCounts(BaseModel):
    records: int
    rows: int
    answers: int
    reviewed_answers: int


class RunDetail(BaseModel):
    manifest: RunManifest
    rows: list[RunRow]
    answers: list[RunAnswer]
    counts: RunCounts


ErrorBody.model_rebuild()

