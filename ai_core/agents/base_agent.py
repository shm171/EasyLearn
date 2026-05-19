from __future__ import annotations

"""Base LangChain agent wrapper."""

from typing import Any
from uuid import uuid4


class BaseLearningAgent:
    """Common wrapper around LangChain create_agent."""

    def __init__(
        self,
        model: Any,
        tools: list[Any] | None = None,
        system_prompt: str = "",
        checkpointer: Any | None = None,
        response_format: Any | None = None,
    ) -> None:
        """Create the underlying LangChain agent."""

        self.model = model
        self.tools = tools or []
        self.system_prompt = system_prompt
        self.checkpointer = checkpointer
        self.response_format = response_format
        self.thread_id = str(uuid4())
        self.agent = self._create_agent()

    def _create_agent(self) -> Any:
        try:
            from langchain.agents import create_agent
        except ImportError as exc:
            raise RuntimeError("Install langchain to use learning agents.") from exc

        kwargs: dict[str, Any] = {
            "model": self.model,
            "tools": self.tools,
            "system_prompt": self.system_prompt,
        }
        if self.checkpointer is not None:
            kwargs["checkpointer"] = self.checkpointer
        if self.response_format is not None:
            kwargs["response_format"] = self.response_format
        return create_agent(**kwargs)

    def reset_thread(self, thread_id: str | None = None) -> str:
        """Reset or set the conversation thread ID."""

        self.thread_id = thread_id or str(uuid4())
        return self.thread_id

    def invoke(self, user_message: str, thread_id: str | None = None) -> Any:
        """Invoke the agent with a user message."""

        active_thread = thread_id or self.thread_id or "default"
        config = {"configurable": {"thread_id": active_thread}}
        response = self.agent.invoke({"messages": [{"role": "user", "content": user_message}]}, config=config)
        if isinstance(response, dict):
            if response.get("structured_response") is not None:
                return response["structured_response"]

            messages = response.get("messages") or []
            if messages:
                last = messages[-1]
                content = getattr(last, "content", None)
                if content:
                    return content

        return response

    def stream(self, user_message: str, thread_id: str | None = None) -> Any:
        """Stream the agent response for a user message."""

        active_thread = thread_id or self.thread_id
        config = {"configurable": {"thread_id": active_thread}}
        return self.agent.stream({"messages": [{"role": "user", "content": user_message}]}, config=config)


