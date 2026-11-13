"""Lookup against the upstream four-market sample; not a live tariff service."""

import csv
from pathlib import Path

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "tariffs" / "hs6-tariff-sample.csv"


def search(keyword: str, limit: int = 3) -> list[dict]:
    terms = {word.casefold() for word in keyword.split() if len(word) > 2}
    if not terms:
        return []
    matches = []
    with SAMPLE.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            words = {word.strip(".,;()/-").casefold() for word in row["description"].split()}
            score = len(terms & words)
            if score:
                matches.append((score, row))
    matches.sort(key=lambda pair: (-pair[0], pair[1]["hs6_code"]))
    return [row for _, row in matches[:limit]]

