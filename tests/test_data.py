"""Data-quality tests: raw CSVs first, then the loaded Postgres table.

Run with:  pytest tests/test_data.py -v
DB tests are skipped automatically if Postgres is not reachable.
"""
import os
import pytest

from helpers import ROOT, SEASONS, load_season, teams_in

pytestmark = pytest.mark.skipif(
    not all((ROOT / "data" / "raw" / f"{s}.csv").exists() for s in SEASONS),
    reason="season CSVs missing in data/raw (run scripts/download_data.sh)",
)


@pytest.mark.parametrize("season", SEASONS)
def test_csv_has_full_season(season):
    df = load_season(season)
    assert len(df) == 380
    assert len(teams_in(df)) == 20


@pytest.mark.parametrize("season", SEASONS)
def test_every_team_plays_38_games(season):
    df = load_season(season)
    for team in teams_in(df):
        n = int(((df["HomeTeam"] == team) | (df["AwayTeam"] == team)).sum())
        assert n == 38, f"{team} has {n} games in {season}"


@pytest.mark.parametrize("season", SEASONS)
def test_result_codes_match_goals(season):
    df = load_season(season)
    assert set(df["FTR"].unique()) <= {"H", "D", "A"}
    expected = df.apply(
        lambda r: "H" if r.FTHG > r.FTAG else "A" if r.FTHG < r.FTAG else "D",
        axis=1,
    )
    bad = df[df["FTR"] != expected]
    assert bad.empty, f"FTR disagrees with goals:\n{bad[['Date','HomeTeam','AwayTeam','FTHG','FTAG','FTR']]}"


@pytest.mark.parametrize("season", SEASONS)
def test_no_nulls_in_columns_the_tools_use(season):
    df = load_season(season)
    cols = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR",
            "Referee", "HS", "AS", "HST", "AST", "HY", "AY", "HR", "AR"]
    nulls = df[cols].isna().sum()
    assert nulls.sum() == 0, nulls[nulls > 0].to_dict()


# ---------- Postgres ----------

@pytest.fixture(scope="module")
def conn():
    psycopg = pytest.importorskip("psycopg")
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    url = os.getenv("DATABASE_URL", "postgresql://pl:pl@localhost:5433/pl")
    try:
        c = psycopg.connect(url, connect_timeout=3)
    except Exception as exc:  # DB not running
        pytest.skip(f"Postgres not reachable: {exc}")
    yield c
    c.close()


@pytest.mark.parametrize("season", SEASONS)
def test_db_row_count_and_goals_match_csv(conn, season):
    df = load_season(season)
    row = conn.execute(
        "SELECT count(*), sum(home_goals + away_goals) FROM matches WHERE season=%s",
        (season,),
    ).fetchone()
    assert row[0] == len(df)
    assert row[1] == int(df["FTHG"].sum() + df["FTAG"].sum())


@pytest.mark.parametrize("season", SEASONS)
def test_db_teams_match_csv(conn, season):
    db_teams = {r[0] for r in conn.execute(
        "SELECT DISTINCT home_team FROM matches WHERE season=%s", (season,))}
    assert db_teams == set(teams_in(load_season(season)))


def test_db_result_codes_valid(conn):
    codes = {r[0] for r in conn.execute("SELECT DISTINCT result FROM matches")}
    assert codes <= {"H", "D", "A"}
