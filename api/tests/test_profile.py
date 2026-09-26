"""DOE standard ceiling for old units (PLAN.md task 3.5).

Expected values are worked by hand from the equations printed in 10 CFR 430.32(a):
kWh/yr = slope * AV + intercept, rounded to the nearest kWh.
"""

import json
import pathlib
import shutil

import pytest

from app.repository import DATA_DIR, Repository


@pytest.fixture(scope="module")
def repo() -> Repository:
    return Repository.load()


def test_2004_unit_returns_the_formula_value_for_its_volume(repo: Repository) -> None:
    # Class 3, 2001 to 2014 period: 9.80 * 20 + 276.0 = 472.
    ceiling = repo.standard_ceiling(2004, "3", 20.0)
    assert ceiling is not None
    assert (ceiling.kwh_per_year, ceiling.source_type, ceiling.source_id) == (
        472.0,
        "published",
        "doe_standards_refrigerators",
    )


def test_each_period_uses_its_own_equation(repo: Repository) -> None:
    assert repo.standard_ceiling(1995, "4", 25.0).kwh_per_year == 796.0  # 11.8 * 25 + 501
    assert repo.standard_ceiling(2010, "4", 25.0).kwh_per_year == 630.0  # 4.91 * 25 + 507.5 = 630.25
    assert repo.standard_ceiling(2018, "5", 18.0).kwh_per_year == 476.0  # 8.85 * 18 + 317.0 = 476.3


def test_the_year_a_standard_changes_gives_the_higher_ceiling(repo: Repository) -> None:
    # 2001-07-01 and 2014-09-15 fall mid-year and only the year is known.
    assert repo.standard_ceiling(2001, "3", 20.0).kwh_per_year == 675.0  # 1993 equation: 16.0 * 20 + 355
    assert repo.standard_ceiling(2014, "3", 20.0).kwh_per_year == 472.0  # 2001 equation, not 8.07 * 20 + 233.7 = 395
    assert repo.standard_ceiling(2013, "3", 20.0).kwh_per_year == 472.0
    assert repo.standard_ceiling(2015, "3", 20.0).kwh_per_year == 395.0


def test_no_ceiling_is_invented(repo: Repository) -> None:
    assert repo.standard_ceiling(1990, "3", 20.0) is None  # before the 1993 standard
    assert repo.standard_ceiling(2004, "99", 20.0) is None  # unknown class
    assert repo.standard_ceiling(2004, "3I", 20.0) is None  # icemaker classes start in 2014
    assert repo.standard_ceiling(2004, "3", 0.0) is None
    assert repo.standard_ceiling(2004, "3", -5.0) is None


def test_class_is_matched_without_regard_to_case_or_spaces(repo: Repository) -> None:
    assert repo.standard_ceiling(2018, " 3i ", 18.0).kwh_per_year == repo.standard_ceiling(2018, "3I", 18.0).kwh_per_year


def test_a_half_kwh_rounds_up(tmp_path: pathlib.Path) -> None:
    for name in ("sources.json", "rates.json"):
        shutil.copy(DATA_DIR / name, tmp_path / name)
    (tmp_path / "doe_standards_refrigerators.json").write_text(
        json.dumps(
            {
                "source_id": "doe_standards_refrigerators",
                "classes": {
                    "X": {"periods": [{"manufactured_from": "2000-01-01", "manufactured_to": None, "slope": 0.5, "intercept": 100.0}]}
                },
            }
        ),
        encoding="utf-8",
    )
    assert Repository.load(tmp_path).standard_ceiling(2004, "X", 1.0).kwh_per_year == 101.0


def test_every_period_is_plausible_and_sourced(repo: Repository) -> None:
    raw = json.loads((DATA_DIR / "doe_standards_refrigerators.json").read_text(encoding="utf-8"))
    assert raw["source_id"] in {s.id for s in repo.sources()}
    assert raw["classes"]
    for product_class, entry in raw["classes"].items():
        assert entry["periods"], product_class
        for p in entry["periods"]:
            assert 0 < p["slope"] < 20, (product_class, p)
            assert 100 < p["intercept"] < 600, (product_class, p)
            assert p["name"].strip(), (product_class, p)
            assert p["manufactured_to"] is None or p["manufactured_from"] < p["manufactured_to"]
