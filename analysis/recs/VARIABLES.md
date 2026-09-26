# RECS 2020: variables and variance method used by `burden.py`

Every name, label and formula below is quoted from an EIA document, checked on 2026-09-26 against the files listed here. Nothing is from memory. Page numbers are the ones printed on the pages.

## Sources

| What | URL |
|---|---|
| Microdata page (lists the files; "v7", released January 2024) | https://www.eia.gov/consumption/residential/data/2020/index.php?view=microdata |
| Microdata CSV, v7 (not committed; 18,496 rows, 799 columns, SHA-256 `8d5f6d3120d2cbc2535151c7d455e7a536ca9768f773e15edd45932ec38b3592`) | https://www.eia.gov/consumption/residential/data/2020/csv/recs2020_public_v7.csv |
| Codebook, v7 | https://www.eia.gov/consumption/residential/data/2020/xls/RECS%202020%20Codebook%20for%20Public%20File%20-%20v7.xlsx |
| Microdata guide: "Using the microdata file to compute estimates and relative standard errors (RSEs)", published June 2022, revised June 2023 | https://www.eia.gov/consumption/residential/data/2020/pdf/microdata-guide.pdf |
| Household Characteristics Technical Documentation Summary (linked from the methodology page, https://www.eia.gov/consumption/residential/data/2020/index.php?view=methodology) | https://www.eia.gov/consumption/residential/data/2020/pdf/2020%20RECS_Methodology%20Report.pdf |

Run it with the downloaded CSV's path:

```
api/.venv/bin/python analysis/recs/burden.py /path/to/recs2020_public_v7.csv
```

## Variables

Rows quoted from the codebook's `codebook` sheet (columns: Variable | Type | Description and Labels | Response Codes | Section).

| Role | Codebook row |
|---|---|
| Income | `MONEYPY` \| Num \| Annual gross household income for the past year \| 1 Less than $5,000 2 $5,000 - $7,499 3 $7,500 - $9,999 4 $10,000 - $12,499 5 $12,500 - $14,999 6 $15,000 - $19,999 7 $20,000 - $24,999 8 $25,000 - $29,999 9 $30,000 - $34,999 10 $35,000 - $39,999 11 $40,000 - $49,999 12 $50,000 - $59,999 13 $60,000 - $74,999 14 $75,000 - $99,999 15 $100,000 - $149,999 16 $150,000 or more \| HOUSEHOLD CHARACTERISTICS |
| Renter status | `KOWNRENT` \| Num \| Own or rent \| 1 Own 2 Rent 3 Occupy without payment of rent \| YOUR HOME |
| Total energy cost | `TOTALDOL` \| Num \| Total cost including electricity, natural gas, propane, and fuel oil, in dollars, 2020 \| -150.51-20043.41 \| End-use Model |
| Household weight | `NWEIGHT` \| Num \| Final Analysis Weight \| 437.9-29279.1 \| WEIGHTS |
| Replicate weights | `NWEIGHT1` \| Num \| Final Analysis Weight for replicate 1 \| 0-30015.5 \| WEIGHTS, through `NWEIGHT60` \| Num \| Final Analysis Weight for replicate 60 \| 0-29818.2 \| WEIGHTS |
| State | `state_postal` \| Char \| State Postal Code \| state_dictionary!A1 \| GEOGRAPHY; the `state_dictionary` sheet has `13 \| GA \| Georgia` |
| Region | `REGIONC` \| Char \| Census Region \| Midwest Northeast South West \| GEOGRAPHY |

The CSV spells `REGIONC` in upper case, unlike the codebook: `SOUTH` (6,426 rows), `WEST` (4,581), `MIDWEST` (3,832), `NORTHEAST` (3,657). The script matches `SOUTH`.

The script uses the imputed values of `MONEYPY` and `KOWNRENT`, as the microdata guide advises (p. 13): "We recommend using the imputed data, where available, to avoid biased estimation." The flags are `ZMONEYPY` \| Num \| Imputation indicator for MONEYPY \| 1 Imputed 0 Not imputed, and `ZKOWNRENT` likewise. `MONEYPY` is imputed for 8.3% of South households (unweighted).

## Variance: the jackknife

Microdata guide, p. 2, "Jackknife method of estimating standard error":

> The 2020 RECS uses the Jackknife method to produce replicate weights to calculate standard errors of an estimate of interest. This method uses replicate weights to repeatedly estimate the statistic of interest from each of multiple replicate samples generated from the full sample and calculates the differences between these estimates and the full-sample estimate. We constructed 60 Jackknife replicates to produce variance estimates for univariate statistics with 59 nominal degrees of freedom.

> If θ is a population parameter of interest, let θ̂ be the estimate from the full sample for θ. Let θ̂_r be an estimator used for the r-th replicate, and R is the total number of the replicate weights, the variance of θ̂ is estimated by:
>
> V̂(θ̂) = ((R − 1) / R) · Σ_{r=1}^{R} (θ̂_r − θ̂)²
>
> The formula for calculating the RSE is: (√V̂(θ̂) / θ̂) × 100

The formula is typeset in the PDF, so its symbols are transcribed here. The coefficient is also stated in words, twice:

- Microdata guide, p. 4: "The jackknife coefficient is 59/60, which is also the default value in the procedure".
- Technical Documentation Summary, p. 20: "We constructed 60 Jackknife replicates. We estimated the standard errors using the Jackknife method with a coefficient of 0.983 (59/60 replicates)."

The guide's R setup is the same method: `svrepdesign(..., type = "JK1", scale = (ncol(repweights)-1)/ncol(repweights), mse = TRUE)`. `burden.jackknife_se` implements it with R = 60, and `cell_estimate` recomputes the weighted mean once per replicate weight.

**Checked against EIA's worked examples** (microdata guide pp. 3 to 5 and 9 to 10), running `burden.jackknife_se` and `burden.cell_estimate` on the v7 CSV:

| Example | EIA's answer | This code |
|---|---|---|
| Households with `FUELHEAT = 1` | 9,595 cases; 62,713,449; SE 483,047; RSE 0.77 | 9,595; 62,713,449; SE 483,047; RSE 0.77 |
| South Carolina, `BTUNG > 0`, mean `BTUNG` | 34.4 million Btu, RSE 6.3 | 34,401.5 thousand Btu, RSE 6.3 |

## When a cell is estimated

Microdata guide, p. 13, "Notes to Consider When Using the Microdata File and Replicate Weights":

> 1. Publication standards: We do not publish RECS estimates where the RSE is higher than 50 or the number of households used for the calculation is less than 10 (indicated by a Q in the data tables). We recommend following these guidelines for custom analysis using the public use microdata file.

The script follows it. "Enough cases" means at least 10 households in the cell (`MIN_CASES = 10`). A cell with fewer, or with an RSE above 50, is written as withheld, with no burden. Georgia is used only if all 30 estimable cells (15 brackets x Own/Rent) have 10 or more households. In v7 Georgia has 417 households, and 17 of its 30 cells fall short (smallest: 2). **So the output is for the South Census region**, where the smallest cell has 35 households.

## 95% confidence intervals

The intervals are the estimate ± 2.001 SE, 2.001 being the two-sided 95% t value for the 59 degrees of freedom quoted above. EIA's published intervals match it. The Technical Documentation Summary (p. 21, Appendix A) gives natural gas main heating as 62.71 million homes, RSE 0.77, "95% CI for estimate (61.75, 63.68)". With the SE of 483,047, ± 2.001 SE reproduces (61.75, 63.68); ± 1.96 SE gives (61.77, 63.66).

## Choices that are ours, not EIA's

- **Income is the bracket midpoint**, (bracket floor + next bracket's floor) / 2. For example, bracket 2 ($5,000 - $7,499) is 6,250 and bracket 15 ($100,000 - $149,999) is 125,000. Bracket 1 ("Less than $5,000") uses 2,500, taking 0 as its floor. It is the weakest midpoint, and its burden is the most sensitive to it.
- **The open top bracket is not estimated.** "$150,000 or more" has no upper bound and so no midpoint. Its rows keep the household counts and leave the burden blank.
- **Burden** is `TOTALDOL / midpoint` per household, and a cell's burden is the `NWEIGHT`-weighted mean. Income is constant within a bracket, so this equals the weighted mean `TOTALDOL` divided by the midpoint.
- **Renter status**: `KOWNRENT = 2` is Rent and `1` is Own. Code `3` ("Occupy without payment of rent") is neither and is excluded: 82 South households.

## Caveats for anyone quoting the result

- **Cost is modeled.** `TOTALDOL` is in the codebook's "End-use Model" section, so it is labeled EIA-estimated. The microdata guide (p. 14) also says: "We added random errors to weather and climate (HDD30YR and CDD30YR) values, as well as to the annualized consumption variables for electricity and natural gas."
- **The cost counts the home's energy whatever the payer.** The codebook has `ELPAY` \| Num \| Who pays for electricity \| 1 Household is responsible for paying for all electricity used in this home 2 All electricity used in this home is included in the rent or condo fee 3 Some is paid by the household, some is included in the rent or condo fee 99 Other. In the South, 8.1% of renters (weighted) have `ELPAY = 2` and 1.4% have `ELPAY = 3`, against 0.6% and 0.3% of owners. For those renters, the burden here is not what they pay in utility bills. `burden.py` does not adjust for this.
- **The cost leaves out wood**, which is not in `TOTALDOL`'s description.
- **Negative totals exist but not in the South.** One household in the national file has a negative `TOTALDOL` (the codebook's range starts at -150.51). None is in the South, where the smallest is 37.53.
