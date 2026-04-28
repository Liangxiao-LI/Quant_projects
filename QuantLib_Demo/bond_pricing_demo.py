import QuantLib as ql


def price_fixed_rate_bond() -> dict[str, float]:
    """Price a simple fixed-rate bond using a flat yield curve."""
    # QuantLib needs a calendar and a global evaluation date before pricing.
    # The evaluation date is the "today" date for discounting future cash flows.
    calendar = ql.UnitedStates(ql.UnitedStates.GovernmentBond)
    settlement_date = ql.Date(27, 4, 2026)
    ql.Settings.instance().evaluationDate = settlement_date

    # Bond and market assumptions.
    # Amounts are quoted per 100 face value, which is standard for bond pricing. etc
    face_value = 100.0
    coupon_rate = 0.045
    market_yield = 0.04

    # Build the coupon schedule: semiannual coupon dates from issue to maturity.
    # DateGeneration.Backward works backward from maturity to create regular periods.
    issue_date = ql.Date(27, 4, 2024)
    maturity_date = ql.Date(27, 4, 2031)
    tenor = ql.Period(ql.Semiannual)
    schedule = ql.Schedule(
        issue_date,
        maturity_date,
        tenor,
        calendar,
        ql.Unadjusted,
        ql.Unadjusted,
        ql.DateGeneration.Backward,
        False,
    )

    # Actual/Actual is commonly used for government and corporate bond accruals.
    # The settlement_days value controls when the buyer actually settles the trade.
    day_count = ql.ActualActual(ql.ActualActual.Bond)
    settlement_days = 2
    bond = ql.FixedRateBond(
        settlement_days,
        face_value,
        schedule,
        [coupon_rate],
        day_count,
    )

    # Use a flat yield curve for the demo: every maturity discounts at market_yield.
    # Real projects usually replace this with a bootstrapped market curve.
    discount_curve = ql.FlatForward(
        settlement_date,
        market_yield,
        day_count,
        ql.Compounded,
        ql.Semiannual,
    )

    # The pricing engine links the instrument to the discount curve.
    engine = ql.DiscountingBondEngine(ql.YieldTermStructureHandle(discount_curve))
    bond.setPricingEngine(engine)

    # Clean price excludes accrued interest; dirty price includes it.
    # Yield is implied from the bond price under the same day-count/compounding rules.
    clean_price = bond.cleanPrice()
    dirty_price = bond.dirtyPrice()
    accrued_interest = bond.accruedAmount()
    yield_to_maturity = bond.bondYield(
        day_count,
        ql.Compounded,
        ql.Semiannual,
    )

    return {
        "clean_price": clean_price,
        "dirty_price": dirty_price,
        "accrued_interest": accrued_interest,
        "yield_to_maturity": yield_to_maturity,
    }


def main() -> None:
    result = price_fixed_rate_bond()

    print("QuantLib Fixed-Rate Bond Demo")
    print("--------------------------------")
    print(f"Clean price:        {result['clean_price']:.4f}")
    print(f"Dirty price:        {result['dirty_price']:.4f}")
    print(f"Accrued interest:   {result['accrued_interest']:.4f}")
    print(f"Yield to maturity:  {result['yield_to_maturity']:.4%}")


if __name__ == "__main__":
    main()
