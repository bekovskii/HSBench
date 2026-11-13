"""One search boundary over the optional Harvard FAISS index and local sample."""

import os
from functools import lru_cache
from pathlib import Path

from core.duty_lookup import search as sample_search
from core.search.language import detect_language

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def _load_faiss_resources():
    index_path = Path(os.environ.get("HS_INDEX_PATH", ROOT / "data" / "intermediate" / "hs12_4_index.parquet"))
    if not index_path.is_file():
        return None
    from sentence_transformers import SentenceTransformer

    from core.search.hs_classifier.retrieval import load_index

    frame, codes, index = load_index(index_path)
    model_name = os.environ.get("EMBEDDING_MODEL")
    if not model_name:
        raise RuntimeError("EMBEDDING_MODEL is required when HS_INDEX_PATH points to an index")
    model = SentenceTransformer(model_name, local_files_only=True)
    return frame, codes, index, model


def search_candidates(query: str, terms: list[str], limit: int = 5) -> tuple[list[dict], str, str]:
    """Return ranked HS4/HS6 candidates and a source label."""
    language = detect_language(query)
    resources = _load_faiss_resources()
    if resources is not None:
        from core.search.hs_classifier.retrieval import multi_search

        frame, codes, index, model = resources
        result = multi_search(
            data=frame,
            codes=codes,
            index=index,
            model=model,
            query=query,
            terms=terms,
            top_k_total=max(limit * 5, 25),
            top_k_bert=limit,
        ).head(limit)
        return result.to_dicts(), language, "harvard_hscode_mapping_faiss"

    results: dict[str, dict] = {}
    for text in [query, *terms]:
        for row in sample_search(text, limit=limit):
            results.setdefault(row["hs6_code"], row)
    return list(results.values())[:limit], language, "bundled_tariff_sample_keyword_search"

