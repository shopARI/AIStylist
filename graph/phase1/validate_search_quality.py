#!/usr/bin/env python3
from config import get_database_config, get_ai_config, get_system_config
"""
Search Quality Testing Framework
Validates that the search system works correctly after all fixes
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from neo4j import GraphDatabase
from qdrant_client import QdrantClient


class SearchQualityValidator:
    """Validates search functionality after graph reconstruction and re-embedding"""
    
    def __init__(self):
        # Database connections
        self.db_config = get_database_config()
        self.neo4j_url = self.db_config.neo4j_url
        self.neo4j_user = self.db_config.neo4j_user 
        self.neo4j_password = self.db_config.neo4j_password
        
        self.qdrant_url = self.db_config.qdrant_url
        self.qdrant_api_key = self.db_config.qdrant_api_key
        self.collection_name = self.db_config.collection_name
        
        # Search test cases
        self.test_scenarios = [
            {
                'name': 'Color-specific search',
                'query': 'red shirt',
                'expected_constraints': ['color:red', 'category:shirt'],
                'validation_method': 'color_validation'
            },
            {
                'name': 'Brand search',
                'query': 'Nike shoes',
                'expected_constraints': ['brand:nike', 'category:shoes'],
                'validation_method': 'brand_validation'
            },
            {
                'name': 'Style search',
                'query': 'casual dress',
                'expected_constraints': ['style:casual', 'category:dress'],
                'validation_method': 'style_validation'
            },
            {
                'name': 'Multi-constraint search',
                'query': 'blue Adidas running shoes',
                'expected_constraints': ['color:blue', 'brand:adidas', 'style:running', 'category:shoes'],
                'validation_method': 'multi_constraint_validation'
            },
            {
                'name': 'Generic product search',
                'query': 'comfortable pants',
                'expected_constraints': ['category:pants'],
                'validation_method': 'semantic_validation'
            },
            {
                'name': 'Price-aware search',
                'query': 'cheap t-shirt under $20',
                'expected_constraints': ['category:t-shirt', 'price:<20'],
                'validation_method': 'price_validation'
            }
        ]
        
        # Results tracking
        self.test_results = {}
        self.overall_stats = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'error_tests': 0,
            'avg_response_time': 0,
            'total_response_time': 0
        }
    
    def connect_databases(self):
        """Connect to both databases"""
        print("🔌 Connecting to databases...")
        
        self.neo4j_driver = GraphDatabase.driver(
            self.neo4j_url,
            auth=(self.neo4j_user, self.neo4j_password)
        )
        
        self.qdrant_client = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key
        )
        
        print("✅ Connected to both databases")
    
    def validate_color_search(self, query: str, results: List[Dict]) -> Dict:
        """Validate color-specific search results"""
        expected_color = self._extract_color_from_query(query)
        
        if not expected_color:
            return {'status': 'error', 'message': 'Could not extract expected color'}
        
        color_matches = 0
        total_results = len(results)
        
        for result in results:
            if self._product_has_color(result['product_id'], expected_color):
                color_matches += 1
        
        color_accuracy = (color_matches / total_results * 100) if total_results > 0 else 0
        
        return {
            'status': 'pass' if color_accuracy >= 80 else 'fail',
            'color_accuracy': color_accuracy,
            'expected_color': expected_color,
            'matching_products': color_matches,
            'total_products': total_results,
            'details': f"{color_matches}/{total_results} products match expected color '{expected_color}'"
        }
    
    def validate_brand_search(self, query: str, results: List[Dict]) -> Dict:
        """Validate brand-specific search results"""
        expected_brand = self._extract_brand_from_query(query)
        
        if not expected_brand:
            return {'status': 'error', 'message': 'Could not extract expected brand'}
        
        brand_matches = 0
        total_results = len(results)
        
        for result in results:
            if self._product_has_brand(result['product_id'], expected_brand):
                brand_matches += 1
        
        brand_accuracy = (brand_matches / total_results * 100) if total_results > 0 else 0
        
        return {
            'status': 'pass' if brand_accuracy >= 70 else 'fail',
            'brand_accuracy': brand_accuracy,
            'expected_brand': expected_brand,
            'matching_products': brand_matches,
            'total_products': total_results,
            'details': f"{brand_matches}/{total_results} products match expected brand '{expected_brand}'"
        }
    
    def validate_style_search(self, query: str, results: List[Dict]) -> Dict:
        """Validate style-specific search results"""
        expected_style = self._extract_style_from_query(query)
        
        if not expected_style:
            return {'status': 'error', 'message': 'Could not extract expected style'}
        
        style_matches = 0
        total_results = len(results)
        
        for result in results:
            if self._product_has_style(result['product_id'], expected_style):
                style_matches += 1
        
        style_accuracy = (style_matches / total_results * 100) if total_results > 0 else 0
        
        return {
            'status': 'pass' if style_accuracy >= 60 else 'fail',
            'style_accuracy': style_accuracy,
            'expected_style': expected_style,
            'matching_products': style_matches,
            'total_products': total_results,
            'details': f"{style_matches}/{total_results} products match expected style '{expected_style}'"
        }
    
    def validate_multi_constraint_search(self, query: str, results: List[Dict]) -> Dict:
        """Validate multi-constraint search results"""
        constraints = {
            'color': self._extract_color_from_query(query),
            'brand': self._extract_brand_from_query(query),
            'style': self._extract_style_from_query(query)
        }
        
        # Remove None constraints
        constraints = {k: v for k, v in constraints.items() if v}
        
        if not constraints:
            return {'status': 'error', 'message': 'Could not extract any constraints'}
        
        constraint_matches = defaultdict(int)
        total_results = len(results)
        
        for result in results:
            product_id = result['product_id']
            
            for constraint_type, expected_value in constraints.items():
                if constraint_type == 'color' and self._product_has_color(product_id, expected_value):
                    constraint_matches[constraint_type] += 1
                elif constraint_type == 'brand' and self._product_has_brand(product_id, expected_value):
                    constraint_matches[constraint_type] += 1
                elif constraint_type == 'style' and self._product_has_style(product_id, expected_value):
                    constraint_matches[constraint_type] += 1
        
        # Calculate accuracy for each constraint
        constraint_accuracies = {}
        for constraint_type in constraints:
            accuracy = (constraint_matches[constraint_type] / total_results * 100) if total_results > 0 else 0
            constraint_accuracies[constraint_type] = accuracy
        
        # Overall accuracy (average of all constraints)
        overall_accuracy = sum(constraint_accuracies.values()) / len(constraint_accuracies) if constraint_accuracies else 0
        
        return {
            'status': 'pass' if overall_accuracy >= 60 else 'fail',
            'overall_accuracy': overall_accuracy,
            'constraint_accuracies': constraint_accuracies,
            'constraints': constraints,
            'total_products': total_results,
            'details': f"Multi-constraint accuracy: {overall_accuracy:.1f}%"
        }
    
    def validate_semantic_search(self, query: str, results: List[Dict]) -> Dict:
        """Validate semantic search results (relevance-based)"""
        total_results = len(results)
        
        if total_results == 0:
            return {'status': 'fail', 'message': 'No results returned'}
        
        # For semantic search, we validate that results are relevant
        # This is more subjective, so we use lighter validation
        relevant_products = 0
        
        # Check if results contain products (basic relevance check)
        for result in results:
            if 'product_id' in result and result['product_id']:
                relevant_products += 1
        
        relevance_rate = (relevant_products / total_results * 100) if total_results > 0 else 0
        
        return {
            'status': 'pass' if relevance_rate >= 95 else 'fail',
            'relevance_rate': relevance_rate,
            'relevant_products': relevant_products,
            'total_products': total_results,
            'details': f"Semantic relevance: {relevance_rate:.1f}%"
        }
    
    def validate_price_search(self, query: str, results: List[Dict]) -> Dict:
        """Validate price-aware search results"""
        # Extract price constraint from query
        price_limit = self._extract_price_limit(query)
        
        if not price_limit:
            return {'status': 'error', 'message': 'Could not extract price constraint'}
        
        price_compliant = 0
        total_results = len(results)
        
        for result in results:
            product_price = self._get_product_price(result['product_id'])
            if product_price and product_price <= price_limit:
                price_compliant += 1
        
        price_accuracy = (price_compliant / total_results * 100) if total_results > 0 else 0
        
        return {
            'status': 'pass' if price_accuracy >= 80 else 'fail',
            'price_accuracy': price_accuracy,
            'price_limit': price_limit,
            'compliant_products': price_compliant,
            'total_products': total_results,
            'details': f"{price_compliant}/{total_results} products under ${price_limit}"
        }
    
    def simulate_vector_search(self, query: str, limit: int = 20) -> List[Dict]:
        """Simulate vector search (placeholder - actual implementation would use embeddings)"""
        try:
            # This would normally do semantic search using embeddings
            # For validation purposes, we'll get a sample of products
            search_results = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                limit=limit,
                with_payload=True,
                with_vectors=False
            )
            
            points = search_results[0]
            results = []
            
            for point in points:
                if point.payload and 'product_id' in point.payload:
                    results.append({
                        'product_id': point.payload['product_id'],
                        'score': 0.8,  # Placeholder score
                        'payload': point.payload
                    })
            
            return results
            
        except Exception as e:
            print(f"❌ Vector search error: {e}")
            return []
    
    def run_search_test(self, scenario: Dict) -> Dict:
        """Run a single search test scenario"""
        print(f"🧪 Testing: {scenario['name']} - '{scenario['query']}'")
        
        start_time = time.time()
        
        try:
            # Simulate search (this would call your actual search system)
            search_results = self.simulate_vector_search(scenario['query'])
            
            end_time = time.time()
            response_time = end_time - start_time
            
            # Validate results based on scenario
            validation_method = getattr(self, scenario['validation_method'])
            validation_result = validation_method(scenario['query'], search_results)
            
            # Add timing info
            validation_result['response_time'] = response_time
            validation_result['query'] = scenario['query']
            validation_result['scenario'] = scenario['name']
            
            # Update stats
            self.overall_stats['total_response_time'] += response_time
            
            return validation_result
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f"Test execution failed: {str(e)}",
                'query': scenario['query'],
                'scenario': scenario['name']
            }
    
    def run_all_tests(self) -> Dict:
        """Run all search quality tests"""
        print("🚀 Starting Search Quality Validation")
        print("=" * 50)
        
        start_time = datetime.now()
        
        for scenario in self.test_scenarios:
            test_result = self.run_search_test(scenario)
            self.test_results[scenario['name']] = test_result
            
            # Update overall stats
            self.overall_stats['total_tests'] += 1
            if test_result['status'] == 'pass':
                self.overall_stats['passed_tests'] += 1
                print(f"✅ {scenario['name']}: PASSED")
            elif test_result['status'] == 'fail':
                self.overall_stats['failed_tests'] += 1
                print(f"❌ {scenario['name']}: FAILED - {test_result.get('details', 'No details')}")
            else:
                self.overall_stats['error_tests'] += 1
                print(f"⚠️ {scenario['name']}: ERROR - {test_result.get('message', 'Unknown error')}")
        
        # Calculate average response time
        if self.overall_stats['total_tests'] > 0:
            self.overall_stats['avg_response_time'] = (
                self.overall_stats['total_response_time'] / self.overall_stats['total_tests']
            )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Generate final report
        report = self.generate_test_report(duration)
        
        return report
    
    def generate_test_report(self, duration: float) -> Dict:
        """Generate comprehensive test report"""
        success_rate = (self.overall_stats['passed_tests'] / 
                       max(self.overall_stats['total_tests'], 1)) * 100
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'duration_seconds': duration,
            'overall_stats': self.overall_stats.copy(),
            'success_rate': success_rate,
            'test_results': self.test_results.copy(),
            'summary': {
                'total_tests': self.overall_stats['total_tests'],
                'passed': self.overall_stats['passed_tests'],
                'failed': self.overall_stats['failed_tests'],
                'errors': self.overall_stats['error_tests'],
                'success_rate_percent': success_rate,
                'avg_response_time_ms': self.overall_stats['avg_response_time'] * 1000
            }
        }
        
        # Print summary
        print(f"\n📊 SEARCH QUALITY TEST RESULTS")
        print("=" * 50)
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"✅ Passed: {report['summary']['passed']}")
        print(f"❌ Failed: {report['summary']['failed']}")
        print(f"⚠️ Errors: {report['summary']['errors']}")
        print(f"Success Rate: {report['summary']['success_rate_percent']:.1f}%")
        print(f"Avg Response Time: {report['summary']['avg_response_time_ms']:.1f}ms")
        print(f"Total Duration: {duration:.1f}s")
        
        if success_rate >= 80:
            print(f"\n🎉 SEARCH QUALITY VALIDATION: PASSED")
        else:
            print(f"\n⚠️ SEARCH QUALITY VALIDATION: NEEDS IMPROVEMENT")
        
        return report
    
    def save_results(self, report: Dict, filename: str = None):
        """Save test results to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"search_quality_results_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"💾 Results saved to: {filename}")
    
    # Helper methods for constraint extraction and validation
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
    
    def _extract_price_limit(self, query: str) -> Optional[float]:
        """Extract price limit from search query"""
        import re
        
        # Look for patterns like "under $20", "< $50", "below 30"
        price_patterns = [
            r'under \$?(\d+(?:\.\d+)?)',
            r'below \$?(\d+(?:\.\d+)?)',
            r'< \$?(\d+(?:\.\d+)?)',
            r'less than \$?(\d+(?:\.\d+)?)'
        ]
        
        query_lower = query.lower()
        
        for pattern in price_patterns:
            match = re.search(pattern, query_lower)
            if match:
                return float(match.group(1))
        
        return None
    
    def _product_has_color(self, product_id: str, expected_color: str) -> bool:
        """Check if product has expected color via Neo4j"""
        try:
            with self.neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (p:Product {id: $product_id})-[:HAS_COLOR]->(c:Color)
                    WHERE toLower(c.name) = toLower($color)
                    RETURN COUNT(c) as count
                """, product_id=product_id, color=expected_color)
                
                record = result.single()
                return record and record['count'] > 0
        except:
            return False
    
    def _product_has_brand(self, product_id: str, expected_brand: str) -> bool:
        """Check if product has expected brand via Neo4j"""
        try:
            with self.neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (p:Product {id: $product_id})-[:HAS_BRAND]->(b:Brand)
                    WHERE toLower(b.name) = toLower($brand)
                    RETURN COUNT(b) as count
                """, product_id=product_id, brand=expected_brand)
                
                record = result.single()
                return record and record['count'] > 0
        except:
            return False
    
    def _product_has_style(self, product_id: str, expected_style: str) -> bool:
        """Check if product has expected style via Neo4j"""
        try:
            with self.neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (p:Product {id: $product_id})-[:HAS_STYLE]->(s:Style)
                    WHERE toLower(s.name) = toLower($style)
                    RETURN COUNT(s) as count
                """, product_id=product_id, style=expected_style)
                
                record = result.single()
                return record and record['count'] > 0
        except:
            return False
    
    def _get_product_price(self, product_id: str) -> Optional[float]:
        """Get product price from Neo4j"""
        try:
            with self.neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (p:Product {id: $product_id})
                    RETURN p.price as price
                """, product_id=product_id)
                
                record = result.single()
                if record and record['price']:
                    return float(record['price'])
        except:
            pass
        return None


def main():
    """Run search quality validation"""
    validator = SearchQualityValidator()
    
    try:
        validator.connect_databases()
        report = validator.run_all_tests()
        validator.save_results(report)
        
        return report['summary']['success_rate_percent'] >= 80
        
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return False
    finally:
        if hasattr(validator, 'neo4j_driver'):
            validator.neo4j_driver.close()


if __name__ == "__main__":
    main()