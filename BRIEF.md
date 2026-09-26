# Project: RealityReceipt, HackGT 13 build

## Context

RealityReceipt sorts purchase options by what they actually cost over time, not by sticker price: the price today, how it is paid for, what it costs to run and keep up, and how long it lasts, with repair, used and new options side by side. I'm building it at HackGT 13 (Georgia Tech, September 25 to 27, 2026).

- **Source of truth:** the build spec, `RealityReceipt_Build_Spec.pdf` (7 pages; not committed to this repo at seed time). Where it conflicts with older notes, the spec wins. Everything below that is not from my own answers is derived from the spec, with its section cited.
- **Team:** four people. Names and who owns what: TBD, not supplied at seed time. Until then the plan uses Track A to D placeholders. All four of us run several parallel sessions on our own machines, in a mix of editors and coding agents, Cursor among them (the SpaceXAI challenge requires Cursor). So there are four machines and many concurrent sessions, and each person's track splits into sub-tracks of its own.
- **Stage:** nothing exists. No code, no downloaded datasets, no research artifacts. This repo was initialized empty on Saturday 2026-09-26 at 01:51 EDT, with the event already underway.
- **Clock:** code freeze Sunday 2026-09-27 at 02:00 EDT; the Devpost deadline is Sunday 08:00 EDT. That is about 24 hours of build from repo init, then six hours for submission, rehearsal and sleep.
- **Entries (spec §1):** the main track is A Marina's Mission (social good, presented by Aramco Americas), and we submit to exactly one themed track. Sponsor challenges: Visa, SpaceXAI, Notability, and the Create-X interest checkbox. TigerData only if its prize is confirmed.
- **Success for this event, checkable by an outsider:** at the expo table, a printed rating label scanned on a real phone over HTTPS produces the identical receipt to typing its brand, model and serial by hand, and every number on that receipt opens to its source and formula (spec §3 "not a wrapper" test; §5 items 1 to 5).

## Source Data

Nothing is fetched live during the demo: every dataset and every retailer result is cached ahead of time (spec §3, Stack). None of the sources below had been downloaded at seed time, so no record counts or file sizes are verified yet.

| Source | Use | Status in spec §4 |
|---|---|---|
| ENERGY STAR certified datasets (data.energystar.gov) | Rated per-model energy | STATED |
| DOE Compliance Certification Database | Rated energy fallback | STATED |
| DOE efficiency standards by year | Estimated energy ceiling for old units | STATED; on the verify list |
| Georgia Power residential tariff sheet | Marginal electricity rate | To pull |
| EPA eGRID, Georgia subregion | Carbon per kWh | STATED |
| Federal Reserve G.19 | Average credit card rate | STATED |
| NCUA PALs II rule | PAL caps | STATED |
| EIA RECS 2020 microdata (CSV, about 18,500 households weighted to 123.5M homes) | Opening finding | Codebook column names to pull |
| Best Buy Products API | New prices, cached | Key requested; may not arrive in time |
| User-supplied listings, price tags, leases | Used prices, rent-to-own terms | No scraping |
| EIA monthly Georgia residential prices | Rate projection | TigerData only; conditional |

User inputs (spec §2): a photo or upload of a rating label, price tag, lease or listing screenshot, or a model number typed by hand, plus an optional "I can spend up to $___ today" amount. No sign-up, no income or personal questions.

### Domain landmines

- Every cost line carries exactly one source label: Rated, Published, You entered, or Not estimated (§2). "Not estimated" is left visibly blank; it is never filled by AI or guessed.
- Estimated figures are ranges, never single points (§2). Repairs are labeled ranges, with no invented failure probabilities (§3).
- The carbon line appears only when the item uses energy or fuel, and is hidden otherwise (§2).
- If no published lifespan exists, cost per year of use shows "not estimated" and the receipt falls back to the 3-year total (§2).
- Total over 3 years includes a replacement purchase when expected life ends inside the 36-month window (§2, §3).
- Rent-to-own shows "effective annual cost". Never label it APR, in the UI or on stage (§3, §6). Prefer the scanned lease's own total of payments vs cash price over any generic multiple.
- PAL is shown as an option with its NCUA PALs II caps: up to $2,000, 1 to 12 months, interest capped at 28%, application fee capped at $20. Never imply the user can get one; eligibility depends on credit union membership (§3, §7).
- Never say a user qualifies for any assistance or loan (§6).
- No absolute claims such as "the cheapest option is always the most expensive". Say "can be", or claim only what the receipt on screen shows (§6).
- No em dashes in any user-facing copy (spec, "How to use this document").
- Used prices come only from the listing the user scans or uploads. No scraping, no invented "market average" (§2).
- New prices come from cached retailer data, with source and retrieval date shown (§2).
- Checkout links out to the retailer. Never fake a payment (§1, Visa).
- Electricity uses Georgia Power's residential marginal rate from the tariff sheet, not the blended average, including per-kWh riders, with the tier and season assumption documented (§3). Which tier, season and riders apply is unverified (§7).
- Carbon uses the EPA eGRID rate for Georgia's subregion and records which rate type is used. Non-baseload may be more defensible than total output for avoided use (§3, §7).
- The DOE standard in force in a unit's manufacture year is a ceiling on its rated energy when new; aged units may draw more. Refrigerator test procedures may have changed around 2014, so old and new ratings may not be directly comparable (§7).
- Water heating dominates some appliances' energy, and gas vs electric changes the result: either ask one question or show both lines (§7).
- Weather-driven items (cooling) need a documented usage-hours assumption, labeled estimated (§7).
- Serial date codes are set by manufacturer, not product type. Some brands' year codes repeat on a cycle: resolve from model era, or set year_confidence low and flag it (§3).
- Vision output must validate against a strict Pydantic schema. On failure, show the manual correction form pre-filled with whatever parsed (§3).
- Grok vision must be the primary path in the demo. If the OCR fallback carries the demo, SpaceXAI eligibility is weak (§1).
- Phone cameras need HTTPS: deploy, or tunnel with cloudflared. Test on a real phone early (§3).
- RECS: use household weights, compute standard errors with the replicate weights, report sample size per cell, and label modeled consumption "EIA-estimated". Use Georgia if cell sizes hold up, otherwise the South region, and say which on the slide (§4).
- The 10.2% Atlanta low-income energy burden figure (ACEEE) is 2016 data: say so, or use a newer figure if one exists (§6).
- Drop the "HL Hunt Research Desk" figure (4.63M rent-to-own households): it is unverified (§6).
- Cite energy figures to ENERGY STAR or DOE directly, and rent-to-own totals to the actual lease (§6).

## Architecture Decision: AI turns input into typed data and a deterministic engine does all the math, NOT an AI that estimates costs

The product's claim is that every number on the receipt traces to a source and a formula (§2, trust layer). A model that estimates or adjusts costs cannot meet that: its numbers carry no source label and cannot be unit-tested. So Grok sits only at the edges (§1, §3):

- **Vision extraction** (`POST /scan`) reads a label, price tag, lease or listing screenshot into strict JSON. OpenCV cleanup plus PaddleOCR is the fallback, a safety net only.
- **Request parsing** (`POST /shop/parse`) turns "about $300, small space, need it this week" into filters.
- **Read-aloud** (Grok Voice) reads the finished receipt in English and Spanish.

Everything between those edges is deterministic and unit-tested: validation, manual correction, serial decode, category profile lookup, the 36-month cost engine, ranking. The proof is the "not a wrapper" test: typing brand, model and serial by hand gives the identical receipt to scanning. The AI is the keyboard.

A second decision with the same shape: **a category is a data profile, NOT code** (§2). The engine never branches on category. Running cost, upkeep, repairs, lifespan and end of life all come from the profile, so adding a category means adding data. Serial decoders are keyed by brand, not category, and reused across categories (§3).

Pipeline (§3):

```
photo -> vision extract (strict JSON) -> validate + manual correction -> serial decode ->
category profile lookup -> cost engine (36 months) -> receipt
```

## Data model, API and stack proposal

The receipt (§2): paths sorted by true cost, each with three headline numbers.

| Path | Notes |
|---|---|
| 1. Repair the one you have | Repair cost as a labeled range |
| 2. Used, as-is | Price from the user's listing; condition unknown, so ranges stay wide |
| 3. Used, refurbished | Warranty term shown; narrows the range |
| 4. New | Sub-paths: cash, credit card, buy now pay later, credit union PAL |
| 5. Rent-to-own | Keep paying to the end, or the cheapest early buyout point |

| Headline number | Definition |
|---|---|
| Pay today | Cash out of pocket now for that path |
| Total over 3 years | All costs in the 36-month window, including a replacement purchase if the item wears out inside it |
| Cost per year of use | Total cost divided by expected years of life (a range); "not estimated" when no published lifespan exists |

Data model (§3):

```
Item: id, category, brand, model, serial, mfg_year, year_confidence, condition
  (new|used_as_is|refurbished), warranty_months, attributes{}
Offer: item_id, price, seller_type, source (retailer_cache|user_listing|price_tag), retrieved_at
Lease: weekly_payment, term_weeks, cash_price, fees, early_purchase_rule, missed_payment_rule
CostLine: kind (purchase|financing|running|upkeep|repair|replacement|end_of_life), label,
  amount_low, amount_high, period, source_type (rated|published|user_entered|not_estimated),
  source_id, formula
Path: name, payment_method, pay_today, total_3yr_low, total_3yr_high, cost_per_year_low,
  cost_per_year_high, expected_life_low, expected_life_high, monthly[36], carbon_kg (nullable),
  lines[CostLine], flags[]
CategoryProfile: category, energy_dataset_refs, usage_assumption, upkeep_schedule[],
  repair_ranges[], lifespan_range, carbon_applicable
Source: id, title, publisher, url, retrieved_date, notes
```

API (§3):

```
POST /scan        {kind: label|price_tag|lease|listing, image} -> extracted JSON
POST /item        manual or corrected item -> Item
POST /quote       {item_id | items[], budget_today?, usage_adjust?} -> Path[]
POST /shop/parse  natural-language request -> filters (Grok)
POST /shop/rank   filters + candidate offers -> offers ranked by true cost
GET  /categories  available category profiles
GET  /sources     all sources with id, publisher, url, retrieved date
```

Category profile contents (§3): a running-cost model (rated energy from the ENERGY STAR dataset first, then the DOE Compliance Certification Database; the federal label's standard usage assumption; an optional usage-adjust slider, never required), estimated energy for old units (decoded manufacture year, then the DOE standard in force that year, shown as a range), a published-only upkeep schedule, repair cost ranges, a lifespan range and end-of-life notes. Any field without a source is stored as `not_estimated`.

Cost engine rules (§3): Georgia Power marginal rate; eGRID Georgia subregion carbon; Federal Reserve G.19 card rate; NCUA PALs II caps; rent-to-own as the full payment stream, the cheapest early buyout week and an effective annual cost; repairs as labeled ranges; a 36-month monthly cash flow per path, with a replacement purchase inserted if expected life ends inside the window.

Stack (§3):

- Frontend: React + Vite PWA, getUserMedia camera, Tailwind, Framer Motion receipt animation.
- Backend: FastAPI + Pydantic. SQLite preloaded with all datasets (TigerData Postgres only if that prize is confirmed). pytest on the engine.
- AI: Grok vision primary; OpenCV cleanup + PaddleOCR fallback. Grok Voice for read-aloud (English, Spanish).
- HTTPS for phone cameras via deploy or a cloudflared tunnel.

The directory layout is not specified yet; the plan's file ownership table sets it.

## What I want you to help me with FIRST (planning stage, don't write code yet)

1. **Validate the architecture.** What would you change and why? Where am I overengineering for a 24-hour build with four people? What will I regret by Saturday night?
2. **Sanity-check the riskiest component.** The spec itself flags the phone scan path: a real phone over HTTPS, Grok vision reading a printed label, and the result matching manual entry exactly (§3 "Test on a real phone early"; §1 "Grok vision must be the primary path"). How would you build and test it?
3. **Suggest the build order.** My current order is the spec's §5 priority list: (1) cost engine, Pydantic models and pytest; (2) one sourced category profile plus manual entry; (3) lease path; (4) receipt UI with tap-to-source; (5) Grok vision scan on a real phone; (6) RECS finding; (7) used vs new ranking and Grok request parsing; (8) Grok Voice read-aloud in English and Spanish; (9) a second category profile, only if 1 to 8 are solid. It has no hour estimates yet and is written as one sequence, not as four parallel tracks. Push back if the order is wrong.
4. **Don't write code yet.** I want the plan, the risks, and the open questions before implementation starts. Give me your honest assessment, including what you think won't work or where I'm being naive.

## Constraints

- Four people. Code freeze Sunday 2026-09-27 02:00 EDT; Devpost deadline 08:00 EDT. Nothing was built as of Saturday 01:51 EDT.
- Only the first step uses AI; everything after extraction is deterministic and unit-tested. This is non-negotiable (spec, "How to use this document").
- The "not a wrapper" test must pass: typed entry and scan give the identical receipt (§3).
- Nothing is fetched live during the demo (§3).
- No scraping. No sign-up. No income or personal questions (§2).
- The stage accuracy rules in spec §6 are non-negotiable; they are listed in Domain landmines above.
- Submit to exactly one themed track (§1).
- SpaceXAI: build in Cursor with Grok, and Grok vision is the primary demo path (§1).
- Notability: use Notability Pro during the event for architecture sketches, the pitch storyboard and the demo run sheet; capture at least two screenshots; tag the Devpost "Notability" and add a note on how it was used (§1).
- Visa: lead the write-up with the generative AI shopping flow and the used vs new ranking, and make the AI shopping step visible in the demo (§1). Aim for about 5 seconds of visible AI to 85 of engine otherwise (§6).

## What's intentionally out of scope

- The ideas already rejected; do not re-suggest them (§9): SONAR (NSA audio detector), hospital price transparency, prior-auth prediction, agentic-commerce price integrity, dark-pattern detection, dark-vessel AIS gaps, lead service line prediction, GreenGate prompt router. The international internship eligibility idea lives in a separate project.
- Skipped sponsor challenges (§1): Meta, Impiricus, NSA C1 HEARSAY, NSA C3 Codebreaker. NSA C2 Packet Pursuit is an optional side effort unrelated to this build.
- TigerData work, unless its prize is confirmed (§1). If it is: scans stored as time series, EIA monthly Georgia prices projected forward, TigerData Postgres behind the same repository interface as SQLite.
- A second category profile, unless build items 1 to 8 are solid (§5).
- Scraping used-market prices, or any invented market average (§2).
- Real payments or an in-app checkout (§1).
- Accounts, sign-up, income or personal questions (§2).
- Failure-probability modeling for repairs (§3).
- Live data fetches during the demo (§3).
- A pitch centered on a specific product (§2), and the Georgia PSC data center topic (§6).

## Open questions I haven't resolved

- **Team names and ownership:** TBD, not supplied at seed time.
- **Cursor and SpaceXAI:** teammates build in Cursor, but not every track is built there. Does "build with Cursor" hold if part of the code is built outside it? Organizers verify sponsor eligibility (§1). Want your take.
- **Which category is the first profile?** The spec says the demo uses a category with a federal energy label (§2) and raises refrigerators, water heating and cooling as verify items (§7), but it does not name one.
- **Grok API access:** the spec says SpaceXAI gives credits to all (§1), but not whether we have a working key yet.
- **Best Buy API key:** status unknown; otherwise a hand-built cache of real listings with URLs and dates (§8).
- **TigerData:** whether the prize exists (§8).
- **Verify list, spec §7, all open at seed time:** the DOE standard as a ceiling and the ~2014 refrigerator test procedure change; Georgia Power tier, season and riders; eGRID rate type; gas vs electric water heating; cooling usage hours; RECS 2020 variable names, income variable, replicate weights and Georgia cell sizes; whether any Georgia regulator publishes rent-to-own multiples; PAL eligibility and credit union membership; whether a newer ACEEE Atlanta energy burden figure exists.
- **Open items, spec §8:** find real rating-label images for the demo and print them; pull the Georgia Power residential tariff sheet and the RECS 2020 codebook; start Notability usage and screenshots.

Start with item (1) above: validate the architecture. Then (2), (3), (4) in order. Be direct, push back where I'm wrong, and don't be sycophantic.
