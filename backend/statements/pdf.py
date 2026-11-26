import re
from pathlib import Path

import pymupdf

# Dashes (including unicode ones), NBSP, middle dot and short runs of spaces
# separate digit groups. An ISO date is matched first so it is left alone. A
# candidate is never started inside a number nor ended before more digits, a
# comma or a decimal fraction, so balances like 125000.00 survive.
MIN_DIGITS = 6
SEP = r"[ \t\u00a0\u2010-\u2015\u00b7-]{1,3}"
NUMBER = re.compile(
    r"(?<![\d.,$])(?:\d{4}-\d{2}-\d{2}(?!\d)"
    rf"|(?:\d{{6,}}|\d{{2,4}}(?:{SEP}\d{{2,4}})+)(?![\d,]|\.\d))"
)


def extract_text(path: Path) -> str:
    with pymupdf.open(path) as doc:
        return "\n".join(str(page.get_text("text")) for page in doc)


def _mask_number(match: re.Match[str]) -> str:
    text = match.group()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    digits = re.sub(r"\D", "", text)
    return "****" + digits[-4:] if len(digits) >= MIN_DIGITS else text


def mask(text: str, terms: list[str]) -> str:
    for term in terms:
        words = term.split()
        if words:
            body = r"\s+".join(map(re.escape, words))
            text = re.sub(rf"(?<!\w){body}(?!\w)", "[MASKED]", text, flags=re.I)
    return NUMBER.sub(_mask_number, text)
