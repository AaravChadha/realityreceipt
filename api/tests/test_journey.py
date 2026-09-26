"""Real-data journey (task 2.7.2): the same calls the entry page makes, on the committed data.

Component tests use stand-ins; this one runs the real Repository through the real routes, so a
gap between the rows (missing data, a stub route, an unresolvable source) fails here.
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from app.main import app
from app.models import Item, Path, Source

RESERVED = {"user", "user_listing", "user_lease"}
YOUR_FRIDGE = {"id": "current", "category": "refrigerator", "brand": "Frigidaire", "model": "FFHT1822UW",
               "condition": "used_as_is", "mfg_year": 2016}
LISTED = {"id": "listing", "category": "refrigerator", "brand": "Frigidaire", "model": "FFHT1822UV",
          "condition": "used_as_is", "mfg_year": 2018}


@pytest.fixture(scope="module")
def receipt() -> list[Path]:
    client = TestClient(app)
    current = client.post("/item", json=YOUR_FRIDGE).json()
    listed = client.post("/item", json=LISTED).json()
    body = {
        "current": current,
        "items": [listed],
        "offers": [{"item_id": "listing", "price": 300, "seller_type": "private", "source": "user_listing",
                    "source_id": "user_listing"}],
        "repair_quote_low": 150,
        "repair_quote_high": 150,
    }
    response = client.post("/quote", json=body)
    assert response.status_code == 200, response.text
    return TypeAdapter(list[Path]).validate_python(response.json())


@pytest.fixture(scope="module")
def source_ids() -> set[str]:
    response = TestClient(app).get("/sources")
    assert response.status_code == 200
    return {s.id for s in TypeAdapter(list[Source]).validate_python(response.json())}


def test_the_receipt_is_real(receipt: list[Path]) -> None:
    assert receipt, "a real request returned no paths"
    assert not any("fixture" in p.flags for p in receipt)
    assert {"repair", "used_as_is"} <= {p.group for p in receipt}


def test_electricity_is_rated_from_the_data(receipt: list[Path]) -> None:
    rated = [ln for p in receipt for ln in p.lines if ln.kind == "running" and ln.source_type == "rated"]
    assert rated, "no rated electricity line: the model lookup found nothing"
    assert all(ln.source_id == "energystar_refrigerators" for ln in rated)


def test_every_source_on_the_receipt_resolves(receipt: list[Path], source_ids: set[str]) -> None:
    named = {ln.source_id for p in receipt for ln in p.lines if ln.source_id}
    named |= {i for p in receipt for ln in p.lines for i in ln.other_source_ids}
    named |= {i for p in receipt for i in p.carbon_source_ids}
    assert named - RESERVED - source_ids == set()


def test_item_route_keeps_typed_units_as_typed() -> None:
    got = Item.model_validate(TestClient(app).post("/item", json=LISTED).json())
    assert (got.brand, got.model, got.mfg_year) == ("Frigidaire", "FFHT1822UV", 2018)
