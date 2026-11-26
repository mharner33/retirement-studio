import re

from backend.profile.models import Household
from backend.statements.pdf import mask


def _names(h: Household) -> list[tuple[str, str]]:
    people = [("[YOU]", h.self_)] + ([("[SPOUSE]", h.spouse)] if h.spouse else [])
    return [
        (p, person.first_name.strip())
        for p, person in people
        if person.first_name.strip()
    ]


def mask_for_model(text: str, h: Household) -> str:
    for placeholder, name in _names(h):
        text = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", placeholder, text, flags=re.I)
    return mask(text, h.mask_terms)


def unmask(text: str, h: Household) -> str:
    for placeholder, name in _names(h):
        text = text.replace(placeholder, name)
    return text
