from functools import lru_cache
from pathlib import Path as FilePath
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

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

WEB_DIST = FilePath(__file__).resolve().parents[2] / "web" / "dist"

router = APIRouter()


@lru_cache(maxsize=1)
def get_repository() -> Repository:
    """The data is committed and read-only, so it loads once per process. Tests override this."""
    return Repository.load()


Repo = Annotated[Repository, Depends(get_repository)]


@router.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@router.post("/quote", response_model=list[Path])
def quote(req: QuoteRequest, repo: Repo) -> list[Path]:
    """Every path for the request, from the real engine and the committed data (task 2.7)."""
    units = [req.current, *req.items] if req.current else req.items
    for category in {u.category for u in units}:
        try:
            repo.profile(category)
        except KeyError:
            raise HTTPException(status_code=422, detail=f"No data for the category {category!r} yet") from None
    return build_quote(req, repo)


@router.post("/item", response_model=Item)
def item(item: Item) -> Item:
    """Fills the manufacture year from the serial when the user gave none; a typed year always wins."""
    if item.mfg_year is None and item.serial:
        found = decode(item.brand, item.serial)
        if found.mfg_year is not None:
            return item.model_copy(update={"mfg_year": found.mfg_year, "year_confidence": found.year_confidence})
    return item


@router.get("/categories")
def categories() -> list[str]:
    return ["refrigerator"]


@router.get("/sources", response_model=list[Source])
def sources(repo: Repo) -> list[Source]:
    return repo.sources()


# Still stubs, replaced by their wiring tasks: /scan in 3.9; /shop/* in 4.3.


@router.post("/scan", response_model=ScanResult)
def scan(kind: Annotated[ScanKind, Form()], image: Annotated[UploadFile, File()]) -> ScanResult:
    return ScanResult(kind=kind, valid=False, errors=["not implemented"])


@router.post("/shop/parse", response_model=ShopFilters)
def shop_parse(req: ShopParseRequest) -> ShopFilters:
    return ShopFilters()


@router.post("/shop/rank", response_model=list[RankedOffer])
def shop_rank(req: ShopRankRequest) -> list[RankedOffer]:
    return []


def _serve_web(app: FastAPI, dist: FilePath) -> None:
    """The built web app at `/`, with `index.html` for client-side routes; never a file outside `dist`."""
    root = dist.resolve()
    index = root / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def web(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        target = (root / path).resolve()
        if path and target.is_file() and target.is_relative_to(root):
            return FileResponse(target)
        return FileResponse(index)


def create_app(web_dist: FilePath | None = WEB_DIST) -> FastAPI:
    """One address (task 2.7.1): every route unprefixed (tests, the Vite dev proxy) and under `/api`
    (the built app), plus the built web app itself when `web_dist` holds one."""
    app = FastAPI(title="RealityReceipt API")
    app.include_router(router)
    app.include_router(router, prefix="/api", include_in_schema=False)
    if web_dist is not None and (web_dist / "index.html").is_file():
        _serve_web(app, web_dist)
    return app


app = create_app()
