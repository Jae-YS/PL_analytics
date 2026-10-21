"""Retrieval tests for src/tools/retrieval.py.

These call Vertex AI (one query embedding per question, roughly 40 calls),
so they are skipped unless you opt in:

    RUN_EMBED_TESTS=1 python -m pytest tests/test_retrieval.py -v -s

Needs: Postgres running with doc_chunks loaded (python -m scripts.ingest_docs)
and `gcloud auth application-default login` done.

Contract assumed for search_documents(query, top_k=3, doc_type=None):
    {"query": str,
     "results": [{"source_file", "title", "date", "score", "content"}, ...]}
    best match first; "score" is cosine similarity (1 - distance).

What is NOT tested here, on purpose: unanswerable questions (U rows in
evals/doc_facts.md). A similarity score measures topic, not whether the
text answers the question, so those are scored on the agent's final answer.

The thresholds below are starting values. After your first real run, note
the actual rates and set each threshold a little under them. Do not lower a
threshold just to make a failing question pass; investigate the question.
"""
import json
import os
import re
from functools import lru_cache

import pytest

from helpers import DOCS, FACTS

if not os.getenv("RUN_EMBED_TESTS"):
    pytest.skip("set RUN_EMBED_TESTS=1 to run (calls Vertex AI)",
                allow_module_level=True)

retrieval = pytest.importorskip(
    "src.tools.retrieval", reason="src/tools/retrieval.py not written yet")

TOP3_MIN_FACTS = 0.90        # core + stress questions
TOP1_MIN_FACTS = 0.70
TOP3_MIN_PARAPHRASE = 0.80   # wording shares few words with the docs


def _rows(prefixes: str):
    """(id, source_file, question) for fact rows whose ID starts with a prefix."""
    out = []
    if not FACTS.exists():
        return out
    for line in FACTS.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and re.match(rf"^[{prefixes}]\d\d$", cells[0]):
            out.append((cells[0], cells[1], cells[2]))
    return out


FACT_ROWS = _rows("DX")
PARAPHRASE_ROWS = _rows("P")


@lru_cache(maxsize=None)
def _files(query: str, k: int = 3) -> tuple:
    """Source files returned for a query, best first (cached to save calls)."""
    out = retrieval.search_documents(query, top_k=k)
    return tuple(r["source_file"] for r in out["results"])


# ---------- tool contract ----------

def test_result_shape_and_ordering():
    out = retrieval.search_documents("Wolves pressing and PPDA", top_k=3)
    assert out["query"] == "Wolves pressing and PPDA"
    results = out["results"]
    assert len(results) == 3
    for r in results:
        assert {"source_file", "title", "date", "score", "content"} <= set(r)
        assert (DOCS / r["source_file"]).exists()
        assert -1.0 <= r["score"] <= 1.0
        assert r["content"].strip()
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True), "best match must come first"
    json.dumps(out)            # plain JSON types only (no date objects)


@pytest.mark.parametrize("k", [1, 2, 5])
def test_top_k_is_respected(k):
    assert len(retrieval.search_documents("scouting report", top_k=k)["results"]) == k


@pytest.mark.parametrize("doc_type", ["briefing", "scouting", "memo"])
def test_doc_type_filter(doc_type):
    out = retrieval.search_documents("tactics and data", top_k=3, doc_type=doc_type)
    assert out["results"], f"no results for doc_type={doc_type}"
    for r in out["results"]:
        assert f"_{doc_type}_" in r["source_file"], r["source_file"]


# ---------- one test per question ----------

@pytest.mark.skipif(not FACT_ROWS, reason="no D/X rows in evals/doc_facts.md")
@pytest.mark.parametrize("fid,source,question", FACT_ROWS)
def test_fact_question_finds_source_in_top3(fid, source, question):
    got = _files(question)
    assert source in got, f"{fid}: expected {source}, got {list(got)}"


@pytest.mark.skipif(not PARAPHRASE_ROWS, reason="no P rows in evals/doc_facts.md")
@pytest.mark.parametrize("pid,source,question", PARAPHRASE_ROWS)
def test_paraphrase_question_finds_source_in_top3(pid, source, question):
    got = _files(question)
    assert source in got, f"{pid}: expected {source}, got {list(got)}"


# ---------- aggregate hit rates (these are the README numbers) ----------

def _rates(rows):
    top1 = sum(1 for _, src, q in rows if _files(q)[0] == src)
    top3 = sum(1 for _, src, q in rows if src in _files(q))
    return top1 / len(rows), top3 / len(rows)


@pytest.mark.skipif(not FACT_ROWS, reason="no D/X rows")
def test_hit_rates_core_and_stress():
    top1, top3 = _rates(FACT_ROWS)
    print(f"\ncore+stress ({len(FACT_ROWS)} questions): "
          f"top-1 {top1:.0%}, top-3 {top3:.0%}")
    assert top3 >= TOP3_MIN_FACTS
    assert top1 >= TOP1_MIN_FACTS


@pytest.mark.skipif(not PARAPHRASE_ROWS, reason="no P rows")
def test_hit_rates_paraphrase():
    top1, top3 = _rates(PARAPHRASE_ROWS)
    print(f"\nparaphrase ({len(PARAPHRASE_ROWS)} questions): "
          f"top-1 {top1:.0%}, top-3 {top3:.0%}")
    assert top3 >= TOP3_MIN_PARAPHRASE