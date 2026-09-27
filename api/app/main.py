from functools import lru_cache
from pathlib import Path as FilePath
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.engine.quote import quote as build_quote
from app.engine.rank import rank as rank_offers
from app.grok.client import GrokClient
from app.grok.scan import scan as read_image
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
MAX_SCAN_BYTES = 15 * 1024 * 1024  # a full-size phone photo is 3 to 8 MB
CATEGORIES = ["refrigerator"]

router = APIRouter()


@lru_cache(maxsize=1)
def get_repository() -> Repository:
    """The data is committed and read-only, so it loads once per process. Tests override this."""
    return Repository.load()


Repo = Annotated[Repository, Depends(get_repository)]


def get_grok_client() -> GrokClient | None:
    """`None` when `XAI_API_KEY` or `XAI_MODEL` is not set, so /scan sends the user to the form
    instead of failing. Tests override this with a fake client."""
    try:
        return GrokClient()
    except RuntimeError:
        return None


Grok = Annotated[GrokClient | None, Depends(get_grok_client)]


def _with_serial_year(item: Item) -> Item:
    """Fills the manufacture year from the serial when none was given; a typed or printed year always wins."""
    if item.mfg_year is None and item.serial:
        found = decode(item.brand, item.serial)
        if found.mfg_year is not None:
            return item.model_copy(update={"mfg_year": found.mfg_year, "year_confidence": found.year_confidence})
    return item


def _require_profiles(repo: Repository, categories: set[str]) -> None:
    """A clear 422 for a category with no data profile, instead of an error deep in the engine."""
    for category in sorted(categories):
        try:
            repo.profile(category)
        except KeyError:
            raise HTTPException(status_code=422, detail=f"No data for the category {category!r} yet") from None


@router.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@router.post("/quote", response_model=list[Path])
def quote(req: QuoteRequest, repo: Repo) -> list[Path]:
    """Every path for the request, from the real engine and the committed data (task 2.7)."""
    units = [req.current, *req.items] if req.current else req.items
    _require_profiles(repo, {u.category for u in units})
    return build_quote(req, repo)


@router.post("/item", response_model=Item)
def item(item: Item) -> Item:
    return _with_serial_year(item)


@router.get("/categories")
def categories() -> list[str]:
    return CATEGORIES


@router.get("/sources", response_model=list[Source])
def sources(repo: Repo) -> list[Source]:
    return repo.sources()


@router.post("/scan", response_model=ScanResult)
def scan(kind: Annotated[ScanKind, Form()], image: Annotated[UploadFile, File()], grok: Grok) -> ScanResult:
    """Reads the photo with Grok (task 3.7). Every failure is `valid=False` with a plain error, so the
    user always lands on the correction form; a valid item also gets its year from the serial."""
    data = image.file.read(MAX_SCAN_BYTES + 1)
    if len(data) > MAX_SCAN_BYTES:
        return ScanResult(kind=kind, valid=False, errors=["The photo is larger than 15 MB. Take a smaller one or enter the details by hand."])
    if not data:
        return ScanResult(kind=kind, valid=False, errors=["No photo arrived. Try again or enter the details by hand."])
    if grok is None:
        return ScanResult(kind=kind, valid=False, errors=["Scanning is not set up on this server. Enter the details by hand."])
    result = read_image(kind, data, grok)
    if result.valid and result.item is not None:
        return result.model_copy(update={"item": _with_serial_year(result.item)})
    return result


# Still a stub: /shop/parse is wired to `parse_request` once task 4.1 lands (task 4.3).


@router.post("/shop/parse", response_model=ShopFilters)
def shop_parse(req: ShopParseRequest) -> ShopFilters:
    return ShopFilters()


@router.post("/shop/rank", response_model=list[RankedOffer])
def shop_rank(req: ShopRankRequest, repo: Repo) -> list[RankedOffer]:
    """The retailer cache's new offers plus the request's own listings, ranked by cost per year of
    use (task 4.3). The request may carry only the user's listings: a new offer's price and source
    come from the cache, never from the client."""
    for offer in req.offers:
        if (offer.source, offer.source_id) != ("user_listing", "user_listing"):
            raise HTTPException(
                status_code=422,
                detail="Only your own listings can be sent (source and source_id 'user_listing'); new offers come from the retailer cache",
            )
    wanted = [req.filters.category] if req.filters.category else CATEGORIES
    _require_profiles(repo, {*wanted, *(i.category for i in req.items)})

    cached = [offer for category in wanted for offer in repo.new_offers(category)]
    cached_items = [item for offer in cached if (item := repo.item(offer.item_id)) is not None]
    # `rank` finds each offer's item by id, so a listing may not reuse a cached item's id.
    taken = sorted({i.id for i in cached_items} & {i.id for i in req.items})
    if taken:
        raise HTTPException(status_code=422, detail=f"The item id {taken[0]!r} is used by a cached offer; give the listing another id")
    return rank_offers(req.filters, [*cached, *req.offers], [*cached_items, *req.items], repo)


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
