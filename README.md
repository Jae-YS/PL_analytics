# PL Analytics Assistant

A multi-agent assistant that answers questions about Premier League
results by combining exact SQL analytics with retrieval over internal-style
documents. Built on Google Cloud (Vertex AI, Cloud Run, Cloud SQL).


## What it does

- **Structured analytics:** parameterized SQL tools over match results
  (standings, team records, head-to-head, home/away splits). The LLM never
  does arithmetic; it calls tools and explains the returned numbers.
- **Unstructured retrieval:** RAG over 12 synthetic scouting and briefing
  documents stored in pgvector.
- **Multi-agent orchestration:** 

## Data

- **Match data:** [football-data.co.uk](https://www.football-data.co.uk/),
  seasons [2023/24, 2024/25, 2025/26]. Not included in this repo.
- **Documents:** `data/docs/` contains synthetic documents (see its README).

## Quickstart

```bash
docker compose up -d
python scripts/load_matches.py
```

Postgres runs on port 5433 to avoid clashing with a local install.

## Evaluation

Accuracy on a [N]-question suite with ground truth from SQL and the
planted facts in `evals/doc_facts.md`. Results: [fill in once measured].

## Limitations

Team- and match-level data only. No player statistics. Documents are
synthetic.