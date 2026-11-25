from backend.chat.masking import mask_for_model, unmask
from backend.profile.models import Household
from backend.tests.conftest import build_sample_household


def household(self_name: str = "Ann", spouse: bool = True) -> Household:
    h = build_sample_household()
    h.self_.first_name = self_name
    if spouse and h.spouse:
        h.spouse.first_name = "Bob"
    else:
        h.spouse = None
    return h


def test_masks_first_names_whole_words() -> None:
    h = household()
    assert mask_for_model("Ann's annual budget", h) == "[YOU]'s annual budget"
    assert mask_for_model("ann and BOB", h) == "[YOU] and [SPOUSE]"


def test_masks_terms_and_account_numbers() -> None:
    h = household()
    h.mask_terms = ["Acme Bank"]
    out = mask_for_model("Acme Bank account 1234567890", h)
    assert out == "[MASKED] account ****7890"


def test_unmask_restores_names_only() -> None:
    h = household()
    assert unmask("[YOU] and [SPOUSE] at [MASKED]", h) == "Ann and Bob at [MASKED]"


def test_spouse_placeholder_unused_without_spouse() -> None:
    h = household(spouse=False)
    assert mask_for_model("Bob and Ann", h) == "Bob and [YOU]"
    assert unmask("[SPOUSE]", h) == "[SPOUSE]"
