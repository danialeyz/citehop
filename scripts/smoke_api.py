"""Live API smoke flow: health -> vector search -> answer -> article -> graph -> stats -> runs.

    python scripts/smoke_api.py [BASE_URL] [--no-answer]

BASE_URL defaults to http://127.0.0.1:3000 (the Next.js proxy); pass :8000 to hit FastAPI
directly. Needs running databases, an embedded corpus, and an imported graph. The answer step
makes one real generator call. Passages are shortened in the printed summary only.
"""

import json
import sys

import httpx

QUESTION = "Who created the first algorithm for random decision forests, and in what year?"


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    base = (args[0] if args else "http://127.0.0.1:3000").rstrip("/") + "/api/v1"
    out, ok = {"base_url": base}, True
    with httpx.Client(timeout=300) as http:
        def call(name, method, path, **kw):
            nonlocal ok
            response = http.request(method, base + path, **kw)
            body = response.json() if "json" in response.headers.get("content-type", "") \
                else response.text
            out[name] = out.get(name, {}) | {"status_code": response.status_code}
            ok &= response.status_code == 200
            return body

        health = call("health", "GET", "/health")
        out["health"]["body"] = health
        search = call("search", "POST", "/search",
                      json={"query": QUESTION, "method": "vector", "k": 5})
        out["search"] |= {
            "corpus_version": search["corpus_version"], "timings": search["timings"],
            "hits": [{k: h[k] for k in ("rank", "chunk_id", "article_id", "title", "score")}
                     for h in search["hits"]]}
        if "--no-answer" not in sys.argv:
            answer = call("answer", "POST", "/answer", json={
                "question": QUESTION, "chunk_ids": [h["chunk_id"] for h in search["hits"]],
                "corpus_version": search["corpus_version"]})
            out["answer"] |= {k: answer.get(k) for k in (
                "status", "text", "citation_map", "reason", "model", "generation_ms", "usage")}
        seed = search["hits"][0]["article_id"]
        article = call("article", "GET", f"/articles/{seed}", params={"passage_page_size": 2})
        out["article"] |= {"title": article["title"], "passages": article["passages"]["total"],
                           "links": article["links"]}
        graph = call("neighborhood", "GET", "/graph/neighborhood",
                     params={"article_id": seed, "max_nodes": 20})
        out["neighborhood"] |= {k: graph[k] for k in ("seed", "graph_version", "truncated",
                                                      "limits")}
        out["neighborhood"]["counts"] = {"nodes": len(graph["nodes"]),
                                         "edges": len(graph["edges"])}
        target = next((n["article_id"] for n in graph["nodes"][1:] if n["kind"] == "article"),
                      seed)
        path = call("path", "GET", "/graph/path", params={"source_id": seed,
                                                          "target_id": target})
        out["path"] |= {k: path[k] for k in ("found", "directed", "graph_version")}
        out["path"]["titles"] = [n["title"] for n in path["nodes"]]
        stats = call("stats", "GET", "/stats")
        out["stats"]["body"] = stats
        runs = call("runs", "GET", "/runs")
        out["runs"] |= {"count": len(runs["runs"]), "invalid": len(runs["invalid"])}
    print(json.dumps(out, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
