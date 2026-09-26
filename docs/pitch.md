# RealityReceipt: pitch script and demo run sheet

Draft for PLAN.md task 4.8. The outline follows spec §6 ("Pitch and demo") and the scenarios follow PLAN.md "Demo Script for Judges". Task 4.8 stays open until the Notability storyboard screenshot (`docs/notability/02-run-sheet.png`) exists and one timed rehearsal is done, both by hand.

## The numbers we say

These are the only statistics in the pitch. All but the last come from `analysis/recs/out/burden.csv`.

| Household income | Renters | Owners |
|---|---|---|
| $20,000-24,999 | 6.0% of income | 7.8% of income |
| $100,000-149,999 | 1.2% of income | 1.8% of income |

- **Where they come from:** EIA's 2020 Residential Energy Consumption Survey (RECS), household-weighted, for the **South Census region**. Georgia alone has too few households in 17 of its 30 income and tenure cells, so the analysis uses the South.
- **Cost** is EIA's modeled total home energy cost, so we call it **"EIA-estimated"**.
- **Income** is the **midpoint** of each bracket: $22,500 and $125,000.
- **ACEEE, Atlanta:** 10.2% energy burden for low-income households. This is **2016** data, so we always say the year with it. It is a different measure from the RECS table, so we never set the two side by side as one comparison.

## Pitch script (about 3 minutes)

Times are cues, not a stopwatch. The demo steps for beats 3 to 5 are in the run sheet below.

### 1. The finding (0:00 to 0:25)

> "In EIA's 2020 household energy survey, for the South, households earning $20,000 to $24,999 a year spent 6.0 to 7.8 percent of their income on home energy. Households earning $100,000 to $149,999 spent 1.2 to 1.8 percent. The lower figure in each pair is renters, the higher one is owners. Those costs are EIA-estimated, and income is the middle of each bracket. Closer to home, ACEEE put the low-income energy burden in Atlanta at 10.2 percent, using 2016 data."

On screen: the RECS chart (`analysis/recs/out/burden.png`). Point only at the $20k and $100k points.

### 2. Why (0:25 to 0:45)

> "The option that looks cheapest today can cost more over time: an old unit that is expensive to run, a rent-to-own lease, a purchase on high-interest credit. The price tag hides the running cost, the interest, the lease terms, and how long the thing lasts."

### 3. Demo: a label, a lease, a request (0:45 to 1:55)

> "These cards are printouts of real labels and a real listing. Watch the receipt, not the item."

Run Scenarios 1, 2 and 3 from the run sheet. Keep the camera on the receipt.

### 4. Not a wrapper (1:55 to 2:15)

> "Now I'll type the model number by hand."

Run Scenario 4. When the receipt matches:

> "Same receipt. The AI is only the keyboard. Every number after it comes from a source and a formula."

### 5. Trust (2:15 to 2:40)

Tap the running-cost line, then the aging line (Scenario 4, step 3).

> "Tap any number and you see its source and its formula. Each line says whether it is rated, published, entered by you, or not estimated. When we have no source, we leave it blank instead of guessing."

### 6. Close (2:40 to 3:00)

Scroll to a path's cost line and carbon line together.

> "What it costs you each year and what it puts in the air, on one receipt. Stores sort by sticker price. We sort by what it costs over time."

## Demo run sheet

### Before judges arrive

- [ ] Printed cards on the table: the rating label from the 2004 unit, the rent-to-own listing, the used-listing screenshot.
- [ ] The Scenario 1 brand, model and serial written on the back of its card, for Scenario 4.
- [ ] Phone mirrored to the laptop. API and web app running; the phone opens the app over the HTTPS tunnel.
- [ ] Saved images of every card ready on the phone, for the upload button fallback.
- [ ] Nothing is fetched live during the demo.
- [ ] The RECS chart open on the laptop.

### Scenario 1: the old unit (energy, trust)

| | |
|---|---|
| **Say** | "This is a rating label from a 2004 unit." |
| **Do** | Scan the printed label card. The correction form opens pre-filled. Confirm it. The receipt prints. |
| **Point at** | Each path's three numbers: pay today, total over 3 years, cost per year of use. The paths are sorted by total over 3 years. |
| **If it fails** | Tap the upload button and pick the saved image of the same card. If Grok is down, go straight to Scenario 4 and type it. |

Don't narrate what the item is; let the receipt talk.

### Scenario 2: the lease (poverty premium)

| | |
|---|---|
| **Say** | "This is a real rent-to-own listing." |
| **Do** | Scan the lease card. |
| **Point at** | The rent-to-own paths: the total of payments against the cash price, the cheapest buyout week, and the **effective annual cost**. Then the credit union loan line, marked "up to", with its caps. |
| **Say, at the loan line** | "This is the most a credit union payday alternative loan can cost under the federal caps. It doesn't mean anyone can get one." |
| **If it fails** | Upload the saved lease image, or fill in the lease fields in the correction form. |

Quote only the totals the lease on screen shows. Say "effective annual cost" for rent-to-own, every time.

### Scenario 3: used vs new, asked in plain words (Visa)

| | |
|---|---|
| **Say** | "About $300, small space, need it this week." |
| **Do** | Type the request. Grok's parsed filters appear as editable chips; fix one by hand if it misread. |
| **Point at** | The offers, ranked by cost per year. Describe the ranking the screen shows, for example a cheap used unit ranked below a new one. Then tap "View at retailer". |
| **If it fails** | Set the filter chips by hand; the ranking does not need Grok. |

This is the one moment of visible AI in the demo. Keep it about 5 seconds, then move to the engine.

### Scenario 4: not a wrapper

| | |
|---|---|
| **Say** | "Now I'll type the model number by hand." |
| **Do** | 1. Type the brand, model and serial from the back of the Scenario 1 card. 2. Show that the receipt is identical to Scenario 1. 3. For beat 5, tap the running-cost line (source, formula, "Published, up to when new"), then the aging line ("Not estimated", blank on purpose). |
| **If it fails** | Nothing to fall back to. This is the fallback for Scenarios 1 and 2, so rehearse it. |

Scenario 4 is the strongest point: it shows the AI is only the keyboard and every number has a source.

## If a judge asks

- **Why the South and not Georgia?** Georgia alone has fewer than 10 households in 17 of the 30 income and tenure cells. EIA doesn't publish cells that small, so the analysis uses the South Census region.
- **How sure are the numbers?** They are household-weighted, with standard errors from EIA's replicate weights. The 95% intervals and sample sizes are below.
- **What does "EIA-estimated" mean?** RECS models each home's energy cost from the survey. It is EIA's estimate, not a utility bill.
- **What about the top earners?** The $150,000-or-more bracket has no upper bound, so it has no midpoint, and we leave its burden not estimated.
- **Renters or owners?** In this data, owners show the higher share in every bracket. Don't go beyond that.
- **Is ACEEE's figure current?** It is from 2016. We say the year every time we use it.

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
- Say "2016" with the ACEEE figure.
- Don't quote the lowest income bracket, and don't claim renters pay a larger share.
- Energy figures come from ENERGY STAR or DOE, and rent-to-own totals from the lease itself.
- Leave out the unverified rent-to-own household count and the Georgia PSC data center topic.
- Don't center the pitch on one product: the fridge is the example, not the story.
