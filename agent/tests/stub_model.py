from typing import Any

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage
from pydantic import Field


class StubModel(GenericFakeChatModel):
    seen: list[list[BaseMessage]] = Field(default_factory=list)

    def __init__(self, responses: list[AIMessage]) -> None:
        super().__init__(messages=iter(responses))

    def bind_tools(self, *_args: Any, **_kwargs: Any) -> "StubModel":
        return self

    def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> Any:
        self.seen.append(list(messages))
        return super()._generate(messages, *args, **kwargs)

    def tool_messages(self) -> list[str]:
        """Contents of every ToolMessage the model has been shown,."""
        last = self.seen[-1] if self.seen else []
        return [str(m.content) for m in last if m.type == "tool"]
