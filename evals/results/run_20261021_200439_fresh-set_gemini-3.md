# Eval report

- eval set: fresh-set
- model: gemini-3.5-flash-lite
- location: global
- timestamp: 20261021_200439
- questions: 8

## Results by category

| Category | Pass | Fail | Review | Infra error | Other error | Accuracy |
|---|---|---|---|---|---|---|
| stats | 2 | 1 | 0 | 0 | 0 | 2/3 |
| combined | 1 | 0 | 0 | 0 | 0 | 1/1 |
| docs | 2 | 0 | 0 | 0 | 0 | 2/2 |
| unanswerable | 2 | 0 | 0 | 0 | 0 | 2/2 |
| **all** | 7 | 1 | 0 | 0 | 0 | **7/8** |

Accuracy = pass / (pass + fail). Review rows and infrastructure failures (429, 5xx, timeouts) are not counted as wrong.

## Tool choice, latency, cost

- Right tools on 8/8 completed questions
- Latency: p50 3.2s, p95 4.0s, max 4.0s
- Tokens: 20,627 input, 1,292 output (including thinking)
- Estimated cost: $0.0094 total, $0.0012 per question (at $0.3/M input, $2.5/M output)

## Needs attention

| ID | Status | Details |
|---|---|---|
| F03 | fail | none of expected_any found |
