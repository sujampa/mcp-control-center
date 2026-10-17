from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Business question for the AI assistant",
    )


class TraceEvent(BaseModel):
    stage: str
    status: str
    message: str
    duration_ms: float | None = None
    details: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    question: str
    answer: str

    tool_used: str | None = None
    tool_arguments: dict[str, Any] | None = None
    tool_result: str | None = None
    tool_duration_ms: float | None = None

    trace: list[TraceEvent] = Field(default_factory=list)

    status: str = "success"
    total_duration_ms: float = 0.0