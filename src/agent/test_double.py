from src.agent.contracts import AgentFinal, AgentToolCall


class DeterministicCrmAgent:
    """Safe local model substitute used until a validated Colab adapter is injected."""

    def __init__(self, campaign_id: str | None) -> None:
        self._campaign_id = campaign_id
        self._used = False

    def next_output(
        self, goal: str, _observations: tuple[dict[str, object], ...]
    ) -> object:
        if (
            not self._used
            and self._campaign_id is not None
            and "prospect" in goal.casefold()
        ):
            self._used = True
            if "link" in goal.casefold():
                return AgentToolCall(
                    kind="tool_call",
                    call_id="tool-call-link-prospect-0001",
                    tool_name="crm.link_selected_prospect",
                    arguments={
                        "campaign_id": self._campaign_id,
                        "idempotency_key": "agent-link-prospect-0001",
                    },
                )
            return AgentToolCall(
                kind="tool_call",
                call_id="tool-call-inspect-prospect-0001",
                tool_name="gtm.inspect_selected_prospect",
                arguments={"campaign_id": self._campaign_id},
            )
        return AgentFinal(
            kind="final",
            message="No further deterministic action is available; review the trace.",
        )
