# Eval report

- eval set: eval-set
- model: gemini-3.5-flash-lite
- location: global
- timestamp: 20261021_173918
- questions: 25

## Results by category

| Category | Pass | Fail | Review | Infra error | Other error | Accuracy |
|---|---|---|---|---|---|---|
| stats | 8 | 0 | 1 | 0 | 0 | 8/8 |
| docs | 7 | 0 | 0 | 0 | 0 | 7/7 |
| combined | 3 | 0 | 0 | 0 | 0 | 3/3 |
| unanswerable | 6 | 0 | 0 | 0 | 0 | 6/6 |
| **all** | 24 | 0 | 1 | 0 | 0 | **24/24** |

Accuracy = pass / (pass + fail). Review rows and infrastructure failures (429, 5xx, timeouts) are not counted as wrong.

## Tool choice, latency, cost

- Right tools on 25/25 completed questions
- Latency: p50 2.4s, p95 10.9s, max 28.1s
- Tokens: 66,368 input, 3,028 output (including thinking)
- Estimated cost: $0.0275 total, $0.0011 per question (at $0.3/M input, $2.5/M output)

## Needs attention

| ID | Status | Details |
|---|---|---|
| S06 | review | check by hand: **Head-to-Head Record: Man City vs Arsenal (Last Three Seasons: 2023/24 – 2025/26)**  ###  |
