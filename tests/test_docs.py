"""Tests for the synthetic documents and evals/doc_facts.md.

These need only the files on disk (and the CSVs for fixture alignment).
Run with:  pytest tests/test_docs.py -v
"""
import re
from datetime import datetime

import pandas as pd
import pytest

from helpers import DOCS, FACTS, SEASONS, load_season, team_games

DOC_FILES = sorted(p for p in DOCS.glob("[0-9][0-9]_*.md"))
pytestmark = pytest.mark.skipif(not DOC_FILES, reason="no docs in data/docs")

FORBIDDEN_WORDS = ["fictional", "synthetic", "demo"]
TEAM_MAP = {"Aston Villa": "Aston Villa", "Newcastle United": "Newcastle",
            "Brighton & Hove Albion": "Brighton", "Wolverhampton Wanderers": "Wolves"}


def parse(path):
    text = path.read_text(encoding="utf-8")
    title = re.search(r"^###\s*(.+)$", text, re.M).group(1).strip()
    date_s = re.search(r"\*\*Date:\*\*\s*(\d{1,2}\s+\w+\s+\d{4})", text).group(1)
    body = text.split("**Recipient:**")[-1] if "**Recipient:**" in text else text
    body = re.sub(r"^\*\*(Audience|Target):\*\*.*$", "", body, flags=re.M)
    return {"text": text, "title": title,
            "date": datetime.strptime(date_s, "%d %B %Y"), "body": body}


DOCS_PARSED = {p.name: parse(p) for p in DOC_FILES}


def test_twelve_docs_with_expected_mix():
    assert len(DOC_FILES) == 12
    kinds = [re.match(r"\d\d_(scouting|briefing|memo)_", p.name) for p in DOC_FILES]
    assert all(kinds), "file names must look like 01_scouting_name.md"
    counts = {k: sum(1 for m in kinds if m.group(1) == k) for k in ("scouting", "briefing", "memo")}
    assert counts == {"scouting": 5, "briefing": 4, "memo": 3}


def test_dates_in_range_and_unique():
    dates = [d["date"] for d in DOCS_PARSED.values()]
    assert min(dates) >= datetime(2023, 8, 1)
    assert max(dates) <= datetime(2026, 10, 20), "no future-dated docs"
    assert len(set(dates)) == len(dates), "every doc needs a distinct date"


def test_four_docs_per_season():
    def season_of(d):
        y = d.year if d.month >= 8 else d.year - 1
        return y
    counts = {}
    for d in DOCS_PARSED.values():
        counts[season_of(d["date"])] = counts.get(season_of(d["date"]), 0) + 1
    assert counts == {2023: 4, 2024: 4, 2025: 4}


@pytest.mark.parametrize("name", [p.name for p in DOC_FILES])
def test_no_self_labelling_words(name):
    low = DOCS_PARSED[name]["text"].lower()
    for w in FORBIDDEN_WORDS:
        assert w not in low, f"'{w}' found in {name}"

@pytest.mark.parametrize("name", [p.name for p in DOC_FILES])
def test_body_length_is_reasonable(name):
    words = len(DOCS_PARSED[name]["body"].split())
    assert 120 <= words <= 300, f"{name} has {words} words"


def _matches_with_scores_in_briefings():
    pat = re.compile(r"\b\d\s*[-–]\s*\d\b")
    bad = []
    for n, d in DOCS_PARSED.items():
        if "briefing" in n:
            # formations like 4-4-2 are allowed; scorelines are two digits
            for m in re.finditer(r"(?<![\d-])\d\s*[-–]\s*\d(?![\d-])", d["body"]):
                bad.append((n, m.group(0)))
    return bad


def test_briefings_contain_no_scorelines():
    assert _matches_with_scores_in_briefings() == []


# ---------- briefing dates line up with real fixtures ----------

def _briefings():
    out = []
    for n, d in DOCS_PARSED.items():
        m = re.match(r"Pre-Match Briefing:\s*(.+?)\s*\(Matchday\s*(\d+)\)", d["title"])
        if m:
            out.append((n, TEAM_MAP[m.group(1)], int(m.group(2)), d["date"]))
    return out


@pytest.mark.parametrize("name,team,matchday,date", _briefings())
def test_briefing_precedes_the_matchday_fixture(name, team, matchday, date):
    season = next((s for s in SEASONS
                   if load_season(s)["Date"].min() <= pd.Timestamp(date) <= load_season(s)["Date"].max()), None)
    assert season, f"{name}: no season in the data covers {date.date()}"
    games = team_games(load_season(season), team)
    nxt = games.iloc[matchday - 1]
    assert nxt["Date"] > pd.Timestamp(date), (
        f"{name}: {team}'s game {matchday} is on {nxt['Date'].date()}, "
        f"not after the briefing date {date.date()}")
    if matchday > 1:
        prev = games.iloc[matchday - 2]
        assert prev["Date"] <= pd.Timestamp(date), (
            f"{name}: game {matchday - 1} is on {prev['Date'].date()}, after the briefing")


# ---------- doc_facts.md matches the documents ----------

def _fact_rows():
    if not FACTS.exists():
        return []
    rows = []
    for line in FACTS.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and re.match(r"^[DX]\d\d$", cells[0]):
            rows.append((cells[0], cells[1], cells[3]))
    return rows


FACT_ROWS = _fact_rows()


@pytest.mark.skipif(not FACT_ROWS, reason="evals/doc_facts.md not found")
@pytest.mark.parametrize("fid,source,answer", FACT_ROWS)
def test_fact_source_exists_and_numeric_answer_in_text(fid, source, answer):
    assert (DOCS / source).exists(), f"{fid}: {source} not found in data/docs"
    if re.match(r"^[€$]?\d", answer):
        lead = re.split(r"\s\(", answer)[0].strip()
        assert lead in DOCS_PARSED[source]["text"], (
            f"{fid}: '{lead}' not found in {source}")
