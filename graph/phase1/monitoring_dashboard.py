#!/usr/bin/env python3
from config import get_database_config, get_ai_config, get_system_config
"""
Monitoring Dashboard Generator
Creates visual dashboards for system health metrics and deployment status
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

from neo4j import GraphDatabase
from qdrant_client import QdrantClient


class MonitoringDashboardGenerator:
    """Generates visual monitoring dashboards for system health and performance"""
    
    def __init__(self):
        # Database connections
        self.db_config = get_database_config()
        self.neo4j_url = self.db_config.neo4j_url
        self.neo4j_user = self.db_config.neo4j_user
        self.neo4j_password = self.db_config.neo4j_password
        
        self.qdrant_url = self.db_config.qdrant_url
        self.qdrant_api_key = self.db_config.qdrant_api_key
        self.collection_name = self.db_config.collection_name
        
        # Dashboard configuration
        self.dashboard_path = Path("./monitoring_dashboards")
        self.dashboard_path.mkdir(exist_ok=True)
        
        # Colors and styling for HTML dashboards
        self.colors = {
            'success': '#28a745',
            'warning': '#ffc107', 
            'error': '#dc3545',
            'info': '#17a2b8',
            'primary': '#007bff',
            'dark': '#343a40',
            'light': '#f8f9fa'
        }
        
    def connect_databases(self):
        """Connect to databases for monitoring data collection"""
        print("🔌 Connecting to databases for dashboard generation...")
        
        self.neo4j_driver = GraphDatabase.driver(
            self.neo4j_url,
            auth=(self.neo4j_user, self.neo4j_password)
        )
        
        self.qdrant_client = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key
        )
        
        print("✅ Connected to databases")
    
    def collect_system_metrics(self) -> Dict:
        """Collect current system metrics for dashboard"""
        print("📊 Collecting system metrics...")
        
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'neo4j_metrics': {},
            'qdrant_metrics': {},
            'system_metrics': {},
            'correlation_metrics': {},
            'performance_metrics': {}
        }
        
        try:
            # Neo4j metrics
            with self.neo4j_driver.session() as session:
                # Node counts
                node_result = session.run("""
                    CALL apoc.meta.stats() 
                    YIELD labels
                    RETURN labels
                """)
                labels = node_result.single()['labels'] if node_result.single() else {}
                
                # Relationship counts  
                rel_result = session.run("""
                    CALL apoc.meta.stats()
                    YIELD relTypesCount
                    RETURN relTypesCount
                """)
                rel_types = rel_result.single()['relTypesCount'] if rel_result.single() else {}
                
                # Query performance sample
                start_time = time.time()
                perf_result = session.run("MATCH (p:Product) RETURN COUNT(p) as count")
                query_time = (time.time() - start_time) * 1000
                product_count = perf_result.single()['count']
                
                metrics['neo4j_metrics'] = {
                    'node_counts': labels,
                    'relationship_counts': rel_types,
                    'total_products': product_count,
                    'sample_query_time_ms': query_time,
                    'connection_status': 'connected'
                }
                
        except Exception as e:
            metrics['neo4j_metrics'] = {
                'connection_status': 'error',
                'error': str(e)
            }
        
        try:
            # Qdrant metrics
            start_time = time.time()
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            query_time = (time.time() - start_time) * 1000
            
            # Sample vector search performance
            sample_vector = [0.1] * 1536  # Dummy vector
            start_time = time.time()
            search_result = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=sample_vector,
                limit=5
            )
            search_time = (time.time() - start_time) * 1000
            
            metrics['qdrant_metrics'] = {
                'vector_count': collection_info.points_count,
                'collection_info_time_ms': query_time,
                'sample_search_time_ms': search_time,
                'search_results_returned': len(search_result),
                'connection_status': 'connected'
            }
            
        except Exception as e:
            metrics['qdrant_metrics'] = {
                'connection_status': 'error',
                'error': str(e)
            }
        
        try:
            # System resource metrics
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            metrics['system_metrics'] = {
                'cpu_usage_percent': cpu_percent,
                'memory_usage_percent': memory.percent,
                'disk_usage_percent': disk.percent,
                'available_memory_gb': memory.available / (1024**3),
                'available_disk_gb': disk.free / (1024**3)
            }
            
        except ImportError:
            metrics['system_metrics'] = {
                'error': 'psutil not available'
            }
        
        try:
            # UUID correlation sample check
            start_time = time.time()
            
            # Get sample products from Neo4j
            with self.neo4j_driver.session() as session:
                sample_result = session.run("""
                    MATCH (p:Product)
                    RETURN p.id as product_id
                    ORDER BY rand()
                    LIMIT 10
                """)
                sample_ids = [record['product_id'] for record in sample_result]
            
            # Check correlation in Qdrant
            correlated_count = 0
            for product_id in sample_ids:
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
                    correlated_count += 1
            
            correlation_time = (time.time() - start_time) * 1000
            correlation_rate = (correlated_count / len(sample_ids) * 100) if sample_ids else 0
            
            metrics['correlation_metrics'] = {
                'sample_size': len(sample_ids),
                'correlated_products': correlated_count,
                'correlation_rate_percent': correlation_rate,
                'correlation_check_time_ms': correlation_time
            }
            
        except Exception as e:
            metrics['correlation_metrics'] = {
                'error': str(e)
            }
        
        # Performance metrics summary
        neo4j_healthy = metrics['neo4j_metrics'].get('connection_status') == 'connected'
        qdrant_healthy = metrics['qdrant_metrics'].get('connection_status') == 'connected'
        correlation_healthy = metrics['correlation_metrics'].get('correlation_rate_percent', 0) > 90
        
        metrics['performance_metrics'] = {
            'overall_health': 'healthy' if (neo4j_healthy and qdrant_healthy and correlation_healthy) else 'degraded',
            'neo4j_healthy': neo4j_healthy,
            'qdrant_healthy': qdrant_healthy,
            'correlation_healthy': correlation_healthy
        }
        
        return metrics
    
    def generate_html_dashboard(self, metrics: Dict) -> str:
        """Generate HTML dashboard from metrics"""
        print("🎨 Generating HTML dashboard...")
        
        # Calculate health status colors
        overall_health = metrics['performance_metrics']['overall_health']
        health_color = self.colors['success'] if overall_health == 'healthy' else self.colors['warning']
        
        neo4j_color = self.colors['success'] if metrics['performance_metrics']['neo4j_healthy'] else self.colors['error']
        qdrant_color = self.colors['success'] if metrics['performance_metrics']['qdrant_healthy'] else self.colors['error']
        correlation_color = self.colors['success'] if metrics['performance_metrics']['correlation_healthy'] else self.colors['error']
        
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AIStylist System Monitoring Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .dashboard {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .header {{
            background: white;
            border-radius: 10px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            text-align: center;
        }}
        
        .header h1 {{
            color: {self.colors['dark']};
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        .header .subtitle {{
            color: {self.colors['primary']};
            font-size: 1.2em;
        }}
        
        .header .timestamp {{
            color: #6c757d;
            margin-top: 10px;
        }}
        
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        
        .metric-card {{
            background: white;
            border-radius: 10px;
            padding: 25px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
        }}
        
        .metric-card:hover {{
            transform: translateY(-5px);
        }}
        
        .metric-card h3 {{
            color: {self.colors['dark']};
            margin-bottom: 15px;
            font-size: 1.3em;
            border-bottom: 2px solid {self.colors['primary']};
            padding-bottom: 10px;
        }}
        
        .status-indicator {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            color: white;
            font-weight: bold;
            margin-bottom: 15px;
        }}
        
        .status-healthy {{ background-color: {self.colors['success']}; }}
        .status-degraded {{ background-color: {self.colors['warning']}; }}
        .status-error {{ background-color: {self.colors['error']}; }}
        
        .metric-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }}
        
        .metric-item:last-child {{
            border-bottom: none;
        }}
        
        .metric-label {{
            color: #495057;
            font-weight: 500;
        }}
        
        .metric-value {{
            font-weight: bold;
            font-size: 1.1em;
        }}
        
        .value-good {{ color: {self.colors['success']}; }}
        .value-warning {{ color: {self.colors['warning']}; }}
        .value-error {{ color: {self.colors['error']}; }}
        
        .progress-bar {{
            width: 100%;
            height: 20px;
            background-color: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
            margin-top: 5px;
        }}
        
        .progress-fill {{
            height: 100%;
            transition: width 0.3s ease;
            border-radius: 10px;
        }}
        
        .large-metric {{
            grid-column: span 2;
        }}
        
        .refresh-button {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            background-color: {self.colors['primary']};
            color: white;
            border: none;
            border-radius: 50px;
            padding: 15px 25px;
            font-size: 1.1em;
            cursor: pointer;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: background-color 0.3s ease;
        }}
        
        .refresh-button:hover {{
            background-color: #0056b3;
        }}
        
        @media (max-width: 768px) {{
            .metrics-grid {{
                grid-template-columns: 1fr;
            }}
            .large-metric {{
                grid-column: span 1;
            }}
        }}
    </style>
    <script>
        function refreshDashboard() {{
            window.location.reload();
        }}
        
        // Auto-refresh every 5 minutes
        setInterval(refreshDashboard, 300000);
    </script>
</head>
<body>
    <div class="dashboard">
        <div class="header">
            <h1>🎯 AIStylist System Monitor</h1>
            <div class="subtitle">Real-time System Health & Performance Dashboard</div>
            <div class="timestamp">Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
        </div>
        
        <div class="metrics-grid">
            <!-- Overall System Health -->
            <div class="metric-card large-metric">
                <h3>🏥 Overall System Health</h3>
                <div class="status-indicator status-{overall_health}">{overall_health.upper()}</div>
                
                <div class="metric-item">
                    <span class="metric-label">Neo4j Database</span>
                    <span class="metric-value" style="color: {neo4j_color};">
                        {'✅ Connected' if metrics['performance_metrics']['neo4j_healthy'] else '❌ Error'}
                    </span>
                </div>
                
                <div class="metric-item">
                    <span class="metric-label">Qdrant Vector DB</span>
                    <span class="metric-value" style="color: {qdrant_color};">
                        {'✅ Connected' if metrics['performance_metrics']['qdrant_healthy'] else '❌ Error'}
                    </span>
                </div>
                
                <div class="metric-item">
                    <span class="metric-label">UUID Correlation</span>
                    <span class="metric-value" style="color: {correlation_color};">
                        {'✅ Healthy' if metrics['performance_metrics']['correlation_healthy'] else '⚠️ Degraded'}
                    </span>
                </div>
            </div>
            
            <!-- Neo4j Metrics -->
            <div class="metric-card">
                <h3>🗃️ Neo4j Database</h3>
        """
        
        if metrics['neo4j_metrics'].get('connection_status') == 'connected':
            node_counts = metrics['neo4j_metrics']['node_counts']
            rel_counts = metrics['neo4j_metrics']['relationship_counts']
            
            html_content += f"""
                <div class="metric-item">
                    <span class="metric-label">Products</span>
                    <span class="metric-value value-good">{node_counts.get('Product', 0):,}</span>
                </div>
                
                <div class="metric-item">
                    <span class="metric-label">Color Nodes</span>
                    <span class="metric-value value-good">{node_counts.get('Color', 0):,}</span>
                </div>
                
                <div class="metric-item">
                    <span class="metric-label">Brand Nodes</span>
                    <span class="metric-value value-good">{node_counts.get('Brand', 0):,}</span>
                </div>
                
                <div class="metric-item">
                    <span class="metric-label">Style Nodes</span>
                    <span class="metric-value value-good">{node_counts.get('Style', 0):,}</span>
                </div>
                
                <div class="metric-item">
                    <span class="metric-label">HAS_COLOR Relations</span>
                    <span class="metric-value value-good">{rel_counts.get('HAS_COLOR', 0):,}</span>
                </div>
                
                <div class="metric-item">
                    <span class="metric-label">Query Time</span>
                    <span class="metric-value {'value-good' if metrics['neo4j_metrics']['sample_query_time_ms'] < 100 else 'value-warning'}">{metrics['neo4j_metrics']['sample_query_time_ms']:.1f}ms</span>
                </div>
            """
        else:
            html_content += f"""
                <div class="metric-item">
                    <span class="metric-label">Status</span>
                    <span class="metric-value value-error">Connection Error</span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">Error</span>
                    <span class="metric-value value-error">{metrics['neo4j_metrics'].get('error', 'Unknown error')[:50]}...</span>
                </div>
            """
        
        html_content += "</div>"
        
        # Qdrant Metrics
        html_content += """
            <div class="metric-card">
                <h3>🔍 Qdrant Vector Database</h3>
        """
        
        if metrics['qdrant_metrics'].get('connection_status') == 'connected':
            html_content += f"""
                <div class="metric-item">
                    <span class="metric-label">Vector Count</span>
                    <span class="metric-value value-good">{metrics['qdrant_metrics']['vector_count']:,}</span>
                </div>
                
                <div class="metric-item">
                    <span class="metric-label">Collection Info Time</span>
                    <span class="metric-value {'value-good' if metrics['qdrant_metrics']['collection_info_time_ms'] < 100 else 'value-warning'}">{metrics['qdrant_metrics']['collection_info_time_ms']:.1f}ms</span>
                </div>
                
                <div class="metric-item">
                    <span class="metric-label">Search Time</span>
                    <span class="metric-value {'value-good' if metrics['qdrant_metrics']['sample_search_time_ms'] < 300 else 'value-warning'}">{metrics['qdrant_metrics']['sample_search_time_ms']:.1f}ms</span>
                </div>
                
                <div class="metric-item">
                    <span class="metric-label">Search Results</span>
                    <span class="metric-value value-good">{metrics['qdrant_metrics']['search_results_returned']}</span>
                </div>
            """
        else:
            html_content += f"""
                <div class="metric-item">
                    <span class="metric-label">Status</span>
                    <span class="metric-value value-error">Connection Error</span>
                </div>
            """
        
        html_content += "</div>"
        
        # System Resources
        if 'error' not in metrics['system_metrics']:
            cpu_usage = metrics['system_metrics']['cpu_usage_percent']
            memory_usage = metrics['system_metrics']['memory_usage_percent']
            disk_usage = metrics['system_metrics']['disk_usage_percent']
            
            html_content += f"""
                <div class="metric-card">
                    <h3>💻 System Resources</h3>
                    
                    <div class="metric-item">
                        <span class="metric-label">CPU Usage</span>
                        <span class="metric-value {'value-good' if cpu_usage < 70 else 'value-warning' if cpu_usage < 90 else 'value-error'}">{cpu_usage:.1f}%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {cpu_usage}%; background-color: {'#28a745' if cpu_usage < 70 else '#ffc107' if cpu_usage < 90 else '#dc3545'};"></div>
                    </div>
                    
                    <div class="metric-item">
                        <span class="metric-label">Memory Usage</span>
                        <span class="metric-value {'value-good' if memory_usage < 80 else 'value-warning' if memory_usage < 90 else 'value-error'}">{memory_usage:.1f}%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {memory_usage}%; background-color: {'#28a745' if memory_usage < 80 else '#ffc107' if memory_usage < 90 else '#dc3545'};"></div>
                    </div>
                    
                    <div class="metric-item">
                        <span class="metric-label">Disk Usage</span>
                        <span class="metric-value {'value-good' if disk_usage < 85 else 'value-warning' if disk_usage < 95 else 'value-error'}">{disk_usage:.1f}%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {disk_usage}%; background-color: {'#28a745' if disk_usage < 85 else '#ffc107' if disk_usage < 95 else '#dc3545'};"></div>
                    </div>
                    
                    <div class="metric-item">
                        <span class="metric-label">Available Memory</span>
                        <span class="metric-value value-info">{metrics['system_metrics']['available_memory_gb']:.1f} GB</span>
                    </div>
                    
                    <div class="metric-item">
                        <span class="metric-label">Available Disk</span>
                        <span class="metric-value value-info">{metrics['system_metrics']['available_disk_gb']:.1f} GB</span>
                    </div>
                </div>
            """
        
        # UUID Correlation Metrics
        if 'error' not in metrics['correlation_metrics']:
            correlation_rate = metrics['correlation_metrics']['correlation_rate_percent']
            
            html_content += f"""
                <div class="metric-card">
                    <h3>🔗 UUID Correlation</h3>
                    
                    <div class="metric-item">
                        <span class="metric-label">Correlation Rate</span>
                        <span class="metric-value {'value-good' if correlation_rate > 95 else 'value-warning' if correlation_rate > 80 else 'value-error'}">{correlation_rate:.1f}%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {correlation_rate}%; background-color: {'#28a745' if correlation_rate > 95 else '#ffc107' if correlation_rate > 80 else '#dc3545'};"></div>
                    </div>
                    
                    <div class="metric-item">
                        <span class="metric-label">Sample Size</span>
                        <span class="metric-value value-info">{metrics['correlation_metrics']['sample_size']}</span>
                    </div>
                    
                    <div class="metric-item">
                        <span class="metric-label">Correlated Products</span>
                        <span class="metric-value value-good">{metrics['correlation_metrics']['correlated_products']}</span>
                    </div>
                    
                    <div class="metric-item">
                        <span class="metric-label">Check Time</span>
                        <span class="metric-value value-info">{metrics['correlation_metrics']['correlation_check_time_ms']:.1f}ms</span>
                    </div>
                </div>
            """
        
        html_content += """
        </div>
        
        <button class="refresh-button" onclick="refreshDashboard()">🔄 Refresh</button>
    </div>
</body>
</html>
        """
        
        return html_content
    
    def generate_json_dashboard(self, metrics: Dict) -> str:
        """Generate JSON dashboard data for API consumption"""
        print("📄 Generating JSON dashboard data...")
        
        # Create simplified dashboard data for APIs
        dashboard_data = {
            'timestamp': metrics['timestamp'],
            'overall_status': metrics['performance_metrics']['overall_health'],
            'components': {
                'neo4j': {
                    'status': 'healthy' if metrics['performance_metrics']['neo4j_healthy'] else 'error',
                    'metrics': {
                        'products': metrics['neo4j_metrics'].get('total_products', 0),
                        'query_time_ms': metrics['neo4j_metrics'].get('sample_query_time_ms', 0),
                        'node_counts': metrics['neo4j_metrics'].get('node_counts', {}),
                        'relationship_counts': metrics['neo4j_metrics'].get('relationship_counts', {})
                    }
                },
                'qdrant': {
                    'status': 'healthy' if metrics['performance_metrics']['qdrant_healthy'] else 'error',
                    'metrics': {
                        'vector_count': metrics['qdrant_metrics'].get('vector_count', 0),
                        'search_time_ms': metrics['qdrant_metrics'].get('sample_search_time_ms', 0)
                    }
                },
                'correlation': {
                    'status': 'healthy' if metrics['performance_metrics']['correlation_healthy'] else 'degraded',
                    'metrics': {
                        'correlation_rate_percent': metrics['correlation_metrics'].get('correlation_rate_percent', 0)
                    }
                }
            },
            'system_resources': {
                'cpu_usage_percent': metrics['system_metrics'].get('cpu_usage_percent', 0),
                'memory_usage_percent': metrics['system_metrics'].get('memory_usage_percent', 0),
                'disk_usage_percent': metrics['system_metrics'].get('disk_usage_percent', 0)
            }
        }
        
        return json.dumps(dashboard_data, indent=2)
    
    def generate_text_dashboard(self, metrics: Dict) -> str:
        """Generate text-based dashboard for console display"""
        print("📝 Generating text dashboard...")
        
        # Create console-friendly dashboard
        text_lines = []
        text_lines.append("🎯 AIStylist System Monitor")
        text_lines.append("=" * 50)
        text_lines.append(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        text_lines.append("")
        
        # Overall health
        overall_health = metrics['performance_metrics']['overall_health']
        health_icon = "✅" if overall_health == 'healthy' else "⚠️"
        text_lines.append(f"🏥 Overall System Health: {health_icon} {overall_health.upper()}")
        text_lines.append("")
        
        # Component status
        text_lines.append("📊 Component Status:")
        
        neo4j_status = "✅ Connected" if metrics['performance_metrics']['neo4j_healthy'] else "❌ Error"
        text_lines.append(f"  • Neo4j Database: {neo4j_status}")
        
        qdrant_status = "✅ Connected" if metrics['performance_metrics']['qdrant_healthy'] else "❌ Error" 
        text_lines.append(f"  • Qdrant Vector DB: {qdrant_status}")
        
        correlation_status = "✅ Healthy" if metrics['performance_metrics']['correlation_healthy'] else "⚠️ Degraded"
        text_lines.append(f"  • UUID Correlation: {correlation_status}")
        text_lines.append("")
        
        # Neo4j details
        if metrics['neo4j_metrics'].get('connection_status') == 'connected':
            text_lines.append("🗃️ Neo4j Metrics:")
            node_counts = metrics['neo4j_metrics']['node_counts']
            text_lines.append(f"  • Products: {node_counts.get('Product', 0):,}")
            text_lines.append(f"  • Colors: {node_counts.get('Color', 0):,}")
            text_lines.append(f"  • Brands: {node_counts.get('Brand', 0):,}")
            text_lines.append(f"  • Styles: {node_counts.get('Style', 0):,}")
            text_lines.append(f"  • Query Time: {metrics['neo4j_metrics']['sample_query_time_ms']:.1f}ms")
            text_lines.append("")
        
        # Qdrant details
        if metrics['qdrant_metrics'].get('connection_status') == 'connected':
            text_lines.append("🔍 Qdrant Metrics:")
            text_lines.append(f"  • Vector Count: {metrics['qdrant_metrics']['vector_count']:,}")
            text_lines.append(f"  • Search Time: {metrics['qdrant_metrics']['sample_search_time_ms']:.1f}ms")
            text_lines.append("")
        
        # System resources
        if 'error' not in metrics['system_metrics']:
            text_lines.append("💻 System Resources:")
            text_lines.append(f"  • CPU Usage: {metrics['system_metrics']['cpu_usage_percent']:.1f}%")
            text_lines.append(f"  • Memory Usage: {metrics['system_metrics']['memory_usage_percent']:.1f}%")
            text_lines.append(f"  • Disk Usage: {metrics['system_metrics']['disk_usage_percent']:.1f}%")
            text_lines.append("")
        
        # Correlation details
        if 'error' not in metrics['correlation_metrics']:
            text_lines.append("🔗 UUID Correlation:")
            text_lines.append(f"  • Correlation Rate: {metrics['correlation_metrics']['correlation_rate_percent']:.1f}%")
            text_lines.append(f"  • Sample Size: {metrics['correlation_metrics']['sample_size']}")
            text_lines.append("")
        
        return '\n'.join(text_lines)
    
    def save_dashboards(self, metrics: Dict) -> Dict:
        """Save all dashboard formats to files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        saved_files = {}
        
        # Save HTML dashboard
        html_content = self.generate_html_dashboard(metrics)
        html_file = self.dashboard_path / f"system_dashboard_{timestamp}.html"
        with open(html_file, 'w') as f:
            f.write(html_content)
        saved_files['html'] = html_file
        
        # Save latest HTML (for easy access)
        latest_html = self.dashboard_path / "system_dashboard_latest.html"
        with open(latest_html, 'w') as f:
            f.write(html_content)
        saved_files['html_latest'] = latest_html
        
        # Save JSON dashboard
        json_content = self.generate_json_dashboard(metrics)
        json_file = self.dashboard_path / f"dashboard_data_{timestamp}.json"
        with open(json_file, 'w') as f:
            f.write(json_content)
        saved_files['json'] = json_file
        
        # Save latest JSON
        latest_json = self.dashboard_path / "dashboard_data_latest.json"
        with open(latest_json, 'w') as f:
            f.write(json_content)
        saved_files['json_latest'] = latest_json
        
        # Save text dashboard
        text_content = self.generate_text_dashboard(metrics)
        text_file = self.dashboard_path / f"dashboard_text_{timestamp}.txt"
        with open(text_file, 'w') as f:
            f.write(text_content)
        saved_files['text'] = text_file
        
        # Save metrics for historical tracking
        metrics_file = self.dashboard_path / f"metrics_{timestamp}.json"
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2, default=str)
        saved_files['metrics'] = metrics_file
        
        return saved_files
    
    def create_deployment_status_dashboard(self, deployment_logs_path: Path = None) -> str:
        """Create dashboard for deployment status monitoring"""
        print("🚀 Creating deployment status dashboard...")
        
        if not deployment_logs_path:
            deployment_logs_path = Path("./deployment_logs")
        
        deployment_data = {}
        
        if deployment_logs_path.exists():
            # Find most recent deployment
            log_files = list(deployment_logs_path.glob("deployment_*.log"))
            report_files = list(deployment_logs_path.glob("*_report.json"))
            
            if report_files:
                latest_report = max(report_files, key=lambda f: f.stat().st_mtime)
                
                try:
                    with open(latest_report, 'r') as f:
                        deployment_data = json.load(f)
                except Exception as e:
                    deployment_data = {'error': f"Could not read deployment report: {e}"}
        
        # Generate deployment dashboard HTML
        deployment_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AIStylist Deployment Status</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%);
            min-height: 100vh;
            padding: 20px;
            margin: 0;
        }}
        
        .deployment-dashboard {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
        }}
        
        .deployment-header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        
        .deployment-header h1 {{
            color: #2d3436;
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        .deployment-status {{
            display: inline-block;
            padding: 10px 20px;
            border-radius: 25px;
            color: white;
            font-weight: bold;
            font-size: 1.2em;
            margin: 10px 0;
        }}
        
        .status-completed {{ background-color: #00b894; }}
        .status-running {{ background-color: #fdcb6e; }}
        .status-failed {{ background-color: #e17055; }}
        .status-unknown {{ background-color: #6c5ce7; }}
        
        .checkpoints-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }}
        
        .checkpoint-card {{
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            border-left: 4px solid #ddd;
        }}
        
        .checkpoint-card.passed {{ border-left-color: #00b894; }}
        .checkpoint-card.failed {{ border-left-color: #e17055; }}
        .checkpoint-card.running {{ border-left-color: #fdcb6e; }}
        
        .checkpoint-title {{
            font-weight: bold;
            color: #2d3436;
            margin-bottom: 10px;
        }}
        
        .checkpoint-status {{
            display: inline-block;
            padding: 5px 10px;
            border-radius: 15px;
            color: white;
            font-size: 0.9em;
            margin-bottom: 10px;
        }}
        
        .status-passed {{ background-color: #00b894; }}
        .status-failed {{ background-color: #e17055; }}
        .status-running {{ background-color: #fdcb6e; }}
        .status-pending {{ background-color: #74b9ff; }}
        
        .checkpoint-details {{
            font-size: 0.9em;
            color: #636e72;
        }}
        
        .progress-section {{
            margin: 30px 0;
            text-align: center;
        }}
        
        .progress-bar {{
            width: 100%;
            height: 30px;
            background-color: #e9ecef;
            border-radius: 15px;
            overflow: hidden;
            margin: 20px 0;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #00b894, #55a3ff);
            border-radius: 15px;
            transition: width 0.3s ease;
        }}
    </style>
</head>
<body>
    <div class="deployment-dashboard">
        <div class="deployment-header">
            <h1>🚀 Deployment Status Monitor</h1>
        """
        
        if 'error' not in deployment_data and deployment_data:
            summary = deployment_data.get('summary', {})
            status = summary.get('status', 'unknown')
            
            status_class = 'status-unknown'
            if 'completed' in status:
                status_class = 'status-completed'
            elif 'running' in status:
                status_class = 'status-running'
            elif 'failed' in status:
                status_class = 'status-failed'
            
            deployment_html += f"""
            <div class="deployment-status {status_class}">{status.replace('_', ' ').title()}</div>
            <p>Deployment ID: {deployment_data.get('deployment_id', 'Unknown')}</p>
            <p>Started: {deployment_data.get('start_time', 'Unknown')}</p>
            """
            
            if 'total_duration_seconds' in summary:
                duration_hours = summary['total_duration_seconds'] / 3600
                deployment_html += f"<p>Duration: {duration_hours:.1f} hours</p>"
            
            # Progress section
            total_checkpoints = summary.get('total_checkpoints', 0)
            completed_checkpoints = summary.get('completed_checkpoints', 0)
            progress_percent = (completed_checkpoints / total_checkpoints * 100) if total_checkpoints > 0 else 0
            
            deployment_html += f"""
        </div>
        
        <div class="progress-section">
            <h3>Overall Progress</h3>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {progress_percent}%;"></div>
            </div>
            <p>{completed_checkpoints}/{total_checkpoints} checkpoints completed ({progress_percent:.1f}%)</p>
        </div>
        
        <div class="checkpoints-grid">
            """
            
            # Checkpoint details
            checkpoints = deployment_data.get('checkpoints', {})
            for checkpoint_name, checkpoint_data in checkpoints.items():
                status = checkpoint_data.get('status', 'pending')
                phase = checkpoint_data.get('phase', 'unknown')
                description = checkpoint_data.get('description', 'No description')
                
                deployment_html += f"""
            <div class="checkpoint-card {status}">
                <div class="checkpoint-title">{checkpoint_name.replace('_', ' ').title()}</div>
                <div class="checkpoint-status status-{status}">{status.upper()}</div>
                <div class="checkpoint-details">
                    <p><strong>Phase:</strong> {phase.replace('_', ' ').title()}</p>
                    <p><strong>Description:</strong> {description}</p>
                """
                
                if 'execution_time_seconds' in checkpoint_data:
                    exec_time = checkpoint_data['execution_time_seconds']
                    deployment_html += f"<p><strong>Execution Time:</strong> {exec_time:.1f}s</p>"
                
                if checkpoint_data.get('error'):
                    deployment_html += f"<p><strong>Error:</strong> {checkpoint_data['error'][:100]}...</p>"
                
                deployment_html += """
                </div>
            </div>
                """
        else:
            deployment_html += """
            <div class="deployment-status status-unknown">No Recent Deployment</div>
            <p>No deployment data available</p>
        </div>
        
        <div class="progress-section">
            <h3>No Active Deployment</h3>
            <p>Start a deployment to see progress here</p>
        </div>
            """
        
        deployment_html += """
        </div>
    </div>
</body>
</html>
        """
        
        # Save deployment dashboard
        deployment_file = self.dashboard_path / "deployment_status.html"
        with open(deployment_file, 'w') as f:
            f.write(deployment_html)
        
        return deployment_html
    
    def generate_all_dashboards(self) -> Dict:
        """Generate all dashboard types and save them"""
        print("🎨 Generating All Monitoring Dashboards")
        print("=" * 50)
        
        # Collect current metrics
        metrics = self.collect_system_metrics()
        
        # Save all dashboard formats
        saved_files = self.save_dashboards(metrics)
        
        # Generate deployment status dashboard
        deployment_html = self.create_deployment_status_dashboard()
        saved_files['deployment_status'] = self.dashboard_path / "deployment_status.html"
        
        # Print summary
        print(f"\n✅ All dashboards generated successfully")
        print(f"📁 Dashboard directory: {self.dashboard_path}")
        print(f"🌐 Main dashboard: {saved_files['html_latest']}")
        print(f"🚀 Deployment status: {saved_files['deployment_status']}")
        
        # Display text dashboard
        text_dashboard = self.generate_text_dashboard(metrics)
        print(f"\n{text_dashboard}")
        
        return {
            'metrics': metrics,
            'saved_files': saved_files,
            'dashboard_directory': str(self.dashboard_path)
        }


def main():
    """Generate monitoring dashboards"""
    generator = MonitoringDashboardGenerator()
    
    try:
        generator.connect_databases()
        result = generator.generate_all_dashboards()
        
        print(f"\n🎯 DASHBOARD GENERATION SUMMARY")
        print("=" * 50)
        print(f"Dashboard Directory: {result['dashboard_directory']}")
        print(f"Files Generated: {len(result['saved_files'])}")
        
        for dashboard_type, file_path in result['saved_files'].items():
            print(f"  • {dashboard_type}: {file_path}")
        
        overall_health = result['metrics']['performance_metrics']['overall_health']
        print(f"\n🏥 Current System Health: {overall_health.upper()}")
        
        return True
        
    except Exception as e:
        print(f"❌ Dashboard generation failed: {e}")
        return False
    
    finally:
        if hasattr(generator, 'neo4j_driver'):
            generator.neo4j_driver.close()


if __name__ == "__main__":
    main()