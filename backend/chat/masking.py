import re

from backend.profile.models import Household
from backend.statements.pdf import mask


def mask_for_model(text: str, h: Household) -> str:
    people = [("[YOU]", h.self_)] + ([("[SPOUSE]", h.spouse)] if h.spouse else [])
    for placeholder, person in people:
        name = re.escape(person.first_name)
        text = re.sub(rf"(?<!\w){name}(?!\w)", placeholder, text, flags=re.I)
    return mask(text, h.mask_terms)


def unmask(text: str, h: Household) -> str:
    text = text.replace("[YOU]", h.self_.first_name)
    return text.replace("[SPOUSE]", h.spouse.first_name) if h.spouse else text
