#!/usr/bin/env python3
from config import get_database_config, get_ai_config, get_system_config
"""
API Integration Preparation Scripts
Prepares the system for API integration after graph and vector fixes
"""

import json
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from neo4j import GraphDatabase
from qdrant_client import QdrantClient


@dataclass
class APIEndpoint:
    """API endpoint configuration"""
    name: str
    path: str
    method: str
    description: str
    expected_params: List[str]
    expected_response_fields: List[str]


class APIIntegrationPreparation:
    """Prepares system for API integration after fixes"""
    
    def __init__(self):
        # Database connections
        self.db_config = get_database_config()
        self.neo4j_url = self.db_config.neo4j_url
        self.neo4j_user = self.db_config.neo4j_user
        self.neo4j_password = self.db_config.neo4j_password
        
        self.qdrant_url = self.db_config.qdrant_url
        self.qdrant_api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhc2Nlc3MiOiJtIn0.zz1R7TKuAT4A0dX-M-oZbgX9sYT-x6bwT1EMPGKZ6Jg"
        self.collection_name = self.db_config.collection_name
        
        # Expected API endpoints after integration
        self.api_endpoints = [
            APIEndpoint(
                name="product_search",
                path="/api/products/search",
                method="POST",
                description="Enhanced product search with color/brand/style filters",
                expected_params=["query", "filters", "limit", "offset"],
                expected_response_fields=["products", "total_count", "facets", "suggestions"]
            ),
            APIEndpoint(
                name="product_details",
                path="/api/products/{product_id}",
                method="GET", 
                description="Product details with enhanced attributes",
                expected_params=["product_id"],
                expected_response_fields=["id", "title", "description", "price", "colors", "brands", "styles", "similar_products"]
            ),
            APIEndpoint(
                name="color_facets",
                path="/api/facets/colors",
                method="GET",
                description="Available color filters",
                expected_params=[],
                expected_response_fields=["colors", "counts"]
            ),
            APIEndpoint(
                name="brand_facets", 
                path="/api/facets/brands",
                method="GET",
                description="Available brand filters",
                expected_params=[],
                expected_response_fields=["brands", "counts"]
            ),
            APIEndpoint(
                name="style_facets",
                path="/api/facets/styles", 
                method="GET",
                description="Available style filters",
                expected_params=[],
                expected_response_fields=["styles", "counts"]
            ),
            APIEndpoint(
                name="similar_products",
                path="/api/products/{product_id}/similar",
                method="GET",
                description="Vector-based similar products",
                expected_params=["product_id", "limit"],
                expected_response_fields=["similar_products", "scores"]
            ),
            APIEndpoint(
                name="search_suggestions",
                path="/api/search/suggestions",
                method="GET",
                description="Search query suggestions",
                expected_params=["partial_query"],
                expected_response_fields=["suggestions", "categories"]
            )
        ]
        
        # Integration readiness checks
        self.readiness_checks = [
            "neo4j_enhanced_schema_ready",
            "qdrant_uuid_correlation_ready", 
            "color_nodes_populated",
            "brand_nodes_populated",
            "style_nodes_populated",
            "product_relationships_ready",
            "vector_embeddings_updated",
            "search_performance_acceptable"
        ]
        
    def connect_databases(self):
        """Connect to databases for preparation"""
        print("🔌 Connecting to databases...")
        
        self.neo4j_driver = GraphDatabase.driver(
            self.neo4j_url,
            auth=(self.neo4j_user, self.neo4j_password)
        )
        
        self.qdrant_client = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key
        )
        
        print("✅ Connected to databases")
    
    def check_neo4j_schema_readiness(self) -> Dict:
        """Check if Neo4j schema is ready for API integration"""
        print("🔍 Checking Neo4j schema readiness...")
        
        readiness_results = {}
        
        with self.neo4j_driver.session() as session:
            # Check node counts
            node_counts_result = session.run("""
                CALL apoc.meta.stats() 
                YIELD labels
                RETURN labels
            """)
            
            labels = node_counts_result.single()['labels'] if node_counts_result.single() else {}
            
            # Expected nodes after Phase 2
            expected_nodes = {
                'Product': {'min': 6000000, 'status': 'required'},
                'Color': {'min': 10, 'status': 'required'}, 
                'Brand': {'min': 50, 'status': 'required'},
                'Style': {'min': 20, 'status': 'required'}
            }
            
            for node_type, requirements in expected_nodes.items():
                actual_count = labels.get(node_type, 0)
                is_ready = actual_count >= requirements['min']
                
                readiness_results[f"{node_type.lower()}_nodes"] = {
                    'required': requirements['min'],
                    'actual': actual_count,
                    'ready': is_ready,
                    'status': requirements['status']
                }
            
            # Check relationship counts
            rel_counts_result = session.run("""
                CALL apoc.meta.stats()
                YIELD relTypesCount
                RETURN relTypesCount
            """)
            
            rel_types = rel_counts_result.single()['relTypesCount'] if rel_counts_result.single() else {}
            
            expected_relationships = {
                'HAS_COLOR': {'min': 1000000, 'status': 'required'},
                'HAS_BRAND': {'min': 1000000, 'status': 'required'}, 
                'HAS_STYLE': {'min': 500000, 'status': 'recommended'}
            }
            
            for rel_type, requirements in expected_relationships.items():
                actual_count = rel_types.get(rel_type, 0)
                is_ready = actual_count >= requirements['min']
                
                readiness_results[f"{rel_type.lower()}_relationships"] = {
                    'required': requirements['min'],
                    'actual': actual_count,
                    'ready': is_ready,
                    'status': requirements['status']
                }
        
        # Overall Neo4j readiness
        required_checks = [k for k, v in readiness_results.items() if v['status'] == 'required']
        ready_required = [k for k in required_checks if readiness_results[k]['ready']]
        
        neo4j_ready = len(ready_required) == len(required_checks)
        
        return {
            'neo4j_schema_ready': neo4j_ready,
            'readiness_details': readiness_results,
            'ready_checks': len(ready_required),
            'total_required_checks': len(required_checks)
        }
    
    def check_qdrant_readiness(self) -> Dict:
        """Check if Qdrant is ready for API integration"""
        print("🔍 Checking Qdrant readiness...")
        
        try:
            # Get collection info
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            vector_count = collection_info.points_count
            
            # Test UUID correlation by sampling
            sample_size = 100
            scroll_result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                limit=sample_size,
                with_payload=True
            )
            
            vectors_with_product_id = 0
            for point in scroll_result[0]:
                if point.payload and 'product_id' in point.payload:
                    vectors_with_product_id += 1
            
            correlation_rate = (vectors_with_product_id / len(scroll_result[0]) * 100) if scroll_result[0] else 0
            
            # Expected minimums
            expected_vector_count = 6000000
            expected_correlation_rate = 95.0
            
            vector_count_ready = vector_count >= expected_vector_count
            correlation_ready = correlation_rate >= expected_correlation_rate
            
            return {
                'qdrant_ready': vector_count_ready and correlation_ready,
                'vector_count': vector_count,
                'expected_vector_count': expected_vector_count,
                'vector_count_ready': vector_count_ready,
                'correlation_rate': correlation_rate,
                'expected_correlation_rate': expected_correlation_rate,
                'correlation_ready': correlation_ready
            }
            
        except Exception as e:
            return {
                'qdrant_ready': False,
                'error': str(e)
            }
    
    def generate_api_response_schemas(self) -> Dict:
        """Generate expected API response schemas"""
        print("📝 Generating API response schemas...")
        
        schemas = {}
        
        for endpoint in self.api_endpoints:
            if endpoint.name == "product_search":
                schemas[endpoint.name] = {
                    "type": "object",
                    "properties": {
                        "products": {
                            "type": "array",
                            "items": {
                                "type": "object", 
                                "properties": {
                                    "id": {"type": "string"},
                                    "title": {"type": "string"},
                                    "description": {"type": "string"},
                                    "price": {"type": "number"},
                                    "colors": {"type": "array", "items": {"type": "string"}},
                                    "brands": {"type": "array", "items": {"type": "string"}}, 
                                    "styles": {"type": "array", "items": {"type": "string"}},
                                    "score": {"type": "number"}
                                }
                            }
                        },
                        "total_count": {"type": "integer"},
                        "facets": {
                            "type": "object",
                            "properties": {
                                "colors": {"type": "object"},
                                "brands": {"type": "object"},
                                "styles": {"type": "object"}
                            }
                        },
                        "suggestions": {"type": "array", "items": {"type": "string"}}
                    }
                }
            
            elif endpoint.name == "product_details":
                schemas[endpoint.name] = {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "price": {"type": "number"},
                        "colors": {"type": "array", "items": {"type": "string"}},
                        "brands": {"type": "array", "items": {"type": "string"}},
                        "styles": {"type": "array", "items": {"type": "string"}},
                        "similar_products": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "title": {"type": "string"},
                                    "score": {"type": "number"}
                                }
                            }
                        }
                    }
                }
            
            elif endpoint.name.endswith("_facets"):
                facet_type = endpoint.name.replace("_facets", "")
                schemas[endpoint.name] = {
                    "type": "object",
                    "properties": {
                        facet_type: {"type": "array", "items": {"type": "string"}},
                        "counts": {"type": "object"}
                    }
                }
        
        return schemas
    
    def generate_sample_requests(self) -> Dict:
        """Generate sample API requests for testing"""
        print("🔧 Generating sample API requests...")
        
        sample_requests = {}
        
        sample_requests["product_search"] = {
            "basic_search": {
                "query": "red shirt",
                "limit": 20,
                "offset": 0
            },
            "filtered_search": {
                "query": "shoes",
                "filters": {
                    "colors": ["black", "white"],
                    "brands": ["Nike", "Adidas"],
                    "price_range": {"min": 50, "max": 200}
                },
                "limit": 10,
                "offset": 0
            },
            "multi_constraint_search": {
                "query": "casual dress",
                "filters": {
                    "colors": ["blue"],
                    "styles": ["casual"]
                },
                "limit": 15,
                "offset": 0
            }
        }
        
        sample_requests["product_details"] = {
            "basic_details": {
                "product_id": "sample-product-uuid-123"
            }
        }
        
        sample_requests["similar_products"] = {
            "basic_similarity": {
                "product_id": "sample-product-uuid-123", 
                "limit": 10
            }
        }
        
        sample_requests["search_suggestions"] = {
            "partial_query": {
                "partial_query": "red sh"
            }
        }
        
        return sample_requests
    
    def create_integration_test_suite(self) -> Dict:
        """Create comprehensive integration test suite"""
        print("🧪 Creating integration test suite...")
        
        test_suite = {
            "pre_integration_tests": [
                {
                    "name": "Neo4j Schema Validation",
                    "description": "Verify enhanced schema is ready",
                    "test_function": "check_neo4j_schema_readiness",
                    "success_criteria": "All required nodes and relationships present"
                },
                {
                    "name": "Qdrant UUID Correlation", 
                    "description": "Verify perfect UUID correlation",
                    "test_function": "check_qdrant_readiness",
                    "success_criteria": ">95% vectors have valid product_id"
                }
            ],
            "api_endpoint_tests": [],
            "integration_flow_tests": [
                {
                    "name": "Search to Product Details Flow",
                    "description": "Test complete search -> details workflow",
                    "steps": [
                        "Search for 'red Nike shoes'",
                        "Get first result product_id",
                        "Request product details",
                        "Verify enhanced attributes present"
                    ]
                },
                {
                    "name": "Faceted Search Flow",
                    "description": "Test faceted search functionality",
                    "steps": [
                        "Get available color facets",
                        "Search with specific color filter",
                        "Verify results match filter"
                    ]
                },
                {
                    "name": "Similar Products Flow",
                    "description": "Test vector-based similarity",
                    "steps": [
                        "Get product details",
                        "Request similar products",
                        "Verify similar products returned",
                        "Check similarity scores"
                    ]
                }
            ]
        }
        
        # Add endpoint-specific tests
        for endpoint in self.api_endpoints:
            test_suite["api_endpoint_tests"].append({
                "name": f"Test {endpoint.name}",
                "endpoint": endpoint.path,
                "method": endpoint.method,
                "description": endpoint.description,
                "expected_params": endpoint.expected_params,
                "expected_response_fields": endpoint.expected_response_fields
            })
        
        return test_suite
    
    def generate_performance_benchmarks(self) -> Dict:
        """Generate performance benchmarks for API integration"""
        print("⚡ Generating performance benchmarks...")
        
        benchmarks = {
            "response_time_targets": {
                "product_search": {"max_ms": 500, "target_ms": 200},
                "product_details": {"max_ms": 100, "target_ms": 50},
                "facets": {"max_ms": 100, "target_ms": 30},
                "similar_products": {"max_ms": 300, "target_ms": 150},
                "search_suggestions": {"max_ms": 200, "target_ms": 100}
            },
            "throughput_targets": {
                "concurrent_users": 100,
                "requests_per_second": 50,
                "search_queries_per_minute": 1000
            },
            "data_quality_targets": {
                "search_relevance": {"min_score": 0.7, "target_score": 0.85},
                "facet_accuracy": {"min_percent": 95, "target_percent": 99},
                "product_attribute_completeness": {"min_percent": 85, "target_percent": 95}
            },
            "system_resource_limits": {
                "max_cpu_percent": 80,
                "max_memory_percent": 85,
                "max_database_connections": 50
            }
        }
        
        return benchmarks
    
    def create_rollback_procedures(self) -> Dict:
        """Create rollback procedures if integration fails"""
        print("🔄 Creating rollback procedures...")
        
        rollback_procedures = {
            "database_rollback": {
                "description": "Rollback database changes if integration fails",
                "steps": [
                    {
                        "action": "backup_current_state",
                        "description": "Create backup of current enhanced schema",
                        "command": "CALL apoc.export.cypher.all('pre_api_integration_backup.cypher', {})"
                    },
                    {
                        "action": "restore_previous_schema",
                        "description": "Restore to pre-Phase-2 state if needed",
                        "command": "Execute restore from backup files"
                    },
                    {
                        "action": "verify_rollback",
                        "description": "Verify system functionality after rollback",
                        "command": "Run basic system health checks"
                    }
                ]
            },
            "vector_rollback": {
                "description": "Rollback vector database if correlation fails",
                "steps": [
                    {
                        "action": "backup_current_collection",
                        "description": "Backup current Qdrant collection",
                        "command": "Create collection snapshot"
                    },
                    {
                        "action": "restore_previous_vectors",
                        "description": "Restore previous vector state",
                        "command": "Restore from snapshot"
                    }
                ]
            },
            "api_rollback": {
                "description": "Rollback API changes",
                "steps": [
                    {
                        "action": "disable_new_endpoints",
                        "description": "Disable enhanced API endpoints",
                        "command": "Update API routing configuration"
                    },
                    {
                        "action": "revert_search_logic",
                        "description": "Revert to previous search implementation",
                        "command": "Deploy previous API version"
                    }
                ]
            }
        }
        
        return rollback_procedures
    
    def run_full_preparation(self) -> Dict:
        """Run complete API integration preparation"""
        print("🚀 Running Full API Integration Preparation")
        print("=" * 50)
        
        preparation_report = {
            'timestamp': datetime.now().isoformat(),
            'preparation_status': 'in_progress'
        }
        
        try:
            # Database readiness checks
            neo4j_readiness = self.check_neo4j_schema_readiness()
            qdrant_readiness = self.check_qdrant_readiness()
            
            preparation_report['neo4j_readiness'] = neo4j_readiness
            preparation_report['qdrant_readiness'] = qdrant_readiness
            
            # Generate integration assets
            api_schemas = self.generate_api_response_schemas()
            sample_requests = self.generate_sample_requests()
            test_suite = self.create_integration_test_suite()
            benchmarks = self.generate_performance_benchmarks()
            rollback_procedures = self.create_rollback_procedures()
            
            preparation_report.update({
                'api_schemas': api_schemas,
                'sample_requests': sample_requests,
                'test_suite': test_suite,
                'performance_benchmarks': benchmarks,
                'rollback_procedures': rollback_procedures
            })
            
            # Overall readiness assessment
            neo4j_ready = neo4j_readiness.get('neo4j_schema_ready', False)
            qdrant_ready = qdrant_readiness.get('qdrant_ready', False)
            
            overall_ready = neo4j_ready and qdrant_ready
            
            preparation_report['overall_readiness'] = {
                'ready_for_integration': overall_ready,
                'neo4j_ready': neo4j_ready,
                'qdrant_ready': qdrant_ready,
                'blocking_issues': []
            }
            
            if not neo4j_ready:
                preparation_report['overall_readiness']['blocking_issues'].append("Neo4j schema not ready")
            if not qdrant_ready:
                preparation_report['overall_readiness']['blocking_issues'].append("Qdrant correlation not ready")
            
            preparation_report['preparation_status'] = 'completed'
            
            # Print summary
            print(f"\n📊 API INTEGRATION PREPARATION SUMMARY")
            print("=" * 50)
            print(f"Neo4j Ready: {'✅' if neo4j_ready else '❌'}")
            print(f"Qdrant Ready: {'✅' if qdrant_ready else '❌'}")
            print(f"Overall Ready: {'✅' if overall_ready else '❌'}")
            
            if overall_ready:
                print(f"\n🎉 SYSTEM READY FOR API INTEGRATION!")
                print(f"Generated {len(api_schemas)} API schemas")
                print(f"Created {len(test_suite['api_endpoint_tests'])} endpoint tests")
                print(f"Prepared {len(rollback_procedures)} rollback procedures")
            else:
                print(f"\n⚠️ BLOCKING ISSUES FOUND:")
                for issue in preparation_report['overall_readiness']['blocking_issues']:
                    print(f"  - {issue}")
            
            return preparation_report
            
        except Exception as e:
            preparation_report['preparation_status'] = 'failed'
            preparation_report['error'] = str(e)
            print(f"❌ Preparation failed: {e}")
            return preparation_report
        
        finally:
            if hasattr(self, 'neo4j_driver'):
                self.neo4j_driver.close()
    
    def save_preparation_assets(self, report: Dict):
        """Save all preparation assets to files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save main report
        with open(f"api_integration_preparation_{timestamp}.json", 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Save individual assets
        if 'api_schemas' in report:
            with open(f"api_schemas_{timestamp}.json", 'w') as f:
                json.dump(report['api_schemas'], f, indent=2)
        
        if 'test_suite' in report:
            with open(f"integration_test_suite_{timestamp}.json", 'w') as f:
                json.dump(report['test_suite'], f, indent=2)
        
        if 'performance_benchmarks' in report:
            with open(f"performance_benchmarks_{timestamp}.json", 'w') as f:
                json.dump(report['performance_benchmarks'], f, indent=2)
        
        print(f"💾 Preparation assets saved with timestamp: {timestamp}")


def main():
    """Run API integration preparation"""
    preparator = APIIntegrationPreparation()
    
    try:
        preparator.connect_databases()
        report = preparator.run_full_preparation()
        preparator.save_preparation_assets(report)
        
        return report['overall_readiness']['ready_for_integration']
        
    except Exception as e:
        print(f"❌ API integration preparation failed: {e}")
        return False


if __name__ == "__main__":
    main()