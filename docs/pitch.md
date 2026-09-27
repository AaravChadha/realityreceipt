# RealityReceipt: pitch script and demo run sheet

Draft for PLAN.md task 4.8. The outline follows spec §6 ("Pitch and demo") and the scenarios follow PLAN.md "Demo Script for Judges". Task 4.8 stays open until the Notability storyboard screenshot (`docs/notability/02-run-sheet.png`) exists and one timed rehearsal is done, both by hand.

## The numbers we say

These are the only statistics in the pitch. The income figures come from `analysis/recs/out/burden.csv`, except ACEEE's. The lease and receipt figures come from PLAN.md "Demo Script for Judges".

| Household income | Renters | Owners |
|---|---|---|
| $20,000-24,999 | 6.0% of income | 7.8% of income |
| $100,000-149,999 | 1.2% of income | 1.8% of income |

- **Where they come from:** EIA's 2020 Residential Energy Consumption Survey (RECS), household-weighted, for the **South Census region**. Georgia alone has too few households in 17 of its 30 income and tenure cells, so the analysis uses the South.
- **Cost** is EIA's modeled total home energy cost, so we call it **"EIA-estimated"**.
- **Income** is the **midpoint** of each bracket: $22,500 and $125,000.
- **ACEEE, Atlanta:** 10.2% energy burden for low-income households. It comes from **ACEEE's 2016 report**, so we always name the report and its year with it. It is a different measure from the RECS table, so we never set the two side by side as one comparison.
- **The lease (Scenario 1):** **$0.01** today, **$1,739.88** in total as printed on the lease, **$542.89** more than its own **$1,196.99** cash price, and an effective annual cost of **45%**. Quote the total as the page prints it. Never work it out from the weekly payment: that gives a different figure.

## Pitch script (about 3 minutes)

Times are cues, not a stopwatch. The demo steps for beats 1, 4, 5 and 6 are in the run sheet below.

### 1. The lease (0:00 to 0:40)

Run Scenario 1. Open on the card, then on the receipt it produces.

> "This is a real rent-to-own page for a fridge, printed out."

When the receipt prints:

> "One cent today. $1,739.88 in total, as printed on the lease: $542.89 more than its own cash price, an effective annual cost of 45 percent. Beside it, a new fridge from a store listing, and a credit union loan line, marked 'up to'."

### 2. The finding (0:40 to 1:00)

> "In EIA's 2020 household energy survey, for the South, households earning $20,000 to $24,999 a year had home energy costs equal to 6.0 to 7.8 percent of their income (EIA-estimated). Households earning $100,000 to $149,999 had home energy costs equal to 1.2 to 1.8 percent of their income. The lower figure in each pair is renters, the higher one is owners. Income is the middle of each bracket. Closer to home, ACEEE's 2016 report put the low-income energy burden in Atlanta at 10.2 percent."

On screen: the RECS chart (`analysis/recs/out/burden.png`), cropped so the under-$5,000 bracket does not show. Point only at the $20k and $100k points.

### 3. Why (1:00 to 1:10)

> "The option that looks cheapest today can cost more over time: an old unit that is expensive to run, a rent-to-own lease, a purchase on high-interest credit. The price tag hides the running cost, the interest, the lease terms, and how long the thing lasts."

### 4. Every line has a source (1:10 to 1:50)

Run Scenario 2. While tapping:

> "Tap any line and you see its source and its formula. Each line says whether it is rated, published, entered by you, or not estimated. When we have no source, we leave it blank instead of guessing."

### 5. Used vs new, in plain words (1:50 to 2:15)

Run Scenario 3, only if it passed its 23:30 check. If not, give its time to beat 4.

### 6. Not a wrapper (2:15 to 2:40)

Run Scenario 4, only if it passed its 22:00 check. If not, give its time to beat 4. When the two receipts match:

> "Same receipt. The AI is only the keyboard. Every number after it comes from a source and a formula."

### 7. Close (2:40 to 3:00)

Scroll to a path's cost line and carbon line together.

> "What it costs you each year and what it puts in the air, on one receipt. Stores sort by sticker price. We sort by what it costs over time."

## Demo run sheet

### Before judges arrive

- [ ] Printed cards on the table: the Aaron's rent-to-own page (`lease-aarons-frigidaire-frte1936av.png`), the older Maytag EnergyGuide label (`label-older-maytag-mb2562.png`), the used GE listing (`listing-used-ge-gie18gsnrss.png`) and the current Frigidaire EnergyGuide label (`label-current-frigidaire-ffht1822u.png`).
- [ ] The lease form (task 3.10) is on `main`. Without it, Scenario 1 depends on a working scan of the lease card.
- [ ] At 22:00: keep Scenario 4 only if a real scan works. At 23:30: keep Scenario 3 only if the shop (tasks 4.1, 4.3 and 4.4) is on `main`.
- [ ] A repair quote amount ready for Scenario 2, for example $180.
- [ ] Phone mirrored to the laptop. API and web app running; the phone opens the app over the HTTPS tunnel.
- [ ] Saved images of every card ready on the phone, for the upload button fallback.
- [ ] Nothing is fetched live during the demo.
- [ ] The RECS chart open on the laptop, with the under-$5,000 bracket cropped out.

### Scenario 1: the lease (the poverty premium). Lead with this.

| | |
|---|---|
| **Say** | "This is a real rent-to-own page for a fridge, printed out." |
| **Do** | Enter the lease: scan the card, or fill in the lease form. The card prints 52 weekly payments of $33.48, a cash price of $1,196.99, $0.01 paid today, and a total of payments of $1,739.88. Enter the total as printed. |
| **Point at** | "Rent-to-own, keep paying": **$0.01 today** and **$1,739.88 in total, as printed on the lease: $542.89 more than its own cash price, an effective annual cost of 45%.** Beside it, new fridges from store listings, and the credit union loan line, marked "up to", with its caps. |
| **Say, at the new fridges** | "A new fridge", never "the same fridge": the cheapest listing, $548 at Home Depot, is a different, smaller Frigidaire. |
| **Say, at the loan line** | "This is the most a credit union payday alternative loan can cost under the federal caps. It doesn't mean anyone can get one." |
| **If it fails** | Upload the saved lease image, or fill in the lease form by hand. |

Quote only the totals the lease on screen shows. Say "effective annual cost" for rent-to-own, every time. Don't name a week to buy the lease out early, and don't say "120 days": the card supports neither number.

Scenario 1 is the strongest point: its numbers come straight off a real lease page and need no explanation.

### Scenario 2: every line has a source (the trust layer)

| | |
|---|---|
| **Say** | "This is the label from an older Maytag." |
| **Do** | Enter it as "Your fridge now", with a repair quote (for example $180). With no quote there are no repair ranges, so there is no repair path. |
| **Point at** | The paths: complete ones come first, cheapest 3-year total first, and a path with a cost not estimated comes after them and says so. Then tap the electricity line: **Rated, 505 kWh a year, from DOE's historical refrigerator ratings**, times the Georgia Power rate; tap through to both sources. Then tap the replacement line: "not estimated", left blank on purpose, because the unit is past its typical life. |
| **If it fails** | Check the brand and model on the form against the label, character by character, and quote again. |

Don't state a year: the label prints none. Don't claim big energy savings: against a new fridge the gap is about $20 a year.

### Scenario 3: used vs new, asked in plain words (Visa)

Only if the shop (tasks 4.1, 4.3 and 4.4) is on `main` by 23:30.

| | |
|---|---|
| **Say** | "About $300, small space, need it this week." |
| **Do** | Type the request. Grok's parsed filters appear as editable chips; fix one by hand if it misread. Include the used GE listing ($175): ask its age and enter it, since the listing states none. |
| **Point at** | The offers, ranked by cost per year, with unknown delivery or width flagged, not hidden. Describe the ranking the screen shows. Then tap "View at retailer". |
| **If it fails** | Set the filter chips by hand; the ranking does not need Grok. |

Before going on stage, check these numbers: at some prices and years a used and a new option land on the same cost per year, which looks like a bug.

Visible AI in the demo adds up to about 20 seconds: the scans (the lease in Scenario 1, if scanned, and the label in Scenario 4) and these filter chips. Keep each part short, then move to the engine.

### Scenario 4: not a wrapper

Only if a real scan works by 22:00.

| | |
|---|---|
| **Say** | "The AI only reads the label. Watch me type the same thing by hand." |
| **Do** | 1. Scan the current Frigidaire label. It prints the brand as "Electrolux Home Products Inc.": correct it to Frigidaire in the form, unless the brand alias has landed. 2. Type Frigidaire and `FFHT1822U*` by hand. 3. Show that the two receipts are identical: rated, 360 kWh. |
| **If it fails** | Skip it. Scenarios 1 to 3 do not need a scan. |

## If a judge asks

- **Why the South and not Georgia?** Georgia alone has fewer than 10 households in 17 of the 30 income and tenure cells. EIA doesn't publish cells that small, so the analysis uses the South Census region.
- **How sure are the numbers?** They are household-weighted, with standard errors from EIA's replicate weights. The 95% intervals and sample sizes are below.
- **What does "EIA-estimated" mean?** RECS models each home's energy cost from the survey. It is EIA's estimate, not a utility bill.
- **What about the top earners?** The $150,000-or-more bracket has no upper bound, so it has no midpoint, and we leave its burden not estimated.
- **Renters or owners?** In this data, owners show the higher share in every bracket. Don't go beyond that.
- **Is ACEEE's figure current?** It comes from ACEEE's 2016 report. We name the report and its year every time we use it.
- **Where does the lease total come from?** The lease page prints its own total, and the receipt uses the lease's printed numbers.

| Household income | Tenure | Share of income | 95% interval | Households surveyed |
|---|---|---|---|---|
| $20,000-24,999 | Renters | 6.0% | 5.5% to 6.6% | 121 |
| $20,000-24,999 | Owners | 7.8% | 7.3% to 8.3% | 197 |
| $100,000-149,999 | Renters | 1.2% | 1.0% to 1.4% | 106 |
| $100,000-149,999 | Owners | 1.8% | 1.7% to 1.8% | 727 |

## Wording check before going on stage

- For rent-to-own, say "effective annual cost". Use no other rate term.
- Never say or suggest that anyone can get a loan or assistance. The credit union loan line is a ceiling, labeled "up to".
- No absolute claims. Say "can", or claim only what the receipt on screen shows.
- Say "ACEEE's 2016 report" with the ACEEE figure.
- Don't quote the lowest income bracket, and don't claim renters pay a larger share.
- Don't say a refurbished warranty narrows the range, or that any category other than fridges works today.
- Say the cards are printouts of real labels and pages. Say "tap any line".
- No year for the Maytag, and no "2004".
- Quote the lease total as printed. Don't name a week to buy it out early, and don't say "120 days".
- Say "a new fridge" about the store listing, never "the same fridge".
- Energy figures come from ENERGY STAR or DOE, and rent-to-own totals from the lease itself.
- Leave out the unverified rent-to-own household count and the Georgia PSC data center topic.
- Don't center the pitch on one product: the fridge is the example, not the story.
