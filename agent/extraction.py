import logging
from contextlib import ExitStack

import httpx
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from pydantic import TypeAdapter

from agent.backend_client import make_client
from agent.model import make_model
from backend.statements.models import (
    ExtractedDocument,
    ExtractedSsStatement,
    ExtractedStatement,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You extract data from a retirement statement for Retirement Studio.

Choose doc_type "social_security" for an ssa.gov "Your Social Security Statement",
otherwise "account".

Account numbers in the text are masked as ****1234. Use those 4 digits as last4.

Map plan types to kind:
- 401(k), 403(b), traditional IRA, SEP or rollover IRA: pretax
- Roth 401(k) and Roth IRA: roth
- brokerage, individual or joint: taxable
- money market, savings or checking held as cash: cash
- HSA: hsa

Record the account holder's first name in owner_hint and leave owner as "self".
The reviewer sets owner.

Use the statement's ending balance, not the beginning balance.

Never guess. If a value is not in the text, leave it out. If no balance can be
found, return no accounts."""

document_adapter: TypeAdapter[ExtractedDocument] = TypeAdapter(ExtractedDocument)


def extract(
    statement_id: int,
    client: httpx.Client | None = None,
    model: BaseChatModel | None = None,
) -> ExtractedDocument | None:
    with ExitStack() as stack:
        if client is None:
            client = stack.enter_context(make_client())
        text = client.get(f"/api/statements/{statement_id}/text")
        if text.status_code == httpx.codes.UNPROCESSABLE_ENTITY:
            logger.warning("statement %s has no readable text", statement_id)
            return None
        text.raise_for_status()
        agent = create_agent(
            model or make_model(),
            tools=[],
            system_prompt=SYSTEM_PROMPT,
            response_format=ToolStrategy(ExtractedStatement | ExtractedSsStatement),
        )
        result = agent.invoke({"messages": [HumanMessage(text.text)]})
        document = result.get("structured_response")
        if document is None:
            logger.warning(
                "model returned no extraction for statement %s", statement_id
            )
            return None
        body = document_adapter.dump_python(document, mode="json")
        response = client.put(f"/api/statements/{statement_id}/extraction", json=body)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            logger.exception(
                "could not store extraction for statement %s: %s",
                statement_id,
                response.text,
            )
            return None
        return document
