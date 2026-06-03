# European EV Transition Monitor

**Built by WifOR | Powered by Python · Dash · Plotly**

A production-ready analytical dashboard tracking Europe's powertrain transition from ICE to Battery Electric Vehicles (BEV), with source-backed data from Eurostat, ACEA, Our World in Data, and the IEA Global EV Data Explorer.

---

## Quick Start

```bash
# 1. Create/sync the managed project environment
uv sync

# 2. Run the data pipeline (fetches & processes data)
uv run python scripts/run_pipeline.py

# 3. Launch the dashboard
uv run python dashboard/app.py

# 4. Open in browser
#    http://127.0.0.1:8050
```

---

## Architecture

This project follows **Medallion Architecture** (Bronze → Silver → Gold):

```
data/
├── bronze/    Raw JSON from Eurostat API (unchanged, timestamped)
├── silver/    Cleaned, typed Parquet files (registrations_annual, forecast_scenarios)
└── gold/      Dashboard-ready aggregates (eu_annual, country_bev_share, kpi_snapshot)
```

### Pipeline Layers

| Layer  | Script                                          | Output                        |
|--------|-------------------------------------------------|-------------------------------|
| Bronze | `pipeline/bronze/fetch_sources.py`              | `eurostat_road_eqr_carpda_*.json`, OWID CSV, IEA XLSX, ACEA JSON |
| Silver | `pipeline/silver/transform_registrations.py`    | `registrations_annual.parquet`    |
| Gold   | `pipeline/gold/build_analytics.py`              | `eu_annual.parquet`, `kpi_snapshot.json` |

---

## Data Sources

| Source | Dataset | Update frequency | Access |
|--------|---------|-----------------|--------|
| **Eurostat** | `road_eqr_carpda` — Annual car registrations by fuel type | Annual (Jan) | Free API |
| **ACEA** | Monthly press releases | Monthly | Web |
| **Our World in Data** | `electric-car-sales-share` — IEA-derived EV sales share | Annual | CSV/API |
| **IEA** | Global EV Data Explorer workbook | Annual | XLSX |

---

## Dashboard Features

- **5 KPI Cards** — Total registrations, BEV share, Hybrid share, ICE share, Market value
- **Powertrain Trend Chart** — Stacked area / bar / line, filterable by year range & powertrain
- **Europe Choropleth Map** — BEV share or total registrations by country
- **EV Sales Share Outlook** — IEA STEPS projection with ACEA latest actual marker
- **Market Value Chart** — EUR bn estimate with uncertainty range + dual-axis registrations
- **Insight Panels** — Plain-language interpretation alongside every chart

---

## Running the Pipeline

```bash
# Full pipeline
uv run python scripts/run_pipeline.py

# Individual layers
uv run python scripts/run_pipeline.py --layer bronze
uv run python scripts/run_pipeline.py --layer silver
uv run python scripts/run_pipeline.py --layer gold
```

The pipeline does not fall back to research-document seed values. If Eurostat/ACEA source data is unavailable, the silver layer raises a clear data-availability error so stale or invented values are not silently published.

---

## Keeping Data Current

To keep the dashboard current, schedule the pipeline to run monthly:

```bash
# cron example (1st of every month at 06:00)
0 6 1 * * cd /path/to/project && uv run python scripts/run_pipeline.py --layer bronze && uv run python scripts/run_pipeline.py --layer silver && uv run python scripts/run_pipeline.py --layer gold
```

---

## Project Structure

```
Automotive Dashboard Tool/
├── README.md
├── pyproject.toml
├── uv.lock
├── config/
│   ├── settings.py          ← WifOR colours, API URLs, constants
│   └── logging_config.py    ← Loguru setup
├── data/
│   ├── bronze/              ← Raw JSON from APIs
│   ├── silver/              ← Cleaned Parquet files
│   └── gold/                ← Dashboard-ready aggregates
├── pipeline/
│   ├── bronze/fetch_sources.py
│   ├── bronze/fetch_eurostat.py
│   ├── silver/transform_registrations.py
│   └── gold/build_analytics.py
├── dashboard/
│   ├── app.py               ← Dash entry point
│   ├── layout.py            ← Page structure
│   ├── callbacks.py         ← Filter → chart wiring
│   ├── data_loader.py       ← Gold layer loader
│   └── components/
│       ├── kpi_cards.py
│       ├── powertrain.py
│       ├── map_view.py
│       ├── forecast.py
│       └── market_value.py
├── assets/
│   └── style.css            ← WifOR brand stylesheet
├── scripts/
│   └── run_pipeline.py      ← Pipeline runner
└── logs/                    ← Rotating log files (auto-generated)
```

---

## Notes

- All values shown are estimates. Primary source data should always be verified.
- Forecast lines are scenario projections, not guarantees.
- The pipeline prefers source fetches from Eurostat, ACEA, OWID, and IEA over static assumptions.
