import re
from decimal import ROUND_HALF_UP, Decimal

_NUMBER = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_DOLLAR = re.compile(rf"-?\$-?(?:{_NUMBER})")
_PERCENT = re.compile(rf"(?:{_NUMBER})%")
_BARE = re.compile(_NUMBER)


def _decimal(token: str) -> Decimal:
    return Decimal(re.sub(r"[^\d.]", "", token))


def _round(value: Decimal, places: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _places(token: str) -> int:
    return len(token.split(".")[1]) if "." in token else 0


def unchecked_figures(reply: str, tool_texts: list[str]) -> list[str]:
    """Dollar and percent tokens in the reply that match no number in the tool texts."""
    values = {_decimal(n) for text in tool_texts for n in _BARE.findall(text)}

    def dollar_ok(token: str) -> bool:
        places = 2 if "." in token else 0
        target = _round(_decimal(token), places)
        return any(_round(v, places) == target for v in values)

    def percent_ok(token: str) -> bool:
        places = _places(token)
        target = _round(_decimal(token), places)
        return any(
            _round(v, places) == target or _round(v * 100, places) == target
            for v in values
        )

    return [t for t in _DOLLAR.findall(reply) if not dollar_ok(t)] + [
        t for t in _PERCENT.findall(reply) if not percent_ok(t)
    ]
