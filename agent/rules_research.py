from contextlib import ExitStack
from datetime import date

import httpx
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool, tool

from agent import pages
from agent.backend_client import make_client
from agent.model import make_model
from agent.pages import fetch_text, make_web_client

MAX_PAGE_CHARS = pages.MAX_PAGE_CHARS

SOURCES = [
    "https://www.irs.gov/newsroom/irs-releases-tax-inflation-adjustments-for-tax-year-2026-including-amendments-from-the-one-big-beautiful-bill",
    "https://www.irs.gov/pub/irs-drop/rp-25-32.pdf",
    "https://www.irs.gov/newsroom/check-your-eligibility-for-the-new-enhanced-deduction-for-seniors",
    "https://www.irs.gov/pub/irs-pdf/f1040s1a.pdf",
    "https://www.irs.gov/publications/p915",
    "https://www.irs.gov/pub/irs-pdf/p590b.pdf",
    "https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-topics-required-minimum-distributions-rmds",
    "https://www.law.cornell.edu/cfr/text/20/404.410",
    "https://www.law.cornell.edu/cfr/text/20/404.313",
    "https://www.cms.gov/newsroom/fact-sheets/2026-medicare-parts-b-premiums-deductibles",
    "https://tax.colorado.gov/individual-income-tax-guide",
    "https://tax.colorado.gov/sites/default/files/documents/DR_0104EP_2026.pdf",
    "https://tax.colorado.gov/income-tax-topics-social-security-pensions-and-annuities",
]

SYSTEM_PROMPT = """You maintain the retirement tax rules file for Retirement Studio.
Today's date is {today}.

Steps:
1. Call current_rules to read the current file.
2. Call fetch_page for the official sources you need. Only these URLs are allowed:
{sources}
3. Write an updated file and call save_rules with the full markdown. If it
   returns an error, fix the file and call it again.

The new file must keep the same headings, tables and the same JSON schema in the
"Figures" section as the current file. Do not add, rename or remove JSON keys.
Every section ends with a "Source:" or "Sources:" line giving the official URL(s)
it was taken from, and the intro states today's date as the copy date.

Cover and verify:
- the federal tax year figures (brackets, standard deduction, capital gains,
  Social Security taxation)
- the enhanced deduction for seniors
- the RMD tables and start ages
- IRMAA
- the Social Security reduction factors
- Colorado: the rate, the retirement subtraction, the Social Security subtraction
  including the 55 to 64 AGI rule, and whether Colorado adds back the federal
  senior deduction

If a source cannot be fetched, keep the current file's figures for that section
unchanged and add one line under that section's heading:
"Not refreshed on {today}: source unavailable."
Never guess figures. Long PDFs such as Pub 590-B need fetch_page with find (for
example "Uniform Lifetime"). If a figure cannot be confirmed from a source, keep
the current value and say so in the text. When finished, reply with the file name
returned by save_rules."""


def _make_tools(client: httpx.Client, web: httpx.Client) -> list[BaseTool]:
    @tool
    def fetch_page(url: str, find: str = "") -> str:
        """Fetch an official source and return its text (PDFs are converted).

        Output is cut at 40,000 characters. For long documents pass `find`, a
        keyword, to start the text just before its first occurrence."""
        return fetch_text(web, url, SOURCES, find)

    @tool
    def current_rules() -> str:
        """Return the current rules file as markdown."""
        status = client.get("/api/rules/status")
        status.raise_for_status()
        name = status.json()["current_file"]
        response = client.get(f"/api/rules/{name}")
        response.raise_for_status()
        return response.text

    @tool
    def save_rules(markdown: str) -> str:
        """Save a new pending rules file. Returns the file name or the error."""
        response = client.post("/api/rules", json={"markdown": markdown})
        if response.status_code == httpx.codes.UNPROCESSABLE_ENTITY:
            return f"Rejected: {response.json()['detail']}"
        response.raise_for_status()
        return response.text

    return [fetch_page, current_rules, save_rules]


def refresh(
    client: httpx.Client | None = None,
    model: BaseChatModel | None = None,
    web: httpx.Client | None = None,
) -> str:
    with ExitStack() as stack:
        if client is None:
            client = stack.enter_context(make_client())
        if web is None:
            web = stack.enter_context(make_web_client())
        return _run(client, web, model)


def _run(client: httpx.Client, web: httpx.Client, model: BaseChatModel | None) -> str:
    tools = _make_tools(client, web)
    prompt = SYSTEM_PROMPT.format(
        today=date.today().isoformat(), sources="\n".join(SOURCES)
    )
    agent = create_agent(model or make_model(), tools=tools, system_prompt=prompt)
    result = agent.invoke({"messages": [HumanMessage("Refresh the rules file.")]})
    return result["messages"][-1].text
