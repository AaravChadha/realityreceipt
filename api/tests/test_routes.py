import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from app.main import app
from app.models import Item, Path, RankedOffer, ScanResult, ShopFilters, Source

ITEM = {"id": "current", "category": "refrigerator", "brand": "Acme", "model": "AR18", "condition": "used_as_is"}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_quote_returns_paths(client: TestClient) -> None:
    response = client.post("/quote", json={"current": ITEM})
    assert response.status_code == 200
    assert len(TypeAdapter(list[Path]).validate_python(response.json())) == 9


def test_quote_rejects_unknown_fields(client: TestClient) -> None:
    assert client.post("/quote", json={"income": 30000}).status_code == 422


def test_scan_stub(client: TestClient) -> None:
    response = client.post("/scan", data={"kind": "label"}, files={"image": ("label.jpg", b"\xff\xd8", "image/jpeg")})
    assert response.status_code == 200
    result = ScanResult.model_validate(response.json())
    assert result.valid is False and result.kind == "label"


def test_item_echoes(client: TestClient) -> None:
    response = client.post("/item", json=ITEM)
    assert response.status_code == 200
    assert Item.model_validate(response.json()).id == "current"


def test_shop_parse_stub(client: TestClient) -> None:
    response = client.post("/shop/parse", json={"text": "about $300, small space"})
    assert response.status_code == 200
    ShopFilters.model_validate(response.json())


def test_shop_rank_stub(client: TestClient) -> None:
    response = client.post("/shop/rank", json={"filters": {}})
    assert response.status_code == 200
    assert TypeAdapter(list[RankedOffer]).validate_python(response.json()) == []


def test_categories(client: TestClient) -> None:
    assert client.get("/categories").json() == ["refrigerator"]


def test_sources_stub(client: TestClient) -> None:
    response = client.get("/sources")
    assert response.status_code == 200
    assert TypeAdapter(list[Source]).validate_python(response.json()) == []
