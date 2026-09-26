from pathlib import Path as FilePath
from typing import Annotated

from fastapi import FastAPI, File, Form, UploadFile
from pydantic import TypeAdapter

from app.models import (
    Item,
    Path,
    QuoteRequest,
    RankedOffer,
    ScanKind,
    ScanResult,
    ShopFilters,
    ShopParseRequest,
    ShopRankRequest,
    Source,
)

FIXTURE = FilePath(__file__).resolve().parents[2] / "contracts" / "receipt_fridge.json"

app = FastAPI(title="RealityReceipt API")


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


# Stubs from task 1.3 so every track can call the real routes now. Each is
# replaced by its wiring task: /quote, /sources, /item in 2.7; /scan in 3.9;
# /shop/* in 4.3.


@app.post("/quote", response_model=list[Path])
def quote(req: QuoteRequest) -> list[Path]:
    """Stub: the sample receipt, every path flagged "fixture"."""
    return TypeAdapter(list[Path]).validate_json(FIXTURE.read_text())


@app.post("/scan", response_model=ScanResult)
def scan(kind: Annotated[ScanKind, Form()], image: Annotated[UploadFile, File()]) -> ScanResult:
    return ScanResult(kind=kind, valid=False, errors=["not implemented"])


@app.post("/item", response_model=Item)
def item(item: Item) -> Item:
    return item


@app.post("/shop/parse", response_model=ShopFilters)
def shop_parse(req: ShopParseRequest) -> ShopFilters:
    return ShopFilters()


@app.post("/shop/rank", response_model=list[RankedOffer])
def shop_rank(req: ShopRankRequest) -> list[RankedOffer]:
    return []


@app.get("/categories")
def categories() -> list[str]:
    return ["refrigerator"]


@app.get("/sources", response_model=list[Source])
def sources() -> list[Source]:
    return []
