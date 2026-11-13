"""Pydantic v2 schemas and in-memory queries for the HSBench graph files."""

import pickle
from pathlib import Path
from time import perf_counter

import networkx as nx
from pydantic import BaseModel, ConfigDict, RootModel, TypeAdapter

ROOT_CODE = "root"
PARENT_EDGE = "PARENT_OF_EDGE"
EXCLUDES_EDGE = "EXCLUDES_EDGE"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPOSITORY_ROOT / "data" / "graph"


class HSNode(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str
    level: str
    name: str
    abstract: str | None = None
    description: str | None = None


class TaxonomyEdge(BaseModel):
    parent: str
    child: str


class HSTaxonomy(BaseModel):
    levels: list[str]
    edges: list[TaxonomyEdge]


class ExclusionRule(BaseModel):
    target: str
    condition: str


class HSExclusions(RootModel[dict[str, list[ExclusionRule]]]):
    pass


_NODE_LIST = TypeAdapter(list[HSNode])


class HSGraph:
    """Validated HSBench nodes, hierarchy, and exclusion notes in memory."""

    def __init__(self, nodes: list[HSNode], taxonomy: HSTaxonomy, exclusions: HSExclusions):
        self.nodes = {node.code: node for node in nodes}
        if len(self.nodes) != len(nodes):
            raise ValueError("hs_nodes.json contains duplicate codes")
        self.nodes[ROOT_CODE] = HSNode(code=ROOT_CODE, level="root", name="HS taxonomy")
        self.levels = taxonomy.levels
        self.exclusion_rules = exclusions.root
        self.unresolved_targets: set[str] = set()
        self.graph = nx.DiGraph()
        self.graph.add_nodes_from((code, node.model_dump()) for code, node in self.nodes.items())
        for edge in taxonomy.edges:
            if edge.parent != ROOT_CODE and edge.parent not in self.nodes:
                raise ValueError(f"Unknown taxonomy parent: {edge.parent}")
            if edge.child not in self.nodes:
                raise ValueError(f"Unknown taxonomy child: {edge.child}")
            self._add_typed_edge(edge.parent, edge.child, PARENT_EDGE)
        for source, rules in self.exclusion_rules.items():
            if source not in self.nodes:
                raise ValueError(f"Unknown exclusion source: {source}")
            for rule in rules:
                target = self._resolve_target(rule.target)
                if target not in self.nodes:
                    self.unresolved_targets.add(target)
                    self.graph.add_node(target, code=target, level="unresolved", name="Unresolved exclusion target", unresolved=True)
                self._add_typed_edge(
                    source,
                    target,
                    EXCLUDES_EDGE,
                    exclusion={"condition": rule.condition, "source_target": rule.target},
                )

    def _resolve_target(self, target: str) -> str:
        if target in self.nodes:
            return target
        if target.isdigit():
            for width in (2, 4, 6):
                candidate = target.zfill(width)
                if candidate in self.nodes:
                    return candidate
        return target

    def _add_typed_edge(self, source: str, target: str, edge_type: str, **attrs) -> None:
        data = self.graph.get_edge_data(source, target)
        if data is None:
            data = {"edge_types": []}
            self.graph.add_edge(source, target, **data)
            data = self.graph[source][target]
        if edge_type not in data["edge_types"]:
            data["edge_types"].append(edge_type)
        data["edge_type"] = edge_type if len(data["edge_types"]) == 1 else "MULTI_EDGE"
        if edge_type == EXCLUDES_EDGE:
            data.setdefault("exclusions", []).append(attrs["exclusion"])
            data.setdefault("condition", attrs["exclusion"]["condition"])
            data.setdefault("source_target", attrs["exclusion"]["source_target"])
        else:
            data.update(attrs)

    @classmethod
    def load(cls, repository_root: Path = REPOSITORY_ROOT) -> "HSGraph":
        knowledge = repository_root / "knowledge"
        if not knowledge.is_dir():
            knowledge = repository_root / "data" / "graph"
        nodes = _NODE_LIST.validate_json((knowledge / "hs_nodes.json").read_bytes())
        taxonomy = HSTaxonomy.model_validate_json((knowledge / "hs_taxonomy.json").read_bytes())
        exclusions = HSExclusions.model_validate_json((knowledge / "hs_exclusions.json").read_bytes())
        return cls(nodes, taxonomy, exclusions)

    def node(self, code: str) -> HSNode | None:
        return self.nodes.get(code)

    def children(self, code: str) -> list[HSNode]:
        return [self.nodes[target] for _, target, data in self.graph.out_edges(code, data=True) if PARENT_EDGE in data["edge_types"] and target in self.nodes]

    def parents(self, code: str) -> list[HSNode]:
        return [self.nodes[source] for source, _, data in self.graph.in_edges(code, data=True) if PARENT_EDGE in data["edge_types"] and source in self.nodes]

    def exclusions(self, code: str) -> list[ExclusionRule]:
        return [
            ExclusionRule(target=entry["source_target"], condition=entry["condition"])
            for _, _, data in self.graph.out_edges(code, data=True)
            if EXCLUDES_EDGE in data["edge_types"]
            for entry in data.get("exclusions", [])
        ]

    def save(self, path: Path = REPOSITORY_ROOT / "graph.pkl") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as file:
            pickle.dump(self.graph, file, protocol=pickle.HIGHEST_PROTOCOL)
        return path

    @staticmethod
    def load_pickle(path: Path = REPOSITORY_ROOT / "graph.pkl") -> nx.DiGraph:
        # Only load artifacts generated from trusted source data; pickle can execute code.
        with path.open("rb") as file:
            graph = pickle.load(file)
        if not isinstance(graph, nx.DiGraph):
            raise TypeError(f"Expected networkx.DiGraph in {path}")
        return graph


if __name__ == "__main__":
    graph = HSGraph.load()
    assert graph.node("1类") is not None
    assert graph.children(ROOT_CODE)
    assert graph.exclusions("6类")
    started = perf_counter()
    assert graph.graph.has_edge("6类", graph._resolve_target("26"))
    assert EXCLUDES_EDGE in graph.graph.edges["6类", graph._resolve_target("26")]["edge_types"]
    query_ms = (perf_counter() - started) * 1000
    assert query_ms < 50
    output = graph.save()
    loaded = HSGraph.load_pickle(output)
    assert loaded.has_edge("6类", graph._resolve_target("26"))
    print(
        f"Saved {graph.graph.number_of_nodes():,} nodes / {graph.graph.number_of_edges():,} edges to {output}; "
        f"exclusion lookup {query_ms:.3f} ms; unresolved targets {ascii(sorted(graph.unresolved_targets))}."
    )

