"""Lookup against the upstream four-market sample; not a live tariff service."""

import csv
from functools import lru_cache
from pathlib import Path

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "tariffs" / "hs6-tariff-sample.csv"


@lru_cache(maxsize=1)
def _rows() -> tuple[dict[str, str], ...]:
    with SAMPLE.open(encoding="utf-8", newline="") as file:
        return tuple(csv.DictReader(file))


def search(keyword: str, limit: int = 3) -> list[dict]:
    terms = {word.casefold() for word in keyword.split() if len(word) > 2}
    if not terms:
        return []
    matches = []
    for row in _rows():
        words = {word.strip(".,;()/-").casefold() for word in row["description"].split()}
        score = len(terms & words)
        if score:
            matches.append((score, row))
    matches.sort(key=lambda pair: (-pair[0], pair[1]["hs6_code"]))
    return [row for _, row in matches[:limit]]


def lookup_hs6(code: str) -> dict[str, str] | None:
    normalized = "".join(character for character in code if character.isdigit())
    if len(normalized) != 6:
        return None
    return next((row for row in _rows() if row["hs6_code"] == normalized), None)


def mfn_rates(code: str) -> dict[str, float | None]:
    row = lookup_hs6(code)
    if row is None:
        return {market: None for market in ("US", "EU", "UK", "CN")}
    return {
        market: float(row[f"{market.lower()}_mfn_pct"])
        if row.get(f"{market.lower()}_mfn_pct", "") != ""
        else None
        for market in ("US", "EU", "UK", "CN")
    }

