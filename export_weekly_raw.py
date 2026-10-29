"""Weekly temperature / humidity / cloud for the dataset table (same weekly construction as export_city_data.py).
Writes outputs/weekly_raw.json and asserts the weeks and radiation values match city_data.json exactly."""
import io, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).parent; DATA = ROOT / "data"; OUT = ROOT / "outputs"
D = json.loads((OUT / "city_data.json").read_text(encoding="utf-8"))
START, END = "2000-01-01", "2026-07-30"
res = {}
for city in D["meta"]["cities"]:
    lines = (DATA / f"{city}.csv").read_text(encoding="utf-8").split("\n")
    i = next(k for k, l in enumerate(lines) if l.startswith("YEAR"))
    df = pd.read_csv(io.StringIO("\n".join(lines[i:]))).dropna(subset=["YEAR"])
    df["date"] = pd.to_datetime(dict(year=df.YEAR, month=df.MO, day=df.DY))
    d = (df.set_index("date")[["ALLSKY_SFC_SW_DWN", "RH2M", "T2M", "CLOUD_AMT"]]
           .rename(columns={"ALLSKY_SFC_SW_DWN": "solar", "RH2M": "rh", "T2M": "temp", "CLOUD_AMT": "cloud"})
           .replace(-999.0, np.nan).loc[START:END].interpolate(method="time", limit_direction="both"))
    cnt = d["solar"].resample("W-SUN").count()
    w = d.resample("W-SUN").mean()[cnt == 7].asfreq("W-SUN").interpolate(method="time")
    keep = pd.DataFrame({c: w[c].shift(1) for c in ("rh", "temp", "cloud")}).notna().all(axis=1)   # same rows as the modelling sample
    w = w[keep]
    dates = [str(t.date()) for t in w.index]
    assert dates == D["city"][city]["dates"], city
    assert np.allclose(np.round(w["solar"].values, 4), D["city"][city]["solar"]), city
    res[city] = {"t": [round(float(v), 2) for v in w["temp"]], "rh": [round(float(v), 2) for v in w["rh"]], "c": [round(float(v), 2) for v in w["cloud"]]}
    print(city, len(dates), "weeks; temp", min(res[city]["t"]), max(res[city]["t"]), "| cloud", min(res[city]["c"]), max(res[city]["c"]))
(OUT / "weekly_raw.json").write_text(json.dumps(res, separators=(",", ":")), encoding="utf-8")
print("wrote outputs/weekly_raw.json", (OUT / "weekly_raw.json").stat().st_size // 1024, "KB")
