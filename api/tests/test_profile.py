import csv
import gzip
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
    assert len(rows) >= 4000, "the full ENERGY STAR dataset, not a brand subset"
    assert list(rows[0]) == ["brand", "model_number", "model_normalized", "annual_kwh", "product_class"]
    keys = [(r["brand"], r["model_normalized"], r["annual_kwh"], r["product_class"]) for r in rows]
    assert len(keys) == len(set(keys)), "one row per brand, model, kWh and class"
    for r in rows:
        assert r["model_normalized"] == normalize_model(r["model_number"])
        assert float(r["annual_kwh"]) > 0
        assert r["product_class"], "every ENERGY STAR row carries its CFR class"
    assert not any("Ã" in r["brand"] for r in rows), "brand names are decoded as UTF-8"


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


def test_label_family_and_a_retail_number_built_from_it_return_the_familys_kwh(repo: Repository) -> None:
    family = repo.model_energy("GE", "GTE18FSL****")
    assert family is not None
    assert (family.kwh_per_year, family.source_type, family.source_id) == (363.0, "rated", "energystar_refrigerators")
    assert repo.model_energy("GE", "GTE18FSLRWW") == family
    assert repo.model_energy("GE", "GTE18FSL") == family, "every wildcard may be blank"
    assert repo.model_energy("GE", "GTE18FSLRWWXY") is None, "one wildcard too many"


def test_another_brands_row_is_never_returned(repo: Repository) -> None:
    assert repo.model_energy("LG", "GTE18FSLRWW") is None
    assert repo.model_energy("Whirlpool", "GBE17HYR") is None
    assert repo.model_energy("", "GBE17HYR") is None
    assert "GTE18FSL****" in repo.model_candidates("GTE18FSLRWW"), "candidates are hints, not answers"


def test_brand_names_match_without_regard_to_case_punctuation_or_the_ge_alias(repo: Repository) -> None:
    assert repo.model_energy("GE Appliances", "GBE17HYR") == repo.model_energy("GE", "GBE17HYR")
    assert repo.model_energy("g.e.", "GBE17HYR") == repo.model_energy("GE", "GBE17HYR")
    assert repo.model_energy("GEA", "GBE17HYR") is None
    assert repo.model_energy("GE Profile", "GBE17HYR") is None, "a sub-brand is not an alias"


def test_electrolux_and_frigidaire_fall_back_to_each_other(repo: Repository) -> None:
    # The Frigidaire demo card's EnergyGuide prints the maker, not the brand.
    card = repo.model_energy("Electrolux Home Products Inc.", "FFHT1822U*")
    assert card is not None and card.kwh_per_year == 360.0
    assert repo.model_energy("Electrolux", "FFHT1822UW") == repo.model_energy("Frigidaire", "FFHT1822UW")
    # Listed under both names at different kWh: each brand keeps its own figure.
    assert repo.model_energy("Frigidaire", "ERQR32E3HSS").kwh_per_year == 409.0
    assert repo.model_energy("Electrolux", "ERQR32E3HSS").kwh_per_year == 438.0
    assert repo.model_energy("Kenmore", "FFHT1822UW") is None, "a house brand is not the maker"


def test_a_model_listed_at_two_kwh_is_not_guessed(repo: Repository) -> None:
    # GTE18DCN**** appears at 359 and 443 kWh.
    assert repo.model_energy("GE", "GTE18DCN****") is None
    assert repo.model_energy("GE", "GTE18DCNRWW") is None
    assert "GTE18DCN****" in repo.model_candidates("GTE18DCNRWW")


def test_product_class_resolves_the_icemaker_pair(repo: Repository) -> None:
    # ENERGY STAR rates these twice: class 3 without an icemaker, 3I with one.
    assert repo.model_energy("GE", "GTE18DTNRWW", "3").kwh_per_year == 359.0
    assert repo.model_energy("GE", "GTE18DTNRWW", "3I").kwh_per_year == 443.0
    assert repo.model_energy("GE", "GTE18DTNRWW") is None
    assert repo.model_energy("Frigidaire", "FFHT1814WW", "3").kwh_per_year == 369.0
    assert repo.model_energy("Frigidaire", "FFHT1814WW", "3I").kwh_per_year == 453.0


def test_class_resolves_the_doe_icemaker_pair_of_a_retailer_model(repo: Repository) -> None:
    # Not in ENERGY STAR; DOE lists each twice, 84 kWh apart (without and with an icemaker).
    assert repo.model_energy("Frigidaire", "FFTR1814WW", "3").kwh_per_year == 410.0
    assert repo.model_energy("Frigidaire", "FFTR1814WW", "3I").kwh_per_year == 494.0
    assert repo.model_energy("Whirlpool", "WRT318FZDM", "3").kwh_per_year == 411.0
    assert repo.model_energy("Whirlpool", "WRT318FZDM", "3").source_id == "doe_wap_refrigerators"
    assert repo.model_energy("Frigidaire", "FFTR1814WW") is None
    assert repo.model_energy("Whirlpool", "WRT318FZDM") is None


def _repo_with(tmp_path: pathlib.Path, rows: list[tuple[str, str, float]]) -> Repository:
    for name in ("sources.json", "rates.json"):
        shutil.copy(DATA_DIR / name, tmp_path / name)
    lines = ["brand,model_number,model_normalized,annual_kwh"]
    lines += [f"{b},{m},{normalize_model(m)},{k}" for b, m, k in rows]
    (tmp_path / "energystar_refrigerators.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return Repository.load(tmp_path)


def test_two_matches_with_different_kwh_return_none_with_both_as_candidates(tmp_path: pathlib.Path) -> None:
    repo = _repo_with(tmp_path, [("Acme", "AB12*", 300), ("Acme", "AB1*3", 350)])
    assert repo.model_energy("Acme", "AB123") is None
    assert sorted(repo.model_candidates("AB123")) == ["AB1*3", "AB12*"]


def test_matches_that_agree_on_kwh_return_it(tmp_path: pathlib.Path) -> None:
    repo = _repo_with(tmp_path, [("Acme", "AB12*", 300), ("Acme", "AB1*3", 300)])
    hit = repo.model_energy("Acme", "AB123")
    assert hit is not None and hit.kwh_per_year == 300.0


def test_the_row_with_the_fewest_wildcards_wins(tmp_path: pathlib.Path) -> None:
    repo = _repo_with(tmp_path, [("Acme", "AB123", 300), ("Acme", "AB12*", 350), ("Acme", "AB***", 400)])
    assert repo.model_energy("Acme", "AB123").kwh_per_year == 300.0
    assert repo.model_energy("Acme", "AB124").kwh_per_year == 350.0
    assert repo.model_energy("Acme", "AB1").kwh_per_year == 400.0


def test_hash_is_one_optional_character_and_a_query_with_wildcards_needs_the_same_pattern(tmp_path: pathlib.Path) -> None:
    repo = _repo_with(tmp_path, [("Acme", "AB12#C", 300), ("Acme", "AB99C", 310)])
    assert repo.model_energy("Acme", "AB12C").kwh_per_year == 300.0
    assert repo.model_energy("Acme", "AB127C").kwh_per_year == 300.0
    assert repo.model_energy("Acme", "AB1277C") is None
    assert repo.model_energy("Acme", "AB12#C").kwh_per_year == 300.0
    assert repo.model_energy("Acme", "AB12*C") is None, "a different pattern is not the same model"
    assert repo.model_energy("Acme", "AB9#C") is None, "a wildcard query does not match a concrete row"


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


# DOE historical ratings (task 2.2.2)

MAYTAG_LABEL = DATA_DIR.parents[2] / "demo" / "cards" / "label-older-maytag-mb2562.png"


def test_doe_file_shape() -> None:
    with gzip.open(DATA_DIR / "doe_wap_refrigerators.csv.gz", "rt", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) > 90_000
    assert list(rows[0]) == ["brand", "model_number", "model_normalized", "year", "annual_kwh"]
    keys = [(r["brand"].casefold(), r["model_normalized"], r["year"], r["annual_kwh"]) for r in rows]
    assert len(keys) == len(set(keys)), "one row per brand, model, year and kWh"
    for r in rows:
        assert r["model_normalized"] == normalize_model(r["model_number"])
        assert 1949 <= int(r["year"]) <= 2021
        assert 0 < float(r["annual_kwh"]) < 5000


def test_the_doe_source_is_recorded_and_used_by_the_profile(repo: Repository, profile: CategoryProfile) -> None:
    assert "doe_wap_refrigerators" in {s.id for s in repo.sources()}
    assert "doe_wap_refrigerators" in profile.energy_dataset_refs


def test_the_maytag_family_on_the_demo_card_returns_the_doe_kwh_and_a_year(repo: Repository) -> None:
    assert MAYTAG_LABEL.exists(), "demo card label-older-maytag-mb2562.png"
    # The card's family is MB*2562***; DOE lists Maytag MB*2562HE* at 505 kWh (the figure on the label) for 2005 to 2009.
    hit = repo.model_energy("Maytag", "MB*2562***")
    assert hit is not None
    assert (hit.kwh_per_year, hit.source_type, hit.source_id) == (505.0, "rated", "doe_wap_refrigerators")
    assert repo.model_year("Maytag", "MB*2562***") == 2009
    assert repo.model_energy("Maytag", "MB*2562HE*") == hit
    assert repo.model_energy("maytag", "mbb-2562 he") == hit, "a full retail number built from the family"


def test_the_doe_lookup_is_brand_matched_and_never_guesses(repo: Repository) -> None:
    assert repo.model_energy("Whirlpool", "MB*2562***") is None
    assert repo.model_year("Whirlpool", "MB*2562***") is None
    assert repo.model_energy("Maytag", "MB*2562") is None, "a family with no trailing wildcards needs the same pattern"
    assert repo.model_energy("Maytag", "ZZZ999") is None
    assert repo.model_year("Maytag", "ZZZ999") is None
    assert repo.model_year("Maytag", "MBF2562HE") == 2005, "a different unit in the same family has its own rating and year"
    assert repo.model_energy("Maytag", "MBF2562HE").kwh_per_year == 488.0


def test_energy_star_wins_and_an_ambiguous_energy_star_model_does_not_fall_back(repo: Repository) -> None:
    assert repo.model_energy("GE", "GBE17HYR").source_id == "energystar_refrigerators"
    # GTE18DCN**** is at 359 and 443 kWh in ENERGY STAR, and DOE also lists it: still no figure.
    assert repo.model_energy("GE", "GTE18DCN****") is None


def test_the_cafe_accent_does_not_matter(repo: Repository) -> None:
    assert repo.model_energy("Café", "CYE22TP4MW2") == repo.model_energy("Cafe", "CYE22TP4MW2")


def _repo_with_doe(tmp_path: pathlib.Path, es: list[tuple[str, str, float]], doe: list[tuple[str, str, int, float]]) -> Repository:
    repo_dir = tmp_path
    for name in ("sources.json", "rates.json"):
        shutil.copy(DATA_DIR / name, repo_dir / name)
    lines = ["brand,model_number,model_normalized,annual_kwh"] + [f"{b},{m},{normalize_model(m)},{k}" for b, m, k in es]
    (repo_dir / "energystar_refrigerators.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    lines = ["brand,model_number,model_normalized,year,annual_kwh"]
    lines += [f"{b},{m},{normalize_model(m)},{y},{k}" for b, m, y, k in doe]
    with gzip.open(repo_dir / "doe_wap_refrigerators.csv.gz", "wt", newline="", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return Repository.load(repo_dir)


def test_doe_is_the_fallback_only_when_energy_star_has_no_match(tmp_path: pathlib.Path) -> None:
    repo = _repo_with_doe(tmp_path, [("Acme", "AB12*", 300)], [("Acme", "AB12*", 1999, 400), ("Acme", "CD34", 1990, 500)])
    assert repo.model_energy("Acme", "AB123").source_id == "energystar_refrigerators"
    assert repo.model_energy("Acme", "AB123").kwh_per_year == 300.0
    assert repo.model_energy("Acme", "CD34").source_id == "doe_wap_refrigerators"
    assert repo.model_year("Acme", "CD34") == 1990
    assert repo.model_year("Acme", "AB123") == 1999, "the year comes from DOE even when ENERGY STAR gives the kWh"


def test_doe_rows_that_disagree_on_kwh_return_none_but_still_have_a_year(tmp_path: pathlib.Path) -> None:
    repo = _repo_with_doe(tmp_path, [], [("Acme", "CD34", 1990, 500), ("Acme", "CD34", 1993, 450), ("Acme", "CD34", 1995, 450)])
    assert repo.model_energy("Acme", "CD34") is None
    assert repo.model_candidates("CD34") == ["CD34"]
    assert repo.model_year("Acme", "CD34") == 1995


def test_a_family_matches_by_core_and_trailing_room_only(tmp_path: pathlib.Path) -> None:
    doe = [("Acme", "MB*2562HE*", 2005, 505), ("Acme", "MB*2562HEXYZ", 2006, 999), ("Acme", "MB*2562KE*", 2007, 480)]
    repo = _repo_with_doe(tmp_path, [], doe)
    # MB*2562*** adds room for three characters: HE* and KE* fit, HEXYZ does not, and they disagree.
    assert repo.model_energy("Acme", "MB*2562***") is None
    assert repo.model_candidates("MB*2562***")[:2] == ["MB*2562HE*", "MB*2562KE*"], "the family's matches come first"
    (tmp_path / "one").mkdir()
    only_one = _repo_with_doe(tmp_path / "one", [], doe[:1])
    assert only_one.model_energy("Acme", "MB*2562***").kwh_per_year == 505.0
    assert only_one.model_energy("Acme", "MB*2562**") is None, "two trailing wildcards leave no room for HE*"
    assert only_one.model_energy("Acme", "MB*2562HE*").kwh_per_year == 505.0, "an identical pattern needs no family rule"


def test_an_identical_pattern_beats_the_family_rule(tmp_path: pathlib.Path) -> None:
    repo = _repo_with_doe(tmp_path, [("Acme", "MB*2562***", 300), ("Acme", "MB*2562HE*", 505)], [])
    assert repo.model_energy("Acme", "MB*2562***").kwh_per_year == 300.0


def test_a_missing_doe_file_gives_no_year(tmp_path: pathlib.Path) -> None:
    for name in ("sources.json", "rates.json"):
        shutil.copy(DATA_DIR / name, tmp_path / name)
    repo = Repository.load(tmp_path)
    assert repo.model_year("Maytag", "MB*2562***") is None
    assert repo.model_energy("Maytag", "MB*2562***") is None
