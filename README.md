# RealityReceipt

RealityReceipt compares the ways to get something you need by what each one costs over time, not by its sticker price. It is built for appliances in general, with cars next; today it covers **refrigerators only**, the one category with sourced data so far. Built at HackGT 13 (Georgia Tech, September 25 to 27, 2026).

The option that looks cheapest today can cost more over time: an old used unit that is expensive to run, a rent-to-own lease whose payments add up to far more than the cash price, a purchase on high-interest credit. A price tag leaves out the running cost, the interest, the lease terms and how long the unit lasts.

## What it does

1. You type the fridge you have, a used one you found, or both. There is no sign-up and no question about income or anything personal.
2. The receipt lays out the ways to get the item side by side: repair the one you have (when you enter a repair quote), used, refurbished, new (pay cash, credit card, buy now pay later, credit union PAL) and rent-to-own (when a lease is entered).
3. Each way shows three numbers: what you pay today, the total over 3 years, and the cost per year of use. Totals are ranges, low to high. Complete paths come first, cheapest 3-year total (high end) first; a path with a cost not estimated comes after them and says so.
4. Tap any cost line to see its source, the formula, and whether the figure is **Rated**, **Published**, **You entered** or **Not estimated**. A carbon line (kg CO2e over 3 years) sits beside the cost.

**How the numbers are made.** AI only reads input: Grok turns a photo of a label, price tag, lease or listing into typed fields, and turns a plain-words shopping request ("about $300, small space, need it this week") into filters. It does not produce or change any number on the receipt. The numbers come from a deterministic engine in `api/app/engine/` and the committed data in `api/app/data/`, both covered by the tests in `api/tests/`. The check for this is "not a wrapper": typing a unit's brand, model and serial by hand gives the same receipt as scanning its label.

**Status (2026-09-26):** typed entry and the receipt with its source sheet are on `main`. The scan (PLAN.md tasks 3.7 to 3.10, which also add the lease form) and the plain-words shopping page (4.1 to 4.4) are still being built; until they land, `/scan` and `/shop/*` return placeholders.

## Scope: refrigerators today, cars next

The receipt, the payment paths (cash, credit card, buy now pay later, credit union PAL, rent-to-own), the lease math, the 3-year window and tap-to-source do not depend on the item. What is specific to a category is its data: for refrigerators, the ENERGY STAR and DOE ratings, the fridge standards, the icemaker rule, a published lifespan and real store listings. `/quote` refuses any other category with "No data for the category … yet".

Cars are the next category: fuel from fueleconomy.gov MPG and the Georgia gasoline price, upkeep by miles (oil changes, tires), Georgia's title tax, auto loans, and buy-here-pay-here lots through the same lease math. Insurance, major repairs and resale value would show as not estimated. This is planned, not built; see PLAN.md, Future Extensions.

## Run it

Run every command from the root of the checkout. CI uses Python 3.12 and Node 20.

### Once per checkout

```
python3 -m venv api/.venv
api/.venv/bin/pip install -r api/requirements.txt
npm --prefix web ci
```

For the Grok steps (scan and shopping request), copy `api/.env.example` to `api/.env` and fill in `XAI_API_KEY` and `XAI_MODEL`. `api/.env` is gitignored; never put a key in a committed file. Typed entry and the receipt run without a key.

### Development: API and web dev server

Two terminals. The web dev server forwards `/api/...` to the API with the `/api` prefix removed.

**Terminal 1, the API** on port 8000:

```
api/.venv/bin/uvicorn app.main:app --app-dir api --port 8000
```

Check: `curl http://localhost:8000/health` prints `{"ok":true}`.

**Terminal 2, the web dev server** on port 5173:

```
npm --prefix web run dev
```

Check: `curl http://localhost:5173/api/health` prints `{"ok":true}`. Open http://localhost:5173/ in a browser.

### One address: the API serves the built web app

Build the web app, then start the API. When `web/dist` exists at startup, the same server serves the web app at `/` and the API under `/api` (the routes also answer without the prefix).

```
npm --prefix web run build
api/.venv/bin/uvicorn app.main:app --app-dir api --port 8000
```

Check: open http://localhost:8000/ for the app, and `curl http://localhost:8000/api/health` prints `{"ok":true}`. The server looks for `web/dist` only when it starts, so after a new build, restart uvicorn.

### On a phone

Phone cameras need HTTPS. A Cloudflare quick tunnel gives the local server a public `https://` address on `trycloudflare.com`; no Cloudflare account is needed. Install it once (on macOS, `brew install cloudflared`), then in a third terminal:

```
cloudflared tunnel --url http://localhost:5173
```

Use `http://localhost:8000` instead when running the one-address mode. Open the printed address on the phone; it changes every time the tunnel starts. Troubleshooting (allowed hosts, proxy errors, tunnel limits) is in [`docs/runbook.md`](docs/runbook.md).

### Deployed

The deployed app is the one-address mode as a single Render web service. How to create it, point the team's .tech domain at it and keep it awake during judging is in the "Deploy" section of [`docs/runbook.md`](docs/runbook.md).

### Tests

```
api/.venv/bin/python -m pytest api/tests analysis -q
npm --prefix web test
npm --prefix web run build
```

These are the checks CI runs on every pull request.

## Data sources

All data is recorded ahead of time and committed: no price, rate or rating is fetched live while the app runs, and the only outside calls are to Grok, for the scan and the shopping request. Each source below was retrieved on 2026-09-26, and its entry in [`api/app/data/sources.json`](api/app/data/sources.json) quotes the exact figures used.

**Electricity price** ($0.15641 per kWh; how it is built is in [`api/app/data/rates.json`](api/app/data/rates.json)):
- Georgia Power, [Residential Service Schedule R-31](https://www.georgiapower.com/content/dam/georgia-power/pdfs/tariffs/r.pdf). The rate uses the 651 to 1,000 kWh block in summer and the single winter block, weighted 4 summer months to 8 winter months. That block is a team choice, not a claim about typical household use.
- Georgia Power riders added per kWh: [Fuel Cost Recovery FCR-27](https://www.georgiapower.com/content/dam/georgia-power/pdfs/tariffs/fcr.pdf), [Environmental Compliance Cost Recovery ECCR-15](https://www.georgiapower.com/content/dam/georgia-power/pdfs/tariffs/eccr.pdf), [Demand Side Management DSM-R-16](https://www.georgiapower.com/content/dam/georgia-power/pdfs/tariffs/dsm-r.pdf).
- Recorded but not applied: [Municipal Franchise Fee MFF-11](https://www.georgiapower.com/content/dam/georgia-power/pdfs/tariffs/mff.pdf), which depends on where you live. The fixed daily basic service charge is also left out, because it does not change with use.

**Carbon** (0.383742 kg CO2e per kWh):
- U.S. EPA, [eGRID2023 Summary Tables (rev2)](https://www.epa.gov/system/files/documents/2025-06/summary_tables_rev2.xlsx), Table 1, subregion SRSO (SERC South), total output emission rate. 242 of Georgia's 250 plants are in that subregion.

**Energy use of each model:**
- U.S. EPA ENERGY STAR, [Certified Residential Refrigerators](https://data.energystar.gov/Active-Specifications/ENERGY-STAR-Certified-Residential-Refrigerators/p5st-her9) (every row of the dataset).
- U.S. Department of Energy, Weatherization Assistance Program, [Refrigerator and Freezer Energy Rating Database](https://www.energy.gov/scep/wap/articles/refrigerator-and-freezer-energy-rating-database-search-tool), 1949 to July 2021, for older models not in ENERGY STAR.
- U.S. Department of Energy, [10 CFR 430.32(a) energy conservation standards](https://www.govinfo.gov/content/pkg/CFR-2013-title10-vol3/xml/CFR-2013-title10-vol3-sec430-32.xml), the highest rated energy use allowed for a new unit, by year made, product class and adjusted volume.

**Financing:**
- Federal Reserve, [Consumer Credit G.19, Terms of Credit](https://www.federalreserve.gov/releases/g19/current/default.htm): the interest rate on credit card accounts assessed interest, 22.15% for 2026 Q2.
- NCUA, [12 CFR 701.21(c)(7)(iv), Payday alternative loans (PALs II)](https://www.ecfr.gov/current/title-12/chapter-VII/subchapter-A/part-701/section-701.21), and [NCUA Board Extends Loan Interest Rate Ceiling](https://ncua.gov/newsroom/press-release/2026/ncua-board-extends-loan-interest-rate-ceiling): together, the 28% interest cap, $20 application fee cap and $2,000 limit.
- Afterpay, [How does Afterpay work? (Pay in 4)](https://developers.afterpay.com/afterpay-button-documentation/guides/about-afterpay/how-does-afterpay-work): 4 installments every 2 weeks, the first at purchase, 0% interest when paid on time.

**Lifespan:**
- National Association of Home Builders and Bank of America Home Equity, [Study of Life Expectancy of Home Components](https://www.reservedataanalyst.com/mt-content/uploads/2019/10/national-association-of-home-builders-life-expectancies.pdf) (2007): 13 years for a standard refrigerator, on first-owner use.

**Year made, from the serial number:**
- GE Appliances, [How to Determine the Age or Manufacture Date](https://products.geappliances.com/appliance/gea-support-search-content?contentId=16195).
- [Whirlpool Date Codes](https://www.electrical-forensics.com/MajorAppliances/WhirlpoolDateCodes.html) and [Electrolux Date Codes](https://www.electrical-forensics.com/MajorAppliances/ElectroluxDateCodes.html) (Frigidaire and related brands), third-party references by Dr. Ray Franco, PE. When a year code repeats on a cycle and cannot be pinned down, the receipt says the year made may not be exact.

**New prices:**
- 14 new refrigerator listings recorded by hand from [Best Buy](https://www.bestbuy.com/), [The Home Depot](https://www.homedepot.com/) and [Lowe's](https://www.lowes.com/), each with its own product URL and the day its price was read, in [`api/app/data/retailer_cache.json`](api/app/data/retailer_cache.json). They are not a live feed. Used prices come only from the listing you enter.

**The energy burden finding** in the pitch:
- U.S. EIA, [2020 Residential Energy Consumption Survey (RECS) microdata](https://www.eia.gov/consumption/residential/data/2020/index.php?view=microdata), household-weighted with replicate-weight standard errors, for the South Census region. The analysis is in [`analysis/recs/`](analysis/recs/) and its variables are quoted from EIA in [`analysis/recs/VARIABLES.md`](analysis/recs/VARIABLES.md).

The printed demo cards (real labels, a rent-to-own page and a used listing) and where each came from are listed in [`demo/cards/README.md`](demo/cards/README.md).

## What is not estimated, and why

When there is no source for a figure, the receipt leaves it blank and labels it **Not estimated** instead of guessing. A way to get the item with a blank electricity, financing or replacement figure counts that blank as $0 in its totals, so it is marked "Some costs are not estimated" and sorted after the complete ones.

| Not estimated | Why |
|---|---|
| Extra electricity an older unit uses as it ages | No published source says how much more an aged unit draws. The old unit's electricity is its rating when new. |
| Electricity for a model with no figure | The model is not found (with a matching brand) in ENERGY STAR or DOE's historical ratings, or its matching rows disagree; no kWh was typed from its yellow label; and its year, product class and adjusted volume are not all known for the DOE standard ceiling. When the ceiling is used, it is labeled "up to, when new". |
| Repair cost, unless you enter a quote | No published repair cost range could be read from a primary source, so the repair option appears only with your own quote. |
| Upkeep | No published upkeep interval or cost was found, so none is added. |
| When a unit will need replacing, once it is at or past the low end of its typical life, or when its age is unknown | Remaining life cannot be worked out, so no replacement purchase is priced, and the cost per year of use is left blank at one or both ends. |
| A range of lifespans | The one published figure is a single number (13 years), so both ends of the range use it. |
| Buy now pay later late fees, and whether a given price is approved | Afterpay's page gives the schedule and 0% interest when paid on time; late fees are not modeled, and spending limits differ by shopper. The receipt shows the published terms, not an offer. |
| Whether anyone can get a PAL, or at what rate | The PAL figures are the federal caps (28% interest, $20 fee, up to $2,000). They are shown as "up to" and are not an offer. |
| Sales tax, delivery and installation | No source was recorded for them, so no amount is added. |
| Future changes in the electricity price | The rate is held at the current tariff for all 36 months. |
| Carbon from making, shipping or disposing of the unit | The carbon line covers only the electricity the unit uses. |
| A like-for-like comparison of ratings from before and after 2014 | DOE's refrigerator test procedure changed around then, so when the receipt compares units made on both sides of 2014 (years known), it flags the older one. |
| Anything about the shopper | The app asks no income or personal questions, so it does not say whether a shopper qualifies for any loan or assistance. |

## Where things are

| Path | What it holds |
|---|---|
| `api/app/main.py` | FastAPI routes, and the one-address serving of `web/dist` |
| `api/app/engine/` | The cost engine: cash, card, PAL, buy now pay later, rent-to-own, running cost, carbon, lifespan and ranking |
| `api/app/data/` | Sources, rates, the refrigerator profile, energy ratings and the retailer cache |
| `api/app/serial/` | Serial number decoders, by brand |
| `web/src/` | The React app: entry form, receipt and source sheet |
| `contracts/` | A sample receipt shared by the API and web tests |
| `analysis/recs/` | The RECS 2020 energy burden analysis |
| `demo/cards/` | Printable demo cards and their sources |
| `docs/` | The build spec, the runbook and the pitch |

`PLAN.md` is the living plan with each task's acceptance check, `BRIEF.md` the frozen problem statement, and `AGENTS.md` how the team branches and lands work.
