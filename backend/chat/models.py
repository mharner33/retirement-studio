from typing import Literal

from pydantic import BaseModel

from backend.plan.changes import ChangeLine, ProfileChange


class Source(BaseModel):
    kind: Literal["engine", "rules", "web"]
    label: str
    url: str | None = None


class ChangeCard(BaseModel):
    id: int
    reason: str
    status: Literal["proposed", "applied", "dismissed"]
    lines: list[ChangeLine]
    error: str | None = None


class ChatMessage(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    text: str
    sources: list[Source]
    unchecked: bool
    changes: list[ChangeCard]


class ChatState(BaseModel):
    status: Literal["idle", "working", "failed"]
    step: str | None
    messages: list[ChatMessage]


class Proposal(BaseModel):
    changes: list[ProfileChange]
    reason: str


class Reply(BaseModel):
    text: str
    sources: list[Source]
    tool_results: list[str]
    unchecked: bool
    proposals: list[Proposal]


class ContextMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str
    tool_results: list[str]


class UserMessage(BaseModel):
    text: str


class Step(BaseModel):
    text: str
