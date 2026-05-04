from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import networkx as nx


class POIType(Enum):
    HOUSEHOLD = "household"
    SCHOOL = "school"
    OFFICE = "office"
    SHOP = "shop"
    PARK = "park"
    HEALTHCARE = "healthcare"


P_BASE: dict[POIType, float] = {
    POIType.HOUSEHOLD: 0.35,
    POIType.SCHOOL: 0.30,
    POIType.OFFICE: 0.20,
    POIType.SHOP: 0.10,
    POIType.PARK: 0.03,
    POIType.HEALTHCARE: 0.15,
}


@dataclass
class POINode:
    node_id: int
    poi_type: POIType
    p_base: float
    agents: list = field(default_factory=list)


class CityGraph:
    """NetworkX-backed graph of POI nodes representing a city."""

    def __init__(
        self,
        n_agents: int,
        p_base_override: dict[POIType, float] | None = None,
        p_base_multiplier: float = 1.0,
    ) -> None:
        self.graph = nx.Graph()
        self._nodes: dict[int, POINode] = {}
        self._next_id = 0

        p_base = {k: v * p_base_multiplier for k, v in P_BASE.items()}
        if p_base_override:
            p_base.update(p_base_override)

        n_households = max(1, n_agents // 4)
        self.households = self._add_nodes(POIType.HOUSEHOLD, n_households, p_base)
        self.schools = self._add_nodes(POIType.SCHOOL, 2, p_base)
        self.offices = self._add_nodes(POIType.OFFICE, 3, p_base)
        self.shops = self._add_nodes(POIType.SHOP, 2, p_base)
        self.parks = self._add_nodes(POIType.PARK, 1, p_base)
        self.healthcares = self._add_nodes(POIType.HEALTHCARE, 1, p_base)

    def _add_nodes(
        self, poi_type: POIType, count: int, p_base: dict[POIType, float]
    ) -> list[POINode]:
        nodes: list[POINode] = []
        for _ in range(count):
            node = POINode(self._next_id, poi_type, p_base[poi_type])
            self._nodes[self._next_id] = node
            self.graph.add_node(self._next_id)
            self._next_id += 1
            nodes.append(node)
        return nodes

    def get_node(self, node_id: int) -> POINode:
        return self._nodes[node_id]

    def all_nodes(self) -> list[POINode]:
        return list(self._nodes.values())

    def clear_agents(self) -> None:
        for node in self._nodes.values():
            node.agents.clear()

    def get_nodes_by_type(self, poi_type: POIType) -> list[POINode]:
        return [n for n in self._nodes.values() if n.poi_type == poi_type]
