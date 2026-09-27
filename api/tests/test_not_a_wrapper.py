"""Not a wrapper (PLAN.md task 3.8): a scanned demo card and the same card typed by hand give the
same receipt. Grok only reads the card; every number on the receipt comes from `quote`.

`fixtures/scan/<card>.json` is the real Grok reply to each card in `demo/cards/`, recorded once
(grok-4.20-0309-non-reasoning, 2026-09-26) and replayed here through a fake client, so the test
never calls the network. `fixtures/typed/<card>.json` is the card's typed equivalent from
`demo/cards/cards.json`.
"""

import json
from pathlib import Path as FilePath

import pytest

from app.engine.quote import quote
from app.grok.scan import scan
from app.models import Item, Lease, Offer, QuoteRequest, ScanResult
from app.repository import Repository

ROOT = FilePath(__file__).resolve().parents[2]
CARDS_DIR = ROOT / "demo" / "cards"
FIXTURES = FilePath(__file__).resolve().parent / "fixtures"
CARDS = json.loads((CARDS_DIR / "cards.json").read_text())["cards"]

# A label prints no price, so both sides list the unit at the same price (as in test_slice.py).
LABEL_CARD_PRICE = 250.0

# One printed value per kind that the receipt depends on, for the control below.
CHANGED = {"label": {"model": "XX0000"}, "lease": {"cash_price": 1000.0}, "listing": {"price": 200}}


class RecordedGrok:
    """Replays a recorded Grok reply; stands in for `GrokClient`."""

    def __init__(self, reply: dict) -> None:
        self.reply = reply

    def chat_json(self, system: str, user: str, image_jpeg: bytes | None = None, schema: dict | None = None) -> dict:
        return self.reply


@pytest.fixture(scope="module")
def repo() -> Repository:
    return Repository.load()


def _stem(card: dict) -> str:
    return FilePath(card["file"]).stem


def _scan(card: dict, reply: dict) -> ScanResult:
    return scan(card["kind"], (CARDS_DIR / card["file"]).read_bytes(), RecordedGrok(reply))


def _receipt(item: Item, offer: Offer | None, lease: Lease | None, repo: Repository) -> list[dict]:
    if offer is None:
        offer = Offer(item_id=item.id, price=LABEL_CARD_PRICE, seller_type="private",
                      source="user_listing", source_id="user_listing")
    paths = quote(QuoteRequest(items=[item], offers=[offer], lease=lease), repo)
    return [p.model_dump(mode="json") for p in paths]


def _scanned_receipt(card: dict, reply: dict, repo: Repository) -> list[dict]:
    result = _scan(card, reply)
    assert result.valid, result.errors
    assert result.item is not None
    return _receipt(result.item, result.offer, result.lease, repo)


@pytest.mark.parametrize("card", CARDS, ids=_stem)
def test_scanned_card_and_typed_card_give_the_same_receipt(card: dict, repo: Repository) -> None:
    reply = json.loads((FIXTURES / "scan" / f"{_stem(card)}.json").read_text())
    typed = json.loads((FIXTURES / "typed" / f"{_stem(card)}.json").read_text())
    assert typed == card["typed"], "typed fixture drifted from demo/cards/cards.json"

    item = Item.model_validate(typed["item"])
    offer = Offer.model_validate(typed["offer"]) if "offer" in typed else None
    lease = Lease.model_validate(typed["lease"]) if "lease" in typed else None
    typed_receipt = _receipt(item, offer, lease, repo)

    assert typed_receipt
    assert json.dumps(_scanned_receipt(card, reply, repo), sort_keys=True) == json.dumps(typed_receipt, sort_keys=True)


def test_the_comparison_can_fail(repo: Repository) -> None:
    # Changing one printed value in the recorded reply changes the receipt, so equality above is
    # not true of any two receipts.
    for card in CARDS:
        reply = json.loads((FIXTURES / "scan" / f"{_stem(card)}.json").read_text())
        changed = {**reply, **CHANGED[card["kind"]]}
        assert _scanned_receipt(card, changed, repo) != _scanned_receipt(card, reply, repo), card["file"]
