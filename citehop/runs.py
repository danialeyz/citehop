"""Read C08 evaluation runs (docs/EVALUATION.md) for the API and export one run as CSV.

    results/runs/<run_id>/manifest.json     schema citehop-eval-v1 (required)
    results/runs/<run_id>/retrieval.jsonl   one record per question repetition, methods nested
    results/runs/<run_id>/answers.json      {"run_id", "instructions", "answers": [...]}; optional

File names come from the manifest's `files` block and must be plain names inside the run
directory. Run IDs are validated against RUN_ID and resolved inside the runs directory, so a
request can never name an arbitrary filesystem path. Saved values are passed through
unchanged: absent values stay null and are never filled with zeros.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
from pathlib import Path

from citehop.evaluate import SCHEMA

RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
FILE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
DEFAULT_FILES = {"retrieval": "retrieval.jsonl", "answers": "answers.json"}
MAX_FILE_BYTES = 20 * 1024 * 1024
TOP_ARTICLES = 5
CSV_COLUMNS = (
    "question_id", "split", "repetition", "method", "answerable", "filtered", "recall_at_5",
    "articles_found", "exhausted", "cutoff_reached", "top_article_ids", "embedding_ms",
    "retrieval_ms", "answer_status", "generation_ms", "review_status",
)
ANSWER_FIELDS = ("question_id", "split", "question", "answerable", "expected_answer", "status",
                 "text", "citations", "reason", "model", "prompt_version", "generation_ms",
                 "truncated", "review")


class RunNotFound(LookupError):
    pass


class MalformedRun(ValueError):
    """A saved run exists but does not match the C08 layout (message is path-free)."""


def runs_dir() -> Path:
    configured = os.getenv("CITEHOP_RUNS_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "results" / "runs"


def run_path(run_id: str, root: Path | None = None) -> Path:
    if not isinstance(run_id, str) or not RUN_ID.match(run_id) or ".." in run_id:
        raise RunNotFound(run_id)
    root = (root or runs_dir()).resolve()
    path = (root / run_id).resolve()
    if path.parent != root or not (path / "manifest.json").is_file():
        raise RunNotFound(run_id)
    return path


def _text(path: Path) -> str:
    if path.stat().st_size > MAX_FILE_BYTES:
        raise MalformedRun(f"{path.name} exceeds {MAX_FILE_BYTES} bytes")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise MalformedRun(f"{path.name} is not UTF-8") from exc


def _json(path: Path):
    try:
        return json.loads(_text(path))
    except json.JSONDecodeError as exc:
        raise MalformedRun(f"{path.name} is not valid JSON") from exc


def load_manifest(run_id: str, root: Path | None = None, check=None) -> dict:
    """The validated manifest. `check(manifest)` may add stricter validation (the API passes
    its response model) and must raise MalformedRun for a manifest it rejects."""
    manifest = _json(run_path(run_id, root) / "manifest.json")
    if not isinstance(manifest, dict):
        raise MalformedRun("manifest.json must be an object")
    if manifest.get("schema") != SCHEMA:
        raise MalformedRun(f"unsupported schema (expected {SCHEMA})")
    if manifest.get("run_id") != run_id:
        raise MalformedRun("manifest run_id does not match its directory")
    if not isinstance(manifest.get("created_at"), str):
        raise MalformedRun("manifest.json lacks created_at")
    splits = manifest.get("splits")
    if not isinstance(splits, dict) or not splits:
        raise MalformedRun("manifest.json lacks splits")
    corpus = manifest.get("corpus")
    if not isinstance(corpus, dict) or not isinstance(corpus.get("id"), str):
        raise MalformedRun("manifest.json lacks corpus.id")
    files = manifest.get("files") or {}
    if not isinstance(files, dict):
        raise MalformedRun("manifest files must be an object")
    for key, name in files.items():
        if key in DEFAULT_FILES and not (isinstance(name, str) and FILE_NAME.match(name)):
            raise MalformedRun(f"manifest files.{key} is not a plain file name")
    if check is not None:
        check(manifest)
    return manifest


def _file(run_id, root, manifest, key) -> Path:
    name = (manifest.get("files") or {}).get(key, DEFAULT_FILES[key])
    return run_path(run_id, root) / name


def load_retrieval(run_id: str, root: Path | None = None, manifest=None) -> list[dict]:
    manifest = manifest or load_manifest(run_id, root)
    path = _file(run_id, root, manifest, "retrieval")
    if not path.is_file():
        raise MalformedRun(f"{path.name} is missing")
    records = []
    for number, line in enumerate(_text(path).splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MalformedRun(f"{path.name} line {number} is not valid JSON") from exc
        if not (isinstance(record, dict) and isinstance(record.get("question_id"), str)
                and isinstance(record.get("methods"), dict)):
            raise MalformedRun(f"{path.name} line {number} lacks question_id or methods")
        records.append(record)
    return records


def load_answers(run_id: str, root: Path | None = None, manifest=None) -> list[dict]:
    """Saved answers, or [] for a run evaluated without generation."""
    manifest = manifest or load_manifest(run_id, root)
    path = _file(run_id, root, manifest, "answers")
    if not path.is_file():
        return []
    data = _json(path)
    if not isinstance(data, dict) or not isinstance(data.get("answers"), list):
        raise MalformedRun(f"{path.name} must be an object with an answers list")
    if data.get("run_id") not in (None, run_id):
        raise MalformedRun(f"{path.name} belongs to another run")
    if not all(isinstance(a, dict) and isinstance(a.get("question_id"), str)
               for a in data["answers"]):
        raise MalformedRun(f"{path.name} has an answer without question_id")
    return data["answers"]


def list_runs(root: Path | None = None, check=None) -> tuple[list[dict], list[dict]]:
    """(valid manifests newest first, [{run_id, error}] for unreadable runs)."""
    root = root or runs_dir()
    valid, invalid = [], []
    if not root.is_dir():
        return valid, invalid
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or not RUN_ID.match(entry.name):
            continue
        if not (entry / "manifest.json").is_file():
            continue
        try:
            valid.append(load_manifest(entry.name, root, check))
        except MalformedRun as exc:
            invalid.append({"run_id": entry.name, "error": str(exc)})
    valid.sort(key=lambda m: (m["created_at"], m["run_id"]), reverse=True)
    return valid, invalid


def rows(records: list[dict], answers: list[dict]) -> list[dict]:
    """One flat row per question, repetition, and method; answers join on all three."""
    by_key = {}
    for a in answers:
        retrieval = a.get("retrieval") or {}
        by_key[(a["question_id"], retrieval.get("method"), retrieval.get("repetition"))] = a
    out = []
    for record in records:
        for method, result in sorted(record["methods"].items()):
            result = result if isinstance(result, dict) else {}
            ranking = result.get("article_ranking") or []
            answer = by_key.get((record["question_id"], method, record.get("repetition")))
            out.append({
                "question_id": record["question_id"],
                "split": record.get("split"),
                "repetition": record.get("repetition"),
                "method": method,
                "answerable": record.get("answerable"),
                "filtered": record.get("filtered"),
                "recall_at_5": result.get("recall_at_5"),
                "articles_found": result.get("articles_found"),
                "exhausted": result.get("exhausted"),
                "cutoff_reached": result.get("cutoff_reached"),
                "top_article_ids": [r.get("article_id") for r in ranking[:TOP_ARTICLES]
                                    if isinstance(r, dict)],
                # keyword search embeds nothing; the record's embedding feeds vector methods
                "embedding_ms": None if method == "keyword" else record.get("embedding_ms"),
                "retrieval_ms": result.get("retrieval_ms"),
                "answer_status": answer.get("status") if answer else None,
                "generation_ms": answer.get("generation_ms") if answer else None,
                "review_status": (answer.get("review") or {}).get("status") if answer else None,
            })
    return out


def compact_answer(answer: dict) -> dict:
    out = {k: answer.get(k) for k in ANSWER_FIELDS}
    out["retrieval"] = answer.get("retrieval")
    out["sources"] = [{k: s.get(k) for k in ("label", "chunk_id", "article_id", "title",
                                             "source_url")}
                      for s in answer.get("sources") or [] if isinstance(s, dict)]
    return out


def load_run(run_id: str, root: Path | None = None, check=None) -> dict:
    manifest = load_manifest(run_id, root, check)
    records = load_retrieval(run_id, root, manifest)
    answers = load_answers(run_id, root, manifest)
    flat = rows(records, answers)
    return {"manifest": manifest, "rows": flat, "answers": [compact_answer(a) for a in answers],
            "counts": {"records": len(records), "rows": len(flat), "answers": len(answers),
                       "reviewed_answers": sum(1 for a in answers
                                               if (a.get("review") or {}).get("status")
                                               not in (None, "unreviewed"))}}


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ";".join(_cell(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, separators=(",", ":"))
    text = str(value)
    # Neutralize spreadsheet formula injection from saved text.
    return "'" + text if text[:1] in ("=", "+", "-", "@") and not _is_number(text) else text


def _is_number(text):
    try:
        float(text)
    except ValueError:
        return False
    return True


def export_csv(run_id: str, root: Path | None = None, check=None) -> str:
    """Fixed CSV_COLUMNS, one row per question/repetition/method; missing values are empty."""
    manifest = load_manifest(run_id, root, check)
    flat = rows(load_retrieval(run_id, root, manifest), load_answers(run_id, root, manifest))
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for row in flat:
        writer.writerow(_cell(row[column]) for column in CSV_COLUMNS)
    return out.getvalue()
