"""Current U.S. HTS lines from the official USITC REST interface."""

import json
import re
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://hts.usitc.gov/reststop/search"
_CACHE_TTL_SECONDS = 900
_CACHE: dict[str, tuple[float, dict]] = {}


def fetch_usitc_tariffs(hs6: str) -> dict:
    if not re.fullmatch(r"\d{6}", hs6):
        raise ValueError("U.S. tariff lookup requires a six-digit HS code")
    now = monotonic()
    cached = _CACHE.get(hs6)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    source_url = f"{BASE_URL}?{urlencode({'keyword': hs6})}"
    request = Request(source_url, headers={"User-Agent": "TarifeLab/0.1"})
    try:
        with urlopen(request, timeout=15) as response:
            rows = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        result = {
            "status": "source_unavailable",
            "hs6_code": hs6,
            "lines": [],
            "retrieved_at": None,
            "source_url": source_url,
            "message": f"USITC HTS request failed: {exc}",
        }
        _CACHE[hs6] = (now, result)
        return result
    if not isinstance(rows, list):
        raise ValueError("USITC HTS search returned an unexpected response")

    lines = []
    for row in rows:
        raw_code = str(row.get("htsno") or "")
        code = "".join(character for character in raw_code if character.isdigit())
        if not code.startswith(hs6) or len(code) not in {8, 10}:
            continue
        general = str(row.get("general") or "").strip()
        special = str(row.get("special") or "").strip()
        column_2 = str(row.get("other") or "").strip()
        if not (general or special or column_2):
            continue
        lines.append({
            "hts_code": code,
            "description": str(row.get("description") or "").strip(),
            "general_rate": general,
            "special_rate": special,
            "column_2_rate": column_2,
        })

    from datetime import datetime, timezone

    result = {
        "status": "available" if lines else "no_lines",
        "hs6_code": hs6,
        "lines": lines,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source_url": source_url,
        "message": None if lines else "No matching U.S. HTS duty lines were returned by USITC.",
    }
    _CACHE[hs6] = (now, result)
    return result


if __name__ == "__main__":
    sample = fetch_usitc_tariffs("850760")
    assert sample["status"] == "available"
    assert any(line["hts_code"].startswith("850760") for line in sample["lines"])
    print(f"USITC returned {len(sample['lines'])} rated HTS lines for HS6 850760.")
