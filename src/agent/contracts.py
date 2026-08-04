from typing import Literal

from pydantic import Field, TypeAdapter

from src.schemas.base import StrictModel


class AgentToolCall(StrictModel):
    kind: Literal["tool_call"]
    call_id: str = Field(pattern=r"^tool-call-[a-z0-9-]{4,64}$")
    tool_name: str = Field(min_length=1, max_length=120)
    arguments: dict[str, object] = Field(default_factory=dict)


class AgentFinal(StrictModel):
    kind: Literal["final"]
    message: str = Field(min_length=1, max_length=2_000)


AgentModelOutput = AgentToolCall | AgentFinal
agent_model_output_adapter = TypeAdapter(AgentModelOutput)


class AgentTraceEntry(StrictModel):
    step: int = Field(ge=1, le=32)
    call_id: str | None = None
    tool_name: str | None = None
    status: Literal["tool_called", "succeeded", "failed", "approval_required", "final"]
    detail: str = Field(min_length=1, max_length=500)


class AgentRunResult(StrictModel):
    status: Literal["completed", "approval_required", "failed", "step_limit_reached"]
    message: str = Field(min_length=1, max_length=2_000)
    trace: tuple[AgentTraceEntry, ...] = Field(max_length=32)
    outputs: tuple[dict[str, object], ...] = Field(max_length=32)


class AgentRunRequest(StrictModel):
    goal: str = Field(min_length=1, max_length=2_000)
    campaign_id: str | None = Field(default=None, pattern=r"^campaign-[a-z0-9-]{4,64}$")
    approved_call_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    max_steps: int = Field(default=8, ge=1, le=12)
