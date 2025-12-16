"""
Knowledge Graph - Graph-based knowledge representation for code concepts
"""

from typing import List, Dict, Optional
import networkx as nx
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Concept:
    """Represents a concept in the knowledge graph"""
    id: str
    type: str  # file, function, class, concept, pattern
    name: str
    properties: Dict

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "properties": self.properties
        }


@dataclass
class Relationship:
    """Represents a relationship between concepts"""
    source_id: str
    target_id: str
    relationship_type: str  # imports, calls, inherits, uses, related_to
    properties: Dict

    def to_dict(self) -> Dict:
        return {
            "source": self.source_id,
            "target": self.target_id,
            "type": self.relationship_type,
            "properties": self.properties
        }


class KnowledgeGraph:
    """
    Graph-based knowledge representation using NetworkX.

    Stores concepts (nodes) and relationships (edges) about code,
    patterns, and development knowledge.
    """

    def __init__(self, session_id: str):
        """
        Initialize knowledge graph.

        Args:
            session_id: Session identifier
        """
        self.session_id = session_id
        self.graph = nx.DiGraph()
        logger.info(f"Knowledge graph initialized for session {session_id}")

    def add_concept(self, concept: Concept):
        """
        Add a concept to the graph.

        Args:
            concept: Concept to add
        """
        self.graph.add_node(
            concept.id,
            type=concept.type,
            name=concept.name,
            **concept.properties
        )
        logger.debug(f"Added concept: {concept.id} ({concept.type})")

    def add_relationship(self, rel: Relationship):
        """
        Add a relationship between concepts.

        Args:
            rel: Relationship to add
        """
        self.graph.add_edge(
            rel.source_id,
            rel.target_id,
            type=rel.relationship_type,
            **rel.properties
        )
        logger.debug(
            f"Added relationship: {rel.source_id} -[{rel.relationship_type}]-> {rel.target_id}"
        )

    def get_concept(self, concept_id: str) -> Optional[Concept]:
        """
        Get a concept by ID.

        Args:
            concept_id: Concept identifier

        Returns:
            Concept if found, None otherwise
        """
        if concept_id not in self.graph:
            return None

        node_data = self.graph.nodes[concept_id]
        return Concept(
            id=concept_id,
            type=node_data.get("type"),
            name=node_data.get("name"),
            properties={k: v for k, v in node_data.items() if k not in ["type", "name"]}
        )

    def get_related_concepts(
        self,
        concept_id: str,
        relationship_type: Optional[str] = None,
        depth: int = 1
    ) -> List[Concept]:
        """
        Get concepts related to a given concept.

        Args:
            concept_id: Starting concept ID
            relationship_type: Optional filter by relationship type
            depth: Maximum traversal depth

        Returns:
            List of related concepts
        """
        if concept_id not in self.graph:
            return []

        related = []
        visited = set()
        queue = [(concept_id, 0)]

        while queue:
            current_id, current_depth = queue.pop(0)

            if current_id in visited or current_depth > depth:
                continue

            visited.add(current_id)

            # Get neighbors
            for neighbor in self.graph.neighbors(current_id):
                edge_data = self.graph.get_edge_data(current_id, neighbor)

                # Filter by relationship type if specified
                if relationship_type and edge_data.get("type") != relationship_type:
                    continue

                # Get concept
                concept = self.get_concept(neighbor)
                if concept:
                    related.append(concept)

                # Add to queue for further exploration
                if current_depth < depth:
                    queue.append((neighbor, current_depth + 1))

        return related

    def search_concepts(self, concept_type: str, properties: Dict = None) -> List[Concept]:
        """
        Search for concepts by type and properties.

        Args:
            concept_type: Type of concept to find
            properties: Optional property filters

        Returns:
            List of matching concepts
        """
        results = []

        for node_id, node_data in self.graph.nodes(data=True):
            # Check type
            if node_data.get("type") != concept_type:
                continue

            # Check properties if specified
            if properties:
                match = all(
                    node_data.get(k) == v
                    for k, v in properties.items()
                )
                if not match:
                    continue

            # Add to results
            concept = self.get_concept(node_id)
            if concept:
                results.append(concept)

        return results

    def get_statistics(self) -> Dict:
        """
        Get graph statistics.

        Returns:
            Statistics dictionary
        """
        stats = {
            "session_id": self.session_id,
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "by_type": {}
        }

        # Count by concept type
        for node_id, node_data in self.graph.nodes(data=True):
            concept_type = node_data.get("type", "unknown")
            stats["by_type"][concept_type] = stats["by_type"].get(concept_type, 0) + 1

        return stats

    def export_to_dict(self) -> Dict:
        """
        Export graph to dictionary for serialization.

        Returns:
            Graph data as dictionary
        """
        return {
            "session_id": self.session_id,
            "nodes": [
                {"id": node_id, **data}
                for node_id, data in self.graph.nodes(data=True)
            ],
            "edges": [
                {"source": u, "target": v, **data}
                for u, v, data in self.graph.edges(data=True)
            ]
        }

    def import_from_dict(self, data: Dict):
        """
        Import graph from dictionary.

        Args:
            data: Graph data dictionary
        """
        # Clear existing graph
        self.graph.clear()

        # Import nodes
        for node in data.get("nodes", []):
            node_id = node.pop("id")
            self.graph.add_node(node_id, **node)

        # Import edges
        for edge in data.get("edges", []):
            source = edge.pop("source")
            target = edge.pop("target")
            self.graph.add_edge(source, target, **edge)

        logger.info(
            f"Imported graph: {self.graph.number_of_nodes()} nodes, "
            f"{self.graph.number_of_edges()} edges"
        )

    def clear(self):
        """Clear all data from the graph"""
        self.graph.clear()
        logger.info(f"Cleared knowledge graph for session {self.session_id}")


# Global graphs per session
_session_graphs: Dict[str, KnowledgeGraph] = {}


def get_knowledge_graph(session_id: str) -> KnowledgeGraph:
    """
    Get knowledge graph for a session.

    Args:
        session_id: Session identifier

    Returns:
        KnowledgeGraph instance for the session
    """
    if session_id not in _session_graphs:
        _session_graphs[session_id] = KnowledgeGraph(session_id)
    return _session_graphs[session_id]
