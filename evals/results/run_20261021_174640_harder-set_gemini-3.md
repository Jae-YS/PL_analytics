# Eval report

- eval set: harder-set
- model: gemini-3.5-flash-lite
- location: global
- timestamp: 20261021_174640
- questions: 14

## Results by category

| Category | Pass | Fail | Review | Infra error | Other error | Accuracy |
|---|---|---|---|---|---|---|
| stats | 5 | 0 | 0 | 0 | 0 | 5/5 |
| robustness | 3 | 0 | 1 | 0 | 0 | 3/3 |
| unanswerable | 1 | 0 | 0 | 0 | 0 | 1/1 |
| docs | 3 | 0 | 0 | 0 | 0 | 3/3 |
| combined | 1 | 0 | 0 | 0 | 0 | 1/1 |
| **all** | 13 | 0 | 1 | 0 | 0 | **13/13** |

Accuracy = pass / (pass + fail). Review rows and infrastructure failures (429, 5xx, timeouts) are not counted as wrong.

## Tool choice, latency, cost

- Right tools on 14/14 completed questions
- Latency: p50 2.6s, p95 6.0s, max 6.4s
- Tokens: 56,064 input, 2,514 output (including thinking)
- Estimated cost: $0.0231 total, $0.0017 per question (at $0.3/M input, $2.5/M output)

## Needs attention

| ID | Status | Details |
|---|---|---|
| H05 | review | check by hand: The team name "United" is ambiguous as it can refer to Manchester United or West Ham Unite |
