# Fixed Income Portfolio Risk Report

As of **November 05, 2026** (latest FRED data) | NAV **$100,000,624** | VaR window: Nov 2023 to Nov 2026 (747 trading days)

## Summary

| Measure | Value |
|---|---|
| Modified duration | 6.38 years |
| DV01 (loss for +1bp parallel rates) | $63,758 |
| CS01 (loss for +1bp credit spreads) | $27,497 |
| 1-day 95% VaR, historical | $513,537 (0.51%) |
| 1-day 99% VaR, historical | $809,509 (0.81%) |
| 1-day 97.5% Expected Shortfall | $824,057 (0.82%) |
| 1-day 95% / 99% VaR, parametric | $528,489 / $747,452 |
| 10-day 99% VaR (sqrt-time) | $2,559,891 |
| Backtest (99%, 250-day rolling) | 5 exceptions in 497 days (expected 5.0); Kupiec p = 0.99; Green zone |
| Worst stress loss | $-15,533,378 (-15.53%) - 2022 Fed hiking shock (Dec-21 to Oct-22) |

## Positions and sensitivities

| Position | MV | Weight | Yield | Mod. dur. | DV01 | CS01 |
|---|---|---|---|---|---|---|
| UST 2Y | $15,000,351 | 15.00% | 4.46% | 1.89 | $2,839 | - |
| UST 5Y | $15,000,184 | 15.00% | 4.59% | 4.42 | $6,630 | - |
| UST 10Y | $15,000,120 | 15.00% | 4.84% | 7.85 | $11,768 | - |
| UST 30Y | $10,000,000 | 10.00% | 5.25% | 15.02 | $15,024 | - |
| Corp A 5Y | $11,999,579 | 12.00% | 5.42% | 4.33 | $5,199 | $5,199 |
| Corp A 10Y | $9,999,894 | 10.00% | 5.67% | 7.56 | $7,563 | $7,563 |
| Corp BBB 7Y | $13,000,000 | 13.00% | 6.00% | 5.65 | $7,342 | $7,342 |
| Corp BBB 10Y | $10,000,496 | 10.00% | 6.15% | 7.39 | $7,393 | $7,393 |

**Key-rate DV01 (portfolio):** 1Y $0, 2Y $2,839, 5Y $16,234, 10Y $29,661, 30Y $15,024

## VaR contribution by position (95% tail)

| Position | Contribution | Share |
|---|---|---|
| UST 30Y | $145,666 | 20.76% |
| UST 10Y | $135,171 | 19.27% |
| Corp BBB 7Y | $83,968 | 11.97% |
| Corp A 10Y | $82,550 | 11.77% |
| UST 5Y | $82,236 | 11.72% |
| Corp BBB 10Y | $80,498 | 11.47% |
| Corp A 5Y | $61,494 | 8.77% |
| UST 2Y | $29,989 | 4.27% |

Daily P&L volatility: rates alone $329,324, credit spreads alone $40,203, total $321,059. Rate and spread P&L are negatively correlated (-0.26), so spreads partly offset rate risk; rates are the dominant risk.

## Stress tests

| Type | Scenario | P&L | % NAV | Rates | Credit | Worst position |
|---|---|---|---|---|---|---|
| Hypothetical | Parallel +100bp | $-6,042,227 | -6.04% | $-6,042,227 | $0 | UST 30Y ($-1,347,488) |
| Hypothetical | Parallel +200bp | $-11,485,447 | -11.49% | $-11,485,447 | $0 | UST 30Y ($-2,432,919) |
| Hypothetical | Parallel -100bp | $6,749,814 | 6.75% | $6,749,814 | $0 | UST 2Y ($287,389) |
| Hypothetical | Bear steepener (2Y +25, 30Y +100) | $-4,369,523 | -4.37% | $-4,369,523 | $0 | UST 30Y ($-1,347,488) |
| Hypothetical | Bull flattener (2Y -25, 30Y -75) | $3,785,040 | 3.79% | $3,785,040 | $0 | UST 2Y ($71,196) |
| Hypothetical | Credit shock (IG +100, BBB +150) | $-3,312,132 | -3.31% | $0 | $-3,312,132 | Corp BBB 7Y ($-1,047,113) |
| Hypothetical | Stagflation (rates +150, IG +100, BBB +150) | $-11,781,549 | -11.78% | $-8,832,837 | $-3,312,132 | Corp BBB 7Y ($-1,993,451) |
| Historical | 2022 Fed hiking shock (Dec-21 to Oct-22) | $-15,533,378 | -15.53% | $-15,533,378 | $0 | UST 30Y ($-2,834,176) |
| Historical | 2013 Taper tantrum (May-13 to Sep-13) | $-7,072,056 | -7.07% | $-7,072,056 | $0 | UST 10Y ($-1,460,498) |
| Historical | 2020 COVID rate collapse (Feb-20 to Mar-20) | $6,778,575 | 6.78% | $6,778,575 | $0 | UST 2Y ($299,030) |
| Historical | 2008 Lehman (Sep-08 to Dec-08) | $11,394,700 | 11.39% | $11,394,700 | $0 | UST 2Y ($427,834) |
| Historical | Worst 5-day spread widening (02-Apr-25 to 09-Apr-25) | $-1,600,778 | -1.60% | $-855,702 | $-752,824 | Corp BBB 10Y ($-318,789) |

Historical episodes before Nov 2023 apply actual Treasury moves only; FRED does not publish ICE spread history that far back.

## Risk limit monitor

| Metric | Value | Limit | Utilization | Status |
|---|---|---|---|---|
| 1-day 99% VaR (% of NAV) | 0.81% | 0.75% | 108% | BREACH |
| 97.5% Expected Shortfall (% NAV) | 0.82% | 0.90% | 92% | WARNING |
| Portfolio DV01 ($ per bp) | $63,758 | $75,000 | 85% | OK |
| Modified duration (years) | 6.38 | 7.00 | 91% | WARNING |
| Portfolio CS01 ($ per bp) | $27,497 | $30,000 | 92% | WARNING |
| Worst stress loss (% of NAV) | 15.53% | 15.00% | 104% | BREACH |
| Largest issuer-type weight | 55.00% | 60.00% | 92% | WARNING |

## Validation checks

| Check | Result | Detail |
|---|---|---|
| Par bond prices at 100 | PASS | price=100.0000000000 |
| Analytic duration = finite-difference duration (all 8 bonds) | PASS | max diff 1.5e-05 yrs |
| Sum of key-rate DV01s = parallel DV01 | PASS | 63,758 vs 63,758 |
| Bump DV01 = MV x duration / 10,000 | PASS | max rel diff 9.73e-07 |
| Duration + convexity explains +100bp full-revaluation P&L within 1% | PASS | approx -6,023,196 vs full -6,042,227 |
| Position P&L sums to portfolio P&L (historical) | PASS | every day reconciles |
| Stress P&L decomposes into rates + credit + cross term | PASS | all scenarios |
| ES(97.5%) >= VaR(97.5%) | PASS | ES 824,057, VaR97.5 676,261 |
| Parametric VaR within 30% of historical VaR (95%) | PASS | 528,489 vs 513,537 |
| Component VaR sums to 100% | PASS | 1.000000 |
| Rates-only + credit-only P&L close to full P&L (historical) | PASS | max cross term $3,547 |
| No missing data in VaR window | PASS | 747 days |
| Portfolio NAV within 1% of $100M target | PASS | $100,000,624 |
