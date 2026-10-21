import os
import difflib
import re
import pandas as pd
from pathlib import Path
from functools import lru_cache 
import psycopg
# get_conn()	Reads DATABASE_URL from .env and returns a psycopg connection.	Default postgresql://pl:pl@localhost:5433/pl.
# resolve_team(name)	Maps user input to the exact name in the data.	Case-insensitive. Use an alias dict (Manchester City, Man Utd, Spurs, Tottenham Hotspur, Nottingham Forest, Wolverhampton Wanderers, Newcastle United, Brighton & Hove Albion). Otherwise raise ValueError listing close matches (difflib.get_close_matches).
# resolve_season(s)	Maps "2023/24", "2023-24", "23/24" and "2324" to "2324".	The tests cover all four.

# resolve_team and resolve_season are public, since the tests call them directly.

# Agent tools
# Function	Returns	Test anchors
# team_record(team, season)	A dict with team, season, matches_counted and played, wins, draws, losses, goals_for, goals_against, goal_difference, points.	If no rows exist, return {"error": "..."} instead of zeros.
# league_table(season)	A list of 20 dicts with position, team and the same record fields.	Sort by points, then goal difference, then goals for, then team name.
# home_away_split(team, season)	{"home": {...}, "away": {...}}, each with played, wins, draws, losses, goals_for, goals_against, points.	Brighton 2425: home 32 points, away 29.
# head_to_head(team_a, team_b, season=None)	{"matches": [...], "summary": {"team_a_wins", "team_b_wins", "draws"}}.	Matches are oldest first. Each has date, home_team, away_team, home_goals, away_goals. Man City vs Arsenal across all seasons gives 1, 2 and 3.
# form(team, n=5, season=None)	{"matches": [...], "points": int} with the newest match first.	Each match has date, opponent, venue ("H" or "A"), goals_for, goals_against, result ("W", "D" or "L"). If season is None, use the latest season in the table.
# team_record_between(team, start_date, end_date)	The same fields as team_record.	Dates are inclusive ISO strings. Newcastle for September 2024 gives 4 played, 2 wins, 1 draw, 1 loss, 6 for, 6 against and 7 points.

def _get_conn():
    try:
        from dotenv import load_dotenv
        load_dotenv(".env")
    except ImportError:
        pass
    url = os.getenv("DATABASE_URL", "postgresql://pl:pl@localhost:5433/pl")
    return psycopg.connect(url, connect_timeout=3)  


TEAMS = [
    "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton",
    "Burnley", "Chelsea", "Crystal Palace", "Everton", "Fulham", "Ipswich",
    "Leeds", "Leicester", "Liverpool", "Luton", "Man City", "Man United",
    "Newcastle", "Nott'm Forest", "Sheffield United", "Southampton",
    "Sunderland", "Tottenham", "West Ham", "Wolves",
]

ALIASES = {
    "Manchester City": "Man City",
    "City": "Man City",
    "Manchester United": "Man United",
    "Man Utd": "Man United",
    "Man U": "Man United",
    "Spurs": "Tottenham",
    "Tottenham Hotspur": "Tottenham",
    "Wolverhampton Wanderers": "Wolves",
    "Wolverhampton": "Wolves",
    "Brighton & Hove Albion": "Brighton",
    "Brighton Hove Albion": "Brighton",
    "Nottingham Forest": "Nott'm Forest",
    "Notts Forest": "Nott'm Forest",
    "Forest": "Nott'm Forest",
    "Newcastle United": "Newcastle",
    "Newcastle Utd": "Newcastle",
    "West Ham United": "West Ham",
    "Leicester City": "Leicester",
    "Leeds United": "Leeds",
    "Sheffield Utd": "Sheffield United",
    "Luton Town": "Luton",
    "Ipswich Town": "Ipswich",
    "Palace": "Crystal Palace",
    "Villa": "Aston Villa",
    "AFC Bournemouth": "Bournemouth",
}


def _norm(s: str) -> str:
    s = s.lower().replace("&", "and")
    s = re.sub(r"[^a-z0-9 ]", "", s)     
    return re.sub(r"\s+", " ", s).strip()


_LOOKUP = {_norm(t): t for t in TEAMS}
_LOOKUP.update({_norm(a): c for a, c in ALIASES.items()})


def resolve_team(name: str) -> str:
    key = _norm(name)
    if key in _LOOKUP:
        return _LOOKUP[key]
    close = difflib.get_close_matches(key, _LOOKUP.keys(), n=3, cutoff=0.6)
    hints = sorted({_LOOKUP[c] for c in close})
    msg = f"Unknown team '{name}'."
    if hints:
        msg += f" Did you mean: {', '.join(hints)}?"
    raise ValueError(msg)


def resolve_season(s: str) -> str:
    s = s.strip().replace("-", "/")
    if re.match(r"^\d{2}/\d{2}$", s):
        return s[0:2] + s[3:5]
    elif re.match(r"^\d{4}$", s):
        return s[2:4] + s[4:6]
    elif re.match(r"^\d{4}/\d{2}$", s):
        return s[2:4] + s[5:7]
    else:
        raise ValueError(f"Invalid season format: {s}")
    
    
def team_record(team: str, season: str) -> dict:
    team = resolve_team(team)
    season = resolve_season(season)
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*), SUM(home_goals), SUM(away_goals), "
            "SUM(CASE WHEN home_goals > away_goals THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN home_goals < away_goals THEN 1 ELSE 0 END) "
            "FROM matches WHERE season=%s AND (home_team=%s OR away_team=%s)",
            (season, team, team),
        ).fetchone()
        if row[0] == 0:
            return {"error": f"No matches found for {team} in season {season}"}
        matches_counted, goals_for, goals_against, wins, draws, losses = row
        goal_difference = goals_for - goals_against
        points = wins * 3 + draws
        return {
            "team": team,
            "season": season, 
            "matches_counted": matches_counted,
            "played": matches_counted,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "goals_for": goals_for,
            "goals_against": goals_against,
            "goal_difference": goal_difference,
            "points": points,
        }


def league_table(season: str) -> list:
    season = resolve_season(season)
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT home_team as teams, "
            "FROM matches WHERE season=%s GROUP BY home_team", (season,)
        ).fetchall()
        teams = []
        for team in rows:
            record = team_record(team[0], season)
            teams.append({
                "position": None,
                "team": team[0],
                **record,
            })
        teams.sort(key=lambda x: (-x["points"], -x["goal_difference"], -x["goals_for"], x["team"]))
        
        table = []
        for i, team in enumerate(teams, start=1):
            team["position"] = i
            table.append(team)
        return table


def home_away_split(team: str, season: str) -> dict:
    team = resolve_team(team)
    season = resolve_season(season)
    with _get_conn() as conn:
        home_row = conn.execute(
            "SELECT COUNT(*), SUM(home_goals), SUM(away_goals), "
            "SUM(CASE WHEN home_goals > away_goals THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN home_goals = away_goals THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN home_goals < away_goals THEN 1 ELSE 0 END) "
            "FROM matches WHERE season=%s AND home_team=%s",
            (season, team),
        ).fetchone()
        away_row = conn.execute(
            "SELECT COUNT(*), SUM(away_goals), SUM(home_goals), "
            "SUM(CASE WHEN away_goals > home_goals THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN away_goals = home_goals THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN away_goals < home_goals THEN 1 ELSE 0 END) "
            "FROM matches WHERE season=%s AND away_team=%s",
            (season, team),
        ).fetchone()
        def make_record(row):
            played, goals_for, goals_against, wins, draws, losses = row
            points = wins * 3 + draws
            return {
                "played": played,
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "goals_for": goals_for,
                "goals_against": goals_against,
                "points": points,
            }
        return {
            "home": make_record(home_row),
            "away": make_record(away_row),
        }


def head_to_head(team_a: str, team_b: str, season: str = None) -> dict:
        team_a = resolve_team(team_a)
        team_b = resolve_team(team_b)
        season = resolve_season(season)
        pass


def form(team: str, n: int = 5, season: str = None) -> dict:
    pass
    
def team_record_between(team: str, start_date: str, end_date: str) -> dict:
    pass