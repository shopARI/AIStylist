#!/usr/bin/env python3
from config import get_database_config, get_ai_config, get_system_config
"""
UUID Synchronization Validation Script
Validates perfect UUID correlation between Neo4j and Qdrant after re-embedding

IMMEDIATE POST-EMBEDDING EXECUTION
Run this script immediately after Qdrant re-embedding to validate UUID sync
"""

import json
import hashlib
import time
from datetime import datetime
from typing import Dict, List, Set, Tuple
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
import uuid

class UuidSynchronizationValidator:
    """Validates perfect UUID synchronization between Neo4j and Qdrant"""
    
    def __init__(self):
        # Database connections
        self.db_config = get_database_config()
        self.neo4j_url = self.db_config.neo4j_url
        self.neo4j_user = self.db_config.neo4j_user
        self.neo4j_password = self.db_config.neo4j_password
        
        self.qdrant_url = self.db_config.qdrant_url
        self.qdrant_api_key = self.db_config.qdrant_api_key
        self.perfect_collection = "fashion_products_perfect"  # New collection from embedding script
        
        # Validation tracking
        self.validation_results = {
            'timestamp': datetime.now().isoformat(),
            'overall_success': False,
            'count_validation': {},
            'uuid_format_validation': {},
            'correlation_validation': {},
            'payload_validation': {},
            'search_functionality': {},
            'performance_metrics': {},
            'errors': []
        }
        
        # Test data for validation
        self.test_scenarios = [
            {'type': 'random_sampling', 'sample_size': 100},
            {'type': 'systematic_sampling', 'sample_size': 50},
            {'type': 'edge_cases', 'sample_size': 20}
        ]
    
    def validate_uuid_format(self, uuid_string: str) -> bool:
        """Validate UUID format"""
        try:
            uuid_obj = uuid.UUID(uuid_string)
            return str(uuid_obj) == uuid_string
        except (ValueError, TypeError):
            return False
    
    def connect_databases(self) -> bool:
        """Connect to both Neo4j and Qdrant"""
        print("🔌 Connecting to databases...")
        
        try:
            # Neo4j connection
            self.neo4j_driver = GraphDatabase.driver(
                self.neo4j_url,
                auth=(self.neo4j_user, self.neo4j_password)
            )
            
            with self.neo4j_driver.session() as session:
                session.run("RETURN 1")
            
            # Qdrant connection
            self.qdrant_client = QdrantClient(
                url=self.qdrant_url,
                api_key=self.qdrant_api_key
            )
            
            # Test Qdrant and check for perfect collection
            collections = self.qdrant_client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.perfect_collection not in collection_names:
                raise Exception(f"Perfect collection '{self.perfect_collection}' not found. Available: {collection_names}")
            
            print("✅ Connected to both databases")
            print(f"✅ Found target collection: {self.perfect_collection}")
            
            return True
            
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            self.validation_results['errors'].append(f"Connection error: {e}")
            return False
    
    def validate_collection_counts(self) -> bool:
        """Validate that Neo4j and Qdrant have matching product counts"""
        print("📊 Validating collection counts...")
        
        try:
            # Get Neo4j product count
            with self.neo4j_driver.session() as session:
                result = session.run("MATCH (p:Product) RETURN count(p) as count")
                neo4j_count = result.single()['count']
            
            # Get Qdrant vector count
            qdrant_count_result = self.qdrant_client.count(collection_name=self.perfect_collection)
            qdrant_count = qdrant_count_result.count
            
            print(f"  📊 Neo4j products: {neo4j_count:,}")
            print(f"  📊 Qdrant vectors: {qdrant_count:,}")
            
            # Calculate match percentage
            if neo4j_count > 0:
                match_percentage = (min(neo4j_count, qdrant_count) / neo4j_count) * 100
            else:
                match_percentage = 0
            
            count_success = abs(neo4j_count - qdrant_count) <= (neo4j_count * 0.01)  # Allow 1% difference
            
            if count_success:
                print(f"  ✅ Count validation: {match_percentage:.2f}% match (within acceptable range)")
            else:
                print(f"  ❌ Count validation: {match_percentage:.2f}% match (outside acceptable range)")
                self.validation_results['errors'].append(f"Count mismatch: Neo4j={neo4j_count:,}, Qdrant={qdrant_count:,}")
            
            self.validation_results['count_validation'] = {
                'neo4j_count': neo4j_count,
                'qdrant_count': qdrant_count,
                'match_percentage': match_percentage,
                'success': count_success
            }
            
            return count_success
            
        except Exception as e:
            print(f"❌ Error validating counts: {e}")
            self.validation_results['errors'].append(f"Count validation error: {e}")
            return False
    
    def validate_uuid_correlation_sampling(self, scenario: Dict) -> Dict:
        """Validate UUID correlation using different sampling methods"""
        print(f"🎯 UUID correlation test: {scenario['type']} ({scenario['sample_size']} samples)")
        
        try:
            with self.neo4j_driver.session() as session:
                
                if scenario['type'] == 'random_sampling':
                    # Random sampling
                    result = session.run(f"""
                    MATCH (p:Product)
                    WITH p ORDER BY rand()
                    LIMIT {scenario['sample_size']}
                    RETURN p.id as product_id, p.title as title
                    """)
                    
                elif scenario['type'] == 'systematic_sampling':
                    # Systematic sampling (every Nth product)
                    total_result = session.run("MATCH (p:Product) RETURN count(p) as total")
                    total_count = total_result.single()['total']
                    step = max(1, total_count // scenario['sample_size'])
                    
                    result = session.run(f"""
                    MATCH (p:Product)
                    WITH p SKIP {step // 2}
                    WHERE id(p) % {step} = 0
                    LIMIT {scenario['sample_size']}
                    RETURN p.id as product_id, p.title as title
                    """)
                    
                elif scenario['type'] == 'edge_cases':
                    # Edge cases - products with special characters, long titles, etc.
                    result = session.run(f"""
                    MATCH (p:Product)
                    WHERE p.title CONTAINS '"' OR p.title CONTAINS "'" OR length(p.title) > 100
                    LIMIT {scenario['sample_size']}
                    RETURN p.id as product_id, p.title as title
                    """)
                
                # Collect test products
                test_products = []
                for record in result:
                    product_id = record['product_id']
                    title = record['title'] or ''
                    
                    if self.validate_uuid_format(product_id):
                        test_products.append({
                            'id': product_id,
                            'title': title
                        })
                
                print(f"    📋 Testing {len(test_products)} valid UUIDs...")
                
                # Test each product for perfect UUID correlation
                perfect_matches = 0
                payload_matches = 0
                format_errors = 0
                retrieval_errors = 0
                
                for product in test_products:
                    neo4j_uuid = product['id']
                    
                    try:
                        # Attempt to retrieve from Qdrant using Neo4j UUID as point ID
                        retrieved_points = self.qdrant_client.retrieve(
                            collection_name=self.perfect_collection,
                            ids=[neo4j_uuid]
                        )
                        
                        if retrieved_points and len(retrieved_points) == 1:
                            retrieved_point = retrieved_points[0]
                            qdrant_point_id = str(retrieved_point.id)
                            
                            # Check payload for product_id
                            payload = retrieved_point.payload or {}
                            payload_product_id = payload.get('product_id', '')
                            
                            # Triple validation
                            uuid_match = (neo4j_uuid == qdrant_point_id)
                            payload_match = (neo4j_uuid == payload_product_id)
                            
                            if uuid_match and payload_match:
                                perfect_matches += 1
                            elif payload_match:
                                payload_matches += 1
                            
                            # Validate payload structure
                            expected_fields = ['product_id', 'title', 'description', 'price']
                            missing_fields = [field for field in expected_fields if field not in payload]
                            
                            if missing_fields:
                                self.validation_results['errors'].append(
                                    f"Missing payload fields for {neo4j_uuid}: {missing_fields}"
                                )
                        
                        else:
                            retrieval_errors += 1
                            
                    except Exception as e:
                        retrieval_errors += 1
                        print(f"      ⚠️ Retrieval error for {neo4j_uuid}: {e}")
                
                # Calculate success rates
                total_tested = len(test_products)
                perfect_rate = (perfect_matches / total_tested) * 100 if total_tested > 0 else 0
                payload_rate = (payload_matches / total_tested) * 100 if total_tested > 0 else 0
                
                scenario_success = perfect_rate >= 99.0  # 99% threshold for perfect correlation
                
                print(f"    📊 Perfect matches: {perfect_matches}/{total_tested} ({perfect_rate:.1f}%)")
                print(f"    📊 Payload matches: {payload_matches}/{total_tested} ({payload_rate:.1f}%)")
                print(f"    📊 Retrieval errors: {retrieval_errors}/{total_tested}")
                
                if scenario_success:
                    print(f"    ✅ {scenario['type']}: SUCCESS")
                else:
                    print(f"    ❌ {scenario['type']}: FAILED - {perfect_rate:.1f}% < 99%")
                    self.validation_results['errors'].append(
                        f"{scenario['type']} failed: {perfect_rate:.1f}% perfect matches"
                    )
                
                return {
                    'scenario_type': scenario['type'],
                    'total_tested': total_tested,
                    'perfect_matches': perfect_matches,
                    'perfect_rate': perfect_rate,
                    'payload_matches': payload_matches,
                    'payload_rate': payload_rate,
                    'retrieval_errors': retrieval_errors,
                    'success': scenario_success
                }
                
        except Exception as e:
            print(f"❌ Error in {scenario['type']}: {e}")
            self.validation_results['errors'].append(f"{scenario['type']} error: {e}")
            return {
                'scenario_type': scenario['type'],
                'success': False,
                'error': str(e)
            }
    
    def validate_enhanced_payload_structure(self) -> bool:
        """Validate that payloads include enhanced Phase 2 attributes"""
        print("🔍 Validating enhanced payload structure...")
        
        try:
            # Sample vectors to check payload structure
            scroll_result = self.qdrant_client.scroll(
                collection_name=self.perfect_collection,
                limit=50,
                with_payload=True
            )
            
            points = scroll_result[0]
            
            if not points:
                print("  ❌ No vectors found for payload validation")
                self.validation_results['errors'].append("No vectors available for payload validation")
                return False
            
            # Check payload structure
            required_fields = ['product_id', 'title', 'description', 'price']
            enhanced_fields = ['colors', 'brands', 'styles', 'embedding_source', 'created_at']
            
            field_coverage = {}
            enhanced_coverage = {}
            
            for field in required_fields + enhanced_fields:
                field_coverage[field] = 0
            
            products_with_attributes = {
                'colors': 0,
                'brands': 0,
                'styles': 0,
                'all_attributes': 0
            }
            
            for point in points:
                payload = point.payload or {}
                
                # Check field presence
                for field in required_fields + enhanced_fields:
                    if field in payload and payload[field]:
                        field_coverage[field] += 1
                
                # Check for Phase 2 attributes
                colors = payload.get('colors', [])
                brands = payload.get('brands', [])
                styles = payload.get('styles', [])
                
                if colors:
                    products_with_attributes['colors'] += 1
                if brands:
                    products_with_attributes['brands'] += 1
                if styles:
                    products_with_attributes['styles'] += 1
                if colors and brands and styles:
                    products_with_attributes['all_attributes'] += 1
            
            # Calculate coverage percentages
            total_points = len(points)
            
            print("  📊 Required field coverage:")
            for field in required_fields:
                coverage_pct = (field_coverage[field] / total_points) * 100
                status = '✅' if coverage_pct >= 95 else '❌'
                print(f"    {field}: {coverage_pct:.1f}% {status}")
            
            print("  📊 Enhanced field coverage:")
            for field in enhanced_fields:
                coverage_pct = (field_coverage[field] / total_points) * 100
                status = '✅' if coverage_pct >= 50 else '⚠️'  # Lower threshold for enhanced fields
                print(f"    {field}: {coverage_pct:.1f}% {status}")
            
            print("  📊 Phase 2 attribute enrichment:")
            for attr_type, count in products_with_attributes.items():
                coverage_pct = (count / total_points) * 100
                print(f"    Products with {attr_type}: {coverage_pct:.1f}%")
            
            # Validation success criteria
            required_success = all(
                (field_coverage[field] / total_points) >= 0.95 
                for field in required_fields
            )
            
            enhanced_success = (
                field_coverage['colors'] / total_points >= 0.5 and
                field_coverage['brands'] / total_points >= 0.5 and
                field_coverage['styles'] / total_points >= 0.3
            )
            
            payload_success = required_success and enhanced_success
            
            if payload_success:
                print("  ✅ Payload structure validation: SUCCESS")
            else:
                print("  ❌ Payload structure validation: FAILED")
                if not required_success:
                    self.validation_results['errors'].append("Required fields missing from payloads")
                if not enhanced_success:
                    self.validation_results['errors'].append("Enhanced fields missing from payloads")
            
            self.validation_results['payload_validation'] = {
                'total_tested': total_points,
                'field_coverage': field_coverage,
                'attribute_coverage': products_with_attributes,
                'required_success': required_success,
                'enhanced_success': enhanced_success,
                'success': payload_success
            }
            
            return payload_success
            
        except Exception as e:
            print(f"❌ Error validating payload structure: {e}")
            self.validation_results['errors'].append(f"Payload validation error: {e}")
            return False
    
    def test_search_functionality(self) -> bool:
        """Test that search functionality works with perfect UUID correlation"""
        print("🔍 Testing search functionality...")
        
        try:
            # Test 1: Vector search with ID retrieval
            print("  🧪 Test 1: Vector search → product ID retrieval")
            
            # Get a sample vector for similarity search
            scroll_result = self.qdrant_client.scroll(
                collection_name=self.perfect_collection,
                limit=1,
                with_vectors=True,
                with_payload=True
            )
            
            if not scroll_result[0]:
                print("    ❌ No vectors available for search testing")
                return False
            
            sample_point = scroll_result[0][0]
            sample_vector = sample_point.vector
            sample_product_id = sample_point.payload.get('product_id')
            
            # Perform similarity search
            search_results = self.qdrant_client.search(
                collection_name=self.perfect_collection,
                query_vector=sample_vector,
                limit=5
            )
            
            search_success = len(search_results) > 0
            
            if search_success:
                print(f"    ✅ Vector search returned {len(search_results)} results")
                
                # Verify top result matches original product
                if search_results[0].payload.get('product_id') == sample_product_id:
                    print("    ✅ Top result matches original product (perfect correlation)")
                else:
                    print("    ⚠️ Top result doesn't match original product")
                    self.validation_results['errors'].append("Vector search correlation issue")
            else:
                print("    ❌ Vector search failed")
                self.validation_results['errors'].append("Vector search failed")
            
            # Test 2: Direct ID lookup
            print("  🧪 Test 2: Direct product ID lookup")
            
            if sample_product_id:
                try:
                    direct_lookup = self.qdrant_client.retrieve(
                        collection_name=self.perfect_collection,
                        ids=[sample_product_id]
                    )
                    
                    lookup_success = len(direct_lookup) == 1 and str(direct_lookup[0].id) == sample_product_id
                    
                    if lookup_success:
                        print("    ✅ Direct ID lookup successful")
                    else:
                        print("    ❌ Direct ID lookup failed")
                        self.validation_results['errors'].append("Direct ID lookup failed")
                
                except Exception as e:
                    lookup_success = False
                    print(f"    ❌ Direct lookup error: {e}")
                    self.validation_results['errors'].append(f"Direct lookup error: {e}")
            else:
                lookup_success = False
                print("    ❌ No product_id available for lookup test")
            
            # Test 3: Hybrid Neo4j → Qdrant workflow
            print("  🧪 Test 3: Neo4j → Qdrant workflow")
            
            workflow_success = False
            try:
                with self.neo4j_driver.session() as session:
                    # Get a random product from Neo4j
                    result = session.run("""
                    MATCH (p:Product)
                    WHERE p.title IS NOT NULL
                    RETURN p.id as product_id, p.title as title
                    ORDER BY rand()
                    LIMIT 1
                    """)
                    
                    neo4j_product = result.single()
                    if neo4j_product:
                        neo4j_id = neo4j_product['product_id']
                        neo4j_title = neo4j_product['title']
                        
                        # Look up same product in Qdrant using the ID
                        qdrant_lookup = self.qdrant_client.retrieve(
                            collection_name=self.perfect_collection,
                            ids=[neo4j_id]
                        )
                        
                        if qdrant_lookup and len(qdrant_lookup) == 1:
                            qdrant_point = qdrant_lookup[0]
                            qdrant_title = qdrant_point.payload.get('title', '')
                            
                            # Verify title match (basic correlation check)
                            title_match = neo4j_title.strip().lower() == qdrant_title.strip().lower()
                            
                            if title_match:
                                workflow_success = True
                                print("    ✅ Neo4j → Qdrant workflow successful")
                            else:
                                print(f"    ⚠️ Title mismatch: '{neo4j_title}' vs '{qdrant_title}'")
                                self.validation_results['errors'].append("Neo4j-Qdrant title mismatch")
                        else:
                            print("    ❌ Qdrant lookup failed for Neo4j product")
                            self.validation_results['errors'].append("Neo4j-Qdrant workflow failed")
                    else:
                        print("    ❌ No Neo4j product found for workflow test")
            
            except Exception as e:
                print(f"    ❌ Workflow test error: {e}")
                self.validation_results['errors'].append(f"Workflow test error: {e}")
            
            overall_search_success = search_success and lookup_success and workflow_success
            
            self.validation_results['search_functionality'] = {
                'vector_search': search_success,
                'direct_lookup': lookup_success,
                'neo4j_workflow': workflow_success,
                'overall_success': overall_search_success
            }
            
            return overall_search_success
            
        except Exception as e:
            print(f"❌ Error testing search functionality: {e}")
            self.validation_results['errors'].append(f"Search functionality error: {e}")
            return False
    
    def generate_validation_report(self) -> str:
        """Generate comprehensive UUID synchronization validation report"""
        
        # Determine overall success
        correlation_results = self.validation_results.get('correlation_validation', {})
        overall_correlation_success = all(
            result.get('success', False) 
            for result in correlation_results.values() 
            if isinstance(result, dict)
        )
        
        overall_success = (
            self.validation_results.get('count_validation', {}).get('success', False) and
            overall_correlation_success and
            self.validation_results.get('payload_validation', {}).get('success', False) and
            self.validation_results.get('search_functionality', {}).get('overall_success', False) and
            len(self.validation_results.get('errors', [])) == 0
        )
        
        self.validation_results['overall_success'] = overall_success
        
        # Generate report
        report_lines = [
            "# UUID Synchronization Validation Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"## 🎯 Overall Result: {'✅ PERFECT SYNC' if overall_success else '❌ SYNC ISSUES'}",
            "",
            "## Collection Count Validation"
        ]
        
        count_val = self.validation_results.get('count_validation', {})
        if count_val:
            report_lines.extend([
                f"- **Neo4j Products**: {count_val.get('neo4j_count', 0):,}",
                f"- **Qdrant Vectors**: {count_val.get('qdrant_count', 0):,}",
                f"- **Match Rate**: {count_val.get('match_percentage', 0):.2f}%",
                f"- **Status**: {'✅ SUCCESS' if count_val.get('success') else '❌ FAILED'}"
            ])
        
        report_lines.append("\n## UUID Correlation Validation")
        
        correlation_val = self.validation_results.get('correlation_validation', {})
        for scenario_type, results in correlation_val.items():
            if isinstance(results, dict):
                status = '✅' if results.get('success') else '❌'
                perfect_rate = results.get('perfect_rate', 0)
                total = results.get('total_tested', 0)
                report_lines.append(f"- **{scenario_type}**: {perfect_rate:.1f}% ({total} tested) {status}")
        
        report_lines.append("\n## Payload Structure Validation")
        
        payload_val = self.validation_results.get('payload_validation', {})
        if payload_val:
            report_lines.extend([
                f"- **Required Fields**: {'✅' if payload_val.get('required_success') else '❌'}",
                f"- **Enhanced Fields**: {'✅' if payload_val.get('enhanced_success') else '❌'}",
                f"- **Sample Size**: {payload_val.get('total_tested', 0)}"
            ])
            
            field_coverage = payload_val.get('field_coverage', {})
            total = payload_val.get('total_tested', 1)
            for field, count in field_coverage.items():
                coverage_pct = (count / total) * 100
                report_lines.append(f"  - {field}: {coverage_pct:.1f}% coverage")
        
        report_lines.append("\n## Search Functionality Validation")
        
        search_val = self.validation_results.get('search_functionality', {})
        if search_val:
            report_lines.extend([
                f"- **Vector Search**: {'✅' if search_val.get('vector_search') else '❌'}",
                f"- **Direct ID Lookup**: {'✅' if search_val.get('direct_lookup') else '❌'}",
                f"- **Neo4j Workflow**: {'✅' if search_val.get('neo4j_workflow') else '❌'}"
            ])
        
        # Errors section
        errors = self.validation_results.get('errors', [])
        if errors:
            report_lines.extend([
                "\n## ❌ Issues Found",
                ""
            ])
            for error in errors:
                report_lines.append(f"- {error}")
        else:
            report_lines.append("\n## ✅ No Issues Found - Perfect UUID Synchronization!")
        
        # Next steps
        if overall_success:
            report_lines.extend([
                "\n## 🚀 Success - Next Steps",
                "1. ✅ UUID synchronization is perfect - proceed with confidence",
                "2. 🔄 Deploy to production with hybrid Neo4j + Qdrant search",
                "3. 📊 Monitor search performance and user experience",
                "4. 🧪 Run full user acceptance testing"
            ])
        else:
            report_lines.extend([
                "\n## ⚠️ Required Actions",
                "1. ❌ Fix UUID synchronization issues listed above",
                "2. 🔄 Re-run embedding process with corrections",
                "3. ⏸️ Do NOT deploy to production until validation passes",
                "4. 📧 Contact development team for technical review"
            ])
        
        report_lines.extend([
            "",
            "---",
            f"**Validation completed**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Target collection**: {self.perfect_collection}",
            f"**Validator**: UUID Synchronization Validation System"
        ])
        
        return "\n".join(report_lines)
    
    def run_complete_validation(self) -> bool:
        """Run complete UUID synchronization validation"""
        print("🚀 UUID SYNCHRONIZATION VALIDATION")
        print("=" * 60)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Target collection: {self.perfect_collection}")
        print()
        
        try:
            # Connect to databases
            if not self.connect_databases():
                return False
            
            # Run validation steps
            step_results = [
                self.validate_collection_counts(),
                self.validate_enhanced_payload_structure(),
                self.test_search_functionality()
            ]
            
            # Run correlation validation for all scenarios
            correlation_results = {}
            for scenario in self.test_scenarios:
                result = self.validate_uuid_correlation_sampling(scenario)
                correlation_results[scenario['type']] = result
                step_results.append(result.get('success', False))
            
            self.validation_results['correlation_validation'] = correlation_results
            
            # Generate report
            report = self.generate_validation_report()
            
            # Save report
            report_file = f"uuid_sync_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            
            # Save raw results
            results_file = f"uuid_sync_validation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(self.validation_results, f, indent=2)
            
            overall_success = self.validation_results['overall_success']
            
            print()
            print("=" * 60)
            if overall_success:
                print("🎉 UUID SYNCHRONIZATION: ✅ PERFECT!")
                print("🚀 Ready for production deployment!")
            else:
                print("⚠️ UUID SYNCHRONIZATION: ❌ ISSUES FOUND")
                print("🔧 Fix issues before production deployment!")
            
            print(f"📋 Report saved: {report_file}")
            print(f"📊 Raw data: {results_file}")
            print("=" * 60)
            
            return overall_success
            
        except Exception as e:
            print(f"❌ Validation failed with error: {e}")
            self.validation_results['errors'].append(f"Critical validation error: {e}")
            return False
        
        finally:
            if hasattr(self, 'neo4j_driver'):
                self.neo4j_driver.close()

if __name__ == "__main__":
    validator = UuidSynchronizationValidator()
    success = validator.run_complete_validation()
    
    if success:
        print("✅ Perfect UUID synchronization validated - ready for production!")
        exit(0)
    else:
        print("❌ UUID synchronization issues found - fix before production!")
        exit(1)