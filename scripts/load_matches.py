import glob, os
import pandas as pd
import psycopg

COLS = ["Date","HomeTeam","AwayTeam","FTHG","FTAG","FTR","HTHG","HTAG",
        "Referee","HS","AS","HST","AST","HF","AF","HC","AC","HY","AY","HR","AR"]

DDL = """
DROP TABLE IF EXISTS matches;
CREATE TABLE matches (
  id SERIAL PRIMARY KEY,
  season TEXT, match_date DATE,
  home_team TEXT, away_team TEXT,
  home_goals INT, away_goals INT, result CHAR(1),
  ht_home_goals INT, ht_away_goals INT, referee TEXT,
  home_shots INT, away_shots INT, home_sot INT, away_sot INT,
  home_fouls INT, away_fouls INT, home_corners INT, away_corners INT,
  home_yellow INT, away_yellow INT, home_red INT, away_red INT
);
"""

frames = []
for path in sorted(glob.glob("data/raw/*.csv")):
    season = os.path.basename(path).replace(".csv", "")
    df = pd.read_csv(path, encoding="latin-1")  
    df = df.dropna(subset=["HomeTeam", "FTHG"]) 
    df = df[[c for c in COLS if c in df.columns]].copy()
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True)
    df.insert(0, "season", season)
    frames.append(df)

all_df = pd.concat(frames, ignore_index=True)
all_df = all_df.astype(object).where(all_df.notna(), None)

with psycopg.connect("postgresql://pl:pl@localhost:5433/pl") as conn:
    conn.execute(DDL)
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO matches (season, match_date, home_team, away_team,
               home_goals, away_goals, result, ht_home_goals, ht_away_goals, referee,
               home_shots, away_shots, home_sot, away_sot, home_fouls, away_fouls,
               home_corners, away_corners, home_yellow, away_yellow, home_red, away_red)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            all_df[["season","Date","HomeTeam","AwayTeam","FTHG","FTAG","FTR","HTHG","HTAG",
                    "Referee","HS","AS","HST","AST","HF","AF","HC","AC","HY","AY","HR","AR"]]
              .itertuples(index=False, name=None),
        )
    conn.commit()
print(f"Loaded {len(all_df)} matches")