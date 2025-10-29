"""
Mem0 Memory Provider for CrewAI
Replaces Redis with Mem0 for episodic, semantic, and factual memory.
Integrates with Neo4j graph memory and Qdrant vector store.
"""
import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from mem0 import Memory

logger = logging.getLogger("crewai.memory.mem0_provider")


class Mem0MemoryProvider:
    """
    Memory provider using Mem0 with graph memory support.
    Implements three memory types:
    - Factual: User preferences, stable information
    - Episodic: Conversation history, interactions
    - Semantic: Concept relationships (user-product, style-brand)
    """

    def __init__(self, user_id: str, session_id: str):
        """
        Initialize Mem0 memory provider.

        Args:
            user_id: User identifier
            session_id: Current session identifier
        """
        self.user_id = user_id
        self.session_id = session_id

        # Configure Mem0 with Neo4j graph store and Qdrant vector store
        config = {
            "graph_store": {
                "provider": "neo4j",
                "config": {
                    "url": os.getenv("NEO4J_URI", "neo4j://localhost:7687"),
                    "username": os.getenv("NEO4J_USER", "neo4j"),
                    "password": os.getenv("NEO4J_PASSWORD", "password"),
                    "database": "users"  # Use users database for graph memory
                }
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "url": os.getenv("QDRANT_URL", "http://localhost:6333"),
                    "api_key": os.getenv("QDRANT_API_KEY"),
                    "collection_name": "mem0_memories"
                }
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "gpt-4o-mini",
                    "api_key": os.getenv("OPENAI_API_KEY")
                }
            }
        }

        self.memory = Memory.from_config(config)
        logger.info(f"Initialized Mem0 memory provider for user: {user_id}, session: {session_id}")

    # ======================
    # EPISODIC MEMORY
    # ======================

    async def add_episodic(self, interaction: str, metadata: Optional[Dict] = None) -> bool:
        """
        Add episodic memory (conversation turn, search interaction).

        Args:
            interaction: Description of the interaction
            metadata: Optional metadata (timestamp, products, etc.)

        Returns:
            Success boolean
        """
        try:
            full_metadata = {
                "memory_type": "episodic",
                "session_id": self.session_id,
                "timestamp": datetime.now().isoformat(),
                **(metadata or {})
            }

            # Add memory for this user
            self.memory.add(
                messages=[{"role": "user", "content": interaction}],
                user_id=self.user_id,
                metadata=full_metadata
            )

            logger.debug(f"Added episodic memory for user {self.user_id}: {interaction[:50]}")
            return True

        except Exception as e:
            logger.error(f"Failed to add episodic memory: {e}")
            return False

    async def get_episodic(self, query: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """
        Retrieve episodic memories (recent conversation history).

        Args:
            query: Optional query to search memories
            limit: Maximum number of memories to return

        Returns:
            List of episodic memories
        """
        try:
            if query:
                # Search memories with query
                results = self.memory.search(
                    query=query,
                    user_id=self.user_id,
                    limit=limit,
                    filters={"memory_type": "episodic"}
                )
            else:
                # Get all episodic memories
                results = self.memory.get_all(
                    user_id=self.user_id,
                    limit=limit,
                    filters={"memory_type": "episodic"}
                )

            memories = []
            for result in results.get("results", []):
                memories.append({
                    "content": result.get("memory"),
                    "metadata": result.get("metadata", {}),
                    "timestamp": result.get("created_at")
                })

            logger.debug(f"Retrieved {len(memories)} episodic memories for user {self.user_id}")
            return memories

        except Exception as e:
            logger.error(f"Failed to get episodic memories: {e}")
            return []

    # ======================
    # FACTUAL MEMORY
    # ======================

    async def add_factual(self, fact: str, category: str, metadata: Optional[Dict] = None) -> bool:
        """
        Add factual memory (user preference, account detail).

        Args:
            fact: Factual statement (e.g., "User prefers minimalist style")
            category: Category of fact (preference, account, domain)
            metadata: Optional metadata

        Returns:
            Success boolean
        """
        try:
            full_metadata = {
                "memory_type": "factual",
                "category": category,
                "timestamp": datetime.now().isoformat(),
                **(metadata or {})
            }

            self.memory.add(
                messages=[{"role": "assistant", "content": fact}],
                user_id=self.user_id,
                metadata=full_metadata
            )

            logger.debug(f"Added factual memory for user {self.user_id}: {fact[:50]}")
            return True

        except Exception as e:
            logger.error(f"Failed to add factual memory: {e}")
            return False

    async def get_factual(self, category: Optional[str] = None) -> List[Dict]:
        """
        Retrieve factual memories (user preferences, account info).

        Args:
            category: Optional category filter

        Returns:
            List of factual memories
        """
        try:
            filters = {"memory_type": "factual"}
            if category:
                filters["category"] = category

            results = self.memory.get_all(
                user_id=self.user_id,
                filters=filters
            )

            memories = []
            for result in results.get("results", []):
                memories.append({
                    "content": result.get("memory"),
                    "category": result.get("metadata", {}).get("category"),
                    "metadata": result.get("metadata", {}),
                    "timestamp": result.get("created_at")
                })

            logger.debug(f"Retrieved {len(memories)} factual memories for user {self.user_id}")
            return memories

        except Exception as e:
            logger.error(f"Failed to get factual memories: {e}")
            return []

    # ======================
    # SEMANTIC MEMORY (Graph Relationships)
    # ======================

    async def add_semantic(self, relationship: str, metadata: Optional[Dict] = None) -> bool:
        """
        Add semantic memory (concept relationship).

        Args:
            relationship: Relationship description (e.g., "User likes Brand X for casual occasions")
            metadata: Optional metadata (entities, relationship type)

        Returns:
            Success boolean
        """
        try:
            full_metadata = {
                "memory_type": "semantic",
                "timestamp": datetime.now().isoformat(),
                **(metadata or {})
            }

            # Mem0 will extract entities and create graph relationships
            self.memory.add(
                messages=[{"role": "assistant", "content": relationship}],
                user_id=self.user_id,
                metadata=full_metadata
            )

            logger.debug(f"Added semantic memory for user {self.user_id}: {relationship[:50]}")
            return True

        except Exception as e:
            logger.error(f"Failed to add semantic memory: {e}")
            return False

    async def get_semantic(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Retrieve semantic memories (concept relationships).

        Args:
            query: Query to search relationships
            limit: Maximum results

        Returns:
            List of semantic memories
        """
        try:
            results = self.memory.search(
                query=query,
                user_id=self.user_id,
                limit=limit,
                filters={"memory_type": "semantic"}
            )

            memories = []
            for result in results.get("results", []):
                memories.append({
                    "content": result.get("memory"),
                    "metadata": result.get("metadata", {}),
                    "score": result.get("score", 0.0)
                })

            logger.debug(f"Retrieved {len(memories)} semantic memories for user {self.user_id}")
            return memories

        except Exception as e:
            logger.error(f"Failed to get semantic memories: {e}")
            return []

    # ======================
    # COMPATIBILITY LAYER (Redis-like methods)
    # ======================

    async def save_short_term(self, data: Dict[str, Any]) -> bool:
        """
        Save to short-term memory (mapped to episodic).
        Maintains compatibility with existing code.

        Args:
            data: Memory data

        Returns:
            Success boolean
        """
        interaction = data.get("interaction", str(data))
        return await self.add_episodic(interaction, data)

    async def load_short_term(self, limit: int = 20) -> List[Dict]:
        """
        Load from short-term memory (episodic).
        Maintains compatibility with existing code.

        Args:
            limit: Maximum items

        Returns:
            List of memories
        """
        return await self.get_episodic(limit=limit)

    async def save_long_term(self, key: str, value: Any) -> bool:
        """
        Save to long-term memory (mapped to factual).
        Maintains compatibility with existing code.

        Args:
            key: Memory key
            value: Memory value

        Returns:
            Success boolean
        """
        fact = f"{key}: {value}"
        return await self.add_factual(fact, category="long_term")

    async def load_long_term(self, key: Optional[str] = None) -> Any:
        """
        Load from long-term memory (factual).
        Maintains compatibility with existing code.

        Args:
            key: Optional key filter

        Returns:
            Memory data
        """
        memories = await self.get_factual(category="long_term")

        if key:
            # Find specific key
            for mem in memories:
                if mem["content"].startswith(f"{key}:"):
                    return mem
            return None
        else:
            # Return all as dict
            result = {}
            for mem in memories:
                content = mem["content"]
                if ":" in content:
                    k, v = content.split(":", 1)
                    result[k.strip()] = v.strip()
            return result

    async def save_entity(self, entity_type: str, entity_value: str, metadata: Optional[Dict] = None) -> bool:
        """
        Save entity (mapped to semantic memory with graph relationships).
        Maintains compatibility with existing code.

        Args:
            entity_type: Entity type (product, brand, category)
            entity_value: Entity value
            metadata: Optional metadata

        Returns:
            Success boolean
        """
        relationship = f"User interacted with {entity_type}: {entity_value}"
        entity_metadata = {
            "entity_type": entity_type,
            "entity_value": entity_value,
            **(metadata or {})
        }
        return await self.add_semantic(relationship, entity_metadata)

    async def load_entities(self, entity_type: Optional[str] = None) -> List[Dict]:
        """
        Load entities (from semantic memory).
        Maintains compatibility with existing code.

        Args:
            entity_type: Optional entity type filter

        Returns:
            List of entities
        """
        query = f"{entity_type} interactions" if entity_type else "entity interactions"
        memories = await self.get_semantic(query, limit=50)

        # Filter by entity type if specified
        if entity_type:
            memories = [
                m for m in memories
                if m.get("metadata", {}).get("entity_type") == entity_type
            ]

        return memories

    # ======================
    # UTILITY METHODS
    # ======================

    async def clear_session_memory(self) -> bool:
        """
        Clear memories for current session.

        Returns:
            Success boolean
        """
        try:
            # Delete memories with current session_id
            results = self.memory.get_all(
                user_id=self.user_id,
                filters={"session_id": self.session_id}
            )

            for result in results.get("results", []):
                memory_id = result.get("id")
                if memory_id:
                    self.memory.delete(memory_id=memory_id)

            logger.info(f"Cleared session memory for user {self.user_id}, session {self.session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to clear session memory: {e}")
            return False

    async def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get memory statistics.

        Returns:
            Dictionary with stats
        """
        try:
            episodic = await self.get_episodic()
            factual = await self.get_factual()

            stats = {
                "user_id": self.user_id,
                "session_id": self.session_id,
                "episodic_count": len(episodic),
                "factual_count": len(factual),
                "timestamp": datetime.now().isoformat()
            }

            return stats

        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {}

    async def search_all(self, query: str, limit: int = 10) -> Dict[str, List[Dict]]:
        """
        Search across all memory types.

        Args:
            query: Search query
            limit: Maximum results per type

        Returns:
            Dictionary with results by memory type
        """
        try:
            results = self.memory.search(
                query=query,
                user_id=self.user_id,
                limit=limit * 3  # Get more to split by type
            )

            episodic = []
            factual = []
            semantic = []

            for result in results.get("results", []):
                mem_type = result.get("metadata", {}).get("memory_type")
                mem_data = {
                    "content": result.get("memory"),
                    "metadata": result.get("metadata", {}),
                    "score": result.get("score", 0.0)
                }

                if mem_type == "episodic":
                    episodic.append(mem_data)
                elif mem_type == "factual":
                    factual.append(mem_data)
                elif mem_type == "semantic":
                    semantic.append(mem_data)

            return {
                "episodic": episodic[:limit],
                "factual": factual[:limit],
                "semantic": semantic[:limit]
            }

        except Exception as e:
            logger.error(f"Failed to search all memories: {e}")
            return {"episodic": [], "factual": [], "semantic": []}


def create_mem0_memory_provider(user_id: str, session_id: str) -> Mem0MemoryProvider:
    """
    Factory function to create Mem0 memory provider.

    Args:
        user_id: User identifier
        session_id: Session identifier

    Returns:
        Mem0MemoryProvider instance
    """
    return Mem0MemoryProvider(user_id, session_id)
