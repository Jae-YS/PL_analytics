import os
import difflib
import re
import psycopg

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

_CTE = """
WITH tm AS (
  SELECT season, match_date, home_team AS team, away_team AS opponent,
         'H' AS venue, home_goals AS gf, away_goals AS ga FROM matches
  UNION ALL
  SELECT season, match_date, away_team, home_team,
         'A', away_goals, home_goals FROM matches
)
"""

_AGG = """
  COUNT(*),
  COUNT(*) FILTER (WHERE gf > ga),
  COUNT(*) FILTER (WHERE gf = ga),
  COUNT(*) FILTER (WHERE gf < ga),
  COALESCE(SUM(gf), 0),
  COALESCE(SUM(ga), 0)
"""


def _record(team, season, played, wins, draws, losses, gf, ga) -> dict:
    gf, ga = int(gf), int(ga)
    return {
        "team": team,
        "season": season,
        "matches_counted": played,
        "played": played,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "goals_for": gf,
        "goals_against": ga,
        "goal_difference": gf - ga,
        "points": 3 * wins + draws,
    }
    

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
    if s is None:
        raise ValueError("Season cannot be None. Expected formats: 'YYYY/YY', 'YYYY-YY', 'YY/YY', or 'YYYY'.")
    s = s.strip().replace("-", "/")
    if re.match(r"^\d{4}/\d{2}$", s):
        return s[2:4] + s[5:7]
    elif re.match(r"^\d{2}/\d{2}$", s):
        return s[0:2] + s[3:5]
    elif re.match(r"^\d{4}$", s):
        return s  
    elif re.match(r"^\d{2}$", s):
        return s
    else:
        raise ValueError(f"Invalid season format: {s}. Expected formats: 'YYYY/YY', 'YYYY-YY', 'YY/YY', or 'YYYY'.")
    
    
def resolve_date(date_str: str) -> str:
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str  
    elif re.match(r"^\d{2}/\d{2}/\d{4}$", date_str):
        parts = date_str.split("/")
        return f"{parts[2]}-{parts[1]}-{parts[0]}"  
    else:
        raise ValueError(f"Invalid date format: {date_str}. Expected formats: 'YYYY-MM-DD' or 'DD/MM/YYYY'.")

def team_record(team: str, season: str) -> dict:
    team = resolve_team(team)
    season = resolve_season(season)
    with _get_conn() as conn:
        row = conn.execute(
            f"{_CTE} SELECT {_AGG} FROM tm WHERE season=%s AND team=%s",
            (season, team),
        ).fetchone()
        if row[0] == 0:
            return {"error": f"No matches found for {team} in season {season}"}
        return _record(team, season, *row)


def league_table(season: str) -> list:    
    season = resolve_season(season)
    with _get_conn() as conn:
        rows = conn.execute(
            f"{_CTE} SELECT team, {_AGG} FROM tm WHERE season=%s GROUP BY team",
            (season,),
        ).fetchall()
    if not rows:
        return [{"error": f"No matches found for season {season}"}]

    table = [_record(r[0], season, *r[1:]) for r in rows]
    table.sort(key=lambda x: (-x["points"], -x["goal_difference"],
                              -x["goals_for"], x["team"]))
    for i, row in enumerate(table, start=1):
        row["position"] = i
    return table


def home_away_split(team: str, season: str) -> dict:
    team = resolve_team(team)
    season = resolve_season(season)
    sides = {}
    with _get_conn() as conn:
        for name, venue in (("home", "H"), ("away", "A")):
            played, wins, draws, losses, gf, ga = conn.execute(
                f"{_CTE} SELECT {_AGG} FROM tm "
                "WHERE season=%s AND team=%s AND venue=%s",
                (season, team, venue),
            ).fetchone()
            sides[name] = {
                "played": played,
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "goals_for": int(gf),
                "goals_against": int(ga),
                "points": 3 * wins + draws,
            }
    if sides["home"]["played"] + sides["away"]["played"] == 0:
        return {"error": f"No matches found for {team} in season {season}"}
    return sides

def head_to_head(team_a: str, team_b: str, season: str = None) -> dict:
        team_a = resolve_team(team_a)
        team_b = resolve_team(team_b)
        sql = (f"{_CTE} SELECT match_date, venue, gf, ga FROM tm "
                "WHERE team=%s AND opponent=%s")
        params = [team_a, team_b]
        if season:
            season = resolve_season(season)
            sql += " AND season=%s"
            params.append(season)
        sql += " ORDER BY match_date"

        with _get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        if not rows:
            return {"error": f"No matches found between {team_a} and {team_b}"
                            + (f" in season {season}" if season else "")}

        matches = []
        summary = {"team_a_wins": 0, "team_b_wins": 0, "draws": 0}
        for match_date, venue, gf, ga in rows:
            if venue == "H":    
                home, away, hg, ag = team_a, team_b, gf, ga
            else:               
                home, away, hg, ag = team_b, team_a, ga, gf
            matches.append({
                "date": match_date.isoformat(),
                "home_team": home, "away_team": away,
                "home_goals": hg, "away_goals": ag,
            })
            if gf > ga:
                summary["team_a_wins"] += 1
            elif gf < ga:
                summary["team_b_wins"] += 1
            else:
                summary["draws"] += 1

        return {"team_a": team_a, "team_b": team_b,
                "matches": matches, "summary": summary}




def form(team: str, n: int = 5, season: str = None) -> dict:
    team = resolve_team(team)
    
    sql = (f"{_CTE} SELECT match_date, opponent, venue, gf, ga FROM tm WHERE team=%s")
    params = [team]
    if season:
        season = resolve_season(season)
        sql += " AND season=%s"
        params.append(season)
    
    sql += " ORDER BY match_date DESC LIMIT %s"
    params.append(n)
    
    with _get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    
    if not rows:
        return {"error": f"No matches found for {team}" + (f" in season {season}" if season else "")}
    
    matches = []
    points = 0
    for match_date, opponent, venue, gf, ga in rows:
        result = "W" if gf > ga else "D" if gf == ga else "L"
        points += 3 if result == "W" else 1 if result == "D" else 0
        matches.append({
            "date": match_date.isoformat(),
            "opponent": opponent,
            "venue": venue,
            "goals_for": gf,
            "goals_against": ga,
            "result": result,
        })

    return {"team": team, "matches": matches, "points": points}
    
        
    
def team_record_between(team: str, start_date: str, end_date: str) -> dict:
    team = resolve_team(team)
    start_date = resolve_date(start_date)
    end_date = resolve_date(end_date)
    with _get_conn() as conn:
        row = conn.execute(
            f"{_CTE} SELECT {_AGG} FROM tm "
            "WHERE team=%s AND match_date BETWEEN %s AND %s",
            (team, start_date, end_date),
        ).fetchone()
        if row[0] == 0:
            return {"error": f"No matches found for {team} between {start_date} and {end_date}"}
        return _record(team, f"{start_date} to {end_date}", *row)