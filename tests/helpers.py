import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SEASONS = ["2324", "2425", "2526"]
RAW = ROOT / "data" / "raw"
DOCS = ROOT / "data" / "docs"
FACTS = ROOT / "evals" / "doc_facts.md"

RECORD_FIELDS = ["played", "wins", "draws", "losses", "goals_for",
                 "goals_against", "goal_difference", "points"]


@lru_cache(maxsize=None)
def load_season(season: str) -> pd.DataFrame:
    path = RAW / f"{season}.csv"
    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="latin-1")
    df = df.dropna(subset=["HomeTeam", "FTHG"]).copy()
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True)
    return df.reset_index(drop=True)


def teams_in(df: pd.DataFrame) -> list:
    return sorted(set(df["HomeTeam"]) | set(df["AwayTeam"]))


def oracle_record(df: pd.DataFrame, team: str) -> dict:
    home = df[df["HomeTeam"] == team]
    away = df[df["AwayTeam"] == team]
    wins = int((home["FTR"] == "H").sum() + (away["FTR"] == "A").sum())
    draws = int((home["FTR"] == "D").sum() + (away["FTR"] == "D").sum())
    played = len(home) + len(away)
    gf = int(home["FTHG"].sum() + away["FTAG"].sum())
    ga = int(home["FTAG"].sum() + away["FTHG"].sum())
    return {
        "played": played, "wins": wins, "draws": draws,
        "losses": played - wins - draws,
        "goals_for": gf, "goals_against": ga,
        "goal_difference": gf - ga, "points": 3 * wins + draws,
    }


def oracle_side(df: pd.DataFrame, team: str, side: str) -> dict:
    if side == "home":
        sub = df[df["HomeTeam"] == team]
        wins, losses = (sub["FTR"] == "H").sum(), (sub["FTR"] == "A").sum()
        gf, ga = sub["FTHG"].sum(), sub["FTAG"].sum()
    else:
        sub = df[df["AwayTeam"] == team]
        wins, losses = (sub["FTR"] == "A").sum(), (sub["FTR"] == "H").sum()
        gf, ga = sub["FTAG"].sum(), sub["FTHG"].sum()
    draws = (sub["FTR"] == "D").sum()
    return {"played": len(sub), "wins": int(wins), "draws": int(draws),
            "losses": int(losses), "goals_for": int(gf),
            "goals_against": int(ga), "points": int(3 * wins + draws)}


def oracle_table(df: pd.DataFrame) -> list:
    rows = [{"team": t, **oracle_record(df, t)} for t in teams_in(df)]
    rows.sort(key=lambda r: (-r["points"], -r["goal_difference"],
                             -r["goals_for"], r["team"]))
    for i, r in enumerate(rows, start=1):
        r["position"] = i
    return rows


def team_games(df: pd.DataFrame, team: str) -> pd.DataFrame:
    g = df[(df["HomeTeam"] == team) | (df["AwayTeam"] == team)]
    return g.sort_values("Date").reset_index(drop=True)


def available_team_seasons() -> list:
    """(season, team) pairs for parametrized tests; empty if no CSVs."""
    pairs = []
    for s in SEASONS:
        if (RAW / f"{s}.csv").exists():
            pairs += [(s, t) for t in teams_in(load_season(s))]
    return pairs
