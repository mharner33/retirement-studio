from datetime import date

import httpx
from bs4 import BeautifulSoup
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool, tool

from agent.backend_client import make_client
from agent.model import make_model

SOURCES = [
    "https://www.irs.gov/newsroom/irs-releases-tax-inflation-adjustments-for-tax-year-2026-including-amendments-from-the-one-big-beautiful-bill",
    "https://www.irs.gov/pub/irs-drop/rp-25-32.pdf",
    "https://www.irs.gov/newsroom/check-your-eligibility-for-the-new-enhanced-deduction-for-seniors",
    "https://www.irs.gov/pub/irs-pdf/f1040s1a.pdf",
    "https://www.irs.gov/publications/p915",
    "https://www.irs.gov/pub/irs-pdf/p590b.pdf",
    "https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-topics-required-minimum-distributions-rmds",
    "https://www.ssa.gov/oact/quickcalc/earlyretire.html",
    "https://www.ssa.gov/benefits/retirement/planner/delayret.html",
    "https://www.ssa.gov/benefits/retirement/planner/applying7.html",
    "https://www.cms.gov/newsroom/fact-sheets/2026-medicare-parts-b-premiums-deductibles",
    "https://tax.colorado.gov/individual-income-tax-guide",
    "https://tax.colorado.gov/sites/default/files/documents/DR_0104EP_2026.pdf",
    "https://tax.colorado.gov/income-tax-topics-social-security-pensions-and-annuities",
]

MAX_PAGE_CHARS = 40_000

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

Never invent figures. If a figure cannot be confirmed from a source, keep the
current value and say so in the text. When finished, reply with the file name
returned by save_rules."""


def _make_tools(client: httpx.Client, web: httpx.Client) -> list[BaseTool]:
    @tool
    def fetch_page(url: str) -> str:
        """Fetch an official source page and return its text."""
        if url not in SOURCES:
            return f"Rejected: {url} is not in the allowed sources."
        response = web.get(url, follow_redirects=True)
        response.raise_for_status()
        text = BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)
        return text[:MAX_PAGE_CHARS]

    @tool
    def current_rules() -> str:
        """Return the current rules file as markdown."""
        name = client.get("/api/rules/status").json()["current_file"]
        return client.get(f"/api/rules/{name}").text

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
    tools = _make_tools(client or make_client(), web or httpx.Client(timeout=30))
    prompt = SYSTEM_PROMPT.format(
        today=date.today().isoformat(), sources="\n".join(SOURCES)
    )
    agent = create_agent(model or make_model(), tools=tools, system_prompt=prompt)
    result = agent.invoke({"messages": [HumanMessage("Refresh the rules file.")]})
    return result["messages"][-1].text
