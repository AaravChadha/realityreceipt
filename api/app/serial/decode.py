"""Manufacture year from a refrigerator serial number (PLAN.md task 3.4).

Each rule is a published serial-number format, cited by `source_id` in `sources.json`.
Every year code below repeats on a cycle (GE every 12 years, Whirlpool and Frigidaire
by decade), and `decode` is not given the model number, so it cannot use the model's
era to pick a cycle. When more than one year fits, it returns the most recent one that
is not in the future, with `year_confidence="low"` and the other candidates in `note`.
A code with one possible year is `"high"`. A brand with no rule, or a serial that does
not match its brand's format, is `SerialDecode(None, "none", ...)`, never a guess.
"""

import datetime
import re
from collections.abc import Callable

from app.models import SerialDecode

# Earliest year a code can mean. The DOE standards, the oldest data here, start in 1993.
MIN_YEAR = 1980

# GE serial: two letters, six numbers, a trailing letter (older serials drop the trailing letter).
# First letter is the month, second the year on a 12-year cycle that starts G = 1980.
_GE_MONTHS = {
    "A": "January", "D": "February", "F": "March", "G": "April", "H": "May", "L": "June",
    "M": "July", "R": "August", "S": "September", "T": "October", "V": "November", "Z": "December",
}
_GE_YEAR_ORDER = "GHLMRSTVZADF"
_GE_SERIAL = re.compile(r"^([ADFGHLMRSTVZ])([ADFGHLMRSTVZ])\d{6}[A-Z]?$")

# Whirlpool serial (nine characters): division letter, year code, two-digit week, five-digit unit number.
_WHIRLPOOL_YEARS: dict[str, tuple[int, ...]] = {}
for _i, _c in enumerate("XABCDEFGHJ"):
    _WHIRLPOOL_YEARS[_c] = (1990 + _i, 2020 + _i)
for _i, _c in enumerate("KLMPRSTUWY"):
    _WHIRLPOOL_YEARS[_c] = (2000 + _i, 2030 + _i)
for _d in range(10):
    _WHIRLPOOL_YEARS[str(_d)] = (1970 + _d, 1980 + _d, 2010 + _d)
_WHIRLPOOL_SERIAL = re.compile(r"^[A-Z][A-Z0-9](\d{2})\d{5}$")

# Frigidaire (Electrolux) serial, ten characters: plant, product (A refrigerator, B freezer),
# last digit of the year, two-digit week, five-digit unit number. The decade is not in the serial.
_ELECTROLUX_SERIAL = re.compile(r"^[A-Z0-9]([A-Z])(\d)(\d{2})\d{5}$")

_BRANDS = {
    "ge": "ge", "ge profile": "ge", "ge adora": "ge", "cafe": "ge", "hotpoint": "ge", "monogram": "ge",
    "whirlpool": "whirlpool", "kitchenaid": "whirlpool",
    "frigidaire": "electrolux", "frigidaire gallery": "electrolux", "electrolux": "electrolux",
}


def _none(note: str, source_id: str | None = None) -> SerialDecode:
    return SerialDecode(mfg_year=None, year_confidence="none", source_id=source_id, note=note)


def _resolve(years: list[int], source_id: str, detail: str, this_year: int) -> SerialDecode:
    fits = sorted(y for y in years if MIN_YEAR <= y <= this_year)
    if not fits:
        return _none(f"year code matches no year from {MIN_YEAR} to {this_year}", source_id)
    if len(fits) == 1:
        return SerialDecode(mfg_year=fits[0], year_confidence="high", source_id=source_id, note=detail)
    others = ", ".join(str(y) for y in fits[:-1])
    return SerialDecode(
        mfg_year=fits[-1],
        year_confidence="low",
        source_id=source_id,
        note=f"{detail}; the year code repeats, so this is the latest fit. Also possible: {others}",
    )


def _ge(serial: str, this_year: int) -> SerialDecode:
    m = _GE_SERIAL.match(serial)
    if not m:
        return _none("serial does not match the GE format (two letters, six numbers)")
    month, offset = _GE_MONTHS[m.group(1)], _GE_YEAR_ORDER.index(m.group(2))
    years = [y for y in range(MIN_YEAR, this_year + 1) if (y - 1980) % 12 == offset]
    return _resolve(years, "ge_serial_dating", f"GE date code: {month}", this_year)


def _whirlpool(serial: str, this_year: int) -> SerialDecode:
    m = _WHIRLPOOL_SERIAL.match(serial)
    week = int(m.group(1)) if m else 0
    if not m or serial[1] not in _WHIRLPOOL_YEARS or not 1 <= week <= 53:
        return _none("serial does not match the nine-character Whirlpool format")
    return _resolve(
        list(_WHIRLPOOL_YEARS[serial[1]]), "whirlpool_serial_dating", f"Whirlpool date code: week {week}", this_year
    )


def _electrolux(serial: str, this_year: int) -> SerialDecode:
    m = _ELECTROLUX_SERIAL.match(serial)
    week = int(m.group(3)) if m else 0
    if not m or not 1 <= week <= 53:
        return _none("serial does not match the ten-character Frigidaire format")
    if m.group(1) not in "AB":
        return _none("second character is not a refrigerator or freezer code")
    years = [y for y in range(MIN_YEAR, this_year + 1) if y % 10 == int(m.group(2))]
    return _resolve(years, "electrolux_serial_dating", f"Frigidaire date code: week {week}", this_year)


_DECODERS: dict[str, Callable[[str, int], SerialDecode]] = {
    "ge": _ge,
    "whirlpool": _whirlpool,
    "electrolux": _electrolux,
}


def decode_as_of(brand: str, serial: str, this_year: int) -> SerialDecode:
    """`decode` with the current year given, so a test does not depend on the clock."""
    key = _BRANDS.get(brand.strip().lower().replace("é", "e"))
    if key is None:
        return _none("no decoder for brand")
    return _DECODERS[key](re.sub(r"[\s-]", "", serial).upper(), this_year)


def decode(brand: str, serial: str) -> SerialDecode:
    return decode_as_of(brand, serial, datetime.date.today().year)
