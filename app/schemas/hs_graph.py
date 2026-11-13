"""Pydantic v2 schemas and in-memory queries for the HSBench graph files."""

from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel, ConfigDict, RootModel, TypeAdapter

ROOT_CODE = "root"
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
        self._children: dict[str, list[str]] = defaultdict(list)
        self._parents: dict[str, list[str]] = defaultdict(list)
        for edge in taxonomy.edges:
            if edge.parent != ROOT_CODE and edge.parent not in self.nodes:
                raise ValueError(f"Unknown taxonomy parent: {edge.parent}")
            if edge.child not in self.nodes:
                raise ValueError(f"Unknown taxonomy child: {edge.child}")
            self._children[edge.parent].append(edge.child)
            self._parents[edge.child].append(edge.parent)

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
        return [self.nodes[child] for child in self._children.get(code, ())]

    def parents(self, code: str) -> list[HSNode]:
        return [self.nodes[parent] for parent in self._parents.get(code, ())]

    def exclusions(self, code: str) -> list[ExclusionRule]:
        return self.exclusion_rules.get(code, [])


if __name__ == "__main__":
    graph = HSGraph.load()
    assert graph.node("1类") is not None
    assert graph.children(ROOT_CODE)
    assert graph.exclusions("6类")
    print(f"Loaded {len(graph.nodes) - 1:,} HS nodes and {len(graph.exclusion_rules):,} exclusion groups.")

