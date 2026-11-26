import httpx
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from agent.backend_client import make_client
from agent.model import make_model


def run(
    task: str,
    thread_id: str,
    client: httpx.Client | None = None,
    model: BaseChatModel | None = None,
) -> str:
    http = client or make_client()

    @tool
    def check_backend() -> str:
        """Check whether the backend is healthy."""
        return http.get("/api/health").text

    agent = create_agent(model or make_model(), tools=[check_backend])
    result = agent.invoke(
        {"messages": [HumanMessage(task)]},
        config={"configurable": {"thread_id": thread_id}},
    )
    return result["messages"][-1].text
