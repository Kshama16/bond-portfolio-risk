"""
Fixed Income Portfolio Market Risk: VaR, Stress Testing & Risk Attribution
==========================================================================
A $100M multi-sector bond portfolio (U.S. Treasuries and investment-grade
corporates) priced off the live U.S. Treasury curve and ICE BofA corporate
spreads from FRED.

Steps
1. Build today's curve and price every bond by discounting cash flows.
2. Risk measures: modified duration, convexity, DV01, key-rate DV01, CS01.
3. One-day Value at Risk (VaR) and Expected Shortfall (ES):
   - historical simulation with full revaluation (3 years of daily moves)
   - parametric (delta-normal) VaR from sensitivities and a covariance matrix
4. VaR backtest: rolling 250-day historical VaR, exception count, Kupiec test.
5. Stress tests: hypothetical shocks and actual historical rate episodes.
6. Risk attribution by position and by risk factor (rates vs. credit spread).
7. Risk limit monitoring with breach flags.
8. Automated validation checks.

Data: FRED series DGS1, DGS2, DGS5, DGS10, DGS30 (Treasury constant-maturity
yields) and BAMLC0A0CM / BAMLC0A4CBBB (ICE BofA US Corporate and BBB
option-adjusted spreads). FRED publishes only the last ~3 years of ICE spread
history, so the VaR window is 3 years and historical stress episodes before
that apply rate moves only.

Run:  python3 bond_risk.py      (downloads any missing FRED data, writes output/)
"""
import os
import subprocess
import urllib.error
import urllib.request
import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)

TENORS = [1, 2, 5, 10, 30]
RATE_COLS = ["DGS1", "DGS2", "DGS5", "DGS10", "DGS30"]
SPREAD_COLS = ["IG", "BBB"]
FACTORS = RATE_COLS + SPREAD_COLS
NAV_TARGET = 100_000_000


# ---------------------------------------------------------------- data
def load_series(code, name=None):
    path = os.path.join(DATA, f"{code}.csv")
    if not os.path.exists(path):                 # download from FRED on first run
        os.makedirs(DATA, exist_ok=True)
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={code}"
        try:
            urllib.request.urlretrieve(url, path)
        except urllib.error.URLError:            # e.g. python.org builds without root certificates
            subprocess.run(["curl", "-sSfL", "-o", path, url], check=True)
    df = pd.read_csv(path, parse_dates=["observation_date"])
    s = pd.to_numeric(df[code], errors="coerce")
    s.index = df["observation_date"]
    s.name = name or code
    return s


rates_long = pd.concat([load_series(c) for c in RATE_COLS], axis=1).dropna()
spreads = pd.concat([load_series("BAMLC0A0CM", "IG"), load_series("BAMLC0A4CBBB", "BBB")], axis=1).dropna()
levels = rates_long.join(spreads, how="inner").dropna()        # common window
AS_OF = levels.index[-1]
base = levels.iloc[-1]                                          # today's levels, in percent

# ---------------------------------------------------------------- portfolio
# Bonds are assumed freshly issued (no accrued interest), semiannual coupons,
# coupon set near today's yield. Corporate yield = Treasury curve + index
# spread + an issuer-specific add-on held constant.
POSITIONS = [
    # name,                 sector,     maturity, spread index, add-on bps, target weight
    ("UST 2Y",              "Treasury",  2,  None,  0, 0.15),
    ("UST 5Y",              "Treasury",  5,  None,  0, 0.15),
    ("UST 10Y",             "Treasury", 10,  None,  0, 0.15),
    ("UST 30Y",             "Treasury", 30,  None,  0, 0.10),
    ("Corp A 5Y",           "IG Corp",   5,  "IG", -10, 0.12),
    ("Corp A 10Y",          "IG Corp",  10,  "IG", -10, 0.10),
    ("Corp BBB 7Y",         "BBB Corp",  7,  "BBB", 15, 0.13),
    ("Corp BBB 10Y",        "BBB Corp", 10,  "BBB", 15, 0.10),
]


def curve_rate(lv, t):
    """Linear interpolation of the Treasury curve (percent) at maturity t."""
    return np.interp(t, TENORS, [lv[c] for c in RATE_COLS])


def bond_yield(lv, pos):
    _, _, mat, sidx, addon, _ = pos
    y = curve_rate(lv, mat)
    if sidx:
        y += lv[sidx] + addon / 100.0
    return y / 100.0


def price(coupon, ytm, mat, freq=2):
    """Clean price per 100 face, discounting each cash flow at the bond's yield."""
    n = int(round(mat * freq))
    t = np.arange(1, n + 1)
    cf = np.full(n, 100 * coupon / freq)
    cf[-1] += 100
    return float(np.sum(cf / (1 + ytm / freq) ** t))


def analytic_duration_convexity(coupon, ytm, mat, freq=2):
    n = int(round(mat * freq))
    t = np.arange(1, n + 1)
    cf = np.full(n, 100 * coupon / freq)
    cf[-1] += 100
    df = (1 + ytm / freq) ** -t
    p = np.sum(cf * df)
    mac = np.sum((t / freq) * cf * df) / p
    mod = mac / (1 + ytm / freq)
    conv = np.sum(cf * df * t * (t + 1)) / (p * freq ** 2 * (1 + ytm / freq) ** 2)
    return mod, conv


# coupons and face amounts fixed at inception (today)
book = []
for pos in POSITIONS:
    y0 = bond_yield(base, pos)
    cpn = round(y0 * 800) / 800                       # nearest 1/8 of a percent
    p0 = price(cpn, y0, pos[2])
    face = round(NAV_TARGET * pos[5] / (p0 / 100) / 1000) * 1000
    book.append(dict(name=pos[0], sector=pos[1], maturity=pos[2], spread_idx=pos[3],
                     addon=pos[4], coupon=cpn, face=face, pos=pos))


def portfolio_values(lv):
    """Full revaluation: market value of each position under factor levels lv."""
    return np.array([b["face"] / 100 * price(b["coupon"], bond_yield(lv, b["pos"]), b["maturity"])
                     for b in book])


mv0 = portfolio_values(base)
NAV = mv0.sum()


def shocked(bp_moves):
    lv = base.copy()
    for k, v in bp_moves.items():
        lv[k] = lv[k] + v / 100.0
    return lv


def pnl_vector(bp_moves):
    return portfolio_values(shocked(bp_moves)) - mv0


# ---------------------------------------------------------------- 2. sensitivities
rows = []
for b, mv in zip(book, mv0):
    y = bond_yield(base, b["pos"])
    mod, conv = analytic_duration_convexity(b["coupon"], y, b["maturity"])
    rows.append(dict(Position=b["name"], Sector=b["sector"], Maturity=b["maturity"],
                     Coupon=b["coupon"] * 100, Yield=y * 100, Face=b["face"], MarketValue=mv,
                     Weight=mv / NAV, ModDuration=mod, Convexity=conv, DV01=mv * mod / 10_000))
risk = pd.DataFrame(rows)

# bump-and-reprice sensitivities: P&L for +1bp in each factor (central difference)
sens = {}
for f in FACTORS:
    up, dn = pnl_vector({f: +1}), pnl_vector({f: -1})
    sens[f] = (up - dn) / 2
sens = pd.DataFrame(sens, index=risk["Position"])
krd = sens[RATE_COLS].rename(columns=dict(zip(RATE_COLS, ["KRD01 1Y", "KRD01 2Y", "KRD01 5Y", "KRD01 10Y", "KRD01 30Y"])))
cs01 = sens[SPREAD_COLS].sum(axis=1).rename("CS01")
parallel_dv01 = -(pnl_vector({c: +1 for c in RATE_COLS}) - pnl_vector({c: -1 for c in RATE_COLS})) / 2
risk["DV01_bump"] = parallel_dv01
risk = risk.join(-krd, on="Position").join(-cs01, on="Position")

port_mod_dur = (risk["ModDuration"] * risk["Weight"]).sum()
port_dv01 = risk["DV01_bump"].sum()
port_cs01 = risk["CS01"].sum()

# ---------------------------------------------------------------- 3. VaR / ES
moves = levels.diff().dropna() * 100                          # daily changes, bps
hist_pnl = []
hist_pos_pnl = []
for _, m in moves.iterrows():
    pv = pnl_vector(m.to_dict())
    hist_pos_pnl.append(pv)
    hist_pnl.append(pv.sum())
hist_pnl = pd.Series(hist_pnl, index=moves.index)
hist_pos_pnl = pd.DataFrame(hist_pos_pnl, index=moves.index, columns=risk["Position"])


def hvar(x, a):
    return -np.quantile(x, 1 - a)


def hes(x, a):
    q = np.quantile(x, 1 - a)
    return -x[x <= q].mean()


var95, var99 = hvar(hist_pnl.values, .95), hvar(hist_pnl.values, .99)
es975 = hes(hist_pnl.values, .975)

# parametric (delta-normal): VaR = z * sqrt(s' Σ s), s = portfolio P&L per 1bp
s_vec = sens.sum(axis=0)[FACTORS].values
cov = np.cov(moves[FACTORS].values, rowvar=False)
sigma_p = float(np.sqrt(s_vec @ cov @ s_vec))
pvar95, pvar99 = stats.norm.ppf(.95) * sigma_p, stats.norm.ppf(.99) * sigma_p

# component (Euler) VaR by position: expected position P&L in the tail beyond VaR95
tail = hist_pnl <= -var95
es95 = -hist_pnl[tail].mean()
comp = -hist_pos_pnl[tail].mean()
comp_pct = comp / comp.sum()

# rates vs credit split of the historical P&L
rate_only = np.array([pnl_vector({k: m[k] for k in RATE_COLS}).sum() for _, m in moves.iterrows()])
credit_only = np.array([pnl_vector({k: m[k] for k in SPREAD_COLS}).sum() for _, m in moves.iterrows()])

# ---------------------------------------------------------------- 4. backtest
WIN = 250
exc_dates, var_path = [], []
for i in range(WIN, len(hist_pnl)):
    v = hvar(hist_pnl.iloc[i - WIN:i].values, .99)
    var_path.append(v)
    if hist_pnl.iloc[i] < -v:
        exc_dates.append(hist_pnl.index[i])
N_bt = len(var_path)
x_bt = len(exc_dates)
p = 0.01
phat = x_bt / N_bt
if x_bt == 0:
    lr = -2 * (N_bt * np.log(1 - p))
else:
    lr = -2 * ((N_bt - x_bt) * np.log(1 - p) + x_bt * np.log(p)
               - (N_bt - x_bt) * np.log(1 - phat) - x_bt * np.log(phat))
kupiec_p = 1 - stats.chi2.cdf(lr, 1)
zone = "Green" if x_bt <= 4 * N_bt / 250 else ("Yellow" if x_bt <= 9 * N_bt / 250 else "Red")

# ---------------------------------------------------------------- 5. stress tests
ALL_R = {c: 1 for c in RATE_COLS}
hypo = {
    "Parallel +100bp":                    {c: 100 for c in RATE_COLS},
    "Parallel +200bp":                    {c: 200 for c in RATE_COLS},
    "Parallel -100bp":                    {c: -100 for c in RATE_COLS},
    "Bear steepener (2Y +25, 30Y +100)":  dict(zip(RATE_COLS, [15, 25, 50, 75, 100])),
    "Bull flattener (2Y -25, 30Y -75)":   dict(zip(RATE_COLS, [-15, -25, -40, -60, -75])),
    "Credit shock (IG +100, BBB +150)":   {"IG": 100, "BBB": 150},
    "Stagflation (rates +150, IG +100, BBB +150)": {**{c: 150 for c in RATE_COLS}, "IG": 100, "BBB": 150},
}


def episode(start, end, with_spreads=False):
    src = levels if with_spreads else rates_long
    a = src.loc[:start].iloc[-1]
    b = src.loc[:end].iloc[-1]
    cols = FACTORS if with_spreads else RATE_COLS
    return {c: (b[c] - a[c]) * 100 for c in cols}


hist_eps = {
    "2022 Fed hiking shock (Dec-21 to Oct-22)":   episode("2021-12-31", "2022-10-21"),
    "2013 Taper tantrum (May-13 to Sep-13)":      episode("2013-05-01", "2013-09-05"),
    "2020 COVID rate collapse (Feb-20 to Mar-20)": episode("2020-02-19", "2020-03-09"),
    "2008 Lehman (Sep-08 to Dec-08)":             episode("2008-09-12", "2008-12-30"),
}
# worst 5-day credit-spread widening inside the spread data window (rates + spreads)
w5 = levels["BBB"].diff(5)
end5 = w5.idxmax()
start5 = levels.index[levels.index.get_loc(end5) - 5]
hist_eps[f"Worst 5-day spread widening ({start5:%d-%b-%y} to {end5:%d-%b-%y})"] = episode(start5, end5, True)

stress_rows = []
for kind, scen in [("Hypothetical", hypo), ("Historical", hist_eps)]:
    for name, mv in scen.items():
        pv = pnl_vector(mv)
        r = pnl_vector({k: v for k, v in mv.items() if k in RATE_COLS}).sum()
        c = pnl_vector({k: v for k, v in mv.items() if k in SPREAD_COLS}).sum()
        stress_rows.append(dict(Type=kind, Scenario=name, PnL=pv.sum(), PnL_pct=pv.sum() / NAV,
                                Rates_PnL=r, Credit_PnL=c, Cross=pv.sum() - r - c,
                                Worst_position=risk["Position"][int(np.argmin(pv))],
                                Worst_position_PnL=pv.min(),
                                DV01_estimate=-port_dv01 * np.mean([mv.get(k, 0) for k in RATE_COLS])))
stress = pd.DataFrame(stress_rows)
stress_pos = pd.DataFrame({n: pnl_vector(m) for n, m in {**hypo, **hist_eps}.items()}, index=risk["Position"])

# ---------------------------------------------------------------- 7. limits
limits = [
    ("1-day 99% VaR (% of NAV)",        var99 / NAV,        0.0075),
    ("97.5% Expected Shortfall (% NAV)", es975 / NAV,       0.0090),
    ("Portfolio DV01 ($ per bp)",       port_dv01,          75_000),
    ("Modified duration (years)",       port_mod_dur,       7.0),
    ("Portfolio CS01 ($ per bp)",       port_cs01,          30_000),
    ("Worst stress loss (% of NAV)",    -stress["PnL_pct"].min(), 0.15),
    ("Largest issuer-type weight",      risk.groupby("Sector")["Weight"].sum().max(), 0.60),
]
# illustrative limits for a core bond fund; set by the risk committee in practice
lim = pd.DataFrame(limits, columns=["Metric", "Value", "Limit"])
lim["Utilization"] = lim["Value"] / lim["Limit"]
lim["Status"] = np.where(lim["Utilization"] > 1, "BREACH",
                         np.where(lim["Utilization"] > 0.9, "WARNING", "OK"))

# ---------------------------------------------------------------- 8. validation checks
checks = []


def check(name, ok, detail):
    checks.append(dict(Check=name, Result="PASS" if ok else "FAIL", Detail=detail))


p_par = price(0.05, 0.05, 10)
check("Par bond prices at 100", abs(p_par - 100) < 1e-9, f"price={p_par:.10f}")
dur_diff = []
for b, r in zip(book, risk.itertuples()):
    y = bond_yield(base, b["pos"])
    fd = -(price(b["coupon"], y + 1e-4, b["maturity"]) - price(b["coupon"], y - 1e-4, b["maturity"])) / (2e-4 * price(b["coupon"], y, b["maturity"]))
    dur_diff.append(abs(fd - r.ModDuration))
check("Analytic duration = finite-difference duration (all 8 bonds)", max(dur_diff) < 1e-4,
      f"max diff {max(dur_diff):.1e} yrs")
krd_sum = risk[[c for c in risk.columns if c.startswith("KRD01")]].sum().sum()
check("Sum of key-rate DV01s = parallel DV01", abs(krd_sum - port_dv01) / port_dv01 < 1e-3,
      f"{krd_sum:,.0f} vs {port_dv01:,.0f}")
check("Bump DV01 = MV x duration / 10,000", np.allclose(risk["DV01"], risk["DV01_bump"], rtol=2e-3),
      f"max rel diff {np.max(np.abs(risk['DV01'] / risk['DV01_bump'] - 1)):.2e}")
dv01_pred = -port_dv01 * 100 + 0.5 * NAV * (risk["Convexity"] * risk["Weight"]).sum() * 0.01 ** 2
act = stress.loc[stress.Scenario == "Parallel +100bp", "PnL"].iloc[0]
check("Duration + convexity explains +100bp full-revaluation P&L within 1%",
      abs(dv01_pred - act) / abs(act) < 0.01, f"approx {dv01_pred:,.0f} vs full {act:,.0f}")
check("Position P&L sums to portfolio P&L (historical)",
      np.allclose(hist_pos_pnl.sum(axis=1), hist_pnl), "every day reconciles")
check("Stress P&L decomposes into rates + credit + cross term",
      np.allclose(stress["PnL"], stress["Rates_PnL"] + stress["Credit_PnL"] + stress["Cross"]), "all scenarios")
var975 = hvar(hist_pnl.values, .975)
check("ES(97.5%) >= VaR(97.5%)", es975 >= var975, f"ES {es975:,.0f}, VaR97.5 {var975:,.0f}")
check("Parametric VaR within 30% of historical VaR (95%)", abs(pvar95 / var95 - 1) < 0.30,
      f"{pvar95:,.0f} vs {var95:,.0f}")
check("Component VaR sums to 100%", abs(comp_pct.sum() - 1) < 1e-9, f"{comp_pct.sum():.6f}")
check("Rates-only + credit-only P&L close to full P&L (historical)",
      np.max(np.abs(rate_only + credit_only - hist_pnl.values)) < 0.002 * NAV,
      f"max cross term ${np.max(np.abs(rate_only + credit_only - hist_pnl.values)):,.0f}")
check("No missing data in VaR window", not moves.isna().any().any(), f"{len(moves)} days")
check("Portfolio NAV within 1% of $100M target", abs(NAV / NAV_TARGET - 1) < 0.01, f"${NAV:,.0f}")
chk = pd.DataFrame(checks)

# ---------------------------------------------------------------- outputs
risk.to_csv(os.path.join(OUT, "position_risk.csv"), index=False)
stress.to_csv(os.path.join(OUT, "stress_tests.csv"), index=False)
stress_pos.to_csv(os.path.join(OUT, "stress_by_position.csv"))
hist_pnl.rename("PnL").to_csv(os.path.join(OUT, "historical_pnl.csv"))
lim.to_csv(os.path.join(OUT, "limit_monitor.csv"), index=False)
chk.to_csv(os.path.join(OUT, "validation_checks.csv"), index=False)

m = lambda x: f"${x:,.0f}"
pc = lambda x: f"{x:.2%}"
L = []
L.append(f"# Fixed Income Portfolio Risk Report\n\nAs of **{AS_OF:%B %d, %Y}** (latest FRED data) | NAV **{m(NAV)}** | "
         f"VaR window: {moves.index[0]:%b %Y} to {moves.index[-1]:%b %Y} ({len(moves)} trading days)\n")
L.append("## Summary\n")
L.append("| Measure | Value |\n|---|---|")
for k, v in [("Modified duration", f"{port_mod_dur:.2f} years"), ("DV01 (loss for +1bp parallel rates)", m(port_dv01)),
             ("CS01 (loss for +1bp credit spreads)", m(port_cs01)),
             ("1-day 95% VaR, historical", f"{m(var95)} ({pc(var95/NAV)})"),
             ("1-day 99% VaR, historical", f"{m(var99)} ({pc(var99/NAV)})"),
             ("1-day 97.5% Expected Shortfall", f"{m(es975)} ({pc(es975/NAV)})"),
             ("1-day 95% / 99% VaR, parametric", f"{m(pvar95)} / {m(pvar99)}"),
             ("10-day 99% VaR (sqrt-time)", m(var99 * np.sqrt(10))),
             ("Backtest (99%, 250-day rolling)", f"{x_bt} exceptions in {N_bt} days (expected {N_bt*p:.1f}); Kupiec p = {kupiec_p:.2f}; {zone} zone"),
             ("Worst stress loss", f"{m(stress.PnL.min())} ({pc(stress.PnL_pct.min())}) - {stress.loc[stress.PnL.idxmin(),'Scenario']}")]:
    L.append(f"| {k} | {v} |")
L.append("\n## Positions and sensitivities\n")
L.append("| Position | MV | Weight | Yield | Mod. dur. | DV01 | CS01 |\n|---|---|---|---|---|---|---|")
for r in risk.itertuples():
    L.append(f"| {r.Position} | {m(r.MarketValue)} | {pc(r.Weight)} | {r.Yield:.2f}% | {r.ModDuration:.2f} | {m(r.DV01_bump)} | {m(abs(r.CS01)) if abs(r.CS01) > 0.5 else "-"} |")
L.append("\n**Key-rate DV01 (portfolio):** " + ", ".join(f"{c.split()[1]} {m(risk[c].sum())}" for c in risk.columns if c.startswith("KRD01")))
L.append("\n## VaR contribution by position (95% tail)\n")
L.append("| Position | Contribution | Share |\n|---|---|---|")
for k in comp.sort_values(ascending=False).index:
    L.append(f"| {k} | {m(comp[k])} | {pc(comp_pct[k])} |")
corr_rc = np.corrcoef(rate_only, credit_only)[0, 1]
L.append(f"\nDaily P&L volatility: rates alone {m(np.std(rate_only))}, credit spreads alone {m(np.std(credit_only))}, total {m(np.std(hist_pnl.values))}. "
         f"Rate and spread P&L are {'negatively' if corr_rc < 0 else 'positively'} correlated ({corr_rc:.2f}), so spreads "
         f"{'partly offset' if corr_rc < 0 else 'add to'} rate risk; rates are the dominant risk.")
L.append("\n## Stress tests\n")
L.append("| Type | Scenario | P&L | % NAV | Rates | Credit | Worst position |\n|---|---|---|---|---|---|---|")
for r in stress.itertuples():
    L.append(f"| {r.Type} | {r.Scenario} | {m(r.PnL)} | {pc(r.PnL_pct)} | {m(r.Rates_PnL)} | {m(r.Credit_PnL)} | {r.Worst_position} ({m(r.Worst_position_PnL)}) |")
L.append("\nHistorical episodes before Nov 2023 apply actual Treasury moves only; FRED does not publish ICE spread history that far back.")
L.append("\n## Risk limit monitor\n")
L.append("| Metric | Value | Limit | Utilization | Status |\n|---|---|---|---|---|")
for r in lim.itertuples():
    fmt = (lambda x: pc(x)) if ("%" in r.Metric or "weight" in r.Metric) else ((lambda x: f"{x:.2f}") if "years" in r.Metric else m)
    L.append(f"| {r.Metric} | {fmt(r.Value)} | {fmt(r.Limit)} | {r.Utilization:.0%} | {r.Status} |")
L.append("\n## Validation checks\n")
L.append("| Check | Result | Detail |\n|---|---|---|")
for r in chk.itertuples():
    L.append(f"| {r.Check} | {r.Result} | {r.Detail} |")
open(os.path.join(OUT, "risk_report.md"), "w").write("\n".join(L) + "\n")

print("\n".join(L))
print(f"\nChecks: {(chk.Result=='PASS').sum()}/{len(chk)} passed")
