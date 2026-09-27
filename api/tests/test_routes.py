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


class FakeGrok:
    """Stands in for GrokClient: returns one canned reply and records each call."""

    def __init__(self, reply: dict) -> None:
        self.reply = reply
        self.calls = 0

    def chat_json(self, system: str, user: str, image_jpeg: bytes | None = None, schema: dict | None = None) -> dict:
        self.calls += 1
        return self.reply


LABEL_REPLY = {"brand": "Whirlpool", "model": "ET1FHTXMQ", "serial": "MK1402320", "mfg_year": None,
               "product_class": "3", "volume_cuft": 20.9, "label_kwh_per_year": 505}
PHOTO = {"image": ("label.jpg", b"\xff\xd8photo", "image/jpeg")}


@pytest.fixture
def grok(client: TestClient):
    """Injects a fake Grok client into /scan; the test sets its reply."""
    from app.main import get_grok_client

    fake = FakeGrok(LABEL_REPLY)
    app.dependency_overrides[get_grok_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_grok_client, None)


def _scan(client: TestClient, kind: str, files: dict = PHOTO, path: str = "/scan") -> ScanResult:
    response = client.post(path, data={"kind": kind}, files=files)
    assert response.status_code == 200
    return ScanResult.model_validate(response.json())


def test_scan_returns_the_item_with_its_year_from_the_serial(client: TestClient, grok: FakeGrok) -> None:
    result = _scan(client, "label")
    assert result.valid and grok.calls == 1
    assert result.item is not None and result.item.model == "ET1FHTXMQ"
    assert (result.item.mfg_year, result.item.year_confidence) == (2000, "high")  # letter K (test_serial.py)
    assert result.item.attributes["label_kwh_per_year"] == 505
    assert result.fields["serial"] == "MK1402320"


def test_scan_keeps_a_printed_year(client: TestClient, grok: FakeGrok) -> None:
    grok.reply = {**LABEL_REPLY, "mfg_year": 2003}
    result = _scan(client, "label")
    assert (result.item.mfg_year, result.item.year_confidence) == (2003, "none")


def test_scan_works_under_api_too(client: TestClient, grok: FakeGrok) -> None:
    assert _scan(client, "label", path="/api/scan").valid


def test_invalid_scan_returns_what_was_read_and_no_objects(client: TestClient, grok: FakeGrok) -> None:
    grok.reply = {**LABEL_REPLY, "model": None}
    result = _scan(client, "label")
    assert not result.valid and "model: missing" in result.errors
    assert result.item is None and result.fields["brand"] == "Whirlpool"


def test_scan_lease_returns_the_lease_offer_and_leased_unit(client: TestClient, grok: FakeGrok) -> None:
    grok.reply = {"brand": "Frigidaire", "model": "FRTE1936AV", "weekly_payment": 33.48, "term_weeks": 52,
                  "cash_price": 1196.99, "fees": 0, "early_purchase_rule": "none", "early_purchase_percent": None,
                  "early_purchase_text": None, "missed_payment_rule": None, "payment_today": 0.01,
                  "total_of_payments": 1739.88}
    result = _scan(client, "lease")
    assert result.valid and result.lease is not None and result.lease.total_of_payments == 1739.88
    assert result.offer is not None and result.offer.item_id == result.item.id


def test_scan_without_a_key_sends_the_user_to_the_form(client: TestClient) -> None:
    from app.main import get_grok_client

    app.dependency_overrides[get_grok_client] = lambda: None
    try:
        result = _scan(client, "label")
    finally:
        app.dependency_overrides.pop(get_grok_client, None)
    assert not result.valid and "not set up" in result.errors[0]


def test_missing_key_gives_no_client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from app.grok import client as grok_client
    from app.main import get_grok_client

    monkeypatch.setattr(grok_client, "_ENV_PATH", tmp_path / "no.env")
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_MODEL", raising=False)
    assert get_grok_client() is None


def test_scan_refuses_an_oversized_photo_before_calling_grok(client: TestClient, grok: FakeGrok) -> None:
    from app.main import MAX_SCAN_BYTES

    big = {"image": ("big.jpg", b"\xff" * (MAX_SCAN_BYTES + 1), "image/jpeg")}
    result = _scan(client, "label", files=big)
    assert not result.valid and "15 MB" in result.errors[0] and grok.calls == 0


def test_scan_refuses_an_empty_upload(client: TestClient, grok: FakeGrok) -> None:
    result = _scan(client, "label", files={"image": ("empty.jpg", b"", "image/jpeg")})
    assert not result.valid and grok.calls == 0


def test_scan_rejects_an_unknown_kind(client: TestClient, grok: FakeGrok) -> None:
    assert client.post("/scan", data={"kind": "receipt"}, files=PHOTO).status_code == 422


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
