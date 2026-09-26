import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from app.main import app
from app.models import Item, Path, RankedOffer, ScanResult, ShopFilters, Source

ITEM = {"id": "current", "category": "refrigerator", "brand": "Acme", "model": "AR18", "condition": "used_as_is"}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


LISTED = {"id": "listing", "category": "refrigerator", "brand": "Frigidaire", "model": "FFHT1822UV",
          "condition": "used_as_is", "mfg_year": 2018}
LISTING_OFFER = {"item_id": "listing", "price": 300, "seller_type": "private", "source": "user_listing",
                 "source_id": "user_listing"}


def test_quote_runs_the_real_engine(client: TestClient) -> None:
    response = client.post("/quote", json={"items": [LISTED], "offers": [LISTING_OFFER]})
    assert response.status_code == 200
    paths = TypeAdapter(list[Path]).validate_python(response.json())
    assert paths and not any("fixture" in p.flags for p in paths)
    used = next(p for p in paths if p.group == "used_as_is")
    assert any(line.kind == "running" and line.source_type == "rated" for line in used.lines)


def test_quote_depends_on_the_request(client: TestClient) -> None:
    cheap = client.post("/quote", json={"items": [LISTED], "offers": [{**LISTING_OFFER, "price": 100}]}).json()
    dear = client.post("/quote", json={"items": [LISTED], "offers": [{**LISTING_OFFER, "price": 500}]}).json()
    assert cheap != dear


def test_quote_unknown_category_is_a_clear_422(client: TestClient) -> None:
    response = client.post("/quote", json={"items": [{**LISTED, "category": "toaster"}], "offers": [LISTING_OFFER]})
    assert response.status_code == 422
    assert "toaster" in response.json()["detail"]


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


def test_item_fills_year_from_serial(client: TestClient) -> None:
    body = {**ITEM, "brand": "Whirlpool", "serial": "MK1402320"}  # letter K is 2000 (test_serial.py)
    got = Item.model_validate(client.post("/item", json=body).json())
    assert (got.mfg_year, got.year_confidence) == (2000, "high")


def test_item_keeps_a_typed_year(client: TestClient) -> None:
    body = {**ITEM, "brand": "Whirlpool", "serial": "MK1402320", "mfg_year": 2003}
    assert Item.model_validate(client.post("/item", json=body).json()).mfg_year == 2003


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


def test_sources_are_the_real_sources(client: TestClient) -> None:
    response = client.get("/sources")
    assert response.status_code == 200
    ids = {s.id for s in TypeAdapter(list[Source]).validate_python(response.json())}
    assert {"energystar_refrigerators", "ga_power_residential_tariff", "egrid_georgia"} <= ids


def test_one_address_serves_the_built_app_and_the_api(tmp_path) -> None:
    from app.main import create_app

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>RealityReceipt</title>")
    (dist / "assets" / "app.js").write_text("console.log('app')")
    (tmp_path / "secret.txt").write_text("do not serve")
    one = TestClient(create_app(dist))
    assert "RealityReceipt" in one.get("/").text
    assert "RealityReceipt" in one.get("/receipt/anything").text  # a client-side route gets index.html
    assert one.get("/assets/app.js").text == "console.log('app')"
    assert one.get("/api/health").json() == {"ok": True}
    assert one.post("/api/quote", json={"items": [LISTED], "offers": [LISTING_OFFER]}).status_code == 200
    assert one.get("/api/nope").status_code == 404
    assert "do not serve" not in one.get("/..%2Fsecret.txt").text


def test_without_a_build_only_the_api_is_served() -> None:
    from app.main import create_app

    bare = TestClient(create_app(None))
    assert bare.get("/").status_code == 404
    assert bare.get("/api/health").json() == {"ok": True}
