# 📈 MEAN REVERSION

**Find securities that repeatedly return to a rising long-term trend.**

---

## 🧩 Overview

Mean Reversion is a stock-research app for examining two questions together: does a security repeatedly return to its long-term trend, and is that trend rising?

Enter a ticker to analyze its full available adjusted-price history. The app draws a long-term trend line, shows the typical range around it, measures the current distance from trend, and counts completed excursions away from and back to trend. It reports the annual trend growth rate alongside a descriptive Strong, Moderate, Weak, or Random walk verdict.

Trend information is never hidden because of a verdict. Every valid ticker retains its trend line, upper and lower bands, annual slope, and current position—even when the observed reversion pattern is weak.

The independent Mean Reversion section sits alongside the app's existing SOXL charts, daily signals, probability tools, options research, backtesting, and AI-assisted strategy tools. It does not replace their calculations or chart state.

## 👥 Who It's For

**Long-term investors** — want to distinguish a rising long-term trend from a temporary price move.

**Mean-reversion traders** — want to examine whether substantial departures from trend have repeatedly closed.

**ETF and leveraged-ETF researchers** — want to compare securities such as SOXL, TQQQ, and SPY without assuming they share the same behavior or risk.

**Quantitative researchers** — want explicit formulas, reproducible thresholds, and a clear separation between descriptive patterns and predictive evidence.

**Independent investors** — want to see where today's price sits relative to a security's own history, rather than relying on a chart impression alone.

## ⚙️ Core Capabilities

**Analyze a Stock Ticker** — Enter a symbol and select Analyze. The independent Mean Reversion tool uses the full adjusted daily history available from the configured provider.

**Always-Visible Trend and Bands** — View the fitted long-term trend and upper and lower bands on a logarithmic price chart. Extend the model lines to an adjustable projection-end date, regardless of the verdict.

**Annual Trend Growth** — See a direct statement such as “Trend rising 39.4% per year.” Flat or declining trends are identified explicitly.

**Current Position and Historical Percentile** — See how far the latest adjusted close is above or below trend and how that distance compares with historical residuals.

**Completed Reversion Cycles** — Count substantial excursions that subsequently return through the trend line. Small fluctuations near trend do not count as completed cycles.

**Transparent Grades** — Strong, Moderate, Weak, and Random walk labels follow explicit cycle-count, persistence, and half-life rules—not an undisclosed scoring system.

**Comparison Overlays** — Add other tickers to the Mean Reversion chart, view their scaled price histories with actual-price hover values, inspect compact summaries, remove comparisons, or switch the main analysis to a comparison ticker.

**Interactive Chart Controls** — Pan and zoom, adjust chart width and height, inspect logarithmic dollar-price labels, and view a separate distance-from-trend panel.

**Conditional Projection Probabilities** — For mathematically supported AR(1) fits, inspect future model prices and cumulative daily-crossing probabilities from 20,000 simulated paths.

**Existing SOXL Research Workspace** — Retain the separate SOXL daily signals, hand-drawn chart channels, benchmark overlays, historical probability tools, options analytics, backtesting, and strategy research.

**Public Research Access** — Use the research interface without a mandatory sign-in wall.

## 🔎 How the Mean Reversion Model Works

### Long-term trend

The model fits a straight line to the logarithm of adjusted daily prices over the full available history:

```text
y_t = ln(adjusted close_t)
y_t = a + g × t + x_t
```

Here, `t` is elapsed calendar time in years, `g` is the fitted annual log-growth rate, and `x_t` is the residual—the distance from the fitted log-price trend.

```text
Trend price          = exp(a + g × t)
Annual trend growth  = (exp(g) − 1) × 100%
Current position     = (exp(x_now) − 1) × 100%
```

### Band width and half-life

A no-intercept AR(1) model describes the residuals:

```text
x_t = φ × x_(t−1) + ε_t
σ_ε = standard deviation of the daily innovations
s   = σ_ε / sqrt(1 − φ²)

Upper band = exp(a + g × t + 2s)
Lower band = exp(a + g × t − 2s)

Half-life = ln(2) / (−ln φ), for 0 < φ < 1
```

The cycle threshold and price bands use **s**, the modeled long-run residual spread—not **σ_ε**, the daily shock size. Half-life is measured in trading days.

If `|φ| ≥ 1`, the stationary AR(1) spread is undefined. The interface explicitly labels an observed-residual-spread fallback so descriptive bands remain visible; stationary-model touch probabilities are unavailable for that fit.

### Completed cycles and grades

A completed cycle begins when `|x_t|` strictly exceeds `s` and finishes when the residual later reaches or crosses zero. An unfinished excursion does not count.

| Verdict | Rule |
| --- | --- |
| Random walk | Fewer than 4 completed cycles **or** φ ≥ 0.9995 |
| Strong | Not Random walk; at least 8 cycles and half-life ≤ 120 trading days |
| Moderate | Not Random walk or Strong; at least 6 cycles and half-life ≤ 300 trading days |
| Weak | Every remaining case |

The thresholds live in the model's configuration object. Trend slope is reported separately: a Strong reversion grade does not itself mean the trend is rising.

## ▶️ Getting Started

1. Open the app and scroll to **Mean Reversion**.
2. Enter a stock or ETF ticker, such as SOXL, TQQQ, SPY, KO, or MSFT.
3. Select **Analyze**.
4. Read the trend direction and current position alongside the cycle count and verdict.
5. Adjust the projection-end date or add comparison tickers as needed.

For the goal of finding repeated returns to a rising trend, consider both the reversion evidence and the annual growth rate. Neither should be read in isolation.

## ⚠️ What the Results Do—and Do Not—Mean

**Descriptive, not a proof of predictability** — The cycle rule summarizes observed history. It is not a statistical test establishing stationarity, and a simulated random walk can also produce in-sample cycles after detrending.

**Full-history fitting is retrospective** — The fitted line uses the entire supplied history. Historical distances from that line are not signals that would necessarily have been available at the time.

**Projection is conditional** — Extending a fitted trend is a model scenario, not a price promise. Monte Carlo probabilities hold fitted parameters fixed and are not calibrated investment-success probabilities.

**Daily crossings are not intraday touches** — Simulations use daily steps. Future dates exclude weekends but do not remove exchange holidays.

**Data availability matters** — Coverage depends on the configured provider. The chart's latest dot represents the latest available adjusted daily close, not necessarily a live quote.

**Leveraged funds carry additional risk** — SOXL and TQQQ can experience large losses, compounding effects, and behavior that differs substantially from an unleveraged index.

This app supports research. It does not guarantee returns or provide a substitute for an independent investment decision.

---

<details>
<summary><strong>🛠️ Technical Setup and Maintenance</strong></summary>

### Technology

- Python and Streamlit for the application interface.
- NumPy and pandas for numerical analysis and time series.
- Plotly and isolated HTML/JavaScript components for interactive charts.
- Tiingo adjusted daily closes for the independent Mean Reversion history loader, with the existing EODHD provider used when configured instead.
- Direct Anthropic and OpenAI credentials for the app's AI-assisted tools.
- Neon PostgreSQL for persistent application data.

### Run the application

Install the Python dependencies and start the public gateway:

```bash
python -m pip install -r requirements.txt
python seo_server.py
```

The gateway listens on `0.0.0.0`, using `PORT` when configured and port `5000` otherwise.

### Configuration and credentials

See [ENV_VARS.md](ENV_VARS.md) for runtime configuration. Keep all credentials in private environment variables, never in this README or source code.

- `TIINGO_API_KEY` — adjusted daily prices for the independent Mean Reversion loader.
- `EODHD_API_KEY` — the loader's existing alternative when Tiingo is not configured.
- `NEON_DATABASE_URL` — this app's dedicated PostgreSQL connection; takes precedence over the `DATABASE_URL` fallback.
- `ANTHROPIC_API_KEY` — direct Anthropic access for AI-assisted features.
- `OPENAI_API_KEY` — direct OpenAI access for AI-assisted features and diagnostics.

Optional `ANTHROPIC_BASE_URL` and `OPENAI_BASE_URL` support compatible custom endpoints. Leave them unset for standard provider endpoints.

Use a dedicated database for this app rather than sharing the original SOXL Pro database. For a new external database, run `python setup_database.py` with that database configured. The setup creates tables without deleting existing records; market-data refreshes run separately.

Configure credentials separately in each hosting environment. Do not assume credentials entered in one environment are available in another.

### Independent Mean Reversion files

| File | Purpose |
| --- | --- |
| `trend_reversion_model.py` | Log-trend fit, residual AR(1), cycle counts, grades, bands, and simulations |
| `trend_reversion_data.py` | Full available adjusted-history loading and per-day caching |
| `trend_reversion_ui.py` | Independent Streamlit controls, summaries, and comparison state |
| `components/mean_reversion/` | Interactive Mean Reversion chart |
| `tests/test_trend_reversion.py` | Model and threshold contract tests |
| `tests/test_trend_reversion_data.py` | Adjusted-history adapter tests |
| `tests/trend_reversion_chart.cjs` | Chart-configuration assertions |

### Focused checks

```bash
python -m pytest -q tests/test_trend_reversion.py tests/test_trend_reversion_data.py
node tests/trend_reversion_chart.cjs
```

These checks cover the independent Mean Reversion feature. They are not a substitute for testing every existing SOXL research tool.

</details>
