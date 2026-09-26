import json
import pathlib
import shutil

import pytest

from app.models import RateValue
from app.repository import DATA_DIR, RATE_KEYS, Repository, normalize_model


@pytest.fixture(scope="module")
def repo() -> Repository:
    return Repository.load()


@pytest.fixture
def bare_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """Only the two required files, as before tasks 2.2, 2.3, 3.5 and 3.6 land."""
    for name in ("sources.json", "rates.json"):
        shutil.copy(DATA_DIR / name, tmp_path / name)
    return tmp_path


def test_every_rate_key_loads(repo: Repository) -> None:
    for key in RATE_KEYS:
        assert isinstance(repo.rate(key), RateValue)


def test_every_rate_source_resolves(repo: Repository) -> None:
    ids = {s.id for s in repo.sources()}
    for key in RATE_KEYS:
        assert repo.rate(key).source_id in ids
        assert repo.source(repo.rate(key).source_id).id == repo.rate(key).source_id


def test_every_rate_has_notes() -> None:
    raw = json.loads((DATA_DIR / "rates.json").read_text(encoding="utf-8"))
    assert set(raw) == set(RATE_KEYS)
    for key, entry in raw.items():
        assert entry["notes"].strip(), key


def test_every_source_has_url_and_date(repo: Repository) -> None:
    for s in repo.sources():
        assert s.url.startswith("https://"), s.id
        assert s.retrieved_date is not None
        assert s.notes.strip(), s.id


def test_unknown_ids_raise(repo: Repository) -> None:
    with pytest.raises(KeyError):
        repo.source("nope")
    with pytest.raises(KeyError):
        repo.rate("nope")


def test_normalize_model() -> None:
    assert normalize_model("GTE18-GTH/RWW") == "GTE18GTHRWW"
    assert normalize_model(" wrt.318fz dw ") == "WRT318FZDW"


def test_optional_files_absent_give_empty_answers(bare_dir: pathlib.Path) -> None:
    repo = Repository.load(bare_dir)
    with pytest.raises(KeyError):
        repo.profile("refrigerator")
    assert repo.model_energy("GE", "GTE18GTHRWW") is None
    assert repo.model_candidates("GTE18GTHRWW") == []
    assert repo.standard_ceiling(2004, "3", 18.0) is None
    assert repo.new_offers("refrigerator") == []
    assert repo.bnpl_terms() is None


def test_energy_lookup_is_exact_with_candidates_on_a_miss(bare_dir: pathlib.Path) -> None:
    (bare_dir / "energystar_refrigerators.csv").write_text(
        "brand,model_number,model_normalized,annual_kwh\n"
        "Acme,AB-123/X,AB123X,400\n"
        "Acme,AB-124,AB124,410\n",
        encoding="utf-8",
    )
    repo = Repository.load(bare_dir)
    hit = repo.model_energy("Acme", "ab 123x")
    assert hit is not None
    assert (hit.kwh_per_year, hit.source_type, hit.source_id) == (400.0, "rated", "energystar_refrigerators")
    assert repo.model_energy("Acme", "AB123Y") is None
    assert repo.model_candidates("AB123Y") == ["AB-123/X"]
