"""Energy burden by income bracket and renter status, from the RECS 2020 microdata.

Energy burden = a household's total energy cost (TOTALDOL) / its income, with
income taken as the midpoint of its MONEYPY bracket. Each cell is the
NWEIGHT-weighted mean burden, with a jackknife standard error from the 60
replicate weights. Every variable name, the variance formula and the
suppression rule are quoted from EIA, with URLs, in VARIABLES.md.

Usage (the raw CSV is not committed; download it from the URL in VARIABLES.md):

    api/.venv/bin/python analysis/recs/burden.py /path/to/recs2020_public_v7.csv

Writes analysis/recs/out/burden.csv and analysis/recs/out/burden.png.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

OUT_DIR = Path(__file__).resolve().parent / "out"

WEIGHT = "NWEIGHT"
REPLICATES = [f"NWEIGHT{r}" for r in range(1, 61)]
INCOME = "MONEYPY"
TENURE = "KOWNRENT"
COST = "TOTALDOL"
STATE = "state_postal"
REGION = "REGIONC"
SOUTH = "SOUTH"  # the value in the CSV; the codebook lists it as "South"

# KOWNRENT codes. 3 ("Occupy without payment of rent") is neither, and is excluded.
TENURES = {2: "Rent", 1: "Own"}

# MONEYPY codes: (codebook label, bracket floor, next bracket's floor).
# Code 16 is open-ended, so it has no midpoint and its burden is not estimated.
BRACKETS = {
    1: ("Less than $5,000", 0, 5_000),
    2: ("$5,000 - $7,499", 5_000, 7_500),
    3: ("$7,500 - $9,999", 7_500, 10_000),
    4: ("$10,000 - $12,499", 10_000, 12_500),
    5: ("$12,500 - $14,999", 12_500, 15_000),
    6: ("$15,000 - $19,999", 15_000, 20_000),
    7: ("$20,000 - $24,999", 20_000, 25_000),
    8: ("$25,000 - $29,999", 25_000, 30_000),
    9: ("$30,000 - $34,999", 30_000, 35_000),
    10: ("$35,000 - $39,999", 35_000, 40_000),
    11: ("$40,000 - $49,999", 40_000, 50_000),
    12: ("$50,000 - $59,999", 50_000, 60_000),
    13: ("$60,000 - $74,999", 60_000, 75_000),
    14: ("$75,000 - $99,999", 75_000, 100_000),
    15: ("$100,000 - $149,999", 100_000, 150_000),
    16: ("$150,000 or more", 150_000, None),
}

# EIA's publication standard: no estimate from fewer than 10 households or with an RSE above 50.
MIN_CASES = 10
MAX_RSE_PCT = 50.0
# Two-sided 95% t critical value for the 59 degrees of freedom of 60 jackknife replicates.
T_95_DF59 = 2.001


def midpoint(code: int) -> float | None:
    """Midpoint of a MONEYPY bracket; None for the open top bracket."""
    _, floor, ceiling = BRACKETS[code]
    return None if ceiling is None else (floor + ceiling) / 2


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    total = float(np.sum(weights))
    return float(np.sum(values * weights) / total) if total > 0 else float("nan")


def jackknife_se(estimate: float, replicate_estimates: list[float]) -> float:
    """EIA's JK1 standard error: sqrt((R - 1) / R * sum_r (theta_r - theta)^2)."""
    reps = np.asarray(replicate_estimates, dtype=float)
    r = len(reps)
    return float(np.sqrt((r - 1) / r * np.sum((reps - estimate) ** 2)))


def cell_estimate(values: np.ndarray, cell: pd.DataFrame, replicates: list[str]) -> tuple[float, float]:
    """Weighted mean of `values` over `cell` and its jackknife standard error."""
    estimate = weighted_mean(values, cell[WEIGHT].to_numpy(float))
    reps = [weighted_mean(values, cell[w].to_numpy(float)) for w in replicates]
    return estimate, jackknife_se(estimate, reps)


def estimable_codes() -> list[int]:
    return [code for code in BRACKETS if midpoint(code) is not None]


def thin_cells(frame: pd.DataFrame) -> list[tuple[int, str]]:
    """Estimable bracket x tenure cells with fewer than MIN_CASES households."""
    counts = frame.groupby([INCOME, TENURE]).size()
    return [
        (code, label)
        for code in estimable_codes()
        for tenure, label in TENURES.items()
        if counts.get((code, tenure), 0) < MIN_CASES
    ]


def choose_geography(df: pd.DataFrame) -> tuple[str, pd.DataFrame, str]:
    """Georgia when every estimable cell has MIN_CASES households, otherwise the South region."""
    georgia = df[df[STATE] == "GA"]
    thin = thin_cells(georgia)
    cells = len(estimable_codes()) * len(TENURES)
    if not thin:
        return "Georgia", georgia, f"Georgia: every one of {cells} cells has at least {MIN_CASES} households"
    reason = (
        f"South Census region, not Georgia: {len(thin)} of {cells} Georgia cells "
        f"have fewer than {MIN_CASES} households"
    )
    return "South Census region", df[df[REGION] == SOUTH], reason


def burden_table(frame: pd.DataFrame, geography: str, replicates: list[str] = REPLICATES) -> pd.DataFrame:
    """One row per MONEYPY bracket x tenure: n, weighted households, and burden with its SE and 95% CI."""
    rows = []
    for code, (label, _, _) in BRACKETS.items():
        mid = midpoint(code)
        for tenure, tenure_label in TENURES.items():
            cell = frame[(frame[INCOME] == code) & (frame[TENURE] == tenure)]
            n = len(cell)
            row = {
                "geography": geography,
                "income_code": code,
                "income_bracket": label,
                "income_midpoint": mid,
                "tenure": tenure_label,
                "n_unweighted": n,
                "households_weighted": float(cell[WEIGHT].sum()),
                "burden": None,
                "burden_se": None,
                "burden_rse_pct": None,
                "burden_ci95_low": None,
                "burden_ci95_high": None,
            }
            if mid is None:
                row["status"] = "not estimated: open top bracket has no midpoint"
            elif n < MIN_CASES:
                row["status"] = f"withheld: fewer than {MIN_CASES} households"
            else:
                burden, se = cell_estimate(cell[COST].to_numpy(float) / mid, cell, replicates)
                rse = se / burden * 100 if burden else float("nan")
                if not rse <= MAX_RSE_PCT:
                    row["status"] = f"withheld: RSE above {MAX_RSE_PCT:g}"
                else:
                    row.update(
                        burden=burden,
                        burden_se=se,
                        burden_rse_pct=rse,
                        burden_ci95_low=burden - T_95_DF59 * se,
                        burden_ci95_high=burden + T_95_DF59 * se,
                        status="estimated",
                    )
            rows.append(row)
    return pd.DataFrame(rows)


def write_csv(table: pd.DataFrame, reason: str, path: Path) -> None:
    out = table.copy()
    out.insert(1, "geography_reason", reason)
    out["households_weighted"] = out["households_weighted"].round(0).astype("int64")
    for col in ["burden", "burden_se", "burden_ci95_low", "burden_ci95_high"]:
        out[col] = out[col].astype(float).round(5)
    out["burden_rse_pct"] = out["burden_rse_pct"].astype(float).round(1)
    out.to_csv(path, index=False)


def plot(table: pd.DataFrame, geography: str, reason: str, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import FixedLocator, NullLocator

    surface, ink, ink2, muted, grid, axis = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
    # name, color, x offset so the two series' interval bars do not overlap, direct-label offset
    series = {"Rent": ("Renters", "#2a78d6", -0.09, (0, -16)), "Own": ("Owners", "#eb6834", 0.09, (0, 12))}
    codes = list(BRACKETS)
    ticks = ["<$5k", "$5k", "$7.5k", "$10k", "$12.5k", "$15k", "$20k", "$25k", "$30k",
             "$35k", "$40k", "$50k", "$60k", "$75k", "$100k", "$150k+"]
    label_code = 9  # direct labels sit at the $30k bracket, where the lines are well apart

    fig, ax = plt.subplots(figsize=(11, 6.4), dpi=200)
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)
    handles = []
    for tenure, (name, color, dx, label_offset) in series.items():
        rows = table[(table["tenure"] == tenure) & (table["status"] == "estimated")]
        x = rows["income_code"].to_numpy() - 1 + dx
        y = rows["burden"].to_numpy() * 100
        yerr = [y - rows["burden_ci95_low"].to_numpy() * 100, rows["burden_ci95_high"].to_numpy() * 100 - y]
        ax.errorbar(x, y, yerr=yerr, color=color, linewidth=2, marker="o", markersize=6,
                    markeredgecolor=surface, markeredgewidth=1.5, elinewidth=1.2, capsize=0, zorder=3)
        at = rows[rows["income_code"] == label_code].iloc[0]
        ax.annotate(name, (label_code - 1 + dx, at["burden"] * 100), xytext=label_offset,
                    textcoords="offset points", ha="center", va="center", color=ink2, fontsize=10)
        handles.append(Line2D([], [], color=color, linewidth=2, marker="o", markersize=6,
                              markeredgecolor=surface, label=name))

    ax.set_yscale("log")
    ax.set_ylim(0.8, 100)
    ax.yaxis.set_major_locator(FixedLocator([1, 2, 5, 10, 20, 50, 100]))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.set_yticks([1, 2, 5, 10, 20, 50, 100], ["1%", "2%", "5%", "10%", "20%", "50%", "100%"])
    ax.set_xticks(range(len(codes)), ticks, color=muted, fontsize=9)
    ax.tick_params(axis="both", length=0, colors=muted)
    ax.set_xlim(-0.6, len(codes) - 0.4)
    ax.grid(axis="y", color=grid, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(axis)
    ax.text(len(codes) - 1, 1.5, "not\nestimated", ha="center", va="center", color=muted, fontsize=8.5)
    ax.set_xlabel("Annual household income bracket (lower bound)", color=ink2, fontsize=10)
    ax.set_ylabel("Energy cost as a share of income (log scale)", color=ink2, fontsize=10)
    ax.legend(handles=handles, loc="upper right", frameon=False, labelcolor=ink2, fontsize=10)

    fig.suptitle(f"Home energy burden by income, {geography}, 2020", x=0.07, ha="left",
                 color=ink, fontsize=15, fontweight="bold")
    ax.set_title(
        "Weighted mean of EIA-estimated total energy cost / income bracket midpoint. "
        "Bars are 95% confidence intervals from EIA's 60 jackknife replicate weights.\n"
        f"{reason}.",
        loc="left", color=ink2, fontsize=9.5, pad=12,
    )
    fig.text(0.07, 0.015,
             "Source: EIA, 2020 Residential Energy Consumption Survey public microdata v7 (TOTALDOL, MONEYPY, "
             "KOWNRENT, NWEIGHT). $150k+ is open-ended, so its burden is not estimated.",
             color=muted, fontsize=8)
    fig.subplots_adjust(left=0.07, right=0.93, top=0.84, bottom=0.12)
    fig.savefig(path, facecolor=surface)
    plt.close(fig)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", type=Path, help="path to recs2020_public_v7.csv (kept outside the repo)")
    args = parser.parse_args(argv)

    columns = [STATE, REGION, INCOME, TENURE, COST, WEIGHT, *REPLICATES]
    df = pd.read_csv(args.csv, usecols=columns)
    geography, frame, reason = choose_geography(df)
    table = burden_table(frame, geography)

    OUT_DIR.mkdir(exist_ok=True)
    write_csv(table, reason, OUT_DIR / "burden.csv")
    plot(table, geography, reason, OUT_DIR / "burden.png")

    excluded = int((frame[TENURE] == 3).sum())
    print(f"Geography: {geography} ({reason}).")
    print(f"Households: {len(frame)}; excluded {excluded} that occupy without payment of rent.")
    print(table["status"].value_counts().to_string())
    print(f"Wrote {OUT_DIR / 'burden.csv'} and {OUT_DIR / 'burden.png'}")


if __name__ == "__main__":
    main()
