"""
Centralized Configuration Management for AI Fashion System
Consolidates all settings from environment variables and provides validation
Based on patterns from config_validator.py and scattered config across the codebase
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("config.settings")

# =============================================================================
# CONFIGURATION ENUMS
# =============================================================================

class Environment(Enum):
    """Deployment environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"

class LogLevel(Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class CacheStrategy(Enum):
    """Cache eviction strategies."""
    LRU = "lru"
    LFU = "lfu"
    FIFO = "fifo"

# =============================================================================
# CONFIGURATION DATACLASSES
# =============================================================================

@dataclass
class Neo4jConfig:
    """Neo4j database configuration."""
    url: str
    username: str
    password: str
    database: str = "neo4j"
    max_connection_pool_size: int = 50
    connection_timeout: int = 30
    query_timeout: float = 30.0
    max_query_timeout: float = 60.0
    batch_size: int = 100
    enable_connection_pooling: bool = True

@dataclass
class QdrantConfig:
    """Qdrant vector database configuration."""
    url: Optional[str] = None
    api_key: Optional[str] = None
    collection_name: str = "fashion_products"
    host: str = "localhost"
    port: int = 6333
    use_grpc: bool = True
    timeout: float = 30.0
    enable_connection_pooling: bool = True
    
    @property
    def is_remote(self) -> bool:
        """Check if using remote Qdrant."""
        return bool(self.url)

@dataclass
class RedisConfig:
    """Redis cache configuration for production scaling."""
    url: Optional[str] = None
    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = None
    db: int = 0
    max_connections: int = 100
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    retry_on_timeout: bool = True
    health_check_interval: int = 30
    decode_responses: bool = True
    
    @property
    def is_remote(self) -> bool:
        """Check if using remote Redis."""
        return bool(self.url)

@dataclass
class OpenAIConfig:
    """OpenAI API configuration."""
    api_key: str
    model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    temperature: float = 0.7
    max_tokens: int = 4000
    request_timeout: int = 60

@dataclass
class CamelConfig:
    """CAMEL-AI configuration."""
    version_required: str = "0.2.70"
    model_type: str = "gpt-4o-mini"
    model_platform: str = "openai"
    agent_temperature: float = 0.7
    agent_max_tokens: int = 4000
    memory_token_limit: int = 2048
    enable_vector_memory: bool = True
    enable_chat_history: bool = True

@dataclass
class BattleConfig:
    """Battle system configuration."""
    enable_cache: bool = True
    enable_optimization: bool = True
    enable_metrics: bool = True
    cache_ttl: int = 300
    cache_max_size: int = 1000
    cache_strategy: CacheStrategy = CacheStrategy.LRU
    cache_cleanup_interval: int = 60
    max_concurrent_battles: int = 5
    default_timeout: float = 120.0  # Increased for large Neo4j datasets
    prefetch_multiplier: int = 2
    quality_threshold: float = 0.2  # Lower threshold to allow more products through
    enable_auto_recovery: bool = True
    recovery_attempts: int = 3
    recovery_interval: int = 60

@dataclass
class ConnectionConfig:
    """Connection management configuration."""
    retry_delay: int = 5
    max_retries: int = 3
    health_check_interval: int = 60
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 300
    connection_pool_size: int = 10

@dataclass
class MemoryConfig:
    """Memory optimization configuration."""
    optimization_interval: int = 3600
    max_memory_records: int = 1000
    cleanup_threshold: float = 0.8
    enable_optimization: bool = True

@dataclass
class SecurityConfig:
    """Security configuration."""
    enable_pii_protection: bool = True
    allowed_image_domains: List[str] = field(default_factory=lambda: [
        'cdn.shopify.com',
        's3.amazonaws.com',
        'storage.googleapis.com',
        'images.unsplash.com',
        'cloudinary.com'
    ])
    max_image_size: int = 10 * 1024 * 1024  # 10MB
    max_image_dimension: int = 4096
    min_image_dimension: int = 32
    request_timeout: int = 10
    max_redirects: int = 2

@dataclass
class FeatureFlags:
    """Feature toggles."""
    enable_luxury_mode: bool = True
    enable_wardrobe_tracking: bool = True
    vip_client_features: bool = True
    enable_ml_intelligence: bool = True
    enable_behavioral_analysis: bool = True
    enable_visual_intelligence: bool = True
    enable_semantic_search: bool = True

@dataclass
class PerformanceConfig:
    """Performance tuning configuration."""
    batch_processing_size: int = 4
    gpu_memory_threshold: float = 0.8
    cpu_thread_pool_size: int = 4
    async_io_pool_size: int = 10
    
# =============================================================================
# MAIN SETTINGS CLASS
# =============================================================================

class Settings:
    """
    Centralized settings management for the AI Fashion System.
    Loads configuration from environment variables with validation.
    """
    
    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize settings from environment.
        
        Args:
            env_file: Optional path to .env file
        """
        # Load environment variables
        if env_file:
            self._load_env_file(env_file)
        
        # Determine environment
        env_str = os.getenv("ENVIRONMENT", "development").lower()
        try:
            self.environment = Environment(env_str)
        except ValueError:
            logger.warning(f"Unknown environment: {env_str}, defaulting to development")
            self.environment = Environment.DEVELOPMENT
        
        # Set log level
        log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
        try:
            self.log_level = LogLevel(log_level_str)
        except ValueError:
            self.log_level = LogLevel.INFO
        
        # Load all configurations
        self.neo4j = self._load_neo4j_config()
        self.qdrant = self._load_qdrant_config()
        self.redis = self._load_redis_config()
        self.openai = self._load_openai_config()
        self.camel = self._load_camel_config()
        self.battle = self._load_battle_config()
        self.connection = self._load_connection_config()
        self.memory = self._load_memory_config()
        self.security = self._load_security_config()
        self.features = self._load_feature_flags()
        self.performance = self._load_performance_config()
        
        # Validate configuration
        self._validate()
        
        logger.info(f"Settings loaded for environment: {self.environment.value}")
    
    def _load_env_file(self, env_file: str):
        """Load environment variables from file."""
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
            logger.info(f"Loaded environment from: {env_file}")
        except ImportError:
            logger.warning("python-dotenv not installed, skipping .env file")
        except Exception as e:
            logger.error(f"Failed to load .env file: {e}")
    
    def _load_neo4j_config(self) -> Neo4jConfig:
        """Load Neo4j configuration."""
        return Neo4jConfig(
            url=os.getenv("NEO4J_URL", os.getenv("NEO4J_URI", "bolt://localhost:7687")),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
            database=os.getenv("NEO4J_DATABASE", "neo4j"),
            max_connection_pool_size=int(os.getenv("NEO4J_MAX_POOL_SIZE", "100")),
            connection_timeout=int(os.getenv("NEO4J_CONNECTION_TIMEOUT", "30")),
            query_timeout=float(os.getenv("NEO4J_QUERY_TIMEOUT", "30.0")),
            max_query_timeout=float(os.getenv("MAX_QUERY_TIMEOUT", "60.0")),
            batch_size=int(os.getenv("BATCH_SIZE", "100")),
            enable_connection_pooling=os.getenv("ENABLE_CONNECTION_POOLING", "true").lower() == "true"
        )
    
    def _load_qdrant_config(self) -> QdrantConfig:
        """Load Qdrant configuration."""
        return QdrantConfig(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY"),
            collection_name=os.getenv("QDRANT_COLLECTION_NAME", "fashion_products"),
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
            use_grpc=os.getenv("QDRANT_USE_GRPC", "true").lower() == "true",
            timeout=float(os.getenv("QDRANT_TIMEOUT", "30.0")),
            enable_connection_pooling=os.getenv("QDRANT_ENABLE_POOLING", "true").lower() == "true"
        )
    
    def _load_redis_config(self) -> RedisConfig:
        """Load Redis configuration."""
        return RedisConfig(
            url=os.getenv("REDIS_URL"),
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD"),
            db=int(os.getenv("REDIS_DB", "0")),
            max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "100")),
            socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT", "5.0")),
            socket_connect_timeout=float(os.getenv("REDIS_CONNECT_TIMEOUT", "5.0")),
            retry_on_timeout=os.getenv("REDIS_RETRY_ON_TIMEOUT", "true").lower() == "true",
            health_check_interval=int(os.getenv("REDIS_HEALTH_CHECK_INTERVAL", "30")),
            decode_responses=os.getenv("REDIS_DECODE_RESPONSES", "true").lower() == "true"
        )
    
    def _load_openai_config(self) -> OpenAIConfig:
        """Load OpenAI configuration."""
        return OpenAIConfig(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "4000")),
            request_timeout=int(os.getenv("OPENAI_REQUEST_TIMEOUT", "60"))
        )
    
    def _load_camel_config(self) -> CamelConfig:
        """Load CAMEL configuration."""
        return CamelConfig(
            version_required=os.getenv("CAMEL_VERSION_REQUIRED", "0.2.70"),
            model_type=os.getenv("CAMEL_MODEL_TYPE", "gpt-4o-mini"),
            model_platform=os.getenv("CAMEL_MODEL_PLATFORM", "openai"),
            agent_temperature=float(os.getenv("AGENT_TEMPERATURE", "0.7")),
            agent_max_tokens=int(os.getenv("AGENT_MAX_TOKENS", "4000")),
            memory_token_limit=int(os.getenv("MEMORY_TOKEN_LIMIT", "2048")),
            enable_vector_memory=os.getenv("ENABLE_VECTOR_MEMORY", "true").lower() == "true",
            enable_chat_history=os.getenv("ENABLE_CHAT_HISTORY", "true").lower() == "true"
        )
    
    def _load_battle_config(self) -> BattleConfig:
        """Load battle system configuration."""
        cache_strategy_str = os.getenv("CACHE_STRATEGY", "lru").lower()
        try:
            cache_strategy = CacheStrategy(cache_strategy_str)
        except ValueError:
            cache_strategy = CacheStrategy.LRU
        
        return BattleConfig(
            enable_cache=os.getenv("ENABLE_CACHE", "true").lower() == "true",
            enable_optimization=os.getenv("ENABLE_OPTIMIZATION", "true").lower() == "true",
            enable_metrics=os.getenv("ENABLE_METRICS", "true").lower() == "true",
            cache_ttl=int(os.getenv("BATTLE_CACHE_TTL", "300")),
            cache_max_size=int(os.getenv("BATTLE_CACHE_MAX_SIZE", "1000")),
            cache_strategy=cache_strategy,
            cache_cleanup_interval=int(os.getenv("CACHE_CLEANUP_INTERVAL", "60")),
            max_concurrent_battles=int(os.getenv("MAX_CONCURRENT_BATTLES", "5")),
            default_timeout=float(os.getenv("BATTLE_TIMEOUT", "120.0")),
            prefetch_multiplier=int(os.getenv("PREFETCH_MULTIPLIER", "2")),
            quality_threshold=float(os.getenv("QUALITY_THRESHOLD", "0.2")),
            enable_auto_recovery=os.getenv("ENABLE_AUTO_RECOVERY", "true").lower() == "true",
            recovery_attempts=int(os.getenv("RECOVERY_ATTEMPTS", "3")),
            recovery_interval=int(os.getenv("RECOVERY_INTERVAL", "60"))
        )
    
    def _load_connection_config(self) -> ConnectionConfig:
        """Load connection management configuration."""
        return ConnectionConfig(
            retry_delay=int(os.getenv("CONNECTION_RETRY_DELAY", "5")),
            max_retries=int(os.getenv("CONNECTION_MAX_RETRIES", "3")),
            health_check_interval=int(os.getenv("CONNECTION_HEALTH_CHECK_INTERVAL", "60")),
            circuit_breaker_threshold=int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "5")),
            circuit_breaker_timeout=int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "300")),
            connection_pool_size=int(os.getenv("CONNECTION_POOL_SIZE", "10"))
        )
    
    def _load_memory_config(self) -> MemoryConfig:
        """Load memory configuration."""
        return MemoryConfig(
            optimization_interval=int(os.getenv("MEMORY_OPTIMIZATION_INTERVAL", "3600")),
            max_memory_records=int(os.getenv("MAX_MEMORY_RECORDS", "1000")),
            cleanup_threshold=float(os.getenv("MEMORY_CLEANUP_THRESHOLD", "0.8")),
            enable_optimization=os.getenv("ENABLE_MEMORY_OPTIMIZATION", "true").lower() == "true"
        )
    
    def _load_security_config(self) -> SecurityConfig:
        """Load security configuration."""
        # Parse allowed domains
        domains_str = os.getenv("ALLOWED_IMAGE_DOMAINS", "")
        if domains_str:
            additional_domains = [d.strip() for d in domains_str.split(",")]
        else:
            additional_domains = []
        
        config = SecurityConfig(
            enable_pii_protection=os.getenv("ENABLE_PII_PROTECTION", "true").lower() == "true",
            max_image_size=int(os.getenv("MAX_IMAGE_SIZE", str(10 * 1024 * 1024))),
            max_image_dimension=int(os.getenv("MAX_IMAGE_DIMENSION", "4096")),
            min_image_dimension=int(os.getenv("MIN_IMAGE_DIMENSION", "32")),
            request_timeout=int(os.getenv("IMAGE_REQUEST_TIMEOUT", "10")),
            max_redirects=int(os.getenv("MAX_IMAGE_REDIRECTS", "2"))
        )
        
        # Add additional domains
        if additional_domains:
            config.allowed_image_domains.extend(additional_domains)
        
        return config
    
    def _load_feature_flags(self) -> FeatureFlags:
        """Load feature flags."""
        return FeatureFlags(
            enable_luxury_mode=os.getenv("ENABLE_LUXURY_MODE", "true").lower() == "true",
            enable_wardrobe_tracking=os.getenv("ENABLE_WARDROBE_TRACKING", "true").lower() == "true",
            vip_client_features=os.getenv("VIP_CLIENT_FEATURES", "true").lower() == "true",
            enable_ml_intelligence=os.getenv("ENABLE_ML_INTELLIGENCE", "true").lower() == "true",
            enable_behavioral_analysis=os.getenv("ENABLE_BEHAVIORAL_ANALYSIS", "true").lower() == "true",
            enable_visual_intelligence=os.getenv("ENABLE_VISUAL_INTELLIGENCE", "true").lower() == "true",
            enable_semantic_search=os.getenv("ENABLE_SEMANTIC_SEARCH", "true").lower() == "true"
        )
    
    def _load_performance_config(self) -> PerformanceConfig:
        """Load performance configuration."""
        return PerformanceConfig(
            batch_processing_size=int(os.getenv("BATCH_PROCESSING_SIZE", "4")),
            gpu_memory_threshold=float(os.getenv("GPU_MEMORY_THRESHOLD", "0.8")),
            cpu_thread_pool_size=int(os.getenv("CPU_THREAD_POOL_SIZE", "4")),
            async_io_pool_size=int(os.getenv("ASYNC_IO_POOL_SIZE", "10"))
        )
    
    def _validate(self):
        """Validate configuration."""
        errors = []
        
        # Validate required fields
        if not self.neo4j.url:
            errors.append("NEO4J_URL is required")
        if not self.neo4j.password:
            errors.append("NEO4J_PASSWORD is required")
        if not self.openai.api_key:
            errors.append("OPENAI_API_KEY is required")
        
        # Validate ranges
        if not 0 <= self.openai.temperature <= 1:
            errors.append("OPENAI_TEMPERATURE must be between 0 and 1")
        if self.battle.cache_ttl <= 0:
            errors.append("BATTLE_CACHE_TTL must be positive")
        if self.connection.max_retries <= 0:
            errors.append("CONNECTION_MAX_RETRIES must be positive")
        
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(errors)
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info("Configuration validation successful")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary."""
        return {
            "environment": self.environment.value,
            "log_level": self.log_level.value,
            "neo4j": self.neo4j.__dict__,
            "qdrant": self.qdrant.__dict__,
            "redis": {k: v for k, v in self.redis.__dict__.items() if k != "password"},
            "openai": {k: v for k, v in self.openai.__dict__.items() if k != "api_key"},
            "camel": self.camel.__dict__,
            "battle": {**self.battle.__dict__, "cache_strategy": self.battle.cache_strategy.value},
            "connection": self.connection.__dict__,
            "memory": self.memory.__dict__,
            "security": self.security.__dict__,
            "features": self.features.__dict__,
            "performance": self.performance.__dict__
        }
    
    def get_summary(self) -> str:
        """Get configuration summary."""
        lines = [
            "=" * 60,
            "AI FASHION SYSTEM CONFIGURATION",
            "=" * 60,
            f"Environment: {self.environment.value}",
            f"Log Level: {self.log_level.value}",
            "",
            "DATABASES:",
            f"  Neo4j: {self.neo4j.url}",
            f"  Qdrant: {'Remote' if self.qdrant.is_remote else 'Local'}",
            "",
            "FEATURES:",
            f"  Luxury Mode: {self.features.enable_luxury_mode}",
            f"  Wardrobe Tracking: {self.features.enable_wardrobe_tracking}",
            f"  ML Intelligence: {self.features.enable_ml_intelligence}",
            "",
            "BATTLE SYSTEM:",
            f"  Cache: {self.battle.enable_cache} (TTL: {self.battle.cache_ttl}s)",
            f"  Optimization: {self.battle.enable_optimization}",
            f"  Auto-Recovery: {self.battle.enable_auto_recovery}",
            "=" * 60
        ]
        return "\n".join(lines)
    
    @classmethod
    def generate_env_template(cls, filepath: str = ".env.example"):
        """Generate template .env file."""
        template = '''# AI Fashion System Environment Configuration
# Generated by config/settings.py

# === ENVIRONMENT ===
ENVIRONMENT=development  # development, staging, production, testing
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# === DATABASES (REQUIRED) ===
# Neo4j
NEO4J_URL=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-secure-password
NEO4J_DATABASE=neo4j

# Qdrant (optional - leave empty for local)
QDRANT_URL=
QDRANT_API_KEY=
QDRANT_COLLECTION_NAME=fashion_products

# === AI SERVICES (REQUIRED) ===
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0.7

# === BATTLE SYSTEM ===
ENABLE_CACHE=true
BATTLE_CACHE_TTL=300
BATTLE_CACHE_MAX_SIZE=1000
CACHE_STRATEGY=lru  # lru, lfu, fifo
MAX_CONCURRENT_BATTLES=5
ENABLE_AUTO_RECOVERY=true

# === CONNECTION MANAGEMENT ===
CONNECTION_RETRY_DELAY=5
CONNECTION_MAX_RETRIES=3
CONNECTION_HEALTH_CHECK_INTERVAL=60
CIRCUIT_BREAKER_THRESHOLD=5

# === MEMORY OPTIMIZATION ===
MEMORY_OPTIMIZATION_INTERVAL=3600
MAX_MEMORY_RECORDS=1000
ENABLE_MEMORY_OPTIMIZATION=true

# === SECURITY ===
ENABLE_PII_PROTECTION=true
MAX_IMAGE_SIZE=10485760  # 10MB
ALLOWED_IMAGE_DOMAINS=  # Comma-separated additional domains

# === FEATURE FLAGS ===
ENABLE_LUXURY_MODE=true
ENABLE_WARDROBE_TRACKING=true
VIP_CLIENT_FEATURES=true
ENABLE_ML_INTELLIGENCE=true
ENABLE_BEHAVIORAL_ANALYSIS=true
ENABLE_VISUAL_INTELLIGENCE=true

# === PERFORMANCE ===
BATCH_PROCESSING_SIZE=4
GPU_MEMORY_THRESHOLD=0.8
CPU_THREAD_POOL_SIZE=4
'''
        
        try:
            with open(filepath, 'w') as f:
                f.write(template)
            logger.info(f"Generated environment template at {filepath}")
        except Exception as e:
            logger.error(f"Failed to generate template: {e}")
            raise

# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

# Global settings instance
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """
    Get the global settings instance.
    Creates it if it doesn't exist.
    """
    global _settings
    if _settings is None:
        # Try to load .env file
        env_file = None
        for possible_env in [".env", "../.env", "../../.env"]:
            if Path(possible_env).exists():
                env_file = possible_env
                break
        
        _settings = Settings(env_file=env_file)
        
        # Log configuration summary
        logger.info(_settings.get_summary())
    
    return _settings

def reload_settings(env_file: Optional[str] = None) -> Settings:
    """
    Force reload settings from environment.
    Useful for testing or configuration changes.
    """
    global _settings
    _settings = Settings(env_file=env_file)
    return _settings

# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Main classes
    'Settings',
    'Environment',
    'LogLevel',
    'CacheStrategy',
    
    # Config dataclasses
    'Neo4jConfig',
    'QdrantConfig',
    'RedisConfig',
    'OpenAIConfig',
    'CamelConfig',
    'BattleConfig',
    'ConnectionConfig',
    'MemoryConfig',
    'SecurityConfig',
    'FeatureFlags',
    'PerformanceConfig',
    
    # Functions
    'get_settings',
    'reload_settings'
]

# Initialize settings on import
if __name__ != "__main__":
    try:
        get_settings()
    except Exception as e:
        logger.error(f"Failed to initialize settings: {e}")
