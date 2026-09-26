from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile

from app.engine.quote import quote as build_quote
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
from app.repository import Repository
from app.serial.decode import decode

app = FastAPI(title="RealityReceipt API")


@lru_cache(maxsize=1)
def get_repository() -> Repository:
    """The data is committed and read-only, so it loads once per process. Tests override this."""
    return Repository.load()


Repo = Annotated[Repository, Depends(get_repository)]


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/quote", response_model=list[Path])
def quote(req: QuoteRequest, repo: Repo) -> list[Path]:
    """Every path for the request, from the real engine and the committed data (task 2.7)."""
    units = [req.current, *req.items] if req.current else req.items
    for category in {u.category for u in units}:
        try:
            repo.profile(category)
        except KeyError:
            raise HTTPException(status_code=422, detail=f"No data for the category {category!r} yet") from None
    return build_quote(req, repo)


@app.post("/item", response_model=Item)
def item(item: Item) -> Item:
    """Fills the manufacture year from the serial when the user gave none; a typed year always wins."""
    if item.mfg_year is None and item.serial:
        found = decode(item.brand, item.serial)
        if found.mfg_year is not None:
            return item.model_copy(update={"mfg_year": found.mfg_year, "year_confidence": found.year_confidence})
    return item


@app.get("/categories")
def categories() -> list[str]:
    return ["refrigerator"]


@app.get("/sources", response_model=list[Source])
def sources(repo: Repo) -> list[Source]:
    return repo.sources()


# Still stubs, replaced by their wiring tasks: /scan in 3.9; /shop/* in 4.3.


@app.post("/scan", response_model=ScanResult)
def scan(kind: Annotated[ScanKind, Form()], image: Annotated[UploadFile, File()]) -> ScanResult:
    return ScanResult(kind=kind, valid=False, errors=["not implemented"])


@app.post("/shop/parse", response_model=ShopFilters)
def shop_parse(req: ShopParseRequest) -> ShopFilters:
    return ShopFilters()


@app.post("/shop/rank", response_model=list[RankedOffer])
def shop_rank(req: ShopRankRequest) -> list[RankedOffer]:
    return []
