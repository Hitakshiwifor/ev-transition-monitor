"""
pipeline/bronze/fetch_sources.py
==================================
Bronze layer — fetches raw data from three independent, reliable sources.
No hardcoded fallback values. If a source fails, it is skipped and logged.
The silver layer decides how to merge available sources.

Sources
───────
1. Eurostat JSON API     — road_eqr_carpda  (primary, most complete)
   Annual new passenger car registrations by powertrain type, all EU + EFTA countries.
   https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/road_eqr_carpda

2. Our World in Data CSV — electric vehicle share  (secondary, BEV+PHEV share)
   Annual share of new car sales that are plug-in electric, by country.
   https://ourworldindata.org/grapher/share-car-sales-electric.csv

3. ACEA website scrape   — latest registration statistics  (tertiary, most recent)
   Scrapes the ACEA statistics page for the most recent annual totals by fuel type.
   https://www.acea.auto/figure/automobile-registrations/

Medallion role : RAW — files saved unchanged to data/bronze/
Output         : data/bronze/eurostat_road_eqr_carpda_<YYYYMMDD>.json
                 data/bronze/owid_ev_share_<YYYYMMDD>.csv
                 data/bronze/acea_registrations_<YYYYMMDD>.json
"""

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import median
from urllib.parse import urljoin

import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.settings import BRONZE_DIR, EUROSTAT_BASE_URL, EUROSTAT_TIMEOUT_SEC

TODAY = datetime.utcnow().strftime("%Y%m%d")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, text/csv, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


# ─────────────────────────────────────────────────────────────
# Utility
# ─────────────────────────────────────────────────────────────

def _get(url: str, timeout: int = 30, stream: bool = False) -> requests.Response:
    """Thin wrapper around requests.get with retry on transient errors."""
    for attempt in range(1, 4):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout, stream=stream)
            resp.raise_for_status()
            return resp
        except requests.exceptions.Timeout:
            logger.warning("Timeout on attempt {} for {}", attempt, url)
            time.sleep(2 ** attempt)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in (429, 503):
                logger.warning("Rate-limited ({}), retrying …", e.response.status_code)
                time.sleep(5 * attempt)
            else:
                raise
    raise TimeoutError(f"All retries exhausted for {url}")


def _already_fetched(pattern: str) -> Path | None:
    """Return existing bronze file if it was fetched today."""
    existing = list(BRONZE_DIR.glob(pattern.replace("<DATE>", TODAY)))
    if existing:
        logger.info("Using today's cached bronze file: {}", existing[0].name)
        return existing[0]
    return None


# ═════════════════════════════════════════════════════════════
# SOURCE 1: Eurostat JSON API
# ═════════════════════════════════════════════════════════════

EUROSTAT_DATASET = "road_eqr_carpda"
EUROSTAT_URL = (
    f"{EUROSTAT_BASE_URL}/{EUROSTAT_DATASET}"
    "?format=JSON&lang=EN"
)


def fetch_eurostat() -> Path | None:
    """
    Fetch annual new passenger car registrations by powertrain from Eurostat.

    Dataset : road_eqr_carpda
    Coverage: EU27 + EFTA + candidate countries · 2013–present
    Update  : Annually (January/February)
    Licence : Eurostat data is free to reuse (CC BY 4.0)
    """
    cached = _already_fetched(f"eurostat_{EUROSTAT_DATASET}_<DATE>.json")
    if cached:
        return cached

    logger.info("SOURCE 1 — Eurostat: fetching {} …", EUROSTAT_DATASET)
    try:
        resp = _get(EUROSTAT_URL, timeout=EUROSTAT_TIMEOUT_SEC)
        data = resp.json()

        n_values = len(data.get("value", {}))
        updated  = data.get("updated", "unknown")
        logger.info("  Eurostat: {:,} data points, last updated {}", n_values, updated)

        out = BRONZE_DIR / f"eurostat_{EUROSTAT_DATASET}_{TODAY}.json"
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.success("  Saved → {}", out.name)
        return out

    except Exception as e:
        logger.error("SOURCE 1 FAILED (Eurostat): {}", e)
        # Check if there is a previous fetch we can use
        prev = sorted(BRONZE_DIR.glob(f"eurostat_{EUROSTAT_DATASET}_*.json"))
        if prev:
            logger.warning("  Falling back to previous fetch: {}", prev[-1].name)
            return prev[-1]
        return None


# ═════════════════════════════════════════════════════════════
# SOURCE 2: Our World in Data — EV share CSV
# ═════════════════════════════════════════════════════════════

OWID_URL = (
    "https://ourworldindata.org/grapher/electric-car-sales-share.csv"
    "?v=1&csvType=full&useColumnShortNames=true"
)

OWID_ALT_URL = (
    "https://ourworldindata.org/grapher/electric-car-sales-share.csv"
)

OWID_METADATA_URL = (
    "https://ourworldindata.org/grapher/electric-car-sales-share.metadata.json"
)

IEA_GLOBAL_EV_XLSX_URL = (
    "https://iea.blob.core.windows.net/assets/"
    "23cc1f1c-c869-4a39-ac51-457725c87103/EVDataExplorer2025.xlsx"
)


def fetch_owid_ev_share() -> Path | None:
    """
    Fetch annual plug-in electric vehicle share of new car sales from
    Our World in Data (sourced from IEA Global EV Tracker).

    Coverage: World countries · ~2010–2024
    Update  : Annual (usually Q1 each year)
    Licence : CC BY 4.0
    Note    : Includes both BEV and PHEV (plug-in share combined)
    """
    cached = _already_fetched("owid_ev_share_<DATE>.csv")
    if cached:
        return cached

    logger.info("SOURCE 2 — Our World in Data: fetching EV share CSV …")
    for url in (OWID_URL, OWID_ALT_URL):
        try:
            resp = _get(url, timeout=30)
            content = resp.text

            # Basic validation — check it looks like a CSV
            lines = [line for line in content.splitlines() if line.strip()]
            if len(lines) < 5:
                logger.warning("  OWID response too short ({} lines) — skipping", len(lines))
                continue

            logger.info("  OWID: {:,} data lines received", len(lines) - 1)

            out = BRONZE_DIR / f"owid_ev_share_{TODAY}.csv"
            out.write_text(content, encoding="utf-8")

            try:
                meta_resp = _get(OWID_METADATA_URL, timeout=30)
                meta_out = BRONZE_DIR / f"owid_ev_share_metadata_{TODAY}.json"
                meta_out.write_text(meta_resp.text, encoding="utf-8")
                logger.info("  OWID metadata saved -> {}", meta_out.name)
            except Exception as e:
                logger.warning("  OWID metadata fetch failed: {}", e)

            logger.success("  Saved → {}", out.name)
            return out

        except Exception as e:
            logger.warning("  OWID attempt failed ({}): {}", url, e)
            continue

    # Try previous fetch
    prev = sorted(BRONZE_DIR.glob("owid_ev_share_*.csv"))
    if prev:
        logger.warning("SOURCE 2: using previous OWID fetch: {}", prev[-1].name)
        return prev[-1]

    logger.error("SOURCE 2 FAILED (Our World in Data): all attempts exhausted")
    return None


# ═════════════════════════════════════════════════════════════
# SOURCE 3: ACEA — European Automobile Manufacturers' Association
# ═════════════════════════════════════════════════════════════

def fetch_iea_global_ev_data() -> Path | None:
    """
    Download the official IEA Global EV Data Explorer workbook.

    Coverage: historical EV sales/stock plus STEPS projections to 2030
    Update  : annual, with versioned workbook releases
    Licence : CC BY 4.0
    """
    cached = _already_fetched("iea_global_ev_data_<DATE>.xlsx")
    if cached:
        return cached

    logger.info("SOURCE 3 - IEA: downloading Global EV Data Explorer workbook")
    try:
        resp = _get(IEA_GLOBAL_EV_XLSX_URL, timeout=60, stream=True)
        out = BRONZE_DIR / f"iea_global_ev_data_{TODAY}.xlsx"
        out.write_bytes(resp.content)
        logger.success("  Saved -> {}", out.name)
        return out
    except Exception as e:
        logger.error("SOURCE 3 FAILED (IEA Global EV Data Explorer): {}", e)
        prev = sorted(BRONZE_DIR.glob("iea_global_ev_data_*.xlsx"))
        if prev:
            logger.warning("  Using previous IEA source fetch: {}", prev[-1].name)
            return prev[-1]
        return None


ACEA_STATS_URL = "https://www.acea.auto/figure/automobile-registrations/"
ACEA_HOME_URL = "https://www.acea.auto/"
ACEA_API_URLS: list[str] = []


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _parse_int(text: str | None) -> int | None:
    if not text:
        return None
    return int(text.replace(",", "").replace(" ", ""))


def _parse_float(text: str | None) -> float | None:
    if not text:
        return None
    return float(text.replace(",", "."))


def _acea_release_links(soup) -> dict[str, str]:
    links: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        label = _clean_text(a.get_text(" ", strip=True))
        href = urljoin(ACEA_HOME_URL, a["href"])
        if "/pc-registrations/" not in href or "new car registrations" not in label.lower():
            continue
        if "battery-electric" not in label.lower():
            continue
        links.setdefault("latest", href)
        if re.search(r"\bin\s+20\d{2};", label, flags=re.I):
            links.setdefault("annual", href)
    return links


def _first_match(pattern: str, text: str) -> re.Match | None:
    return re.search(pattern, text, flags=re.I)


def _add_powertrain(
    rows: dict[str, dict],
    key: str,
    registrations: int | None,
    share_pct: float | None,
    note: str,
) -> None:
    if registrations is None and share_pct is None:
        return
    rows[key] = {
        "registrations": registrations,
        "share_pct": share_pct,
        "note": note,
    }


def _parse_acea_passenger_car_release(url: str, release_kind: str) -> dict | None:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("  BeautifulSoup4 not installed — skipping ACEA release parse")
        return None

    resp = _get(url, timeout=30)
    soup = BeautifulSoup(resp.text, "lxml")
    text = _clean_text(soup.get_text(" ", strip=True))
    title = _clean_text(soup.find("h1").get_text(" ", strip=True)) if soup.find("h1") else ""

    published = None
    if m := _first_match(r"\b(\d{1,2}\s+[A-Z][a-z]+\s+20\d{2})\b", text):
        published = m.group(1)

    year = None
    period_label = None
    period_type = release_kind
    if m := _first_match(r"\b(Q[1-4]\s+20\d{2})\b", title):
        period_label = m.group(1)
        year = int(period_label[-4:])
        period_type = "quarter_to_date"
    elif m := _first_match(r"\bin\s+(20\d{2})\b", title):
        year = int(m.group(1))
        period_label = str(year)
        period_type = "annual"
    elif m := _first_match(r"\b(20\d{2})\b", title):
        year = int(m.group(1))
        period_label = str(year)

    rows: dict[str, dict] = {}

    if m := _first_match(
        r"([\d,]+)\s+new battery-electric cars were registered, capturing\s+([\d.]+)%",
        text,
    ):
        _add_powertrain(rows, "BEV", _parse_int(m.group(1)), _parse_float(m.group(2)),
                        "ACEA count and market share parsed from release text")

    if m := _first_match(
        r"hybrid-electric car registrations (?:rising to|reaching|rose to)\s+([\d,]+)\s+units.*?"
        r"(?:accounted for|account for|captured)\s+([\d.]+)%",
        text,
    ):
        _add_powertrain(rows, "HEV", _parse_int(m.group(1)), _parse_float(m.group(2)),
                        "ACEA count and market share parsed from release text")

    if m := _first_match(
        r"plug-in-hybrid electric cars.*?reaching\s+([\d,]+)\s+units.*?"
        r"(?:represent|represents|represented)\s+([\d.]+)%",
        text,
    ):
        _add_powertrain(rows, "PHEV", _parse_int(m.group(1)), _parse_float(m.group(2)),
                        "ACEA count and market share parsed from release text")

    if m := _first_match(
        r"With\s+([\d,]+)\s+new cars registered.*?market share for petrol fell to\s+([\d.]+)%",
        text,
    ):
        _add_powertrain(rows, "ICE_Petrol", _parse_int(m.group(1)), _parse_float(m.group(2)),
                        "ACEA count and market share parsed from release text")

    diesel_share = None
    if m := _first_match(r"diesel car market.*?(?:accounting for|resulting in an?)\s+([\d.]+)%", text):
        diesel_share = _parse_float(m.group(1))

    inferred_totals = [
        item["registrations"] / (item["share_pct"] / 100)
        for item in rows.values()
        if item.get("registrations") is not None and item.get("share_pct")
    ]
    total_registrations = round(median(inferred_totals)) if inferred_totals else None

    if diesel_share is not None:
        diesel_regs = round(total_registrations * diesel_share / 100) if total_registrations else None
        _add_powertrain(
            rows,
            "ICE_Diesel",
            diesel_regs,
            diesel_share,
            "ACEA diesel market share parsed; registrations derived from inferred official total",
        )

    known_share = sum(v["share_pct"] or 0 for v in rows.values())
    known_regs = sum(v["registrations"] or 0 for v in rows.values())
    if total_registrations and known_share < 99.9:
        other_share = round(max(0.0, 100 - known_share), 1)
        other_regs = max(0, total_registrations - known_regs)
        _add_powertrain(
            rows,
            "Other",
            other_regs,
            other_share,
            "Residual from ACEA official shares/counts",
        )

    if not rows:
        logger.warning("  ACEA release parse found no powertrain data: {}", url)
        return None

    return {
        "source": "ACEA passenger car registrations",
        "source_url": url,
        "title": title,
        "published_date": published,
        "period_label": period_label,
        "period_type": period_type,
        "year": year,
        "total_registrations": total_registrations,
        "powertrain": rows,
    }


def fetch_acea_registrations() -> Path | None:
    """
    Scrape ACEA website for the latest annual EU registration figures by fuel type.

    Coverage: EU + EFTA · most recent year + historical
    Update  : Monthly press releases; annual summary in January
    Licence : Publicly available statistics
    """
    cached = _already_fetched("acea_registrations_<DATE>.json")
    if cached:
        return cached

    logger.info("SOURCE 4 - ACEA: parsing official passenger-car releases")

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("  BeautifulSoup4 not installed — skipping ACEA scrape")
        return None

    result = {"source": "ACEA", "fetched_at": datetime.utcnow().isoformat(), "tables": []}

    try:
        home_soup = BeautifulSoup(_get(ACEA_HOME_URL, timeout=30).text, "lxml")
        release_links = _acea_release_links(home_soup)

        if release_links.get("latest"):
            latest_soup = BeautifulSoup(_get(release_links["latest"], timeout=30).text, "lxml")
            for key, href in _acea_release_links(latest_soup).items():
                release_links.setdefault(key, href)

        if release_links.get("latest"):
            result["latest_ytd"] = _parse_acea_passenger_car_release(
                release_links["latest"], "latest_ytd"
            )
        if release_links.get("annual"):
            result["latest_annual"] = _parse_acea_passenger_car_release(
                release_links["annual"], "annual"
            )

        result["release_links"] = release_links
        logger.info("  ACEA release links parsed: {}", release_links)
    except Exception as e:
        logger.warning("  ACEA latest-release parse failed: {}", e)

    for url in ACEA_API_URLS:
        try:
            resp = _get(url, timeout=30)
            soup = BeautifulSoup(resp.text, "lxml")

            # Look for data tables on the page
            tables = soup.find_all("table")
            charts = soup.find_all(attrs={"data-chart": True})
            json_blocks = soup.find_all("script", type="application/json")

            logger.debug("  ACEA ({}): {} tables, {} chart blocks, {} JSON scripts",
                         url, len(tables), len(charts), len(json_blocks))

            # Extract any structured data from script tags (chart.js or similar)
            for script in soup.find_all("script"):
                if script.string and ("registrations" in script.string.lower()
                                      or "electric" in script.string.lower()
                                      or "fuel" in script.string.lower()):
                    try:
                        # Try to extract embedded JSON data
                        text = script.string
                        start = text.find("{")
                        if start >= 0:
                            embedded = json.loads(text[start:])
                            result["embedded_data"] = embedded
                            logger.info("  Found embedded chart data in ACEA page")
                    except Exception:
                        pass

            # Extract visible table data
            for tbl in tables[:5]:  # first 5 tables
                rows = []
                for tr in tbl.find_all("tr"):
                    row = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
                    if row:
                        rows.append(row)
                if rows:
                    result["tables"].append({"url": url, "rows": rows})

            # Extract any anchor links to downloadable files (Excel/CSV)
            downloads = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if any(href.lower().endswith(ext) for ext in [".xlsx", ".xls", ".csv"]):
                    full_url = href if href.startswith("http") else f"https://www.acea.auto{href}"
                    downloads.append({"url": full_url, "label": a.get_text(strip=True)})

            if downloads:
                result["download_links"] = downloads
                logger.info("  Found {} downloadable file(s) on ACEA page", len(downloads))

                # Try to download the first Excel file
                for dl in downloads[:3]:
                    if ".xlsx" in dl["url"] or ".xls" in dl["url"]:
                        try:
                            file_resp = _get(dl["url"], timeout=30)
                            xl_path = BRONZE_DIR / f"acea_download_{TODAY}.xlsx"
                            xl_path.write_bytes(file_resp.content)
                            result["downloaded_file"] = str(xl_path)
                            logger.success("  Downloaded ACEA Excel → {}", xl_path.name)
                            break
                        except Exception as e:
                            logger.warning("  Could not download ACEA file {}: {}", dl["url"], e)

            result["url"] = url
            break  # success on first URL

        except Exception as e:
            logger.warning("  ACEA URL {} failed: {}", url, e)
            continue

    out = BRONZE_DIR / f"acea_registrations_{TODAY}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.success("  ACEA metadata saved → {}", out.name)
    return out


# ═════════════════════════════════════════════════════════════
# Run all bronze steps
# ═════════════════════════════════════════════════════════════

def run_bronze() -> dict:
    """Execute all three source fetches. Returns dict of paths (None = failed)."""
    logger.info("=" * 60)
    logger.info("BRONZE LAYER — Multi-Source Ingestion")
    logger.info("=" * 60)

    results = {
        "eurostat": fetch_eurostat(),
        "owid":     fetch_owid_ev_share(),
        "iea":      fetch_iea_global_ev_data(),
        "acea":     fetch_acea_registrations(),
    }

    available = [k for k, v in results.items() if v is not None]
    failed    = [k for k, v in results.items() if v is None]

    logger.info("=" * 60)
    logger.info("BRONZE COMPLETE — available: {} | failed: {}",
                available or "none", failed or "none")
    if not available:
        logger.error("ALL SOURCES FAILED — no data available for silver layer")
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    from config.logging_config import setup_logging
    from config.settings import LOG_DIR
    setup_logging(LOG_DIR)
    run_bronze()
