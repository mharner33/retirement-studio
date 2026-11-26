import re
from decimal import ROUND_HALF_UP, Decimal

_NUMBER = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_DOLLAR = re.compile(rf"-?\$-?(?:{_NUMBER})")
_PERCENT = re.compile(rf"(?:{_NUMBER})%")
_MIN_BARE_DOLLARS = 1000
_TOOL_TOKEN = re.compile(rf"-?\$-?(?:{_NUMBER})|(?:{_NUMBER})%|(?:{_NUMBER})")


def _decimal(token: str) -> Decimal:
    return Decimal(re.sub(r"[^\d.]", "", token))


def _round(value: Decimal, places: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _places(token: str) -> int:
    return len(token.split(".")[1]) if "." in token else 0


def _tool_figures(
    tool_texts: list[str],
) -> tuple[set[Decimal], set[Decimal], set[Decimal]]:
    """Return dollar-like values, percent-like values and rates (bare decimals
    between 0 and 1)."""
    dollars: set[Decimal] = set()
    percents: set[Decimal] = set()
    decimals: set[Decimal] = set()
    for text in tool_texts:
        for match in _TOOL_TOKEN.finditer(text):
            token = match.group()
            value = _decimal(token)
            if token.startswith(("$", "-$")):
                dollars.add(value)
            elif token.endswith("%"):
                percents.add(value)
            elif "." in token:
                dollars.add(value)
                if 0 < value < 1:
                    decimals.add(value)
            elif value >= _MIN_BARE_DOLLARS:
                dollars.add(value)
    return dollars, percents, decimals


def unchecked_figures(reply: str, tool_texts: list[str]) -> list[str]:
    """Dollar and percent tokens in the reply that match no number in the tool texts."""
    dollars, percents, decimals = _tool_figures(tool_texts)

    def dollar_ok(token: str) -> bool:
        places = 2 if "." in token else 0
        target = _round(_decimal(token), places)
        return any(_round(v, places) == target for v in dollars)

    def percent_ok(token: str) -> bool:
        places = _places(token)
        target = _round(_decimal(token), places)
        return any(_round(v, places) == target for v in percents) or any(
            _round(v * 100, places) == target for v in decimals
        )

    return [t for t in _DOLLAR.findall(reply) if not dollar_ok(t)] + [
        t for t in _PERCENT.findall(reply) if not percent_ok(t)
    ]
