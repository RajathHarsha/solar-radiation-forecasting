"""Export everything the redesigned dashboard needs, for ALL five cities, to outputs/city_data.json.
Same design as analysis.py: weekly means, m=52, SARIMA(1,0,1)x(0,1,1,52), SARIMAX = same orders + lag-1
humidity/temperature/cloud (standardised on train), chronological 80/20 split, one-week-ahead forecasts
with parameters fixed at their training estimates.
Adds: per-city decomposition/ACF/PACF/ADF, test-block forecasts with 95% intervals, an 8-week-ahead SARIMA
forecast from the end of the modelling window, and the REAL weeks that followed (solar is published later than cloud),
so the forecast can be checked against what actually happened."""
import io, json, sys, time, warnings
from pathlib import Path
import numpy as np, pandas as pd
from statsmodels.tsa.stattools import adfuller, acf, pacf
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.statespace.sarimax import SARIMAX
from scipy import stats
warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent; DATA = ROOT / "data"; OUT = ROOT / "outputs"
CITIES = ["Bengaluru", "Delhi", "Mumbai", "Chennai", "Jodhpur"]
START, END = "2000-01-01", "2026-07-30"; M = 52
ORDER, SORDER = (1, 0, 1), (0, 1, 1, 52)
EXOG = ["rh", "temp", "cloud"]; FUT = 8

def load(city):
    lines = (DATA / f"{city}.csv").read_text(encoding="utf-8").split("\n")
    i = next(k for k, l in enumerate(lines) if l.startswith("YEAR"))
    df = pd.read_csv(io.StringIO("\n".join(lines[i:]))).dropna(subset=["YEAR"])
    df["date"] = pd.to_datetime(dict(year=df.YEAR, month=df.MO, day=df.DY))
    return (df.set_index("date")[["ALLSKY_SFC_SW_DWN", "RH2M", "T2M", "CLOUD_AMT"]]
              .rename(columns={"ALLSKY_SFC_SW_DWN": "solar", "RH2M": "rh", "T2M": "temp", "CLOUD_AMT": "cloud"})
              .replace(-999.0, np.nan))

def weekly(d):
    cnt = d["solar"].resample("W-SUN").count()
    return d.resample("W-SUN").mean()[cnt == 7].asfreq("W-SUN")

def metrics(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float); e = y - p
    return {"MAE": float(np.mean(np.abs(e))), "RMSE": float(np.sqrt(np.mean(e ** 2))), "MAPE": float(np.mean(np.abs(e / y)) * 100)}

def one_step(res, ytr, yte, Xtr=None, Xte=None):
    yf = pd.concat([ytr, yte]); Xf = None if Xtr is None else pd.concat([Xtr, Xte])
    pred = res.apply(yf, exog=Xf, refit=False).get_prediction(start=len(ytr), end=len(yf) - 1, dynamic=False)
    ci = pred.conf_int(alpha=0.05)
    return pred.predicted_mean.values, ci.iloc[:, 0].values, ci.iloc[:, 1].values

def fit(y, X=None):
    t0 = time.time()
    r = SARIMAX(y, exog=X, order=ORDER, seasonal_order=SORDER, enforce_stationarity=False,
                enforce_invertibility=False).fit(disp=False, method="lbfgs", maxiter=300)
    return r, time.time() - t0

r2 = lambda a, k=4: [None if (v is None or (isinstance(v, float) and np.isnan(v))) else round(float(v), k) for v in a]
out = {"meta": {"cities": CITIES, "window": [START, END], "m": M, "order": ORDER, "seasonal_order": SORDER,
                "future_weeks": FUT, "generated": pd.Timestamp.today().strftime("%Y-%m-%d")}, "city": {}}

for city in CITIES:
    t_city = time.time(); print("==", city, flush=True)
    raw = load(city)
    d = raw.loc[START:END].interpolate(method="time", limit_direction="both")
    w = weekly(d).interpolate(method="time")
    X = pd.DataFrame({f"{c}_lag1": w[c].shift(1) for c in EXOG}, index=w.index)
    keep = X.notna().all(axis=1); y, X = w["solar"][keep], X[keep]
    n = len(y); ntr = int(0.8 * n); ytr, yte = y.iloc[:ntr], y.iloc[ntr:]
    mu, sd = X.iloc[:ntr].mean(), X.iloc[:ntr].std(); Xs = (X - mu) / sd; Xtr, Xte = Xs.iloc[:ntr], Xs.iloc[ntr:]

    sar, s1 = fit(ytr); sm, slo, shi = one_step(sar, ytr, yte)
    sax, s2 = fit(ytr, Xtr); xm, xlo, xhi = one_step(sax, ytr, yte, Xtr, Xte)
    sn = y.shift(M).loc[yte.index].values; nv = y.shift(1).loc[yte.index].values
    e1, e2 = yte.values - sm, yte.values - xm
    dd = e1 ** 2 - e2 ** 2; dm = dd.mean() / np.sqrt(dd.var(ddof=1) / len(dd)); pv = 2 * (1 - stats.norm.cdf(abs(dm)))
    mon = yte.index.month.isin([6, 7, 8, 9])
    seas = lambda p: {"overall": metrics(yte, p), "monsoon": metrics(yte[mon], np.asarray(p)[mon]), "other": metrics(yte[~mon], np.asarray(p)[~mon])}

    # 8-week-ahead SARIMA forecast from the end of the modelling window (parameters from training, state updated through the end)
    full = sar.apply(y, refit=False)
    fc = full.get_forecast(steps=FUT); fci = fc.conf_int(alpha=0.05)
    last = y.index[-1]; fdates = [last + pd.Timedelta(weeks=i + 1) for i in range(FUT)]
    # what actually happened afterwards (solar exists to ~Oct 2026; cloud does not, so SARIMAX could not be scored there)
    rr = raw.loc[last + pd.Timedelta(days=1):].dropna(subset=["solar"])
    aw = weekly(rr[["solar", "rh", "temp", "cloud"]].ffill())["solar"].dropna() if len(rr) else pd.Series(dtype=float)
    aw = aw[aw.index.isin(fdates)]

    dec = seasonal_decompose(ytr, model="additive", period=M)
    yd = ytr.diff(M).dropna()
    adf_l, adf_d = adfuller(ytr, autolag="AIC"), adfuller(yd, autolag="AIC")
    mm = [float(d["solar"][d.index.month == m].mean()) for m in range(1, 13)]
    wk = (ytr.groupby(ytr.index.isocalendar().week.clip(upper=52)).mean()).reindex(range(1, 53))

    out["city"][city] = {
        "latlon": None, "n_weeks": n, "n_train": ntr, "n_test": n - ntr, "daily_rows": int(len(d)),
        "train_range": [str(ytr.index[0].date()), str(ytr.index[-1].date())], "test_range": [str(yte.index[0].date()), str(yte.index[-1].date())],
        "dates": [str(t.date()) for t in y.index], "solar": r2(y.values),
        "mean": float(y.mean()), "std": float(y.std()), "min": float(y.min()), "max": float(y.max()),
        "trend_per_year": float(np.polyfit(np.arange(n) / 52.18, y.values, 1)[0]),
        "monthly_mean": r2(mm, 3), "week_of_year_mean": r2(wk.values, 3),
        "decomp": {"dates": [str(t.date()) for t in ytr.index], "trend": r2(dec.trend.values), "seasonal": r2(dec.seasonal.values), "resid": r2(dec.resid.values),
                   "amp": float(dec.seasonal.max() - dec.seasonal.min())},
        "acf_level": r2(acf(ytr, nlags=120), 3), "acf_sdiff": r2(acf(yd, nlags=120), 3),
        "pacf_level": r2(pacf(ytr, nlags=60, method="ywm"), 3), "pacf_sdiff": r2(pacf(yd, nlags=60, method="ywm"), 3),
        "adf": {"level": {"stat": float(adf_l[0]), "p": float(adf_l[1])}, "sdiff": {"stat": float(adf_d[0]), "p": float(adf_d[1])}},
        "test": {"dates": [str(t.date()) for t in yte.index], "actual": r2(yte.values),
                 "sarima": r2(sm), "sarima_lo": r2(slo), "sarima_hi": r2(shi), "sarimax": r2(xm), "sarimax_lo": r2(xlo), "sarimax_hi": r2(xhi),
                 "seasonal_naive": r2(sn), "naive": r2(nv)},
        "metrics": {"sarima": seas(sm), "sarimax": seas(xm), "seasonal_naive": seas(sn), "naive": seas(nv)},
        "dm": {"stat": float(dm), "p": float(pv), "n": int(len(dd))},
        "improvement_pct": {k: float((metrics(yte, sm)[k] - metrics(yte, xm)[k]) / metrics(yte, sm)[k] * 100) for k in ("MAE", "RMSE", "MAPE")},
        "sarima_model": {"aic": float(sar.aic), "fit_seconds": round(s1, 1), "params": {k: round(float(v), 4) for k, v in sar.params.items()}},
        "sarimax_model": {"aic": float(sax.aic), "fit_seconds": round(s2, 1),
                          "coef": {k: {"coef": round(float(sax.params[k]), 4), "p": round(float(sax.pvalues[k]), 4)} for k in Xtr.columns}},
        "future": {"dates": [str(t.date()) for t in fdates], "mean": r2(fc.predicted_mean.values), "lo": r2(fci.iloc[:, 0].values), "hi": r2(fci.iloc[:, 1].values),
                   "actual_dates": [str(t.date()) for t in aw.index], "actual": r2(aw.values)},
    }
    print(f"   {city}: SARIMA MAE {metrics(yte, sm)['MAE']:.3f}  SARIMAX MAE {metrics(yte, xm)['MAE']:.3f}  DM p {pv:.3f}  future actual weeks {len(aw)}  ({time.time() - t_city:.0f}s)", flush=True)

(OUT / "city_data.json").write_text(json.dumps(out), encoding="utf-8")
print("== wrote outputs/city_data.json", (OUT / "city_data.json").stat().st_size // 1024, "KB", flush=True)
