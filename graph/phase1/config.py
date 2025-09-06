#!/usr/bin/env python3
"""
Secure Configuration Management
Handles all credentials and configuration securely using environment variables
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class DatabaseConfig:
    """Database configuration"""
    neo4j_url: str
    neo4j_user: str
    neo4j_password: str
    qdrant_url: str
    qdrant_api_key: str
    collection_name: str


@dataclass
class AIConfig:
    """AI service configuration"""
    openai_api_key: str
    model_name: str = "text-embedding-3-small"
    max_retries: int = 3
    timeout_seconds: int = 30


@dataclass
class SystemConfig:
    """System configuration"""
    working_directory: str
    logs_directory: str
    backup_directory: str
    max_batch_size: int = 1000
    max_concurrent_connections: int = 10


class ConfigManager:
    """Secure configuration manager"""
    
    def __init__(self):
        self._database_config = None
        self._ai_config = None
        self._system_config = None
    
    def get_database_config(self) -> DatabaseConfig:
        """Get database configuration from environment variables"""
        if self._database_config is None:
            self._database_config = DatabaseConfig(
                neo4j_url=self._get_env_var("NEO4J_URL", "bolt://localhost:7687"),
                neo4j_user=self._get_env_var("NEO4J_USER", "neo4j"),
                neo4j_password=self._get_env_var("NEO4J_PASSWORD", required=True),
                qdrant_url=self._get_env_var("QDRANT_URL", required=True),
                qdrant_api_key=self._get_env_var("QDRANT_API_KEY", required=True),
                collection_name=self._get_env_var("QDRANT_COLLECTION", "fashion_products")
            )
        return self._database_config
    
    def get_ai_config(self) -> AIConfig:
        """Get AI service configuration from environment variables"""
        if self._ai_config is None:
            self._ai_config = AIConfig(
                openai_api_key=self._get_env_var("OPENAI_API_KEY", required=True),
                model_name=self._get_env_var("OPENAI_MODEL", "text-embedding-3-small"),
                max_retries=int(self._get_env_var("OPENAI_MAX_RETRIES", "3")),
                timeout_seconds=int(self._get_env_var("OPENAI_TIMEOUT", "30"))
            )
        return self._ai_config
    
    def get_system_config(self) -> SystemConfig:
        """Get system configuration"""
        if self._system_config is None:
            self._system_config = SystemConfig(
                working_directory=self._get_env_var("WORKING_DIR", "/home/leo/AIStylist/graph/phase1"),
                logs_directory=self._get_env_var("LOGS_DIR", "./logs"),
                backup_directory=self._get_env_var("BACKUP_DIR", "./backups"),
                max_batch_size=int(self._get_env_var("MAX_BATCH_SIZE", "1000")),
                max_concurrent_connections=int(self._get_env_var("MAX_CONNECTIONS", "10"))
            )
        return self._system_config
    
    def _get_env_var(self, var_name: str, default: Optional[str] = None, required: bool = False) -> str:
        """Securely get environment variable"""
        value = os.environ.get(var_name, default)
        
        if required and not value:
            raise ValueError(
                f"Required environment variable {var_name} is not set. "
                f"Please set this variable before running the application."
            )
        
        return value
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate all configurations"""
        validation_results = {
            'database_config_valid': False,
            'ai_config_valid': False,
            'system_config_valid': False,
            'errors': []
        }
        
        try:
            db_config = self.get_database_config()
            validation_results['database_config_valid'] = True
        except ValueError as e:
            validation_results['errors'].append(f"Database config error: {e}")
        
        try:
            ai_config = self.get_ai_config()
            validation_results['ai_config_valid'] = True
        except ValueError as e:
            validation_results['errors'].append(f"AI config error: {e}")
        
        try:
            system_config = self.get_system_config()
            validation_results['system_config_valid'] = True
        except ValueError as e:
            validation_results['errors'].append(f"System config error: {e}")
        
        return validation_results


# Global configuration instance
config_manager = ConfigManager()


def get_database_config() -> DatabaseConfig:
    """Get database configuration"""
    return config_manager.get_database_config()


def get_ai_config() -> AIConfig:
    """Get AI configuration"""
    return config_manager.get_ai_config()


def get_system_config() -> SystemConfig:
    """Get system configuration"""
    return config_manager.get_system_config()


def validate_all_config() -> Dict[str, Any]:
    """Validate all configurations"""
    return config_manager.validate_config()


if __name__ == "__main__":
    """Test configuration loading"""
    print("🔧 Testing Configuration Loading")
    print("=" * 40)
    
    validation = validate_all_config()
    
    print(f"Database Config Valid: {validation['database_config_valid']}")
    print(f"AI Config Valid: {validation['ai_config_valid']}")
    print(f"System Config Valid: {validation['system_config_valid']}")
    
    if validation['errors']:
        print("\n❌ Configuration Errors:")
        for error in validation['errors']:
            print(f"  • {error}")
        
        print("\n📝 Required Environment Variables:")
        print("  • NEO4J_PASSWORD")
        print("  • QDRANT_URL") 
        print("  • QDRANT_API_KEY")
        print("  • OPENAI_API_KEY")
        
        print("\n💡 Optional Environment Variables:")
        print("  • NEO4J_URL (default: bolt://localhost:7687)")
        print("  • NEO4J_USER (default: neo4j)")
        print("  • QDRANT_COLLECTION (default: fashion_products)")
        print("  • OPENAI_MODEL (default: text-embedding-3-small)")
        print("  • MAX_BATCH_SIZE (default: 1000)")
        print("  • MAX_CONNECTIONS (default: 10)")
    else:
        print("✅ All configurations valid!")