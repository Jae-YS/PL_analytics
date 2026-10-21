"""Scoring and reporting for the agent eval (no model calls in here).

score_row() compares one answer with one row of evals/eval_set.jsonl.
summarize() turns a list of scored results into a markdown report.

Statuses:
  pass          right tools, right values (or a correct refusal).
                A row may also list expected_tools_any: at least one must be called.
  fail          wrong tools, wrong or missing values, or no refusal when needed
  review        tools were right but the row has no machine-checkable values
  infra_error   429 / 5xx / timeout after all retries. NOT counted as wrong.
  error         any other exception while running the question
"""
import re

REFUSAL_PATTERNS = [
    r"\bnot (in|included in|contained in|found in|covered (in|by))\b",
    r"\b(do(es)? not|don't|doesn't|did not|didn't) (contain|include|have|provide|mention|specify|list|cover|name|"
    r"state|say|report|give|show|indicate|detail|identify|supply|record|reveal|describe|offer|capture|track)\b",
    r"\bno (information|data|record|records|matches|mention|figures?|numbers?|counts?|details|statistics|stats)\b",
    r"\b(nothing|none) (about|on|in|of)\b",
    r"\b(cannot|can't|can not|unable to|couldn't|could not)\b",
    r"\b(isn't|is not|aren't|are not|wasn't|weren't) (available|provided|stated|specified|included|mentioned|named)\b",
    r"\bnot (available|provided|stated|specified|mentioned)\b",
]
_REFUSAL = [re.compile(p, re.I) for p in REFUSAL_PATTERNS]

_INFRA = re.compile(
    r"\b429\b|RESOURCE_EXHAUSTED|ResourceExhausted|\b503\b|UNAVAILABLE|"
    r"\b500\b.*INTERNAL|DEADLINE_EXCEEDED|timed?[ -]?out|ServerError",
    re.I,
)


def is_refusal(answer: str) -> bool:
    return any(p.search(answer or "") for p in _REFUSAL)


def classify_error(text: str) -> str:
    """'infra' for rate limits, outages and timeouts; otherwise 'error'."""
    return "infra" if _INFRA.search(text or "") else "error"


def score_row(row: dict, answer: str, tools_called, error_kind=None) -> dict:
    """Score one answer. error_kind: None, 'infra' or 'error'."""
    if error_kind == "infra":
        return {"status": "infra_error", "tool_ok": None, "reasons": ["infrastructure failure"]}
    if error_kind == "error":
        return {"status": "error", "tool_ok": None, "reasons": ["exception while running"]}

    called = set(tools_called or [])
    low = (answer or "").lower()
    reasons = []

    missing = [t for t in row["expected_tools"] if t not in called]
    forbidden = [t for t in row["forbidden_tools"] if t in called]
    any_of = row.get("expected_tools_any", [])           # optional: at least one of these
    any_missing = bool(any_of) and not (set(any_of) & called)
    tool_ok = not missing and not forbidden and not any_missing
    reasons += [f"missing tool {t}" for t in missing]
    reasons += [f"forbidden tool {t} called" for t in forbidden]
    if any_missing:
        reasons.append(f"none of {any_of} called")

    values_ok = True
    for s in row["expected_all"]:
        if s.lower() not in low:
            values_ok = False
            reasons.append(f"missing '{s}'")
    if row["expected_any"] and not any(s.lower() in low for s in row["expected_any"]):
        values_ok = False
        reasons.append("none of expected_any found")
    for s in row["must_not_contain"]:
        if s.lower() in low:
            values_ok = False
            reasons.append(f"contains forbidden '{s}'")
    if row["refusal"] and not is_refusal(answer):
        values_ok = False
        reasons.append("no refusal detected")

    machine_checkable = bool(row["expected_all"] or row["expected_any"] or row["refusal"])
    if not tool_ok or not values_ok:
        status = "fail"
    elif not machine_checkable:
        status = "review"
    else:
        status = "pass"
    return {"status": status, "tool_ok": tool_ok, "reasons": reasons}


def _pct(values, p):
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, max(0, round(p / 100 * (len(s) - 1))))]


def summarize(results, meta=None, price_in=None, price_out=None) -> str:
    """Markdown report. Prices are USD per 1M tokens (optional)."""
    meta = meta or {}
    cats = []
    for r in results:
        if r["category"] not in cats:
            cats.append(r["category"])

    def counts(rs):
        c = {k: sum(1 for r in rs if r["status"] == k)
             for k in ("pass", "fail", "review", "infra_error", "error")}
        graded = c["pass"] + c["fail"]
        c["accuracy"] = f"{c['pass']}/{graded}" if graded else "n/a"
        return c

    total = counts(results)
    done = [r for r in results if r["status"] in ("pass", "fail", "review")]
    lat = [r["latency_s"] for r in done]
    tool_scored = [r for r in done if r["tool_ok"] is not None]
    tool_ok = sum(1 for r in tool_scored if r["tool_ok"])
    in_tok = sum(r.get("input_tokens", 0) for r in results)
    out_tok = sum(r.get("output_tokens", 0) + r.get("thought_tokens", 0) for r in results)

    out = ["# Eval report", ""]
    for k in ("eval set", "model", "location", "timestamp"):
        if meta.get(k):
            out.append(f"- {k}: {meta[k]}")
    out += [f"- questions: {len(results)}", ""]
    out += ["## Results by category", "",
            "| Category | Pass | Fail | Review | Infra error | Other error | Accuracy |",
            "|---|---|---|---|---|---|---|"]
    for c in cats:
        x = counts([r for r in results if r["category"] == c])
        out.append(f"| {c} | {x['pass']} | {x['fail']} | {x['review']} | "
                   f"{x['infra_error']} | {x['error']} | {x['accuracy']} |")
    out.append(f"| **all** | {total['pass']} | {total['fail']} | {total['review']} | "
               f"{total['infra_error']} | {total['error']} | **{total['accuracy']}** |")
    out += ["", "Accuracy = pass / (pass + fail). Review rows and infrastructure "
            "failures (429, 5xx, timeouts) are not counted as wrong.", ""]

    out += ["## Tool choice, latency, cost", ""]
    out.append(f"- Right tools on {tool_ok}/{len(tool_scored)} completed questions")
    if lat:
        out.append(f"- Latency: p50 {_pct(lat, 50):.1f}s, p95 {_pct(lat, 95):.1f}s, max {max(lat):.1f}s")
    out.append(f"- Tokens: {in_tok:,} input, {out_tok:,} output (including thinking)")
    if price_in is not None and price_out is not None and results:
        cost = in_tok * price_in / 1e6 + out_tok * price_out / 1e6
        out.append(f"- Estimated cost: ${cost:.4f} total, ${cost / len(results):.4f} per question "
                   f"(at ${price_in}/M input, ${price_out}/M output)")
    else:
        out.append("- Cost: pass --price-in and --price-out (USD per 1M tokens, "
                   "from Google's pricing page) to estimate it")
    out.append("")

    bad = [r for r in results if r["status"] in ("fail", "infra_error", "error", "review")]
    if bad:
        out += ["## Needs attention", "", "| ID | Status | Details |", "|---|---|---|"]
        for r in bad:
            detail = "; ".join(r["reasons"]) if r["reasons"] else ""
            if "no refusal detected" in r["reasons"]:
                detail += " | answer: " + r.get("answer", "")[:110].replace("\n", " ")
            if r["status"] == "review":
                detail = "check by hand: " + (r.get("answer", "")[:90].replace("\n", " "))
            out.append(f"| {r['id']} | {r['status']} | {detail} |")
        out.append("")
    return "\n".join(out)