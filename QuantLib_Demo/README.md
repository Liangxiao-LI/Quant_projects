# QuantLib Python Demo

This small project demonstrates how to use QuantLib in Python to price a fixed-rate bond with a flat yield curve.

## Project Contents

- `bond_pricing_demo.py`: runnable QuantLib example with comments explaining each pricing step
- `requirements.txt`: Python dependency list
- `.venv/`: local virtual environment with QuantLib installed

## Setup

The virtual environment has already been created in `.venv`, and QuantLib is installed there.

To recreate the environment:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

## Run

```bash
./.venv/bin/python bond_pricing_demo.py
```

Expected output will look similar to:

```text
QuantLib Fixed-Rate Bond Demo
--------------------------------
Clean price:        102.2432
Dirty price:        102.2678
Accrued interest:   0.0246
Yield to maturity:  3.9978%
```

## What The Demo Does

- Sets an evaluation date
- Builds a semiannual fixed-rate bond schedule
- Creates a flat yield curve
- Prices the bond using `DiscountingBondEngine`
- Prints clean price, dirty price, accrued interest, and yield to maturity

## Model Assumptions

| Item | Value |
|---|---:|
| Face value | 100 |
| Coupon rate | 4.50% |
| Market yield | 4.00% |
| Coupon frequency | Semiannual |
| Issue date | 2024-04-27 |
| Maturity date | 2031-04-27 |
| Settlement days | 2 |

## Key QuantLib Concepts

- `Settings.instance().evaluationDate`: sets the pricing date used by QuantLib.
- `Schedule`: generates the bond coupon dates.
- `FixedRateBond`: represents the fixed-coupon instrument.
- `FlatForward`: creates a simple flat yield curve for discounting.
- `DiscountingBondEngine`: prices the bond from discounted future cash flows.
- `cleanPrice()` vs `dirtyPrice()`: clean price excludes accrued interest, while dirty price includes it.
