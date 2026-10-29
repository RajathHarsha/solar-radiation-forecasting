# Weekly Solar Radiation Forecasting Across Five Indian Cities

SARIMA vs weather-aware SARIMAX, built for the Time Series Analysis (24AM7PCTSA) Lab AAT at B.M.S. College of Engineering.

The project asks one question: does adding last week's humidity, temperature and cloud cover improve a one-week-ahead forecast of solar radiation, compared with a seasonal ARIMA model that uses the radiation history alone? It tests this for Bengaluru, Delhi, Mumbai, Chennai and Jodhpur, using NASA POWER weekly data from 2000 to July 2026.

## Headline result

For Bengaluru, SARIMAX lowered the MAE by only about 1.5% compared with SARIMA, and that difference is **not statistically significant** (Diebold-Mariano p = 0.15). In Delhi, Mumbai and Chennai SARIMAX was slightly worse, and no city showed a significant difference. Both models are roughly a quarter more accurate than guessing "same week as last year". No LSTM was built.

The radiation values are NASA POWER satellite and reanalysis estimates, not ground-station readings.

## Live dashboard

https://rajathharsha.github.io/solar-radiation-forecasting/

(Served by GitHub Pages from the main branch. It needs internet to load the chart libraries.)

## What to open

- `dashboard.html`: an interactive dashboard. Double-click it to open in a browser. It needs internet only to load the chart libraries. Pick a city at the top and every section updates.
- `REPORT.md`: a short written summary of the data, method and results.

## Re-running the analysis

Needs Python 3.10+ and:

```
pip install pandas numpy scipy statsmodels matplotlib
```

From the repository folder:

```
python analysis.py              # about 30-40 minutes; rebuilds outputs/results.json and figures
python export_city_data.py      # about 15-25 minutes; rebuilds outputs/city_data.json
python export_weekly_raw.py     # a few seconds; rebuilds outputs/weekly_raw.json
python make_dashboard2.py       # a few seconds; rebuilds dashboard.html
```

Keep the files together: the scripts read `data/` and `outputs/` next to them, and `make_dashboard2.py` also reads `make_dashboard.py` for the paper list.

## Files

| Path | Purpose |
|---|---|
| `data/` | The five NASA POWER CSV files (1984-2026), one per city |
| `outputs/` | `results.json`, `city_data.json`, `weekly_raw.json`, `metrics_table.csv` and 12 figures |
| `analysis.py` | Full pipeline for the main city (Bengaluru) plus robustness cities |
| `export_city_data.py` | Per-city forecasts used by the dashboard |
| `export_weekly_raw.py` | Weekly temperature, humidity and cloud values for the dataset table |
| `make_dashboard.py` | Holds the literature text (five papers checked against their abstracts) |
| `make_dashboard2.py` | Builds `dashboard.html` from `dashboard_template.html` and the outputs |
| `dashboard_template.html` | The dashboard's HTML, CSS and JavaScript template |

## Data source

NASA POWER (Prediction Of Worldwide Energy Resources), https://power.larc.nasa.gov/. Please credit NASA POWER when using the data.

## Limitations

One grid point represents each city, results use a single chronological train/test split, the weather inputs are last week's observed values (not weather forecasts), and the literature review covers five papers and is not exhaustive.
