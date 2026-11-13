"""Compatibility import for the WP-0.1 graph implementation."""

from app.schemas.hs_graph import (
    DATA_DIR,
    ROOT_CODE,
    ExclusionRule,
    HSExclusions,
    HSGraph,
    HSNode,
    HSTaxonomy,
    TaxonomyEdge,
)

__all__ = [
    "DATA_DIR",
    "ROOT_CODE",
    "ExclusionRule",
    "HSExclusions",
    "HSGraph",
    "HSNode",
    "HSTaxonomy",
    "TaxonomyEdge",
]


if __name__ == "__main__":
    graph = HSGraph.build_from_source()
    assert graph.node("1类") is not None
    assert graph.children(ROOT_CODE)
    assert graph.exclusions("6类")
    print(f"Loaded {len(graph.nodes) - 1:,} HS nodes and {len(graph.exclusion_rules):,} exclusion groups.")
