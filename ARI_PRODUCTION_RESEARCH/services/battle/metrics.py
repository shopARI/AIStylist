"""
Battle Metrics - Comprehensive metrics tracking for battles
Tracks performance, patterns, and system health
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import Counter, deque
from dataclasses import dataclass, field
import statistics

logger = logging.getLogger("services.battle.metrics")

@dataclass
class BattleRecord:
    """Record of a single battle."""
    battle_id: str
    query: str
    timestamp: datetime
    cypher_count: int
    vibe_count: int
    final_count: int
    winner: str
    battle_time: float
    ml_enhanced: bool
    cache_hit: bool = False
    timeout: bool = False
    error: Optional[str] = None

class BattleMetrics:
    """
    Comprehensive metrics tracking for battle system.
    Tracks performance, patterns, and provides insights.
    """
    
    def __init__(self, history_size: int = 1000):
        """
        Initialize battle metrics tracker.
        
        Args:
            history_size: Maximum number of battles to keep in history
        """
        self.history_size = history_size
        self.battle_history = deque(maxlen=history_size)
        
        # Counters
        self.total_battles = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.timeouts = 0
        self.errors = 0
        
        # Winner tracking
        self.winner_counts = Counter()
        
        # Performance tracking
        self.battle_times = deque(maxlen=100)
        self.query_patterns = Counter()
        
        # ML enhancement tracking
        self.ml_enhanced_battles = 0
        self.ml_performance = {
            "with_ml": {"wins": 0, "total": 0, "avg_time": 0.0},
            "without_ml": {"wins": 0, "total": 0, "avg_time": 0.0}
        }
        
        # Time-based metrics
        self.hourly_stats = {}
        self.daily_stats = {}
        
        logger.info(f"BattleMetrics initialized with history_size={history_size}")
    
    def record_battle(
        self,
        query: str,
        cypher_count: int,
        vibe_count: int,
        final_count: int,
        battle_time: float,
        winner: str,
        ml_enhanced: bool = False,
        cache_hit: bool = False
    ):
        """
        Record a successful battle.
        
        Args:
            query: Search query
            cypher_count: Number of CypherBot results
            vibe_count: Number of VibeBot results
            final_count: Number of final results
            battle_time: Time taken for battle
            winner: Winner of the battle
            ml_enhanced: Whether ML was used
            cache_hit: Whether result was from cache
        """
        self.total_battles += 1
        
        # Create battle record
        record = BattleRecord(
            battle_id=f"battle_{self.total_battles}",
            query=query[:100],  # Truncate long queries
            timestamp=datetime.now(),
            cypher_count=cypher_count,
            vibe_count=vibe_count,
            final_count=final_count,
            winner=winner,
            battle_time=battle_time,
            ml_enhanced=ml_enhanced,
            cache_hit=cache_hit
        )
        
        self.battle_history.append(record)
        
        # Update counters
        if not cache_hit:
            self.cache_misses += 1
            self.battle_times.append(battle_time)
            self.winner_counts[winner] += 1
            
            # Track ML performance
            if ml_enhanced:
                self.ml_enhanced_battles += 1
                self._update_ml_performance(True, winner, battle_time)
            else:
                self._update_ml_performance(False, winner, battle_time)
        
        # Track query patterns
        self._track_query_pattern(query)
        
        # Update time-based stats
        self._update_time_stats(record)
        
        if self.total_battles % 100 == 0:
            self._cleanup_old_stats()
            
        logger.debug(f"Recorded battle: winner={winner}, time={battle_time:.2f}s, ml={ml_enhanced}")
    
    def record_cache_hit(self, query: str, cached_result: Dict[str, Any]):
        """
        Record a cache hit.
        
        Args:
            query: Search query
            cached_result: Cached result data
        """
        self.total_battles += 1
        self.cache_hits += 1
        
        # Create minimal battle record for cache hit
        record = BattleRecord(
            battle_id=f"battle_{self.total_battles}",
            query=query[:100],
            timestamp=datetime.now(),
            cypher_count=0,
            vibe_count=0,
            final_count=len(cached_result.get("products", [])),
            winner="cached",
            battle_time=0.0,
            ml_enhanced=False,
            cache_hit=True
        )
        
        self.battle_history.append(record)
        self._update_time_stats(record)
        
        logger.debug(f"Recorded cache hit for query: {query[:30]}...")
    
    def record_timeout(self, query: str):
        """
        Record a battle timeout.
        
        Args:
            query: Search query that timed out
        """
        self.timeouts += 1
        
        record = BattleRecord(
            battle_id=f"battle_{self.total_battles}",
            query=query[:100],
            timestamp=datetime.now(),
            cypher_count=0,
            vibe_count=0,
            final_count=0,
            winner="timeout",
            battle_time=0.0,
            ml_enhanced=False,
            timeout=True
        )
        
        self.battle_history.append(record)
        logger.warning(f"Recorded timeout for query: {query[:30]}...")
    
    def record_error(self, query: str, error: str):
        """
        Record a battle error.
        
        Args:
            query: Search query that errored
            error: Error message
        """
        self.errors += 1
        
        record = BattleRecord(
            battle_id=f"battle_{self.total_battles}",
            query=query[:100],
            timestamp=datetime.now(),
            cypher_count=0,
            vibe_count=0,
            final_count=0,
            winner="error",
            battle_time=0.0,
            ml_enhanced=False,
            error=error[:200]
        )
        
        self.battle_history.append(record)
        logger.error(f"Recorded error for query: {query[:30]}... - {error[:50]}...")
    
    def _track_query_pattern(self, query: str):
        """Track query patterns for analysis."""
        # Extract key terms from query
        terms = query.lower().split()
        
        # Track common terms
        for term in terms:
            if len(term) > 3:  # Skip short words
                self.query_patterns[term] += 1
    
    def _update_ml_performance(self, with_ml: bool, winner: str, battle_time: float):
        """Update ML performance statistics."""
        key = "with_ml" if with_ml else "without_ml"
        
        self.ml_performance[key]["total"] += 1
        
        # Track wins (not errors/timeouts)
        if winner not in ["error", "timeout", "cached"]:
            self.ml_performance[key]["wins"] += 1
        
        # Update average time
        total = self.ml_performance[key]["total"]
        current_avg = self.ml_performance[key]["avg_time"]
        self.ml_performance[key]["avg_time"] = (
            (current_avg * (total - 1) + battle_time) / total
        )
    
    def _cleanup_old_stats(self, days_to_keep: int = 7):
        """
        Clean up old time-based statistics.
        
        Args:
            days_to_keep: Number of days of stats to keep
        """
        cutoff = datetime.now() - timedelta(days=days_to_keep)
        
        # Clean hourly stats
        self.hourly_stats = {
            k: v for k, v in self.hourly_stats.items()
            if datetime.strptime(k, "%Y-%m-%d %H:00") > cutoff
        }
        
        # Clean daily stats
        self.daily_stats = {
            k: v for k, v in self.daily_stats.items()
            if datetime.strptime(k, "%Y-%m-%d") > cutoff
        }
        
        logger.debug(f"Cleaned up stats older than {days_to_keep} days")

    def _update_time_stats(self, record: BattleRecord):
        """Update time-based statistics."""
        # Hourly stats
        hour_key = record.timestamp.strftime("%Y-%m-%d %H:00")
        if hour_key not in self.hourly_stats:
            self.hourly_stats[hour_key] = {
                "battles": 0,
                "cache_hits": 0,
                "errors": 0,
                "avg_time": 0.0
            }
        
        self.hourly_stats[hour_key]["battles"] += 1
        if record.cache_hit:
            self.hourly_stats[hour_key]["cache_hits"] += 1
        if record.error:
            self.hourly_stats[hour_key]["errors"] += 1
        
        # Daily stats
        day_key = record.timestamp.strftime("%Y-%m-%d")
        if day_key not in self.daily_stats:
            self.daily_stats[day_key] = {
                "battles": 0,
                "cache_hits": 0,
                "errors": 0,
                "winners": Counter()
            }
        
        self.daily_stats[day_key]["battles"] += 1
        if record.cache_hit:
            self.daily_stats[day_key]["cache_hits"] += 1
        if record.error:
            self.daily_stats[day_key]["errors"] += 1
        if record.winner:
            self.daily_stats[day_key]["winners"][record.winner] += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive metrics summary.
        
        Returns:
            Metrics summary dictionary
        """
        # Calculate cache metrics
        cache_total = self.cache_hits + self.cache_misses
        cache_hit_rate = (self.cache_hits / cache_total * 100) if cache_total > 0 else 0
        
        # Calculate battle time statistics
        if self.battle_times:
            time_stats = {
                "avg_battle_time": statistics.mean(self.battle_times),
                "median_battle_time": statistics.median(self.battle_times),
                "min_battle_time": min(self.battle_times),
                "max_battle_time": max(self.battle_times)
            }
        else:
            time_stats = {
                "avg_battle_time": 0,
                "median_battle_time": 0,
                "min_battle_time": 0,
                "max_battle_time": 0
            }
        
        # Calculate winner percentages
        total_wins = sum(self.winner_counts.values())
        if total_wins > 0:
            winner_percentages = {
                winner: (count / total_wins * 100)
                for winner, count in self.winner_counts.items()
            }
        else:
            winner_percentages = {}
        
        # Get top query patterns
        top_patterns = self.query_patterns.most_common(10)
        
        return {
            "total_battles": self.total_battles,
            "cache": {
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "hit_rate": f"{cache_hit_rate:.1f}%"
            },
            "performance": time_stats,
            "winners": {
                "counts": dict(self.winner_counts),
                "percentages": winner_percentages
            },
            "ml_enhancement": {
                "total_ml_battles": self.ml_enhanced_battles,
                "ml_percentage": (
                    self.ml_enhanced_battles / self.total_battles * 100
                    if self.total_battles > 0 else 0
                ),
                "performance_comparison": self.ml_performance
            },
            "errors": {
                "timeouts": self.timeouts,
                "errors": self.errors,
                "error_rate": (
                    (self.timeouts + self.errors) / self.total_battles * 100
                    if self.total_battles > 0 else 0
                )
            },
            "query_patterns": {
                "top_terms": top_patterns,
                "unique_terms": len(self.query_patterns)
            }
        }
    
    def get_recent_battles(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent battle records.
        
        Args:
            count: Number of recent battles to return
            
        Returns:
            List of recent battle dictionaries
        """
        recent = list(self.battle_history)[-count:]
        recent.reverse()  # Most recent first
        
        return [
            {
                "id": r.battle_id,
                "query": r.query,
                "timestamp": r.timestamp.isoformat(),
                "winner": r.winner,
                "battle_time": r.battle_time,
                "ml_enhanced": r.ml_enhanced,
                "cache_hit": r.cache_hit,
                "product_count": r.final_count
            }
            for r in recent
        ]
    
    def get_time_series(self, period: str = "hourly") -> Dict[str, Any]:
        """
        Get time series data for analysis.
        
        Args:
            period: "hourly" or "daily"
            
        Returns:
            Time series data
        """
        if period == "hourly":
            return self.hourly_stats
        elif period == "daily":
            return self.daily_stats
        else:
            return {}
    
    def reset(self):
        """Reset all metrics."""
        self.battle_history.clear()
        self.battle_times.clear()
        self.query_patterns.clear()
        self.winner_counts.clear()
        self.hourly_stats.clear()
        self.daily_stats.clear()
        
        self.total_battles = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.timeouts = 0
        self.errors = 0
        self.ml_enhanced_battles = 0
        
        self.ml_performance = {
            "with_ml": {"wins": 0, "total": 0, "avg_time": 0.0},
            "without_ml": {"wins": 0, "total": 0, "avg_time": 0.0}
        }
        
        logger.info("Battle metrics reset")
