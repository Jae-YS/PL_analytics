# Eval report

- eval set: harder-set
- model: gemini-3.5-flash-lite
- location: global
- timestamp: 20261021_175313
- questions: 1

## Results by category

| Category | Pass | Fail | Review | Infra error | Other error | Accuracy |
|---|---|---|---|---|---|---|
| robustness | 0 | 1 | 0 | 0 | 0 | 0/1 |
| **all** | 0 | 1 | 0 | 0 | 0 | **0/1** |

Accuracy = pass / (pass + fail). Review rows and infrastructure failures (429, 5xx, timeouts) are not counted as wrong.

## Tool choice, latency, cost

- Right tools on 1/1 completed questions
- Latency: p50 2.7s, p95 2.7s, max 2.7s
- Tokens: 2,073 input, 152 output (including thinking)
- Cost: pass --price-in and --price-out (USD per 1M tokens, from Google's pricing page) to estimate it

## Needs attention

| ID | Status | Details |
|---|---|---|
| H06 | fail | none of expected_any found |
