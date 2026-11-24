from typing import Any

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage


class StubModel(GenericFakeChatModel):
    def __init__(self, responses: list[AIMessage]) -> None:
        super().__init__(messages=iter(responses))

    def bind_tools(self, *_args: Any, **_kwargs: Any) -> "StubModel":
        return self
