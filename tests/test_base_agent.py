from __future__ import annotations

from ai_core.agents.base_agent import BaseLearningAgent


class DummyAgent:
    def invoke(self, payload, config=None):
        return {
            "messages": [{"role": "assistant", "content": ""}],
            "structured_response": {"ok": True},
        }


def test_base_agent_invoke_structured_response() -> None:
    agent = BaseLearningAgent.__new__(BaseLearningAgent)
    agent.agent = DummyAgent()
    agent.thread_id = "thread_test"

    result = BaseLearningAgent.invoke(agent, "hello")

    assert result == {"ok": True}

