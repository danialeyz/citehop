"""FastAPI application: thin, validated routes over citehop package logic.

Every handler is a plain `def`, so FastAPI runs the blocking MariaDB, Neo4j, embedding, and
generation calls in its thread pool instead of on the event loop. One generation runs at a
time per process; a second request gets HTTP 429 immediately and is never queued or retried.
Error bodies carry a stable code and a fixed message, never exception text, hosts, or paths.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from contextlib import ExitStack, contextmanager
from dataclasses import asdict
from typing import Annotated

import mariadb
from fastapi import APIRouter, Depends, FastAPI, Path, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from citehop import library, rag, runs
from citehop import search as retrieval
from citehop.api.schemas import (
    AnswerRequest,
    AnswerResponse,
    ArticleDetail,
    ArticleId,
    ArticlePage,
    CorpusStats,
    ErrorBody,
    GraphPath,
    GraphStatusOut,
    Health,
    Neighborhood,
    RunDetail,
    RunList,
    RunManifest,
    SearchFilters,
    SearchRequest,
    SearchResponse,
    Stats,
    TitleFilter,
)
from citehop.graph.source import read_corpus_version
from citehop.graph.store import GraphNotFound, GraphNotReady, GraphTimeout
from citehop.health import service_status

log = logging.getLogger("citehop.api")


class ApiError(Exception):
    def __init__(self, status_code: int, error: str, message: str, **extra):
        super().__init__(message)
        self.status_code, self.body = status_code, ErrorBody(error=error, message=message,
                                                              **extra)


def errors(*codes: int) -> dict:
    return {code: {"model": ErrorBody} for code in codes}


# --- dependencies (overridden in tests) ----------------------------------------------------

def get_db() -> Callable:
    """Context-manager factory for one MariaDB connection; opened only where needed."""
    from citehop.db import connect

    return connect


_graph = None
_graph_lock = threading.Lock()


def get_graph():
    """One GraphQueries (driver + cached source version) per process; None if unconfigured."""
    global _graph
    with _graph_lock:
        if _graph is None:
            from citehop.db import graph_driver
            from citehop.graph.__main__ import source_version
            from citehop.graph.queries import GraphQueries

            try:
                _graph = GraphQueries(graph_driver(), source_version)
            except Exception:
                log.exception("graph driver could not be created")
                return None
        return _graph


def get_embedder() -> Callable:
    """Returns the loader, so keyword search never loads the model."""
    return retrieval.default_embedder


def get_generator():
    return rag.OllamaGenerator()


_embed_lock = threading.Lock()  # one model forward pass at a time; also guards lazy loading
_generation_slot = threading.BoundedSemaphore(1)


def ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 1)


@contextmanager
def db_session(db):
    with ExitStack() as stack:
        try:
            connection = stack.enter_context(db())
        except Exception as exc:  # unreachable, misconfigured, or missing credentials
            log.warning("MariaDB connection failed: %s", type(exc).__name__)
            raise ApiError(503, "mariadb_unavailable", "MariaDB is unavailable.") from exc
        yield connection


# --- graph status helpers ------------------------------------------------------------------

SAFE_GRAPH_DETAIL = {
    "graph never imported": "Graph never imported; run `make graph-import`.",
    "MariaDB source version unavailable": "MariaDB corpus version unavailable.",
    "MariaDB corpus changed; rerun the import": "MariaDB corpus changed; rerun the import.",
    "import in progress or interrupted; rerun the import":
        "Import in progress or interrupted; rerun the import.",
}


def graph_status_out(status) -> GraphStatusOut:
    detail = status.detail
    if detail is not None:
        if detail in SAFE_GRAPH_DETAIL:
            detail = SAFE_GRAPH_DETAIL[detail]
        elif detail.startswith("last import failed"):
            detail = "Last import failed; rerun the import."
        else:  # driver/server text may name hosts or credentials
            detail = "Neo4j is unavailable."
    return GraphStatusOut(status=status.status, source_version=status.source_version,
                          imported_version=status.imported_version,
                          imported_at=status.imported_at, counts=status.counts, detail=detail)


UNAVAILABLE_GRAPH = GraphStatusOut(status="unavailable", source_version=None,
                                   imported_version=None, imported_at=None, counts=None,
                                   detail="Neo4j is unavailable.")


def current_graph_status(graph) -> GraphStatusOut:
    if graph is None:
        return UNAVAILABLE_GRAPH
    try:
        return graph_status_out(graph.status())
    except Exception:
        log.exception("graph status failed")
        return UNAVAILABLE_GRAPH


def graph_call(graph, operation):
    if graph is None:
        raise ApiError(503, "graph_unavailable", "The graph service is unavailable.",
                       graph=UNAVAILABLE_GRAPH)
    try:
        return operation(graph)
    except GraphNotReady as exc:
        status = graph_status_out(exc.status)
        if status.status == "unavailable":
            raise ApiError(503, "graph_unavailable",
                           status.detail or "The graph service is unavailable.",
                           graph=status) from exc
        raise ApiError(409, f"graph_{status.status}",
                       f"The graph is {status.status}; traversal is disabled until it matches "
                       "the MariaDB corpus.", graph=status) from exc
    except GraphNotFound as exc:
        raise ApiError(404, "not_found", "Article is not in the imported graph.") from exc
    except GraphTimeout as exc:
        raise ApiError(504, "graph_timeout", "The graph query exceeded its time limit.") from exc
    except ValueError as exc:
        raise ApiError(422, "invalid_request", str(exc)) from exc
    except Exception as exc:  # GraphUnavailable, driver and server errors
        log.exception("graph query failed")
        raise ApiError(503, "graph_unavailable", "The graph service is unavailable.",
                       graph=current_graph_status(graph)) from exc


# --- routes --------------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1")
Db = Annotated[Callable, Depends(get_db)]


@router.get("/health", response_model=Health)
def health():
    # HTTP 200 means the API is alive; readiness is explicit per service.
    return Health(status="ok", services=service_status())


@router.post("/search", response_model=SearchResponse, responses=errors(422, 503))
def search(body: SearchRequest, db: Db, embedder: Annotated[Callable, Depends(get_embedder)]):
    started = time.perf_counter()
    filters = body.filters.model_dump(exclude_none=True)
    try:
        query, filters = retrieval.validate(body.query, body.method, filters, body.k)
    except ValueError as exc:
        raise ApiError(422, "invalid_request", str(exc)) from exc
    vector = config = embedding_ms = None
    if body.method != "keyword":
        try:
            with _embed_lock:
                embed_query, config = embedder()
                embed_started = time.perf_counter()
                vector = embed_query(query)
                embedding_ms = ms(embed_started)
        except retrieval.EmbedderUnavailable as exc:
            raise ApiError(503, "embedder_unavailable",
                           "Vector search needs the embedding model (ml extra).") from exc
    with db_session(db) as conn:
        version = read_corpus_version(conn)
        retrieval_started = time.perf_counter()
        try:
            hits = retrieval.search(query, body.method, filters, body.k, connection=conn,
                                    query_vector=vector, embedding_config=config)
        except ValueError as exc:
            raise ApiError(409, "embedding_mismatch", str(exc)) from exc
        retrieval_ms = ms(retrieval_started)
    return SearchResponse(
        query=query, method=body.method, k=body.k, filters=SearchFilters(**filters),
        corpus_version=version, embedding_config=config,
        hits=[asdict(h) for h in hits],
        timings={"embedding_ms": embedding_ms, "retrieval_ms": retrieval_ms,
                 "total_ms": ms(started)},
    )


@router.post("/answer", response_model=AnswerResponse, responses=errors(404, 409, 422, 429, 503))
def answer(body: AnswerRequest, db: Db,
           generator: Annotated[object, Depends(get_generator)]):
    """Answer from stored passages only. Status `provider_error` keeps the resolved sources."""
    if not _generation_slot.acquire(blocking=False):
        raise ApiError(429, "generation_busy",
                       "Another answer is being generated; try again when it finishes.")
    try:
        with db_session(db) as conn:  # released before the (slow) generation call
            current = read_corpus_version(conn)
            if body.corpus_version != current:
                raise ApiError(409, "stale_context",
                               "The corpus changed since this search; search again.",
                               current_corpus_version=current)
            hits, missing = library.resolve_chunks(conn, body.chunk_ids)
        if missing:
            raise ApiError(404, "unknown_chunks", "Some chunk IDs are not in the current corpus.",
                           missing_chunk_ids=missing, current_corpus_version=current)
        try:
            result = rag.answer(body.question, hits, generator=generator)
        except ValueError as exc:
            raise ApiError(422, "invalid_request", str(exc)) from exc
    finally:
        _generation_slot.release()
    reason = result.reason
    if result.status == rag.PROVIDER_ERROR:
        log.warning("generation failed: %s", reason)
        reason = "The answer generator is unavailable; the sources are still valid."
    return AnswerResponse(
        status=result.status, text=result.text, citations=result.citations,
        citation_map={label: s.chunk_id for label, s in result.citation_map.items()},
        sources=[{k: getattr(s, k) for k in ("label", "chunk_id", "article_id", "title",
                                              "source_url", "passage", "rank")}
                 for s in result.sources],
        reason=reason, omitted=result.omitted, model=result.model,
        prompt_version=result.prompt_version, usage=result.usage,
        generation_ms=result.generation_ms, truncated=result.truncated, corpus_version=current,
    )


@router.get("/articles", response_model=ArticlePage, responses=errors(422, 503))
def articles(db: Db, title: Annotated[TitleFilter | None, Query()] = None,
             category: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
             page: Annotated[int, Query(ge=1, le=10_000)] = 1,
             page_size: Annotated[int, Query(ge=1, le=library.MAX_PAGE_SIZE)] = 20):
    with db_session(db) as conn:
        return library.list_articles(conn, title=(title or "").strip() or None,
                                     category=category, page=page, page_size=page_size)


@router.get("/articles/{article_id}", response_model=ArticleDetail, responses=errors(404, 422, 503))
def article(article_id: Annotated[int, Path(ge=1, le=4_294_967_295)], db: Db,
            passage_page: Annotated[int, Query(ge=1, le=10_000)] = 1,
            passage_page_size: Annotated[int, Query(ge=1,
                                                    le=library.MAX_PASSAGE_PAGE_SIZE)] = 20):
    with db_session(db) as conn:
        detail = library.article_detail(conn, article_id, passage_page=passage_page,
                                        passage_page_size=passage_page_size)
    if detail is None:
        raise ApiError(404, "not_found", "Article not found.")
    return detail


Graph = Annotated[object, Depends(get_graph)]


@router.get("/graph/status", response_model=GraphStatusOut)
def graph_status(graph: Graph):
    """Always HTTP 200; `status` says whether traversal is available."""
    return current_graph_status(graph)


@router.get("/graph/neighborhood", response_model=Neighborhood,
            responses=errors(404, 409, 422, 503, 504))
def graph_neighborhood(
    graph: Graph, article_id: Annotated[ArticleId, Query()],
    hops: Annotated[int, Query(ge=1, le=2)] = 1,
    max_nodes: Annotated[int, Query(ge=1, le=100)] = 50,
    max_edges: Annotated[int, Query(ge=1, le=200)] = 100,
    rel_types: Annotated[list[str] | None, Query(
        description="LINKS_TO and/or IN_CATEGORY; default both")] = None,
):
    allowed = ("LINKS_TO", "IN_CATEGORY")
    types = tuple(rel_types or allowed)
    if not set(types) <= set(allowed):
        raise ApiError(422, "invalid_request", "rel_types must be LINKS_TO and/or IN_CATEGORY")
    result = graph_call(graph, lambda g: g.neighborhood(
        article_id, hops=hops, max_nodes=max_nodes, max_edges=max_edges, rel_types=types))
    return {**result, "status": "ready"}


@router.get("/graph/path", response_model=GraphPath, responses=errors(404, 409, 422, 503, 504))
def graph_path(graph: Graph, source_id: Annotated[ArticleId, Query()],
               target_id: Annotated[ArticleId, Query()],
               directed: Annotated[bool, Query(description="false = labeled undirected mode")]
               = True):
    result = graph_call(graph, lambda g: g.path(source_id, target_id, directed=directed))
    return {**result, "status": "ready"}


@router.get("/stats", response_model=Stats, responses=errors(503))
def stats(db: Db, graph: Graph):
    with db_session(db) as conn:
        corpus = CorpusStats(**library.corpus_stats(conn))
    return Stats(corpus=corpus, graph=current_graph_status(graph))


RunId = Annotated[str, Path(pattern=runs.RUN_ID.pattern, max_length=100)]


def check_manifest(manifest: dict) -> None:
    """Reject a manifest the RunManifest response model cannot serialize, so one bad run is
    reported as malformed instead of failing the whole response."""
    try:
        RunManifest.model_validate(manifest)
    except ValidationError as exc:
        first = exc.errors()[0]
        field = ".".join(str(p) for p in first["loc"]) or "manifest"
        raise runs.MalformedRun(f"manifest.json field {field}: {first['msg']}") from exc


def run_call(operation):
    try:
        return operation()
    except runs.RunNotFound as exc:
        raise ApiError(404, "run_not_found", "No saved run with this ID.") from exc
    except runs.MalformedRun as exc:
        raise ApiError(500, "malformed_run", f"Saved run is malformed: {exc}") from exc


@router.get("/runs", response_model=RunList, response_model_by_alias=True)
def list_runs():
    valid, invalid = runs.list_runs(check=check_manifest)
    return {"runs": valid, "invalid": invalid}


@router.get("/runs/{run_id}", response_model=RunDetail, response_model_by_alias=True,
            responses=errors(404, 422, 500))
def get_run(run_id: RunId):
    """Manifest, flat per-question rows (the CSV columns), and answers prepared for review."""
    return run_call(lambda: runs.load_run(run_id, check=check_manifest))


@router.get("/runs/{run_id}/export", response_class=Response, responses={
    200: {"content": {"text/csv": {"schema": {"type": "string"}}},
          "description": f"Columns: {', '.join(runs.CSV_COLUMNS)}"},
    **errors(404, 422, 500)})
def export_run(run_id: RunId):
    body = run_call(lambda: runs.export_csv(run_id, check=check_manifest))
    return Response(body, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{run_id}.csv"'})


# --- application ---------------------------------------------------------------------------

app = FastAPI(title="CiteHop", version="0.1.0")
app.include_router(router)


def error_response(body: ErrorBody, status_code: int) -> JSONResponse:
    # Drop only absent top-level extras; a nested `graph` status keeps its null fields.
    content = {k: v for k, v in body.model_dump().items() if v is not None}
    return JSONResponse(content, status_code=status_code)


@app.exception_handler(ApiError)
def api_error(_: Request, exc: ApiError):
    return error_response(exc.body, exc.status_code)


@app.exception_handler(mariadb.OperationalError)
@app.exception_handler(mariadb.InterfaceError)
def mariadb_down(_: Request, exc: Exception):
    log.warning("MariaDB failed during a request: %s", type(exc).__name__)
    body = ErrorBody(error="mariadb_unavailable", message="MariaDB is unavailable.")
    return error_response(body, 503)


@app.exception_handler(Exception)
def unexpected(_: Request, exc: Exception):
    log.exception("unhandled API error", exc_info=exc)
    body = ErrorBody(error="internal_error", message="Unexpected server error.")
    return error_response(body, 500)
