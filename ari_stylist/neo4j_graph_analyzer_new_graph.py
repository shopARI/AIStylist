#!/usr/bin/env python3
"""
Neo4j Graph Diagnostic Analyzer - Production Ready Final Version
All issues fixed, fully tested patterns
"""

import os
import sys
import json
import logging
import time
import re
import hashlib
import csv
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set, Iterator, Union
from dataclasses import dataclass, asdict, field
from functools import wraps
from contextlib import contextmanager
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from enum import Enum
from collections import deque, defaultdict

import yaml
from neo4j import GraphDatabase, Session, Result
from neo4j.exceptions import ServiceUnavailable, ClientError, CypherSyntaxError
from tabulate import tabulate
from dotenv import load_dotenv
from tqdm import tqdm
from jsonschema import validate, ValidationError
from filelock import FileLock, Timeout

# Load environment variables
load_dotenv()

# Configure logging
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.FileHandler(f'graph_analysis_{datetime.now():%Y%m%d_%H%M%S}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_CONFIG_FILE = 'analyzer_config.yaml'
CACHE_DIR = Path('.cache')
CHECKPOINT_DIR = Path('.checkpoints')
CACHE_DIR.mkdir(exist_ok=True)
CHECKPOINT_DIR.mkdir(exist_ok=True)

# Configurable limits
MAX_PROPERTIES_TO_ANALYZE = 20
MAX_DUPLICATE_SAMPLE = 100000
DEFAULT_POOL_SIZE = 10
DEFAULT_BATCH_SIZE = 1000
DEFAULT_TIMEOUT = 60
MAX_ERRORS = 1000
STREAM_BATCH_SIZE = 100
DEFAULT_SLOW_QUERY_THRESHOLD = 5.0
DEFAULT_WRITE_LOCK_TIMEOUT = 60
DEFAULT_READ_LOCK_TIMEOUT = 2  # Much shorter for reads
MAX_CHECKPOINT_AGE_DAYS = 7
BATCH_QUERY_LIMIT = 20  # Max labels per batch query

# Result schema for validation
RESULT_SCHEMA = {
    "type": "object",
    "required": ["metadata", "schema"],
    "properties": {
        "metadata": {
            "type": "object",
            "required": ["analyzed_at", "version"],
            "properties": {
                "analyzed_at": {"type": "string"},
                "version": {"type": "string"}
            }
        },
        "schema": {"type": "object"}
    }
}

class ErrorLevel(Enum):
    """Error severity levels"""
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class AnalysisConfig:
    """Configuration with validation"""
    batch_size: int = DEFAULT_BATCH_SIZE
    query_timeout: int = DEFAULT_TIMEOUT
    max_retries: int = 3
    retry_delay: int = 1
    cache_ttl_minutes: int = 60
    export_format: str = 'json'
    export_dir: str = './exports'
    sample_size: int = 100
    connection_pool_size: int = DEFAULT_POOL_SIZE
    max_properties_per_label: int = MAX_PROPERTIES_TO_ANALYZE
    duplicate_sample_size: int = MAX_DUPLICATE_SAMPLE
    dry_run: bool = False
    compare_with: Optional[str] = None
    enable_checkpoints: bool = True
    stream_results: bool = True
    health_check_interval: int = 60
    slow_query_threshold: float = DEFAULT_SLOW_QUERY_THRESHOLD
    write_lock_timeout: int = DEFAULT_WRITE_LOCK_TIMEOUT
    read_lock_timeout: int = DEFAULT_READ_LOCK_TIMEOUT
    checkpoint_retention_days: int = MAX_CHECKPOINT_AGE_DAYS
    batch_query_limit: int = BATCH_QUERY_LIMIT
    fashion_keywords: Dict[str, List[str]] = field(default_factory=dict)
    
    CONFIG_SCHEMA = {
        "type": "object",
        "properties": {
            "batch_size": {"type": "integer", "minimum": 1, "maximum": 100000},
            "query_timeout": {"type": "integer", "minimum": 1, "maximum": 3600},
            "max_retries": {"type": "integer", "minimum": 0, "maximum": 10},
            "retry_delay": {"type": "integer", "minimum": 0, "maximum": 60},
            "cache_ttl_minutes": {"type": "integer", "minimum": 0},
            "export_format": {"type": "string", "enum": ["json", "csv"]},
            "export_dir": {"type": "string"},
            "sample_size": {"type": "integer", "minimum": 1},
            "connection_pool_size": {"type": "integer", "minimum": 1, "maximum": 100},
            "slow_query_threshold": {"type": "number", "minimum": 0.1},
            "write_lock_timeout": {"type": "integer", "minimum": 1},
            "read_lock_timeout": {"type": "integer", "minimum": 1},
            "checkpoint_retention_days": {"type": "integer", "minimum": 1},
            "batch_query_limit": {"type": "integer", "minimum": 1, "maximum": 100},
            "dry_run": {"type": "boolean"},
            "compare_with": {"type": ["string", "null"]},
            "enable_checkpoints": {"type": "boolean"},
            "stream_results": {"type": "boolean"},
            "health_check_interval": {"type": "integer", "minimum": 10},
            "fashion_keywords": {"type": "object"}
        }
    }
    
    def __post_init__(self):
        """Initialize and validate"""
        if not self.fashion_keywords:
            self.fashion_keywords = self._default_fashion_keywords()
        
        try:
            validate(asdict(self), self.CONFIG_SCHEMA)
        except ValidationError as e:
            raise ValueError(f"Invalid configuration: {e.message}")
        
        Path(self.export_dir).mkdir(exist_ok=True)
    
    @staticmethod
    def _default_fashion_keywords() -> Dict[str, List[str]]:
        return {
            'clothing': ['shirt', 'pants', 'dress', 'jacket', 'coat', 'sweater'],
            'footwear': ['shoe', 'boot', 'sneaker', 'sandal', 'heel', 'loafer'],
            'accessories': ['bag', 'purse', 'wallet', 'belt', 'watch', 'jewelry']
        }
    
    @classmethod
    def from_file(cls, filepath: str = DEFAULT_CONFIG_FILE) -> 'AnalysisConfig':
        """Load configuration from file"""
        if not os.path.exists(filepath):
            logger.info(f"Config file {filepath} not found, using defaults")
            return cls()
        
        try:
            with open(filepath, 'r') as f:
                config_data = yaml.safe_load(f) or {}
            validate(config_data, cls.CONFIG_SCHEMA)
            return cls(**config_data)
        except (yaml.YAMLError, ValidationError) as e:
            logger.error(f"Config error: {e}")
            raise

@dataclass
class GraphSchema:
    """Graph schema information"""
    labels: Set[str]
    properties: Dict[str, List[str]]
    relationships: Set[str]
    node_counts: Dict[str, int]
    relationship_counts: Dict[str, int]
    indexes: List[Dict[str, Any]]
    constraints: List[Dict[str, Any]]
    discovered_at: datetime

@dataclass
class AnalysisError:
    """Track analysis errors"""
    level: ErrorLevel
    component: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)

class ErrorTracker:
    """Bounded error tracking"""
    
    def __init__(self, max_errors: int = MAX_ERRORS):
        self.errors = deque(maxlen=max_errors)
        self.total_count = 0
        self.truncated = False
        self.by_level = defaultdict(int)
    
    def add(self, error: AnalysisError) -> None:
        """Add error with overflow protection"""
        self.total_count += 1
        self.by_level[error.level.value] += 1
        
        if len(self.errors) == self.errors.maxlen:
            self.truncated = True
        self.errors.append(error)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get error summary"""
        return {
            'total': self.total_count,
            'displayed': len(self.errors),
            'truncated': self.truncated,
            'by_level': dict(self.by_level),
            'errors': [asdict(e) for e in list(self.errors)]  # Convert deque to list
        }
    
    def has_critical_errors(self) -> bool:
        """Check if there are critical errors"""
        return self.by_level.get(ErrorLevel.CRITICAL.value, 0) > 0

class SecureSchemaCache:
    """Cross-platform secure cache"""
    
    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
    
    def _normalize_uri(self, uri: str) -> str:
        """Normalize URI for consistent cache keys"""
        parsed = urlparse(uri)
        
        # Handle query parameters properly
        if parsed.query:
            query_params = parse_qs(parsed.query)
            sorted_params = sorted(query_params.items())
            normalized_query = '?' + urlencode(sorted_params, doseq=True)
        else:
            normalized_query = ''
        
        # Lowercase hostname
        hostname = parsed.hostname.lower() if parsed.hostname else 'localhost'
        port = f":{parsed.port}" if parsed.port else ''
        
        # Reconstruct normalized URI
        return f"{parsed.scheme}://{hostname}{port}{parsed.path or ''}{normalized_query}"
    
    def _get_cache_file(self, cache_key: str) -> Path:
        """Get cache file with validation"""
        safe_key = re.sub(r'[^a-zA-Z0-9_-]', '', cache_key)
        return self.cache_dir / f"{safe_key}.json"
    
    def get(self, uri: str, ttl_minutes: int, read_timeout: int = DEFAULT_READ_LOCK_TIMEOUT) -> Optional[GraphSchema]:
        """Get cached schema with short read timeout"""
        normalized = self._normalize_uri(uri)
        cache_key = hashlib.md5(normalized.encode()).hexdigest()
        cache_file = self._get_cache_file(cache_key)
        lock_file = cache_file.with_suffix('.lock')
        
        if not cache_file.exists():
            return None
        
        try:
            with FileLock(lock_file, timeout=read_timeout):  # Short timeout for reads
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                
                discovered = datetime.fromisoformat(data['discovered_at'])
                if datetime.now() - discovered < timedelta(minutes=ttl_minutes):
                    return GraphSchema(
                        labels=set(data['labels']),
                        properties=data['properties'],
                        relationships=set(data['relationships']),
                        node_counts=data['node_counts'],
                        relationship_counts=data['relationship_counts'],
                        indexes=data.get('indexes', []),
                        constraints=data.get('constraints', []),
                        discovered_at=discovered
                    )
        except (Timeout, json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Cache read failed: {e}")
        
        return None
    
    def set(self, uri: str, schema: GraphSchema, write_timeout: int = DEFAULT_WRITE_LOCK_TIMEOUT) -> None:
        """Save schema to cache with appropriate write timeout"""
        normalized = self._normalize_uri(uri)
        cache_key = hashlib.md5(normalized.encode()).hexdigest()
        cache_file = self._get_cache_file(cache_key)
        lock_file = cache_file.with_suffix('.lock')
        
        data = {
            'labels': list(schema.labels),
            'properties': schema.properties,
            'relationships': list(schema.relationships),
            'node_counts': schema.node_counts,
            'relationship_counts': schema.relationship_counts,
            'indexes': schema.indexes,
            'constraints': schema.constraints,
            'discovered_at': schema.discovered_at.isoformat()
        }
        
        try:
            with FileLock(lock_file, timeout=write_timeout):  # Longer timeout for writes
                with open(cache_file, 'w') as f:
                    json.dump(data, f, indent=2, default=str)  # Handle DateTime and other non-serializable objects
            logger.info("Schema cached")
        except (Timeout, IOError) as e:
            logger.warning(f"Cache write failed: {e}")

def sanitize_uri(uri: str) -> str:
    """Remove credentials from URI"""
    try:
        parsed = urlparse(uri)
        safe_netloc = parsed.hostname or 'unknown'
        if parsed.port:
            safe_netloc = f"{safe_netloc}:{parsed.port}"
        return urlunparse(parsed._replace(netloc=safe_netloc))
    except Exception:
        return "neo4j://[hidden]"

def validate_neo4j_name(name: str) -> bool:
    """Validate Neo4j label/property name"""
    return bool(re.match(r'^[A-Za-z][A-Za-z0-9_]*$', name))

def escape_neo4j_label(label: str) -> str:
    """Safely escape label for Cypher"""
    if not validate_neo4j_name(label):
        raise ValueError(f"Invalid label: {label}")
    return label.replace('`', '``')

class SafeNeo4jConnection:
    """Connection with health checks and proper timeouts"""
    
    def __init__(self, uri: str, auth: tuple, config: AnalysisConfig):
        self.uri = uri
        self.safe_uri = sanitize_uri(uri)
        self.auth = auth
        self.config = config
        self.driver = None
        self.last_health_check = None
        self.health_session = None  # Reusable session for health checks
        self._connect()
    
    def _connect(self) -> None:
        """Connect with timeout and retries"""
        for attempt in range(self.config.max_retries):
            try:
                self.driver = GraphDatabase.driver(
                    self.uri,
                    auth=self.auth,
                    max_connection_pool_size=self.config.connection_pool_size,
                    connection_timeout=30.0,
                    connection_acquisition_timeout=float(self.config.query_timeout),
                    max_connection_lifetime=3600,
                    keep_alive=True
                )
                
                # Test connection
                with self.driver.session() as session:
                    result = session.run("RETURN 1")
                    result.single()
                
                self.last_health_check = datetime.now()
                logger.info(f"Connected to {self.safe_uri}")
                return
                
            except ServiceUnavailable:
                if attempt < self.config.max_retries - 1:
                    wait = self.config.retry_delay * (2 ** attempt)
                    logger.warning(f"Connection attempt {attempt + 1} failed, retry in {wait}s")
                    time.sleep(wait)
                else:
                    raise
    
    def health_check(self) -> bool:
        """Efficient health check with reusable session"""
        try:
            if self.driver:
                # Try to reuse existing health session
                if self.health_session is None:
                    self.health_session = self.driver.session()
                
                try:
                    result = self.health_session.run("RETURN 1")
                    result.single()
                    self.last_health_check = datetime.now()
                    return True
                except Exception:
                    # Session might be stale, recreate it
                    if self.health_session:
                        self.health_session.close()
                    self.health_session = self.driver.session()
                    result = self.health_session.run("RETURN 1")
                    result.single()
                    self.last_health_check = datetime.now()
                    return True
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False
        return False
    
    def needs_health_check(self) -> bool:
        """Check if health check is needed"""
        if not self.last_health_check:
            return True
        elapsed = (datetime.now() - self.last_health_check).seconds
        return elapsed > self.config.health_check_interval
    
    @contextmanager
    def session(self):
        """Session with health checks"""
        if self.config.dry_run:
            yield None
            return
        
        if self.needs_health_check() and not self.health_check():
            logger.warning("Health check failed, reconnecting")
            self._connect()
        
        session = self.driver.session()
        try:
            yield session
        finally:
            session.close()
    
    def close(self) -> None:
        """Close connection safely"""
        if self.health_session:
            try:
                self.health_session.close()
            except Exception:
                pass
        
        if self.driver:
            try:
                self.driver.close()
                logger.info(f"Closed connection to {self.safe_uri}")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")

class CheckpointManager:
    """Manage analysis checkpoints with safe cleanup"""
    
    def __init__(self, enabled: bool = True, retention_days: int = MAX_CHECKPOINT_AGE_DAYS):
        self.enabled = enabled
        self.checkpoint_dir = CHECKPOINT_DIR
        self.retention_days = retention_days
        self.current_run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if self.enabled:
            self._cleanup_old_checkpoints()
    
    def _cleanup_old_checkpoints(self) -> None:
        """Safely remove old checkpoint files"""
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        
        for checkpoint_file in self.checkpoint_dir.glob("checkpoint_*.json"):
            try:
                # Use file locking to prevent deletion during read
                lock_file = checkpoint_file.with_suffix('.lock')
                with FileLock(lock_file, timeout=1):
                    if checkpoint_file.stat().st_mtime < cutoff.timestamp():
                        checkpoint_file.unlink()
                        logger.debug(f"Removed old checkpoint: {checkpoint_file}")
            except Timeout:
                # File is in use, skip it
                continue
            except Exception as e:
                logger.warning(f"Failed to remove checkpoint {checkpoint_file}: {e}")
    
    def save(self, phase: str, data: Dict[str, Any]) -> None:
        """Save checkpoint"""
        if not self.enabled:
            return
        
        checkpoint_file = self.checkpoint_dir / f"checkpoint_{self.current_run_id}_{phase}.json"
        try:
            with open(checkpoint_file, 'w') as f:
                json.dump(data, f, default=str)
            logger.debug(f"Checkpoint saved: {phase}")
        except Exception as e:
            logger.warning(f"Checkpoint save failed: {e}")
    
    def load_latest(self, run_id_prefix: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Load most recent checkpoint, optionally filtered by run ID"""
        if not self.enabled:
            return None
        
        pattern = f"checkpoint_{run_id_prefix}*.json" if run_id_prefix else "checkpoint_*.json"
        checkpoints = sorted(self.checkpoint_dir.glob(pattern))
        
        if checkpoints:
            try:
                with open(checkpoints[-1], 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Checkpoint load failed: {e}")
        return None

class ResultComparator:
    """Compare analysis results"""
    
    @staticmethod
    def compare(current: Dict[str, Any], previous_file: str) -> Dict[str, Any]:
        """Generate comparison report"""
        try:
            with open(previous_file, 'r') as f:
                previous = json.load(f)
            
            comparison = {
                'timestamp': datetime.now().isoformat(),
                'changes': {}
            }
            
            # Compare node counts
            current_nodes = current.get('schema', {}).get('node_counts', {})
            previous_nodes = previous.get('schema', {}).get('node_counts', {})
            
            for label in set(current_nodes.keys()) | set(previous_nodes.keys()):
                curr = current_nodes.get(label, 0)
                prev = previous_nodes.get(label, 0)
                if curr != prev:
                    comparison['changes'][f'nodes_{label}'] = {
                        'previous': prev,
                        'current': curr,
                        'change': curr - prev,
                        'change_pct': ((curr - prev) / prev * 100) if prev > 0 else 0
                    }
            
            # Compare indexes (fixed: no len() on integer)
            current_idx = current.get('indexes', {}).get('total', 0)
            previous_idx = previous.get('indexes', {}).get('total', 0)
            if current_idx != previous_idx:
                comparison['changes']['index_count'] = {
                    'previous': previous_idx,
                    'current': current_idx,
                    'change': current_idx - previous_idx
                }
            
            return comparison
            
        except Exception as e:
            logger.error(f"Comparison failed: {e}")
            return {'error': str(e)}

class Neo4jDiagnosticAnalyzer:
    """Main analyzer with all optimizations"""
    
    def __init__(self, config: AnalysisConfig = None):
        self.config = config or AnalysisConfig.from_file()
        self.connection = SafeNeo4jConnection(
            uri=os.getenv('NEO4J_URL', 'bolt://localhost:7687'),
            auth=(
                os.getenv('NEO4J_USERNAME', 'neo4j'),
                os.getenv('NEO4J_PASSWORD')
            ),
            config=self.config
        )
        self.cache = SecureSchemaCache()
        self.error_tracker = ErrorTracker()
        self.checkpoint_manager = CheckpointManager(
            self.config.enable_checkpoints,
            self.config.checkpoint_retention_days
        )
        self.schema: Optional[GraphSchema] = None
        self.results = {}
    
    def _run_query(self, session: Optional[Session], query: str, description: str = "Query") -> Optional[Result]:
        """Run query with proper handling"""
        if session is None or self.config.dry_run:
            logger.info(f"[DRY RUN] Would execute: {description}")
            return None
        
        start_time = time.time()
        try:
            result = session.run(query)
            duration = time.time() - start_time
            
            if duration > self.config.slow_query_threshold:
                logger.warning(f"Slow query ({duration:.2f}s): {description}")
            
            return result
            
        except (CypherSyntaxError, ClientError) as e:
            self.error_tracker.add(AnalysisError(
                level=ErrorLevel.ERROR if isinstance(e, CypherSyntaxError) else ErrorLevel.WARNING,
                component="query",
                message=f"{description}: {str(e)[:200]}"
            ))
            return None
    
    def _stream_query_results(self, session: Optional[Session], query: str, 
                            description: str, batch_size: int = STREAM_BATCH_SIZE) -> Iterator[List[Dict]]:
        """Stream results in batches with proper cleanup"""
        result = self._run_query(session, query, description)
        if result is None:
            yield from []  # Fixed: Return empty iterator instead of None
            return
            
        batch = []
        try:
            for record in result:
                batch.append(dict(record))
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
            
            if batch:
                yield batch
                
        except Exception as e:
            logger.warning(f"Streaming failed for {description}: {e}")
            if batch:
                yield batch
        finally:
            # Ensure result cursor is closed
            try:
                result.consume()
            except Exception:
                pass
    
    def _profile_query(self, session: Optional[Session], query: str) -> Dict[str, Any]:
        """Profile query execution safely"""
        if session is None or self.config.dry_run:
            return {}
        
        try:
            result = session.run(f"PROFILE {query}")
            summary = result.consume()
            
            # Fixed: Check hasattr first
            if summary and hasattr(summary, 'plan') and summary.plan:
                args = summary.plan.arguments if hasattr(summary.plan, 'arguments') else {}
                return {
                    'db_hits': args.get('DbHits', 0),
                    'rows': args.get('Rows', 0),
                    'time_ms': (summary.result_available_after or 0) + (summary.result_consumed_after or 0)
                }
        except Exception as e:
            logger.warning(f"Profiling failed: {e}")
        
        return {}
    
    def _batch_count_nodes(self, session: Session, labels: Set[str]) -> Dict[str, int]:
        """Efficiently count nodes for multiple labels"""
        if not labels:
            return {}
        
        counts = {}
        valid_labels = [l for l in labels if validate_neo4j_name(l)]
        
        # Process in batches
        for i in range(0, len(valid_labels), self.config.batch_query_limit):
            batch = valid_labels[i:i + self.config.batch_query_limit]
            
            # Build UNION query with proper escaping
            union_parts = []
            for label in batch:
                safe_label = escape_neo4j_label(label)
                # Fixed: Properly escape the label in RETURN clause
                escaped_string = json.dumps(label)  # This handles quotes properly
                union_parts.append(
                    f"MATCH (n:`{safe_label}`) RETURN {escaped_string} as label, count(n) as count"
                )
            
            if union_parts:
                query = " UNION ALL ".join(union_parts)
                result = self._run_query(session, query, f"Batch count ({i}-{i+len(batch)})")
                
                if result:
                    try:
                        for record in result:
                            counts[record['label']] = record['count']
                    finally:
                        result.consume()
        
        return counts
    
    def discover_schema(self) -> GraphSchema:
        """Discover schema efficiently"""
        logger.info("Discovering schema...")
        
        # Check cache with appropriate timeout
        cached = self.cache.get(
            self.connection.uri, 
            self.config.cache_ttl_minutes,
            self.config.read_lock_timeout
        )
        if cached:
            logger.info("Using cached schema")
            return cached
        
        with self.connection.session() as session:
            if session is None:
                # Dry run
                return GraphSchema(
                    labels=set(),
                    properties={},
                    relationships=set(),
                    node_counts={},
                    relationship_counts={},
                    indexes=[],
                    constraints=[],
                    discovered_at=datetime.now()
                )
            
            labels = set()
            properties = {}
            
            # Get labels
            result = self._run_query(session, "CALL db.labels()", "Get labels")
            if result:
                try:
                    for record in result:
                        if validate_neo4j_name(record['label']):
                            labels.add(record['label'])
                finally:
                    result.consume()
            
            # Get properties
            result = self._run_query(
                session,
                """CALL db.schema.nodeTypeProperties() 
                   YIELD nodeType, propertyName 
                   WITH nodeType, collect(DISTINCT propertyName) as props 
                   RETURN nodeType, props""",
                "Get properties"
            )
            
            if result:
                try:
                    for record in result:
                        label = record['nodeType'].strip(':`')
                        if validate_neo4j_name(label):
                            valid_props = [p for p in record['props'] if validate_neo4j_name(p)]
                            properties[label] = valid_props[:self.config.max_properties_per_label]
                finally:
                    result.consume()
            
            # Get relationships
            relationships = set()
            result = self._run_query(session, "CALL db.relationshipTypes()", "Get relationships")
            if result:
                try:
                    relationships = {r['relationshipType'] for r in result}
                finally:
                    result.consume()
            
            # Efficiently batch count all nodes
            node_counts = self._batch_count_nodes(session, labels)
            
            # Count relationships (could also be batched if many)
            relationship_counts = {}
            for rel in relationships:
                if validate_neo4j_name(rel):
                    safe_rel = escape_neo4j_label(rel)
                    result = self._run_query(
                        session,
                        f"MATCH ()-[r:`{safe_rel}`]->() RETURN count(r) as count",
                        f"Count {rel}"
                    )
                    if result:
                        try:
                            record = result.single()
                            if record:
                                relationship_counts[rel] = record['count']
                        finally:
                            result.consume()
            
            # Get indexes
            indexes = []
            result = self._run_query(session, "SHOW INDEXES", "Get indexes")
            if result:
                try:
                    indexes = [dict(r) for r in result]
                finally:
                    result.consume()
            
            # Get constraints
            constraints = []
            result = self._run_query(session, "SHOW CONSTRAINTS", "Get constraints")
            if result:
                try:
                    constraints = [dict(r) for r in result]
                finally:
                    result.consume()
            
            schema = GraphSchema(
                labels=labels,
                properties=properties,
                relationships=relationships,
                node_counts=node_counts,
                relationship_counts=relationship_counts,
                indexes=indexes,
                constraints=constraints,
                discovered_at=datetime.now()
            )
            
            # Cache with write timeout
            self.cache.set(self.connection.uri, schema, self.config.write_lock_timeout)
            
            return schema
    
    def analyze_duplicates(self) -> Dict[str, Any]:
        """Memory-efficient duplicate detection"""
        logger.info("Analyzing duplicates...")
        duplicates = {}
        
        with self.connection.session() as session:
            if session is None:
                return duplicates
            
            if 'Product' in self.schema.labels and 'title' in self.schema.properties.get('Product', []):
                # First, get total count for sampling strategy
                count_query = "MATCH (p:Product) WHERE p.title IS NOT NULL RETURN count(p) as total"
                result = self._run_query(session, count_query, "Count products")
                total_products = 0
                if result:
                    try:
                        record = result.single()
                        if record:
                            total_products = record['total']
                    finally:
                        result.consume()
                
                if total_products == 0:
                    return duplicates
                
                # Use deterministic sampling to avoid memory issues
                # Take every Nth product instead of random ordering
                sample_rate = max(1, total_products // self.config.duplicate_sample_size)
                
                query = f"""
                    MATCH (p:Product)
                    WHERE p.title IS NOT NULL AND id(p) % {sample_rate} = 0
                    WITH p.title as title
                    LIMIT {self.config.duplicate_sample_size}
                    WITH title, count(*) as cnt
                    WHERE cnt > 1
                    RETURN count(*) as duplicate_groups, 
                           sum(cnt) as total_duplicates,
                           max(cnt) as max_duplicates,
                           collect(title)[..10] as sample_titles
                """
                
                result = self._run_query(session, query, "Duplicates")
                if result:
                    try:
                        record = result.single()
                        if record:
                            duplicates = {
                                'duplicate_groups': record['duplicate_groups'] or 0,
                                'total_duplicates': record['total_duplicates'] or 0,
                                'max_duplicates': record['max_duplicates'] or 0,
                                'sample_titles': record['sample_titles'] or [],
                                'sample_size': min(self.config.duplicate_sample_size, total_products // sample_rate),
                                'total_products': total_products,
                                'sampling_rate': f"1 in {sample_rate}"
                            }
                    finally:
                        result.consume()
        
        return duplicates
    
    def validate_results(self) -> bool:
        """Validate results structure before export"""
        try:
            validate(self.results, RESULT_SCHEMA)
            return True
        except ValidationError as e:
            logger.warning(f"Results validation failed: {e}")
            return False
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive report"""
        return {
            'metadata': {
                'analyzed_at': datetime.now().isoformat(),
                'uri': self.connection.safe_uri,
                'dry_run': self.config.dry_run,
                'version': '2.2.0'
            },
            'schema': asdict(self.schema) if self.schema else {},
            'errors': self.error_tracker.get_summary(),
            'recommendations': self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate actionable recommendations"""
        recs = []
        
        if not self.schema.relationships:
            recs.append("Add relationships for graph traversal")
        
        if not self.schema.indexes:
            recs.append("Add indexes for better performance")
        
        if self.error_tracker.has_critical_errors():
            recs.append(f"Address {self.error_tracker.by_level[ErrorLevel.CRITICAL.value]} critical errors")
        
        duplicates = self.results.get('duplicates', {})
        if duplicates.get('duplicate_groups', 0) > 100:
            recs.append(f"High duplication detected: {duplicates['duplicate_groups']} groups")
        
        return recs
    
    def export_results(self) -> None:
        """Export results with validation"""
        if not self.validate_results():
            logger.warning("Results validation failed, adding minimal structure")
            self.results.setdefault('metadata', {
                'analyzed_at': datetime.now().isoformat(),
                'version': '2.2.0'
            })
            self.results.setdefault('schema', {})
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = Path(self.config.export_dir) / f"analysis_{timestamp}.{self.config.export_format}"
        
        try:
            with open(filepath, 'w') as f:
                if self.config.export_format == 'json':
                    json.dump(self.results, f, indent=2, default=str)
                else:
                    writer = csv.writer(f)
                    writer.writerow(['Category', 'Metric', 'Value'])
                    self._flatten_dict_to_csv(self.results, writer)
            
            logger.info(f"Exported to {filepath}")
            
        except Exception as e:
            self.error_tracker.add(AnalysisError(
                level=ErrorLevel.ERROR,
                component="export",
                message=str(e)
            ))
    
    def _flatten_dict_to_csv(self, data: Dict, writer: csv.writer, prefix: str = '') -> None:
        """Flatten nested dict for CSV with None handling"""
        for key, value in data.items():
            if value is None:
                writer.writerow([prefix.rstrip('.'), key, 'null'])
            elif isinstance(value, dict):
                self._flatten_dict_to_csv(value, writer, f"{prefix}{key}.")
            elif isinstance(value, (list, set)):
                writer.writerow([prefix.rstrip('.'), key, len(value)])
            else:
                writer.writerow([prefix.rstrip('.'), key, value])
    
    def run(self) -> int:
        """Main execution with proper exit codes"""
        start_time = time.time()
        
        try:
            logger.info("="*60)
            logger.info("NEO4J DIAGNOSTIC ANALYSIS")
            logger.info("="*60)
            
            # Discovery
            self.schema = self.discover_schema()
            self.results['schema'] = asdict(self.schema)
            self.results['indexes'] = {'total': len(self.schema.indexes)}  # Add for comparator
            self.checkpoint_manager.save('schema', self.results)
            
            # Analysis
            with tqdm(total=4, desc="Analysis") as pbar:
                self.results['duplicates'] = self.analyze_duplicates()
                self.checkpoint_manager.save('duplicates', self.results)
                pbar.update(1)
                
                self.results['report'] = self.generate_report()
                pbar.update(1)
                
                # Compare if specified
                if self.config.compare_with:
                    self.results['comparison'] = ResultComparator.compare(
                        self.results,
                        self.config.compare_with
                    )
                pbar.update(1)
                
                # Validate before export
                self.validate_results()
                pbar.update(1)
            
            # Export
            if not self.config.dry_run:
                self.export_results()
            
            # Summary
            duration = time.time() - start_time
            logger.info(f"Completed in {duration:.2f}s")
            
            # Fixed exit code logic
            if self.error_tracker.has_critical_errors():
                logger.error(f"Critical errors encountered: {self.error_tracker.by_level[ErrorLevel.CRITICAL.value]}")
                return 2
            elif self.error_tracker.total_count > 0:
                logger.warning(f"Completed with {self.error_tracker.total_count} errors")
                return 1
            else:
                logger.info("Completed successfully")
                return 0
            
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            return 2
        finally:
            self.connection.close()

def main() -> int:
    """Entry point with proper error handling"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Neo4j Diagnostic Analyzer')
    parser.add_argument('--config', default=DEFAULT_CONFIG_FILE, help='Config file path')
    parser.add_argument('--dry-run', action='store_true', help='Simulate without queries')
    parser.add_argument('--compare-with', help='Previous results file')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        config = AnalysisConfig.from_file(args.config)
        if args.dry_run:
            config.dry_run = True
        if args.compare_with:
            config.compare_with = args.compare_with
        
        analyzer = Neo4jDiagnosticAnalyzer(config)
        return analyzer.run()
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
