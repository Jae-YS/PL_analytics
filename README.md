# PL Analytics Assistant

An agent that answers questions about Premier League results by combining
exact SQL analytics with retrieval over internal-style documents. Built with
Google ADK, Gemini on Vertex AI, and Postgres + pgvector.

**Status:** runs locally (Docker Postgres + Vertex AI). Not yet deployed.

## What it does

- **Structured analytics:** parameterized SQL tools over match results
  (standings, team records, head-to-head, home/away splits). The model never
  does arithmetic; it calls tools and explains the numbers they return.
- **Unstructured retrieval:** RAG over 12 synthetic scouting reports,
  briefings and memos stored in pgvector.
- **Agent:** a Google ADK agent (`pl_agent/agent.py`) that routes each
  question to the stats tools, document search, or both. It answers from
  documents only when the retrieved passages contain the answer, cites the
  source file for document facts, and declines otherwise.
- **Observability:** every tool call is logged with its name, arguments,
  duration and any error.

```
question -> agent (Gemini) -> stats tools   -> Postgres (matches)
                           -> search_documents -> embed query -> Postgres (doc_chunks)
         <- answer grounded in what the tools returned
```

## Design notes

- **Numbers come from SQL, never from the model.** That is what makes the
  answers checkable: the tests recompute every figure from the raw CSVs.
- **Similarity is not relevance.** Vector search always returns the nearest
  documents. In a real run, a question about a player's weekly wage (not in
  any document) matched that player's report at 0.703, higher than the
  correct match for an answerable question (0.664). So refusals are enforced
  by the agent's instructions and scored in the eval, not by a score cutoff.

## Project layout

```
pl_agent/        ADK agent definition and system instruction
src/tools/       stats.py (SQL tools), retrieval.py (pgvector search)
src/             config.py (model name), embeddings.py (Vertex embeddings),
                 tool_logging.py (tool-call callbacks),
                 eval_scoring.py (scoring and report)
scripts/         load_matches.py, ingest_docs.py, run_eval.py, check_model.py
data/docs/       12 synthetic scouting reports, briefings and memos
evals/           eval_set.jsonl (25 questions), harder_set.jsonl (14 questions),
                 doc_facts.md, results/
tests/           pytest suite (data, docs, stats, retrieval, eval set,
                 tool logging, scoring)
```

## Tools

| Tool | Purpose |
| --- | --- |
| `team_record` | W/D/L, goals and points for a team in a season |
| `league_table` | Full table for a season |
| `home_away_split` | Home vs. away record |
| `head_to_head` | Results between two teams, optionally per season |
| `form` | Last *n* results for a team |
| `team_record_between` | Record over a date range |
| `search_documents` | Vector search over the documents (optional `doc_type` filter) |

Team names and seasons are fuzzy-resolved (for example "Manchester City" to
"Man City", "25/26" to "2025/26"). Unknown names return a "did you mean"
message instead of a guess.

## Data

- **Match data:** [football-data.co.uk](https://www.football-data.co.uk/),
  seasons 2023/24, 2024/25 and 2025/26 (380 matches each). Not included in
  this repo. Check the site's terms of use, then download the CSVs:
  ```bash
  mkdir -p data/raw
  curl -o data/raw/2324.csv https://www.football-data.co.uk/mmz4281/2324/E0.csv
  curl -o data/raw/2425.csv https://www.football-data.co.uk/mmz4281/2425/E0.csv
  curl -o data/raw/2526.csv https://www.football-data.co.uk/mmz4281/2526/E0.csv
  ```
- **Documents:** `data/docs/` holds 12 synthetic documents dated August 2023
  to April 2026. Scouting targets play for invented clubs. Briefings name real
  Premier League opponents, but every tactical tendency and statistic in them
  is invented. See `data/docs/README.md`.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install google-adk "psycopg[binary]" pandas python-dotenv pytest

gcloud auth application-default login   # Vertex AI credentials, no API key needed

docker compose up -d                    # Postgres + pgvector on port 5433
python scripts/load_matches.py          # load match results
python -m scripts.ingest_docs           # embed and store the documents

adk web --port 8000                     # run the agent (from the repo root)
python -m pytest tests                  # run the tests
```

Postgres runs on port 5433 to avoid clashing with a local install.

### Configuration

Two `.env` files, both git-ignored. ADK reads the agent folder's file; the
scripts and tools read the root file.

`pl_agent/.env`:

| Variable | Value | Notes |
| --- | --- | --- |
| `GOOGLE_GENAI_USE_VERTEXAI` | `True` | Use Vertex AI, not an API key |
| `GOOGLE_CLOUD_PROJECT` | your project ID | |
| `GOOGLE_CLOUD_LOCATION` | `global` | The Gemini models were only served here in my tests |

Root `.env`:

| Variable | Default | Notes |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql://pl:pl@localhost:5433/pl` | Postgres connection |
| `AGENT_MODEL` | `gemini-3.5-flash-lite` | Model used by the agent |
| `EMBED_LOCATION` | `us-east4` | Region for the embedding calls |

`scripts/check_model.py` tests which models and regions your project can use.

## Evaluation

Two eval sets. Each row lists the tools that must and must not be called, the
strings the answer must contain, and whether a refusal is expected.

| Set | File | Questions |
| --- | --- | --- |
| Main | `evals/eval_set.jsonl` | 25: 9 stats, 7 docs, 3 combined, 6 unanswerable |
| Hard | `evals/harder_set.jsonl` | 14: typos, ambiguity, prompt injection, multi-document, multi-season |

Stats answers are checked against the raw CSVs and document answers against the
source files by `tests/test_eval_set.py`.

```bash
python -m scripts.run_eval --dry-run                                  # list questions, no model calls
python -m scripts.run_eval --price-in 0.30 --price-out 2.50           # main set, with a cost estimate
python -m scripts.run_eval --file evals/harder_set.jsonl              # hard set
python -m scripts.run_eval --ids S01,U01                              # a few rows
```

Each run writes a `.jsonl` record per question and a markdown report to
`evals/results/`, named with the set and model. Infrastructure failures (429,
5xx, timeouts) are retried, then reported separately and not counted as wrong
answers. All runs are kept in `evals/results/`.

### Results (21 October 2026)

`gemini-3.5-flash-lite` on the `global` endpoint, single runs:

| | Main set | Hard set |
| --- | --- | --- |
| Pass / fail | 24 / 0, plus 1 checked by hand (S06) | 13 / 0, plus 1 checked by hand (H05) |
| Right tools called | 25 of 25 | 14 of 14 |
| Latency p50 | 2.6 s | 2.5 s |
| Latency p95 / max | 24.2 s / 32.1 s | 6.8 s / 9.1 s |
| Tokens (in / out) | 66,286 / 3,056 | 62,538 / 2,832 |
| Estimated cost per question | $0.0011 | $0.0018 |

Costs use list prices of $0.30 per million input tokens and $2.50 per million
output tokens. Confirm against current Google pricing.

**Latency stalls.** In the first main-set run, three questions (U03, R01, R05)
took 32.1 s, 24.2 s and 17.7 s while the rest took about 2 to 3 s. Each of
those spent under a second inside its tool, so the delay is in the model call
or the client, not in the SQL or vector search. In three repeat runs the stalls
landed on different rows (S02 at 28.1 s, then R01 at 8.5 s, then C03 at
11.6 s), and the hard set never exceeded 6.4 s. That pattern fits transient API
behavior, but the cause is not isolated: the harness records total latency per
question, not per model call. p50 is the typical figure and the max is the
worst case.

### Consistency

Each set was run 3 more times on the same model and instructions
(`gemini-3.5-flash-lite`, `global`, 21 October 2026). All result files are in
`evals/results/`.

| | Run 1 | Run 2 | Run 3 |
| --- | --- | --- | --- |
| Main set (pass / fail / review) | 24 / 0 / 1 | 24 / 0 / 1 | 24 / 0 / 1 |
| Main set latency p50 / max | 2.4 s / 28.1 s | 2.4 s / 8.5 s | 2.3 s / 11.6 s |
| Hard set (pass / fail / review) | 12 / **1** / 1 | 13 / 0 / 1 | 13 / 0 / 1 |
| Hard set latency p50 / max | 2.7 s / 5.5 s | 2.5 s / 5.8 s | 2.6 s / 6.4 s |

38 of the 39 questions had the same status in all three runs. The one that
changed is **H06** ("How did Arsenal do this season?"). The instructions say to
state that there is no data for the current season and answer for 2025/26.
H06 failed in the first hard-set run and passed in the other two. I then ran
H06 alone 10 times: 9 passed and 1 failed, so 2 failures in 13 runs overall.

Both failing answers had the right numbers (85 points) and labelled the season
2025/26, and both mentioned that the data ends in May 2026. Neither said
outright that the current season is not covered, which is what the check
requires. I kept the check strict instead of widening it to accept the
cutoff wording, and I did not change the instructions. H06 is therefore a
known flaky row, roughly 15% failure on this sample (13 runs, too few for a
tight estimate).

S06 and H05 are reviewed by hand because the automatic check cannot judge
them. S06 was checked against the raw CSVs in all three repeat runs and the
head-to-head results were correct each time.

### How the results changed

| Stage | Main set | Hard set |
| --- | --- | --- |
| First run | 25/25 | 11/13, 1 for hand review |
| After instruction changes | 1 failure (U05) | 12/13 |
| After fixes | clean | 13/13, H05 passed by hand |

Not every failure was the agent's fault, and the harness separates the two:

- **U05 was a real agent error.** The agent turned a "no data" tool error into
  "0 points". I fixed it in the instructions and tightened the check.
- **H06 and U04 were grader errors.** Correct answers failed because the
  expected-phrase lists were too narrow. I fixed the eval row and the scorer
  and recorded the reason.

### Retrieval

Retrieval is tested separately by `tests/test_retrieval.py`, which calls
Vertex AI and so is opt-in:

```bash
RUN_EMBED_TESTS=1 python -m pytest tests/test_retrieval.py -v -s
```

It prints top-1 and top-3 hit rates over the questions in `evals/doc_facts.md`:
top-1 [fill in], top-3 [fill in].

### Caveats

- The main set was used to tune the agent's instructions, so it is a
  regression check, not an unbiased test. The hard set was also tuned against
  after its first run, so it is a development set too.
- H06's check was widened after a correct answer failed on wording.
- 25 + 14 questions, single runs, one model. A perfect score here is not proof
  of robustness.
- Consistency was checked with 3 runs per set (see above). H06 is flaky and
  was left failing when it fails: its check was not loosened a second time.

### Fresh questions (untuned)

`evals/fresh_set.jsonl` has 8 questions I wrote after the agent and checks were
frozen: 3 stats, 1 combined, 2 docs, 2 unanswerable, in casual wording with
typos. Expected answers were computed from the raw CSVs and the source
documents, not from the agent's output. Single run, `gemini-3.5-flash-lite`.

| | Result |
| --- | --- |
| Automatic | 7 of 8 pass |
| After reading answers | [8 of 8 / fill in] |
| Right tools | 8 of 8 |
| Latency p50 / max | 3.2 s / 4.0 s |
| Tokens (in / out) | 20,627 / 1,292 |
| Estimated cost per question | $0.0012 |

The one automatic failure, F03 (Spurs vs West Ham), was a grader error: the
answer gave the correct counts (2 wins each, 2 draws) but my phrase list
expected a word like "level". I did not edit the row.

Four rows (F01 to F03 and F08) were run once in a partial run before the full
set existed, so they are not fully blind. F04 to F07 were run for the first
time in this run and passed 4 of 4. Eight questions and one run cannot support
a percentage. The checks are substring and regex matches, so passes were read
by hand.

## Limitations

- Team- and match-level data only. No player statistics, so questions about
  top scorers cannot be answered, and the agent should say so.
- Match data ends in May 2026. There is no 2026/27 data, and the agent does
  not predict results.
- Documents are synthetic.
- Two rows (S06, H05) are checked by hand because the automatic check cannot
  judge them.
- Latency has occasional stalls of 8 to 32 s on single questions, on different
  rows in different runs. The cause is not yet isolated (see Evaluation).
- H06 fails on about 15% of runs on this sample (2 of 13), by not saying
  outright that the current season has no data.
- The `global` endpoint does not pin requests to one region. For regulated
  data you would use a regional endpoint and choose a model by where it is
  available.