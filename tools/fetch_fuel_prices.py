#!/usr/bin/env python3
"""Publish this week's U.S. average fuel prices as a small JSON file.

Why a published file rather than calling EIA from the app:

* The EIA API needs a key. Embedding one in a mobile app exposes it to
  anyone who unpacks the binary, and gives every install its own rate
  limit against a public service.
* The number is identical for every user and changes once a week. Asking
  16,000 phones to fetch it independently is wasteful.

So a scheduled job fetches it once, writes `fuel-prices.json` to the
public site, and the apps read that. The key lives in a repository secret
and never reaches a device.

Usage:
    EIA_API_KEY=... python3 tools/fetch_fuel_prices.py --out DIR

Register for a free key (no card) at https://www.eia.gov/opendata/register.php
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EIA_ENDPOINT = "https://api.eia.gov/v2/petroleum/pri/gnd/data/"

# EIA product codes. "PTE" is the retail price series, "NUS" the whole US.
PRODUCTS = {
    "regular_gasoline": "EPMR",
    "diesel": "EPD2D",
}
NATIONAL_AREA = "NUS"

USER_AGENT = "OpenCampAtlas/1.0 (contact@FreeRangeLabs)"


def fetch_series(api_key: str, product: str) -> dict | None:
    """Most recent weekly national retail price for one product."""
    query = [
        ("api_key", api_key),
        ("frequency", "weekly"),
        ("data[0]", "value"),
        ("facets[product][]", product),
        ("facets[duoarea][]", NATIONAL_AREA),
        ("facets[process][]", "PTE"),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "desc"),
        ("length", "1"),
    ]
    url = EIA_ENDPOINT + "?" + urllib.parse.urlencode(query)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")[:300]
        print(f"  EIA returned HTTP {error.code} for {product}: {body}", file=sys.stderr)
        return None
    except Exception as error:  # noqa: BLE001 - report and carry on
        print(f"  Could not reach EIA for {product}: {error}", file=sys.stderr)
        return None

    rows = (payload.get("response") or {}).get("data") or []
    if not rows:
        print(f"  EIA returned no rows for {product}", file=sys.stderr)
        return None

    row = rows[0]
    try:
        value = float(row["value"])
    except (KeyError, TypeError, ValueError):
        print(f"  EIA row for {product} had no usable value: {row}", file=sys.stderr)
        return None

    return {
        "pricePerUnit": round(value, 3),
        "unit": row.get("units") or "$/GAL",
        "period": row.get("period"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="site directory")
    args = parser.parse_args()

    api_key = os.environ.get("EIA_API_KEY", "").strip()
    if not api_key:
        print(
            "EIA_API_KEY is not set. Register free at "
            "https://www.eia.gov/opendata/register.php",
            file=sys.stderr,
        )
        return 2

    prices: dict[str, dict] = {}
    for name, product in PRODUCTS.items():
        series = fetch_series(api_key, product)
        if series:
            prices[name] = series
            print(f"  {name}: {series['pricePerUnit']} {series['unit']} ({series['period']})")

    if not prices:
        # Better to leave the previous week's file in place than to
        # overwrite it with nothing. The app treats a stale price as
        # missing once it ages out, and shows no cost rather than a wrong
        # one.
        print("No prices fetched; leaving the existing file untouched.", file=sys.stderr)
        return 1

    # Keep the previous timestamp when the prices themselves have not
    # moved. updatedAt is wall-clock, so rewriting it every run makes the
    # file differ every week even when nothing changed, and the workflow's
    # "commit if the price changed" guard never actually holds.
    target = args.out / "fuel-prices.json"
    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if target.exists():
        try:
            previous = json.loads(target.read_text(encoding="utf-8"))
            if previous.get("prices") == prices and previous.get("updatedAt"):
                updated_at = previous["updatedAt"]
                print("  prices unchanged; keeping the previous timestamp")
        except Exception:  # noqa: BLE001 - a damaged file just gets replaced
            pass

    document = {
        "updatedAt": updated_at,
        "source": "U.S. Energy Information Administration, weekly retail prices",
        "sourceUrl": "https://www.eia.gov/petroleum/gasdiesel/",
        "coverage": "United States national average",
        "prices": prices,
    }

    args.out.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
