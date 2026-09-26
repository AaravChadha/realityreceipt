import csv
import json
import pathlib
import shutil

from app.models import CategoryProfile
from app.repository import DATA_DIR, Repository, normalize_model

import pytest


@pytest.fixture(scope="module")
def repo() -> Repository:
    return Repository.load()


@pytest.fixture(scope="module")
def profile(repo: Repository) -> CategoryProfile:
    return repo.profile("refrigerator")


def test_profile_validates(profile: CategoryProfile) -> None:
    assert profile.category == "refrigerator"
    assert profile.carbon_applicable is True
    assert profile.lifespan_range is not None
    assert 0 < profile.lifespan_range.low_years <= profile.lifespan_range.high_years


def test_every_profile_source_resolves(repo: Repository, profile: CategoryProfile) -> None:
    ids = {s.id for s in repo.sources()}
    refs = list(profile.energy_dataset_refs)
    refs += [u.source_id for u in profile.upkeep_schedule]
    refs += [r.source_id for r in profile.repair_ranges]
    if profile.lifespan_range:
        refs.append(profile.lifespan_range.source_id)
    assert refs
    assert set(refs) <= ids
    for r in profile.repair_ranges:
        assert r.cost_low <= r.cost_high


def test_csv_shape() -> None:
    path = DATA_DIR / "energystar_refrigerators.csv"
    assert path.stat().st_size < 1_000_000
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows
    assert list(rows[0]) == ["brand", "model_number", "model_normalized", "annual_kwh"]
    keys = [(r["brand"], r["model_normalized"]) for r in rows]
    assert len(keys) == len(set(keys)), "one row per brand and model"
    for r in rows:
        assert r["model_normalized"] == normalize_model(r["model_number"]).rstrip("*")
        assert float(r["annual_kwh"]) > 0


def test_known_demo_model_returns_its_csv_kwh(repo: Repository) -> None:
    hit = repo.model_energy("GE", "GBE17HYR")
    assert hit is not None
    assert (hit.kwh_per_year, hit.source_type, hit.source_id) == (454.0, "rated", "energystar_refrigerators")
    assert repo.model_energy("ge", "gbe-17 hyr") == hit


def test_one_character_typo_misses_with_candidates(repo: Repository) -> None:
    assert repo.model_energy("GE", "GBE17HYQ") is None
    candidates = repo.model_candidates("GBE17HYQ")
    assert 1 <= len(candidates) <= 5
    assert any(c.startswith("GBE17HY") for c in candidates)


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
