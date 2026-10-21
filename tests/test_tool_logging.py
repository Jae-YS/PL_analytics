"""Free tests for src/tool_logging.py (no ADK, no model calls)."""
from types import SimpleNamespace

from src import tool_logging as tl


def _tool(name):
    return SimpleNamespace(name=name)


def _ctx(call_id):
    return SimpleNamespace(function_call_id=call_id)


def test_callbacks_return_none_so_adk_keeps_call_and_result():
    t, c = _tool("team_record"), _ctx("id-1")
    assert tl.before_tool(t, {"team": "Arsenal"}, c) is None
    assert tl.after_tool(t, {"team": "Arsenal"}, c, {"points": 85}) is None


def test_records_name_args_duration_and_response():
    calls = tl.start_collecting()
    t, c = _tool("team_record"), _ctx("id-2")
    tl.before_tool(t, {"team": "Arsenal", "season": "2025/26"}, c)
    tl.after_tool(t, {"team": "Arsenal", "season": "2025/26"}, c, {"points": 85})
    assert len(calls) == 1
    r = calls[0]
    assert r["tool"] == "team_record"
    assert r["args"] == {"team": "Arsenal", "season": "2025/26"}
    assert r["duration_ms"] is not None and r["duration_ms"] >= 0
    assert r["error"] is None
    assert "85" in r["response_preview"]


def test_error_dict_is_flagged():
    calls = tl.start_collecting()
    t, c = _tool("team_record"), _ctx("id-3")
    tl.before_tool(t, {}, c)
    tl.after_tool(t, {}, c, {"error": "No matches found for Luton in season 2526"})
    assert calls[0]["error"].startswith("No matches found")


def test_error_inside_a_list_is_flagged():
    """league_table returns [{"error": ...}] when the season has no data."""
    calls = tl.start_collecting()
    t, c = _tool("league_table"), _ctx("id-4")
    tl.before_tool(t, {}, c)
    tl.after_tool(t, {}, c, [{"error": "No matches found for season 9999"}])
    assert "No matches" in calls[0]["error"]


def test_parallel_calls_keep_their_own_timings():
    calls = tl.start_collecting()
    a, b = _tool("home_away_split"), _tool("search_documents")
    ca, cb = _ctx("id-a"), _ctx("id-b")
    tl.before_tool(a, {}, ca)
    tl.before_tool(b, {}, cb)
    tl.after_tool(b, {}, cb, {"results": []})
    tl.after_tool(a, {}, ca, {"home": {}})
    assert [r["tool"] for r in calls] == ["search_documents", "home_away_split"]
    assert all(r["duration_ms"] is not None for r in calls)


def test_missing_call_id_falls_back_to_tool_name():
    calls = tl.start_collecting()
    t, c = _tool("form"), SimpleNamespace()          # no function_call_id
    tl.before_tool(t, {}, c)
    tl.after_tool(t, {}, c, {"matches": []})
    assert calls[0]["duration_ms"] is not None


def test_without_a_collector_it_still_works():
    tl._collector.set(None)
    t, c = _tool("form"), _ctx("id-5")
    tl.before_tool(t, {}, c)
    assert tl.after_tool(t, {}, c, {"matches": []}) is None


def test_non_json_args_do_not_crash():
    calls = tl.start_collecting()
    t, c = _tool("head_to_head"), _ctx("id-6")
    tl.before_tool(t, {"x": object()}, c)
    tl.after_tool(t, {"x": object()}, c, {"ok": True})
    assert isinstance(calls[0]["args"]["x"], str)
