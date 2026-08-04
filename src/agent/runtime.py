import re
from collections.abc import Iterable
from typing import Protocol

from pydantic import ValidationError

from src.agent.contracts import (
    AgentFinal,
    AgentModelOutput,
    AgentRunResult,
    AgentToolCall,
    AgentTraceEntry,
    agent_model_output_adapter,
)
from src.agent.tools import CrmToolRegistry


class AgentModel(Protocol):
    def next_output(
        self, goal: str, observations: tuple[dict[str, object], ...]
    ) -> object: ...


class ControlledAgentRuntime:
    """Executes validated model proposals with bounded steps and approvals."""

    def __init__(self, registry: CrmToolRegistry, max_steps: int = 8) -> None:
        self._registry = registry
        self._max_steps = min(max_steps, 12)

    def run(
        self,
        *,
        tenant_id: str,
        goal: str,
        model: AgentModel,
        approved_call_ids: Iterable[str] = (),
    ) -> AgentRunResult:
        if not goal.strip():
            return AgentRunResult(
                status="failed", message="agent goal is required", trace=(), outputs=()
            )
        if re.fullmatch(r"tenant-[a-z0-9-]{4,64}", tenant_id) is None:
            return AgentRunResult(
                status="failed",
                message="tenant context is invalid",
                trace=(),
                outputs=(),
            )
        approved = frozenset(approved_call_ids)
        trace: list[AgentTraceEntry] = []
        observations: list[dict[str, object]] = []
        for step in range(1, self._max_steps + 1):
            try:
                output: AgentModelOutput = agent_model_output_adapter.validate_python(
                    model.next_output(goal, tuple(observations))
                )
            except (ValidationError, ValueError, TypeError) as error:
                error_detail = (
                    error.errors()[0]["msg"]
                    if isinstance(error, ValidationError)
                    else str(error)
                )
                trace.append(
                    AgentTraceEntry(
                        step=step,
                        status="failed",
                        detail=f"invalid model output: {error_detail}",
                    )
                )
                return AgentRunResult(
                    status="failed",
                    message="model output failed validation",
                    trace=tuple(trace),
                    outputs=tuple(observations),
                )
            if isinstance(output, AgentFinal):
                trace.append(
                    AgentTraceEntry(step=step, status="final", detail=output.message)
                )
                return AgentRunResult(
                    status="completed",
                    message=output.message,
                    trace=tuple(trace),
                    outputs=tuple(observations),
                )
            result, payload = self._execute_call(
                tenant_id, output, step, approved, trace
            )
            if result is not None:
                return AgentRunResult(
                    status=result.status,
                    message=result.message,
                    trace=tuple(trace),
                    outputs=tuple(observations),
                )
            observations.append(
                {
                    "call_id": output.call_id,
                    "tool_name": output.tool_name,
                    "result": payload or {},
                }
            )
        trace.append(
            AgentTraceEntry(
                step=self._max_steps, status="failed", detail="agent step limit reached"
            )
        )
        return AgentRunResult(
            status="step_limit_reached",
            message="agent step limit reached",
            trace=tuple(trace),
            outputs=tuple(observations),
        )

    def _execute_call(
        self,
        tenant_id: str,
        call: AgentToolCall,
        step: int,
        approved: frozenset[str],
        trace: list[AgentTraceEntry],
    ) -> tuple[AgentRunResult | None, dict[str, object] | None]:
        try:
            spec = self._registry.get(call.tool_name)
            arguments = spec.argument_model.model_validate(call.arguments)
        except (ValidationError, ValueError) as error:
            trace.append(
                AgentTraceEntry(
                    step=step,
                    call_id=call.call_id,
                    tool_name=call.tool_name,
                    status="failed",
                    detail=f"tool call rejected: {error}",
                )
            )
            return AgentRunResult(
                status="failed",
                message="tool call failed validation",
                trace=(),
                outputs=(),
            ), None
        trace.append(
            AgentTraceEntry(
                step=step,
                call_id=call.call_id,
                tool_name=call.tool_name,
                status="tool_called",
                detail=f"{spec.name} v{spec.version}",
            )
        )
        if spec.requires_approval and call.call_id not in approved:
            trace.append(
                AgentTraceEntry(
                    step=step,
                    call_id=call.call_id,
                    tool_name=call.tool_name,
                    status="approval_required",
                    detail="user approval is required before this mutation",
                )
            )
            return AgentRunResult(
                status="approval_required",
                message=f"Approval required for {spec.name}",
                trace=(),
                outputs=(),
            ), None
        try:
            payload = spec.handler(tenant_id, arguments)
        # This boundary keeps unexpected handler failures visible to the agent trace.
        except Exception as error:
            trace.append(
                AgentTraceEntry(
                    step=step,
                    call_id=call.call_id,
                    tool_name=call.tool_name,
                    status="failed",
                    detail=f"tool execution failed: {error}",
                )
            )
            return AgentRunResult(
                status="failed", message=f"{spec.name} failed", trace=(), outputs=()
            ), None
        trace.append(
            AgentTraceEntry(
                step=step,
                call_id=call.call_id,
                tool_name=call.tool_name,
                status="succeeded",
                detail="tool completed",
            )
        )
        return None, payload
