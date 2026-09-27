import gzip
import json
import pathlib
import shutil

import pytest

from app.engine.financing import bnpl
from app.models import BnplTerms, RateValue
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


RATE_RANGES = {
    "ga_power_marginal_per_kwh": (0.05, 0.40),  # dollars per kWh
    "egrid_ga_kg_per_kwh": (0.1, 1.2),  # kg CO2e per kWh, not lb/MWh
    "g19_card_apr_assessed": (0.05, 0.60),  # a fraction, not 22.15
    "pal_rate_cap": (0.05, 0.60),  # a fraction, not 28
    "pal_fee_cap": (1.0, 100.0),  # dollars
    "pal_max_amount": (100.0, 10000.0),  # dollars
}


def test_every_rate_lies_in_its_unit_range(repo: Repository) -> None:
    assert set(RATE_RANGES) == set(RATE_KEYS)
    for key, (low, high) in RATE_RANGES.items():
        assert low <= repo.rate(key).value <= high, key


def test_retailer_sources_exist(repo: Repository) -> None:
    ids = {s.id for s in repo.sources()}
    assert {"retailer_cache_bestbuy", "retailer_cache_homedepot", "retailer_cache_lowes"} <= ids


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


def test_product_class_picks_between_icemaker_ratings(bare_dir: pathlib.Path) -> None:
    (bare_dir / "energystar_refrigerators.csv").write_text(
        "brand,model_number,model_normalized,annual_kwh,product_class\n"
        "Acme,AB1*,AB1*,369,3\n"
        "Acme,AB1*,AB1*,453,3I\n",
        encoding="utf-8",
    )
    repo = Repository.load(bare_dir)
    assert repo.model_energy("Acme", "AB1W") is None, "without a class the two ratings disagree"
    assert repo.model_energy("Acme", "AB1W", "3").kwh_per_year == 369.0
    assert repo.model_energy("Acme", "AB1W", "3i").kwh_per_year == 453.0
    assert repo.model_energy("Acme", "AB1W", 3.0).kwh_per_year == 369.0, "a class sent as a number"
    assert repo.model_energy("Acme", "AB1W", "5I") is None, "a class it is not rated in falls back to all rows"


def _doe_pair_repo(bare_dir: pathlib.Path, *kwh: float, standards: bool = True) -> Repository:
    """A DOE file listing Acme `AB1*` once per figure in `kwh`, beside the real DOE standards."""
    lines = ["brand,model_number,model_normalized,year,annual_kwh"] + [f"Acme,AB1*,AB1*,2020,{k}" for k in kwh]
    with gzip.open(bare_dir / "doe_wap_refrigerators.csv.gz", "wt", newline="", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    if standards:
        shutil.copy(DATA_DIR / "doe_standards_refrigerators.json", bare_dir / "doe_standards_refrigerators.json")
    return Repository.load(bare_dir)


def test_a_doe_pair_one_icemaker_adder_apart_resolves_by_class(bare_dir: pathlib.Path) -> None:
    # DOE has no class column; 3I's standard is 3's plus 84 kWh, and so is the second rating.
    repo = _doe_pair_repo(bare_dir, 410, 494)
    hit = repo.model_energy("Acme", "AB1W", "3")
    assert hit is not None
    assert (hit.kwh_per_year, hit.source_type, hit.source_id) == (410.0, "rated", "doe_wap_refrigerators")
    assert repo.model_energy("Acme", "AB1W", "3I").kwh_per_year == 494.0
    assert repo.model_energy("Acme", "AB1W", "3i").kwh_per_year == 494.0
    assert repo.model_energy("Acme", "AB1W", 3.0).kwh_per_year == 410.0, "a class sent as a number"
    assert repo.model_energy("Acme", "AB1W", "5I-BI") is not None, "every base class with an icemaker form"
    assert repo.model_energy("Acme", "AB1W") is None, "without a class the pair still disagrees"
    assert repo.model_energy("Acme", "AB1W", "7") is None, "class 7 has no icemaker form"
    assert repo.model_energy("Acme", "AB1W", "3A") is None, "3A is not 3I's base"


def test_a_doe_disagreement_that_is_not_an_icemaker_pair_stays_none(bare_dir: pathlib.Path) -> None:
    # Standards first: each call rewrites the DOE file, and the standards file stays once copied.
    assert _doe_pair_repo(bare_dir, 410, 494, standards=False).model_energy("Acme", "AB1W", "3") is None, (
        "no standards file, no adder"
    )
    assert _doe_pair_repo(bare_dir, 410, 460).model_energy("Acme", "AB1W", "3") is None, "50 kWh apart"
    assert _doe_pair_repo(bare_dir, 410, 494, 578).model_energy("Acme", "AB1W", "3") is None, "three figures"


def test_the_icemaker_pair_rule_never_touches_energy_star(bare_dir: pathlib.Path) -> None:
    (bare_dir / "energystar_refrigerators.csv").write_text(
        "brand,model_number,model_normalized,annual_kwh\nAcme,AB1*,AB1*,410\nAcme,AB1*,AB1*,494\n",
        encoding="utf-8",
    )
    shutil.copy(DATA_DIR / "doe_standards_refrigerators.json", bare_dir / "doe_standards_refrigerators.json")
    assert Repository.load(bare_dir).model_energy("Acme", "AB1W", "3") is None


def test_same_maker_is_asked_only_when_the_brand_has_no_row(bare_dir: pathlib.Path) -> None:
    (bare_dir / "energystar_refrigerators.csv").write_text(
        "brand,model_number,model_normalized,annual_kwh\n"
        "Frigidaire,AB1,AB1,300\n"
        "Electrolux,AB1,AB1,350\n"
        "Frigidaire,CD2,CD2,400\n",
        encoding="utf-8",
    )
    repo = Repository.load(bare_dir)
    assert repo.model_energy("Electrolux", "AB1").kwh_per_year == 350.0
    assert repo.model_energy("Frigidaire", "AB1").kwh_per_year == 300.0
    assert repo.model_energy("Electrolux", "CD2").kwh_per_year == 400.0
    assert repo.model_energy("Electrolux Home Products Inc.", "CD2").kwh_per_year == 400.0
    assert repo.model_energy("Whirlpool", "CD2") is None


def test_item_lookup_by_id(bare_dir: pathlib.Path) -> None:
    assert Repository.load(bare_dir).item("fridge-1") is None
    (bare_dir / "retailer_cache.json").write_text(
        json.dumps(
            {
                "items": [{"id": "fridge-1", "category": "refrigerator", "brand": "Acme", "model": "AB-123", "condition": "new"}],
                "offers": [
                    {
                        "item_id": "fridge-1",
                        "price": 899.0,
                        "seller_type": "retailer",
                        "source": "retailer_cache",
                        "source_id": "retailer_cache_homedepot",
                        "url": "https://www.homedepot.com/",
                        "retrieved_at": "2026-09-26",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    repo = Repository.load(bare_dir)
    item = repo.item("fridge-1")
    assert item is not None and (item.brand, item.model) == ("Acme", "AB-123")
    assert repo.item("missing") is None
    (offer,) = repo.new_offers("refrigerator")
    assert repo.item(offer.item_id) == item


def test_bnpl_terms_are_one_sourced_provider(repo: Repository) -> None:
    terms = repo.bnpl_terms()
    assert terms is not None
    assert (terms.provider, terms.installments, terms.interval_weeks, terms.apr) == ("Afterpay", 4, 2, 0.0)
    source = repo.source(terms.source_id)
    assert source.url.startswith("https://") and "0% interest" in source.notes


def test_bnpl_terms_feed_the_bnpl_path(repo: Repository) -> None:
    terms = repo.bnpl_terms()
    assert isinstance(terms, BnplTerms)
    path = bnpl(1000.0, terms)
    assert path.pay_today == 250.0
    assert path.lines[0].source_type == "published" and path.lines[0].source_id == terms.source_id
    assert path.lines[0].amount_low == 0.0  # 0% interest when paid on time; late fees are not modeled


STANDARDS_SOURCE_ID = json.loads((DATA_DIR / "doe_standards_refrigerators.json").read_text(encoding="utf-8"))["source_id"]


def test_an_adder_picked_figure_says_so_and_names_the_standards_source(bare_dir: pathlib.Path) -> None:
    repo = _doe_pair_repo(bare_dir, 410, 494)
    without = repo.model_energy("Acme", "AB1W", "3")
    assert without is not None and without.kwh_per_year == 410.0
    assert without.note == (
        "DOE lists this model at two figures one icemaker apart; the lower is taken for a unit without an automatic icemaker"
    )
    assert without.note_source_ids == [STANDARDS_SOURCE_ID]
    with_icemaker = repo.model_energy("Acme", "AB1W", "3I")
    assert with_icemaker is not None and with_icemaker.kwh_per_year == 494.0
    assert with_icemaker.note == (
        "DOE lists this model at two figures one icemaker apart; the higher is taken for a unit with an automatic icemaker"
    )
    assert with_icemaker.note_source_ids == [STANDARDS_SOURCE_ID]
    assert STANDARDS_SOURCE_ID in {s.id for s in repo.sources()}


def test_a_directly_rated_figure_carries_no_note(bare_dir: pathlib.Path) -> None:
    single = _doe_pair_repo(bare_dir, 410).model_energy("Acme", "AB1W", "3")
    assert single is not None and single.kwh_per_year == 410.0
    assert (single.note, single.note_source_ids) == ("", [])
    (bare_dir / "energystar_refrigerators.csv").write_text(
        "brand,model_number,model_normalized,annual_kwh\nAcme,AB1*,AB1*,400\n", encoding="utf-8"
    )
    rated = Repository.load(bare_dir).model_energy("Acme", "AB1W", "3")
    assert rated is not None and (rated.source_id, rated.note, rated.note_source_ids) == ("energystar_refrigerators", "", [])
