import logging
import time
import uuid
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, status
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel, StringConstraints
from typing import Annotated

from pl_agent.agent import root_agent
from src.config import MODEL
from src.tool_logging import start_collecting

APP_NAME = "pl_agent"
DEFAULT_USER_ID = "default_user"

app = FastAPI(title="PL Analytics API")
runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)

logger = logging.getLogger("ask_service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class AskRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]


class AskResponse(BaseModel):
    id: str
    question: str
    answer: str
    tools: List[str]
    tool_calls: List[Dict[str, Any]]
    latency_s: float
    input_tokens: int
    output_tokens: int
    thought_tokens: int
    model_calls: int
    cost_estimate_usd: float | None = None
    error: Optional[str] = None


def _function_call_names(event) -> List[str]:
    """Tool names the model asked for in this event (cross-check on callbacks)."""
    names = []
    parts = getattr(getattr(event, "content", None), "parts", None) or []
    for p in parts:
        fc = getattr(p, "function_call", None)
        if fc is not None and getattr(fc, "name", None):
            names.append(fc.name)
    return names


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL}


@app.post("/ask", response_model=AskResponse)
async def ask_endpoint(payload: AskRequest):
    request_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    question = payload.question

    logger.info(
        "Request started: request_id=%s question_length=%d",
        request_id,
        len(question),
    )

    session = await runner.session_service.create_session(
        app_name=APP_NAME,
        user_id=DEFAULT_USER_ID,
    )

    message = types.Content(role="user", parts=[types.Part(text=question)])
    calls = start_collecting()

    res = {
        "answer": "",
        "input_tokens": 0,
        "output_tokens": 0,
        "thought_tokens": 0,
        "model_calls": 0,
        "event_tools": [],
    }

    try:
        async for event in runner.run_async(
            user_id=DEFAULT_USER_ID,
            session_id=session.id,
            new_message=message,
        ):
            usage = getattr(event, "usage_metadata", None)
            if usage:
                res["model_calls"] += 1
                res["input_tokens"] += getattr(usage, "prompt_token_count", 0) or 0
                res["output_tokens"] += getattr(usage, "candidates_token_count", 0) or 0
                res["thought_tokens"] += getattr(usage, "thoughts_token_count", 0) or 0

            res["event_tools"].extend(_function_call_names(event))

            if event.is_final_response() and event.content and event.content.parts:
                res["answer"] = "".join(
                    p.text for p in event.content.parts if getattr(p, "text", None)
                )

    except HTTPException:
        raise
    except Exception as exc:
        latency_s = round(time.perf_counter() - start_time, 3)
        logger.exception(
            "Request failed: request_id=%s latency_sec=%.3f error=%s",
            request_id,
            latency_s,
            type(exc).__name__,
        )

        err_msg = f"{type(exc).__name__}: {exc}".lower()

        if any(term in err_msg for term in ["rate limit", "resource exhausted", "429", "503"]):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": "Upstream service temporarily overloaded. Please retry later.",
                    "request_id": request_id,
                },
                headers={"Retry-After": "30"},
            )

        if any(term in err_msg for term in ["timeout", "timed out", "deadline"]):
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={
                    "message": "Upstream service timed out.",
                    "request_id": request_id,
                },
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "An internal error occurred during execution.",
                "request_id": request_id,
            },
        )

    latency_s = round(time.perf_counter() - start_time, 3)

    if not res["answer"]:
        logger.error(
            "Model finished without final text response: request_id=%s latency_sec=%.3f",
            request_id,
            latency_s,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": "Model run completed without returning a text response.",
                "request_id": request_id,
            },
        )

    unique_tools = list(dict.fromkeys([c.get("tool", "") for c in calls] + res["event_tools"]))
    # to be fixed
    cost = None
    # cost = calculate_cost(res["input_tokens"], res["output_tokens"])

    logger.info(
        "Request completed: request_id=%s latency_sec=%.3f tools=%s tokens_in=%d tokens_out=%d cost_usd=%.6f",
        request_id,
        latency_s,
        unique_tools,
        res["input_tokens"],
        res["output_tokens"],
        cost,
    )

    return AskResponse(
        id=request_id, 
        question=question,
        answer=res["answer"],
        tools=unique_tools,
        tool_calls=calls,
        latency_s=latency_s,
        input_tokens=res["input_tokens"],
        output_tokens=res["output_tokens"],
        thought_tokens=res["thought_tokens"],
        model_calls=res["model_calls"],
        cost_estimate_usd=cost,
    )