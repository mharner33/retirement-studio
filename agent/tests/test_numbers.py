from agent.numbers import unchecked_figures


def test_matches_formatted_money() -> None:
    assert unchecked_figures("You have $1,248,000.00 saved.", ["1248000.0"]) == []


def test_matches_whole_dollars() -> None:
    assert unchecked_figures("About $86,000 a year.", ["85999.6"]) == []


def test_flags_invented_money() -> None:
    assert unchecked_figures("Spend $86,000.00.", ["85000"]) == ["$86,000.00"]


def test_matches_rate_as_percent() -> None:
    assert unchecked_figures("A rate of 6.2%.", ["0.062"]) == []


def test_percent_matches_rate_times_100_not_bare_number() -> None:
    assert unchecked_figures("Growth of 7%.", ["7.0"]) == ["7%"]
    assert unchecked_figures("Growth of 7%.", ["0.07"]) == []


def test_matches_percent_written_as_percent() -> None:
    assert unchecked_figures("Taxed at 22%.", ["bracket 22%"]) == []
    assert unchecked_figures("Taxed at 24%.", ["bracket 22%"]) == ["24%"]


def test_ignores_years_and_ages() -> None:
    assert unchecked_figures("In 2030 at 67", []) == []


def test_matches_negative_money_by_absolute_value() -> None:
    assert unchecked_figures("Short by -$1,250.00 or $-1,250.00.", ["1250"]) == []
    assert unchecked_figures("Short by -$1,250.00.", ["-1250"]) == []


def test_reads_money_and_percent_tokens_in_tool_text() -> None:
    texts = ['{"balance": "$1,000.00", "rate": "4.5%", "n": 12}']
    assert unchecked_figures("$1,000.00 at 4.5%", texts) == []


def test_bare_small_integers_in_tool_text_do_not_match() -> None:
    tool = "year 2030 age 67 count 22 and 0.05 on 2026-11-25"
    reply = "$2,030 and $67 and 22% and 5%"
    assert sorted(unchecked_figures(reply, [tool])) == ["$67", "22%"]
