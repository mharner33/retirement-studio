import re
from pathlib import Path

import pymupdf

# An ISO date matches first so it is left alone; other runs of 6+ digits
# (spaces and dashes allowed inside) are account or tax numbers. Amounts with
# commas never form such a run, and a leading $ is skipped.
NUMBER = re.compile(r"\d{4}-\d{2}-\d{2}(?!\d)|(?<![\d$])\d(?:[ -]?\d){5,}")


def extract_text(path: Path) -> str:
    with pymupdf.open(path) as doc:
        return "\n".join(str(page.get_text("text")) for page in doc)


def _mask_number(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group())
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", match.group()):
        return match.group()
    return "****" + digits[-4:]


def mask(text: str, terms: list[str]) -> str:
    for term in terms:
        if term:
            text = re.sub(re.escape(term), "[MASKED]", text, flags=re.IGNORECASE)
    return NUMBER.sub(_mask_number, text)
