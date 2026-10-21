"""Validates evals/eval_set.jsonl before you spend model calls on it.

Free to run (no Vertex calls):  python -m pytest tests/test_eval_set.py -v

Row schema:
  id, category (stats | docs | combined | unanswerable), question
  expected_tools   tools that must be called
  forbidden_tools  tools that must NOT be called
  expected_all     strings that must all appear in the answer
  expected_any     at least one of these must appear (if non-empty)
  must_not_contain strings that must not appear (borrowed-figure check)
  refusal          true if the right answer is "not in the documents / data"
  source_file      doc the answer comes from (docs, combined, some unanswerable)
  expected_facts   human-readable truth, for manual or judge review
"""
import json

import pytest

from helpers import DOCS, ROOT, load_season, oracle_record, oracle_table

EVAL = ROOT / "evals" / "eval_set.jsonl"
pytestmark = pytest.mark.skipif(not EVAL.exists(), reason="evals/eval_set.jsonl not found")

TOOLS = {"team_record", "league_table", "home_away_split", "head_to_head",
         "form", "team_record_between", "search_documents"}
CATEGORIES = {"stats", "docs", "combined", "unanswerable"}
KEYS = {"id", "category", "question", "expected_tools", "forbidden_tools",
        "expected_all", "expected_any", "must_not_contain", "refusal",
        "source_file", "expected_facts", "notes"}


def _rows():
    if not EVAL.exists():
        return []
    return [json.loads(l) for l in EVAL.read_text(encoding="utf-8").splitlines() if l.strip()]


ROWS = _rows()
BY_ID = {r["id"]: r for r in ROWS}


def test_enough_rows_and_unique_ids():
    assert len(ROWS) >= 20
    assert len({r["id"] for r in ROWS}) == len(ROWS)
    assert len({r["question"] for r in ROWS}) == len(ROWS)


def test_every_category_is_covered():
    counts = {c: sum(1 for r in ROWS if r["category"] == c) for c in CATEGORIES}
    assert all(n >= 3 for n in counts.values()), counts


@pytest.mark.parametrize("row", ROWS, ids=[r["id"] for r in ROWS])
def test_row_schema(row):
    assert KEYS <= set(row), KEYS - set(row)
    assert row["category"] in CATEGORIES
    assert row["question"].strip()
    assert set(row["expected_tools"]) <= TOOLS
    assert set(row["forbidden_tools"]) <= TOOLS
    assert not set(row["expected_tools"]) & set(row["forbidden_tools"])
    assert row["expected_facts"], "needs human-readable expected_facts"


@pytest.mark.parametrize("row", ROWS, ids=[r["id"] for r in ROWS])
def test_refusal_rows_have_no_expected_values(row):
    if row["refusal"]:
        assert row["category"] == "unanswerable"
        assert row["expected_all"] == []
    if row["category"] == "unanswerable":
        assert row["refusal"] is True


@pytest.mark.parametrize("row", [r for r in ROWS if r["category"] == "stats"],
                         ids=[r["id"] for r in ROWS if r["category"] == "stats"])
def test_stats_rows_use_stats_tools_only(row):
    assert row["expected_tools"] and "search_documents" not in row["expected_tools"]
    assert "search_documents" in row["forbidden_tools"]


@pytest.mark.parametrize("row", [r for r in ROWS if r["category"] == "docs"],
                         ids=[r["id"] for r in ROWS if r["category"] == "docs"])
def test_doc_rows_expected_strings_appear_in_source(row):
    src = DOCS / row["source_file"]
    assert src.exists(), row["source_file"]
    text = src.read_text(encoding="utf-8")
    for s in row["expected_all"]:
        assert s in text, f"{row['id']}: '{s}' not in {row['source_file']}"


@pytest.mark.parametrize("row", [r for r in ROWS if r["category"] in ("combined", "unanswerable")
                                  and r["source_file"]],
                         ids=[r["id"] for r in ROWS if r["category"] in ("combined", "unanswerable")
                              and r["source_file"]])
def test_source_files_exist(row):
    assert (DOCS / row["source_file"]).exists()


# ---- stats answers re-derived from the raw CSVs ----

def test_stats_expectations_match_csv():
    def pts(season, team):
        return str(oracle_record(load_season(season), team)["points"])

    champ = oracle_table(load_season("2425"))[0]
    bottom = oracle_table(load_season("2324"))[-1]
    city = oracle_record(load_season("2324"), "Man City")

    assert BY_ID["S01"]["expected_all"] == [pts("2526", "Arsenal")]
    assert BY_ID["S02"]["expected_all"] == [champ["team"], str(champ["points"])]
    assert BY_ID["S03"]["expected_all"] == [bottom["team"], str(bottom["points"])]
    assert BY_ID["S04"]["expected_all"] == [str(city["goals_for"]), str(city["goals_against"])]
    assert BY_ID["S09"]["expected_all"] == [pts("2324", "Tottenham")]


def test_luton_really_is_missing_from_2526():
    df = load_season("2526")
    assert "Luton" not in set(df["HomeTeam"]) | set(df["AwayTeam"])
