#!/usr/bin/env python3
from config import get_database_config, get_ai_config, get_system_config
"""
Performance Benchmarking Suite
Comprehensive performance testing for the entire system after all fixes
"""

import json
import time
import statistics
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from neo4j import GraphDatabase
from qdrant_client import QdrantClient


@dataclass
class BenchmarkResult:
    """Individual benchmark test result"""
    test_name: str
    execution_time_ms: float
    throughput_per_second: float
    success: bool
    error_message: Optional[str] = None
    additional_metrics: Optional[Dict] = None


@dataclass
class BenchmarkSuite:
    """Benchmark test suite definition"""
    suite_name: str
    tests: List[Dict]
    concurrent_threads: int = 1
    iterations_per_test: int = 10
    warmup_iterations: int = 2


class PerformanceBenchmarkRunner:
    """Runs comprehensive performance benchmarks"""
    
    def __init__(self):
        # Database connections
        self.db_config = get_database_config()
        self.neo4j_url = self.db_config.neo4j_url
        self.neo4j_user = self.db_config.neo4j_user
        self.neo4j_password = self.db_config.neo4j_password
        
        self.qdrant_url = self.db_config.qdrant_url
        self.qdrant_api_key = self.db_config.qdrant_api_key
        self.collection_name = self.db_config.collection_name
        
        # Performance targets
        self.performance_targets = {
            'neo4j_simple_query_ms': 100,        # Max 100ms for simple queries
            'neo4j_complex_query_ms': 500,       # Max 500ms for complex queries
            'neo4j_attribute_query_ms': 200,     # Max 200ms for attribute queries
            'qdrant_vector_search_ms': 300,      # Max 300ms for vector search
            'qdrant_scroll_ms': 100,             # Max 100ms for scroll operations
            'correlation_lookup_ms': 150,        # Max 150ms for UUID correlation
            'concurrent_throughput_rps': 50,     # Min 50 requests per second
            'memory_usage_mb_max': 1000,         # Max 1GB memory usage
            'cpu_usage_percent_max': 80          # Max 80% CPU usage
        }
        
        # Benchmark suites
        self.benchmark_suites = self._define_benchmark_suites()
        
        # Results storage
        self.benchmark_results = {}
        
    def connect_databases(self):
        """Connect to databases for benchmarking"""
        print("🔌 Connecting to databases for benchmarking...")
        
        self.neo4j_driver = GraphDatabase.driver(
            self.neo4j_url,
            auth=(self.neo4j_user, self.neo4j_password)
        )
        
        self.qdrant_client = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key
        )
        
        print("✅ Connected to databases")
    
    def _define_benchmark_suites(self) -> List[BenchmarkSuite]:
        """Define all benchmark suites"""
        suites = []
        
        # Neo4j Performance Suite
        neo4j_suite = BenchmarkSuite(
            suite_name="neo4j_performance",
            concurrent_threads=10,
            iterations_per_test=20,
            tests=[
                {
                    'name': 'simple_product_lookup',
                    'description': 'Simple product lookup by ID',
                    'function': self._benchmark_neo4j_simple_lookup,
                    'target_ms': self.performance_targets['neo4j_simple_query_ms']
                },
                {
                    'name': 'product_with_attributes',
                    'description': 'Product with color/brand/style attributes',
                    'function': self._benchmark_neo4j_attribute_query,
                    'target_ms': self.performance_targets['neo4j_attribute_query_ms']
                },
                {
                    'name': 'color_facet_aggregation',
                    'description': 'Aggregate products by color',
                    'function': self._benchmark_neo4j_color_aggregation,
                    'target_ms': self.performance_targets['neo4j_complex_query_ms']
                },
                {
                    'name': 'brand_facet_aggregation',
                    'description': 'Aggregate products by brand',
                    'function': self._benchmark_neo4j_brand_aggregation,
                    'target_ms': self.performance_targets['neo4j_complex_query_ms']
                },
                {
                    'name': 'multi_attribute_filter',
                    'description': 'Filter products by multiple attributes',
                    'function': self._benchmark_neo4j_multi_filter,
                    'target_ms': self.performance_targets['neo4j_complex_query_ms']
                }
            ]
        )
        suites.append(neo4j_suite)
        
        # Qdrant Performance Suite
        qdrant_suite = BenchmarkSuite(
            suite_name="qdrant_performance",
            concurrent_threads=5,
            iterations_per_test=15,
            tests=[
                {
                    'name': 'vector_similarity_search',
                    'description': 'Vector similarity search',
                    'function': self._benchmark_qdrant_similarity_search,
                    'target_ms': self.performance_targets['qdrant_vector_search_ms']
                },
                {
                    'name': 'vector_scroll_operation',
                    'description': 'Scroll through vectors',
                    'function': self._benchmark_qdrant_scroll,
                    'target_ms': self.performance_targets['qdrant_scroll_ms']
                },
                {
                    'name': 'payload_filtering',
                    'description': 'Filter vectors by payload',
                    'function': self._benchmark_qdrant_payload_filter,
                    'target_ms': self.performance_targets['qdrant_vector_search_ms']
                },
                {
                    'name': 'collection_info',
                    'description': 'Get collection information',
                    'function': self._benchmark_qdrant_collection_info,
                    'target_ms': 50
                }
            ]
        )
        suites.append(qdrant_suite)
        
        # UUID Correlation Suite
        correlation_suite = BenchmarkSuite(
            suite_name="uuid_correlation_performance",
            concurrent_threads=8,
            iterations_per_test=25,
            tests=[
                {
                    'name': 'neo4j_to_qdrant_lookup',
                    'description': 'Look up Qdrant vector from Neo4j product ID',
                    'function': self._benchmark_neo4j_to_qdrant_lookup,
                    'target_ms': self.performance_targets['correlation_lookup_ms']
                },
                {
                    'name': 'qdrant_to_neo4j_lookup',
                    'description': 'Look up Neo4j product from Qdrant vector',
                    'function': self._benchmark_qdrant_to_neo4j_lookup,
                    'target_ms': self.performance_targets['correlation_lookup_ms']
                },
                {
                    'name': 'full_product_enrichment',
                    'description': 'Get enriched product data (Neo4j + Qdrant)',
                    'function': self._benchmark_full_product_enrichment,
                    'target_ms': 250
                }
            ]
        )
        suites.append(correlation_suite)
        
        # Concurrent Load Suite
        load_suite = BenchmarkSuite(
            suite_name="concurrent_load_performance",
            concurrent_threads=20,
            iterations_per_test=50,
            tests=[
                {
                    'name': 'mixed_workload_simulation',
                    'description': 'Simulate mixed read workload',
                    'function': self._benchmark_mixed_workload,
                    'target_ms': 300
                },
                {
                    'name': 'search_throughput_test',
                    'description': 'Measure search throughput under load',
                    'function': self._benchmark_search_throughput,
                    'target_ms': 200
                }
            ]
        )
        suites.append(load_suite)
        
        return suites
    
    def _get_random_product_id(self) -> Optional[str]:
        """Get a random product ID for testing"""
        try:
            with self.neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (p:Product)
                    RETURN p.id as id
                    ORDER BY rand()
                    LIMIT 1
                """)
                record = result.single()
                return record['id'] if record else None
        except Exception:
            return None
    
    # Neo4j Benchmark Functions
    def _benchmark_neo4j_simple_lookup(self) -> BenchmarkResult:
        """Benchmark simple Neo4j product lookup"""
        product_id = self._get_random_product_id()
        if not product_id:
            return BenchmarkResult("neo4j_simple_lookup", 0, 0, False, "No product ID available")
        
        start_time = time.time()
        
        try:
            with self.neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (p:Product {id: $product_id})
                    RETURN p.title, p.description, p.price
                """, product_id=product_id)
                
                record = result.single()
                success = record is not None
            
            execution_time_ms = (time.time() - start_time) * 1000
            throughput = 1000 / execution_time_ms if execution_time_ms > 0 else 0
            
            return BenchmarkResult(
                "neo4j_simple_lookup",
                execution_time_ms,
                throughput,
                success
            )
            
        except Exception as e:
            return BenchmarkResult("neo4j_simple_lookup", 0, 0, False, str(e))
    
    def _benchmark_neo4j_attribute_query(self) -> BenchmarkResult:
        """Benchmark Neo4j query with attributes"""
        product_id = self._get_random_product_id()
        if not product_id:
            return BenchmarkResult("neo4j_attribute_query", 0, 0, False, "No product ID available")
        
        start_time = time.time()
        
        try:
            with self.neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (p:Product {id: $product_id})
                    OPTIONAL MATCH (p)-[:HAS_COLOR]->(c:Color)
                    OPTIONAL MATCH (p)-[:HAS_BRAND]->(b:Brand)
                    OPTIONAL MATCH (p)-[:HAS_STYLE]->(s:Style)
                    RETURN p.title, p.price,
                           COLLECT(DISTINCT c.name) as colors,
                           COLLECT(DISTINCT b.name) as brands,
                           COLLECT(DISTINCT s.name) as styles
                """, product_id=product_id)
                
                record = result.single()
                success = record is not None
            
            execution_time_ms = (time.time() - start_time) * 1000
            throughput = 1000 / execution_time_ms if execution_time_ms > 0 else 0
            
            return BenchmarkResult(
                "neo4j_attribute_query",
                execution_time_ms,
                throughput,
                success
            )
            
        except Exception as e:
            return BenchmarkResult("neo4j_attribute_query", 0, 0, False, str(e))
    
    def _benchmark_neo4j_color_aggregation(self) -> BenchmarkResult:
        """Benchmark Neo4j color aggregation"""
        start_time = time.time()
        
        try:
            with self.neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (c:Color)<-[:HAS_COLOR]-(p:Product)
                    RETURN c.name as color, COUNT(p) as product_count
                    ORDER BY product_count DESC
                    LIMIT 20
                """)
                
                records = list(result)
                success = len(records) > 0
            
            execution_time_ms = (time.time() - start_time) * 1000
            throughput = len(records) * 1000 / execution_time_ms if execution_time_ms > 0 else 0
            
            return BenchmarkResult(
                "neo4j_color_aggregation",
                execution_time_ms,
                throughput,
                success,
                additional_metrics={'aggregated_colors': len(records)}
            )
            
        except Exception as e:
            return BenchmarkResult("neo4j_color_aggregation", 0, 0, False, str(e))
    
    def _benchmark_neo4j_brand_aggregation(self) -> BenchmarkResult:
        """Benchmark Neo4j brand aggregation"""
        start_time = time.time()
        
        try:
            with self.neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (b:Brand)<-[:HAS_BRAND]-(p:Product)
                    RETURN b.name as brand, COUNT(p) as product_count
                    ORDER BY product_count DESC
                    LIMIT 20
                """)
                
                records = list(result)
                success = len(records) > 0
            
            execution_time_ms = (time.time() - start_time) * 1000
            throughput = len(records) * 1000 / execution_time_ms if execution_time_ms > 0 else 0
            
            return BenchmarkResult(
                "neo4j_brand_aggregation",
                execution_time_ms,
                throughput,
                success,
                additional_metrics={'aggregated_brands': len(records)}
            )
            
        except Exception as e:
            return BenchmarkResult("neo4j_brand_aggregation", 0, 0, False, str(e))
    
    def _benchmark_neo4j_multi_filter(self) -> BenchmarkResult:
        """Benchmark Neo4j multi-attribute filtering"""
        start_time = time.time()
        
        try:
            with self.neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (p:Product)-[:HAS_COLOR]->(c:Color {name: 'red'})
                    MATCH (p)-[:HAS_BRAND]->(b:Brand)
                    WHERE p.price < 100
                    RETURN p.id, p.title, p.price, b.name as brand
                    LIMIT 50
                """)
                
                records = list(result)
                success = True  # Multi-filter can return 0 results and still be successful
            
            execution_time_ms = (time.time() - start_time) * 1000
            throughput = len(records) * 1000 / execution_time_ms if execution_time_ms > 0 else 0
            
            return BenchmarkResult(
                "neo4j_multi_filter",
                execution_time_ms,
                throughput,
                success,
                additional_metrics={'filtered_results': len(records)}
            )
            
        except Exception as e:
            return BenchmarkResult("neo4j_multi_filter", 0, 0, False, str(e))
    
    # Qdrant Benchmark Functions
    def _benchmark_qdrant_similarity_search(self) -> BenchmarkResult:
        """Benchmark Qdrant similarity search"""
        start_time = time.time()
        
        try:
            # Create a dummy query vector (normally this would be from embedding)
            query_vector = [0.1] * 1536  # Assuming 1536-dimensional vectors
            
            search_result = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=10,
                with_payload=True
            )
            
            execution_time_ms = (time.time() - start_time) * 1000
            throughput = len(search_result) * 1000 / execution_time_ms if execution_time_ms > 0 else 0
            
            return BenchmarkResult(
                "qdrant_similarity_search",
                execution_time_ms,
                throughput,
                True,
                additional_metrics={'results_found': len(search_result)}
            )
            
        except Exception as e:
            return BenchmarkResult("qdrant_similarity_search", 0, 0, False, str(e))
    
    def _benchmark_qdrant_scroll(self) -> BenchmarkResult:
        """Benchmark Qdrant scroll operation"""
        start_time = time.time()
        
        try:
            scroll_result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                limit=100,
                with_payload=True,
                with_vectors=False
            )
            
            vectors = scroll_result[0]
            execution_time_ms = (time.time() - start_time) * 1000
            throughput = len(vectors) * 1000 / execution_time_ms if execution_time_ms > 0 else 0
            
            return BenchmarkResult(
                "qdrant_scroll",
                execution_time_ms,
                throughput,
                len(vectors) > 0,
                additional_metrics={'vectors_scrolled': len(vectors)}
            )
            
        except Exception as e:
            return BenchmarkResult("qdrant_scroll", 0, 0, False, str(e))
    
    def _benchmark_qdrant_payload_filter(self) -> BenchmarkResult:
        """Benchmark Qdrant payload filtering"""
        start_time = time.time()
        
        try:
            # Filter by payload (assuming product_id exists)
            from qdrant_client.http import models
            
            filter_condition = models.Filter(
                must=[
                    models.FieldCondition(
                        key="product_id",
                        match=models.MatchAny(any=["sample-id-1", "sample-id-2"])
                    )
                ]
            )
            
            search_result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=filter_condition,
                limit=50,
                with_payload=True
            )
            
            vectors = search_result[0]
            execution_time_ms = (time.time() - start_time) * 1000
            throughput = len(vectors) * 1000 / execution_time_ms if execution_time_ms > 0 else 0
            
            return BenchmarkResult(
                "qdrant_payload_filter",
                execution_time_ms,
                throughput,
                True,
                additional_metrics={'filtered_results': len(vectors)}
            )
            
        except Exception as e:
            return BenchmarkResult("qdrant_payload_filter", 0, 0, False, str(e))
    
    def _benchmark_qdrant_collection_info(self) -> BenchmarkResult:
        """Benchmark Qdrant collection info retrieval"""
        start_time = time.time()
        
        try:
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            
            execution_time_ms = (time.time() - start_time) * 1000
            throughput = 1000 / execution_time_ms if execution_time_ms > 0 else 0
            
            return BenchmarkResult(
                "qdrant_collection_info",
                execution_time_ms,
                throughput,
                True,
                additional_metrics={'points_count': collection_info.points_count}
            )
            
        except Exception as e:
            return BenchmarkResult("qdrant_collection_info", 0, 0, False, str(e))
    
    # Correlation Benchmark Functions
    def _benchmark_neo4j_to_qdrant_lookup(self) -> BenchmarkResult:
        """Benchmark Neo4j product ID to Qdrant vector lookup"""
        product_id = self._get_random_product_id()
        if not product_id:
            return BenchmarkResult("neo4j_to_qdrant_lookup", 0, 0, False, "No product ID available")
        
        start_time = time.time()
        
        try:
            # Look up vector in Qdrant using product_id
            from qdrant_client.http import models
            
            filter_condition = models.Filter(
                must=[
                    models.FieldCondition(
                        key="product_id",
                        match=models.MatchValue(value=product_id)
                    )
                ]
            )
            
            scroll_result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=filter_condition,
                limit=1,
                with_payload=True
            )
            
            vectors = scroll_result[0]
            success = len(vectors) > 0
            
            execution_time_ms = (time.time() - start_time) * 1000
            throughput = 1000 / execution_time_ms if execution_time_ms > 0 else 0
            
            return BenchmarkResult(
                "neo4j_to_qdrant_lookup",
                execution_time_ms,
                throughput,
                success
            )
            
        except Exception as e:
            return BenchmarkResult("neo4j_to_qdrant_lookup", 0, 0, False, str(e))
    
    def _benchmark_qdrant_to_neo4j_lookup(self) -> BenchmarkResult:
        """Benchmark Qdrant vector to Neo4j product lookup"""
        start_time = time.time()
        
        try:
            # Get a random vector
            scroll_result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                limit=1,
                with_payload=True
            )
            
            if not scroll_result[0]:
                return BenchmarkResult("qdrant_to_neo4j_lookup", 0, 0, False, "No vectors found")
            
            vector = scroll_result[0][0]
            product_id = vector.payload.get('product_id') if vector.payload else None
            
            if not product_id:
                return BenchmarkResult("qdrant_to_neo4j_lookup", 0, 0, False, "No product_id in vector")
            
            # Look up product in Neo4j
            with self.neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (p:Product {id: $product_id})
                    RETURN p.title, p.price
                """, product_id=product_id)
                
                record = result.single()
                success = record is not None
            
            execution_time_ms = (time.time() - start_time) * 1000
            throughput = 1000 / execution_time_ms if execution_time_ms > 0 else 0
            
            return BenchmarkResult(
                "qdrant_to_neo4j_lookup",
                execution_time_ms,
                throughput,
                success
            )
            
        except Exception as e:
            return BenchmarkResult("qdrant_to_neo4j_lookup", 0, 0, False, str(e))
    
    def _benchmark_full_product_enrichment(self) -> BenchmarkResult:
        """Benchmark full product enrichment (Neo4j + Qdrant data)"""
        product_id = self._get_random_product_id()
        if not product_id:
            return BenchmarkResult("full_product_enrichment", 0, 0, False, "No product ID available")
        
        start_time = time.time()
        
        try:
            # Get Neo4j data
            with self.neo4j_driver.session() as session:
                neo4j_result = session.run("""
                    MATCH (p:Product {id: $product_id})
                    OPTIONAL MATCH (p)-[:HAS_COLOR]->(c:Color)
                    OPTIONAL MATCH (p)-[:HAS_BRAND]->(b:Brand)
                    OPTIONAL MATCH (p)-[:HAS_STYLE]->(s:Style)
                    RETURN p.title, p.description, p.price,
                           COLLECT(DISTINCT c.name) as colors,
                           COLLECT(DISTINCT b.name) as brands,
                           COLLECT(DISTINCT s.name) as styles
                """, product_id=product_id)
                
                neo4j_data = neo4j_result.single()
            
            # Get Qdrant data
            from qdrant_client.http import models
            
            filter_condition = models.Filter(
                must=[
                    models.FieldCondition(
                        key="product_id",
                        match=models.MatchValue(value=product_id)
                    )
                ]
            )
            
            qdrant_result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=filter_condition,
                limit=1,
                with_payload=True
            )
            
            success = neo4j_data is not None and len(qdrant_result[0]) > 0
            
            execution_time_ms = (time.time() - start_time) * 1000
            throughput = 1000 / execution_time_ms if execution_time_ms > 0 else 0
            
            return BenchmarkResult(
                "full_product_enrichment",
                execution_time_ms,
                throughput,
                success
            )
            
        except Exception as e:
            return BenchmarkResult("full_product_enrichment", 0, 0, False, str(e))
    
    # Load Testing Functions
    def _benchmark_mixed_workload(self) -> BenchmarkResult:
        """Benchmark mixed workload simulation"""
        import random
        
        start_time = time.time()
        operations_completed = 0
        
        try:
            # Simulate mixed operations
            for _ in range(5):  # 5 random operations
                operation_type = random.choice(['neo4j_lookup', 'qdrant_search', 'correlation'])
                
                if operation_type == 'neo4j_lookup':
                    self._benchmark_neo4j_simple_lookup()
                elif operation_type == 'qdrant_search':
                    self._benchmark_qdrant_scroll()
                else:
                    self._benchmark_neo4j_to_qdrant_lookup()
                
                operations_completed += 1
            
            execution_time_ms = (time.time() - start_time) * 1000
            throughput = operations_completed * 1000 / execution_time_ms if execution_time_ms > 0 else 0
            
            return BenchmarkResult(
                "mixed_workload_simulation",
                execution_time_ms,
                throughput,
                True,
                additional_metrics={'operations_completed': operations_completed}
            )
            
        except Exception as e:
            return BenchmarkResult("mixed_workload_simulation", 0, 0, False, str(e))
    
    def _benchmark_search_throughput(self) -> BenchmarkResult:
        """Benchmark search throughput under load"""
        start_time = time.time()
        successful_searches = 0
        
        try:
            # Perform multiple quick searches
            for _ in range(3):
                scroll_result = self.qdrant_client.scroll(
                    collection_name=self.collection_name,
                    limit=10,
                    with_payload=False
                )
                
                if scroll_result[0]:
                    successful_searches += 1
            
            execution_time_ms = (time.time() - start_time) * 1000
            throughput = successful_searches * 1000 / execution_time_ms if execution_time_ms > 0 else 0
            
            return BenchmarkResult(
                "search_throughput_test",
                execution_time_ms,
                throughput,
                successful_searches > 0,
                additional_metrics={'successful_searches': successful_searches}
            )
            
        except Exception as e:
            return BenchmarkResult("search_throughput_test", 0, 0, False, str(e))
    
    def run_single_benchmark(self, test_function: Callable, test_name: str, iterations: int = 10) -> Dict:
        """Run a single benchmark test multiple times"""
        results = []
        warmup_results = []
        
        # Warmup iterations
        for _ in range(2):
            warmup_result = test_function()
            warmup_results.append(warmup_result)
        
        # Actual benchmark iterations
        for _ in range(iterations):
            result = test_function()
            results.append(result)
        
        # Calculate statistics
        successful_results = [r for r in results if r.success]
        
        if not successful_results:
            return {
                'test_name': test_name,
                'success': False,
                'error': 'All iterations failed',
                'failed_iterations': len(results)
            }
        
        execution_times = [r.execution_time_ms for r in successful_results]
        throughputs = [r.throughput_per_second for r in successful_results]
        
        benchmark_stats = {
            'test_name': test_name,
            'success': True,
            'total_iterations': iterations,
            'successful_iterations': len(successful_results),
            'failed_iterations': len(results) - len(successful_results),
            'execution_time_ms': {
                'min': min(execution_times),
                'max': max(execution_times),
                'mean': statistics.mean(execution_times),
                'median': statistics.median(execution_times),
                'std_dev': statistics.stdev(execution_times) if len(execution_times) > 1 else 0
            },
            'throughput_per_second': {
                'min': min(throughputs),
                'max': max(throughputs),
                'mean': statistics.mean(throughputs),
                'median': statistics.median(throughputs)
            }
        }
        
        # Add additional metrics if available
        additional_metrics = {}
        for result in successful_results:
            if result.additional_metrics:
                for key, value in result.additional_metrics.items():
                    if key not in additional_metrics:
                        additional_metrics[key] = []
                    additional_metrics[key].append(value)
        
        if additional_metrics:
            benchmark_stats['additional_metrics'] = {}
            for key, values in additional_metrics.items():
                if all(isinstance(v, (int, float)) for v in values):
                    benchmark_stats['additional_metrics'][key] = {
                        'mean': statistics.mean(values),
                        'total': sum(values)
                    }
        
        return benchmark_stats
    
    def run_concurrent_benchmark(self, test_function: Callable, test_name: str, 
                                concurrent_threads: int = 5, iterations_per_thread: int = 10) -> Dict:
        """Run benchmark with concurrent threads"""
        print(f"⚡ Running concurrent benchmark: {test_name} ({concurrent_threads} threads)")
        
        start_time = time.time()
        all_results = []
        
        def thread_worker():
            thread_results = []
            for _ in range(iterations_per_thread):
                result = test_function()
                thread_results.append(result)
            return thread_results
        
        with ThreadPoolExecutor(max_workers=concurrent_threads) as executor:
            futures = [executor.submit(thread_worker) for _ in range(concurrent_threads)]
            
            for future in as_completed(futures):
                try:
                    thread_results = future.result()
                    all_results.extend(thread_results)
                except Exception as e:
                    print(f"Thread failed: {e}")
        
        total_time = time.time() - start_time
        
        # Calculate concurrent performance statistics
        successful_results = [r for r in all_results if r.success]
        total_operations = len(all_results)
        successful_operations = len(successful_results)
        
        if not successful_results:
            return {
                'test_name': test_name,
                'success': False,
                'concurrent_threads': concurrent_threads,
                'total_operations': total_operations,
                'error': 'All concurrent operations failed'
            }
        
        # Overall throughput (operations per second)
        overall_throughput = successful_operations / total_time
        
        execution_times = [r.execution_time_ms for r in successful_results]
        
        return {
            'test_name': test_name,
            'success': True,
            'concurrent_threads': concurrent_threads,
            'total_operations': total_operations,
            'successful_operations': successful_operations,
            'failed_operations': total_operations - successful_operations,
            'total_execution_time_seconds': total_time,
            'overall_throughput_ops_per_second': overall_throughput,
            'individual_operation_stats': {
                'execution_time_ms': {
                    'min': min(execution_times),
                    'max': max(execution_times),
                    'mean': statistics.mean(execution_times),
                    'median': statistics.median(execution_times),
                    'p95': statistics.quantiles(execution_times, n=20)[18] if len(execution_times) >= 20 else max(execution_times)
                }
            }
        }
    
    def run_benchmark_suite(self, suite: BenchmarkSuite) -> Dict:
        """Run a complete benchmark suite"""
        print(f"🚀 Running benchmark suite: {suite.suite_name}")
        
        suite_results = {
            'suite_name': suite.suite_name,
            'timestamp': datetime.now().isoformat(),
            'test_results': {},
            'suite_summary': {}
        }
        
        total_tests = len(suite.tests)
        passed_tests = 0
        failed_tests = 0
        
        for test in suite.tests:
            test_name = test['name']
            test_function = test['function']
            target_ms = test.get('target_ms', float('inf'))
            
            print(f"  📊 Running: {test_name}")
            
            if suite.concurrent_threads > 1:
                # Concurrent benchmark
                result = self.run_concurrent_benchmark(
                    test_function,
                    test_name,
                    suite.concurrent_threads,
                    suite.iterations_per_test
                )
            else:
                # Single-threaded benchmark
                result = self.run_single_benchmark(
                    test_function,
                    test_name,
                    suite.iterations_per_test
                )
            
            # Performance assessment
            if result['success']:
                if suite.concurrent_threads > 1:
                    avg_time = result['individual_operation_stats']['execution_time_ms']['mean']
                else:
                    avg_time = result['execution_time_ms']['mean']
                
                performance_passed = avg_time <= target_ms
                result['performance_target_ms'] = target_ms
                result['performance_passed'] = performance_passed
                
                if performance_passed:
                    passed_tests += 1
                    print(f"    ✅ PASSED: {avg_time:.1f}ms (target: {target_ms}ms)")
                else:
                    failed_tests += 1
                    print(f"    ⚠️ SLOW: {avg_time:.1f}ms (target: {target_ms}ms)")
            else:
                failed_tests += 1
                print(f"    ❌ FAILED: {result.get('error', 'Unknown error')}")
            
            suite_results['test_results'][test_name] = result
        
        # Suite summary
        suite_results['suite_summary'] = {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0
        }
        
        return suite_results
    
    def run_all_benchmarks(self) -> Dict:
        """Run all benchmark suites"""
        print("🚀 Starting Comprehensive Performance Benchmarking")
        print("=" * 60)
        
        benchmark_report = {
            'timestamp': datetime.now().isoformat(),
            'system_info': self._get_system_info(),
            'performance_targets': self.performance_targets,
            'suite_results': {},
            'overall_summary': {}
        }
        
        total_suites = len(self.benchmark_suites)
        passed_suites = 0
        
        for suite in self.benchmark_suites:
            suite_result = self.run_benchmark_suite(suite)
            benchmark_report['suite_results'][suite.suite_name] = suite_result
            
            if suite_result['suite_summary']['success_rate'] >= 80:
                passed_suites += 1
                print(f"✅ Suite {suite.suite_name}: {suite_result['suite_summary']['success_rate']:.1f}% passed")
            else:
                print(f"❌ Suite {suite.suite_name}: {suite_result['suite_summary']['success_rate']:.1f}% passed")
        
        # Overall summary
        benchmark_report['overall_summary'] = {
            'total_suites': total_suites,
            'passed_suites': passed_suites,
            'failed_suites': total_suites - passed_suites,
            'overall_success_rate': (passed_suites / total_suites * 100) if total_suites > 0 else 0
        }
        
        self._print_final_summary(benchmark_report)
        
        return benchmark_report
    
    def _get_system_info(self) -> Dict:
        """Get system information for benchmark context"""
        try:
            import psutil
            import platform
            
            return {
                'platform': platform.platform(),
                'python_version': platform.python_version(),
                'cpu_count': psutil.cpu_count(),
                'memory_total_gb': psutil.virtual_memory().total / (1024**3),
                'disk_total_gb': psutil.disk_usage('/').total / (1024**3)
            }
        except ImportError:
            return {'error': 'System info not available'}
    
    def _print_final_summary(self, report: Dict):
        """Print final benchmark summary"""
        print(f"\n📊 PERFORMANCE BENCHMARK RESULTS")
        print("=" * 60)
        
        overall = report['overall_summary']
        print(f"Overall Success Rate: {overall['overall_success_rate']:.1f}%")
        print(f"Suites Passed: {overall['passed_suites']}/{overall['total_suites']}")
        
        # Print suite summaries
        print(f"\n📈 SUITE DETAILS:")
        for suite_name, suite_result in report['suite_results'].items():
            summary = suite_result['suite_summary']
            print(f"  {suite_name}: {summary['success_rate']:.1f}% ({summary['passed_tests']}/{summary['total_tests']} tests)")
        
        # Performance recommendations
        print(f"\n💡 PERFORMANCE RECOMMENDATIONS:")
        if overall['overall_success_rate'] >= 90:
            print("  🎉 Excellent performance - system ready for production")
        elif overall['overall_success_rate'] >= 70:
            print("  ⚠️ Good performance - minor optimizations recommended")
        else:
            print("  ❌ Performance issues detected - optimization required")
    
    def save_benchmark_results(self, report: Dict, filename: str = None):
        """Save benchmark results to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_benchmark_results_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"💾 Benchmark results saved: {filename}")


def main():
    """Run performance benchmarking suite"""
    benchmarker = PerformanceBenchmarkRunner()
    
    try:
        benchmarker.connect_databases()
        report = benchmarker.run_all_benchmarks()
        benchmarker.save_benchmark_results(report)
        
        return report['overall_summary']['overall_success_rate'] >= 70
        
    except Exception as e:
        print(f"❌ Benchmarking failed: {e}")
        return False
    
    finally:
        if hasattr(benchmarker, 'neo4j_driver'):
            benchmarker.neo4j_driver.close()


if __name__ == "__main__":
    main()