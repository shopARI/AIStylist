#!/usr/bin/env python3
from config import get_database_config, get_ai_config, get_system_config
"""
Real-time Integration Testing
Tests actual search API endpoints and system integration in real-time during deployment
"""

import json
import time
import requests
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from neo4j import GraphDatabase
from qdrant_client import QdrantClient


@dataclass
class IntegrationTestResult:
    """Result of an integration test"""
    test_name: str
    success: bool
    response_time_ms: float
    expected_result: Any
    actual_result: Any
    error_message: Optional[str] = None
    timestamp: Optional[datetime] = None


class LiveIntegrationTester:
    """Real-time integration testing during deployment"""
    
    def __init__(self):
        # Database connections
        self.db_config = get_database_config()
        self.neo4j_url = self.db_config.neo4j_url
        self.neo4j_user = self.db_config.neo4j_user
        self.neo4j_password = self.db_config.neo4j_password
        
        self.qdrant_url = self.db_config.qdrant_url
        self.qdrant_api_key = self.db_config.qdrant_api_key
        self.collection_name = self.db_config.collection_name
        
        # API endpoints (would be configured for actual API)
        self.api_base_url = "http://localhost:8000/api"  # Placeholder
        self.api_key = "your-api-key"  # Placeholder
        
        # Test scenarios for real-time validation
        self.integration_test_scenarios = [
            {
                'name': 'color_search_integration',
                'description': 'Test end-to-end color search functionality',
                'test_queries': ['red shirt', 'blue dress', 'black shoes'],
                'expected_behavior': 'Returns products matching specified color'
            },
            {
                'name': 'brand_search_integration',
                'description': 'Test brand-specific search functionality',
                'test_queries': ['Nike shoes', 'Adidas clothing', 'Puma sneakers'],
                'expected_behavior': 'Returns products from specified brand'
            },
            {
                'name': 'multi_attribute_search',
                'description': 'Test complex multi-attribute filtering',
                'test_queries': ['red Nike shoes', 'blue casual dress', 'black formal shirt'],
                'expected_behavior': 'Returns products matching all specified attributes'
            },
            {
                'name': 'uuid_correlation_validation',
                'description': 'Test Neo4j to Qdrant correlation works correctly',
                'test_type': 'correlation_test',
                'expected_behavior': 'Perfect correlation between databases'
            },
            {
                'name': 'search_performance_validation',
                'description': 'Test search performance under load',
                'test_type': 'performance_test',
                'expected_behavior': 'Response times within acceptable limits'
            }
        ]
        
        # Continuous monitoring settings
        self.monitoring_active = False
        self.monitoring_thread = None
        self.test_results = []
        
    def connect_databases(self):
        """Connect to databases for testing"""
        print("🔌 Connecting to databases for live testing...")
        
        self.neo4j_driver = GraphDatabase.driver(
            self.neo4j_url,
            auth=(self.neo4j_user, self.neo4j_password)
        )
        
        self.qdrant_client = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key
        )
        
        print("✅ Connected to databases")
    
    def test_color_search_integration(self, query: str) -> IntegrationTestResult:
        """Test color search end-to-end integration"""
        start_time = time.time()
        
        try:
            # Extract color from query
            color = self._extract_color_from_query(query)
            if not color:
                return IntegrationTestResult(
                    'color_search_integration',
                    False,
                    0,
                    f"Products with color: {color}",
                    None,
                    f"Could not extract color from query: {query}",
                    datetime.now()
                )
            
            # Step 1: Search Neo4j for products with this color
            with self.neo4j_driver.session() as session:
                neo4j_result = session.run("""
                    MATCH (p:Product)-[:HAS_COLOR]->(c:Color)
                    WHERE toLower(c.name) = toLower($color)
                    RETURN p.id as product_id, p.title as title, c.name as color_name
                    LIMIT 10
                """, color=color)
                
                neo4j_products = [dict(record) for record in neo4j_result]
            
            # Step 2: For each product, verify it exists in Qdrant with correct correlation
            correlated_products = []
            for product in neo4j_products:
                product_id = product['product_id']
                
                # Look up in Qdrant using product_id
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
                
                if qdrant_result[0]:  # Found correlation
                    correlated_products.append({
                        'neo4j_data': product,
                        'qdrant_found': True,
                        'qdrant_id': qdrant_result[0][0].id
                    })
                else:
                    correlated_products.append({
                        'neo4j_data': product,
                        'qdrant_found': False,
                        'qdrant_id': None
                    })
            
            # Calculate success metrics
            total_products = len(neo4j_products)
            correlated_count = len([p for p in correlated_products if p['qdrant_found']])
            correlation_rate = (correlated_count / total_products * 100) if total_products > 0 else 0
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            # Success if we found products with the color and correlation is good
            success = total_products > 0 and correlation_rate >= 95
            
            return IntegrationTestResult(
                'color_search_integration',
                success,
                execution_time_ms,
                f"Products with color '{color}' and >95% correlation",
                {
                    'products_found': total_products,
                    'correlation_rate': correlation_rate,
                    'correlated_products': correlated_count,
                    'query': query,
                    'color': color
                },
                None if success else f"Low correlation rate: {correlation_rate:.1f}%",
                datetime.now()
            )
            
        except Exception as e:
            return IntegrationTestResult(
                'color_search_integration',
                False,
                (time.time() - start_time) * 1000,
                f"Products with color from query: {query}",
                None,
                str(e),
                datetime.now()
            )
    
    def test_brand_search_integration(self, query: str) -> IntegrationTestResult:
        """Test brand search end-to-end integration"""
        start_time = time.time()
        
        try:
            # Extract brand from query
            brand = self._extract_brand_from_query(query)
            if not brand:
                return IntegrationTestResult(
                    'brand_search_integration',
                    False,
                    0,
                    f"Products with brand: {brand}",
                    None,
                    f"Could not extract brand from query: {query}",
                    datetime.now()
                )
            
            # Search Neo4j for products with this brand
            with self.neo4j_driver.session() as session:
                neo4j_result = session.run("""
                    MATCH (p:Product)-[:HAS_BRAND]->(b:Brand)
                    WHERE toLower(b.name) = toLower($brand)
                    RETURN p.id as product_id, p.title as title, b.name as brand_name
                    LIMIT 10
                """, brand=brand)
                
                neo4j_products = [dict(record) for record in neo4j_result]
            
            # Verify Qdrant correlation for found products
            correlated_products = 0
            for product in neo4j_products:
                product_id = product['product_id']
                
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
                    limit=1
                )
                
                if qdrant_result[0]:
                    correlated_products += 1
            
            total_products = len(neo4j_products)
            correlation_rate = (correlated_products / total_products * 100) if total_products > 0 else 0
            execution_time_ms = (time.time() - start_time) * 1000
            
            success = total_products > 0 and correlation_rate >= 95
            
            return IntegrationTestResult(
                'brand_search_integration',
                success,
                execution_time_ms,
                f"Products with brand '{brand}' and >95% correlation",
                {
                    'products_found': total_products,
                    'correlation_rate': correlation_rate,
                    'query': query,
                    'brand': brand
                },
                None if success else f"Brand search failed or low correlation: {correlation_rate:.1f}%",
                datetime.now()
            )
            
        except Exception as e:
            return IntegrationTestResult(
                'brand_search_integration',
                False,
                (time.time() - start_time) * 1000,
                f"Products with brand from query: {query}",
                None,
                str(e),
                datetime.now()
            )
    
    def test_multi_attribute_search(self, query: str) -> IntegrationTestResult:
        """Test multi-attribute search integration"""
        start_time = time.time()
        
        try:
            # Extract multiple attributes from query
            color = self._extract_color_from_query(query)
            brand = self._extract_brand_from_query(query)
            style = self._extract_style_from_query(query)
            
            attributes = {'color': color, 'brand': brand, 'style': style}
            found_attributes = {k: v for k, v in attributes.items() if v}
            
            if len(found_attributes) < 2:
                return IntegrationTestResult(
                    'multi_attribute_search',
                    False,
                    0,
                    "Products matching multiple attributes",
                    None,
                    f"Could not extract enough attributes from query: {query}",
                    datetime.now()
                )
            
            # Build Neo4j query dynamically based on found attributes
            cypher_parts = ["MATCH (p:Product)"]
            params = {}
            
            if 'color' in found_attributes:
                cypher_parts.append("MATCH (p)-[:HAS_COLOR]->(c:Color)")
                cypher_parts.append("WHERE toLower(c.name) = toLower($color)")
                params['color'] = found_attributes['color']
            
            if 'brand' in found_attributes:
                cypher_parts.append("MATCH (p)-[:HAS_BRAND]->(b:Brand)")
                if 'color' not in found_attributes:
                    cypher_parts.append("WHERE toLower(b.name) = toLower($brand)")
                else:
                    cypher_parts.append("AND toLower(b.name) = toLower($brand)")
                params['brand'] = found_attributes['brand']
            
            if 'style' in found_attributes:
                cypher_parts.append("MATCH (p)-[:HAS_STYLE]->(s:Style)")
                if len([k for k in found_attributes.keys() if k in ['color', 'brand']]) == 0:
                    cypher_parts.append("WHERE toLower(s.name) = toLower($style)")
                else:
                    cypher_parts.append("AND toLower(s.name) = toLower($style)")
                params['style'] = found_attributes['style']
            
            cypher_parts.append("RETURN p.id as product_id, p.title as title LIMIT 10")
            cypher_query = " ".join(cypher_parts)
            
            with self.neo4j_driver.session() as session:
                neo4j_result = session.run(cypher_query, **params)
                neo4j_products = [dict(record) for record in neo4j_result]
            
            # Verify Qdrant correlation
            correlated_products = 0
            for product in neo4j_products:
                from qdrant_client.http import models
                filter_condition = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="product_id",
                            match=models.MatchValue(value=product['product_id'])
                        )
                    ]
                )
                
                qdrant_result = self.qdrant_client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=filter_condition,
                    limit=1
                )
                
                if qdrant_result[0]:
                    correlated_products += 1
            
            total_products = len(neo4j_products)
            correlation_rate = (correlated_products / total_products * 100) if total_products > 0 else 0
            execution_time_ms = (time.time() - start_time) * 1000
            
            success = total_products > 0 and correlation_rate >= 90
            
            return IntegrationTestResult(
                'multi_attribute_search',
                success,
                execution_time_ms,
                f"Products matching {len(found_attributes)} attributes with >90% correlation",
                {
                    'products_found': total_products,
                    'correlation_rate': correlation_rate,
                    'attributes_found': found_attributes,
                    'query': query
                },
                None if success else f"Multi-attribute search failed: {correlation_rate:.1f}% correlation",
                datetime.now()
            )
            
        except Exception as e:
            return IntegrationTestResult(
                'multi_attribute_search',
                False,
                (time.time() - start_time) * 1000,
                f"Multi-attribute search for: {query}",
                None,
                str(e),
                datetime.now()
            )
    
    def test_uuid_correlation_live(self) -> IntegrationTestResult:
        """Test live UUID correlation between Neo4j and Qdrant"""
        start_time = time.time()
        
        try:
            # Sample random products from Neo4j
            with self.neo4j_driver.session() as session:
                neo4j_result = session.run("""
                    MATCH (p:Product)
                    RETURN p.id as product_id
                    ORDER BY rand()
                    LIMIT 100
                """)
                
                product_ids = [record['product_id'] for record in neo4j_result]
            
            if not product_ids:
                return IntegrationTestResult(
                    'uuid_correlation_validation',
                    False,
                    0,
                    "Perfect UUID correlation",
                    None,
                    "No products found in Neo4j",
                    datetime.now()
                )
            
            # Check correlation in Qdrant
            correlated_count = 0
            for product_id in product_ids:
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
                    limit=1
                )
                
                if qdrant_result[0]:
                    # Verify the vector ID matches the product ID
                    vector = qdrant_result[0][0]
                    if str(vector.id) == str(product_id):
                        correlated_count += 1
            
            correlation_rate = (correlated_count / len(product_ids)) * 100
            execution_time_ms = (time.time() - start_time) * 1000
            
            success = correlation_rate >= 99
            
            return IntegrationTestResult(
                'uuid_correlation_validation',
                success,
                execution_time_ms,
                ">99% UUID correlation",
                {
                    'tested_products': len(product_ids),
                    'correlated_products': correlated_count,
                    'correlation_rate': correlation_rate
                },
                None if success else f"Low correlation rate: {correlation_rate:.1f}%",
                datetime.now()
            )
            
        except Exception as e:
            return IntegrationTestResult(
                'uuid_correlation_validation',
                False,
                (time.time() - start_time) * 1000,
                "Perfect UUID correlation",
                None,
                str(e),
                datetime.now()
            )
    
    def test_search_performance_live(self) -> IntegrationTestResult:
        """Test search performance under concurrent load"""
        start_time = time.time()
        
        try:
            test_queries = [
                "red shirt", "blue dress", "Nike shoes", "casual pants",
                "black jacket", "white sneakers", "formal shirt", "summer dress"
            ]
            
            performance_results = []
            
            def execute_search(query):
                query_start = time.time()
                try:
                    # Simulate search operation (would call actual search API)
                    color = self._extract_color_from_query(query)
                    if color:
                        with self.neo4j_driver.session() as session:
                            result = session.run("""
                                MATCH (p:Product)-[:HAS_COLOR]->(c:Color)
                                WHERE toLower(c.name) = toLower($color)
                                RETURN COUNT(p) as count
                            """, color=color)
                            
                            count = result.single()['count']
                    
                    query_time = (time.time() - query_start) * 1000
                    return {'query': query, 'time_ms': query_time, 'success': True}
                    
                except Exception as e:
                    query_time = (time.time() - query_start) * 1000
                    return {'query': query, 'time_ms': query_time, 'success': False, 'error': str(e)}
            
            # Execute queries concurrently
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(execute_search, query) for query in test_queries]
                performance_results = [future.result() for future in futures]
            
            # Analyze performance
            successful_results = [r for r in performance_results if r['success']]
            response_times = [r['time_ms'] for r in successful_results]
            
            if not successful_results:
                return IntegrationTestResult(
                    'search_performance_validation',
                    False,
                    (time.time() - start_time) * 1000,
                    "Fast concurrent search performance",
                    None,
                    "All search queries failed",
                    datetime.now()
                )
            
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
            success_rate = (len(successful_results) / len(test_queries)) * 100
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            # Success if average response time < 300ms and success rate > 90%
            success = avg_response_time < 300 and success_rate > 90
            
            return IntegrationTestResult(
                'search_performance_validation',
                success,
                execution_time_ms,
                "Avg response time <300ms, success rate >90%",
                {
                    'avg_response_time_ms': avg_response_time,
                    'max_response_time_ms': max_response_time,
                    'success_rate': success_rate,
                    'total_queries': len(test_queries),
                    'successful_queries': len(successful_results)
                },
                None if success else f"Performance below target: {avg_response_time:.1f}ms avg, {success_rate:.1f}% success",
                datetime.now()
            )
            
        except Exception as e:
            return IntegrationTestResult(
                'search_performance_validation',
                False,
                (time.time() - start_time) * 1000,
                "Fast concurrent search performance",
                None,
                str(e),
                datetime.now()
            )
    
    def run_single_integration_test(self, scenario: Dict) -> IntegrationTestResult:
        """Run a single integration test scenario"""
        scenario_name = scenario['name']
        
        if scenario_name == 'color_search_integration':
            # Test with first query from the scenario
            query = scenario['test_queries'][0]
            return self.test_color_search_integration(query)
            
        elif scenario_name == 'brand_search_integration':
            query = scenario['test_queries'][0]
            return self.test_brand_search_integration(query)
            
        elif scenario_name == 'multi_attribute_search':
            query = scenario['test_queries'][0]
            return self.test_multi_attribute_search(query)
            
        elif scenario_name == 'uuid_correlation_validation':
            return self.test_uuid_correlation_live()
            
        elif scenario_name == 'search_performance_validation':
            return self.test_search_performance_live()
        
        else:
            return IntegrationTestResult(
                scenario_name,
                False,
                0,
                "Unknown test scenario",
                None,
                f"Test scenario {scenario_name} not implemented",
                datetime.now()
            )
    
    def run_all_integration_tests(self) -> Dict:
        """Run all integration test scenarios"""
        print("🧪 Running Live Integration Tests")
        print("=" * 50)
        
        test_report = {
            'timestamp': datetime.now().isoformat(),
            'test_results': {},
            'summary': {}
        }
        
        total_tests = len(self.integration_test_scenarios)
        passed_tests = 0
        failed_tests = 0
        
        for scenario in self.integration_test_scenarios:
            print(f"  🔍 Testing: {scenario['name']}")
            
            result = self.run_single_integration_test(scenario)
            test_report['test_results'][scenario['name']] = {
                'success': result.success,
                'response_time_ms': result.response_time_ms,
                'expected': result.expected_result,
                'actual': result.actual_result,
                'error': result.error_message,
                'timestamp': result.timestamp.isoformat() if result.timestamp else None
            }
            
            if result.success:
                passed_tests += 1
                print(f"    ✅ PASSED: {result.response_time_ms:.1f}ms")
            else:
                failed_tests += 1
                print(f"    ❌ FAILED: {result.error_message}")
        
        # Calculate summary
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        test_report['summary'] = {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'success_rate': success_rate,
            'integration_ready': success_rate >= 80
        }
        
        print(f"\n📊 INTEGRATION TEST SUMMARY:")
        print(f"Success Rate: {success_rate:.1f}% ({passed_tests}/{total_tests})")
        
        if test_report['summary']['integration_ready']:
            print("🎉 SYSTEM INTEGRATION: READY")
        else:
            print("⚠️ SYSTEM INTEGRATION: NEEDS ATTENTION")
        
        return test_report
    
    def start_continuous_monitoring(self, interval_minutes: int = 5):
        """Start continuous integration monitoring"""
        print(f"🔄 Starting continuous integration monitoring (every {interval_minutes} minutes)")
        
        self.monitoring_active = True
        
        def monitoring_loop():
            while self.monitoring_active:
                try:
                    # Run a subset of critical tests
                    critical_scenarios = [
                        scenario for scenario in self.integration_test_scenarios 
                        if scenario['name'] in ['color_search_integration', 'uuid_correlation_validation']
                    ]
                    
                    for scenario in critical_scenarios:
                        result = self.run_single_integration_test(scenario)
                        self.test_results.append(result)
                        
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        if result.success:
                            print(f"[{timestamp}] ✅ {scenario['name']}: OK ({result.response_time_ms:.1f}ms)")
                        else:
                            print(f"[{timestamp}] ❌ {scenario['name']}: FAILED - {result.error_message}")
                    
                    # Keep only last 100 results
                    if len(self.test_results) > 100:
                        self.test_results = self.test_results[-100:]
                    
                    time.sleep(interval_minutes * 60)
                    
                except Exception as e:
                    print(f"❌ Monitoring error: {e}")
                    time.sleep(60)  # Wait 1 minute before retrying
        
        self.monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self.monitoring_thread.start()
    
    def stop_continuous_monitoring(self):
        """Stop continuous monitoring"""
        print("⏹️ Stopping continuous integration monitoring")
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
    
    def get_monitoring_summary(self) -> Dict:
        """Get summary of continuous monitoring results"""
        if not self.test_results:
            return {'error': 'No monitoring data available'}
        
        recent_results = self.test_results[-20:]  # Last 20 results
        success_count = len([r for r in recent_results if r.success])
        
        return {
            'monitoring_duration': 'Continuous',
            'recent_tests': len(recent_results),
            'recent_success_rate': (success_count / len(recent_results) * 100) if recent_results else 0,
            'last_test_time': recent_results[-1].timestamp.isoformat() if recent_results else None,
            'system_health': 'Good' if success_count / len(recent_results) > 0.8 else 'Degraded'
        }
    
    def save_test_results(self, report: Dict, filename: str = None):
        """Save integration test results"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"live_integration_test_results_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"💾 Integration test results saved: {filename}")
    
    # Helper methods for attribute extraction
    def _extract_color_from_query(self, query: str) -> Optional[str]:
        """Extract color from search query"""
        colors = ['red', 'blue', 'green', 'black', 'white', 'yellow', 'pink', 'purple', 'orange', 'brown', 'gray', 'grey']
        query_lower = query.lower()
        
        for color in colors:
            if color in query_lower:
                return color
        return None
    
    def _extract_brand_from_query(self, query: str) -> Optional[str]:
        """Extract brand from search query"""
        brands = ['nike', 'adidas', 'puma', 'reebok', 'under armour', 'new balance', 'converse', 'vans']
        query_lower = query.lower()
        
        for brand in brands:
            if brand in query_lower:
                return brand
        return None
    
    def _extract_style_from_query(self, query: str) -> Optional[str]:
        """Extract style from search query"""
        styles = ['casual', 'formal', 'athletic', 'running', 'training', 'outdoor', 'vintage', 'modern']
        query_lower = query.lower()
        
        for style in styles:
            if style in query_lower:
                return style
        return None


def main():
    """Run live integration testing"""
    tester = LiveIntegrationTester()
    
    try:
        tester.connect_databases()
        
        # Run all integration tests
        report = tester.run_all_integration_tests()
        tester.save_test_results(report)
        
        # Optionally start continuous monitoring
        print(f"\n🔄 Start continuous monitoring? (Press Ctrl+C to stop)")
        try:
            tester.start_continuous_monitoring(interval_minutes=2)
            
            # Keep main thread alive
            while True:
                time.sleep(10)
                summary = tester.get_monitoring_summary()
                if summary.get('system_health') == 'Degraded':
                    print(f"⚠️ System health degraded - recent success rate: {summary.get('recent_success_rate', 0):.1f}%")
                
        except KeyboardInterrupt:
            tester.stop_continuous_monitoring()
            print("\n👋 Integration testing stopped")
        
        return report['summary']['integration_ready']
        
    except Exception as e:
        print(f"❌ Live integration testing failed: {e}")
        return False
    
    finally:
        if hasattr(tester, 'neo4j_driver'):
            tester.neo4j_driver.close()


if __name__ == "__main__":
    main()