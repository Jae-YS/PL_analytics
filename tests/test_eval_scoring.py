"""Free tests for src/eval_scoring.py (no ADK, no model calls)."""
import json

from helpers import ROOT
from src.eval_scoring import classify_error, is_refusal, score_row, summarize

ROWS = {json.loads(l)["id"]: json.loads(l)
        for l in (ROOT / "evals" / "eval_set.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}


# ---------- refusal detection ----------

def test_real_agent_refusal_is_detected():
    # Wording the agent actually produced for the Kael question.
    assert is_refusal("The internal documents do not contain information regarding "
                      "Joren Kael's weekly wage.")


def test_other_refusal_phrasings():
    for text in ["I couldn't find that figure.",
                 "There are no matches for Luton in 2025/26.",
                 "That is not in the documents.",
                 "I can't predict future results.",
                 "Newcastle's PPDA isn't available in the notes."]:
        assert is_refusal(text), text


def test_normal_answers_are_not_refusals():
    assert not is_refusal("Liverpool won the league with 84 points.")
    assert not is_refusal("Arsenal earned 85 points: 26 wins, 7 draws, 5 losses.")


# ---------- error classification ----------

def test_rate_limits_and_outages_are_infra():
    for text in ["429 RESOURCE_EXHAUSTED. Resource exhausted",
                 "_ResourceExhaustedError: ...",
                 "503 UNAVAILABLE",
                 "DEADLINE_EXCEEDED",
                 "Request timed out"]:
        assert classify_error(text) == "infra", text


def test_other_errors_are_not_infra():
    assert classify_error("KeyError: 'DATABASE_URL'") == "error"
    assert classify_error("ValueError: Unknown team 'Atlantis FC'") == "error"


# ---------- scoring ----------

def test_correct_stats_answer_passes():
    r = score_row(ROWS["S01"], "Arsenal earned 85 points in 2025/26.", ["team_record"])
    assert r["status"] == "pass" and r["tool_ok"] is True


def test_wrong_number_fails():
    r = score_row(ROWS["S01"], "Arsenal earned 84 points.", ["team_record"])
    assert r["status"] == "fail" and any("85" in x for x in r["reasons"])


def test_right_answer_from_forbidden_tool_still_fails():
    r = score_row(ROWS["S01"], "Arsenal earned 85 points.", ["team_record", "search_documents"])
    assert r["status"] == "fail"
    assert any("forbidden tool search_documents" in x for x in r["reasons"])


def test_missing_expected_tool_fails():
    r = score_row(ROWS["S01"], "Arsenal earned 85 points.", [])
    assert r["status"] == "fail" and any("missing tool team_record" in x for x in r["reasons"])


def test_combined_needs_both_tools():
    answer = "Brighton took 29 away points. The notes say 1.4 metres per second in build-up."
    assert score_row(ROWS["C01"], answer, ["home_away_split", "search_documents"])["status"] == "pass"
    assert score_row(ROWS["C01"], answer, ["home_away_split"])["status"] == "fail"


def test_borrowed_figure_is_caught():
    # U02 trap: Villa's PPDA (9.8) must not be reported as Newcastle's.
    r = score_row(ROWS["U02"], "Newcastle's PPDA is 9.8.", ["search_documents"])
    assert r["status"] == "fail"
    assert any("forbidden '9.8'" in x for x in r["reasons"])


def test_correct_refusal_passes_and_guess_fails():
    ok = score_row(ROWS["U01"], "The documents do not contain his weekly wage.", ["search_documents"])
    bad = score_row(ROWS["U01"], "His weekly wage is about 45,000 euros.", ["search_documents"])
    assert ok["status"] == "pass"
    assert bad["status"] == "fail" and "no refusal detected" in bad["reasons"]


def test_no_tools_needed_prediction_refusal():
    r = score_row(ROWS["U06"], "I don't have 2026/27 data and I can't predict results.", [])
    assert r["status"] == "pass"


def test_row_without_machine_checkable_values_is_review():
    r = score_row(ROWS["S06"], "City won once, Arsenal twice, three draws.", ["head_to_head"])
    assert r["status"] == "review"


def test_review_row_with_wrong_tool_is_still_a_fail():
    assert score_row(ROWS["S06"], "Some answer.", [])["status"] == "fail"


def test_infra_and_other_errors_are_separate_statuses():
    assert score_row(ROWS["S01"], "", [], "infra")["status"] == "infra_error"
    assert score_row(ROWS["S01"], "", [], "error")["status"] == "error"


def test_case_insensitive_matching():
    assert score_row(ROWS["S02"], "LIVERPOOL won with 84 points", ["league_table"])["status"] == "pass"


# ---------- report ----------

def _res(id_, cat, status, lat, tool_ok=True, reasons=None):
    return {"id": id_, "category": cat, "status": status, "latency_s": lat, "tool_ok": tool_ok,
            "reasons": reasons or [], "input_tokens": 1000, "output_tokens": 100,
            "thought_tokens": 0, "answer": "x"}


def test_summary_counts_and_excludes_infra_from_accuracy():
    results = [_res("S01", "stats", "pass", 2.0), _res("S02", "stats", "fail", 3.0, reasons=["missing '84'"]),
               _res("S03", "stats", "infra_error", 40.0, tool_ok=None),
               _res("U01", "unanswerable", "pass", 4.0)]
    text = summarize(results, {"model": "m"}, price_in=1.0, price_out=4.0)
    assert "| stats | 1 | 1 | 0 | 1 | 0 | 1/2 |" in text      # accuracy ignores the infra error
    assert "**2/3**" in text
    assert "p50" in text and "Estimated cost" in text
    assert "S02" in text and "S03" in text                       # both listed under needs attention


def test_summary_without_prices_says_how_to_get_cost():
    text = summarize([_res("S01", "stats", "pass", 1.0)])
    assert "--price-in" in text
