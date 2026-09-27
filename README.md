# RealityReceipt

**A cheap fridge can be expensive to own.** RealityReceipt helps low-income households compare purchase, financing, energy, and repair costs to see what they can afford today and over time.

[![ci](https://github.com/AaravChadha/realityreceipt/actions/workflows/ci.yml/badge.svg)](https://github.com/AaravChadha/realityreceipt/actions/workflows/ci.yml)

Built at HackGT 13 (Georgia Tech, September 25 to 27, 2026) for the Oracle of the Deep (ML/AI) track and the Aramco (A Marina's Mission) and SpaceXAI challenges.

**Who this is for:** someone deciding how to get a refrigerator on a tight budget: keep or repair the one they have, buy used, buy new with cash, a credit card, buy now pay later or a credit union loan, or rent-to-own. And anyone who wants to check the math behind each option, because every number links to its source.

**Who it is not for, yet:** anyone shopping for something other than a fridge (cars are next, see [Scope](#scope-refrigerators-today-cars-next)), or anyone looking for a loan offer. The app asks nothing about income and never says whether a shopper qualifies for anything.

[See it work](#see-it-work) · [What it does](#what-it-does) · [Run it](#run-it) · [Data sources](#data-sources) · [What is not estimated](#what-is-not-estimated-and-why) · [Team](#team)

## See it work

A real rent-to-own page from Aaron's (one of the printed cards in [`demo/cards/`](demo/cards/README.md)) offers a Frigidaire FRTE1936AV for $0.01 today. With the app running ([Run it](#run-it)), send the lease's printed numbers:

```
curl -s http://localhost:8000/api/quote -H 'content-type: application/json' -d @- <<'EOF' | jq -r '.[] | [.name, .pay_today, .total_3yr_high] | @tsv'
{"items": [{"id": "lease", "category": "refrigerator", "brand": "Frigidaire", "model": "FRTE1936AV", "condition": "new"}],
 "offers": [{"item_id": "lease", "price": 1196.99, "seller_type": "rent_to_own", "source": "user_listing", "source_id": "user_listing"}],
 "lease": {"weekly_payment": 33.48, "term_weeks": 52, "cash_price": 1196.99, "payment_today": 0.01, "total_of_payments": 1739.88}}
EOF
```

What came back on 2026-09-27 (each way to get the fridge, what it costs today, and its 3-year total including electricity):

```
New, buy now pay later	175.0	875.31
New, pay cash	699.99	875.31
New, credit card	0.0	962.16
New, credit union PAL	20.0	1005.92
Rent-to-own, keep paying	0.01	1915.2
```

The new options are the same model: the app matched the leased fridge to a store listing of its own model number, new at Best Buy for $699.99. The lease sorts last because it costs the most over 3 years. Its first line shows exactly where its numbers come from:

```
$0.01 today and $1,739.88 in all over 52 weeks, as printed on your lease; the remaining $1,739.87 is spread evenly over 51 weekly payments of about $34.11. Total of payments = $1,739.88. That is $542.89 more than the cash price of $1,196.99. No early purchase terms entered. Effective annual cost = ((1739.88 - 1196.99) / 1196.99) / (52 / 52) = 45%.
```

In the app, the same receipt appears as cards, and tapping any line opens its source and formula.

## What it does

1. You enter the fridge you have, a used one you found, or a lease: typed, or read from a photo of a rating label, a lease page or a listing screenshot. There is no sign-up and no question about income or anything personal.
2. The receipt lays out every way to get the item side by side: keep the one you have, repair it (when you enter a repair quote), used or refurbished (from a listing you enter), new paid four ways (cash, credit card, buy now pay later, credit union PAL), and rent-to-own (when you enter a lease). The new fridge is the store listing most like yours: the same model family, then the same type, then the closest size. Its line says which.
3. Each way shows three numbers: what you pay today, the total over 3 years, and the cost per year of use. Totals are ranges, low to high. Complete ways come first, cheapest 3-year total first; a way with a cost not estimated comes after them and says so. If you say how much you can spend today, the ways that cost more today are dimmed, not hidden.
4. Tap any cost line to see its source, the formula, and whether the figure is **Rated**, **Published**, **You entered** or **Not estimated**. A carbon line (kg CO2e over 3 years) sits beside the cost.
5. A shopping page takes a plain-words request ("About $300, small space, need it this week"), shows the filters it read as editable chips, and ranks store listings by cost per year, not by price. Each links to the store; nothing is bought in the app.

**How the numbers are made.** AI only reads input: Grok turns a photo into typed fields and a shopping request into filters. It does not produce or change any number on the receipt. The numbers come from a deterministic engine in [`api/app/engine/`](api/app/engine/) and the committed data in [`api/app/data/`](api/app/data/). The proof is [`api/tests/test_not_a_wrapper.py`](api/tests/test_not_a_wrapper.py): scanning each demo card gives the identical receipt to typing it by hand. Everything also works without the AI: typed entry needs no API key, and a scan that cannot be read falls back to the form.

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

There is no hosted deployment: the demo runs on a laptop, with phones reaching it over the tunnel. [`render.yaml`](render.yaml) and the "Deploy" section of the runbook are kept for later.

### Tests

```
api/.venv/bin/python -m pytest api/tests analysis -q
npm --prefix web test
npm --prefix web run build
```

These are the checks CI runs on every pull request.

## Data sources

All data is recorded ahead of time and committed: no price, rate or rating is fetched live while the app runs, and the only outside calls are to Grok, for the scan and the shopping request. Each source below was retrieved on 2026-09-26 (three store prices on 2026-09-27), and its entry in [`api/app/data/sources.json`](api/app/data/sources.json) quotes the exact figures used.

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
- 17 new refrigerator listings in [`api/app/data/retailer_cache.json`](api/app/data/retailer_cache.json), each with its own product URL and the day its price was read: 14 recorded by hand from [Best Buy](https://www.bestbuy.com/), [The Home Depot](https://www.homedepot.com/) and [Lowe's](https://www.lowes.com/), and 3 Best Buy prices as Google Shopping showed them on 2026-09-27 (a side-by-side, a French door, and the lease card's own model), because Best Buy's pages block scripts. They are not a live feed. Used prices come only from the listing you enter.

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
| A like-for-like comparison of ratings from before and after 2014 | DOE's refrigerator test procedure changed around then, so when the receipt compares a unit that could have been made before 2014 with a newer one, it flags the older one. |
| Anything about the shopper | The app asks no income or personal questions, so it does not say whether a shopper qualifies for any loan or assistance. |

## Where things are

- [`api/app/main.py`](api/app/main.py): the FastAPI routes, and serving the built web app at the same address.
- [`api/app/engine/`](api/app/engine/): the cost engine (cash, card, PAL, buy now pay later, rent-to-own, running cost, carbon, lifespan, matching and ranking).
- [`api/app/grok/`](api/app/grok/): the Grok client, the scan and the shopping-request parser, with every reply checked before use.
- [`api/app/data/`](api/app/data/): sources, rates, the refrigerator profile, energy ratings and the retailer cache.
- [`api/app/serial/`](api/app/serial/): serial number decoders, by brand.
- [`web/src/`](web/src/): the React app (entry and scan, receipt, source sheet, shopping page).
- [`contracts/`](contracts/): a sample receipt shared by the API and web tests.
- [`analysis/recs/`](analysis/recs/): the RECS 2020 energy burden analysis and its chart.
- [`demo/cards/`](demo/cards/README.md): the printable demo cards and where each came from.
- [`docs/`](docs/): the build spec, the runbook and the pitch.

[`PLAN.md`](PLAN.md) is the living plan with each task's acceptance check, [`BRIEF.md`](BRIEF.md) the frozen problem statement, and [`AGENTS.md`](AGENTS.md) how the team branched and landed work.

## Team

- Aarav Chadha ([@AaravChadha](https://github.com/AaravChadha))
- Neil ([@sachdevneil35-web](https://github.com/sachdevneil35-web))
- Krish Agrawal ([@KrishAgrawal595](https://github.com/KrishAgrawal595))
- Adhyayan Agarwal ([@adhyayancs50](https://github.com/adhyayancs50))
