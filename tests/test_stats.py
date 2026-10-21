"""Tests for src/tools/stats.py.

Contract these tests assume (write stats.py to match, or edit here):

  resolve_team(name) -> exact CSV team name; raises ValueError if unknown
  resolve_season(s)  -> "2324" from "2023/24", "2023-24" or "2324"

  team_record(team, season) -> dict with team, season, matches_counted and
      played, wins, draws, losses, goals_for, goals_against,
      goal_difference, points. Unknown season -> dict with an "error" key.
  league_table(season) -> list of dicts: position, team + the record fields
  home_away_split(team, season) -> {"home": {...}, "away": {...}} with
      played, wins, draws, losses, goals_for, goals_against, points
  head_to_head(team_a, team_b, season=None) -> {"matches": [...] oldest
      first, each with date, home_team, away_team, home_goals, away_goals;
      "summary": {"team_a_wins", "team_b_wins", "draws"}}
  form(team, n=5, season=None) -> {"matches": [...] newest first, each with
      date, opponent, venue, goals_for, goals_against, result; "points": int}
  team_record_between(team, start_date, end_date) -> same fields as
      team_record, dates inclusive, ISO strings ("2024-09-01")

Run with:  pytest tests/test_stats.py -v
Needs Postgres running and loaded (docker compose up -d).
"""
import json

import pytest

from helpers import (RECORD_FIELDS, SEASONS, available_team_seasons,
                     load_season, oracle_record, oracle_side, oracle_table,
                     team_games)

stats = pytest.importorskip(
    "src.tools.stats", reason="src/tools/stats.py not written yet")

TEAM_SEASONS = available_team_seasons()
pytestmark = pytest.mark.skipif(not TEAM_SEASONS, reason="no CSVs in data/raw")


# ---------- helpers: aliases ----------

@pytest.mark.parametrize("alias,expected", [
    ("Manchester City", "Man City"), ("Man City", "Man City"),
    ("man city", "Man City"), ("Man Utd", "Man United"),
    ("Manchester United", "Man United"), ("Spurs", "Tottenham"),
    ("Tottenham Hotspur", "Tottenham"), ("Nottingham Forest", "Nott'm Forest"),
    ("Wolverhampton Wanderers", "Wolves"), ("Newcastle United", "Newcastle"),
    ("Brighton & Hove Albion", "Brighton"),
])
def test_resolve_team_aliases(alias, expected):
    assert stats.resolve_team(alias) == expected


def test_resolve_team_unknown_raises():
    with pytest.raises(ValueError):
        stats.resolve_team("Atlantis FC")


@pytest.mark.parametrize("raw", ["2023/24", "2023-24", "2324", "23/24"])
def test_resolve_season_formats(raw):
    assert stats.resolve_season(raw) == "2324"


# ---------- team_record ----------

@pytest.mark.parametrize("season,team", TEAM_SEASONS)
def test_team_record_matches_csv_oracle(season, team):
    got = stats.team_record(team, season)
    want = oracle_record(load_season(season), team)
    for field in RECORD_FIELDS:
        assert got[field] == want[field], f"{team} {season} {field}"


@pytest.mark.parametrize("season,team,w,d,l,gf,ga,pts", [
    ("2324", "Man City", 28, 7, 3, 96, 34, 91),
    ("2324", "Arsenal", 28, 5, 5, 91, 29, 89),
    ("2324", "Sheffield United", 3, 7, 28, 35, 104, 16),
    ("2425", "Liverpool", 25, 9, 4, 86, 41, 84),
    ("2425", "Southampton", 2, 6, 30, 26, 86, 12),
    ("2526", "Arsenal", 26, 7, 5, 71, 27, 85),
    ("2526", "Wolves", 3, 11, 24, 27, 68, 20),
])
def test_team_record_known_anchors(season, team, w, d, l, gf, ga, pts):
    got = stats.team_record(team, season)
    assert (got["played"], got["wins"], got["draws"], got["losses"]) == (38, w, d, l)
    assert (got["goals_for"], got["goals_against"], got["points"]) == (gf, ga, pts)


@pytest.mark.parametrize("season,team", TEAM_SEASONS)
def test_team_record_internal_consistency(season, team):
    r = stats.team_record(team, season)
    assert r["points"] == 3 * r["wins"] + r["draws"]
    assert r["played"] == r["wins"] + r["draws"] + r["losses"]
    assert r["goal_difference"] == r["goals_for"] - r["goals_against"]


def test_team_record_accepts_aliases_and_season_formats():
    a = stats.team_record("Manchester City", "2023/24")
    b = stats.team_record("Man City", "2324")
    assert a["points"] == b["points"] == 91


def test_team_record_no_rows_returns_error_not_zeros():
    try:
        r = stats.team_record("Man City", "1011")
    except ValueError:
        return
    assert "error" in r


# ---------- league_table ----------

@pytest.mark.parametrize("season", SEASONS)
def test_league_table_matches_oracle(season):
    got = stats.league_table(season)
    want = oracle_table(load_season(season))
    assert len(got) == 20
    assert [r["position"] for r in got] == list(range(1, 21))
    assert [r["team"] for r in got] == [r["team"] for r in want]
    assert [r["points"] for r in got] == [r["points"] for r in want]


@pytest.mark.parametrize("season,champion,pts,bottom,bpts", [
    ("2324", "Man City", 91, "Sheffield United", 16),
    ("2425", "Liverpool", 84, "Southampton", 12),
    ("2526", "Arsenal", 85, "Wolves", 20),
])
def test_league_table_champion_and_bottom(season, champion, pts, bottom, bpts):
    t = stats.league_table(season)
    assert (t[0]["team"], t[0]["points"]) == (champion, pts)
    assert (t[-1]["team"], t[-1]["points"]) == (bottom, bpts)


@pytest.mark.parametrize("season", SEASONS)
def test_league_table_totals_balance(season):
    df = load_season(season)
    t = stats.league_table(season)
    total_goals = int(df["FTHG"].sum() + df["FTAG"].sum())
    assert sum(r["goals_for"] for r in t) == total_goals
    assert sum(r["goals_against"] for r in t) == total_goals
    assert sum(r["wins"] for r in t) == sum(r["losses"] for r in t)
    draws = int((df["FTR"] == "D").sum())
    decisive = len(df) - draws
    assert sum(r["points"] for r in t) == 3 * decisive + 2 * draws


# ---------- home_away_split ----------

@pytest.mark.parametrize("season,team", TEAM_SEASONS)
def test_home_away_split_matches_oracle(season, team):
    got = stats.home_away_split(team, season)
    df = load_season(season)
    for side in ("home", "away"):
        want = oracle_side(df, team, side)
        for k, v in want.items():
            assert got[side][k] == v, f"{team} {season} {side} {k}"


@pytest.mark.parametrize("season,team", TEAM_SEASONS)
def test_home_plus_away_equals_total(season, team):
    s = stats.home_away_split(team, season)
    r = stats.team_record(team, season)
    assert s["home"]["points"] + s["away"]["points"] == r["points"]
    assert s["home"]["played"] + s["away"]["played"] == r["played"]
    assert s["home"]["goals_for"] + s["away"]["goals_for"] == r["goals_for"]


def test_home_away_known_anchor_brighton_2425():
    s = stats.home_away_split("Brighton", "2425")
    assert (s["home"]["points"], s["home"]["goals_for"], s["home"]["goals_against"]) == (32, 30, 26)
    assert (s["away"]["points"], s["away"]["goals_for"], s["away"]["goals_against"]) == (29, 36, 33)


# ---------- head_to_head ----------

def test_head_to_head_city_arsenal_all_seasons():
    h = stats.head_to_head("Man City", "Arsenal")
    assert len(h["matches"]) == 6
    assert h["summary"] == {"team_a_wins": 1, "team_b_wins": 2, "draws": 3}
    dates = [m["date"] for m in h["matches"]]
    assert dates == sorted(dates), "matches should be oldest first"


def test_head_to_head_single_season_and_order_of_args():
    h = stats.head_to_head("Arsenal", "Man City", season="2425")
    assert len(h["matches"]) == 2
    assert h["summary"] == {"team_a_wins": 1, "team_b_wins": 0, "draws": 1}
    last = h["matches"][-1]
    assert (last["home_team"], last["home_goals"], last["away_goals"]) == ("Arsenal", 5, 1)


# ---------- form ----------

def test_form_wolves_last_five_2526():
    f = stats.form("Wolves", 5, season="2526")
    games = team_games(load_season("2526"), "Wolves").tail(5).iloc[::-1]
    assert len(f["matches"]) == 5
    assert [m["date"] for m in f["matches"]] == [d.strftime("%Y-%m-%d") for d in games["Date"]]
    assert f["points"] == 3
    assert [m["result"] for m in f["matches"]] == ["D", "D", "L", "D", "L"]


@pytest.mark.parametrize("n", [1, 3, 10])
def test_form_respects_n(n):
    assert len(stats.form("Arsenal", n, season="2526")["matches"]) == n


# ---------- team_record_between ----------

def test_between_newcastle_september_2024():
    r = stats.team_record_between("Newcastle", "2024-09-01", "2024-09-30")
    assert (r["played"], r["wins"], r["draws"], r["losses"]) == (4, 2, 1, 1)
    assert (r["goals_for"], r["goals_against"], r["points"]) == (6, 6, 7)


@pytest.mark.parametrize("season,team", [("2425", "Liverpool"), ("2526", "Wolves")])
def test_between_full_season_equals_team_record(season, team):
    df = load_season(season)
    start, end = df["Date"].min().strftime("%Y-%m-%d"), df["Date"].max().strftime("%Y-%m-%d")
    a = stats.team_record_between(team, start, end)
    b = stats.team_record(team, season)
    for f in RECORD_FIELDS:
        assert a[f] == b[f]


# ---------- output hygiene ----------

def test_all_outputs_are_json_serializable():
    """Agent tools must return plain JSON types (no dates, Decimals, numpy)."""
    outputs = [
        stats.team_record("Man City", "2324"),
        stats.league_table("2324"),
        stats.home_away_split("Brighton", "2425"),
        stats.head_to_head("Man City", "Arsenal"),
        stats.form("Wolves", 5, season="2526"),
        stats.team_record_between("Newcastle", "2024-09-01", "2024-09-30"),
    ]
    for o in outputs:
        json.dumps(o)
