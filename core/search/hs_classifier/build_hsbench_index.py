"""Build a multilingual FAISS source table from HSB's HS6 graph nodes."""

import json
from pathlib import Path

import numpy as np
import polars as pl
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[3]
MODEL_NAME = "intfloat/multilingual-e5-small"


def build_index(output_path: Path | None = None) -> Path:
    graph_path = ROOT / "data" / "graph" / "hs_nodes.json"
    nodes = json.loads(graph_path.read_text(encoding="utf-8"))
    by_code = {node["code"]: node for node in nodes}
    rows = []
    for node in nodes:
        code = node["code"]
        if node["level"] != "subheading" or len(code) != 6 or not code.isdigit():
            continue
        names = [by_code[parent]["name"] for parent in (code[:2], code[:4]) if parent in by_code]
        names.append(node["name"])
        rows.append({"code": code, "description": " / ".join(names)})

    assert len(rows) == 5615, f"Expected 5,615 HS6 graph nodes, got {len(rows)}"
    assert len({row["code"] for row in rows}) == len(rows), "HS6 codes must be unique"

    model = SentenceTransformer(MODEL_NAME)
    vectors = model.encode([f"passage: {row['description']}" for row in rows], show_progress_bar=True)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    assert vectors.shape == (len(rows), model.get_embedding_dimension())

    destination = output_path or ROOT / "data" / "intermediate" / "hsbench_hs6_index.parquet"
    destination.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows).with_columns(pl.Series("embedding", vectors.tolist())).write_parquet(destination)
    assert destination.is_file() and destination.stat().st_size > 0
    return destination


if __name__ == "__main__":
    print(f"Built 5,615-node multilingual HS6 index: {build_index()}")
