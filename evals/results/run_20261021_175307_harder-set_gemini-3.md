# Eval report

- eval set: harder-set
- model: gemini-3.5-flash-lite
- location: global
- timestamp: 20261021_175307
- questions: 1

## Results by category

| Category | Pass | Fail | Review | Infra error | Other error | Accuracy |
|---|---|---|---|---|---|---|
| robustness | 1 | 0 | 0 | 0 | 0 | 1/1 |
| **all** | 1 | 0 | 0 | 0 | 0 | **1/1** |

Accuracy = pass / (pass + fail). Review rows and infrastructure failures (429, 5xx, timeouts) are not counted as wrong.

## Tool choice, latency, cost

- Right tools on 1/1 completed questions
- Latency: p50 2.5s, p95 2.5s, max 2.5s
- Tokens: 2,073 input, 132 output (including thinking)
- Cost: pass --price-in and --price-out (USD per 1M tokens, from Google's pricing page) to estimate it
