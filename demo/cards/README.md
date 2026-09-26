# Demo cards

Printable scan cards for the RealityReceipt demo. Retrieved **2026-09-26**. Every card is a real label, lease page or listing; nothing here was invented.

For each pipeline card, `cards.json` records:
- `printed`: the fields exactly as the card shows them, which is what a Grok scan returns.
- `corrections`: each change a person makes before the pipeline can use a field, with the printed value, the typed value and why.
- `typed`: the item, offer and lease a person would type.

`api/tests/test_demo_cards.py` checks that:
- `typed` equals `printed` plus `corrections` and nothing else;
- each fridge card's model returns a rated kWh figure, equal to the label's kWh where one is printed;
- the lease card's term, weekly payment and cash price match the page.

## Pipeline cards

### `label-older-maytag-mb2562.png` — old unit's EnergyGuide

- **Source URL:** https://pdf.lowes.com/energyguides/719881153483.pdf
- **What it shows:** Older-format yellow U.S. EnergyGuide for Maytag refrigerator-freezer model family `MB*2562***` (bottom-mounted freezer, automatic defrost, no through-the-door ice), capacity **25.1 cu ft**, **505 kWh/year**, similar-model range **465–594 kWh/year**, estimated yearly operating cost **$46** at the **2005** national average of 9.06¢/kWh, ENERGY STAR mark.
- **Pipeline:** typed as printed. The model family is not in the ENERGY STAR data; it resolves to **505 kWh** through DOE's historical ratings (`doe_wap_refrigerators`), the figure the label prints.

### `label-current-frigidaire-ffht1822u.png` — current EnergyGuide

- **Source URL:** https://frigidaire.bynder.com/asset/a5b8e92f-bf19-40e6-a70d-1ac4e1845e0e/FFHT1822U_EG-pdf.pdf, linked as "Energy Guide" from Frigidaire's product support page for **FFHT1822UW**: https://www.frigidaire.ca/Owner-Centre/Product-Support/FFHT1822UW (rendered from the PDF at 1563×2200).
- **What it shows:** Current U.S. EnergyGuide, Electrolux Home Products Inc., model `FFHT1822U*`, refrigerator-freezer with automatic defrost, top-mounted freezer, no through-the-door ice, capacity **17.6 cu ft**, **360 kWh** estimated yearly electricity use, estimated yearly energy cost **$50** (similar models $49–$70, all models $38–$90) at 14¢/kWh, ENERGY STAR mark.
- **Pipeline:** the model is typed as printed, `FFHT1822U*`, and the wildcard lookup finds the family in `energystar_refrigerators.csv` at **360 kWh**, the figure the label prints. One recorded correction: the label prints the maker, **Electrolux Home Products Inc.**, and nothing is found under that name. The brand is typed as **Frigidaire**: the label is linked from Frigidaire's FFHT1822UW support page, and ENERGY STAR lists the model under Frigidaire.

### `lease-aarons-frigidaire-frte1936av.png` — rent-to-own page

- **Source URL:** https://www.aarons.com/appliances/refrigerators/18.6-cu.-ft.-top-mount-refrigerator---stainless-7405BB0.html (ZIP **30309**, 52-week plan selected). Stacked from screenshots of the same page, top to bottom: the Aaron's header (the "Get instant approval" banner above it is cropped off), the brand and title, the "Model Number" row from Specifications, and the payment panel.
- **What it shows:** brand **FRIGIDAIRE**, "18.6 cu. ft. Top Mount Refrigerator - Stainless", model number **FRTE1936AV** (ENERGY STAR data: 374 kWh/year). Weekly EZPay plans **$33.48 × 52 weeks**, **$25.40 × 78 weeks**, **$19.63 × 104 weeks**; today's payment **$0.01**; 52 payments to ownership; enrollment fee **none**; ownership plan 12 months, monthly total **$144.99**; **cash price $1,196.99**; cost of lease services **$542.89**; **total cost of ownership $1,739.88**.
- **Early purchase terms:** printed in the same page's Leasing FAQs, not in the captured panel: "if you payout your merchandise within the applicable same as cash period, you will pay the cash price, plus tax and applicable fees (if any). The same as cash period varies by location but is generally 120 days. … after the same as cash option expires, you can purchase the merchandise for more than the cash price but less than the total of remaining lease payments, as described in your lease agreement. This early purchase option amount varies by state and is explained in the lease agreement." That is not a fixed rule, so the typed lease uses `early_purchase_rule: "none"`.
- **Pipeline:** typed as printed. The fees are the "Enrollment Fee: None" line, so 0. `payment_today` is the printed today's payment, **$0.01**. `total_of_payments` is the printed total cost of ownership, **$1,739.88** (12 × $144.99). The cost of lease services is not a fee; it is the difference between that total and the cash price. `also_printed` in `cards.json` keeps the other printed figures.

### `listing-used-ge-gie18gsnrss.png` — used listing

- **Source URL:** https://www.craigslist.org/view/s2qTKDEZGPr9oHGTneorn9 (Craigslist Atlanta, post id **7969927890**, by owner).
- **What it shows:** GE stainless steel top-freezer refrigerator, **$175**, condition **excellent**, model **GIE18GSNRSS**. No year is stated. Photos and map hidden before capture; no seller name appeared on the posting.
- **Pipeline:** the ENERGY STAR data lists this model as the family `GIE18GSN****`, and the wildcard lookup finds it at **443 kWh/year**. One recorded correction: condition "excellent" is typed as `used_as_is`, because the contract's conditions are new, refurbished and used_as_is.

## Other cards

### `label-pre2005-kenmore-features.jpg` — features sticker on an old Kenmore unit

- **Source URL:** https://commons.wikimedia.org/wiki/File:2022-05-04_12_31_11_Label_on_an_old_Kenmore_refrigerator-freezer_in_the_Franklin_Farm_section_of_Oak_Hill,_Fairfax_County,_Virginia.jpg (photo dated 2022-05-04; CC BY-SA 4.0, Famartin)
- **What it shows:** Kenmore features label: series **20**, **19.6 cu ft**, dimensions 30.5 × 67 × 32.5. It has no model number, so it cannot run through the pipeline; use it only as a photo of an old unit.

Removed in 3.13.1: the GE `GTE18ETH****` label (its models are not in the ENERGY STAR data), the out-of-stock Aaron's Element page (no cash price shown), and a Craigslist Frigidaire listing (no model number).

## Print

Print each PNG at letter size (or 4×6) for phone scanning. Prefer matte paper so glare does not block Grok vision.
