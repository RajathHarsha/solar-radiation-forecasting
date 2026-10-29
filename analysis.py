"""
Daily Solar Radiation Forecasting Across Five Indian Cities
SARIMA (baseline) vs weather-aware SARIMAX (improved)

Data  : NASA POWER daily point data (ALLSKY_SFC_SW_DWN, RH2M, T2M, CLOUD_AMT),
        1984-01-01 .. 2026-10-20, five cities. Window used: 2000-01-01 .. 2026-07-30
        (CLOUD_AMT is not yet published after 2026-07-30).
Design: daily -> weekly means (m = 52). Main city = Bengaluru (full pipeline);
        Delhi, Mumbai, Chennai, Jodhpur = robustness table with the same orders.
Eval  : rolling one-week-ahead forecasts over the 20% test block (true forecasts:
        SARIMAX uses only LAGGED weather, so nothing from the target week leaks in),
        plus a static multi-step SARIMA forecast to show long-horizon behaviour.

Run:  python analysis.py            (full run, ~10-15 min)
      python analysis.py --fast     (skips the 4 robustness cities + extensions)
"""
import io, json, sys, time, warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
from statsmodels.tsa.stattools import adfuller
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.stats.diagnostic import acorr_ljungbox

warnings.filterwarnings("ignore")
FAST = "--fast" in sys.argv

ROOT = Path(__file__).parent
DATA = ROOT / "data"
OUT = ROOT / "outputs"
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

CITIES = {  # name: (lat, lon) used in the NASA POWER request
    "Bengaluru": (12.97, 77.59), "Delhi": (28.61, 77.21), "Mumbai": (19.08, 72.88),
    "Chennai": (13.08, 80.27), "Jodhpur": (26.24, 73.02),
}
MAIN = "Bengaluru"
START, END = "2000-01-01", "2026-07-30"
M = 52                       # weekly seasonal period
EXOG = ["rh", "temp", "cloud"]
MONSOON = {6, 7, 8, 9}       # Jun-Sep, the all-India SW monsoon months

# ---------------------------------------------------------------- plotting theme
# Dark theme from the dataviz reference palette (dark column). Series colours are
# assigned by entity and never change between charts:
C_SURF, C_PAGE = "#1a1a19", "#0d0d0d"
C_INK, C_INK2, C_MUTE, C_GRID, C_AXIS = "#f0efec", "#c3c2b7", "#898781", "#2c2c2a", "#383835"
C_ACTUAL, C_SARIMA, C_SARIMAX, C_PERSIST = "#3987e5", "#d95926", "#199e70", "#c98500"
plt.rcParams.update({
    "figure.facecolor": C_SURF, "axes.facecolor": C_SURF, "savefig.facecolor": C_SURF,
    "text.color": C_INK, "axes.labelcolor": C_INK2, "axes.edgecolor": C_AXIS,
    "xtick.color": C_MUTE, "ytick.color": C_MUTE, "grid.color": C_GRID, "grid.linestyle": "-",
    "grid.linewidth": 0.6, "axes.grid": True, "axes.spines.top": False, "axes.spines.right": False,
    "font.family": "sans-serif", "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
    "legend.frameon": False, "lines.linewidth": 1.6, "figure.dpi": 110, "savefig.dpi": 150,
})

def savefig(name):
    plt.tight_layout()
    plt.savefig(FIG / name)
    plt.close()
    print(f"   fig -> {name}")

# ---------------------------------------------------------------- 1. data loading
def load_city(name):
    """Parse one NASA POWER CSV (header block + YEAR,MO,DY,... table)."""
    lines = (DATA / f"{name}.csv").read_text(encoding="utf-8").split("\n")
    i = next(k for k, l in enumerate(lines) if l.startswith("YEAR"))
    df = pd.read_csv(io.StringIO("\n".join(lines[i:]))).dropna(subset=["YEAR"])
    df["date"] = pd.to_datetime(dict(year=df.YEAR, month=df.MO, day=df.DY))
    df = (df.set_index("date")[["ALLSKY_SFC_SW_DWN", "RH2M", "T2M", "CLOUD_AMT"]]
            .rename(columns={"ALLSKY_SFC_SW_DWN": "solar", "RH2M": "rh", "T2M": "temp", "CLOUD_AMT": "cloud"})
            .replace(-999.0, np.nan))
    return df.loc[START:END]

def prepare(name):
    """Daily -> cleaned daily + weekly means. Returns (daily, weekly, info)."""
    d = load_city(name)
    info = {"daily_rows": int(len(d)), "missing_before": {c: int(d[c].isna().sum()) for c in d}}
    # Missing-value policy: gaps are isolated single days inside a smooth physical
    # series, so linear time-interpolation is the least distorting choice
    # (forward-fill would repeat yesterday's weather; dropping would break the
    # daily frequency needed for weekly resampling).
    d = d.interpolate(method="time", limit_direction="both")
    info["missing_after"] = {c: int(d[c].isna().sum()) for c in d}
    # Weekly means over full Monday-Sunday weeks only
    cnt = d["solar"].resample("W-SUN").count()
    w = d.resample("W-SUN").mean()[cnt == 7].asfreq("W-SUN")
    info["weekly_rows"] = int(len(w))
    info["weekly_missing_weeks"] = int(w["solar"].isna().sum())
    w = w.interpolate(method="time")
    return d, w, info

def metrics(y, yhat):
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    e = y - yhat
    return {"MAE": float(np.mean(np.abs(e))),
            "RMSE": float(np.sqrt(np.mean(e ** 2))),
            "MAPE": float(np.mean(np.abs(e / y)) * 100)}

def season_metrics(y, yhat):
    idx = y.index
    mon = idx.month.isin(list(MONSOON))
    return {"overall": metrics(y, yhat),
            "monsoon_JJAS": metrics(y[mon], np.asarray(yhat)[mon]),
            "dry_rest": metrics(y[~mon], np.asarray(yhat)[~mon])}

def dm_test(e1, e2):
    """Diebold-Mariano test, squared-error loss, h=1 (no autocorrelation correction
    needed for one-step errors). Negative DM => model 1 (first) has LOWER loss."""
    d = np.asarray(e1) ** 2 - np.asarray(e2) ** 2
    dm = d.mean() / np.sqrt(d.var(ddof=1) / len(d))
    p = 2 * (1 - stats.norm.cdf(abs(dm)))
    return {"DM": float(dm), "p_value": float(p), "n": int(len(d))}

def rolling_one_step(res, y_train, y_test, X_train=None, X_test=None):
    """One-week-ahead forecasts over the test block with the parameters FIXED at their
    training-sample estimates. Running the Kalman filter once over train+test and
    reading the in-sample one-step-ahead predictions for the test weeks is exactly
    equivalent to re-anchoring on each new observation and forecasting one step
    (every prediction uses only data up to the previous week), but runs in seconds
    instead of re-filtering the whole history 280 times.
    Returns mean, lower95, upper95 arrays."""
    y_full = pd.concat([y_train, y_test])
    X_full = None if X_train is None else pd.concat([X_train, X_test])
    applied = res.apply(y_full, exog=X_full, refit=False)
    pred = applied.get_prediction(start=len(y_train), end=len(y_full) - 1, dynamic=False)
    ci = pred.conf_int(alpha=0.05)
    return (pred.predicted_mean.values, ci.iloc[:, 0].values, ci.iloc[:, 1].values)

def fit(y, order, sorder, X=None):
    t0 = time.time()
    mod = SARIMAX(y, exog=X, order=order, seasonal_order=sorder,
                  enforce_stationarity=False, enforce_invertibility=False)
    res = mod.fit(disp=False, method="lbfgs", maxiter=300)
    return res, time.time() - t0

def lagged_exog(w, lags=(1,), scaler=None):
    """Lagged, standardised weather regressors. Only PAST weeks are used, so the
    one-week-ahead forecast never sees the target week's weather."""
    cols = {}
    for L in lags:
        for c in EXOG:
            cols[f"{c}_lag{L}"] = w[c].shift(L)
    X = pd.DataFrame(cols, index=w.index)
    return X

# ============================================================== MAIN CITY PIPELINE
R = {"meta": {"main_city": MAIN, "window": [START, END], "seasonal_period": M,
              "exog": EXOG, "monsoon_months": sorted(MONSOON), "cities": CITIES,
              "run_date": pd.Timestamp.today().strftime("%Y-%m-%d"), "fast": FAST}}

print(f"== Phase 2: data preparation ({MAIN})")
daily, weekly, info = prepare(MAIN)
R["data"] = info
print("   daily rows:", info["daily_rows"], "| missing before:", info["missing_before"])
print("   weekly rows:", info["weekly_rows"], "| missing weeks:", info["weekly_missing_weeks"])

# Build exog (lag 1) and drop the first week so y and X share one sample
X_all = lagged_exog(weekly, lags=(1,))
y_all = weekly["solar"]
keep = X_all.notna().all(axis=1)
y_all, X_all = y_all[keep], X_all[keep]
n = len(y_all); ntr = int(0.8 * n)
y_tr, y_te = y_all.iloc[:ntr], y_all.iloc[ntr:]
mu, sd = X_all.iloc[:ntr].mean(), X_all.iloc[:ntr].std()     # scale with TRAIN stats only
X_std = (X_all - mu) / sd
X_tr, X_te = X_std.iloc[:ntr], X_std.iloc[ntr:]
R["split"] = {"n_weeks": n, "n_train": ntr, "n_test": n - ntr,
              "train_range": [str(y_tr.index[0].date()), str(y_tr.index[-1].date())],
              "test_range": [str(y_te.index[0].date()), str(y_te.index[-1].date())]}
print(f"   split: train {R['split']['train_range']}  test {R['split']['test_range']}")

# --- descriptive statistics
R["stats"] = {"mean": float(y_all.mean()), "std": float(y_all.std()), "min": float(y_all.min()),
              "max": float(y_all.max()),
              "trend_slope_per_year": float(np.polyfit(np.arange(n) / 52.18, y_all.values, 1)[0])}

# --- plot: raw daily + weekly
fig, ax = plt.subplots(figsize=(12, 4))
ax.plot(daily.index, daily["solar"], color=C_ACTUAL, alpha=0.35, lw=0.6, label="Daily")
ax.plot(weekly.index, weekly["solar"], color=C_ACTUAL, lw=1.4, label="Weekly mean")
ax.set_title(f"{MAIN}: daily all-sky surface solar radiation, {START[:4]}-{END[:4]}")
ax.set_xlabel("Date"); ax.set_ylabel("kWh / m² / day"); ax.legend(loc="upper right")
ax.annotate("Pre-monsoon peak (Mar-May)", xy=(pd.Timestamp("2010-04-15"), 7.3), color=C_INK2, fontsize=9)
ax.annotate("Monsoon / NE-monsoon trough (Jun-Nov)", xy=(pd.Timestamp("2010-07-15"), 1.2), color=C_INK2, fontsize=9)
savefig("01_raw_series.png")

# --- decomposition (period 52)
dec = seasonal_decompose(y_tr, model="additive", period=M)
fig, axs = plt.subplots(4, 1, figsize=(12, 8), sharex=True)
for a, (s, t) in zip(axs, [(y_tr, "Observed (weekly)"), (dec.trend, "Trend"), (dec.seasonal, "Seasonal (52-week)"), (dec.resid, "Residual")]):
    a.plot(s.index, s.values, color=C_ACTUAL, lw=1.2); a.set_title(t, loc="left", fontsize=10)
axs[-1].set_xlabel("Date"); fig.suptitle("Classical additive decomposition of the training series", fontweight="bold")
savefig("02_decomposition.png")
R["decomposition"] = {"seasonal_amplitude": float(dec.seasonal.max() - dec.seasonal.min()),
                      "trend_range": [float(dec.trend.min()), float(dec.trend.max())]}

# --- ADF tests
def adf(series, label):
    r = adfuller(series.dropna(), autolag="AIC")
    out = {"label": label, "adf_stat": float(r[0]), "p_value": float(r[1]), "lags_used": int(r[2]),
           "n_obs": int(r[3]), "crit_5pct": float(r[4]["5%"]), "stationary_5pct": bool(r[1] < 0.05)}
    print(f"   ADF [{label}]: stat={r[0]:.3f} p={r[1]:.4f} -> {'stationary' if r[1] < .05 else 'NON-stationary'}")
    return out
R["adf"] = {"level": adf(y_tr, "weekly level"),
            "seasonal_diff": adf(y_tr.diff(M), "seasonal difference (lag 52)")}
d_order = 0 if R["adf"]["level"]["stationary_5pct"] else 1
R["adf"]["action"] = (f"ADF rejects a unit root at the level (p={R['adf']['level']['p_value']:.4f}), so d={d_order}. "
                      "The ACF still shows a dominant 52-week cycle that a unit-root test is blind to, "
                      "so one seasonal difference (D=1, m=52) is applied; the differenced series is also stationary.")

# --- ACF / PACF
fig, axs = plt.subplots(2, 2, figsize=(12, 7))
plot_acf(y_tr, lags=120, ax=axs[0, 0], color=C_ACTUAL, vlines_kwargs={"colors": C_ACTUAL}); axs[0, 0].set_title("ACF - weekly level (lags 0-120)")
plot_pacf(y_tr, lags=60, ax=axs[0, 1], method="ywm", color=C_ACTUAL, vlines_kwargs={"colors": C_ACTUAL}); axs[0, 1].set_title("PACF - weekly level")
yd = y_tr.diff(M).dropna()
plot_acf(yd, lags=120, ax=axs[1, 0], color=C_SARIMA, vlines_kwargs={"colors": C_SARIMA}); axs[1, 0].set_title("ACF - after seasonal difference (D=1, m=52)")
plot_pacf(yd, lags=60, ax=axs[1, 1], method="ywm", color=C_SARIMA, vlines_kwargs={"colors": C_SARIMA}); axs[1, 1].set_title("PACF - after seasonal difference")
for a in axs.flat:
    for coll in a.collections: coll.set_alpha(0.25)
savefig("03_acf_pacf.png")

# --- split plot
fig, ax = plt.subplots(figsize=(12, 4))
ax.plot(y_tr.index, y_tr, color=C_ACTUAL, label=f"Train (80%, {ntr} weeks)")
ax.plot(y_te.index, y_te, color=C_MUTE, label=f"Test (20%, {n-ntr} weeks)")
ax.axvline(y_te.index[0], color=C_INK2, lw=0.8); ax.text(y_te.index[0], 7.6, " split", color=C_INK2, fontsize=9)
ax.set_title("Train / test split (chronological)"); ax.set_xlabel("Date"); ax.set_ylabel("kWh / m² / day"); ax.legend(loc="lower left")
savefig("04_train_test_split.png")

# ============================================================== Phase 3: SARIMA
print("== Phase 3: SARIMA baseline - AIC grid")
# Candidate set is read off the ACF/PACF: after seasonal differencing the ACF has a
# single negative spike at lag 52 (-> seasonal MA(1)) and short-lag decay (-> low-order
# AR/MA). We keep the grid small because each m=52 fit is expensive.
cands = [((1, d_order, 0), (0, 1, 1, M)), ((0, d_order, 1), (0, 1, 1, M)), ((1, d_order, 1), (0, 1, 1, M)),
         ((2, d_order, 0), (0, 1, 1, M)), ((1, d_order, 1), (1, 1, 0, M)), ((1, d_order, 1), (1, 1, 1, M))]
grid = []
best = None
for o, so in cands:
    res, secs = fit(y_tr, o, so)
    row = {"order": o, "seasonal_order": so, "AIC": float(res.aic), "BIC": float(res.bic), "fit_seconds": round(secs, 1)}
    grid.append(row); print(f"   SARIMA{o}x{so}: AIC={res.aic:.1f} ({secs:.0f}s)")
    if best is None or res.aic < best[0].aic: best = (res, o, so)
sar_res, SAR_O, SAR_SO = best
R["sarima"] = {"grid": grid, "order": SAR_O, "seasonal_order": SAR_SO, "AIC": float(sar_res.aic),
               "params": {k: float(v) for k, v in sar_res.params.items()}}
lb = acorr_ljungbox(sar_res.resid.iloc[M + 5:], lags=[10, 26, 52], return_df=True)
R["sarima"]["ljung_box"] = {str(k): float(v) for k, v in lb["lb_pvalue"].items()}

print("   rolling one-step forecasts on test...")
sar_m, sar_lo, sar_hi = rolling_one_step(sar_res, y_tr, y_te)
R["sarima"]["metrics"] = season_metrics(y_te, sar_m)
# static multi-step forecast over the whole test horizon
sf = sar_res.get_forecast(steps=len(y_te))
sar_static = sf.predicted_mean.values; sci = sf.conf_int(alpha=0.05).values
R["sarima"]["static_metrics"] = metrics(y_te, sar_static)
print(f"   SARIMA rolling: {R['sarima']['metrics']['overall']}")
print(f"   SARIMA static : {R['sarima']['static_metrics']}")

# naive & seasonal-naive benchmarks
naive = y_all.shift(1).loc[y_te.index].values
snaive = y_all.shift(M).loc[y_te.index].values
R["benchmarks"] = {"naive_lastweek": season_metrics(y_te, naive), "seasonal_naive_52": season_metrics(y_te, snaive)}

def plot_fit(name, mean, lo, hi, color, fname, extra=None):
    fig, ax = plt.subplots(figsize=(12, 4.2))
    ax.fill_between(y_te.index, lo, hi, color=color, alpha=0.18, lw=0, label="95% interval")
    ax.plot(y_te.index, y_te, color=C_ACTUAL, label="Actual")
    ax.plot(y_te.index, mean, color=color, label=f"{name} forecast (1-week-ahead, rolling)")
    if extra is not None: ax.plot(y_te.index, extra[0], color=color, lw=1, alpha=0.6, ls="--", label=extra[1])
    ax.set_title(f"{name}: actual vs forecast on the test block"); ax.set_xlabel("Date"); ax.set_ylabel("kWh / m² / day")
    ax.legend(loc="lower left", ncol=2); savefig(fname)

plot_fit("SARIMA", sar_m, sar_lo, sar_hi, C_SARIMA, "05_sarima_forecast.png", extra=(sar_static, "static multi-step forecast"))
res_sar = y_te.values - sar_m
fig, axs = plt.subplots(1, 2, figsize=(12, 3.8), gridspec_kw={"width_ratios": [3, 1]})
axs[0].plot(y_te.index, res_sar, color=C_SARIMA, lw=1); axs[0].axhline(0, color=C_AXIS); axs[0].set_title("SARIMA one-step residuals"); axs[0].set_xlabel("Date")
axs[1].hist(res_sar, bins=30, color=C_SARIMA, alpha=0.85); axs[1].set_title("Residual distribution"); axs[1].set_xlabel("Residual")
savefig("06_sarima_residuals.png")

# ============================================================== Phase 4: SARIMAX
print("== Phase 4: SARIMAX with lagged weather covariates")
sax_res, secs = fit(y_tr, SAR_O, SAR_SO, X_tr)
print(f"   fitted in {secs:.0f}s, AIC={sax_res.aic:.1f}")
sax_m, sax_lo, sax_hi = rolling_one_step(sax_res, y_tr, y_te, X_tr, X_te)
R["sarimax"] = {"order": SAR_O, "seasonal_order": SAR_SO, "AIC": float(sax_res.aic), "exog": list(X_tr.columns),
                "exog_coef": {k: {"coef": float(sax_res.params[k]), "p_value": float(sax_res.pvalues[k])} for k in X_tr.columns},
                "metrics": season_metrics(y_te, sax_m)}
print(f"   SARIMAX rolling: {R['sarimax']['metrics']['overall']}")
print("   exog coefficients:", {k: round(v["coef"], 3) for k, v in R["sarimax"]["exog_coef"].items()})
plot_fit("SARIMAX", sax_m, sax_lo, sax_hi, C_SARIMAX, "07_sarimax_forecast.png")
res_sax = y_te.values - sax_m
fig, axs = plt.subplots(1, 2, figsize=(12, 3.8), gridspec_kw={"width_ratios": [3, 1]})
axs[0].plot(y_te.index, res_sax, color=C_SARIMAX, lw=1); axs[0].axhline(0, color=C_AXIS); axs[0].set_title("SARIMAX one-step residuals"); axs[0].set_xlabel("Date")
axs[1].hist(res_sax, bins=30, color=C_SARIMAX, alpha=0.85); axs[1].set_title("Residual distribution"); axs[1].set_xlabel("Residual")
savefig("08_sarimax_residuals.png")

# side-by-side (zoom on the last 2 years so the lines are readable)
z = y_te.index >= (y_te.index[-1] - pd.Timedelta(weeks=104))
fig, axs = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
for a, (nm, mval, col) in zip(axs, [("SARIMA", sar_m, C_SARIMA), ("SARIMAX (lagged weather)", sax_m, C_SARIMAX)]):
    a.plot(y_te.index[z], y_te[z], color=C_ACTUAL, label="Actual"); a.plot(y_te.index[z], mval[z], color=col, label=nm)
    a.set_title(f"{nm} - last 104 test weeks", loc="left", fontsize=10); a.legend(loc="lower left"); a.set_ylabel("kWh / m² / day")
axs[-1].set_xlabel("Date"); savefig("09_side_by_side.png")

# ============================================================== Phase 5: comparison
R["dm_tests"] = {"sarima_vs_sarimax": dm_test(res_sar, res_sax),
                 "snaive_vs_sarima": dm_test(y_te.values - snaive, res_sar),
                 "snaive_vs_sarimax": dm_test(y_te.values - snaive, res_sax)}
imp = {k: (R["sarima"]["metrics"]["overall"][k] - R["sarimax"]["metrics"]["overall"][k]) / R["sarima"]["metrics"]["overall"][k] * 100 for k in ("MAE", "RMSE", "MAPE")}
R["improvement_pct"] = imp
print("   improvement % (SARIMA -> SARIMAX):", {k: round(v, 2) for k, v in imp.items()})
print("   DM SARIMA vs SARIMAX:", R["dm_tests"]["sarima_vs_sarimax"])

labels = ["Seasonal naive", "Naive (last week)", "SARIMA", "SARIMAX"]
vals = [R["benchmarks"]["seasonal_naive_52"]["overall"], R["benchmarks"]["naive_lastweek"]["overall"],
        R["sarima"]["metrics"]["overall"], R["sarimax"]["metrics"]["overall"]]
cols = [C_MUTE, C_PERSIST, C_SARIMA, C_SARIMAX]
fig, axs = plt.subplots(1, 3, figsize=(12, 3.8))
for a, k in zip(axs, ["MAE", "RMSE", "MAPE"]):
    v = [m[k] for m in vals]; b = a.bar(labels, v, color=cols, width=0.6)
    for bi, vi in zip(b, v): a.text(bi.get_x() + bi.get_width() / 2, vi, f"{vi:.3f}" if k != "MAPE" else f"{vi:.2f}%", ha="center", va="bottom", fontsize=9, color=C_INK)
    a.set_title(k); a.tick_params(axis="x", labelrotation=20); a.grid(axis="x", visible=False)
fig.suptitle("Test-block error, rolling one-week-ahead", fontweight="bold"); savefig("10_metric_comparison.png")

fig, axs = plt.subplots(1, 2, figsize=(12, 3.8), sharey=True)
for a, seg, ttl in zip(axs, ["monsoon_JJAS", "dry_rest"], ["Monsoon weeks (Jun-Sep)", "Other weeks"]):
    v = [R["sarima"]["metrics"][seg]["MAE"], R["sarimax"]["metrics"][seg]["MAE"], R["benchmarks"]["seasonal_naive_52"][seg]["MAE"]]
    b = a.bar(["SARIMA", "SARIMAX", "Seasonal naive"], v, color=[C_SARIMA, C_SARIMAX, C_MUTE], width=0.55)
    for bi, vi in zip(b, v): a.text(bi.get_x() + bi.get_width() / 2, vi, f"{vi:.3f}", ha="center", va="bottom", fontsize=9)
    a.set_title(ttl); a.grid(axis="x", visible=False)
axs[0].set_ylabel("MAE (kWh / m² / day)"); fig.suptitle("Error by season", fontweight="bold"); savefig("11_seasonal_error.png")

# ============================================================== robustness + extensions
R["cities"] = {}
R["extensions"] = {}
if not FAST:
    print("== Robustness: other four cities (same orders, rolling one-step)")
    for city in CITIES:
        if city == MAIN: continue
        _, w, inf = prepare(city)
        Xa = lagged_exog(w, lags=(1,)); ya = w["solar"]; k = Xa.notna().all(axis=1); ya, Xa = ya[k], Xa[k]
        nn = len(ya); nt = int(0.8 * nn); ytr, yte = ya.iloc[:nt], ya.iloc[nt:]
        Xs = (Xa - Xa.iloc[:nt].mean()) / Xa.iloc[:nt].std(); Xtr, Xte = Xs.iloc[:nt], Xs.iloc[nt:]
        r1, s1 = fit(ytr, SAR_O, SAR_SO); m1, _, _ = rolling_one_step(r1, ytr, yte)
        r2, s2 = fit(ytr, SAR_O, SAR_SO, Xtr); m2, _, _ = rolling_one_step(r2, ytr, yte, Xtr, Xte)
        sn = ya.shift(M).loc[yte.index].values
        R["cities"][city] = {"n_weeks": nn, "n_test": nn - nt, "missing_before": inf["missing_before"],
                             "sarima": season_metrics(yte, m1), "sarimax": season_metrics(yte, m2),
                             "seasonal_naive": season_metrics(yte, sn), "dm_sarima_vs_sarimax": dm_test(yte.values - m1, yte.values - m2),
                             "exog_coef": {c: float(r2.params[c]) for c in Xtr.columns}}
        print(f"   {city}: SARIMA MAE={R['cities'][city]['sarima']['overall']['MAE']:.3f}  SARIMAX MAE={R['cities'][city]['sarimax']['overall']['MAE']:.3f}  ({s1 + s2:.0f}s)")
    R["cities"][MAIN] = {"n_weeks": n, "n_test": n - ntr, "missing_before": info["missing_before"], "sarima": R["sarima"]["metrics"],
                         "sarimax": R["sarimax"]["metrics"], "seasonal_naive": R["benchmarks"]["seasonal_naive_52"],
                         "dm_sarima_vs_sarimax": R["dm_tests"]["sarima_vs_sarimax"], "exog_coef": {k: v["coef"] for k, v in R["sarimax"]["exog_coef"].items()}}

    # city comparison figure (MAE by model, one panel per metric; colour follows the model)
    cities = list(R["cities"]); x = np.arange(len(cities)); wbar = 0.26
    fig, ax = plt.subplots(figsize=(12, 4))
    for j, (nm, key, col) in enumerate([("Seasonal naive", "seasonal_naive", C_MUTE), ("SARIMA", "sarima", C_SARIMA), ("SARIMAX", "sarimax", C_SARIMAX)]):
        v = [R["cities"][c][key]["overall"]["MAE"] for c in cities]
        ax.bar(x + (j - 1) * wbar, v, wbar - 0.02, color=col, label=nm)
    ax.set_xticks(x, cities); ax.set_ylabel("MAE (kWh / m² / day)"); ax.set_title("Robustness across five cities - test MAE, rolling one-week-ahead")
    ax.legend(ncol=3, loc="upper left"); ax.grid(axis="x", visible=False); savefig("12_city_robustness.png")

    print("== Extensions (future-work ideas, implemented)")
    # E1 - richer lag structure: lags 1, 2 and 52 of each weather variable
    Xb = lagged_exog(weekly, lags=(1, 2, 52)); kb = Xb.notna().all(axis=1)
    yb = weekly["solar"][kb]; Xb = Xb[kb]; nb = len(yb); ntb = nb - (n - ntr)        # keep the SAME test weeks
    Xbs = (Xb - Xb.iloc[:ntb].mean()) / Xb.iloc[:ntb].std()
    rE1, sE1 = fit(yb.iloc[:ntb], SAR_O, SAR_SO, Xbs.iloc[:ntb]); mE1, _, _ = rolling_one_step(rE1, yb.iloc[:ntb], yb.iloc[ntb:], Xbs.iloc[:ntb], Xbs.iloc[ntb:])
    assert (yb.iloc[ntb:].index == y_te.index).all()
    R["extensions"]["E1_multi_lag_exog"] = {"desc": "SARIMAX with lags 1, 2 and 52 of humidity, temperature and cloud (9 regressors)",
                                            "metrics": season_metrics(y_te, mE1), "dm_vs_sarimax": dm_test(res_sax, y_te.values - mE1), "fit_seconds": round(sE1, 1)}
    print(f"   E1 multi-lag  MAE={R['extensions']['E1_multi_lag_exog']['metrics']['overall']['MAE']:.3f}")
    # E2 - log transform (variance stabilisation; monsoon weeks are more volatile)
    rE2, sE2 = fit(np.log(y_tr), SAR_O, SAR_SO, X_tr); mE2, _, _ = rolling_one_step(rE2, np.log(y_tr), np.log(y_te), X_tr, X_te); mE2 = np.exp(mE2)
    R["extensions"]["E2_log_sarimax"] = {"desc": "SARIMAX fitted on log(solar) and back-transformed",
                                         "metrics": season_metrics(y_te, mE2), "dm_vs_sarimax": dm_test(res_sax, y_te.values - mE2), "fit_seconds": round(sE2, 1)}
    print(f"   E2 log-SARIMAX MAE={R['extensions']['E2_log_sarimax']['metrics']['overall']['MAE']:.3f}")
    # E3 - simple ensemble of SARIMA and SARIMAX one-step forecasts
    mE3 = 0.5 * (sar_m + sax_m)
    R["extensions"]["E3_ensemble_mean"] = {"desc": "Equal-weight average of the SARIMA and SARIMAX one-step forecasts",
                                           "metrics": season_metrics(y_te, mE3), "dm_vs_sarimax": dm_test(res_sax, y_te.values - mE3), "fit_seconds": 0}
    print(f"   E3 ensemble   MAE={R['extensions']['E3_ensemble_mean']['metrics']['overall']['MAE']:.3f}")

# ============================================================== export
R["series"] = {
    "weekly_dates": [str(d.date()) for d in y_all.index], "weekly_solar": [round(float(v), 4) for v in y_all.values],
    "daily_dates": [str(d.date()) for d in daily.index], "daily_solar": [round(float(v), 3) for v in daily["solar"].values],
    "test_dates": [str(d.date()) for d in y_te.index], "test_actual": [round(float(v), 4) for v in y_te.values],
    "sarima_mean": sar_m.round(4).tolist(), "sarima_lo": sar_lo.round(4).tolist(), "sarima_hi": sar_hi.round(4).tolist(),
    "sarima_static": sar_static.round(4).tolist(), "sarima_static_lo": sci[:, 0].round(4).tolist(), "sarima_static_hi": sci[:, 1].round(4).tolist(),
    "sarimax_mean": sax_m.round(4).tolist(), "sarimax_lo": sax_lo.round(4).tolist(), "sarimax_hi": sax_hi.round(4).tolist(),
    "seasonal_naive": np.round(snaive, 4).tolist(),
    "acf_level": [float(v) for v in __import__("statsmodels.tsa.stattools", fromlist=["acf"]).acf(y_tr, nlags=120)],
    "acf_sdiff": [float(v) for v in __import__("statsmodels.tsa.stattools", fromlist=["acf"]).acf(yd, nlags=120)],
    "pacf_level": [float(v) for v in __import__("statsmodels.tsa.stattools", fromlist=["pacf"]).pacf(y_tr, nlags=60, method="ywm")],
    "pacf_sdiff": [float(v) for v in __import__("statsmodels.tsa.stattools", fromlist=["pacf"]).pacf(yd, nlags=60, method="ywm")],
    "decomp_dates": [str(d.date()) for d in y_tr.index], "decomp_trend": [None if np.isnan(v) else round(float(v), 4) for v in dec.trend.values],
    "decomp_seasonal": [round(float(v), 4) for v in dec.seasonal.values], "decomp_resid": [None if np.isnan(v) else round(float(v), 4) for v in dec.resid.values],
}
(OUT / "results.json").write_text(json.dumps(R, indent=1, default=str), encoding="utf-8")

rows = [("Seasonal naive (t-52)", R["benchmarks"]["seasonal_naive_52"]["overall"]), ("Naive (t-1)", R["benchmarks"]["naive_lastweek"]["overall"]),
        ("SARIMA (baseline)", R["sarima"]["metrics"]["overall"]), ("SARIMAX (improved)", R["sarimax"]["metrics"]["overall"])]
for k, v in R["extensions"].items(): rows.append((k, v["metrics"]["overall"]))
pd.DataFrame([{"model": a, **b} for a, b in rows]).to_csv(OUT / "metrics_table.csv", index=False)
print("== done. results.json + metrics_table.csv written to outputs/")
