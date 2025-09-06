#!/usr/bin/env python3
from config import get_database_config, get_ai_config, get_system_config
"""
Production Monitoring Setup
Monitors system health and performance after deployment
"""

import json
import time
import psutil
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict, deque

from neo4j import GraphDatabase
from qdrant_client import QdrantClient


class ProductionMonitor:
    """Monitors production system health and performance"""
    
    def __init__(self, monitoring_duration_hours: int = 24):
        # Database connections
        self.db_config = get_database_config()
        self.neo4j_url = self.db_config.neo4j_url
        self.neo4j_user = self.db_config.neo4j_user
        self.neo4j_password = self.db_config.neo4j_password
        
        self.qdrant_url = self.db_config.qdrant_url
        self.qdrant_api_key = self.db_config.qdrant_api_key
        self.collection_name = self.db_config.collection_name
        
        # Monitoring configuration
        self.monitoring_duration = monitoring_duration_hours
        self.check_interval = 300  # 5 minutes
        self.max_history_points = 1000
        
        # Health thresholds
        self.thresholds = {
            'neo4j_response_time_ms': 1000,      # Max 1 second
            'qdrant_response_time_ms': 500,       # Max 0.5 seconds
            'search_success_rate': 95.0,          # Min 95% success
            'correlation_accuracy': 90.0,         # Min 90% correlation
            'cpu_usage_percent': 80.0,            # Max 80% CPU
            'memory_usage_percent': 85.0,         # Max 85% memory
            'disk_usage_percent': 90.0,           # Max 90% disk
            'error_rate_per_hour': 10             # Max 10 errors per hour
        }
        
        # Monitoring data
        self.metrics_history = {
            'timestamps': deque(maxlen=self.max_history_points),
            'neo4j_response_times': deque(maxlen=self.max_history_points),
            'qdrant_response_times': deque(maxlen=self.max_history_points),
            'search_success_rates': deque(maxlen=self.max_history_points),
            'correlation_accuracies': deque(maxlen=self.max_history_points),
            'cpu_usage': deque(maxlen=self.max_history_points),
            'memory_usage': deque(maxlen=self.max_history_points),
            'disk_usage': deque(maxlen=self.max_history_points),
            'error_counts': deque(maxlen=self.max_history_points)
        }
        
        self.alerts_log = []
        self.errors_log = deque(maxlen=1000)
        
    def connect_databases(self):
        """Connect to monitoring targets"""
        print("🔌 Connecting to databases for monitoring...")
        
        try:
            self.neo4j_driver = GraphDatabase.driver(
                self.neo4j_url,
                auth=(self.neo4j_user, self.neo4j_password)
            )
            
            self.qdrant_client = QdrantClient(
                url=self.qdrant_url,
                api_key=self.qdrant_api_key
            )
            
            print("✅ Connected to monitoring targets")
            
        except Exception as e:
            print(f"❌ Failed to connect to databases: {e}")
            raise
    
    def check_neo4j_health(self) -> Dict:
        """Check Neo4j database health"""
        start_time = time.time()
        
        try:
            with self.neo4j_driver.session() as session:
                # Simple health check query
                result = session.run("RETURN 1 as health_check")
                record = result.single()
                
                if record and record['health_check'] == 1:
                    response_time = (time.time() - start_time) * 1000
                    
                    # Get database stats
                    stats_result = session.run("""
                        CALL apoc.meta.stats() 
                        YIELD nodeCount, relCount
                        RETURN nodeCount, relCount
                    """)
                    
                    stats = stats_result.single()
                    node_count = stats['nodeCount'] if stats else 0
                    rel_count = stats['relCount'] if stats else 0
                    
                    return {
                        'status': 'healthy',
                        'response_time_ms': response_time,
                        'node_count': node_count,
                        'relationship_count': rel_count,
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    return {
                        'status': 'unhealthy',
                        'error': 'Health check query failed',
                        'timestamp': datetime.now().isoformat()
                    }
                    
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def check_qdrant_health(self) -> Dict:
        """Check Qdrant vector database health"""
        start_time = time.time()
        
        try:
            # Check collection info
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            response_time = (time.time() - start_time) * 1000
            
            # Get collection stats
            vector_count = collection_info.points_count
            config = collection_info.config
            
            return {
                'status': 'healthy',
                'response_time_ms': response_time,
                'vector_count': vector_count,
                'collection_config': {
                    'vector_size': config.params.vectors.size,
                    'distance_metric': str(config.params.vectors.distance)
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def check_system_resources(self) -> Dict:
        """Check system resource usage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'status': 'healthy',
                'cpu_usage_percent': cpu_percent,
                'memory_usage_percent': memory.percent,
                'disk_usage_percent': disk.percent,
                'memory_available_gb': memory.available / (1024**3),
                'disk_free_gb': disk.free / (1024**3),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def test_search_functionality(self) -> Dict:
        """Test basic search functionality"""
        test_queries = [
            "red shirt",
            "Nike shoes",
            "casual dress"
        ]
        
        successful_searches = 0
        total_searches = len(test_queries)
        search_times = []
        
        for query in test_queries:
            start_time = time.time()
            
            try:
                # Simulate search (placeholder - would use actual search API)
                search_result = self.qdrant_client.scroll(
                    collection_name=self.collection_name,
                    limit=10,
                    with_payload=True
                )
                
                if search_result[0]:  # Got results
                    successful_searches += 1
                
                search_times.append((time.time() - start_time) * 1000)
                
            except Exception as e:
                self.errors_log.append({
                    'timestamp': datetime.now().isoformat(),
                    'type': 'search_error',
                    'query': query,
                    'error': str(e)
                })
        
        success_rate = (successful_searches / total_searches) * 100
        avg_search_time = sum(search_times) / len(search_times) if search_times else 0
        
        return {
            'status': 'healthy' if success_rate >= self.thresholds['search_success_rate'] else 'degraded',
            'success_rate': success_rate,
            'avg_search_time_ms': avg_search_time,
            'successful_searches': successful_searches,
            'total_searches': total_searches,
            'timestamp': datetime.now().isoformat()
        }
    
    def test_correlation_accuracy(self, sample_size: int = 20) -> Dict:
        """Test Neo4j-Qdrant correlation accuracy"""
        try:
            # Get sample of Qdrant vectors
            scroll_result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                limit=sample_size,
                with_payload=True
            )
            
            vectors = scroll_result[0]
            correlation_matches = 0
            
            for vector in vectors:
                if vector.payload and 'product_id' in vector.payload:
                    product_id = vector.payload['product_id']
                    
                    # Check if product exists in Neo4j
                    with self.neo4j_driver.session() as session:
                        result = session.run("""
                            MATCH (p:Product {id: $product_id})
                            RETURN COUNT(p) as count
                        """, product_id=product_id)
                        
                        record = result.single()
                        if record and record['count'] > 0:
                            correlation_matches += 1
            
            accuracy = (correlation_matches / len(vectors)) * 100 if vectors else 0
            
            return {
                'status': 'healthy' if accuracy >= self.thresholds['correlation_accuracy'] else 'degraded',
                'correlation_accuracy': accuracy,
                'matched_correlations': correlation_matches,
                'tested_vectors': len(vectors),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def collect_metrics(self) -> Dict:
        """Collect all monitoring metrics"""
        timestamp = datetime.now()
        
        print(f"📊 Collecting metrics at {timestamp.strftime('%H:%M:%S')}")
        
        # Collect all health checks
        neo4j_health = self.check_neo4j_health()
        qdrant_health = self.check_qdrant_health()
        system_health = self.check_system_resources()
        search_health = self.test_search_functionality()
        correlation_health = self.test_correlation_accuracy()
        
        # Store metrics
        self.metrics_history['timestamps'].append(timestamp)
        self.metrics_history['neo4j_response_times'].append(
            neo4j_health.get('response_time_ms', 0)
        )
        self.metrics_history['qdrant_response_times'].append(
            qdrant_health.get('response_time_ms', 0)
        )
        self.metrics_history['search_success_rates'].append(
            search_health.get('success_rate', 0)
        )
        self.metrics_history['correlation_accuracies'].append(
            correlation_health.get('correlation_accuracy', 0)
        )
        self.metrics_history['cpu_usage'].append(
            system_health.get('cpu_usage_percent', 0)
        )
        self.metrics_history['memory_usage'].append(
            system_health.get('memory_usage_percent', 0)
        )
        self.metrics_history['disk_usage'].append(
            system_health.get('disk_usage_percent', 0)
        )
        self.metrics_history['error_counts'].append(len(self.errors_log))
        
        # Check for alerts
        self.check_alerts(timestamp, {
            'neo4j': neo4j_health,
            'qdrant': qdrant_health,
            'system': system_health,
            'search': search_health,
            'correlation': correlation_health
        })
        
        return {
            'timestamp': timestamp.isoformat(),
            'neo4j_health': neo4j_health,
            'qdrant_health': qdrant_health,
            'system_health': system_health,
            'search_health': search_health,
            'correlation_health': correlation_health
        }
    
    def check_alerts(self, timestamp: datetime, health_data: Dict):
        """Check for alert conditions"""
        alerts = []
        
        # Neo4j response time
        neo4j_time = health_data['neo4j'].get('response_time_ms', 0)
        if neo4j_time > self.thresholds['neo4j_response_time_ms']:
            alerts.append({
                'type': 'neo4j_slow_response',
                'severity': 'warning',
                'message': f"Neo4j response time: {neo4j_time:.1f}ms (threshold: {self.thresholds['neo4j_response_time_ms']}ms)",
                'timestamp': timestamp.isoformat()
            })
        
        # Qdrant response time
        qdrant_time = health_data['qdrant'].get('response_time_ms', 0)
        if qdrant_time > self.thresholds['qdrant_response_time_ms']:
            alerts.append({
                'type': 'qdrant_slow_response',
                'severity': 'warning',
                'message': f"Qdrant response time: {qdrant_time:.1f}ms (threshold: {self.thresholds['qdrant_response_time_ms']}ms)",
                'timestamp': timestamp.isoformat()
            })
        
        # Search success rate
        search_success = health_data['search'].get('success_rate', 100)
        if search_success < self.thresholds['search_success_rate']:
            alerts.append({
                'type': 'search_degradation',
                'severity': 'critical',
                'message': f"Search success rate: {search_success:.1f}% (threshold: {self.thresholds['search_success_rate']}%)",
                'timestamp': timestamp.isoformat()
            })
        
        # Correlation accuracy
        correlation_accuracy = health_data['correlation'].get('correlation_accuracy', 100)
        if correlation_accuracy < self.thresholds['correlation_accuracy']:
            alerts.append({
                'type': 'correlation_degradation',
                'severity': 'critical',
                'message': f"Correlation accuracy: {correlation_accuracy:.1f}% (threshold: {self.thresholds['correlation_accuracy']}%)",
                'timestamp': timestamp.isoformat()
            })
        
        # System resources
        cpu_usage = health_data['system'].get('cpu_usage_percent', 0)
        if cpu_usage > self.thresholds['cpu_usage_percent']:
            alerts.append({
                'type': 'high_cpu_usage',
                'severity': 'warning',
                'message': f"CPU usage: {cpu_usage:.1f}% (threshold: {self.thresholds['cpu_usage_percent']}%)",
                'timestamp': timestamp.isoformat()
            })
        
        memory_usage = health_data['system'].get('memory_usage_percent', 0)
        if memory_usage > self.thresholds['memory_usage_percent']:
            alerts.append({
                'type': 'high_memory_usage',
                'severity': 'warning',
                'message': f"Memory usage: {memory_usage:.1f}% (threshold: {self.thresholds['memory_usage_percent']}%)",
                'timestamp': timestamp.isoformat()
            })
        
        disk_usage = health_data['system'].get('disk_usage_percent', 0)
        if disk_usage > self.thresholds['disk_usage_percent']:
            alerts.append({
                'type': 'high_disk_usage',
                'severity': 'critical',
                'message': f"Disk usage: {disk_usage:.1f}% (threshold: {self.thresholds['disk_usage_percent']}%)",
                'timestamp': timestamp.isoformat()
            })
        
        # Log alerts
        for alert in alerts:
            self.alerts_log.append(alert)
            severity_icon = "🚨" if alert['severity'] == 'critical' else "⚠️"
            print(f"{severity_icon} ALERT: {alert['message']}")
    
    def generate_monitoring_report(self) -> Dict:
        """Generate comprehensive monitoring report"""
        if not self.metrics_history['timestamps']:
            return {'error': 'No monitoring data collected'}
        
        # Calculate averages
        avg_neo4j_time = sum(self.metrics_history['neo4j_response_times']) / len(self.metrics_history['neo4j_response_times'])
        avg_qdrant_time = sum(self.metrics_history['qdrant_response_times']) / len(self.metrics_history['qdrant_response_times'])
        avg_search_success = sum(self.metrics_history['search_success_rates']) / len(self.metrics_history['search_success_rates'])
        avg_correlation = sum(self.metrics_history['correlation_accuracies']) / len(self.metrics_history['correlation_accuracies'])
        avg_cpu = sum(self.metrics_history['cpu_usage']) / len(self.metrics_history['cpu_usage'])
        avg_memory = sum(self.metrics_history['memory_usage']) / len(self.metrics_history['memory_usage'])
        avg_disk = sum(self.metrics_history['disk_usage']) / len(self.metrics_history['disk_usage'])
        
        # Count alerts by severity
        critical_alerts = len([a for a in self.alerts_log if a['severity'] == 'critical'])
        warning_alerts = len([a for a in self.alerts_log if a['severity'] == 'warning'])
        
        # Overall health score (0-100)
        health_factors = [
            100 if avg_neo4j_time <= self.thresholds['neo4j_response_time_ms'] else 80,
            100 if avg_qdrant_time <= self.thresholds['qdrant_response_time_ms'] else 80,
            min(100, avg_search_success),
            min(100, avg_correlation),
            100 if avg_cpu <= self.thresholds['cpu_usage_percent'] else 70,
            100 if avg_memory <= self.thresholds['memory_usage_percent'] else 70,
            100 if avg_disk <= self.thresholds['disk_usage_percent'] else 60
        ]
        
        overall_health_score = sum(health_factors) / len(health_factors)
        
        # Determine overall status
        if overall_health_score >= 95:
            overall_status = "excellent"
        elif overall_health_score >= 85:
            overall_status = "good"
        elif overall_health_score >= 70:
            overall_status = "degraded"
        else:
            overall_status = "poor"
        
        report = {
            'monitoring_period': {
                'start_time': self.metrics_history['timestamps'][0].isoformat(),
                'end_time': self.metrics_history['timestamps'][-1].isoformat(),
                'duration_hours': (self.metrics_history['timestamps'][-1] - self.metrics_history['timestamps'][0]).total_seconds() / 3600,
                'data_points_collected': len(self.metrics_history['timestamps'])
            },
            'overall_health': {
                'status': overall_status,
                'score': overall_health_score,
                'critical_alerts': critical_alerts,
                'warning_alerts': warning_alerts
            },
            'performance_averages': {
                'neo4j_response_time_ms': avg_neo4j_time,
                'qdrant_response_time_ms': avg_qdrant_time,
                'search_success_rate': avg_search_success,
                'correlation_accuracy': avg_correlation
            },
            'resource_averages': {
                'cpu_usage_percent': avg_cpu,
                'memory_usage_percent': avg_memory,
                'disk_usage_percent': avg_disk
            },
            'thresholds': self.thresholds.copy(),
            'alerts_summary': {
                'total_alerts': len(self.alerts_log),
                'critical_alerts': critical_alerts,
                'warning_alerts': warning_alerts,
                'recent_alerts': self.alerts_log[-5:] if self.alerts_log else []
            },
            'recommendations': self.generate_recommendations(overall_health_score, health_factors)
        }
        
        return report
    
    def generate_recommendations(self, health_score: float, health_factors: List[float]) -> List[str]:
        """Generate actionable recommendations based on monitoring data"""
        recommendations = []
        
        if health_score < 85:
            recommendations.append("System health is degraded - immediate attention required")
        
        if len(self.alerts_log) > 0:
            recommendations.append(f"Address {len(self.alerts_log)} active alerts")
        
        # Performance recommendations
        avg_neo4j_time = sum(self.metrics_history['neo4j_response_times']) / len(self.metrics_history['neo4j_response_times'])
        if avg_neo4j_time > self.thresholds['neo4j_response_time_ms']:
            recommendations.append("Consider optimizing Neo4j queries or scaling database")
        
        avg_qdrant_time = sum(self.metrics_history['qdrant_response_times']) / len(self.metrics_history['qdrant_response_times'])
        if avg_qdrant_time > self.thresholds['qdrant_response_time_ms']:
            recommendations.append("Consider optimizing Qdrant configuration or scaling vector database")
        
        # Resource recommendations
        avg_cpu = sum(self.metrics_history['cpu_usage']) / len(self.metrics_history['cpu_usage'])
        if avg_cpu > self.thresholds['cpu_usage_percent']:
            recommendations.append("CPU usage is high - consider scaling compute resources")
        
        avg_memory = sum(self.metrics_history['memory_usage']) / len(self.metrics_history['memory_usage'])
        if avg_memory > self.thresholds['memory_usage_percent']:
            recommendations.append("Memory usage is high - consider increasing RAM or optimizing memory usage")
        
        avg_disk = sum(self.metrics_history['disk_usage']) / len(self.metrics_history['disk_usage'])
        if avg_disk > self.thresholds['disk_usage_percent']:
            recommendations.append("Disk usage is critical - free up space or expand storage")
        
        if not recommendations:
            recommendations.append("System is operating within normal parameters")
        
        return recommendations
    
    def run_monitoring(self, save_interval_minutes: int = 60):
        """Run continuous monitoring"""
        print(f"🚀 Starting Production Monitoring")
        print(f"Duration: {self.monitoring_duration} hours")
        print(f"Check interval: {self.check_interval} seconds")
        print("=" * 50)
        
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=self.monitoring_duration)
        last_save_time = start_time
        
        try:
            while datetime.now() < end_time:
                # Collect metrics
                metrics = self.collect_metrics()
                
                # Save periodic reports
                if (datetime.now() - last_save_time).total_seconds() >= save_interval_minutes * 60:
                    self.save_monitoring_report()
                    last_save_time = datetime.now()
                
                # Sleep until next check
                time.sleep(self.check_interval)
            
            # Final report
            final_report = self.generate_monitoring_report()
            self.save_monitoring_report(final_report, "final_monitoring_report.json")
            
            print(f"\n🎉 Monitoring completed successfully")
            print(f"Overall health score: {final_report['overall_health']['score']:.1f}/100")
            print(f"Status: {final_report['overall_health']['status'].upper()}")
            
            return final_report
            
        except KeyboardInterrupt:
            print(f"\n⏹️ Monitoring stopped by user")
            report = self.generate_monitoring_report()
            self.save_monitoring_report(report, "interrupted_monitoring_report.json")
            return report
        
        except Exception as e:
            print(f"❌ Monitoring error: {e}")
            return None
        
        finally:
            if hasattr(self, 'neo4j_driver'):
                self.neo4j_driver.close()
    
    def save_monitoring_report(self, report: Dict = None, filename: str = None):
        """Save monitoring report to file"""
        if not report:
            report = self.generate_monitoring_report()
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"monitoring_report_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"💾 Monitoring report saved: {filename}")


def main():
    """Run production monitoring"""
    # Default to 1 hour for testing, 24 hours for production
    monitor = ProductionMonitor(monitoring_duration_hours=1)
    
    try:
        monitor.connect_databases()
        report = monitor.run_monitoring()
        
        if report:
            print(f"\n📊 MONITORING SUMMARY:")
            print(f"Health Score: {report['overall_health']['score']:.1f}/100")
            print(f"Status: {report['overall_health']['status'].upper()}")
            print(f"Alerts: {report['alerts_summary']['total_alerts']}")
            
            if report['recommendations']:
                print(f"\n💡 RECOMMENDATIONS:")
                for i, rec in enumerate(report['recommendations'], 1):
                    print(f"{i}. {rec}")
        
        return True
        
    except Exception as e:
        print(f"❌ Monitoring setup failed: {e}")
        return False


if __name__ == "__main__":
    main()