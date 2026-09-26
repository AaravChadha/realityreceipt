import math

import pandas as pd
import pytest

from recs import burden

REPS = ["NWEIGHT1", "NWEIGHT2", "NWEIGHT3"]

# Six households, three replicate weights. Bracket 11 ($40,000 - $49,999) has midpoint 45,000.
SYNTHETIC = pd.DataFrame(
    [
        # MONEYPY, KOWNRENT, TOTALDOL, NWEIGHT, NWEIGHT1, NWEIGHT2, NWEIGHT3
        (11, 2, 900.0, 1.0, 0.0, 1.0, 1.0),  # burden 0.02
        (11, 2, 1800.0, 1.0, 2.0, 0.0, 1.0),  # burden 0.04
        (11, 2, 2700.0, 2.0, 3.0, 1.0, 2.0),  # burden 0.06
        (11, 1, 450.0, 3.0, 3.0, 3.0, 0.0),  # owner, burden 0.01; zero weight in replicate 3
        (16, 2, 3000.0, 1.0, 1.0, 1.0, 1.0),  # open top bracket
        (11, 3, 999.0, 5.0, 5.0, 5.0, 5.0),  # occupies without paying rent: excluded
    ],
    columns=["MONEYPY", "KOWNRENT", "TOTALDOL", "NWEIGHT", *REPS],
)

# Renters in bracket 11, by hand. The weights make the unweighted mean (0.04) differ from the
# weighted one, and each replicate's weights sum to a different total than NWEIGHT's.
#   full sample: (1*0.02 + 1*0.04 + 2*0.06) / (1 + 1 + 2) = 0.18 / 4 = 0.045
#   replicate 1: (0*0.02 + 2*0.04 + 3*0.06) / (0 + 2 + 3) = 0.26 / 5 = 0.052
#   replicate 2: (1*0.02 + 0*0.04 + 1*0.06) / (1 + 0 + 1) = 0.08 / 2 = 0.040
#   replicate 3: same weights as the full sample = 0.045
#   variance = (3 - 1) / 3 * ((0.052 - 0.045)^2 + (0.040 - 0.045)^2 + 0)
#            = 2/3 * (0.000049 + 0.000025) = 2/3 * 0.000074
#   SE = sqrt(0.000074 * 2 / 3) = 0.0070238...
RENT_MEAN = 0.045
RENT_SE = math.sqrt(0.000074 * 2 / 3)


def renters_bracket_11() -> pd.DataFrame:
    return SYNTHETIC[(SYNTHETIC.MONEYPY == 11) & (SYNTHETIC.KOWNRENT == 2)]


def test_weighted_mean_and_replicate_se():
    cell = renters_bracket_11()
    mean, se = burden.cell_estimate(cell.TOTALDOL.to_numpy() / 45_000, cell, REPS)
    assert mean == pytest.approx(RENT_MEAN)
    assert se == pytest.approx(RENT_SE)


def test_bracket_midpoints():
    assert burden.midpoint(1) == 2_500
    assert burden.midpoint(11) == 45_000
    assert burden.midpoint(15) == 125_000
    assert burden.midpoint(16) is None


def test_table_on_synthetic_frame(monkeypatch):
    monkeypatch.setattr(burden, "MIN_CASES", 1)
    table = burden.burden_table(SYNTHETIC, "test", REPS).set_index(["income_code", "tenure"])

    rent = table.loc[(11, "Rent")]
    assert rent.status == "estimated"
    assert rent.n_unweighted == 3
    assert rent.households_weighted == 4
    assert rent.burden == pytest.approx(RENT_MEAN)
    assert rent.burden_se == pytest.approx(RENT_SE)
    assert rent.burden_rse_pct == pytest.approx(RENT_SE / RENT_MEAN * 100)
    assert rent.burden_ci95_low == pytest.approx(RENT_MEAN - 2.001 * RENT_SE)

    # A replicate with zero total weight leaves the SE undefined, so the cell is withheld.
    assert table.loc[(11, "Own")].status.startswith("withheld")
    assert table.loc[(16, "Rent")].status.startswith("not estimated")
    assert pd.isna(table.loc[(16, "Rent")].burden)
    # The KOWNRENT == 3 household appears in no cell.
    assert table.n_unweighted.sum() == 5


def test_table_withholds_cells_under_ten_households():
    table = burden.burden_table(SYNTHETIC, "test", REPS).set_index(["income_code", "tenure"])
    assert table.loc[(11, "Rent")].status == "withheld: fewer than 10 households"
    assert pd.isna(table.loc[(11, "Rent")].burden)


def full_cells(state: str, region: str) -> pd.DataFrame:
    rows = [
        (state, region, code, tenure)
        for code in burden.estimable_codes()
        for tenure in burden.TENURES
        for _ in range(burden.MIN_CASES)
    ]
    return pd.DataFrame(rows, columns=["state_postal", "REGIONC", "MONEYPY", "KOWNRENT"])


def test_georgia_when_every_cell_has_ten_households():
    df = pd.concat([full_cells("GA", "SOUTH"), full_cells("TX", "SOUTH")])
    geography, frame, _ = burden.choose_geography(df)
    assert geography == "Georgia"
    assert set(frame.state_postal) == {"GA"}


def test_south_when_a_georgia_cell_is_thin():
    georgia = full_cells("GA", "SOUTH").iloc[1:]  # one cell drops to 9 households
    df = pd.concat([georgia, full_cells("TX", "SOUTH"), full_cells("OH", "MIDWEST")])
    geography, frame, reason = burden.choose_geography(df)
    assert geography == "South Census region"
    assert set(frame.state_postal) == {"GA", "TX"}
    assert "1 of 30 Georgia cells" in reason
