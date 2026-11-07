# Fixed Income Portfolio Market Risk: VaR, Stress Testing & Risk Attribution

A Python market risk model for a $100M multi-sector bond portfolio: 4 U.S. Treasuries (2Y–30Y) and 4 investment-grade corporates (A and BBB). The bonds are priced off the live U.S. Treasury curve and ICE BofA corporate spreads from FRED, and the model produces a daily-style risk report.

**Run:** `pip install -r requirements.txt`, then `python3 bond_risk.py`. It downloads any missing FRED data and writes `output/risk_report.md` and CSV files. The ICE BofA spread files are not included in this repository because ICE's terms prohibit redistribution; the script downloads them from FRED.

## What it does

| Step | Method |
|---|---|
| Pricing | Discounted semiannual cash flows; yield = interpolated Treasury curve + corporate index spread + issuer add-on |
| Sensitivities | Modified duration, convexity, DV01, key-rate DV01 (1/2/5/10/30Y), CS01 (bump-and-reprice) |
| Value at Risk | 1-day historical-simulation VaR at 95% and 99%, plus 97.5% Expected Shortfall, with full revaluation across 747 daily curve and spread moves (Nov 2023–Nov 2026); parametric (delta-normal) VaR as a cross-check |
| Backtest | Rolling 250-day 99% VaR against realized P&L, exception count, Kupiec proportion-of-failures test and Basel traffic-light zone |
| Stress tests | 7 hypothetical scenarios (parallel shifts, steepener, flattener, credit shock, stagflation) and 5 historical replays (2022 hiking cycle, 2013 taper tantrum, 2020 COVID, 2008 Lehman, worst 5-day spread widening) |
| Attribution | Component VaR by position; rates vs. credit-spread P&L split for every scenario |
| Limits | VaR, ES, DV01, duration, CS01, stress loss and concentration limits, with OK / WARNING / BREACH flags |
| Validation | 13 automated checks: pricing, duration, key-rate DV01 sum, convexity approximation, P&L reconciliation and data completeness |

## Key results (as of Nov 5, 2026)

- Modified duration **6.38 years**; DV01 **$63.8K** per bp; CS01 **$27.5K** per bp. The 10Y key rate carries the most risk ($29.7K per bp).
- 1-day 99% VaR **$810K (0.81% of NAV)**; 97.5% ES **$824K**. Parametric 95% VaR is within 3% of historical VaR.
- **Backtest:** 5 exceptions in 497 days, against 5.0 expected (Kupiec p = 0.99, green zone).
- **Worst stress:** replaying the 2022 Fed hiking cycle loses **$15.5M (−15.5%)**. A credit shock (IG +100bp, BBB +150bp) loses $3.3M.
- The 30Y and 10Y Treasuries drive **40%** of tail risk. Rate and spread P&L are negatively correlated (−0.26), so spreads partly offset rate risk.
- **Limit monitor:** 2 breaches (99% VaR at 108% and stress loss at 104% of limit) and 4 warnings. The limits are illustrative.

## Assumptions and limitations

- Bonds are treated as newly issued at a coupon date (no accrued interest), with no optionality or default.
- FRED publishes only about 3 years of ICE spread history. The VaR window is therefore 3 years, and historical stress replays before November 2023 apply Treasury moves only.
- The 10-day VaR uses square-root-of-time scaling.
- The portfolio and its limits are illustrative, not an actual fund.

Data: Federal Reserve Bank of St. Louis (FRED) series DGS1, DGS2, DGS5, DGS10, DGS30, BAMLC0A0CM and BAMLC0A4CBBB.
