"""Run the eval set against the ADK agent and write a report.

    python -m scripts.run_eval --dry-run                 # list questions, no model calls
    python -m scripts.run_eval --ids S01,U01              # a few questions
    python -m scripts.run_eval --category stats           # one category
    python -m scripts.run_eval --price-in 1.5 --price-out 9   # all, with a cost estimate

Writes evals/results/run_<time>_<model>.jsonl (one record per question) and a
matching .md report. Run from the repo root with the venv active and
Postgres running.

Infrastructure failures (429, 5xx, timeouts) are retried a little, then
recorded as infra_error. They are reported separately and are not counted as
wrong answers.
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  

load_dotenv(ROOT / "pl_agent" / ".env")
load_dotenv(ROOT / ".env")

from src.eval_scoring import classify_error, score_row, summarize 

# EVAL_SET = ROOT / "evals" / "eval_set.jsonl"
EVAL_SET = ROOT / "evals" / "harder_set.jsonl"
RESULTS = ROOT / "evals" / "results"
APP_NAME = "pl_agent"        
USER_ID = "eval"


def load_rows(args):
    rows = [json.loads(line) for line in EVAL_SET.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.ids:
        wanted = {i.strip() for i in args.ids.split(",")}
        rows = [r for r in rows if r["id"] in wanted]
    if args.category:
        rows = [r for r in rows if r["category"] == args.category]
    if args.limit:
        rows = rows[: args.limit]
    return rows


def _function_call_names(event):
    """Tool names the model asked for in this event (a cross-check on the callbacks)."""
    names = []
    parts = getattr(getattr(event, "content", None), "parts", None) or []
    for p in parts:
        fc = getattr(p, "function_call", None)
        if fc is not None and getattr(fc, "name", None):
            names.append(fc.name)
    return names


async def ask_once(runner, types, question):
    from src.tool_logging import start_collecting

    session = await runner.session_service.create_session(app_name=APP_NAME, user_id=USER_ID)
    message = types.Content(role="user", parts=[types.Part(text=question)])

    calls = start_collecting()
    out = {"answer": "", "event_tools": [], "input_tokens": 0, "output_tokens": 0,
           "thought_tokens": 0, "model_calls": 0, "error": None, "error_kind": None}
    start = time.perf_counter()
    try:
        async for event in runner.run_async(user_id=USER_ID, session_id=session.id, new_message=message):
            usage = getattr(event, "usage_metadata", None)
            if usage:
                out["model_calls"] += 1
                out["input_tokens"] += getattr(usage, "prompt_token_count", 0) or 0
                out["output_tokens"] += getattr(usage, "candidates_token_count", 0) or 0
                out["thought_tokens"] += getattr(usage, "thoughts_token_count", 0) or 0
            out["event_tools"] += _function_call_names(event)
            if event.is_final_response() and event.content and event.content.parts:
                out["answer"] = "".join(p.text for p in event.content.parts if getattr(p, "text", None))
    except Exception as exc:  # noqa: BLE001  (we classify and report it)
        out["error"] = f"{type(exc).__name__}: {exc}"
        out["error_kind"] = classify_error(out["error"])
    out["latency_s"] = round(time.perf_counter() - start, 2)
    out["tool_calls"] = calls
    return out


async def ask_with_retries(runner, types, question, retries, backoff):
    attempts = 0
    while True:
        attempts += 1
        res = await ask_once(runner, types, question)
        if res["error_kind"] != "infra" or attempts > retries:
            res["attempts"] = attempts
            return res
        wait = backoff * 2 ** (attempts - 1)
        print(f"    infra error, retrying in {wait:.0f}s ({res['error'][:70]})")
        await asyncio.sleep(wait)


async def run(rows, args):
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    from pl_agent.agent import root_agent
    from src.config import MODEL

    runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)
    results = []
    for i, row in enumerate(rows, start=1):
        res = await ask_with_retries(runner, types, row["question"], args.retries, args.backoff)
        tools = list(dict.fromkeys([c["tool"] for c in res["tool_calls"]] + res["event_tools"]))
        scored = score_row(row, res["answer"], tools, res["error_kind"])
        rec = {"id": row["id"], "category": row["category"], "question": row["question"],
               "answer": res["answer"], "tools": tools, "tool_calls": res["tool_calls"],
               "latency_s": res["latency_s"], "input_tokens": res["input_tokens"],
               "output_tokens": res["output_tokens"], "thought_tokens": res["thought_tokens"],
               "model_calls": res["model_calls"], "attempts": res["attempts"],
               "error": res["error"], **scored}
        results.append(rec)
        why = "; ".join(scored["reasons"])
        print(f"[{i:>2}/{len(rows)}] {row['id']:<4} {scored['status']:<11} "
              f"{res['latency_s']:>5.1f}s  tools={','.join(tools) or '-'}  {why}")
        if i < len(rows):
            await asyncio.sleep(args.sleep)
    return results, MODEL


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ids", help="comma-separated row ids, e.g. S01,U01")
    ap.add_argument("--category", choices=["stats", "docs", "combined", "unanswerable"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--sleep", type=float, default=2.0, help="seconds between questions (eases 429s)")
    ap.add_argument("--retries", type=int, default=1, help="extra attempts after an infra error")
    ap.add_argument("--backoff", type=float, default=10.0, help="first retry wait, doubles each time")
    ap.add_argument("--price-in", type=float, help="USD per 1M input tokens")
    ap.add_argument("--price-out", type=float, help="USD per 1M output tokens")
    ap.add_argument("--dry-run", action="store_true", help="list the selected questions and exit")
    args = ap.parse_args()

    rows = load_rows(args)
    if not rows:
        sys.exit("No rows selected.")
    if args.dry_run:
        for r in rows:
            print(f"{r['id']:<4} {r['category']:<12} tools={r['expected_tools']}  {r['question']}")
        print(f"\n{len(rows)} questions, no model calls made.")
        return

    results, model = asyncio.run(run(rows, args))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    RESULTS.mkdir(parents=True, exist_ok=True)
    stem = RESULTS / f"run_{stamp}_{re.sub(r'[^A-Za-z0-9.-]', '', model)}"
    stem.with_suffix(".jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in results) + "\n", encoding="utf-8")
    meta = {"model": model, "location": os.getenv("GOOGLE_CLOUD_LOCATION"), "timestamp": stamp}
    report = summarize(results, meta, args.price_in, args.price_out)
    stem.with_suffix(".md").write_text(report, encoding="utf-8")
    print("\n" + report)
    print(f"\nSaved {stem.name}.jsonl and {stem.name}.md in {RESULTS}")


if __name__ == "__main__":
    main()
