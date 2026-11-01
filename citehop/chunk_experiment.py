"""S03: one chunk-size experiment, 200/50 against the 300/50 default, decided on dev only.

    python -m citehop.chunk_experiment embed            # both arms, from empty chunk tables
    python -m citehop.chunk_experiment dev [--rounds 3] # dev split only, arms alternate
    python -m citehop.chunk_experiment freeze           # apply the rule; write decision.json
    python -m citehop.chunk_experiment test             # one follow-up test run, chosen arm

Each arm lives in its own MariaDB database (ARMS[...]["database"], on the server in .env), so
the demo database and its 300/50 chunks are never touched. Both databases hold the same
pinned corpus; queries use the same model and the frozen questions. `freeze` refuses to run
once a test run exists, and `test` refuses to run before the decision is frozen or twice, so
test results cannot feed the choice. Output goes to results/experiments/s03-chunking/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from citehop.evaluate import latency

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "experiments" / "s03-chunking"
QUESTIONS = ROOT / "eval" / "questions.json"
BASELINE, CANDIDATE = "300-50", "200-50"
ARMS = {
    BASELINE: {"chunk_tokens": 300, "overlap_tokens": 50, "database": "citehop_s03_300"},
    CANDIDATE: {"chunk_tokens": 200, "overlap_tokens": 50, "database": "citehop_s03_200"},
}
DEV_ROUNDS = 3
# Written before the S03 dev runs; `freeze` copies it verbatim into decision.json.
RULE = ("Primary metric: dev vector (ANN) article Recall@5 over all answerable questions. "
        "Adopt 200/50 only if its primary metric is strictly higher than 300/50 and its dev "
        "keyword Recall@5 is not lower. Otherwise keep 300/50, the current default, which has "
        "fewer chunks to embed and store. Chunk count, embedding effort and latency are "
        "recorded but do not decide: one laptop, few samples. The test split is never used "
        "for the choice.")


def arm_dir(arm, root=OUT):
    return root / arm


def runs(arm, split, root=OUT):
    """Saved run directories of one arm and split, oldest first."""
    base = arm_dir(arm, root) / "runs"
    if not base.is_dir():
        return []
    found = []
    for path in sorted(base.iterdir()):
        manifest = path / "manifest.json"
        if manifest.is_file() and list(json.loads(manifest.read_text())["splits"]) == [split]:
            found.append(path)
    return found


def load_run(path):
    manifest = json.loads((path / "manifest.json").read_text())
    records = [json.loads(line) for line in (path / "retrieval.jsonl").read_text().splitlines()
               if line.strip()]
    return manifest, records


# ---------- comparison (pure; tests/test_chunk_experiment.py) ----------


def pooled_latency(record_lists):
    """Median/p95 over every timed call of every run, split as in the C08 summary."""
    rows = [r for records in record_lists for r in records]
    methods = sorted({m for r in rows for m in r["methods"]})
    out = {"embedding_ms": latency([r["embedding_ms"] for r in rows])}
    for method in methods:
        for suffix, subset in (("", rows), ("_unfiltered", [r for r in rows if not r["filtered"]]),
                               ("_filtered", [r for r in rows if r["filtered"]])):
            out[f"retrieval_ms_{method}{suffix}"] = latency(
                [r["methods"][method]["retrieval_ms"] for r in subset if method in r["methods"]])
    return out


def arm_summary(arm, embed_report, manifests, record_lists):
    """One arm's dev evidence: chunks, embedding effort, recall, pooled latency."""
    first = manifests[0]
    retrieval = first["summary"]["retrieval"]["dev"]
    recall = {m: retrieval[m]["all_answerable"] for m in retrieval}
    stable = all(m["summary"]["retrieval"]["dev"][k]["all_answerable"] == recall[k]
                 for m in manifests for k in recall)
    chunk_configs = first["chunk_configs"]
    return {
        "arm": arm, **{k: ARMS[arm][k] for k in ("chunk_tokens", "overlap_tokens", "database")},
        "embedding_config": first["config"]["embedding_config"],
        "chunks": sum(c["chunks"] for c in chunk_configs) if chunk_configs else None,
        "embedding": None if embed_report is None else {
            k: embed_report.get(k) for k in (
                "articles_embedded", "articles_skipped", "chunks_written", "token_count_min",
                "token_count_max", "input_tokens_max", "input_tokens_embedded", "embed_seconds",
                "total_seconds", "wall_seconds", "peak_rss_bytes")},
        "dev_runs": [m["run_id"] for m in manifests],
        "recall_at_5": recall,
        "recall_unfiltered": {m: retrieval[m]["unfiltered"] for m in retrieval},
        "recall_filtered": {m: retrieval[m]["filtered"] for m in retrieval},
        "recall_identical_across_runs": stable,
        "ann_vs_exact": {k: (first["summary"]["ann_vs_exact"]["dev"] or {}).get(k) for k in (
            "n_unfiltered", "mean_chunk_overlap_at_5_unfiltered",
            "min_chunk_overlap_at_5_unfiltered", "mean_article_overlap_at_5")},
        "latency": pooled_latency(record_lists),
        "misses": {m: sorted({r["question_id"] for records in record_lists[:1] for r in records
                              if r["answerable"] and (r["methods"][m]["recall_at_5"] or 0) < 1})
                   for m in retrieval},
    }


def decide(baseline, candidate):
    """Apply RULE to two arm summaries; returns (chosen arm, reason)."""
    def value(summary, method):
        return summary["recall_at_5"][method]["recall_at_5"]

    for summary in (baseline, candidate):
        if value(summary, "vector") is None or value(summary, "keyword") is None:
            raise ValueError(f"{summary['arm']} has no answerable dev recall")
    vector = value(candidate, "vector") - value(baseline, "vector")
    keyword = value(candidate, "keyword") - value(baseline, "keyword")
    if vector > 0 and keyword >= 0:
        return candidate["arm"], (f"200/50 vector Recall@5 is higher by {vector:+.4f} and "
                                  f"keyword is not lower ({keyword:+.4f})")
    reason = ("200/50 vector Recall@5 is not higher" if vector <= 0
              else "200/50 keyword Recall@5 is lower")
    return baseline["arm"], f"{reason} (vector {vector:+.4f}, keyword {keyword:+.4f}); keep 300/50"


def same_inputs(manifests):
    """Corpus content, question labels and model must match across every compared run."""
    keys = {(m["corpus"]["content_sha256"], m["question_set"]["labels_sha256"],
             m["config"]["embedding_model"], m["config"]["embedding_model_revision"])
            for m in manifests}
    if len(keys) != 1:
        raise ValueError(f"runs differ in corpus, questions or model: {sorted(keys)}")
    return dict(zip(("content_sha256", "labels_sha256", "embedding_model",
                     "embedding_model_revision"), keys.pop(), strict=True))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------- commands ----------


def _env(arm):
    return {**os.environ, "DB_NAME": ARMS[arm]["database"]}


def _sizes(arm):
    return ["--chunk-tokens", str(ARMS[arm]["chunk_tokens"]),
            "--overlap-tokens", str(ARMS[arm]["overlap_tokens"])]


def embed(root=OUT):
    """Embed each arm in a child process so wall time and peak RSS are per arm."""
    for arm in ARMS:
        target = arm_dir(arm, root) / "embed.json"
        if target.exists():
            print(f"{arm}: {target} exists; skipped", file=sys.stderr)
            continue
        started = time.perf_counter()
        child = subprocess.Popen([sys.executable, "-m", "citehop.embed", "run", *_sizes(arm)],
                                 env=_env(arm), stdout=subprocess.PIPE, cwd=ROOT, text=True)
        stdout = child.stdout.read()
        _, status, usage = os.wait4(child.pid, 0)  # this child's own resource usage
        child.returncode = os.waitstatus_to_exitcode(status)
        if child.returncode:
            return child.returncode
        report = json.loads(stdout)
        report["wall_seconds"] = round(time.perf_counter() - started, 2)
        # ru_maxrss is bytes on macOS and KiB on Linux.
        report["peak_rss_bytes"] = usage.ru_maxrss * (1 if sys.platform == "darwin" else 1024)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2) + "\n")
        print(f"{arm}: {report['chunks_written']} chunks, {report['embed_seconds']} s model time",
              file=sys.stderr)
    return 0


def evaluate_arm(arm, split, label, extra=(), root=OUT):
    out = arm_dir(arm, root) / "runs"
    out.mkdir(parents=True, exist_ok=True)
    done = subprocess.run([sys.executable, "-m", "citehop.evaluate", "--splits", split,
                           *_sizes(arm), "--out", str(out), "--label", label, *extra],
                          env=_env(arm), cwd=ROOT)
    return done.returncode


def dev(rounds=DEV_ROUNDS, root=OUT):
    if (root / "decision.json").exists():
        print("decision is frozen; dev runs after the freeze would not change it",
              file=sys.stderr)
        return 1
    for number in range(1, rounds + 1):
        order = list(ARMS) if number % 2 else list(reversed(ARMS))  # alternate to spread drift
        for arm in order:
            code = evaluate_arm(arm, "dev", f"S03 dev {arm} round {number}/{rounds}", root=root)
            if code:
                return code
    return 0


def freeze(root=OUT):
    target = root / "decision.json"
    if target.exists():
        print(f"{target} already exists; the decision is frozen", file=sys.stderr)
        return 1
    if any(runs(arm, "test", root) for arm in ARMS):
        print("a test run already exists; refusing to decide after seeing test results",
              file=sys.stderr)
        return 1
    summaries, manifests = {}, []
    for arm in ARMS:
        loaded = [load_run(path) for path in runs(arm, "dev", root)]
        if not loaded:
            print(f"{arm}: no dev runs; run `dev` first", file=sys.stderr)
            return 1
        embed_path = arm_dir(arm, root) / "embed.json"
        report = json.loads(embed_path.read_text()) if embed_path.exists() else None
        summaries[arm] = arm_summary(arm, report, [m for m, _ in loaded], [r for _, r in loaded])
        manifests += [m for m, _ in loaded]
    inputs = same_inputs(manifests)
    chosen, reason = decide(summaries[BASELINE], summaries[CANDIDATE])
    comparison = {"card": "S03", "split": "dev", "inputs": inputs,
                  "hardware": manifests[0]["hardware"], "warm_up": manifests[0]["warm_up"],
                  "latency_boundaries": manifests[0]["latency"]["boundaries"],
                  "label_review": manifests[0]["question_set"]["label_review"],
                  "final_claims_allowed": all(m["final_claims_allowed"] for m in manifests),
                  "arms": summaries}
    (root / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    decision = {"card": "S03", "frozen_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "rule": RULE, "chosen": chosen, "chosen_config": ARMS[chosen], "reason": reason,
                "evidence": {"comparison.json": sha256(root / "comparison.json"),
                             "dev_runs": {arm: summaries[arm]["dev_runs"] for arm in ARMS}},
                "test_runs_at_freeze": 0}
    with target.open("x") as fh:  # exclusive: never overwritten
        fh.write(json.dumps(decision, indent=2) + "\n")
    print(json.dumps({"chosen": chosen, "reason": reason}))
    return 0


def test(root=OUT):
    target = root / "decision.json"
    if not target.exists():
        print("freeze the decision on dev first", file=sys.stderr)
        return 1
    if any(runs(arm, "test", root) for arm in ARMS):
        print("the follow-up test run already exists", file=sys.stderr)
        return 1
    decision = json.loads(target.read_text())
    arm, digest = decision["chosen"], sha256(target)
    code = evaluate_arm(arm, "test", f"S03 follow-up test of frozen choice {arm} "
                        f"(decision.json sha256 {digest})", ["--no-answers"], root)
    if code:
        return code
    path = runs(arm, "test", root)[-1]
    manifest, _ = load_run(path)
    retrieval = manifest["summary"]["retrieval"]["test"]
    (root / "followup.json").write_text(json.dumps({
        "card": "S03", "decision_sha256": digest, "arm": arm, "run_id": manifest["run_id"],
        "final_claims_allowed": manifest["final_claims_allowed"],
        "recall_at_5": {m: retrieval[m]["all_answerable"] for m in retrieval},
        "latency": manifest["summary"]["latency"]["test"],
        "note": "confirmation only; recorded after the freeze and not used for the choice",
    }, indent=2) + "\n")
    print(path)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m citehop.chunk_experiment",
                                     description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("embed", "dev", "freeze", "test"))
    parser.add_argument("--rounds", type=int, default=DEV_ROUNDS)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.command == "dev":
        return dev(args.rounds, args.out)
    return {"embed": embed, "freeze": freeze, "test": test}[args.command](args.out)


if __name__ == "__main__":
    sys.exit(main())
