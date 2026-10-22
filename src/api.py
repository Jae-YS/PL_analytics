import time
import uuid
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, status
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel, Field

from pl_agent.agent import root_agent
from src.config import MODEL
from src.tool_logging import start_collecting

APP_NAME = "pl_agent"
DEFAULT_USER_ID = "default_user"

app = FastAPI(title="PL Analytics API")
runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)


class AskRequest(BaseModel):
    question: str = Field(
        ...,
        description="The question to ask the model",
        min_length=3,
        max_length=1000,
    )


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
    cost_estimate_usd: Optional[float] = None
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
async def ask(body: AskRequest):
    question = body.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Question cannot be whitespace only.",
        )

    session = await runner.session_service.create_session(
        app_name=APP_NAME,
        user_id=DEFAULT_USER_ID,
    )

    message = types.Content(role="user", parts=[types.Part(text=question)])
    
    # Tool collection hook
    calls = start_collecting()

    res = {
        "answer": "",
        "input_tokens": 0,
        "output_tokens": 0,
        "thought_tokens": 0,
        "model_calls": 0,
        "cost_estimate_usd": None, 
        "event_tools": [],
    }

    start = time.perf_counter()
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

    except Exception as exc:
        err_msg = str(exc).lower()
        if any(term in err_msg for term in ["rate limit", "resource exhausted", "429"]):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {exc}",
            )
        if any(term in err_msg for term in ["timeout", "timed out", "deadline"]):
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Request timed out: {exc}",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failure: {type(exc).__name__} - {exc}",
        )

    latency_s = round(time.perf_counter() - start, 2)

    # Empty answer check
    if not res["answer"]:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Model run completed without returning a final text response.",
        )

    unique_tools = list(dict.fromkeys([c.get("tool", "") for c in calls] + res["event_tools"]))

    return AskResponse(
        id=str(uuid.uuid4()),  # Stable unique request identifier
        question=question,
        answer=res["answer"],
        tools=unique_tools,
        tool_calls=calls,
        latency_s=latency_s,
        input_tokens=res["input_tokens"],
        output_tokens=res["output_tokens"],
        thought_tokens=res["thought_tokens"],
        model_calls=res["model_calls"],
        cost_estimate_usd=res["cost_estimate_usd"],
        error=None,
    )