"""Serial decode (PLAN.md task 3.4).

Every serial below is a worked example printed in its cited source, so the expected year
comes from the source, not from this code. `decode_as_of` fixes "today" so a cycle's
candidates do not change with the clock.
"""

import pytest

from app.repository import Repository
from app.serial.decode import decode, decode_as_of


@pytest.fixture(scope="module")
def source_ids() -> set[str]:
    return {s.id for s in Repository.load().sources()}


def test_ge_serial_decodes_to_its_year_and_month() -> None:
    # electrical-forensics.com: GE refrigerator TBX22PAYARBB, serial ZR525322, December 1996.
    d = decode_as_of("GE", "ZR525322", 1999)
    assert (d.mfg_year, d.source_id) == (1996, "ge_serial_dating")
    assert "December" in d.note


def test_ge_serial_matches_the_year_on_ges_own_page() -> None:
    # products.geappliances.com: serial AS 123456S is January 2009.
    d = decode_as_of("GE", "AS 123456S", 2010)
    assert d.mfg_year == 2009 and "January" in d.note


def test_whirlpool_serial_decodes_to_its_year() -> None:
    # electrical-forensics.com: Kenmore refrigerator 106.9712611, serial EB1719162, week 17 of 1992.
    d = decode_as_of("Whirlpool", "EB1719162", 2010)
    assert (d.mfg_year, d.year_confidence, d.source_id) == (1992, "high", "whirlpool_serial_dating")
    assert "week 17" in d.note


def test_frigidaire_serial_decodes_to_its_year() -> None:
    # electrical-forensics.com: LA81503430 is a refrigerator made in week 15 of 1998.
    d = decode_as_of("Frigidaire", "LA81503430", 1999)
    assert (d.mfg_year, d.source_id) == (1998, "electrolux_serial_dating")
    assert "week 15" in d.note


def test_a_repeating_code_is_low_confidence_with_the_other_years_named() -> None:
    d = decode_as_of("GE", "ZR525322", 2026)  # R is 1984, 1996, 2008 or 2020
    assert (d.mfg_year, d.year_confidence) == (2020, "low")
    assert all(y in d.note for y in ("1984", "1996", "2008"))
    d = decode_as_of("Frigidaire", "LA81503430", 2026)  # digit 8 is 1988, 1998, 2008 or 2018
    assert (d.mfg_year, d.year_confidence) == (2018, "low")


def test_a_code_that_fits_one_year_is_high_confidence() -> None:
    # Whirlpool letter K is 2000 (the next K is 2030); the serial is built to the source's format.
    d = decode_as_of("Whirlpool", "MK1402320", 2026)
    assert (d.mfg_year, d.year_confidence) == (2000, "high")


def test_a_year_in_the_future_is_never_returned() -> None:
    for brand, serial in (("GE", "ZR525322"), ("Whirlpool", "EB1719162"), ("Frigidaire", "LA81503430")):
        for this_year in range(1995, 2027):
            d = decode_as_of(brand, serial, this_year)
            assert d.mfg_year is None or d.mfg_year <= this_year


def test_unknown_brand_has_no_decoder() -> None:
    d = decode("Acme", "ZR525322")
    assert (d.mfg_year, d.year_confidence, d.source_id, d.note) == (None, "none", None, "no decoder for brand")


def test_brand_without_a_sourced_rule_is_not_guessed() -> None:
    # Kenmore's format depends on the model prefix, which decode() is not given; Maytag and
    # Element have no rule in the record.
    for brand in ("Kenmore", "Maytag", "Element", "Samsung"):
        assert decode(brand, "EB1719162").year_confidence == "none"


@pytest.mark.parametrize(
    "brand,serial",
    [
        ("GE", "ZR52532"),  # too short
        ("GE", "QR525322"),  # Q is not a GE month code
        ("Whirlpool", "EB9919162"),  # week 99
        ("Whirlpool", "EB17"),
        ("Frigidaire", "LC81503430"),  # second character is a washer code, not a refrigerator
        ("Frigidaire", "LA81503"),
        ("Whirlpool", ""),
    ],
)
def test_a_serial_that_does_not_match_its_brands_format_gives_none(brand: str, serial: str) -> None:
    d = decode_as_of(brand, serial, 2026)
    assert (d.mfg_year, d.year_confidence) == (None, "none")


def test_brand_and_serial_are_normalized() -> None:
    assert decode_as_of("  ge profile ", "zr-525-322", 1999).mfg_year == 1996
    assert decode_as_of("Café", "ZR525322", 1999).mfg_year == 1996
    assert decode_as_of("Hotpoint", "ZR525322", 1999).mfg_year == 1996
    assert decode_as_of("KitchenAid", "EB1719162", 2010).mfg_year == 1992


def test_every_source_id_resolves(source_ids: set[str]) -> None:
    cases = (("GE", "ZR525322"), ("Whirlpool", "EB1719162"), ("Frigidaire", "LA81503430"))
    for brand, serial in cases:
        d = decode_as_of(brand, serial, 2026)
        assert d.source_id in source_ids
    for source in Repository.load().sources():
        if source.id.endswith("_serial_dating"):
            assert source.url.startswith("https://") and source.retrieved_date


def test_note_copy_has_no_em_dash_or_apr() -> None:
    for brand, serial in (("GE", "ZR525322"), ("Whirlpool", "EB1719162"), ("Frigidaire", "LA81503430"), ("Acme", "X")):
        note = decode_as_of(brand, serial, 2026).note
        assert "—" not in note and "APR" not in note
