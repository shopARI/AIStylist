"""
Memory Fallback Manager
Provides fallback strategies when primary memory systems fail
Ensures system continues working even without perfect memory
"""

import logging
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import deque, defaultdict
from dataclasses import dataclass, field
import hashlib

logger = logging.getLogger("services.memory.fallback_manager")


@dataclass
class MemorySnapshot:
    """Snapshot of memory state."""
    timestamp: datetime
    user_id: str
    conversation_summary: str
    key_preferences: Dict[str, Any]
    recent_products: List[str]
    interaction_count: int


@dataclass
class FallbackMemoryEntry:
    """Fallback memory storage entry."""
    user_id: str
    session_id: str
    timestamp: datetime
    data: Dict[str, Any]
    ttl: int = 3600  # 1 hour default
    
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        age = (datetime.now() - self.timestamp).total_seconds()
        return age > self.ttl


class MemoryFallbackManager:
    """
    Manages fallback strategies for memory system failures.
    Provides degraded but functional service when primary memory fails.
    """
    
    def __init__(
        self,
        max_memory_per_user: int = 100,
        max_total_entries: int = 10000,
        default_ttl: int = 3600,
        enable_compression: bool = True
    ):
        """
        Initialize memory fallback manager.
        
        Args:
            max_memory_per_user: Maximum memory entries per user
            max_total_entries: Maximum total entries
            default_ttl: Default TTL for entries
            enable_compression: Enable data compression
        """
        self.max_memory_per_user = max_memory_per_user
        self.max_total_entries = max_total_entries
        self.default_ttl = default_ttl
        self.enable_compression = enable_compression
        
        # In-memory storage (fallback when databases fail)
        self.memory_store: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_memory_per_user))
        self.session_store: Dict[str, Dict[str, Any]] = {}
        self.preference_cache: Dict[str, Dict[str, Any]] = {}
        
        # Statistics
        self.stats = {
            "fallback_activations": 0,
            "memory_hits": 0,
            "memory_misses": 0,
            "evictions": 0,
            "compressions": 0
        }
        
        # Cleanup task
        self._cleanup_task = None
        self._running = True
        
        logger.info("Memory fallback manager initialized")
    
    async def initialize(self):
        """Initialize fallback manager."""
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_worker())
        logger.info("Memory fallback cleanup task started")
    
    async def _cleanup_worker(self):
        """Background cleanup of expired entries."""
        while self._running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                if not self._running:
                    break
                
                expired_count = await self._cleanup_expired_entries()
                
                if expired_count > 0:
                    logger.debug(f"Cleaned up {expired_count} expired memory entries")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in memory cleanup: {e}")
    
    async def _cleanup_expired_entries(self) -> int:
        """Clean up expired entries."""
        expired_count = 0
        
        # Clean up session store
        expired_sessions = []
        for session_id, data in self.session_store.items():
            if "timestamp" in data:
                age = (datetime.now() - data["timestamp"]).total_seconds()
                if age > self.default_ttl:
                    expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.session_store[session_id]
            expired_count += 1
        
        # Clean up old memory entries
        for user_id in list(self.memory_store.keys()):
            entries = self.memory_store[user_id]
            original_len = len(entries)
            
            # Filter out expired entries
            valid_entries = [
                entry for entry in entries
                if not self._is_entry_expired(entry)
            ]
            
            if len(valid_entries) < original_len:
                self.memory_store[user_id] = deque(valid_entries, maxlen=self.max_memory_per_user)
                expired_count += original_len - len(valid_entries)
        
        self.stats["evictions"] += expired_count
        return expired_count
    
    def _is_entry_expired(self, entry: Any) -> bool:
        """Check if entry is expired."""
        if isinstance(entry, FallbackMemoryEntry):
            return entry.is_expired()
        elif isinstance(entry, dict) and "timestamp" in entry:
            timestamp = entry["timestamp"]
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            age = (datetime.now() - timestamp).total_seconds()
            return age > self.default_ttl
        return False
    
    async def store_memory(
        self,
        user_id: str,
        session_id: str,
        memory_type: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Store memory in fallback system.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            memory_type: Type of memory
            data: Memory data
            ttl: Optional TTL
            
        Returns:
            Success status
        """
        try:
            self.stats["fallback_activations"] += 1
            
            # Create memory entry
            entry = FallbackMemoryEntry(
                user_id=user_id,
                session_id=session_id,
                timestamp=datetime.now(),
                data={
                    "type": memory_type,
                    "content": data
                },
                ttl=ttl or self.default_ttl
            )
            
            # Compress if enabled
            if self.enable_compression and len(json.dumps(data)) > 1000:
                entry.data = self._compress_data(entry.data)
                self.stats["compressions"] += 1
            
            # Store in user's memory
            self.memory_store[user_id].append(entry)
            
            # Update session store
            if session_id not in self.session_store:
                self.session_store[session_id] = {
                    "user_id": user_id,
                    "created_at": datetime.now(),
                    "timestamp": datetime.now()
                }
            else:
                self.session_store[session_id]["timestamp"] = datetime.now()
            
            # Check total size limit
            total_entries = sum(len(entries) for entries in self.memory_store.values())
            if total_entries > self.max_total_entries:
                await self._evict_oldest_entries()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store fallback memory: {e}")
            return False
    
    async def retrieve_memory(
        self,
        user_id: str,
        memory_type: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve memory from fallback system.
        
        Args:
            user_id: User identifier
            memory_type: Optional memory type filter
            session_id: Optional session filter
            limit: Maximum results
            
        Returns:
            List of memory entries
        """
        if user_id not in self.memory_store:
            self.stats["memory_misses"] += 1
            return []
        
        entries = self.memory_store[user_id]
        results = []
        
        for entry in reversed(entries):  # Most recent first
            if isinstance(entry, FallbackMemoryEntry):
                # Check filters
                if memory_type and entry.data.get("type") != memory_type:
                    continue
                if session_id and entry.session_id != session_id:
                    continue
                
                # Check expiration
                if not entry.is_expired():
                    # Decompress if needed
                    data = self._decompress_data(entry.data) if self._is_compressed(entry.data) else entry.data
                    
                    results.append({
                        "session_id": entry.session_id,
                        "timestamp": entry.timestamp.isoformat(),
                        "data": data
                    })
                    
                    if len(results) >= limit:
                        break
        
        if results:
            self.stats["memory_hits"] += 1
        else:
            self.stats["memory_misses"] += 1
        
        return results
    
    async def store_preferences(
        self,
        user_id: str,
        preferences: Dict[str, Any]
    ) -> bool:
        """
        Store user preferences in fallback.
        
        Args:
            user_id: User identifier
            preferences: Preferences dictionary
            
        Returns:
            Success status
        """
        try:
            # Merge with existing preferences
            if user_id in self.preference_cache:
                existing = self.preference_cache[user_id]
                # Deep merge
                for key, value in preferences.items():
                    if isinstance(value, list) and key in existing and isinstance(existing[key], list):
                        # Merge lists
                        existing[key] = list(set(existing[key] + value))
                    elif isinstance(value, dict) and key in existing and isinstance(existing[key], dict):
                        # Merge dicts
                        existing[key].update(value)
                    else:
                        # Replace
                        existing[key] = value
            else:
                self.preference_cache[user_id] = preferences.copy()
            
            # Add timestamp
            self.preference_cache[user_id]["updated_at"] = datetime.now().isoformat()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store preferences: {e}")
            return False
    
    async def retrieve_preferences(
        self,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve user preferences from fallback.
        
        Args:
            user_id: User identifier
            
        Returns:
            Preferences dictionary or None
        """
        return self.preference_cache.get(user_id)
    
    async def create_memory_snapshot(
        self,
        user_id: str,
        session_id: str
    ) -> Optional[MemorySnapshot]:
        """
        Create a snapshot of current memory state.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            
        Returns:
            Memory snapshot or None
        """
        try:
            # Get recent memories
            memories = await self.retrieve_memory(user_id, limit=20)
            
            # Get preferences
            preferences = await self.retrieve_preferences(user_id) or {}
            
            # Extract key information
            conversation_summary = self._generate_summary(memories)
            recent_products = self._extract_recent_products(memories)
            
            snapshot = MemorySnapshot(
                timestamp=datetime.now(),
                user_id=user_id,
                conversation_summary=conversation_summary,
                key_preferences=preferences,
                recent_products=recent_products,
                interaction_count=len(memories)
            )
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Failed to create memory snapshot: {e}")
            return None
    
    def _generate_summary(self, memories: List[Dict[str, Any]]) -> str:
        """Generate summary from memories."""
        if not memories:
            return "No recent activity"
        
        # Extract key topics
        topics = set()
        for memory in memories[:5]:  # Last 5 memories
            data = memory.get("data", {})
            content = data.get("content", {})
            
            if "query" in content:
                topics.add(content["query"][:30])
            elif "intent" in content:
                topics.add(content["intent"])
        
        if topics:
            return f"Recent topics: {', '.join(list(topics)[:3])}"
        
        return f"Active session with {len(memories)} interactions"
    
    def _extract_recent_products(self, memories: List[Dict[str, Any]]) -> List[str]:
        """Extract recent product IDs from memories."""
        products = []
        
        for memory in memories:
            data = memory.get("data", {})
            content = data.get("content", {})
            
            if "products" in content:
                product_list = content["products"]
                if isinstance(product_list, list):
                    products.extend([str(p) for p in product_list[:5]])
            elif "product_id" in content:
                products.append(str(content["product_id"]))
        
        # Return unique products
        seen = set()
        unique = []
        for p in products:
            if p not in seen:
                seen.add(p)
                unique.append(p)
                if len(unique) >= 10:
                    break
        
        return unique
    
    async def _evict_oldest_entries(self):
        """Evict oldest entries when over limit."""
        # Find user with most entries
        if not self.memory_store:
            return
        
        user_with_most = max(self.memory_store.keys(), key=lambda k: len(self.memory_store[k]))
        
        # Remove oldest entry
        if self.memory_store[user_with_most]:
            self.memory_store[user_with_most].popleft()
            self.stats["evictions"] += 1
    
    def _compress_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Compress data for storage."""
        try:
            import zlib
            import base64
            
            json_str = json.dumps(data)
            compressed = zlib.compress(json_str.encode())
            encoded = base64.b64encode(compressed).decode()
            
            return {
                "_compressed": True,
                "data": encoded
            }
        except:
            return data
    
    def _decompress_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Decompress data from storage."""
        try:
            import zlib
            import base64
            
            encoded = data["data"]
            compressed = base64.b64decode(encoded)
            json_str = zlib.decompress(compressed).decode()
            
            return json.loads(json_str)
        except:
            return data
    
    def _is_compressed(self, data: Dict[str, Any]) -> bool:
        """Check if data is compressed."""
        return isinstance(data, dict) and data.get("_compressed") == True
    
    async def export_user_memory(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Export all memory for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Exported memory dictionary
        """
        memories = await self.retrieve_memory(user_id, limit=1000)
        preferences = await self.retrieve_preferences(user_id)
        
        return {
            "user_id": user_id,
            "export_timestamp": datetime.now().isoformat(),
            "memories": memories,
            "preferences": preferences,
            "memory_count": len(memories)
        }
    
    async def import_user_memory(
        self,
        user_id: str,
        export_data: Dict[str, Any]
    ) -> bool:
        """
        Import memory for a user.
        
        Args:
            user_id: User identifier
            export_data: Exported memory data
            
        Returns:
            Success status
        """
        try:
            # Import preferences
            if "preferences" in export_data:
                await self.store_preferences(user_id, export_data["preferences"])
            
            # Import memories
            if "memories" in export_data:
                for memory in export_data["memories"]:
                    session_id = memory.get("session_id", "imported")
                    data = memory.get("data", {})
                    
                    await self.store_memory(
                        user_id=user_id,
                        session_id=session_id,
                        memory_type=data.get("type", "imported"),
                        data=data.get("content", data)
                    )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to import memory: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get fallback manager statistics."""
        total_memories = sum(len(entries) for entries in self.memory_store.values())
        
        return {
            "total_users": len(self.memory_store),
            "total_memories": total_memories,
            "total_sessions": len(self.session_store),
            "cached_preferences": len(self.preference_cache),
            "fallback_activations": self.stats["fallback_activations"],
            "memory_hits": self.stats["memory_hits"],
            "memory_misses": self.stats["memory_misses"],
            "evictions": self.stats["evictions"],
            "compressions": self.stats["compressions"],
            "hit_rate": (
                f"{self.stats['memory_hits'] / (self.stats['memory_hits'] + self.stats['memory_misses']) * 100:.1f}%"
                if (self.stats['memory_hits'] + self.stats['memory_misses']) > 0
                else "0%"
            )
        }
    
    async def shutdown(self):
        """Shutdown fallback manager."""
        logger.info("Shutting down memory fallback manager")
        
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Memory fallback manager shutdown complete")


# Global instance
_fallback_manager: Optional[MemoryFallbackManager] = None


def get_fallback_manager() -> MemoryFallbackManager:
    """
    Get global fallback manager instance.
    
    Returns:
        MemoryFallbackManager instance
    """
    global _fallback_manager
    
    if _fallback_manager is None:
        _fallback_manager = MemoryFallbackManager()
    
    return _fallback_manager


# Exports
__all__ = [
    'MemoryFallbackManager',
    'MemorySnapshot',
    'FallbackMemoryEntry',
    'get_fallback_manager'
]