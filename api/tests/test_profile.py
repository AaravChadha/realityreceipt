import csv

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
