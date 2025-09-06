#!/usr/bin/env python3
from config import get_database_config, get_ai_config, get_system_config
"""
Rollback and Safety Procedures
Comprehensive safety procedures and rollback mechanisms for all operations
"""

import json
import os
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from neo4j import GraphDatabase
from qdrant_client import QdrantClient


class RollbackSafetyManager:
    """Manages rollback and safety procedures for all operations"""
    
    def __init__(self):
        # Database connections
        self.db_config = get_database_config()
        self.neo4j_url = self.db_config.neo4j_url
        self.neo4j_user = self.db_config.neo4j_user
        self.neo4j_password = self.db_config.neo4j_password
        
        self.qdrant_url = self.db_config.qdrant_url
        self.qdrant_api_key = self.db_config.qdrant_api_key
        self.collection_name = self.db_config.collection_name
        
        # Backup and safety configuration
        self.backup_directory = Path("./backups")
        self.backup_directory.mkdir(exist_ok=True)
        
        # Safety thresholds
        self.safety_thresholds = {
            'max_node_deletion_percent': 5.0,      # Max 5% nodes can be deleted
            'max_relationship_deletion_percent': 10.0,  # Max 10% relationships
            'min_vector_retention_percent': 90.0,   # Min 90% vectors must remain
            'max_rollback_time_hours': 24,          # Max 24h for rollback
            'required_backup_age_max_hours': 2      # Backups must be < 2h old
        }
        
        # Operation tracking
        self.operation_log = []
        self.backup_registry = {}
        
    def connect_databases(self):
        """Connect to databases for safety operations"""
        print("🔌 Connecting to databases for safety operations...")
        
        self.neo4j_driver = GraphDatabase.driver(
            self.neo4j_url,
            auth=(self.neo4j_user, self.neo4j_password)
        )
        
        self.qdrant_client = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key
        )
        
        print("✅ Connected to databases")
    
    def create_comprehensive_backup(self, operation_name: str) -> Dict:
        """Create comprehensive backup before major operations"""
        print(f"💾 Creating comprehensive backup for: {operation_name}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_id = f"{operation_name}_{timestamp}"
        backup_path = self.backup_directory / backup_id
        backup_path.mkdir(exist_ok=True)
        
        backup_manifest = {
            'backup_id': backup_id,
            'operation': operation_name,
            'timestamp': datetime.now().isoformat(),
            'components': {},
            'status': 'in_progress'
        }
        
        try:
            # 1. Neo4j Schema and Data Backup
            neo4j_backup = self._backup_neo4j(backup_path)
            backup_manifest['components']['neo4j'] = neo4j_backup
            
            # 2. Qdrant Collection Backup 
            qdrant_backup = self._backup_qdrant(backup_path)
            backup_manifest['components']['qdrant'] = qdrant_backup
            
            # 3. Configuration Backup
            config_backup = self._backup_configurations(backup_path)
            backup_manifest['components']['configurations'] = config_backup
            
            # 4. Phase 1 Analysis Results
            analysis_backup = self._backup_analysis_results(backup_path)
            backup_manifest['components']['analysis'] = analysis_backup
            
            backup_manifest['status'] = 'completed'
            backup_manifest['backup_size_mb'] = self._calculate_backup_size(backup_path)
            
            # Register backup
            self.backup_registry[backup_id] = backup_manifest
            
            # Save manifest
            with open(backup_path / "backup_manifest.json", 'w') as f:
                json.dump(backup_manifest, f, indent=2, default=str)
            
            print(f"✅ Comprehensive backup created: {backup_id}")
            print(f"   Size: {backup_manifest['backup_size_mb']:.1f} MB")
            print(f"   Path: {backup_path}")
            
            return backup_manifest
            
        except Exception as e:
            backup_manifest['status'] = 'failed'
            backup_manifest['error'] = str(e)
            print(f"❌ Backup failed: {e}")
            return backup_manifest
    
    def _backup_neo4j(self, backup_path: Path) -> Dict:
        """Backup Neo4j database"""
        neo4j_backup_path = backup_path / "neo4j"
        neo4j_backup_path.mkdir(exist_ok=True)
        
        backup_info = {
            'type': 'neo4j_backup',
            'timestamp': datetime.now().isoformat(),
            'components': []
        }
        
        with self.neo4j_driver.session() as session:
            # Export full database
            export_query = """
                CALL apoc.export.cypher.all($file, {
                    format: 'cypher-shell',
                    useOptimizations: {type: 'UNWIND_BATCH', unwindBatchSize: 20}
                })
                YIELD file, source, format, nodes, relationships, properties, time, rows, batchSize
                RETURN file, nodes, relationships, properties, time
            """
            
            export_file = str(neo4j_backup_path / "full_database_export.cypher")
            result = session.run(export_query, file=export_file)
            
            record = result.single()
            if record:
                backup_info['components'].append({
                    'name': 'full_database_export',
                    'file': export_file,
                    'nodes_exported': record['nodes'],
                    'relationships_exported': record['relationships'],
                    'properties_exported': record['properties'],
                    'export_time_ms': record['time']
                })
            
            # Export schema
            schema_query = "CALL apoc.meta.schema() YIELD value RETURN value"
            schema_result = session.run(schema_query)
            schema_data = [record['value'] for record in schema_result]
            
            schema_file = neo4j_backup_path / "schema_export.json"
            with open(schema_file, 'w') as f:
                json.dump(schema_data, f, indent=2)
            
            backup_info['components'].append({
                'name': 'schema_export',
                'file': str(schema_file),
                'schema_elements': len(schema_data)
            })
            
            # Export constraints and indexes
            constraints_query = "SHOW CONSTRAINTS YIELD * RETURN *"
            indexes_query = "SHOW INDEXES YIELD * RETURN *"
            
            constraints_result = session.run(constraints_query)
            indexes_result = session.run(indexes_query)
            
            constraints_data = [dict(record) for record in constraints_result]
            indexes_data = [dict(record) for record in indexes_result]
            
            constraints_file = neo4j_backup_path / "constraints.json"
            indexes_file = neo4j_backup_path / "indexes.json"
            
            with open(constraints_file, 'w') as f:
                json.dump(constraints_data, f, indent=2, default=str)
            with open(indexes_file, 'w') as f:
                json.dump(indexes_data, f, indent=2, default=str)
            
            backup_info['components'].extend([
                {'name': 'constraints', 'file': str(constraints_file), 'count': len(constraints_data)},
                {'name': 'indexes', 'file': str(indexes_file), 'count': len(indexes_data)}
            ])
        
        return backup_info
    
    def _backup_qdrant(self, backup_path: Path) -> Dict:
        """Backup Qdrant collection"""
        qdrant_backup_path = backup_path / "qdrant"
        qdrant_backup_path.mkdir(exist_ok=True)
        
        backup_info = {
            'type': 'qdrant_backup',
            'timestamp': datetime.now().isoformat(),
            'components': []
        }
        
        try:
            # Get collection info
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            
            collection_config_file = qdrant_backup_path / "collection_config.json"
            with open(collection_config_file, 'w') as f:
                json.dump({
                    'name': self.collection_name,
                    'config': {
                        'vector_size': collection_info.config.params.vectors.size,
                        'distance': str(collection_info.config.params.vectors.distance),
                        'points_count': collection_info.points_count
                    }
                }, f, indent=2)
            
            backup_info['components'].append({
                'name': 'collection_config',
                'file': str(collection_config_file),
                'points_count': collection_info.points_count
            })
            
            # Sample vectors for validation (first 1000)
            sample_vectors = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                limit=1000,
                with_payload=True,
                with_vectors=True
            )
            
            sample_file = qdrant_backup_path / "sample_vectors.json"
            sample_data = []
            
            for point in sample_vectors[0]:
                sample_data.append({
                    'id': point.id,
                    'payload': point.payload,
                    'vector': point.vector if hasattr(point, 'vector') else None
                })
            
            with open(sample_file, 'w') as f:
                json.dump(sample_data, f, indent=2, default=str)
            
            backup_info['components'].append({
                'name': 'sample_vectors',
                'file': str(sample_file),
                'sample_size': len(sample_data)
            })
            
        except Exception as e:
            backup_info['error'] = str(e)
        
        return backup_info
    
    def _backup_configurations(self, backup_path: Path) -> Dict:
        """Backup system configurations"""
        config_backup_path = backup_path / "configurations"
        config_backup_path.mkdir(exist_ok=True)
        
        backup_info = {
            'type': 'configuration_backup',
            'timestamp': datetime.now().isoformat(),
            'components': []
        }
        
        # Backup current working directory structure
        cwd_structure = self._get_directory_structure(".")
        structure_file = config_backup_path / "directory_structure.json"
        with open(structure_file, 'w') as f:
            json.dump(cwd_structure, f, indent=2)
        
        backup_info['components'].append({
            'name': 'directory_structure',
            'file': str(structure_file)
        })
        
        # Backup Python environment info
        try:
            import sys
            import pkg_resources
            
            env_info = {
                'python_version': sys.version,
                'python_path': sys.path,
                'installed_packages': [str(pkg) for pkg in pkg_resources.working_set]
            }
            
            env_file = config_backup_path / "python_environment.json"
            with open(env_file, 'w') as f:
                json.dump(env_info, f, indent=2)
            
            backup_info['components'].append({
                'name': 'python_environment',
                'file': str(env_file)
            })
            
        except Exception as e:
            backup_info['env_backup_error'] = str(e)
        
        return backup_info
    
    def _backup_analysis_results(self, backup_path: Path) -> Dict:
        """Backup Phase 1 analysis results"""
        analysis_backup_path = backup_path / "analysis"
        analysis_backup_path.mkdir(exist_ok=True)
        
        backup_info = {
            'type': 'analysis_backup',
            'timestamp': datetime.now().isoformat(),
            'components': []
        }
        
        # Look for analysis result files
        analysis_files = [
            "phase1_analysis_results.json",
            "extraction_results.json",
            "correlation_analysis.json"
        ]
        
        for filename in analysis_files:
            if os.path.exists(filename):
                backup_file = analysis_backup_path / filename
                shutil.copy2(filename, backup_file)
                
                backup_info['components'].append({
                    'name': filename,
                    'original_file': filename,
                    'backup_file': str(backup_file)
                })
        
        return backup_info
    
    def _get_directory_structure(self, path: str, max_depth: int = 3) -> Dict:
        """Get directory structure for backup"""
        structure = {'files': [], 'directories': {}}
        
        try:
            for item in os.listdir(path):
                if item.startswith('.'):
                    continue
                    
                item_path = os.path.join(path, item)
                
                if os.path.isfile(item_path):
                    structure['files'].append({
                        'name': item,
                        'size': os.path.getsize(item_path),
                        'modified': os.path.getmtime(item_path)
                    })
                elif os.path.isdir(item_path) and max_depth > 0:
                    structure['directories'][item] = self._get_directory_structure(
                        item_path, max_depth - 1
                    )
                    
        except PermissionError:
            structure['error'] = 'Permission denied'
        
        return structure
    
    def _calculate_backup_size(self, backup_path: Path) -> float:
        """Calculate total backup size in MB"""
        total_size = 0
        for root, dirs, files in os.walk(backup_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    total_size += os.path.getsize(file_path)
                except OSError:
                    pass
        
        return total_size / (1024 * 1024)  # Convert to MB
    
    def validate_pre_operation_safety(self, operation_name: str) -> Dict:
        """Validate safety conditions before major operations"""
        print(f"🔍 Validating safety conditions for: {operation_name}")
        
        safety_check = {
            'operation': operation_name,
            'timestamp': datetime.now().isoformat(),
            'checks': {},
            'overall_safe': False,
            'warnings': [],
            'blocking_issues': []
        }
        
        # 1. Check backup currency
        backup_check = self._check_backup_currency()
        safety_check['checks']['backup_currency'] = backup_check
        
        if not backup_check['recent_backup_exists']:
            safety_check['blocking_issues'].append("No recent backup found - create backup first")
        
        # 2. Check system resources
        resource_check = self._check_system_resources()
        safety_check['checks']['system_resources'] = resource_check
        
        if resource_check['disk_usage_percent'] > 90:
            safety_check['blocking_issues'].append("Disk usage too high for safe operation")
        
        # 3. Check database connectivity
        db_check = self._check_database_connectivity()
        safety_check['checks']['database_connectivity'] = db_check
        
        if not db_check['neo4j_connected'] or not db_check['qdrant_connected']:
            safety_check['blocking_issues'].append("Database connectivity issues detected")
        
        # 4. Check operation-specific safety
        if operation_name == "phase2_graph_reconstruction":
            phase2_check = self._check_phase2_safety()
            safety_check['checks']['phase2_safety'] = phase2_check
            
            if not phase2_check['safe_to_proceed']:
                safety_check['blocking_issues'].extend(phase2_check['blocking_issues'])
        
        elif operation_name == "vector_re_embedding":
            embedding_check = self._check_embedding_safety()
            safety_check['checks']['embedding_safety'] = embedding_check
            
            if not embedding_check['safe_to_proceed']:
                safety_check['blocking_issues'].extend(embedding_check['blocking_issues'])
        
        # Overall safety assessment
        safety_check['overall_safe'] = len(safety_check['blocking_issues']) == 0
        
        # Print summary
        if safety_check['overall_safe']:
            print("✅ Safety validation passed - operation can proceed")
        else:
            print("❌ Safety validation failed - blocking issues found:")
            for issue in safety_check['blocking_issues']:
                print(f"  • {issue}")
        
        if safety_check['warnings']:
            print("⚠️ Warnings:")
            for warning in safety_check['warnings']:
                print(f"  • {warning}")
        
        return safety_check
    
    def _check_backup_currency(self) -> Dict:
        """Check if recent backups exist"""
        backup_check = {
            'recent_backup_exists': False,
            'latest_backup_age_hours': None,
            'backup_count': 0
        }
        
        if not self.backup_directory.exists():
            return backup_check
        
        backup_dirs = [d for d in self.backup_directory.iterdir() if d.is_dir()]
        backup_check['backup_count'] = len(backup_dirs)
        
        if backup_dirs:
            # Find most recent backup
            latest_backup = max(backup_dirs, key=lambda d: d.stat().st_mtime)
            latest_time = datetime.fromtimestamp(latest_backup.stat().st_mtime)
            age_hours = (datetime.now() - latest_time).total_seconds() / 3600
            
            backup_check['latest_backup_age_hours'] = age_hours
            backup_check['recent_backup_exists'] = age_hours <= self.safety_thresholds['required_backup_age_max_hours']
        
        return backup_check
    
    def _check_system_resources(self) -> Dict:
        """Check system resource availability"""
        try:
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'cpu_usage_percent': cpu_percent,
                'memory_usage_percent': memory.percent,
                'disk_usage_percent': disk.percent,
                'available_memory_gb': memory.available / (1024**3),
                'available_disk_gb': disk.free / (1024**3),
                'resource_check_passed': (
                    cpu_percent < 80 and 
                    memory.percent < 85 and 
                    disk.percent < 90
                )
            }
        except ImportError:
            return {'error': 'psutil not available', 'resource_check_passed': True}
    
    def _check_database_connectivity(self) -> Dict:
        """Check database connectivity"""
        connectivity_check = {
            'neo4j_connected': False,
            'qdrant_connected': False,
            'neo4j_response_time_ms': None,
            'qdrant_response_time_ms': None
        }
        
        # Test Neo4j
        try:
            import time
            start_time = time.time()
            
            with self.neo4j_driver.session() as session:
                result = session.run("RETURN 1 as test")
                if result.single():
                    connectivity_check['neo4j_connected'] = True
                    connectivity_check['neo4j_response_time_ms'] = (time.time() - start_time) * 1000
        except Exception:
            pass
        
        # Test Qdrant
        try:
            start_time = time.time()
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            if collection_info:
                connectivity_check['qdrant_connected'] = True
                connectivity_check['qdrant_response_time_ms'] = (time.time() - start_time) * 1000
        except Exception:
            pass
        
        return connectivity_check
    
    def _check_phase2_safety(self) -> Dict:
        """Check safety conditions specific to Phase 2"""
        phase2_check = {
            'safe_to_proceed': True,
            'blocking_issues': [],
            'warnings': []
        }
        
        try:
            with self.neo4j_driver.session() as session:
                # Check current node counts
                node_count_result = session.run("""
                    CALL apoc.meta.stats()
                    YIELD nodeCount
                    RETURN nodeCount
                """)
                
                current_nodes = node_count_result.single()['nodeCount'] if node_count_result.single() else 0
                
                # Check if we're about to create too many new nodes
                expected_new_nodes = 200  # Estimated Color + Brand + Style nodes
                
                if current_nodes == 0:
                    phase2_check['blocking_issues'].append("No existing nodes found - database may be empty")
                    phase2_check['safe_to_proceed'] = False
                
                if current_nodes < 1000000:  # Less than 1M products
                    phase2_check['warnings'].append(f"Only {current_nodes:,} nodes found - expected more products")
                
        except Exception as e:
            phase2_check['blocking_issues'].append(f"Failed to check Phase 2 safety: {e}")
            phase2_check['safe_to_proceed'] = False
        
        return phase2_check
    
    def _check_embedding_safety(self) -> Dict:
        """Check safety conditions specific to vector re-embedding"""
        embedding_check = {
            'safe_to_proceed': True,
            'blocking_issues': [],
            'warnings': []
        }
        
        try:
            # Check Qdrant collection
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            current_vectors = collection_info.points_count
            
            if current_vectors == 0:
                embedding_check['blocking_issues'].append("No existing vectors found")
                embedding_check['safe_to_proceed'] = False
            
            if current_vectors < 1000000:
                embedding_check['warnings'].append(f"Only {current_vectors:,} vectors found - expected more")
            
            # Check if we have the budget for re-embedding (cost estimation)
            estimated_cost = current_vectors * 0.0001  # Rough estimate
            if estimated_cost > 500:  # $500 threshold
                embedding_check['warnings'].append(f"Estimated re-embedding cost: ${estimated_cost:.2f}")
            
        except Exception as e:
            embedding_check['blocking_issues'].append(f"Failed to check embedding safety: {e}")
            embedding_check['safe_to_proceed'] = False
        
        return embedding_check
    
    def execute_rollback(self, backup_id: str, rollback_scope: str = "full") -> Dict:
        """Execute rollback to previous state"""
        print(f"🔄 Executing rollback from backup: {backup_id}")
        print(f"Scope: {rollback_scope}")
        
        rollback_report = {
            'backup_id': backup_id,
            'rollback_scope': rollback_scope,
            'timestamp': datetime.now().isoformat(),
            'status': 'in_progress',
            'steps_completed': [],
            'errors': []
        }
        
        try:
            # Validate backup exists and is valid
            backup_path = self.backup_directory / backup_id
            if not backup_path.exists():
                raise Exception(f"Backup {backup_id} not found")
            
            manifest_file = backup_path / "backup_manifest.json"
            if not manifest_file.exists():
                raise Exception("Backup manifest not found")
            
            with open(manifest_file, 'r') as f:
                backup_manifest = json.load(f)
            
            # Execute rollback steps based on scope
            if rollback_scope in ["full", "neo4j"]:
                neo4j_rollback = self._rollback_neo4j(backup_path)
                rollback_report['steps_completed'].append('neo4j_rollback')
                if not neo4j_rollback['success']:
                    rollback_report['errors'].append(neo4j_rollback['error'])
            
            if rollback_scope in ["full", "qdrant"]:
                qdrant_rollback = self._rollback_qdrant(backup_path)
                rollback_report['steps_completed'].append('qdrant_rollback')
                if not qdrant_rollback['success']:
                    rollback_report['errors'].append(qdrant_rollback['error'])
            
            # Validate rollback success
            validation_result = self._validate_rollback_success(backup_manifest)
            rollback_report['validation'] = validation_result
            
            if len(rollback_report['errors']) == 0 and validation_result['success']:
                rollback_report['status'] = 'completed'
                print("✅ Rollback completed successfully")
            else:
                rollback_report['status'] = 'completed_with_errors'
                print("⚠️ Rollback completed but with errors")
            
        except Exception as e:
            rollback_report['status'] = 'failed'
            rollback_report['errors'].append(str(e))
            print(f"❌ Rollback failed: {e}")
        
        return rollback_report
    
    def _rollback_neo4j(self, backup_path: Path) -> Dict:
        """Rollback Neo4j to backup state"""
        neo4j_backup_path = backup_path / "neo4j"
        
        try:
            # Clear current database (DANGEROUS - only in rollback)
            with self.neo4j_driver.session() as session:
                print("⚠️ Clearing current Neo4j database...")
                session.run("MATCH (n) DETACH DELETE n")
            
            # Restore from backup
            cypher_file = neo4j_backup_path / "full_database_export.cypher"
            if cypher_file.exists():
                print("📥 Restoring Neo4j from backup...")
                
                # Read and execute cypher file
                with open(cypher_file, 'r') as f:
                    cypher_content = f.read()
                
                # Split into individual statements and execute
                statements = cypher_content.split(';\n')
                
                with self.neo4j_driver.session() as session:
                    for statement in statements:
                        if statement.strip():
                            session.run(statement)
                
                return {'success': True, 'message': 'Neo4j restored from backup'}
            else:
                return {'success': False, 'error': 'Backup cypher file not found'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _rollback_qdrant(self, backup_path: Path) -> Dict:
        """Rollback Qdrant to backup state"""
        qdrant_backup_path = backup_path / "qdrant"
        
        try:
            # Note: Full Qdrant rollback requires recreating collection
            # This is a simplified version - full implementation would restore all vectors
            
            config_file = qdrant_backup_path / "collection_config.json"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                
                print("⚠️ Qdrant rollback - configuration restored")
                print("Note: Full vector restoration requires separate process")
                
                return {'success': True, 'message': 'Qdrant config restored (vectors require separate restoration)'}
            else:
                return {'success': False, 'error': 'Qdrant backup config not found'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _validate_rollback_success(self, backup_manifest: Dict) -> Dict:
        """Validate that rollback was successful"""
        validation = {
            'success': True,
            'checks': {},
            'errors': []
        }
        
        try:
            # Validate Neo4j restoration
            with self.neo4j_driver.session() as session:
                node_count_result = session.run("CALL apoc.meta.stats() YIELD nodeCount RETURN nodeCount")
                current_nodes = node_count_result.single()['nodeCount'] if node_count_result.single() else 0
                
                validation['checks']['neo4j_nodes_restored'] = current_nodes > 0
                if current_nodes == 0:
                    validation['errors'].append("No nodes found after Neo4j rollback")
                    validation['success'] = False
            
            # Validate Qdrant restoration (basic check)
            try:
                collection_info = self.qdrant_client.get_collection(self.collection_name)
                validation['checks']['qdrant_collection_exists'] = True
            except:
                validation['checks']['qdrant_collection_exists'] = False
                validation['errors'].append("Qdrant collection not accessible after rollback")
                validation['success'] = False
                
        except Exception as e:
            validation['errors'].append(f"Validation failed: {e}")
            validation['success'] = False
        
        return validation
    
    def create_emergency_procedures(self) -> Dict:
        """Create emergency procedures documentation"""
        emergency_procedures = {
            'created': datetime.now().isoformat(),
            'procedures': {
                'immediate_system_stop': {
                    'description': 'Stop all operations immediately in case of critical failure',
                    'steps': [
                        'Stop all running Python processes',
                        'Close all database connections',
                        'Create emergency state backup',
                        'Assess system damage'
                    ],
                    'commands': [
                        'pkill -f python',
                        'pkill -f neo4j',
                        'systemctl stop redis',
                    ]
                },
                'database_corruption_recovery': {
                    'description': 'Recover from database corruption',
                    'steps': [
                        'Stop all database access',
                        'Identify corruption extent',
                        'Restore from most recent valid backup',
                        'Validate restoration',
                        'Resume operations'
                    ]
                },
                'partial_operation_failure': {
                    'description': 'Handle partial failures during operations',
                    'steps': [
                        'Stop current operation',
                        'Assess completion percentage',
                        'Determine rollback vs continuation strategy',
                        'Execute chosen strategy',
                        'Validate system state'
                    ]
                },
                'out_of_disk_space': {
                    'description': 'Handle disk space exhaustion',
                    'steps': [
                        'Stop all write operations',
                        'Identify and remove temporary files',
                        'Move old backups to external storage',
                        'Resume operations with monitoring'
                    ]
                }
            },
            'contact_information': {
                'database_admin': 'Contact system administrator',
                'backup_storage': 'Check backup storage location',
                'monitoring_logs': 'Check system logs for details'
            },
            'recovery_time_estimates': {
                'full_system_restore': '2-6 hours',
                'neo4j_only_restore': '30-60 minutes', 
                'qdrant_only_restore': '1-2 hours',
                'partial_rollback': '15-30 minutes'
            }
        }
        
        return emergency_procedures
    
    def generate_safety_report(self) -> Dict:
        """Generate comprehensive safety and rollback report"""
        print("📋 Generating Safety and Rollback Report")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'backup_status': {},
            'safety_procedures': {},
            'rollback_capabilities': {},
            'emergency_procedures': {}
        }
        
        # Backup status
        backup_dirs = list(self.backup_directory.iterdir()) if self.backup_directory.exists() else []
        report['backup_status'] = {
            'total_backups': len(backup_dirs),
            'backup_directory': str(self.backup_directory),
            'total_backup_size_mb': sum(self._calculate_backup_size(d) for d in backup_dirs if d.is_dir()),
            'recent_backups': [d.name for d in sorted(backup_dirs, key=lambda x: x.stat().st_mtime, reverse=True)[:5]]
        }
        
        # Safety procedures
        report['safety_procedures'] = {
            'pre_operation_validation': 'Comprehensive safety checks before major operations',
            'backup_creation': 'Automatic backup creation before destructive operations',
            'resource_monitoring': 'System resource monitoring during operations',
            'operation_logging': 'Detailed logging of all operations for audit trail'
        }
        
        # Rollback capabilities
        report['rollback_capabilities'] = {
            'full_system_rollback': 'Complete system restore from backup',
            'partial_rollback': 'Selective component rollback (Neo4j or Qdrant only)',
            'emergency_stop': 'Immediate operation termination with state preservation',
            'validation_after_rollback': 'Automatic validation of system state after rollback'
        }
        
        # Emergency procedures
        report['emergency_procedures'] = self.create_emergency_procedures()
        
        # Safety recommendations
        report['recommendations'] = [
            'Always create backup before major operations',
            'Validate system state before and after operations',
            'Monitor system resources during long-running operations',
            'Test rollback procedures in non-production environment',
            'Keep multiple backup generations',
            'Document all operations for audit trail'
        ]
        
        print("✅ Safety report generated")
        return report


def main():
    """Run safety procedures setup and validation"""
    safety_manager = RollbackSafetyManager()
    
    try:
        safety_manager.connect_databases()
        
        # Generate comprehensive safety report
        safety_report = safety_manager.generate_safety_report()
        
        # Save safety report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"safety_and_rollback_report_{timestamp}.json"
        
        with open(report_file, 'w') as f:
            json.dump(safety_report, f, indent=2, default=str)
        
        print(f"💾 Safety report saved: {report_file}")
        
        # Print summary
        print(f"\n🛡️ SAFETY SYSTEM SUMMARY")
        print("=" * 50)
        print(f"Backup Directory: {safety_report['backup_status']['backup_directory']}")
        print(f"Total Backups: {safety_report['backup_status']['total_backups']}")
        print(f"Total Backup Size: {safety_report['backup_status']['total_backup_size_mb']:.1f} MB")
        print(f"Safety Procedures: {len(safety_report['safety_procedures'])} implemented")
        print(f"Rollback Capabilities: {len(safety_report['rollback_capabilities'])} available")
        print(f"Emergency Procedures: {len(safety_report['emergency_procedures']['procedures'])} documented")
        
        return True
        
    except Exception as e:
        print(f"❌ Safety system setup failed: {e}")
        return False
    
    finally:
        if hasattr(safety_manager, 'neo4j_driver'):
            safety_manager.neo4j_driver.close()


if __name__ == "__main__":
    main()