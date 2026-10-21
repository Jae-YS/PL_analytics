"""Per-call tool logging for the ADK agent.

Attach to an agent with:

    from src.tool_logging import before_tool, after_tool
    Agent(..., before_tool_callback=before_tool, after_tool_callback=after_tool)

Every tool call then logs its name, arguments, duration and any error. The
eval runner also collects the records for each question with
start_collecting().

Both callbacks return None, which ADK treats as "leave the call and the
result unchanged". Callbacks are set per LlmAgent, so a sub-agent needs the
same two lines.
"""
import contextvars
import json
import logging
import time

log = logging.getLogger("pl_agent.tools")

_collector = contextvars.ContextVar("tool_call_collector", default=None)
_starts: dict = {}


def start_collecting() -> list:
    """Begin collecting tool-call records for the current task; returns the list."""
    calls: list = []
    _collector.set(calls)
    return calls


def _key(tool, tool_context) -> str:
    return getattr(tool_context, "function_call_id", None) or getattr(tool, "name", "tool")


def _error_of(response):
    """The tools return {"error": "..."} (or a list holding one) on failure."""
    if isinstance(response, dict):
        return response.get("error")
    if isinstance(response, list) and response and isinstance(response[0], dict):
        return response[0].get("error")
    return None


def before_tool(tool, args, tool_context):
    _starts.setdefault(_key(tool, tool_context), []).append(time.perf_counter())
    return None


def after_tool(tool, args, tool_context, tool_response):
    key = _key(tool, tool_context)
    started = _starts.get(key)
    duration_ms = None
    if started:
        duration_ms = round((time.perf_counter() - started.pop()) * 1000, 1)
        if not started:
            del _starts[key]

    record = {
        "tool": getattr(tool, "name", str(tool)),
        "args": json.loads(json.dumps(dict(args or {}), default=str)),
        "duration_ms": duration_ms,
        "error": _error_of(tool_response),
        "response_preview": json.dumps(tool_response, default=str)[:300],
    }
    calls = _collector.get()
    if calls is not None:
        calls.append(record)
    log.info("tool=%s args=%s ms=%s error=%s",
             record["tool"], record["args"], duration_ms, record["error"])
    return None
