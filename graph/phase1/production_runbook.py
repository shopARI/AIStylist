#!/usr/bin/env python3
"""
Production Runbook Generator
Creates comprehensive runbooks and documentation for all operations
"""

import json
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path


class ProductionRunbookGenerator:
    """Generates production runbooks and operational documentation"""
    
    def __init__(self):
        self.runbooks = {}
        self.documentation_path = Path("./production_docs")
        self.documentation_path.mkdir(exist_ok=True)
        
        # Operation categories
        self.operation_categories = [
            "pre_deployment",
            "deployment",
            "post_deployment", 
            "maintenance",
            "troubleshooting",
            "emergency_procedures"
        ]
    
    def create_phase2_deployment_runbook(self) -> Dict:
        """Create runbook for Phase 2 deployment"""
        runbook = {
            'title': 'Phase 2 Graph Reconstruction Deployment',
            'version': '1.0',
            'created': datetime.now().isoformat(),
            'category': 'deployment',
            'estimated_duration': '2-4 hours',
            'prerequisites': [
                'Phase 1 analysis completed successfully',
                'Neo4j database accessible with write permissions',
                'Backup created and validated',
                'System resources verified (CPU, memory, disk)',
                'All validation scripts tested'
            ],
            'steps': [
                {
                    'step': 1,
                    'title': 'Pre-Deployment Safety Check',
                    'duration': '15 minutes',
                    'description': 'Validate system readiness and create backup',
                    'commands': [
                        'python rollback_safety_procedures.py --operation phase2_graph_reconstruction',
                        'python rollback_safety_procedures.py --create-backup phase2_deployment'
                    ],
                    'success_criteria': [
                        'Safety validation passes with no blocking issues',
                        'Backup created successfully',
                        'System resources within acceptable limits'
                    ],
                    'failure_actions': [
                        'Address blocking issues identified in safety check',
                        'Do not proceed until all safety checks pass'
                    ]
                },
                {
                    'step': 2,
                    'title': 'Execute Phase 2 Graph Reconstruction',
                    'duration': '1-2 hours',
                    'description': 'Run the Phase 2 scripts to add Color, Brand, Style nodes',
                    'commands': [
                        'cd /home/leo/AIStylist/graph/phase1',
                        'python prepare_phase2.py --execute',
                        'tail -f phase2_execution.log'
                    ],
                    'success_criteria': [
                        'All Color nodes created (expected: ~15 nodes)',
                        'All Brand nodes created (expected: ~100 nodes)',
                        'All Style nodes created (expected: ~50 nodes)',
                        'Product relationships created (expected: ~2M+ relationships)',
                        'No critical errors in execution log'
                    ],
                    'monitoring': [
                        'Watch Neo4j memory usage',
                        'Monitor disk space consumption',
                        'Track execution progress in logs'
                    ],
                    'failure_actions': [
                        'Stop execution if critical errors occur',
                        'Check Neo4j logs for constraint violations',
                        'Verify database connectivity',
                        'Consider partial rollback if needed'
                    ]
                },
                {
                    'step': 3,
                    'title': 'Validate Phase 2 Completion',
                    'duration': '30 minutes',
                    'description': 'Run comprehensive validation of Phase 2 results',
                    'commands': [
                        'python validate_phase2_completion.py',
                        'python validate_phase2_completion.py --detailed-report'
                    ],
                    'success_criteria': [
                        'Node count validation passes',
                        'Relationship count validation passes',
                        'Data integrity checks pass',
                        'No orphaned nodes or relationships'
                    ],
                    'failure_actions': [
                        'Review validation report for specific failures',
                        'Fix data integrity issues if minor',
                        'Consider rollback if major issues found'
                    ]
                },
                {
                    'step': 4,
                    'title': 'Performance Validation',
                    'duration': '15 minutes',
                    'description': 'Test query performance with new schema',
                    'commands': [
                        'python performance_benchmarking.py --suite neo4j_performance',
                        'python performance_benchmarking.py --suite uuid_correlation_performance'
                    ],
                    'success_criteria': [
                        'Query performance within acceptable limits',
                        'No significant degradation from baseline',
                        'Relationship queries execute efficiently'
                    ],
                    'failure_actions': [
                        'Investigate slow queries',
                        'Consider adding database indexes',
                        'Monitor system resources'
                    ]
                }
            ],
            'rollback_procedure': {
                'trigger_conditions': [
                    'Validation failures that cannot be fixed',
                    'Severe performance degradation',
                    'Data corruption detected',
                    'System resource exhaustion'
                ],
                'rollback_steps': [
                    'python rollback_safety_procedures.py --execute-rollback phase2_deployment',
                    'Validate rollback success',
                    'Restore system to pre-Phase-2 state'
                ]
            },
            'post_deployment_tasks': [
                'Document any issues encountered',
                'Update monitoring dashboards',
                'Notify stakeholders of completion',
                'Schedule follow-up health checks'
            ]
        }
        
        return runbook
    
    def create_embedding_deployment_runbook(self) -> Dict:
        """Create runbook for vector re-embedding deployment"""
        runbook = {
            'title': 'Vector Re-embedding with Perfect UUID Correlation',
            'version': '1.0',
            'created': datetime.now().isoformat(),
            'category': 'deployment',
            'estimated_duration': '4-8 hours',
            'prerequisites': [
                'Phase 2 graph reconstruction completed',
                'OpenAI API key configured and tested',
                'Qdrant database accessible',
                'Sufficient API quota for re-embedding (~6.4M products)',
                'Backup of current Qdrant collection created'
            ],
            'cost_estimate': '$500-$1000 for OpenAI API calls',
            'steps': [
                {
                    'step': 1,
                    'title': 'Pre-Embedding Safety and Cost Check',
                    'duration': '15 minutes',
                    'description': 'Validate readiness and estimate costs',
                    'commands': [
                        'python rollback_safety_procedures.py --operation vector_re_embedding',
                        'python proper_embedding_with_uuid_sync.py --estimate-cost --dry-run'
                    ],
                    'success_criteria': [
                        'Safety validation passes',
                        'Cost estimate within budget',
                        'API connectivity confirmed',
                        'Sufficient system resources available'
                    ],
                    'failure_actions': [
                        'Address safety issues before proceeding',
                        'Confirm budget approval for API costs',
                        'Verify OpenAI API key and quotas'
                    ]
                },
                {
                    'step': 2,
                    'title': 'Backup Current Qdrant Collection',
                    'duration': '30 minutes',
                    'description': 'Create comprehensive backup of current vectors',
                    'commands': [
                        'python rollback_safety_procedures.py --create-backup qdrant_pre_reembedding',
                        'python qdrant_vector_analysis.py --export-sample 10000'
                    ],
                    'success_criteria': [
                        'Backup completed successfully',
                        'Sample vectors exported for validation',
                        'Backup integrity verified'
                    ]
                },
                {
                    'step': 3,
                    'title': 'Execute Re-embedding with UUID Sync',
                    'duration': '3-6 hours',
                    'description': 'Re-embed all products with perfect UUID correlation',
                    'commands': [
                        'python proper_embedding_with_uuid_sync.py --execute --batch-size 100',
                        'tail -f embedding_progress.log'
                    ],
                    'success_criteria': [
                        'All products re-embedded successfully',
                        'Perfect UUID correlation maintained',
                        'No API errors or timeouts',
                        'Vector count matches product count'
                    ],
                    'monitoring': [
                        'Track API usage and costs',
                        'Monitor embedding progress',
                        'Watch for API rate limits',
                        'Check system memory usage'
                    ],
                    'failure_actions': [
                        'Pause on API errors and investigate',
                        'Resume from checkpoint if interrupted',
                        'Monitor API quotas and billing'
                    ]
                },
                {
                    'step': 4,
                    'title': 'Validate UUID Correlation',
                    'duration': '30 minutes',
                    'description': 'Comprehensive validation of UUID synchronization',
                    'commands': [
                        'python validate_uuid_synchronization.py --comprehensive',
                        'python validate_uuid_synchronization.py --sample-size 10000'
                    ],
                    'success_criteria': [
                        '>99% perfect UUID correlation',
                        'No orphaned vectors',
                        'All Neo4j products have corresponding vectors',
                        'Payload product_id matches vector ID'
                    ],
                    'failure_actions': [
                        'Investigate correlation failures',
                        'Re-run embedding for failed products',
                        'Consider full rollback if correlation < 95%'
                    ]
                },
                {
                    'step': 5,
                    'title': 'Search Quality Validation',
                    'duration': '30 minutes',
                    'description': 'Test search functionality with new embeddings',
                    'commands': [
                        'python validate_search_quality.py --full-suite',
                        'python performance_benchmarking.py --suite qdrant_performance'
                    ],
                    'success_criteria': [
                        'Search quality tests pass',
                        'Performance within acceptable limits',
                        'Semantic search returns relevant results'
                    ]
                }
            ],
            'rollback_procedure': {
                'trigger_conditions': [
                    'UUID correlation < 95%',
                    'Search quality significantly degraded',
                    'API costs exceed budget',
                    'Severe performance issues'
                ],
                'rollback_steps': [
                    'python rollback_safety_procedures.py --execute-rollback qdrant_pre_reembedding',
                    'Restore previous Qdrant collection',
                    'Validate rollback success'
                ]
            }
        }
        
        return runbook
    
    def create_monitoring_runbook(self) -> Dict:
        """Create runbook for production monitoring"""
        runbook = {
            'title': 'Production System Monitoring',
            'version': '1.0',
            'created': datetime.now().isoformat(),
            'category': 'maintenance',
            'estimated_duration': 'Continuous',
            'overview': 'Comprehensive monitoring of production system health and performance',
            'monitoring_components': [
                {
                    'component': 'Neo4j Database Health',
                    'monitoring_script': 'production_monitoring.py',
                    'check_frequency': '5 minutes',
                    'key_metrics': [
                        'Query response time (target: <100ms)',
                        'Connection pool utilization',
                        'Memory usage',
                        'Transaction throughput'
                    ],
                    'alert_conditions': [
                        'Response time > 1000ms',
                        'Memory usage > 85%',
                        'Connection failures'
                    ]
                },
                {
                    'component': 'Qdrant Vector Database',
                    'monitoring_script': 'production_monitoring.py',
                    'check_frequency': '5 minutes',
                    'key_metrics': [
                        'Vector search response time (target: <300ms)',
                        'Collection size',
                        'API response time',
                        'Search accuracy'
                    ],
                    'alert_conditions': [
                        'Search response time > 500ms',
                        'API errors > 1%',
                        'Collection corruption detected'
                    ]
                },
                {
                    'component': 'UUID Correlation Health',
                    'monitoring_script': 'validate_uuid_synchronization.py',
                    'check_frequency': '1 hour',
                    'key_metrics': [
                        'Correlation accuracy (target: >99%)',
                        'Orphaned vectors count',
                        'Missing correlations count'
                    ],
                    'alert_conditions': [
                        'Correlation accuracy < 95%',
                        'Orphaned vectors > 100',
                        'Missing correlations increasing'
                    ]
                },
                {
                    'component': 'Search Quality',
                    'monitoring_script': 'validate_search_quality.py',
                    'check_frequency': '2 hours',
                    'key_metrics': [
                        'Search relevance score',
                        'Facet accuracy',
                        'Query success rate'
                    ],
                    'alert_conditions': [
                        'Relevance score < 70%',
                        'Query success rate < 95%'
                    ]
                }
            ],
            'dashboard_metrics': [
                'System uptime',
                'Query response times (P50, P95, P99)',
                'Error rates by component',
                'Resource utilization (CPU, memory, disk)',
                'API usage and costs',
                'User satisfaction metrics'
            ],
            'daily_tasks': [
                'Review monitoring dashboards',
                'Check error logs for anomalies',
                'Validate backup integrity',
                'Monitor resource utilization trends',
                'Review performance metrics'
            ],
            'weekly_tasks': [
                'Run comprehensive health checks',
                'Review and rotate log files',
                'Update monitoring thresholds if needed',
                'Performance trend analysis',
                'Security audit of access logs'
            ],
            'monthly_tasks': [
                'Full system performance review',
                'Backup and recovery testing',
                'Capacity planning review',
                'Update monitoring documentation',
                'Disaster recovery drill'
            ]
        }
        
        return runbook
    
    def create_troubleshooting_runbook(self) -> Dict:
        """Create comprehensive troubleshooting runbook"""
        runbook = {
            'title': 'Production Troubleshooting Guide',
            'version': '1.0',
            'created': datetime.now().isoformat(),
            'category': 'troubleshooting',
            'common_issues': [
                {
                    'issue': 'Search Results Not Matching Query Intent',
                    'symptoms': [
                        'Searching "red shirt" returns blue items',
                        'Color filters not working correctly',
                        'Brand searches returning wrong brands'
                    ],
                    'root_causes': [
                        'UUID correlation broken',
                        'Phase 2 relationships missing',
                        'Search logic routing incorrectly'
                    ],
                    'diagnostic_steps': [
                        'python validate_uuid_synchronization.py --quick-check',
                        'python validate_phase2_completion.py --check-relationships',
                        'Check intent detection routing logs'
                    ],
                    'resolution_steps': [
                        'If UUID correlation < 95%: Re-run embedding synchronization',
                        'If relationships missing: Re-run Phase 2 deployment',
                        'If routing issues: Update intent detection logic'
                    ]
                },
                {
                    'issue': 'Slow Query Performance',
                    'symptoms': [
                        'Search queries taking >1 second',
                        'Database timeouts',
                        'High CPU usage on database servers'
                    ],
                    'root_causes': [
                        'Missing database indexes',
                        'Inefficient query patterns',
                        'Large result sets without pagination'
                    ],
                    'diagnostic_steps': [
                        'python performance_benchmarking.py --quick-benchmark',
                        'Check Neo4j query logs for slow queries',
                        'Analyze query execution plans'
                    ],
                    'resolution_steps': [
                        'Add missing indexes on frequently queried fields',
                        'Optimize slow queries',
                        'Implement result pagination',
                        'Consider query caching'
                    ]
                },
                {
                    'issue': 'UUID Correlation Drift',
                    'symptoms': [
                        'Products found in Neo4j but not in Qdrant',
                        'Vector search returns products that don\'t exist',
                        'Inconsistent product data'
                    ],
                    'root_causes': [
                        'Data synchronization issues',
                        'Partial embedding failures',
                        'Database updates without vector updates'
                    ],
                    'diagnostic_steps': [
                        'python validate_uuid_synchronization.py --full-analysis',
                        'Check for recent data import activities',
                        'Verify embedding pipeline logs'
                    ],
                    'resolution_steps': [
                        'Identify scope of correlation drift',
                        'Re-embed affected products',
                        'Implement monitoring to prevent future drift',
                        'Update data update procedures'
                    ]
                },
                {
                    'issue': 'System Resource Exhaustion',
                    'symptoms': [
                        'High CPU usage (>90%)',
                        'Memory usage approaching limits',
                        'Disk space critically low',
                        'Connection timeouts'
                    ],
                    'root_causes': [
                        'Unexpected load increase',
                        'Memory leaks in applications',
                        'Large batch operations running',
                        'Log files consuming disk space'
                    ],
                    'diagnostic_steps': [
                        'python production_monitoring.py --resource-check',
                        'Check system resource utilization',
                        'Identify resource-intensive processes',
                        'Review recent system changes'
                    ],
                    'resolution_steps': [
                        'Scale resources if needed',
                        'Terminate resource-intensive operations',
                        'Clean up log files and temporary data',
                        'Implement resource monitoring alerts'
                    ]
                },
                {
                    'issue': 'API Integration Failures',
                    'symptoms': [
                        'API endpoints returning errors',
                        'Incomplete response data',
                        'Integration tests failing'
                    ],
                    'root_causes': [
                        'Database schema changes',
                        'API contract changes',
                        'Authentication issues'
                    ],
                    'diagnostic_steps': [
                        'python api_integration_prep.py --validate-readiness',
                        'Test individual API endpoints',
                        'Check API authentication and authorization'
                    ],
                    'resolution_steps': [
                        'Update API schemas to match database changes',
                        'Fix authentication configuration',
                        'Update integration tests',
                        'Deploy API fixes'
                    ]
                }
            ],
            'escalation_procedures': [
                {
                    'severity': 'Critical (System Down)',
                    'response_time': '15 minutes',
                    'actions': [
                        'Execute emergency procedures',
                        'Notify on-call team immediately',
                        'Begin immediate rollback if needed',
                        'Document all actions taken'
                    ]
                },
                {
                    'severity': 'High (Degraded Performance)',
                    'response_time': '1 hour',
                    'actions': [
                        'Investigate root cause',
                        'Implement temporary workarounds',
                        'Plan permanent fix',
                        'Monitor system closely'
                    ]
                },
                {
                    'severity': 'Medium (Functional Issues)',
                    'response_time': '4 hours',
                    'actions': [
                        'Analyze issue scope',
                        'Develop fix plan',
                        'Test fix in staging',
                        'Schedule deployment'
                    ]
                }
            ]
        }
        
        return runbook
    
    def create_emergency_procedures_runbook(self) -> Dict:
        """Create emergency procedures runbook"""
        runbook = {
            'title': 'Emergency Response Procedures',
            'version': '1.0',
            'created': datetime.now().isoformat(),
            'category': 'emergency_procedures',
            'overview': 'Critical procedures for handling system emergencies',
            'emergency_scenarios': [
                {
                    'scenario': 'Complete System Failure',
                    'description': 'Total system unavailability',
                    'immediate_actions': [
                        'Assess scope of failure',
                        'Activate incident response team',
                        'Begin system recovery procedures',
                        'Communicate status to stakeholders'
                    ],
                    'recovery_procedure': [
                        'python rollback_safety_procedures.py --emergency-stop',
                        'Identify root cause of failure',
                        'Execute appropriate recovery plan',
                        'Validate system functionality',
                        'Restore service gradually'
                    ],
                    'estimated_recovery_time': '2-6 hours'
                },
                {
                    'scenario': 'Data Corruption Detected',
                    'description': 'Database integrity compromised',
                    'immediate_actions': [
                        'Stop all write operations',
                        'Isolate affected data',
                        'Assess corruption extent',
                        'Begin data recovery procedures'
                    ],
                    'recovery_procedure': [
                        'python rollback_safety_procedures.py --execute-rollback latest_backup',
                        'Validate data integrity after restore',
                        'Identify and fix corruption cause',
                        'Resume operations with monitoring'
                    ],
                    'estimated_recovery_time': '1-4 hours'
                },
                {
                    'scenario': 'Security Incident',
                    'description': 'Suspected unauthorized access or data breach',
                    'immediate_actions': [
                        'Isolate affected systems',
                        'Change all credentials',
                        'Enable additional logging',
                        'Contact security team'
                    ],
                    'recovery_procedure': [
                        'Conduct security audit',
                        'Patch security vulnerabilities',
                        'Restore from clean backups if needed',
                        'Implement additional security measures'
                    ],
                    'estimated_recovery_time': '4-24 hours'
                }
            ],
            'communication_plan': {
                'internal_stakeholders': [
                    'Engineering team',
                    'Product management',
                    'Customer support',
                    'Executive team'
                ],
                'external_stakeholders': [
                    'End users',
                    'API consumers',
                    'Business partners'
                ],
                'communication_channels': [
                    'Incident response chat channel',
                    'Status page updates',
                    'Email notifications',
                    'Social media updates'
                ]
            },
            'post_incident_procedures': [
                'Conduct post-mortem analysis',
                'Document lessons learned',
                'Update procedures based on findings',
                'Implement preventive measures',
                'Review and test emergency procedures'
            ]
        }
        
        return runbook
    
    def create_maintenance_runbook(self) -> Dict:
        """Create routine maintenance runbook"""
        runbook = {
            'title': 'Routine System Maintenance',
            'version': '1.0',
            'created': datetime.now().isoformat(),
            'category': 'maintenance',
            'maintenance_schedules': {
                'daily': [
                    {
                        'task': 'Health Check Monitoring',
                        'duration': '15 minutes',
                        'commands': ['python production_monitoring.py --daily-check'],
                        'success_criteria': 'All health metrics within normal ranges'
                    },
                    {
                        'task': 'Backup Verification',
                        'duration': '10 minutes',
                        'commands': ['python rollback_safety_procedures.py --verify-backups'],
                        'success_criteria': 'Recent backups exist and are valid'
                    }
                ],
                'weekly': [
                    {
                        'task': 'Performance Benchmarking',
                        'duration': '1 hour',
                        'commands': ['python performance_benchmarking.py --weekly-benchmark'],
                        'success_criteria': 'Performance within acceptable limits'
                    },
                    {
                        'task': 'UUID Correlation Validation',
                        'duration': '30 minutes',
                        'commands': ['python validate_uuid_synchronization.py --comprehensive'],
                        'success_criteria': 'Correlation accuracy >99%'
                    },
                    {
                        'task': 'Search Quality Assessment',
                        'duration': '30 minutes',
                        'commands': ['python validate_search_quality.py --full-suite'],
                        'success_criteria': 'Search quality tests pass'
                    }
                ],
                'monthly': [
                    {
                        'task': 'Full System Validation',
                        'duration': '2 hours',
                        'commands': [
                            'python validate_phase2_completion.py --detailed-report',
                            'python api_integration_prep.py --validate-readiness',
                            'python performance_benchmarking.py --comprehensive'
                        ],
                        'success_criteria': 'All validation tests pass'
                    },
                    {
                        'task': 'Capacity Planning Review',
                        'duration': '1 hour',
                        'description': 'Review resource usage trends and plan for scaling',
                        'deliverable': 'Capacity planning report'
                    },
                    {
                        'task': 'Security Audit',
                        'duration': '2 hours',
                        'description': 'Review access logs and security configurations',
                        'deliverable': 'Security audit report'
                    }
                ]
            },
            'maintenance_windows': {
                'preferred_time': '2:00 AM - 4:00 AM UTC (low usage period)',
                'notification_period': '24 hours advance notice',
                'rollback_plan': 'All maintenance should have rollback procedures defined'
            }
        }
        
        return runbook
    
    def generate_all_runbooks(self) -> Dict:
        """Generate all production runbooks"""
        print("📚 Generating Production Runbooks and Documentation")
        print("=" * 60)
        
        runbooks = {
            'generation_timestamp': datetime.now().isoformat(),
            'runbooks': {}
        }
        
        # Generate each runbook
        runbook_generators = {
            'phase2_deployment': self.create_phase2_deployment_runbook,
            'embedding_deployment': self.create_embedding_deployment_runbook,
            'production_monitoring': self.create_monitoring_runbook,
            'troubleshooting': self.create_troubleshooting_runbook,
            'emergency_procedures': self.create_emergency_procedures_runbook,
            'routine_maintenance': self.create_maintenance_runbook
        }
        
        for runbook_name, generator_func in runbook_generators.items():
            print(f"📖 Generating: {runbook_name}")
            runbook = generator_func()
            runbooks['runbooks'][runbook_name] = runbook
            
            # Save individual runbook
            runbook_file = self.documentation_path / f"{runbook_name}_runbook.json"
            with open(runbook_file, 'w') as f:
                json.dump(runbook, f, indent=2, default=str)
            print(f"   💾 Saved: {runbook_file}")
        
        # Create summary document
        summary = self.create_runbook_summary(runbooks['runbooks'])
        runbooks['summary'] = summary
        
        # Save master runbook file
        master_file = self.documentation_path / "production_runbooks_master.json"
        with open(master_file, 'w') as f:
            json.dump(runbooks, f, indent=2, default=str)
        
        print(f"\n✅ All runbooks generated successfully")
        print(f"📁 Documentation directory: {self.documentation_path}")
        print(f"📋 Master file: {master_file}")
        
        return runbooks
    
    def create_runbook_summary(self, runbooks: Dict) -> Dict:
        """Create summary of all runbooks"""
        summary = {
            'total_runbooks': len(runbooks),
            'runbook_categories': {},
            'key_procedures': [],
            'estimated_deployment_time': '6-12 hours total',
            'critical_dependencies': [
                'Neo4j database with write permissions',
                'Qdrant vector database access',
                'OpenAI API key and quota',
                'System backup capabilities',
                'Monitoring and alerting setup'
            ]
        }
        
        # Categorize runbooks
        for name, runbook in runbooks.items():
            category = runbook.get('category', 'other')
            if category not in summary['runbook_categories']:
                summary['runbook_categories'][category] = []
            summary['runbook_categories'][category].append(name)
        
        # Key procedures summary
        summary['key_procedures'] = [
            {
                'name': 'Phase 2 Graph Reconstruction',
                'duration': '2-4 hours',
                'impact': 'Adds Color, Brand, Style nodes and relationships',
                'rollback_available': True
            },
            {
                'name': 'Vector Re-embedding with UUID Sync',
                'duration': '4-8 hours',
                'impact': 'Perfect correlation between Neo4j and Qdrant',
                'cost': '$500-$1000 API costs',
                'rollback_available': True
            },
            {
                'name': 'Production Monitoring Setup',
                'duration': 'Continuous',
                'impact': 'Ongoing system health monitoring',
                'rollback_available': False
            }
        ]
        
        return summary
    
    def generate_markdown_documentation(self, runbooks: Dict) -> str:
        """Generate markdown documentation from runbooks"""
        markdown_content = [
            "# Production Operations Runbooks\n",
            f"Generated: {datetime.now().isoformat()}\n",
            "## Overview\n",
            "This document contains comprehensive runbooks for all production operations.\n"
        ]
        
        # Table of Contents
        markdown_content.extend([
            "## Table of Contents\n",
            "1. [Phase 2 Deployment](#phase2-deployment)",
            "2. [Vector Re-embedding](#embedding-deployment)",
            "3. [Production Monitoring](#production-monitoring)",
            "4. [Troubleshooting](#troubleshooting)",
            "5. [Emergency Procedures](#emergency-procedures)",
            "6. [Routine Maintenance](#routine-maintenance)\n"
        ])
        
        # Generate sections for each runbook
        for runbook_name, runbook_data in runbooks.items():
            markdown_content.extend([
                f"## {runbook_data['title']}\n",
                f"**Category:** {runbook_data.get('category', 'N/A')}  ",
                f"**Duration:** {runbook_data.get('estimated_duration', 'N/A')}\n"
            ])
            
            if 'prerequisites' in runbook_data:
                markdown_content.append("### Prerequisites\n")
                for prereq in runbook_data['prerequisites']:
                    markdown_content.append(f"- {prereq}")
                markdown_content.append("")
            
            if 'steps' in runbook_data:
                markdown_content.append("### Execution Steps\n")
                for step in runbook_data['steps']:
                    markdown_content.extend([
                        f"#### Step {step['step']}: {step['title']}",
                        f"**Duration:** {step['duration']}  ",
                        f"**Description:** {step['description']}\n",
                        "**Commands:**"
                    ])
                    for cmd in step.get('commands', []):
                        markdown_content.append(f"```bash\n{cmd}\n```")
                    
                    markdown_content.append("**Success Criteria:**")
                    for criteria in step.get('success_criteria', []):
                        markdown_content.append(f"- {criteria}")
                    markdown_content.append("")
        
        # Save markdown file
        markdown_file = self.documentation_path / "production_runbooks.md"
        with open(markdown_file, 'w') as f:
            f.write('\n'.join(markdown_content))
        
        print(f"📝 Markdown documentation saved: {markdown_file}")
        
        return '\n'.join(markdown_content)


def main():
    """Generate all production runbooks and documentation"""
    generator = ProductionRunbookGenerator()
    
    try:
        # Generate all runbooks
        runbooks = generator.generate_all_runbooks()
        
        # Generate markdown documentation
        markdown_doc = generator.generate_markdown_documentation(runbooks['runbooks'])
        
        print(f"\n📊 RUNBOOK GENERATION SUMMARY")
        print("=" * 50)
        print(f"Total Runbooks: {runbooks['summary']['total_runbooks']}")
        print(f"Documentation Path: {generator.documentation_path}")
        
        for category, runbook_list in runbooks['summary']['runbook_categories'].items():
            print(f"{category.title()} Runbooks: {len(runbook_list)}")
        
        print(f"\n🎯 KEY PROCEDURES:")
        for procedure in runbooks['summary']['key_procedures']:
            print(f"  • {procedure['name']}: {procedure['duration']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Runbook generation failed: {e}")
        return False


if __name__ == "__main__":
    main()