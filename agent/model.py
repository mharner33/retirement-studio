import os

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

DEFAULT_MODEL = "openai/gpt-6-luna"


def make_model() -> BaseChatModel:
    load_dotenv()
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],  # type: ignore[arg-type]
        model=os.environ.get("MODEL_NAME") or DEFAULT_MODEL,
        reasoning_effort="medium",
    )
