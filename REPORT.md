# Weekly Solar Radiation Forecasting Across Five Indian Cities Using SARIMA and Weather-Aware SARIMAX

Time Series Analysis (24AM7PCTSA) - Lab AAT. Generated 2026-10-25 from `analysis.py` (results in `outputs/results.json`).

## 1. Problem and data

- **Goal:** forecast weekly mean all-sky surface solar radiation (kWh/m²/day) one week ahead, and test whether lagged weather information improves a seasonal ARIMA model.
- **Data:** NASA POWER daily point data (MERRA-2 / CERES SYN1deg based - a satellite/reanalysis product, not a ground sensor): `ALLSKY_SFC_SW_DWN`, `RH2M`, `T2M`, `CLOUD_AMT`.
- **Cities (one grid point each):** Bengaluru 12.97N 77.59E (main), Delhi 28.61N 77.21E, Mumbai 19.08N 72.88E, Chennai 13.08N 80.27E, Jodhpur 26.24N 73.02E.
- **Window:** 2000-01-01 to 2026-07-30 (9,708 days -> 1,385 full weeks). `CLOUD_AMT` was not yet published after 2026-07-30, so the window ends there. No missing values inside the window.
- **Resolution:** weekly means (Mon-Sun), seasonal period m = 52. Daily data cannot be fitted with a 365-day seasonal period by SARIMA.
- **Split:** chronological 80/20 - train 2000-01-16 to 2021-04-04 (1,108 weeks), test 2021-04-11 to 2026-07-26 (277 weeks).

## 2. Literature review

The five papers below were checked against CrossRef/OpenAlex (title, authors, journal, year, DOI) and their abstracts were read. The findings are taken from the abstracts only, so read the full papers before citing any detail.

| # | Paper | Relevance and finding (from the abstract) | Limitation for this project |
|---|---|---|---|
| 1 | Inanlougani, A., Reddy, T. A., Katiamula, S. (2017). Evaluation of Time-Series, Regression and Neural Network Models for Solar Forecasting: Part I: One-Hour Horizon. arXiv:1708.08376. | A simple baseline beat seasonal ARIMA for one-hour-ahead forecasts; regression models with cloud cover beat the baseline; neural networks were most accurate. | Hourly horizon only; no weekly forecasts or several climates. |
| 2 | Alsharif, M. H., Younes, M. K., Kim, J. (2019). Time Series ARIMA Model for Prediction of Daily and Monthly Average Global Solar Radiation: The Case Study of Seoul, South Korea. *Symmetry* 11(2), 240. doi:10.3390/sym11020240 | Seasonal ARIMA on 37 years (1981-2017) of Korean data: ARIMA(1,1,2) daily, seasonal ARIMA(4,1,1) monthly; RMSE and R². | Radiation history only; one city; no persistence benchmark described. |
| 3 | Sheoran, S., Singh, R. S., Pasari, S., Kulshrestha, R. (2022). Forecasting of Solar Irradiances using Time Series and Machine Learning Models: A Case Study from India. *Applied Solar Energy*. doi:10.3103/S0003701X22010170 | SARIMA best for monthly forecasts; MLP and LSTM better for short-term daily forecasts at Pokhran and Bitta. | Compares model families, so it does not isolate the effect of weather inputs; two sites. |
| 4 | Benitez, I. B. et al. (2023). Day-Ahead Hourly Solar Photovoltaic Output Forecasting Using SARIMAX, Long Short-Term Memory, and Extreme Gradient Boosting: Case of the Philippines. *Energies* 16(23), 7823. doi:10.3390/en16237823 | SARIMAX best at two of three plants, XGBoost at the third; hybrids did not beat single models. | Forecasts PV output, not radiation; one year; not an Indian climate. |
| 5 | Baloch, M. H. et al. (2024). An Intelligent SARIMAX-Based Machine Learning Framework for Long-Term Solar Irradiance Forecasting at Muscat, Oman. *Energies* 17(23), 6118. doi:10.3390/en17236118 | SARIMAX with humidity, temperature and wind speed performed best (MSE 0.0746, MAE 0.2096, R² 0.9197) on 24 years of data. | One city; the abstract mentions no persistence benchmark, significance test or split by season. |

### Research gap summary

1. **Established:** SARIMAX, seasonal ARIMA and cloud-cover regressors are each established in the literature reviewed.
2. **The gap, limited to these five papers (not an exhaustive review):** the abstracts do not show whether lagged weather inputs improve a seasonal ARIMA forecast against persistence benchmarks, with a significance test, across several Indian climates and separately for monsoon weeks. The gap is narrow.
3. **How the project addresses it:** the model family is held fixed (identical orders), so only the lagged weather block differs; seasonal and last-week persistence are the benchmarks; the Diebold-Mariano test checks significance.
4. **Improvement implemented:** SARIMAX with lag-1 humidity, temperature and cloud amount (standardised on training data).

## 3. Method

- **Missing values:** none inside the window; the pipeline would linearly time-interpolate isolated gaps (forward-fill would repeat stale weather; dropping would break the weekly frequency).
- **Stationarity (ADF, training weeks):** weekly level stat -9.57, p < 0.0001 -> stationary, so d = 0; after one seasonal difference (lag 52) stat -12.20, p < 0.0001. A unit-root test cannot see the dominant 52-week cycle, so one seasonal difference (D = 1) is still applied.
- **ACF/PACF:** the ACF of the level has the strong 52-week cycle; after seasonal differencing it has a single negative spike at lag 52 -> seasonal MA(1), with short-lag decay -> low-order ARMA.
- **Baseline (SARIMA):** six candidates fitted; lowest AIC = SARIMA(1,0,1)x(0,1,1,52), AIC 1956.4. Residuals pass Ljung-Box (p = 0.155, 0.227, 0.176 at lags 10, 26, 52).
- **Improved (SARIMAX):** same orders plus `rh_lag1`, `temp_lag1`, `cloud_lag1`; AIC 1953.1.
- **Evaluation:** one-week-ahead forecasts over all 277 test weeks with parameters fixed at their training estimates (every forecast uses only data up to the previous week). A static 277-week SARIMA forecast is also shown. Benchmarks: seasonal naive (same week last year) and naive (last week). Diebold-Mariano test on squared errors.
- **Limitation of the lag design:** the regressors are observed lag-1 weather. An operational system would use weather forecasts, which adds error.

## 4. Results (Bengaluru, test block 2021-04-11 to 2026-07-26)

| Metric | Baseline SARIMA | Improved SARIMAX | % improvement |
|---|---|---|---|
| MAE (kWh/m²/day) | 0.488 | 0.481 | 1.5 % |
| RMSE | 0.622 | 0.616 | 1.0 % |
| MAPE | 10.39 % | 10.25 % | 1.4 % |

| Benchmark | MAE | RMSE | MAPE |
|---|---|---|---|
| Seasonal naive | 0.644 | 0.824 | 13.27 % |
| Naive (last week) | 0.587 | 0.742 | 12.06 % |

- **SARIMAX vs SARIMA: Diebold-Mariano = 1.44, p = 0.150 -> NOT statistically significant at 5 %.**
- Both models beat both benchmarks decisively (DM vs seasonal naive: p < 0.001).
- Static 277-week SARIMA forecast: MAE 0.545, RMSE 0.686, MAPE 11.7 % - it reverts to the seasonal mean, as expected.
- **By season (MAE):** monsoon weeks (Jun-Sep) 0.474 -> 0.471; other weeks 0.496 -> 0.486.
- **Weather coefficients (standardised):** humidity -0.037 (p = 0.484), temperature +0.067 (p = 0.198), cloud amount -0.157 (p = 0.008). Only cloud amount is individually significant, with the expected negative sign.

### Robustness across cities (same orders, refitted per city; test MAE)

| City | Seasonal naive | SARIMA | SARIMAX | DM p (SARIMA vs SARIMAX) |
|---|---|---|---|---|
| Bengaluru | 0.644 | 0.488 | 0.481 | 0.150 |
| Delhi | 0.684 | 0.526 | 0.529 | 0.995 |
| Mumbai | 0.740 | 0.545 | 0.548 | 0.922 |
| Chennai | 0.693 | 0.542 | 0.544 | 0.944 |
| Jodhpur | 0.599 | 0.447 | 0.445 | 0.159 |

SARIMAX is slightly worse than SARIMA in Delhi, Mumbai and Chennai and slightly better in Bengaluru and Jodhpur; no difference is significant.

### Extensions implemented (Bengaluru, versus SARIMAX)

| Variant | MAE | RMSE | MAPE | DM p vs SARIMAX |
|---|---|---|---|---|
| Multi-lag weather (lags 1, 2, 52; 9 regressors) | 0.485 | 0.621 | 10.34 % | 0.117 |
| Log-transformed target | 0.476 | 0.610 | 10.10 % | 0.042 |
| Equal-weight SARIMA+SARIMAX ensemble | 0.484 | 0.618 | 10.31 % | 0.357 |

The log-transform result (p = 0.042) is one of three comparisons; with a Bonferroni correction (0.05/3 = 0.017) it is not significant. Treat it as a lead for further testing.

## 5. Conclusion

- **Which is better and by how much:** SARIMAX is nominally ahead of SARIMA by 1.5 % (MAE), 1.0 % (RMSE) and 1.4 % (MAPE), but the difference is not statistically significant, and across five cities the sign is mixed. Both far outperform persistence.
- **Why the gain is small (plausible, not tested here):** SARIMA already captures the 52-week cycle and week-to-week persistence; weekly means smooth away the day-to-day cloud variation that the covariates describe; a one-week-old weather reading says little about next week's sky. Cloud amount carries real signal (p = 0.008), it just does not translate into a significant forecast gain at this resolution.
- **Limitations:** NASA POWER is a modelled product (0.5° grid), not a ground pyranometer; one grid point per city; a single 80/20 split; lag-1 observed weather rather than forecast weather; MAPE is sensitive to low-radiation weeks; the literature review covers five papers and is not exhaustive, and four of the five could not be checked beyond their bibliographic records.
- **Future work (three specific suggestions):**
  1. Move to the daily scale with Fourier seasonal terms and use forecast weather (numerical weather prediction) instead of lag-1 observations - this is where covariates are most likely to matter.
  2. Fit a pooled or hierarchical model across the five cities so that climate-zone differences are estimated rather than refitted city by city, and evaluate with rolling-origin cross-validation instead of one split.
  3. Add probabilistic evaluation (CRPS, interval coverage) and a machine-learning comparison (gradient boosting or LSTM on the same lagged features) so SARIMAX can be judged against the models the literature compares with.

## 6. Files

| File | Purpose |
|---|---|
| `analysis.py` | full pipeline; `python analysis.py` (about 25-30 min), `--fast` skips the robustness cities and extensions |
| `make_dashboard.py` | builds `dashboard.html` from `outputs/results.json` |
| `dashboard.html` | interactive dashboard (Plotly from CDN needs internet; everything else inline) |
| `outputs/` | `results.json`, `metrics_table.csv`, 12 PNG figures, run logs |
| `data/` | the five NASA POWER CSVs, 1984-2026 |

Requires Python with pandas, numpy, scipy, statsmodels, matplotlib.
