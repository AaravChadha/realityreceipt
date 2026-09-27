# RealityReceipt
### HackGT 13 | code freeze Sun 2026-09-27 02:00 EDT | Devpost deadline Sun 08:00 EDT

> **Purpose of this document.** The living plan: phases, tasks, and the command that proves each task is done. `BRIEF.md` is the frozen problem statement. The build spec (`docs/RealityReceipt_Build_Spec.pdf`) is the source of truth for product rules. How sessions branch, land and ask for changes is in `AGENTS.md` "Team workflow".
>
> **Cross-cutting constraints (every phase, every session, every tool):**
> - Only extraction uses AI. No number on the receipt is produced or changed by a model. Everything after extraction is deterministic and has a test.
> - "Not a wrapper": typing brand, model and serial gives the identical receipt to scanning the label.
> - Every cost line carries exactly one source label (`rated`, `published`, `user_entered`, `not_estimated`) and a formula. `not_estimated` means blank, never guessed.
> - Estimates are ranges, never single points. Repairs are labeled ranges with no failure probabilities.
> - Nothing is fetched live during the demo. No scraping. No sign-up, no income or personal questions. Checkout links out; never fake a payment.
> - Wording in the UI and on stage (spec §6): "effective annual cost", never "APR"; never say a user qualifies for a loan or assistance; no absolute claims; no em dashes in user-facing copy.
> - Secrets live only in `api/.env`, which is gitignored. `api/.env.example` holds the variable names with empty values.

**Gate verdict (2026-09-26):** Challenged in writing: the spec's single-sequence build order, the one-machine merge lane, the undefined formulas, the "only the first step uses AI" wording, the OCR fallback and the optional stack pieces, and the unnamed first category. Changed: scope stays at spec items 1 to 8 (item 9 conditional) because four people each run several sessions, with Sat 12:00 EDT as an integration checkpoint; integration is PR + squash on GitHub instead of the acstack hackathon lane; the formulas are pinned below; the OCR fallback, PWA, live camera viewfinder and SQLite are cut; refrigerators are the first category. Accepted as-is: the spec's architecture (AI only at the edges, a deterministic engine, a category as data), the data model and API with the deltas in task 1.1, the sponsor entries, and every spec §6 stage rule.

**Status (2026-09-26 14:52 EDT):** build had not started; 12 hours passed between the gate and this plan. The team works untimed, as fast as possible, in the priority order below. The Sat 12:00 checkpoint becomes the Phase 2 exit criterion. Fixed times remain the code freeze (Sun 02:00) and the Devpost deadline (Sun 08:00).

## Problem

The option that looks cheapest today often costs the most over time: an old used unit that is expensive to run, a rent-to-own lease that totals several times the cash price, a purchase on high-interest credit. Stores sort by sticker price, which hides running costs, interest, lease terms and lifespan, and lower-income households are the most exposed.

## Solution

1. Scan or type an appliance's label, a price tag, a lease or a used listing. No sign-up, no personal questions.
2. See every way to get the item side by side: repair, used, refurbished, new (cash, card, buy now pay later, credit union PAL), rent-to-own.
3. Each path shows three numbers, pay today, total over 3 years and cost per year of use, sorted by true cost.
4. Tap any number for its source and formula. A carbon line sits next to the cost line.
5. Ask in plain words ("about $300, small space, need it this week") and get new and used offers ranked by cost per year.

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| API | FastAPI + Pydantic v2, Python 3.12 in CI | Strict schemas are the contract; `TestClient` gives acceptance checks without a running server |
| Data | Committed JSON and CSV in `api/app/data/`, loaded into memory by `api/app/repository.py` | No database to break; the repository interface still allows a TigerData swap |
| AI | Grok vision and text over HTTPS with `httpx` (~~Grok Voice~~, dropped 2026-09-26) | SpaceXAI challenge; no vendor SDK to install |
| Web | React + Vite + TypeScript, Tailwind, Framer Motion | Spec stack, minus the PWA |
| Tests | pytest (`api/tests`, `analysis`), vitest + Testing Library (`web/src`) | Every task's acceptance is a test run |
| Phone | `cloudflared` quick tunnel to the Vite dev server | Phone cameras need HTTPS |
| Evidence | pandas + matplotlib in `analysis/recs/` | RECS 2020 weighted analysis |

## Decisions (from the gate)

> **Decision (2026-09-26):** Integration is GitHub `main` via small PRs, squash-merged when CI passes. Each person merges their own sessions' PRs; no review, no single integrator. Tradeoff: a few minutes of CI per landing and no human review; mitigated by per-session file ownership and by running the task's acceptance before opening the PR. Revisit when CI takes over 10 minutes.

> **Decision (2026-09-26):** No `acstack:hackathon-lane` block in AGENTS.md. The lane's own scope is one machine, one clone; we are four machines. Tradeoff: `/do` stops at a local commit and the person pushes and opens the PR; mitigated by the push-and-PR steps in AGENTS.md "Team workflow". Revisit never during this event.

> **Decision (2026-09-26):** The first category is refrigerators. They run all the time, so the rated annual kWh is the usage (no usage-hours assumption), and they are electric only (no gas vs electric split). Tradeoff: the ~2014 test procedure change (spec §7) makes old and new ratings not directly comparable; mitigated by a receipt flag on any comparison across it. Revisit when items 1 to 8 are solid (spec item 9).

> **Decision (2026-09-26):** Cut the PaddleOCR + OpenCV fallback, the PWA, the live getUserMedia viewfinder and SQLite. The scan fallback is the manual correction form, pre-filled with whatever parsed, plus an upload button. The camera path is `<input type="file" accept="image/*" capture="environment">`. Tradeoff: no offline install and no live viewfinder; mitigated by full-resolution stills and a TigerData-ready repository interface. Revisit if a track finishes early.

> **Decision (2026-09-26): formulas pinned.** Every one is shown when its number is tapped.
> - **Cost per year of use:** low = purchase total low / life high + annual cost low; high = purchase total high / life low + annual cost high. "Purchase total" includes financing; "annual cost" is running plus upkeep per year. `None` (shown "not estimated") when no published lifespan exists, and the high end is `None` when remaining life low is 0 (flag `past_typical_life`).
> - **Credit card:** Federal Reserve G.19 "accounts assessed interest" rate, paid off in 12 equal monthly payments starting month 1. Pay today = 0.
> - **PAL:** NCUA PALs II caps as the ceiling: 28% interest, 12 months, $20 application fee, only for prices up to $2,000. Low = high = cost at the caps, labeled "up to". Never implies the user can get one.
> - **Buy now pay later:** `not_estimated`, unless one provider's published terms are cached with URL and retrieval date.
> - **Replacement purchase:** the cheapest cached new offer in the category, added to `monthly_high` at month `ceil(life_low * 12)` and to `monthly_low` at month `ceil(life_high * 12)`, each only when that month is under 36. → **Verdict (2026-09-26):** no replacement is priced for a unit at or past its typical life, or with no year made; its timing is `not_estimated` (decision 8, task 3.3.2).
> - **Monthly cash flow:** `monthly_low[36]` and `monthly_high[36]` (index 0 = today), replacing the spec's single `monthly[36]`. Total over 3 years = sum of each array.
> - **Old unit energy:** its sourced rated figure. Extra draw from aging is `not_estimated`.
> - ~~**Rent-to-own effective annual cost** = ((total of payments - cash price) / cash price) / (term_weeks / 52). Never labeled APR.~~ → **Verdict (2026-09-26):** the same formula, never labeled APR, shown only on the keep-paying path; the buyout path states its total minus the cash price instead. Annualizing a buyout after a few weeks gave -32% and 706% in review.
> - ~~**Sort order:** paths by `total_3yr_high`, ties by `pay_today`. Shop offers by `cost_per_year_high`, `None` last.~~ → **Verdict (2026-09-26):** complete paths first, by `total_3yr_high` then `pay_today`; paths flagged `costs_not_estimated` after them in the same order. Shop: complete offers first, then flagged, each by `cost_per_year_high` with `None` last. A blank cost counted as $0 made incomplete paths look cheapest.

> **Decision (2026-09-26):** ~~Contracts frozen by 03:30 EDT.~~ → **Verdict (2026-09-26):** ~~frozen by 04:30 EDT~~ → **Verdict (2026-09-26 14:52):** frozen when the Phase 1 PR merges; no clock time. The team works untimed.

> **Decision (2026-09-26):** An old unit with no rating in ENERGY STAR or the DOE CCD falls back to the DOE standard maximum for its manufacture year, product class and adjusted volume (spec §3), labeled `published` and "up to, when new". Tradeoff: an upper bound when new, not what an aged unit draws; mitigated by the separate `not_estimated` aging line. Revisit if a sourced degradation figure turns up.

> **Decision (2026-09-26):** "Not a wrapper" parity covers brand, model, serial, condition, price, and the optional `product_class` and `volume_cuft`. ~~Energy always comes from lookup by model (or the standard fallback), never from a kWh figure printed on a scanned label, so typed and scanned entries resolve identically. Tradeoff: a label's printed kWh is not used directly; mitigated by the model lookup returning the same rated figure. Revisit never during this event.~~ → **Verdict (2026-09-26):** a label's printed kWh may be used, as `attributes["label_kwh_per_year"]` (`user_entered`, source `user`), when no rated figure is found. Typed and scanned entry fill the same field, so parity holds. Old models are missing from ENERGY STAR, so without it the old unit's electricity was always blank.

> **Decision (2026-09-26 18:05): fixes from the review** (five reviewers plus a Codex review of main at 08d78ac). Each fix is a follow-up task next to the task it corrects.
> 1. **Old-unit energy:** after ENERGY STAR, look the model up in DOE's historical refrigerator rating database (1949 to 2021, `rated`); then the label's printed kWh (`user_entered`); then the standard ceiling (adjusted volume only); else `not_estimated`. The DOE data also gives a manufacture year when none is entered. Tasks 2.2.2, 3.3.3.
> 2. **"Year made"** is an optional field on both entry sections; the scan reads it when printed. Task 2.8.1.
> 3. **Incomplete paths:** a path missing its electricity, financing or replacement-timing figure is flagged `costs_not_estimated`, says so on screen, and sorts after complete paths. Tasks 3.3.1, 4.2.1, 2.9.1.
> 4. **Effective annual cost** only on the keep-paying path (see the Verdict above). Task 3.2.1.
> 5. **Shop filters** keep offers whose delivery time or width is unknown, flagged `delivery_unknown` or `width_unknown`. Task 4.2.1.
> 6. **Demo address:** the API serves the built web app at one address, deployed behind the team's free .tech domain; the quick tunnel stays as backup; a backup video is recorded. Tasks 2.7.1, 2.11.1.
> 7. **3-year window:** only payments falling in months 0 to 35 count; later lease or BNPL payments are left out, not moved into month 35 (the full total stays in the line's formula). Supersedes 3.2's `min(35, ...)` bucketing. Tasks 3.1.1, 3.2.1.
> 8. **Past typical life:** flag `past_typical_life`, insert no replacement, mark replacement timing `not_estimated`. After a replacement inside the window, running cost switches to the replacement unit. Task 3.3.2.
> 9. **Rated means the brand matches;** several matching rows with different kWh return `None` with the rows as candidates. Task 2.2.1. **Refined (2026-09-26):** ENERGY STAR certifies many models twice, without and with an automatic icemaker (class `3` and `3I`, about 84 kWh apart). The CSV keeps each row's CFR class, and an item's `product_class` picks the rows of that class. With no class given, the two still disagree and return `None`. Task 2.2.3. **Refined (2026-09-26):** an EnergyGuide may print the maker ("Electrolux Home Products Inc." on the Frigidaire demo label), which counts as Electrolux. Electrolux and Frigidaire, one maker, fall back to each other only when the brand as given has no matching row. They are never merged, because DOE lists some models under both names at different kWh. A retailer's house brand (Kenmore) is never an alias. Task 2.2.4. **Refined (2026-09-26):** DOE's historical file has no class column and lists many models twice, exactly 84 kWh apart. Every icemaker class's DOE standard (10 CFR 430.32(a)) has its base class's slope and an intercept 84 kWh higher, so two DOE figures exactly that adder apart are read as without and with an icemaker, and the item's class picks one (lower for `3`, `4`, `5`, `3-BI`, ...; higher for `3I`, `4I`, `5I`, `3I-BI`, ...). This is an inference from the standard, limited to an exact pair and a given class; any other disagreement, or no class, still returns `None`. ENERGY STAR rows are unaffected. Task 2.2.6.
> Tradeoff: about fifteen small tasks across rows tonight; mitigated by each being one row's files with its own acceptance.

> **Decision (2026-09-26 18:45):** ~~Grok Voice read-aloud in English and Spanish (spec §5 item 8; tasks 4.5, 4.6)~~ → **Verdict (2026-09-26):** dropped. Reading a table of numbers aloud adds little a user would actually use, and judges would see it was there for the prize. The SpaceXAI entry rests on the Grok scan and the shopping request. Future extension: a Spanish version of the screen from written templates, not voice.

> **Decision (2026-09-26 21:10): fixes from the second Codex review** (main at f435b79). (1) Cost per year uses the full acquisition cost: a lease or BNPL total beyond 36 months still counts, even though the 3-year total leaves those payments out. Tasks 3.2.3, 3.3.4. (2) Every range is built from the min and max of its scenarios, so low never exceeds high; an earlier, more efficient replacement can be the cheaper case. Task 3.3.4. (3) A manufacture year inferred from DOE listing years is a range with a visible flag, never written in as if typed. Tasks 2.2.5, 3.3.5, 2.9.2. (4) The scan picker drops "Price tag" tonight, because the quote prices new paths from the cached offers, not from a scanned tag. Task 3.10's status. (5) docs/pitch.md follows the rewritten demo script. Task 4.8.2.

> **Decision (2026-09-26 21:45): from the demo check on main (session 4, 54a9954).** (1) The keep-paying path states its cost over the cash price ($542.89 on the demo lease, the cost of lease services), as the demo script says; 3.2.1 had put that comparison on the buyout path only. Task 3.2.4. (2) With no early purchase terms there is no buyout card: it repeated the keep-paying numbers, which asserts a buyout price nobody knows. Task 3.3.6. (3) The script follows the pinned sort (complete paths by 3-year total), so the lease is the last path, the most expensive over 3 years; Scenarios 1 to 4 now say what main shows.

## Index of phases

Phases are milestones, not time slots. A task in a later phase starts as soon as its inputs are on `origin/main`; Track D's scan and RECS work can start right after Phase 1.

| Phase | Goal | Exit criterion |
|---|---|---|
| [0 Setup](#phase-0) | Scaffold, CI and hook on GitHub `main`; every clone passes | `gh run list --workflow ci.yml --branch main --limit 1 --json conclusion -q '.[0].conclusion'` prints `success` |
| [1 Contracts](#phase-1) | Models, route stubs and a sample receipt that every track builds against | `api/.venv/bin/python -m pytest api/tests -q` and `npm --prefix web test` pass |
| [2 Vertical slice](#phase-2) | Typed fridge model gives a sourced receipt on a real phone | `api/.venv/bin/python -m pytest api/tests/test_slice.py -q` passes, plus the phone check |
| [3 Full receipt and scan](#phase-3) | All paths, the lease, serial decode, Grok scan equal to typed entry, RECS finding | `api/.venv/bin/python -m pytest api/tests analysis -q` passes with `test_not_a_wrapper.py` included |
| [4 Shop, submit](#phase-4) | Grok shopping request, demo hardened, frozen at 02:00, submitted | CI green on the `freeze` tag, submission checklist ticked |

## File ownership

One row = one session's file set. A person with fewer sessions runs several rows in order. A session edits only its row's files; for a change in another row, ask that row's owner. Tests live next to the owner: a row owns the test files named in its tasks.

| Row | Owner | Edits only | Reads from |
|---|---|---|---|
| 0 Operator | repo owner | `.gitignore`, `.github/`, `pytest.ini`, `api/requirements.txt`, `api/app/__init__.py`, `api/.env.example`, `web/package.json`, `web/package-lock.json`, `web/vite.config.ts`, `web/tsconfig*.json`, `web/index.html`, `docs/`, `README.md`, `AGENTS.md`, `.claude/acstack.md`, `.cursor/` | — |
| A1 Contracts and routes | Track A | `api/app/models.py`, `api/app/main.py`, `contracts/`, `web/src/contracts.ts`, `web/src/contracts.test.ts`, `api/tests/test_contracts.py`, `api/tests/test_health.py`, `api/tests/test_routes.py`, `api/tests/test_journey.py` | every module's functions below |
| A2 Quote and lifecycle | Track A | `api/app/engine/__init__.py`, `api/app/engine/quote.py`, `api/app/engine/lifecycle.py`, `api/app/engine/rank.py`, `api/tests/test_lifecycle.py`, `api/tests/test_slice.py`, `api/tests/test_quote_all_paths.py`, `api/tests/test_rank.py`, `api/tests/test_copy.py`, `api/tests/test_quote_unit.py` | A3 to A5, B1 |
| A3 Financing | Track A | `api/app/engine/financing.py`, `api/tests/test_financing.py` | A1 models |
| A4 Rent-to-own | Track A | `api/app/engine/lease.py`, `api/tests/test_lease.py` | A1 models |
| A5 Running cost and carbon | Track A | `api/app/engine/running.py`, `api/tests/test_running.py` | A1 models |
| B1 Sources and repository | Track B | `api/app/repository.py`, `api/app/data/sources.json`, `api/app/data/rates.json`, `api/app/data/bnpl.json`, `api/tests/test_repository.py` | A1 models |
| B2 Refrigerator profile | Track B | `api/app/data/refrigerator.json`, `api/app/data/energystar_refrigerators.csv`, `api/app/data/doe_standards_refrigerators.json`, `api/app/data/doe_wap_refrigerators.csv.gz`, `api/tests/test_profile.py` | B1 |
| B3 Offers and demo materials | Track B | `api/app/data/retailer_cache.json`, `demo/`, `api/tests/test_retailer_cache.py`, `api/tests/test_demo_cards.py` | B1 |
| B4 Serial decode | Track B | `api/app/serial/`, `api/tests/test_serial.py` | A1 models |
| C1 Shell, entry and scan UI | Track C | `web/src/App.tsx`, `web/src/main.tsx`, `web/src/api.ts`, `web/src/pages/Entry.tsx`, `web/src/pages/Entry.test.tsx`, `web/src/copy.test.ts`, `web/src/index.css` | A1 contracts |
| C2 Receipt | Track C | `web/src/components/Receipt.tsx`, `web/src/components/PathCard.tsx`, `web/src/format.ts`, `web/src/components/Receipt.test.tsx`, `web/src/format.test.ts` | A1 contracts |
| C3 Source sheet | Track C | `web/src/components/SourceSheet.tsx`, `web/src/components/SourceSheet.test.tsx` | C2's `format.ts` |
| C4 Shop | Track C | `web/src/pages/Shop.tsx`, `web/src/pages/Shop.test.tsx` | C2, A1 contracts |
| D1 Grok scan | Track D, **in Cursor** | `api/app/grok/__init__.py`, `api/app/grok/client.py`, `api/app/grok/scan.py`, `api/tests/test_scan.py`, `api/tests/test_not_a_wrapper.py`, `api/tests/fixtures/` | A1 models, A2 `quote` |
| D2 Grok request parsing | Track D, **in Cursor** | `api/app/grok/parse.py`, `api/tests/test_parse.py` | D1's `client.py` |
| ~~D3 Voice~~ (dropped 2026-09-26) | Track D, **in Cursor** | `api/app/voice/`, `api/tests/test_voice.py` | A1 models |
| D4 RECS finding | Track D | `analysis/` | — |

`PLAN.md` is shared: each task ticks only its own box, in its own PR. New tasks go in through the operator. `BRIEF.md` is frozen. A new dependency is a request to the operator.

**Fixed interfaces** (names other rows code against; change only through the A1 owner):
- `api/app/engine/financing.py`: `cash(price: float, source_id: str) -> Contribution`; `card(price: float, apr: RateValue, months: int = 12) -> Contribution`; `pal(price: float, rate_cap: RateValue, fee_cap: RateValue, max_amount: RateValue, months: int = 12) -> Contribution | None`; `bnpl(price: float, terms: BnplTerms | None) -> Contribution`.
- `api/app/engine/lease.py`: `rto_full(lease: Lease) -> Contribution`; `cheapest_buyout(lease: Lease) -> tuple[int, float]` (week, total paid); `rto_buyout(lease: Lease) -> Contribution`; `effective_annual_cost(total_payments: float, cash_price: float, term_weeks: int) -> float`.
- `api/app/engine/running.py`: `energy(kwh: ModelEnergy, rate: RateValue, months: int = 36) -> Contribution`; `aging_line() -> CostLine`; `carbon_kg(kwh_per_year: float, kg_per_kwh: RateValue, months: int = 36) -> float`; `upkeep(schedule: list[UpkeepItem], months: int = 36) -> Contribution`.
- `api/app/engine/lifecycle.py`: `remaining_life(age_years: float | None, lifespan: LifespanRange | None) -> tuple[float | None, float | None]`; `cost_per_year(purchase_low: float, purchase_high: float, annual_low: float, annual_high: float, life_low: float | None, life_high: float | None) -> tuple[float | None, float | None]`; `replacement(offer: Offer, life_low: float | None, life_high: float | None) -> Contribution`; `combine(parts: list[Contribution]) -> Contribution`.
- `api/app/engine/quote.py`: `quote(req: QuoteRequest, repo: Repository) -> list[Path]`. `api/app/engine/rank.py`: `rank(filters: ShopFilters, offers: list[Offer], items: list[Item], repo: Repository) -> list[RankedOffer]`.
- `api/app/repository.py`: `Repository.load() -> Repository`; methods `sources() -> list[Source]`, `source(id: str) -> Source`, `rate(key: str) -> RateValue` with keys, in these units: `ga_power_marginal_per_kwh` (dollars per kWh, e.g. `0.15`), `egrid_ga_kg_per_kwh` (kg CO2 per kWh; eGRID publishes lb/MWh, so divide by `2204.62`), `g19_card_apr_assessed` (a fraction: `0.2215` means 22.15%), `pal_rate_cap` (a fraction: `0.28`), `pal_fee_cap` (dollars: `20.0`), `pal_max_amount` (dollars: `2000.0`). `api/app/engine/financing.py` already assumes these units, and 2.1's test should assert each value lies in its unit's plausible range, which catches a percent stored as `22.15` or an unconverted lb/MWh figure; `profile(category: str) -> CategoryProfile`; `model_energy(brand: str, model: str, product_class: str | float | None = None) -> ModelEnergy | None` (`product_class` added 2026-09-26, task 2.2.3); `model_candidates(model: str) -> list[str]`; `standard_ceiling(mfg_year: int, product_class: str, volume_cuft: float) -> ModelEnergy | None`; `new_offers(category: str) -> list[Offer]`; `item(id: str) -> Item | None` (the `Item` in `retailer_cache.json`'s `items` whose `id` matches an offer's `item_id`; `None` if absent; added 2026-09-26 so a new offer's brand and model can reach `model_energy`); `bnpl_terms() -> BnplTerms | None`. Module function `normalize_model(s: str) -> str` (uppercase; drop spaces, `-`, `/`, `.`).
- `api/app/serial/decode.py`: `decode(brand: str, serial: str) -> SerialDecode`.
- `api/app/grok/client.py`: `class GrokClient` with `chat_json(system: str, user: str, image_jpeg: bytes | None = None) -> dict`; reads `XAI_API_KEY` and `XAI_MODEL` from `api/.env`. `api/app/grok/scan.py`: `scan(kind: ScanKind, image_jpeg: bytes, client: GrokClient) -> ScanResult`. `api/app/grok/parse.py`: `parse_request(text: str, client: GrokClient) -> ShopFilters`.
- ~~`api/app/voice/script.py`: `script(paths: list[Path], lang: Literal["en", "es"]) -> str`.~~ Dropped 2026-09-26 with 4.5 and 4.6.
- Reserved source ids: `user` (typed by the user), `user_listing` (from the user's listing), `user_lease` (from the user's lease). Every other id comes from `api/app/data/sources.json`.
- **Flags** (pinned 2026-09-26; the web shows each as a plain sentence): `year_from_rating_data` (added 21:10, task 3.3.5), `costs_not_estimated`, `past_typical_life`, `test_procedure_changed`, `year_from_serial_low_confidence`, `pal_caps_not_an_offer`, `bnpl_terms_not_an_offer`, `over_budget_today`, `delivery_unknown`, `width_unknown`, `fixture`.
- **`Item.attributes` keys:** `product_class` (CFR class code, e.g. `"3"`), `volume_cuft` (total volume printed on the label), `adjusted_volume_cuft` (DOE adjusted volume; only this feeds the standard ceiling), `width_in`, `label_kwh_per_year` (kWh printed on the unit's own EnergyGuide label).
- **Added 2026-09-26 21:10:** `lease.full_term_total(lease: Lease) -> float` (3.2.3: ~~`total_of_payments` if printed, else `weekly_payment * term_weeks`, plus fees~~ → **Verdict (2026-09-26):** the sum of 3.2.2's payment schedule (so a printed payment today replaces the first weekly payment), plus fees — it must match the keep-paying line.); `Repository.model_year_range(brand: str, model: str, product_class: str | float | None = None) -> tuple[int, int] | None` (2.2.5: first and last year DOE lists the model).
- **Energy lookup order** (3.3.3), used by every path builder: `repo.model_energy` (ENERGY STAR, then DOE historical), then `label_kwh_per_year` (`user_entered`), then `repo.standard_ceiling` with `adjusted_volume_cuft`, else `not_estimated`. Added: `Repository.model_year(brand: str, model: str) -> int | None` (2.2.2).

## Phases

<a id="phase-0"></a>
### [ ] Phase 0 — Setup (operator)
> Goal: GitHub `main` holds the scaffold, the test setup, CI and these docs, so every session's worktree starts complete.
> **Build order:** 0.1 → 0.2 → 0.3 → 0.4 → 0.5 → 0.6 → 0.7 → 0.8. Tasks 0.1 to 0.4 are committed directly on `main` in the main checkout (the only commits ever made there); 0.6 then installs the hook that refuses any further commit on `main`.
> **Exit criterion:** `gh run list --workflow ci.yml --branch main --limit 1 --json conclusion -q '.[0].conclusion'` prints `success`.

- [x] **0.1 Commit the docs (Track 0 — operator)** ← start here
  Put the spec at `docs/RealityReceipt_Build_Spec.pdf`. Commit `BRIEF.md`, `PLAN.md`, `AGENTS.md`, `CLAUDE.md`, `LEARNINGS.md`, `.gitignore`, `.claude/acstack.md` and the PDF as `task 0.1: planning docs and repo config`.
  **Acceptance:** `git ls-files BRIEF.md PLAN.md AGENTS.md CLAUDE.md .gitignore .claude/acstack.md docs/RealityReceipt_Build_Spec.pdf | wc -l` prints `7`.

- [x] **0.2 Scaffold the API (Track 0 — operator)**
  `api/app/__init__.py` (empty); `api/app/main.py` with `app = FastAPI()` and `GET /health` returning `{"ok": true}`; `api/tests/test_health.py` calling it through `fastapi.testclient.TestClient`; root `pytest.ini` with `[pytest]`, `pythonpath = api analysis`, `testpaths = api/tests analysis`. Create `api/.venv` with `python3 -m venv api/.venv`, install `fastapi uvicorn pydantic pytest httpx python-multipart python-dotenv pandas matplotlib`, then pin every package with `api/.venv/bin/pip freeze > api/requirements.txt`. `api/.env.example` holds two lines, `XAI_API_KEY=` and `XAI_MODEL=`.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests -q` prints `1 passed`, and `test "$(grep -c '==' api/requirements.txt)" -gt 5 && echo pinned` prints `pinned`.

- [x] **0.3 Scaffold the web app (Track 0 — operator)**
  `npm create vite@latest web -- --template react-ts`; add `tailwindcss`, `@tailwindcss/vite`, `framer-motion`, and dev dependencies `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`. In `web/vite.config.ts`: the Tailwind plugin; `server.proxy` sending `/api` to `http://localhost:8000` with the `/api` prefix stripped; `server.allowedHosts: ['.trycloudflare.com']`; `test.environment: 'jsdom'`. `web/package.json` scripts: `"test": "vitest run"`, `"build": "tsc -b && vite build"`. Add `web/src/smoke.test.ts` asserting `1 + 1 === 2`. Commit `web/package-lock.json`. Delete any unanchored `dist` or `node_modules` line from `web/.gitignore`; the root `.gitignore` covers both.
  **Acceptance:** `npm --prefix web test` exits `0` with `1 passed`, and `npm --prefix web run build` exits `0`.

- [x] **0.4 Add CI (Track 0 — operator)**
  `.github/workflows/ci.yml`, one job named `ci`, on `pull_request` and on `push` to `main`: checkout; `actions/setup-python` 3.12; `python -m venv api/.venv && api/.venv/bin/pip install -r api/requirements.txt`; `api/.venv/bin/python -m pytest api/tests analysis -q`; `actions/setup-node` 20; `npm --prefix web ci`; `npm --prefix web test`; `npm --prefix web run build`.
  **Acceptance:** `grep -c -E 'npm --prefix web run build|pytest api/tests' .github/workflows/ci.yml` prints `2`.

- [x] **0.5 Publish `main` (Track 0 — operator, by hand)**
  Create a private GitHub repo `realityreceipt` (GitHub UI, or `gh repo create realityreceipt --private`). Add the remote yourself (`git remote add origin <url>`; sessions may not edit `.git/config`), then `git push origin main`. Invite the three teammates as collaborators.
  **Acceptance:** `test "$(git ls-remote origin refs/heads/main | cut -f1)" = "$(git rev-parse main)" && echo synced` prints `synced`.

- [x] **0.6 Protect `main` (Track 0 — operator, by hand)**
  In every clone, install the local hook that refuses commits on `main`:
  `h="$(git rev-parse --git-common-dir)/hooks/pre-commit"; printf '%s\n' '#!/bin/sh' '[ "$(git symbolic-ref -q HEAD)" = refs/heads/main ] && { echo "refused: no commits on main; branch and open a PR"; exit 1; }' 'exit 0' > "$h"; chmod +x "$h"`.
  In GitHub settings: branch rule on `main` requiring a pull request (0 approvals) and the `ci` status check; allow squash merging only; enable "Allow auto-merge".
  **Acceptance:** `test -x "$(git rev-parse --git-common-dir)/hooks/pre-commit" && echo hook` prints `hook`, and `gh api 'repos/{owner}/{repo}/branches/main/protection' --jq '.required_status_checks.contexts[]'` prints `ci`.

- [ ] **0.7 Teammate clones (Track 0 — each teammate)** ← unblocks Tracks A to D
  Each teammate clones the repo, installs the 0.6 hook, runs the worktree setup from AGENTS.md "Team workflow", and for Claude Code installs acstack (`git clone https://github.com/AaravChadha/acstack.git ~/acstack && ~/acstack/setup`). Cursor and Codex users confirm their agent reads `AGENTS.md`; if Cursor does not, the operator adds `.cursor/rules/agents.mdc` pointing at it.
  **Acceptance:** in each clone, `api/.venv/bin/python -m pytest api/tests -q` prints `1 passed` and `npm --prefix web run build` exits `0`.

- [ ] **0.8 Keys and Notability (Track 0 — operator)**
  Put a working key and model name in `api/.env` (`XAI_API_KEY=...`, `XAI_MODEL=...`, a vision-capable Grok model from xAI's docs) on every machine that runs the API. Start Notability now: an architecture sketch, screenshot saved to `docs/notability/01-architecture.png`.
  **Acceptance:** `git check-ignore -q api/.env && echo ignored` prints `ignored`, and `ls docs/notability/*.png | wc -l` prints at least `1`.

<a id="phase-1"></a>
### [x] Phase 1 — Contracts (A1)
> Goal: every track builds against the same models, routes and sample receipt. After this PR merges, a contract change needs the A1 owner and a message to the whole team.
> **Build order:** 1.1 → 1.2 → 1.3 → 1.4, landed as one PR the moment all four pass, to unblock Tracks A, B, C and D.
> **Exit criterion:** `api/.venv/bin/python -m pytest api/tests -q` passes with `test_contracts.py` included, and `npm --prefix web test` passes with `contracts.test.ts` included.

- [x] **1.1 Models (Track A1)** ← start here; unblocks everyone
  `api/app/models.py`, Pydantic v2, every model with `model_config = ConfigDict(extra="forbid")`.
  - Literals: `SourceType = Literal["rated", "published", "user_entered", "not_estimated"]`; `CostKind = Literal["purchase", "financing", "running", "upkeep", "repair", "replacement", "end_of_life"]`; `Condition = Literal["new", "used_as_is", "refurbished"]`; `OfferSource = Literal["retailer_cache", "user_listing", "price_tag"]`; `ScanKind = Literal["label", "price_tag", "lease", "listing"]`; `PathGroup = Literal["repair", "used_as_is", "refurbished", "new", "rent_to_own"]`; `PaymentMethod = Literal["cash", "card", "bnpl", "pal", "rto_full", "rto_buyout"]`.
  - Spec models (BRIEF.md "Data model") with deltas. `Item`: as spec; `attributes` keys used: `product_class`, `volume_cuft`, `width_in`. `Offer`: add `url: str | None`, `source_id: str`, `available_within_days: int | None`. `Lease`: `early_purchase_rule: Literal["pct_of_remaining", "cash_price_minus_pct_paid", "none"]`, `early_purchase_pct: float | None`, `early_purchase_text: str`, `missed_payment_rule: str`, `source_id: str`. `CostLine`: `amount_low` and `amount_high` are `float | None`, and a validator requires both `None` exactly when `source_type == "not_estimated"`. `Path`: add `group: PathGroup`; `payment_method: PaymentMethod | None`; `monthly_low` and `monthly_high`, each `list[float]` of length 36, replacing `monthly`; `cost_per_year_low/high` and `expected_life_low/high` are `float | None`. `CategoryProfile`: `upkeep_schedule: list[UpkeepItem]`, `repair_ranges: list[RepairRange]`, `lifespan_range: LifespanRange | None`.
  - New models: `UpkeepItem(label: str, cost_low: float, cost_high: float, every_months: int, source_id: str)`; `RepairRange(label: str, cost_low: float, cost_high: float, source_id: str)`; `LifespanRange(low_years: float, high_years: float, source_id: str)`; `Contribution(pay_today: float, monthly_low: list[float], monthly_high: list[float], lines: list[CostLine])`; `RateValue(value: float, source_id: str)`; `ModelEnergy(kwh_per_year: float, source_type: SourceType, source_id: str)`; `BnplTerms(provider: str, installments: int, interval_weeks: int, apr: float, source_id: str)`; `SerialDecode(mfg_year: int | None, year_confidence: Literal["high", "low", "none"], source_id: str | None, note: str)`.
  - Requests and responses: `QuoteRequest(current: Item | None = None, items: list[Item] = [], offers: list[Offer] = [], lease: Lease | None = None, repair_quote_low: float | None = None, repair_quote_high: float | None = None, budget_today: float | None = None, usage_adjust: float | None = None)` (`current` is "the one you have" and enables the repair path); `ScanResult(kind: ScanKind, valid: bool, errors: list[str], item: Item | None, offer: Offer | None, lease: Lease | None)`; `ShopFilters(category: str | None, budget_today: float | None, need_within_days: int | None, max_width_in: float | None, conditions: list[Condition])`; `RankedOffer(offer: Offer, path: Path)`; `VoiceRequest(paths: list[Path], lang: Literal["en", "es"])`.
  - Money is dollars as `float`, rounded to cents by the engine.
  **Acceptance:** `api/.venv/bin/python -c "import sys; sys.path.insert(0, 'api'); from app.models import Item, Offer, Lease, CostLine, Path, CategoryProfile, Source, Contribution, RateValue, ModelEnergy, BnplTerms, SerialDecode, QuoteRequest, ScanResult, ShopFilters, RankedOffer, VoiceRequest; print('ok')"` prints `ok`.
  **Status (2026-09-26):** also in the contract, beyond the text above: `Period = Literal["once", "month", "year", "window"]` for `CostLine.period`; `SellerType = Literal["retailer", "private", "refurbisher", "rent_to_own"]` for `Offer.seller_type`; `YearConfidence` shared by `Item` and `SerialDecode`; `CategoryProfile.end_of_life_notes`; request bodies `ShopParseRequest(text)` and `ShopRankRequest(filters, offers, items)`. Validators: an estimated `CostLine` needs both amounts, `low <= high`, and a `source_id`; a `Lease` needs `early_purchase_pct` exactly when its rule is not `none`. `Offer.retrieved_at` and `Source.retrieved_date` are dates (ISO strings in JSON).

- [x] **1.2 Sample receipt (Track A1)**
  `contracts/receipt_fridge.json`: a hand-built `list[Path]` for one refrigerator with 9 paths: `repair`; `used_as_is`; `refurbished`; `new` x4 (`cash`, `card`, `bnpl`, `pal`); `rent_to_own` x2 (`rto_full`, `rto_buyout`). It includes at least one line of each `source_type`, one `null` cost per year, one `replacement` line, and `"fixture"` in every path's `flags`, so it can never pass as real data. Numbers are placeholders.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_contracts.py -q` passes (written in 1.3).

- [x] **1.3 Contract tests and route stubs (Track A1)**
  `api/tests/test_contracts.py`: loads `contracts/receipt_fridge.json` with `TypeAdapter(list[Path])`; asserts every `monthly_low` and `monthly_high` has length 36, every `not_estimated` line has `None` amounts, all 5 groups are present, every path has `"fixture"` in `flags`, and a `CostLine` with `source_type="not_estimated"` and `amount_low=1.0` raises `ValidationError`. In `api/app/main.py`, stub every route so other tracks can call them now: `POST /quote` returns the fixture; `POST /scan` (multipart `kind` + `image`) returns `ScanResult(valid=False, errors=["not implemented"])`; `POST /item` echoes a valid `Item`; `POST /shop/parse` returns an empty `ShopFilters`; `POST /shop/rank` returns `[]`; `GET /categories` returns `["refrigerator"]`; `GET /sources` returns `[]`. `api/tests/test_routes.py` calls each stub through `TestClient` and validates the response model.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests -q` reports no failures and at least 9 passed.

- [x] **1.4 TypeScript mirror (Track A1)** ← unblocks Track C
  `web/src/contracts.ts`: hand-written types mirroring every model in 1.1, exported string-literal unions for each `Literal`, and an exported `PATH_KEYS` array of every `Path` field. `web/src/contracts.test.ts` reads `../../contracts/receipt_fridge.json` and asserts each path's keys equal `PATH_KEYS` as a set and each line's `source_type` is one of the four values.
  **Acceptance:** `npm --prefix web test -- contracts` passes, and `npm --prefix web run build` exits `0`.

- [x] **1.5 Source ids for multi-input numbers (Track A1)** (NEW 2026-09-26, raised by row A5 after 2.4)
  A number computed from two sourced inputs must name both. `CostLine.other_source_ids: list[str] = []` lists the sources of a line's other inputs (electricity: the rate; `source_id` stays the kWh figure's). `Path.carbon_source_ids: list[str] = []`, required non-empty whenever `carbon_kg` is set (the kWh source and the eGRID source). Mirrored in `web/src/contracts.ts`; `contracts/receipt_fridge.json` regenerated. Tests in `api/tests/test_contracts.py`.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_contracts.py -q` passes, and `npm --prefix web test -- contracts` passes.

- [x] **1.6 Contract hardening (Track A1)** (NEW 2026-09-26, review)
  In `api/app/models.py`: `ConfigDict(extra="forbid", allow_inf_nan=False)` on `Contract`; `UpkeepItem` and `RepairRange` require `cost_low <= cost_high`; `Item.mfg_year` between 1940 and the current year; `Lease.term_weeks` at most 260. Document the `Item.attributes` keys from "Fixed interfaces" in the `Item` docstring and in `web/src/contracts.ts`.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_contracts.py -q` passes, including new tests that reject an infinite price, an upkeep item with low above high, and `mfg_year=1800`.

- [x] **1.7 Scan results and printed lease numbers (Track A1)** (NEW 2026-09-26, Codex review of #33 and #39)
  `ScanResult.fields: dict[str, str | float | int | bool | None]` carries every value read, valid or not, to pre-fill the correction form; `item`, `offer` and `lease` are set only when `valid` (validator), and a valid scan has no errors. `Lease.payment_today` and `Lease.total_of_payments` (optional, `>= 0`) hold a lease's own printed numbers. Mirrored in `web/src/contracts.ts`.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_contracts.py -q` passes, including tests that an invalid scan cannot carry a lease, that a partial scan's JSON round-trips through `ScanResult`, and that a lease keeps its printed numbers.

<a id="phase-2"></a>
### [ ] Phase 2 — Vertical slice
> Goal: a typed fridge model, plus a used listing price, produces a real sourced receipt with `used_as_is` and `new`/`cash` paths, on a real phone over HTTPS. Proves every track connects before widening.
> **Build order:** B1 (2.1) and A5 (2.4) and A3 (2.5) and C1 (2.8) start at once → B2 (2.2), B3 (2.3) → A2 (2.6) → A1 (2.7) → C2 (2.9), C3 (2.10) → operator (2.11). C tracks build against the `/quote` stub until 2.7 lands.
> **Exit criterion:** `api/.venv/bin/python -m pytest api/tests/test_slice.py -q` passes, and by hand: a phone on the tunnel URL shows the live receipt with no "Sample data" banner.

- [x] **2.1 Sources, rates and repository (Track B1)** ← start here; unblocks A2
  Verify each against its primary document, then record it. `api/app/data/sources.json`: a `Source` list with `energystar_refrigerators`, `doe_ccd`, `ga_power_residential_tariff`, `egrid_georgia`, `frb_g19`, `ncua_pals_ii`, plus lifespan, upkeep and repair sources as B2 finds them. `api/app/data/rates.json`: `{key: {value, source_id, notes}}` for the six rate keys in "Fixed interfaces"; `notes` records the Georgia Power tier, season and riders used, the eGRID rate type used (spec §7: consider non-baseload), and which G.19 series. `api/app/repository.py` implements the `Repository` interface and `normalize_model`, loading from `api/app/data/` via a path relative to the module file. `api/tests/test_repository.py`: every rate's `source_id` resolves in `sources()`; `normalize_model("GTE18-GTH/RWW") == "GTE18GTHRWW"`.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_repository.py -q` passes.
  **Status (2026-09-26):** landed in #7, then reverted in #8 at its owner's request; the work is kept on `feature/2.1-sources-rates-repository`. Relands once its data is checked.

- [ ] **2.2 Refrigerator profile and model energy (Track B2)**
  `api/app/data/refrigerator.json`: a `CategoryProfile` with a published lifespan range, a published-only upkeep schedule (empty list if none is published), repair ranges with sources, `carbon_applicable: true`. `api/app/data/energystar_refrigerators.csv`: columns `brand,model_number,model_normalized,annual_kwh` from the ENERGY STAR certified refrigerators dataset, filtered to the brands in the demo and the retailer cache (keep the file under 1 MB). `Repository.model_energy` returns `ModelEnergy(source_type="rated", source_id="energystar_refrigerators")` on an exact normalized match; `model_candidates` returns up to 5 prefix matches. `api/tests/test_profile.py`: the profile validates, every `source_id` resolves, a known demo model returns its CSV kWh, and a one-character typo returns `None` with at least one candidate.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_profile.py -q` passes.

- [x] **2.2.1 Wildcard, brand-matched model lookup (Track B1/B2)** (NEW 2026-09-26, decision 9)
  Load the full ENERGY STAR certified refrigerators dataset (every row, not a brand subset). In `Repository.model_energy`: treat each `*` or `#` in a dataset model number as one optional letter or digit and match the normalized query against that pattern (a query that itself contains wildcards matches a row with the same pattern); require the brand to match, with a small alias list (GE = GE Appliances); prefer the row with the fewest wildcards; return `None` when the remaining matches disagree on kWh, listing them in `model_candidates`. Never return another brand's row.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_profile.py -q` passes, including tests that a label family (`GTE18FSL****`) and a full retail number built from it both return the family's kWh, that a matching row from another brand returns `None`, and that two matches with different kWh return `None` with both as candidates.

- [x] **2.2.2 DOE historical ratings for old units (Track B2)** (NEW 2026-09-26, decision 1)
  Add DOE's refrigerator and freezer energy rating database (the Weatherization Assistance Program search tool's data, 1949 to 2021) as `api/app/data/doe_wap_refrigerators.csv.gz`, with its source in `sources.json`. `model_energy` falls back to it, with the same matching rules, when ENERGY STAR has no match, returning `source_type="rated"` and that source's id. Add `Repository.model_year(brand: str, model: str) -> int | None` from the same data.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_profile.py -q` passes, including a test that the Maytag family on demo card `label-older-maytag-mb2562.png` returns the DOE file's kWh (the figure printed on that label) and a model year.

- [x] **2.2.3 Icemaker-aware ENERGY STAR lookup (Track B2)** (NEW 2026-09-26, decision 9)
  `api/app/data/energystar_refrigerators.csv` gains a last column `product_class`: the CFR code (`3`, `3I`, `5I-BI`, ...) from the dataset's `product_class` field, re-pulled 2026-09-26 (the same 4,830 rows). `Repository.model_energy(brand, model, product_class=None)` keeps only the matching rows of that class when the model is rated in it, else all of them; `quote`'s energy lookup passes the item's `product_class`. Without the class, GE `GTE18DTNRWW` (359 and 443 kWh) and Frigidaire `FFHT1814WW` (369 and 453) gave no figure, which blanked the retailer cache's new offers.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_repository.py api/tests/test_profile.py api/tests/test_quote_unit.py -q` passes, including tests that `GTE18DTNRWW` gives 359 with class `3`, 443 with `3I` and `None` with no class.
- [x] **2.2.4 Electrolux and Frigidaire, one maker (Track B1/B2)** (NEW 2026-09-26, decision 9)
  In `api/app/repository.py`: `_BRAND_ALIASES` maps `Electrolux Home Products Inc.` to Electrolux, and `_SAME_MAKER` lets Electrolux and Frigidaire each fall back to the other's rows only when the brand as given has none. Scanning the Frigidaire card (`label-current-frigidaire-ffht1822u.png`) returned brand "Electrolux Home Products Inc." and no rating; it now returns the ENERGY STAR 360 kWh. No lookup of a model listed under either brand changes.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_repository.py api/tests/test_profile.py -q` passes, including a test that `model_energy("Electrolux Home Products Inc.", "FFHT1822U*")` gives 360 kWh and that `ERQR32E3HSS` keeps 409 kWh for Frigidaire and 438 for Electrolux.

- [x] **2.2.6 DOE icemaker pairs (Track B2)** (NEW 2026-09-26, decision 9; 2.2.5 was taken by #62)
  In `Repository.model_energy`, DOE rows only: when the matching rows give exactly two kWh figures that differ by the icemaker adder (the icemaker class's current DOE standard intercept minus its base class's, read from `doe_standards_refrigerators.json`: 84 kWh, within 0.5 for rounding), and the item's class is a base class with an icemaker form or that form, return the lower figure for the base class and the higher for the icemaker class. No class, another gap, or three or more figures still give `None`. Seven retailer-cache new fridges that ENERGY STAR does not list (GE `GTS18HGNRWW` 399, `GTS22KGNRWW` 451; Frigidaire `FFTR1814WB`/`WW` 410; Whirlpool `WRT311FZDW` 436, `WRT318FZDM`/`FZDW` 411, all class `3`) had no rating and showed electricity as not estimated.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_repository.py api/tests/test_profile.py -q` passes, including tests that a DOE pair 410/494 gives 410 for class `3`, 494 for `3I` and `None` with no class, that a pair 50 apart, three figures or class `7` give `None`, and that `FFTR1814WW` (class `3`) gives 410 and `WRT318FZDM` gives 411 from the real data.

- [ ] **2.2.5 DOE listing years as a range (Track B1/B2)** (NEW 2026-09-26, Codex review; numbered 2.2.4 in #59, renumbered because #60 took 2.2.4)
  Add `Repository.model_year_range(brand, model, product_class=None) -> tuple[int, int] | None`: the first and last year the DOE historical data lists the model, with the same matching rules as `model_energy`. Keep `model_year` for now.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_profile.py -q` passes, including a test that the Maytag family on `label-older-maytag-mb2562.png` returns the DOE file's first and last listing years, and that an unknown model returns `None`.

- [x] **2.3 Retailer cache (Track B3)**
  `api/app/data/retailer_cache.json`: 8 to 15 real new refrigerator listings recorded by hand, each an `Offer` with `source: "retailer_cache"`, `url`, `retrieved_at`, a `source_id` present in `sources.json`, and an `item_id` whose `Item` (brand, model, `product_class`, `volume_cuft`, `width_in`) is stored alongside. Every model appears in `energystar_refrigerators.csv` or is noted as missing. `api/tests/test_retailer_cache.py`: every offer validates, has a URL and date, and resolves its source.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_retailer_cache.py -q` passes.

- [x] **2.3.1 Retailer-cache notes match the data (Track B3)** (NEW 2026-09-26)
  `retailer_cache.json`'s `energystar_notes` said the ENERGY STAR CSV was not on main and marked all 14 models missing; 7 are ENERGY STAR (class 3) and the other 7 are now noted missing with DOE's without/with-icemaker kWh. `test_retailer_cache.py` now checks each note against `Repository.model_energy` (the repository's wildcard and product-class matching, ENERGY STAR source only) both ways, so a stale "missing" note fails. Done on Krish's behalf.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_retailer_cache.py -q`

- [x] **2.4 Running cost and carbon (Track A5)**
  `api/app/engine/running.py` per "Fixed interfaces". `energy`: monthly cost = `kwh_per_year / 12 * rate.value` in every month 0 to 35; one `running` line with the kWh source label and a `formula` string. `aging_line`: a `running` line labeled "Extra use from age", `not_estimated`. `carbon_kg`: `kwh_per_year * kg_per_kwh.value * months / 12`. `upkeep`: each item's cost at every `every_months`. `api/tests/test_running.py`: 600 kWh at $0.15 gives $7.50 a month and $270.00 over the 36 months; carbon for 600 kWh at 0.4 kg over 36 months is 720 kg.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_running.py -q` passes.

- [x] **2.4.1 Name the rate's source on the electricity line (Track A5)** (NEW 2026-09-26, needs 1.5)
  In `energy`, set `other_source_ids=[rate.source_id]` on the estimated electricity line (not on the `not_estimated` one). Add a test in `api/tests/test_running.py` asserting it.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_running.py -q` passes, including the new test.

- [x] **2.4.2 Electricity formula shows the exact rate (Track A5)** (NEW 2026-09-26, review)
  `running.py`'s `_num` shows up to 6 decimal places, so each electricity formula reproduces its own amount (the rate prints as 0.15641, not 0.1564).
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_running.py -q` passes, including a test that recomputes the per-year amount from the numbers printed in the formula.

- [x] **2.5 Cash path (Track A3)**
  `api/app/engine/financing.py`: `cash` puts the price in month 0 of both arrays, `pay_today = price`, one `purchase` line. `api/tests/test_financing.py`: `cash(800.0, "user_listing")` gives `pay_today == 800.0` and month-0 totals of 800.0.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_financing.py -q` passes.

- [x] **2.6 Lifecycle and the slice quote (Track A2)**
  `api/app/engine/lifecycle.py` and `api/app/engine/quote.py` per "Fixed interfaces" and the pinned formulas. For the slice, `quote` builds `used_as_is` (from a `user_listing` offer and its item) and `new`/`cash` (the cheapest `repo.new_offers("refrigerator")`), each with energy from `model_energy` (else an energy line `not_estimated`), the aging line for used items, carbon with `carbon_source_ids = [kWh source, egrid rate source]` (task 1.5), cost per year from the profile lifespan, replacement when life ends inside 36 months, and paths sorted by `total_3yr_high`. `api/tests/test_lifecycle.py`: `remaining_life(12, LifespanRange(10, 15, ...)) == (0, 3)`; `cost_per_year(1200, 1800, 100, 150, 10, 15) == (1200/15 + 100, 1800/10 + 150)`. `api/tests/test_slice.py`: a typed demo fridge `Item` plus a used offer through `quote` returns both groups, every line's `source_id` is `user`, `user_listing` or in `repo.sources()`, and no path has `"fixture"` in `flags`.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_lifecycle.py api/tests/test_slice.py -q` passes.

- [x] **2.7 Wire the real routes (Track A1)**
  `api/app/main.py`: `POST /quote` calls `quote(req, Repository.load())`; `GET /sources` returns `repo.sources()`; `POST /item` validates and, when brand and serial are present, fills `mfg_year` and `year_confidence` from `decode` once B4 lands. Update `api/tests/test_routes.py` so `/quote` with the slice input returns non-fixture paths.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_routes.py -q` passes.

- [x] **2.7.1 One address: the API serves the web app (Track A1)** (NEW 2026-09-26, decision 6)
  In `api/app/main.py`, serve every route under `/api` as well as unprefixed, and when `web/dist` exists, serve it at `/` with `index.html` for unknown non-API paths, so the built app and the API share one address.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_routes.py -q` passes, including a test that, with a temporary `dist` directory, `GET /` returns its `index.html` and `GET /api/health` returns `{"ok": true}`.

- [x] **2.7.2 Real-data journey test (Track A1)** (NEW 2026-09-26, review)
  `api/tests/test_journey.py`: through `TestClient` on the real `Repository`, POST `/quote` with a typed fridge whose model is in the ENERGY STAR data plus a used listing; assert non-fixture paths, a `rated` electricity line, and that every source id on every line resolves through `GET /sources`.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_journey.py -q` passes.

- [x] **2.8 App shell, API client and manual entry (Track C1)**
  `web/src/api.ts`: typed wrappers for every route, base path `/api`. `web/src/pages/Entry.tsx`: manual entry for brand, model, serial, condition, optional `product_class` and `volume_cuft`, a used listing price, an optional repair quote, and an optional "I can spend up to $___ today" amount; submit calls `/quote` and shows the receipt. No personal questions. `web/src/copy.test.ts` scans every `.ts` and `.tsx` file under `web/src` except tests and fails on an em dash (U+2014) or the word `APR`. `web/src/pages/Entry.test.tsx` renders the form and finds the brand, model and serial inputs by label.
  **Acceptance:** `npm --prefix web test -- Entry copy` passes.

- [x] **2.8.1 Show the real receipt; year and label kWh (Track C1)** (NEW 2026-09-26, decisions 1 and 2)
  In `Entry.tsx`: replace the plain list with `<Receipt paths onLineTap>` and open `<SourceSheet>` from `onLineTap`, fetching `/sources` once; add an optional "Year made" field to both sections (sent as `mfg_year`) and an optional "kWh per year on the yellow label" field to "Your fridge now" (sent as `attributes.label_kwh_per_year`); after a quote, move focus to the results and scroll them into view. In `api.ts`, time requests out after 15 seconds with a plain message.
  **Acceptance:** `npm --prefix web test -- Entry` passes, including tests that the year and label kWh reach the `/quote` body, that the response renders through `Receipt`, and that tapping a cost line opens the source sheet.

- [x] **2.9 Receipt view (Track C2)**
  `web/src/components/Receipt.tsx` and `PathCard.tsx`: paths in API order, each with pay today, total over 3 years and cost per year, ranges shown as `$A to $B`, `not estimated` for `null`; a carbon line only when `carbon_kg` is non-null; a visible "Sample data, not a real quote" banner when any path has `"fixture"` in `flags`. `web/src/format.ts`: `money(n)`, `range(low, high)`. `Receipt.test.tsx` renders `contracts/receipt_fridge.json` and finds the banner and all 9 path names; `format.test.ts` checks `range(80, 180) === "$80 to $180"`.
  **Acceptance:** `npm --prefix web test -- Receipt format` passes.

- [x] **2.9.1 Receipt fits the page and says what is missing (Track C2)** (NEW 2026-09-26, decision 3)
  Remove `Receipt`'s own width, padding and light background so it sits inside the app shell and follows dark mode; give the "What's in this number" toggle a 44px minimum height; show each pinned flag as a plain sentence, with `costs_not_estimated` as a visible note under the headline numbers ("Some costs are not estimated, so the real total may be higher"); label carbon "kg CO2e"; show "up to" beside the PAL path's pay today.
  **Acceptance:** `npm --prefix web test -- Receipt` passes, including tests for the `costs_not_estimated` note, one flag sentence, "CO2e", and "up to" on the PAL path.

- [x] **2.9.2 Sentence for the inferred-year flag (Track C2)** (NEW 2026-09-26, Codex review; with 3.3.5)
  Add the plain sentence for the new pinned flag `year_from_rating_data`: "The year made is estimated from the years DOE lists this model, so its remaining life is a range."
  **Acceptance:** `npm --prefix web test -- Receipt` passes, including a test that the flag renders that sentence.

- [x] **2.10 Tap-to-source sheet (Track C3)**
  `web/src/components/SourceSheet.tsx`: tapping any cost line opens a sheet with its label, amount range, formula, source label (`Rated`, `Published`, `You entered`, `Not estimated`) and, from `/sources`, the title, publisher, URL and retrieved date. `SourceSheet.test.tsx` renders one line of each `source_type` and finds the four label texts.
  **Acceptance:** `npm --prefix web test -- SourceSheet` passes.

- [ ] **2.11 Phone over HTTPS (Track 0 — operator)**
  `docs/runbook.md`: start the API (`api/.venv/bin/uvicorn app.main:app --app-dir api --port 8000`), the web dev server (`npm --prefix web run dev`), and `cloudflared tunnel --url http://localhost:5173`; open the printed `trycloudflare.com` URL on a real phone.
  **Acceptance:** `grep -c -E 'cloudflared tunnel --url|uvicorn app.main:app' docs/runbook.md` prints `2`; by hand, the phone shows the live receipt.

- [ ] **2.11.1 Deploy behind the team's .tech domain (Track 0 — operator)** (NEW 2026-09-26, decision 6; after 2.7.1)
  Claim the free .tech domain (MLH offer), deploy the single service (the API serving `web/dist`) to a host with the xAI key as an environment variable, point the domain at it following the host's DNS instructions, and keep it awake during judging. The quick tunnel stays as backup. Add a "Deploy" section to `docs/runbook.md`, and record a backup video of the demo.
  **Acceptance:** `grep -c '^## Deploy' docs/runbook.md` prints `1`; by hand, a phone on mobile data opens `https://<domain>/` and `https://<domain>/api/health` prints `{"ok":true}`.

<a id="phase-3"></a>
### [ ] Phase 3 — Full receipt and scan
> Goal: every path, the lease, serial decode, and a Grok scan that produces the same receipt as typing, plus the RECS finding.
> **Build order:** A3 (3.1), A4 (3.2), B4 (3.4), B2 (3.5), B1 (3.6), D1 (3.7), D4 (3.12), B3 (3.13) run in parallel → A2 (3.3) → D1 (3.8) → A1 (3.9) → C1 (3.10), C2 (3.11). D1 and D4 may start right after Phase 1.
> **Exit criterion:** `api/.venv/bin/python -m pytest api/tests analysis -q` passes with `test_quote_all_paths.py` and `test_not_a_wrapper.py` included, and `npm --prefix web test` passes.

- [x] **3.1 Card, PAL and BNPL (Track A3)**
  `card`, `pal`, `bnpl` per "Fixed interfaces" and the pinned formulas. Tests in `api/tests/test_financing.py`: `card(1000, RateValue(0.24, ...))` pays 94.56 a month for months 1 to 12 (total 1134.72, within 0.01) with `pay_today == 0`; `pal(1000, ...)` at 28% for 12 months pays 96.50 a month (within 0.01) plus the $20 fee, and returns `None` for a price of 2500; `bnpl(500, None)` returns one `not_estimated` financing line.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_financing.py -q` passes.

- [x] **3.1.1 BNPL installments outside 36 months (Track A3)** (NEW 2026-09-26, decision 7)
  In `bnpl`, an installment falling after month 35 is left out of the window arrays instead of added to month 35; the line's formula still states the full schedule.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_financing.py -q` passes, including a test with installments past month 35.

- [x] **3.2 Rent-to-own (Track A4)**
  `api/app/engine/lease.py` per "Fixed interfaces". Weekly payment `w` (1-based) falls in month `min(35, (w - 1) * 12 // 52)`; fees fall in month 0. `cheapest_buyout` tries every week 1 to `term_weeks` and returns the lowest total paid (payments so far plus the buyout amount under the lease's rule; `none` returns the full term). Lines carry `source_id="user_lease"`. `api/tests/test_lease.py`: `effective_annual_cost(2000, 800, 52) == 1.5` and `(2000, 800, 104) == 0.75`; a 52-week, $30-a-week lease with `pct_of_remaining` 0.5 has its cheapest buyout at week 1 for 795.0; no line label or formula contains `APR`.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_lease.py -q` passes.

- [x] **3.2.1 Lease window, buyout pay today and wording (Track A4)** (NEW 2026-09-26, decisions 4 and 7)
  Weekly payments after month 35 are left out of the window arrays (a 208-week lease at $30 a week counts 156 payments, $4,680; the formula states the full lease total). A buyout in week 1 is included in pay today. `rto_full` keeps the effective annual cost in its formula; `rto_buyout` drops it and states its total minus the cash price ("$X more than the cash price" or "$X less"). A lease with `early_purchase_rule="none"` says "No early purchase terms entered", never "Your lease has no early purchase option".
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_lease.py -q` passes, including tests for the 208-week lease ($4,680 inside the window), a week-1 buyout's pay today ($795 for task 3.2's example lease), the buyout wording, and the "no terms entered" wording.

- [x] **3.2.2 Use the lease's own printed numbers (Track A4)** (NEW 2026-09-26, needs 1.7)
  When `lease.payment_today` is set it is pay today (and month 0's payment) instead of the first weekly payment; when `lease.total_of_payments` is set it is the full-term total, spread evenly over the weeks in the window, and the effective annual cost uses it. Both formulas say the figure is "as printed on your lease".
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_lease.py -q` passes, including a test with the Aaron's demo card's numbers (52 weeks, $33.48 a week, $0.01 today, $1,739.88 total, $1,196.99 cash): pay today is $0.01, the full-term total is $1,739.88, and the effective annual cost is 45%.

- [x] **3.2.3 A lease's full-term total (Track A4)** (NEW 2026-09-26, Codex review; after 3.2.2)
  Add `full_term_total(lease: Lease) -> float` to `api/app/engine/lease.py`: ~~`total_of_payments` if printed, else `weekly_payment * term_weeks`, plus `fees`~~ → **Verdict (2026-09-26):** the sum of 3.2.2's payment schedule (so a printed payment today replaces the first weekly payment), plus fees — it must match the keep-paying line. Pinned in "Fixed interfaces"; 3.3.4 uses it for cost per year.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_lease.py -q` passes, including tests that a 208-week $30 lease totals $6,240, that a printed total wins over the weekly figure, and that fees are added.

- [ ] **3.2.4 Keep-paying states its cost over the cash price (Track A4)** (NEW 2026-09-26 21:45, demo check)
  ~~`rto_full` keeps the effective annual cost in its formula; `rto_buyout` drops it and states its total minus the cash price~~ (3.2.1) → **Verdict (2026-09-26):** `rto_full`'s formula also states `full_term_total(lease)` minus the cash price ("That is $X more than the cash price of $Y"), before the effective annual cost, and says "No early purchase terms entered" when `early_purchase_rule` is "none" (3.3.6 drops the buyout path in that case). `rto_buyout` keeps its own comparison.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_lease.py -q` passes, including a test that the Aaron's demo lease (`demo/cards/cards.json`) gives a keep-paying formula containing "$542.89 more than the cash price of $1,196.99", "45%" and "No early purchase terms entered".

- [x] **3.3 All paths in the quote (Track A2)**
  Extend `quote` to all 9 path kinds: `repair` (when `current` is given; repair cost from `repair_quote_*` as `user_entered`, else the profile's repair ranges as `published`; running cost from the current unit), `refurbished` (from a refurbished listing; warranty months shown in a flag), `new` x4 via A3, `rent_to_own` x2 via A4 (when `lease` is given). A path whose inputs are absent is omitted, never invented. Apply flags: `past_typical_life`, `test_procedure_changed` (when comparing a pre-2014 unit with a newer one), `year_from_serial_low_confidence`. `api/tests/test_quote_all_paths.py`: a full request returns 9 paths sorted by `total_3yr_high`; each path's totals equal the sums of its arrays. `api/tests/test_copy.py`: no label, formula or flag in that output contains an em dash, `APR` or `qualif`.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_quote_all_paths.py api/tests/test_copy.py -q` passes.

- [x] **3.3.1 Incomplete paths flagged and sorted last (Track A2)** (NEW 2026-09-26, decision 3)
  A path whose electricity (for a category that uses energy), financing or replacement timing is `not_estimated` gets the flag `costs_not_estimated`. `quote` sorts complete paths by `total_3yr_high` then `pay_today`, then flagged paths in the same order.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_quote_all_paths.py -q` passes, including a test where a rent-to-own path with no electricity figure sorts after a complete new-cash path even though its total is lower.

- [x] **3.3.2 Replacement and past-typical-life honesty (Track A2)** (NEW 2026-09-26, decision 8)
  At or past the typical life: flag `past_typical_life`, insert no replacement, and add a `not_estimated` replacement line ("When it will need replacing is not estimated"), so the path is also `costs_not_estimated`. When a replacement falls inside the window, the old unit's running cost and carbon stop at that month and the replacement unit's (its rated figure, or `not_estimated`) run after it.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_quote_all_paths.py -q` passes, including tests for a 20-year-old unit (no replacement amount; flags `past_typical_life` and `costs_not_estimated`) and a replacement at month 12 (running cost from month 12 uses the new unit's kWh).

- [x] **3.3.3 One energy lookup for every path, including the shop (Track A2)** (NEW 2026-09-26, decisions 1 and 2)
  One function in `quote.py` resolves a unit's kWh in the pinned "Energy lookup order", and every path builder uses it, including `_cash_path`, so `rank` agrees with `quote`. When `mfg_year` is missing, use `repo.model_year` if it returns one. Add `model_year` to the `QuoteRepository` protocol.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_quote_all_paths.py api/tests/test_rank.py -q` passes, including a test that the same used unit gets the same electricity line from `quote` and from `rank`, and a test for each step of the lookup order.

- [x] **3.3.4 Cost per year from the full cost; ranges that never flip (Track A2)** (NEW 2026-09-26, Codex review; needs 3.2.3)
  Cost per year's purchase total is the full acquisition cost: the cash price, or the full financed total (card and PAL schedules, BNPL's full cost, `lease.full_term_total` for rent-to-own), never the part inside the 36-month window. Build every low/high pair (3-year total, cost per year, expected life) as the min and max of its scenarios, since an earlier, more efficient replacement can be the cheaper case.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_quote_all_paths.py -q` passes, including a test that a 208-week $30 lease's cost per year uses the $6,240 total (about $536 a year, not $416), and a property test over at least 500 generated requests that low never exceeds high for any path's 3-year total, cost per year or expected life.

- [x] **3.3.5 An inferred year is a range, flagged (Track A2)** (NEW 2026-09-26, Codex review; needs 2.2.5)
  When `mfg_year` is missing and `repo.model_year_range` returns years, use both ends for the age, so expected life and cost per year become ranges; add the flag `year_from_rating_data`; never write an inferred year into `mfg_year`. Call `model_year_range` only if the repository has it until 2.2.5 lands.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_quote_all_paths.py -q` passes, including a test that an undated unit whose model DOE lists over several years gets an expected-life range from both ends and the `year_from_rating_data` flag, with `mfg_year` left `None`.

- [ ] **3.3.6 No buyout path without buyout terms (Track A2)** (NEW 2026-09-26 21:45, demo check; after 3.3.4)
  In `quote`, build "Rent-to-own, early buyout" only when `req.lease.early_purchase_rule` is not "none". Without terms it repeated the keep-paying numbers on a second card; 3.2.4 puts "No early purchase terms entered" on the keep-paying path instead.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_quote_all_paths.py -q` passes, including tests that a lease with `early_purchase_rule="none"` gives exactly one rent-to-own path and a lease with terms gives two.

- [x] **3.4 Serial decode (Track B4)**
  `api/app/serial/decode.py`: decoders keyed by brand, only for the brands on the demo cards and in the retailer cache, each rule's `source_id` in `sources.json`. A year code that repeats on a cycle resolves from model era when possible, otherwise returns `year_confidence="low"`. An unknown brand returns `SerialDecode(None, "none", None, "no decoder for brand")`. `api/tests/test_serial.py`: one known serial per supported brand decodes to its year; an unknown brand returns confidence `none`.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_serial.py -q` passes.

- [x] **3.5 Standard ceiling for old units (Track B2)**
  `api/app/data/doe_standards_refrigerators.json`: for the product classes on the demo cards, each DOE standard period with its maximum-energy formula in adjusted volume, sourced. `Repository.standard_ceiling` returns `ModelEnergy(source_type="published", source_id=...)`. `quote` (A2) uses it only when `model_energy` returns `None` and year, class and volume are known. Test in `api/tests/test_profile.py`: a 2004 unit of a demo class returns the formula's value for its volume.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_profile.py -q` passes.

- [x] **3.6 BNPL terms, optional (Track B1)**
  If one provider publishes pay-in-installment terms, record them in `api/app/data/bnpl.json` with URL and date and return them from `bnpl_terms()`; otherwise `bnpl_terms()` returns `None` and the BNPL path stays `not_estimated`. Test in `api/tests/test_repository.py` either way.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_repository.py -q` passes.

- [x] **3.7 Grok scan (Track D1, in Cursor)** ← may start after Phase 1
  `api/app/grok/client.py` and `api/app/grok/scan.py` per "Fixed interfaces". One system prompt per `ScanKind` asking for strict JSON with only the fields printed on the image (label: brand, model, serial, `product_class`, `volume_cuft`; price tag: brand, model, price; lease: every `Lease` field plus `early_purchase_text`; listing: brand, model, price, condition). The response validates into `ScanResult`; on failure `valid=False`, `errors` lists the Pydantic errors, and every field that did parse is kept for the correction form. No number is computed by the model. `api/tests/test_scan.py` uses a fake `GrokClient` returning recorded JSON from `api/tests/fixtures/scan/`: one valid response per kind, and one malformed response that yields `valid=False` with partial fields.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_scan.py -q` passes. The real call is checked by hand in 3.8.
  **Status (2026-09-26 18:05, review):** also extract `mfg_year` when printed and, from an EnergyGuide label, `label_kwh_per_year`. Per xAI's docs as read in review (not re-verified): the API is OpenAI-compatible with JSON-schema structured output; use a non-reasoning vision model; send JPEG or PNG only, shrunk on the phone to about 1600px.

- [x] **3.8 Not-a-wrapper test (Track D1, in Cursor)**
  For each demo card from 3.13: record the real Grok response once into `api/tests/fixtures/scan/<card>.json`, and write the typed equivalent into `api/tests/fixtures/typed/<card>.json`. `api/tests/test_not_a_wrapper.py`: for every card, `quote` on the scan result's item equals `quote` on the typed item, compared as JSON.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_not_a_wrapper.py -q` passes with one case per demo card.

- [x] **3.9 Wire scan (Track A1)**
  `POST /scan` calls `scan(kind, image, GrokClient())` and returns the `ScanResult`; when `valid` is true and the item has brand and serial, it also applies `decode`. Test in `api/tests/test_routes.py` with the fake client injected through a FastAPI dependency override.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_routes.py -q` passes.

- [ ] **3.10 Capture, upload and correction (Track C1)**
  In `Entry.tsx`: a "Scan" button using `<input type="file" accept="image/*" capture="environment">`, an "Upload saved image" button, and a kind picker (label, price tag, lease, listing). A scan result, valid or not, pre-fills the same manual form for correction; the user confirms before quoting. A lease form with every `Lease` field. `Entry.test.tsx`: an invalid `ScanResult` with a parsed brand pre-fills the brand field and shows the errors.
  **Acceptance:** `npm --prefix web test -- Entry` passes.
  **Status (2026-09-26, task 1.7):** pre-fill the correction form from `ScanResult.fields`; `item`, `offer` and `lease` arrive only when the scan is valid.
  **Status (2026-09-26 21:10, reviews of #48 and #52):** also: the lease form gets `payment_today`, `total_of_payments` and the leased fridge's brand and model, and no "Lease source" field; pass `budgetToday` into `Receipt` so 3.11's dimming works; drop "Price tag" from the scan picker tonight; give the `/scan` request a 60-second timeout with a visible reading state.

- [x] **3.11 Budget, flags and motion (Track C2)**
  In `Receipt.tsx`: paths whose `pay_today` exceeds the "spend up to" amount are dimmed with "More than you can spend today" (never hidden); flags render as plain sentences; a Framer Motion print-in animation on first render, off under `prefers-reduced-motion`. `Receipt.test.tsx` covers the dimming.
  **Acceptance:** `npm --prefix web test -- Receipt` passes.

- [x] **3.12 RECS finding (Track D4)** ← may start after Phase 0
  `analysis/recs/VARIABLES.md`: the verified RECS 2020 variable names (income, `KOWNRENT`, total energy cost, household weight, replicate weights, state or region) and the replicate-weight variance formula, each quoted from the EIA codebook or methodology page with its URL. `analysis/recs/burden.py`: energy burden (energy cost / income) by income bracket x renter status, weighted, with replicate-weight standard errors and unweighted n per cell; income from bracket midpoints, the open top bracket reported as not estimated; Georgia if every cell has enough cases, otherwise South, stated in the output. Writes `analysis/recs/out/burden.csv` and `analysis/recs/out/burden.png` (both committed; the raw microdata is not). `analysis/recs/test_burden.py` checks the weighted mean and the replicate SE on a 6-row synthetic frame with hand-computed answers.
  **Acceptance:** `api/.venv/bin/python -m pytest analysis -q` passes, and `test -f analysis/recs/out/burden.csv && test -f analysis/recs/out/burden.png && echo ok` prints `ok`.

- [x] **3.13 Demo materials (Track B3)**
  `demo/cards/`: printable images of real rating labels (at least one pre-2005 unit and one current model), a real rent-to-own listing or lease, and a used-listing screenshot with the seller's name and photos cropped out. `demo/cards/README.md` lists each card's source URL, date, and the fields it shows. Print them.
  **Acceptance:** `test "$(ls demo/cards/*.png demo/cards/*.jpg 2>/dev/null | wc -l)" -ge 3 && echo ok` prints `ok`.

- [x] **3.13.1 Demo cards that produce the demo (Track B3)** (NEW 2026-09-26, review)
  Replace or add cards so each scenario runs through the real pipeline: an old unit's EnergyGuide label whose model is in the ENERGY STAR or DOE historical data (the Maytag card, once 2.2.2 lands), a current label whose exact model is in the ENERGY STAR data, a rent-to-own page showing the weekly payment, term, cash price and early purchase terms, and a used listing showing price, brand and model (and year if stated). Record each card's typed equivalent in `demo/cards/cards.json`; `api/tests/test_demo_cards.py` checks that each fridge card's model returns a rated figure and that the lease card has a term and a cash price.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_demo_cards.py -q` passes.

<a id="phase-4"></a>
### [ ] Phase 4 — Shop, submit
> Goal: the Grok shopping request ranks new and used offers by cost per year (Visa), ~~the receipt can be read aloud in English and Spanish (SpaceXAI),~~ and the demo is frozen and submitted.
> **Build order:** D2 (4.1) and A2 (4.2) in parallel → A1 (4.3) → C4 (4.4) → operator (4.7 to 4.9). ~~D3 (4.5, 4.6)~~ dropped 2026-09-26.
> **Exit criterion:** `gh run list --workflow ci.yml --branch main --limit 1 --json conclusion -q '.[0].conclusion'` prints `success` on the commit tagged `freeze`, and every submission checklist box is ticked.

- [ ] **4.1 Request parsing (Track D2, in Cursor)**
  `api/app/grok/parse.py` per "Fixed interfaces": Grok turns text into `ShopFilters` JSON, validated; on failure, empty filters plus the errors. The UI shows the filters for editing before ranking. `api/tests/test_parse.py` with a fake client: "about $300, small space, need it this week" maps to `budget_today=300`, `need_within_days=7`, and a width filter from the recorded response.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_parse.py -q` passes.

- [x] **4.2 Ranking (Track A2)**
  `api/app/engine/rank.py` per "Fixed interfaces": each offer is quoted with its own `Item` as the `new`/`cash` path (retailer cache) or `used_as_is` (user listing), filtered by `ShopFilters`, sorted by `cost_per_year_high` with `None` last. `api/tests/test_rank.py`: a cheap used offer with 1 year of life left ranks below a new offer with a lower cost per year.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_rank.py -q` passes.

- [x] **4.2.1 Shop keeps unknowns, flagged (Track A2)** (NEW 2026-09-26, decisions 3 and 5)
  An offer with no `available_within_days` stays in when `need_within_days` is set, flagged `delivery_unknown`; an offer with no width stays in when `max_width_in` is set, flagged `width_unknown`. Offers flagged `costs_not_estimated` rank after complete ones, then each group by `cost_per_year_high`, `None` last.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_rank.py -q` passes, including tests that a used listing survives "need it within 7 days" with `delivery_unknown`, and that an incomplete offer ranks after a complete one.

- [ ] **4.3 Wire shop routes (Track A1)**
  `POST /shop/parse` calls `parse_request`; `POST /shop/rank` calls `rank` with the retailer cache plus any listings in the request. Tests in `api/tests/test_routes.py` with the fake client.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_routes.py -q` passes.
  **Status (2026-09-26 21:31):** `/shop/rank` is wired: the retailer cache's new offers plus the request's own listings, through `rank`, with tests in `test_routes.py`. The request may carry only `user_listing` offers, and a listing may not reuse a cached item's id (both 422). `/shop/parse` stays a stub until 4.1 lands; this box stays open until then.

- [x] **4.4 Shop page (Track C4)**
  `web/src/pages/Shop.tsx`: a text box for the request, the parsed filters shown as editable chips (the visible AI step), ranked offers with cost per year and a "View at retailer" link that opens the offer's `url`. No in-app checkout. `Shop.test.tsx` renders ranked offers from a stub and finds each link.
  **Acceptance:** `npm --prefix web test -- Shop` passes.

- [x] **4.5 ~~Voice script (Track D3, in Cursor)~~** Dropped (2026-09-26): see the voice decision; not built.
  `api/app/voice/script.py`: English and Spanish templates filled only from `Path` fields; no model writes or translates the script. `api/tests/test_voice.py`: for the fixture receipt, every number in the script appears in the paths, and neither script contains an em dash or `APR`.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_voice.py -q` passes.

- [x] **4.6 ~~Grok Voice read-aloud, stretch (Track D3, in Cursor)~~** Dropped (2026-09-26): see the voice decision; not built.
  Only after the open item "Grok Voice plays given text" is confirmed: `api/app/voice/tts.py` sends the fixed script to Grok Voice and returns audio; A1 adds `POST /voice` (`VoiceRequest` in, `audio/mpeg` out); C2 adds a play button with a language toggle. Test with a fake TTS client.
  **Acceptance:** `api/.venv/bin/python -m pytest api/tests/test_voice.py -q` passes; by hand, both languages play on the phone.

- [ ] **4.7 README (Track 0 — operator)**
  `README.md`: what it is, how to run it (from `docs/runbook.md`), the data sources with links, and what is not estimated and why.
  **Acceptance:** `grep -c -E 'api/.venv/bin/uvicorn|npm --prefix web run dev' README.md` prints at least `2`; by hand, a teammate follows it on their clone.

- [ ] **4.8 Demo run sheet and pitch (Track 0 — operator)**
  In Notability: the pitch storyboard and demo run sheet (spec §6), screenshot saved as `docs/notability/02-run-sheet.png`. Rehearse the demo once end to end with a timer.
  **Acceptance:** `ls docs/notability/*.png | wc -l` prints at least `2`.

- [x] **4.8.1 Stage wording fixes (Track 0 — operator)** (NEW 2026-09-26, review)
  In `docs/pitch.md`: "ACEEE's 2016 report" instead of "2016 data" (or ACEEE's 2024 update, after confirming its Atlanta low-income column); no "2004 unit" (say what the card shows); "tap any line" instead of "tap any number"; "energy costs equal to X% of income (EIA-estimated)" instead of "spent"; no claim that a refurbished warranty narrows a range or that other categories work today; crop the under-$5,000 bracket from the chart; about 20 seconds of visible AI (the scan and the shopping request's filter chips); open with the lease story.
  **Acceptance:** `grep -c -E '2004 unit|2016 data|[Tt]ap any number' docs/pitch.md` prints `0`.

- [x] **4.8.2 Pitch follows the rewritten demo script (Track 0, operator)** (NEW 2026-09-26, Codex review)
  Align `docs/pitch.md` with "Demo Script for Judges": lead with the lease ($0.01 today, $1,739.88 total, $542.89 over its cash price, 45%); no serial typed from a card, no buyout week, the Maytag as Rated 505 kWh from DOE historical data with no year; paths sorted with complete ones first; the lease page does show its total. Every number must match `analysis/recs/out/burden.csv` or the demo script.
  **Acceptance:** `grep -c -i -E 'buyout week|serial|sorted by total over 3 years' docs/pitch.md` prints `0`.

- [ ] **4.9 Code freeze at Sun 02:00 (Track 0 — operator)**
  Merge nothing new after 02:00 except demo-breaking fixes. Tag the last green `main` commit: `git tag freeze origin/main` then `git push origin freeze`.
  **Acceptance:** `git rev-parse -q --verify refs/tags/freeze && echo tagged` prints `tagged`.

## Demo Script for Judges

~~Scenarios 1 to 4 as first written (the "2004 unit", "Published, up to when new", the serial typed from the back, the cheapest buyout week).~~ → **Verdict (2026-09-26 21:00):** rewritten from what the cards and data actually produce, per the reviews of #39 and the demo cards: none of those four claims holds. Every number said aloud must be on screen.

**Scenario 1: the lease (the poverty premium). Lead with this.**
> "This is a real rent-to-own page for a fridge, printed out."
- Card: `lease-aarons-frigidaire-frte1936av.png` (Aaron's, ZIP 30309, retrieved 2026-09-26). Enter the lease (scan, or the lease form from 3.10): 52 weekly payments of $33.48, cash price $1,196.99, paid today $0.01, total of payments $1,739.88.
- The receipt: "Rent-to-own, keep paying" shows **$0.01 today** and **$1,739.88 in total, as printed on the lease: $542.89 more than its own cash price, an effective annual cost of 45%.** ~~Beside it, new fridges from store listings~~ → **Verdict (2026-09-26 21:45):** the paths sort by 3-year total, so the new fridges come first and the lease is the last card, with the highest 3-year total on the receipt: point at that. The new fridges come from store listings (the cheapest is a $548 Frigidaire at Home Depot: a different, smaller model, so say "a new fridge", not "the same fridge"; the card itself shows no brand), then the PAL line ("up to", with its caps).
- Needs: 3.2.2 (printed numbers), 3.2.4 (the $542.89 on the keep-paying path), 3.3.6 (one lease card, not two) and a lease form (3.10); until 3.10 is on main, the only way in is the scan. Never say a buyout week, "120 days", or APR.

**Scenario 2: every line has a source (the trust layer).**
> "This is the label from an older Maytag."
- Card: `label-older-maytag-mb2562.png`. Enter it as "Your fridge now" with a repair quote (for example $180): with no quote there are no repair ranges, so there is no repair path.
- Tap the electricity line: **Rated, 505 kWh a year, from DOE's historical refrigerator ratings**, times the Georgia Power rate (tap through to both sources). Tap the replacement line: "not estimated", left blank on purpose, because the unit is past its typical life.
- Don't state a year (the label prints none), and don't claim big energy savings: against a new fridge the gap is about $20 a year ($78.99 against $56.31 on main at 54a9954).
- The receipt also shows two flag sentences, both true: the year made is estimated from the years DOE lists this model (3.3.5), and the energy test changed around 2014. Read them if asked; still state no year.

**Scenario 3: used vs new, asked in plain words (Visa).** Only if the shop (4.1, 4.3, 4.4) is on main by 23:30.
> "About $300, small space, need it this week."
- Type the request → Grok's parsed filters appear as editable chips → offers ranked by cost per year, with unknown delivery or width flagged, not hidden → "View at retailer". Include the used GE listing (`listing-used-ge-gie18gsnrss.png`, $175): ask its age and enter it, since the listing states none.
- Check the numbers before going on stage: at some prices and years a used and a new option land on the same cost per year, which looks like a bug. Measured on main at 54a9954 through `/quote`: the $175 used GE is rated 443 kWh, $94.29 a year, against $98.46 for the cheapest new: close, not equal.

**Scenario 4: not a wrapper.** Only if a real scan works by 22:00.
> "The AI only reads the label. Watch me type the same thing by hand."
- Scan `label-current-frigidaire-ffht1822u.png` (it prints the maker, "Electrolux Home Products Inc."; leave it as read: the app treats Electrolux and Frigidaire as one maker, task 2.2.4, and task 3.8 checks that the scanned and typed receipts match), then type `FFHT1822U*` by hand: the identical receipt, rated 360 kWh.

**Presenter rules:** say the cards are printouts of real labels and pages; tap any *line*, not any number; no year for the Maytag, no "2004", no buyout week, no APR, no "you qualify", no absolute claims.

Scenario 1 is the strongest talking point: its numbers come straight off a real lease page and need no explanation. ~~Open the pitch on the RECS finding (South region, EIA-estimated);~~ → **Verdict (2026-09-26):** open the pitch on the lease (Scenario 1), then the RECS finding (South region, EIA-estimated) second. The old sentence was carried over from the earlier script and contradicted Scenario 1 and task 4.8.2. Close on the cost line and the carbon line together.

## Future Extensions (mention to judges, don't build)

- A Spanish version of the screen, from written templates, so no model touches a number.

- More categories as data profiles: water heaters (gas and electric lines), room air conditioners (usage hours), washers, vehicles (fuel, scheduled servicing).
- Electricity rates projected forward from EIA monthly Georgia prices instead of held flat (TigerData, if that prize is confirmed).
- Published degradation data for aging appliances, to close the "Extra use from age" gap.
- Buy now pay later terms from more providers, with sources.

## Submission checklist `Sun 02:00 to 08:00`
- [ ] Confirm no secrets file was ever committed:
  `git log --all --name-only --format= | sort -u | grep -iE '(^|/)\.env|\.envrc$|secret|\.pem$|\.key$|service.?account|credential'`
  prints nothing, or only `.env.example` files. No name list is complete: also read `git ls-files` once for anything else that holds a key.
- [ ] README has run instructions verified on a teammate's clone.
- [ ] Devpost: main track A Marina's Mission; sponsor challenges Visa, SpaceXAI and Notability; the Create-X checkbox if the team wants it.
- [ ] Notability: at least 2 screenshots in the Devpost, the "Notability" tag, and a note on how it was used.
- [ ] SpaceXAI: the write-up names the Grok vision and request-parsing parts and that they were built in Cursor (no voice feature: dropped).
- [ ] Visa: the write-up leads with the generative AI shopping flow and used vs new ranking.
- [ ] Stage wording checked against spec §6: "effective annual cost", no "APR", no "you qualify", no absolute claims, the ACEEE figure dated 2016, no HL Hunt figure.
- [ ] Any event-required sections present and **user-authored**; the agent never writes them.
- [ ] Demo rehearsed once end to end, timed.

## Cross-cutting risks

- **R1: Contract churn.** A model change after Phase 1 breaks every session coding against it at once. Handled by one owner, A1, and a team message before any change merges. **Owner: Phase 1.1.**
- **R2: PLAN.md merge conflicts.** Every PR ticks a box in PLAN.md. Handled by separating each checkbox line from the next by its acceptance line, and adding new tasks only through the operator. **Owner: Phase 0.1.**
- **R3: A secret committed.** A key in any committed file is exposed to every collaborator and hard to erase. Handled by the `.gitignore` rules, `api/.env.example` with empty values, and the submission check. **Owner: Phase 0.2.**
- **R4: Unverified numbers on stage.** A wrong tariff tier or eGRID rate type slips past a quick review. Handled by B1 recording in `rates.json` notes exactly which tier, season, riders and rate type were used, from the primary document. **Owner: Phase 2.1.**
- **R5: Model-number misreads.** One wrong character and the lookup misses. Handled by exact normalized matching, candidates on a miss, and the correction form; never a silent fuzzy match. **Owner: Phase 2.2.**
- **R6: Grok unavailable at the expo.** Handled by the upload button with saved images and the typed entry, which produce the same receipt. **Owner: Phase 3.8.**
- **R7: CI slowness under many PRs.** Handled by keeping tests fast and network-free (fake Grok clients everywhere). **Owner: Phase 0.4.**

## Open items

- [ ] **Team names and row assignment (NEW 2026-09-26).** Track A to D placeholders until assigned; each person claims rows in the team chat.
- [ ] **Grok API key and vision model name (NEW 2026-09-26).** SpaceXAI gives credits (spec §1); a working key is not confirmed. Blocks 3.7 onward; checked in 0.8.
- [x] **Grok Voice plays given text (NEW 2026-09-26).** Resolved 2026-09-26: voice dropped, so no longer needed. It must read a fixed script word for word, or a spoken number can differ from the screen. Blocks 4.6.
- [ ] **Cursor reads AGENTS.md (NEW 2026-09-26).** Checked in 0.7.
- [ ] **Best Buy API key (NEW 2026-09-26).** Assume it will not arrive; the hand-built cache in 2.3 is the plan.
- [ ] **TigerData prize (NEW 2026-09-26).** Enter only if confirmed (spec §1).
- [ ] **Spec §7 verify list (NEW 2026-09-26).** Georgia Power tier, season and riders and the eGRID rate type (2.1); the DOE standard ceiling and the ~2014 test procedure change (3.5); RECS variables and cell sizes (3.12); whether a Georgia regulator publishes rent-to-own multiples and whether a newer ACEEE Atlanta figure exists (pitch, 4.8).
  **Status (2026-09-26):** RECS variables and cell sizes answered by `analysis/recs/VARIABLES.md` (3.12, #10): every name and the jackknife formula quoted from EIA; Georgia fails EIA's 10-household rule in 17 of 30 cells, so the finding is for the South region.

- [ ] **Year made from DOE rating data (NEW 2026-09-26, from 3.3.3).** `Repository.model_year` returns the *last* year DOE lists a model, so an undated unit can look younger than it is. Decide: return the first-to-last range (B1) and show it, or a flag such as `year_from_rating_data` with a sentence (A1). Until then, never state that year on stage.

## Glossary

- **Path:** one way to get the item (repair, used, refurbished, new with a payment method, rent-to-own), with its three headline numbers.
- **Contribution:** the costs one engine module adds to a path: pay today, two 36-month arrays, and its cost lines.
- **Row:** one line of the file ownership table; one session's file set.
- **Not a wrapper:** the rule that typed entry and scanning produce the identical receipt.
