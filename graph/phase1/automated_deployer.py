#!/usr/bin/env python3
from config import get_database_config, get_ai_config, get_system_config
"""
Automated Deployment Orchestrator
Orchestrates the entire enhancement sequence automatically with checkpoints and rollback capabilities
"""

import json
import time
import subprocess
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from neo4j import GraphDatabase
from qdrant_client import QdrantClient


class DeploymentPhase(Enum):
    """Deployment phase enumeration"""
    PRE_DEPLOYMENT = "pre_deployment"
    PHASE2_GRAPH = "phase2_graph"
    VECTOR_EMBEDDING = "vector_embedding"
    VALIDATION = "validation"
    MONITORING_SETUP = "monitoring_setup"
    POST_DEPLOYMENT = "post_deployment"


class CheckpointStatus(Enum):
    """Checkpoint status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class DeploymentCheckpoint:
    """Deployment checkpoint configuration"""
    name: str
    phase: DeploymentPhase
    description: str
    script_command: str
    success_criteria: List[str]
    failure_actions: List[str]
    timeout_minutes: int = 30
    critical: bool = True
    rollback_on_failure: bool = True


@dataclass
class DeploymentResult:
    """Result of a deployment checkpoint"""
    checkpoint_name: str
    status: CheckpointStatus
    execution_time_seconds: float
    output: str
    error: Optional[str] = None
    timestamp: Optional[datetime] = None
    success_criteria_met: Optional[Dict] = None


class AutomatedDeploymentOrchestrator:
    """Orchestrates the complete deployment sequence automatically"""
    
    def __init__(self, dry_run: bool = False, skip_confirmations: bool = False):
        # Deployment configuration
        self.dry_run = dry_run
        self.skip_confirmations = skip_confirmations
        self.deployment_id = f"deployment_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Paths and directories
        self.working_directory = Path("/home/leo/AIStylist/graph/phase1")
        self.logs_directory = Path("./deployment_logs")
        self.logs_directory.mkdir(exist_ok=True)
        
        # Database connections (for validation)
        self.db_config = get_database_config()
        self.neo4j_url = self.db_config.neo4j_url
        self.neo4j_user = self.db_config.neo4j_user
        self.neo4j_password = self.db_config.neo4j_password
        
        self.qdrant_url = self.db_config.qdrant_url
        self.qdrant_api_key = self.db_config.qdrant_api_key
        
        # Deployment state
        self.current_phase = DeploymentPhase.PRE_DEPLOYMENT
        self.deployment_results = []
        self.deployment_start_time = None
        self.deployment_status = "initialized"
        
        # Define deployment checkpoints
        self.checkpoints = self._define_deployment_checkpoints()
        
        # Monitoring and logging
        self.log_file = self.logs_directory / f"{self.deployment_id}.log"
        self.monitoring_active = False
        self.monitoring_thread = None
        
    def _define_deployment_checkpoints(self) -> List[DeploymentCheckpoint]:
        """Define all deployment checkpoints in execution order"""
        return [
            # PRE-DEPLOYMENT PHASE
            DeploymentCheckpoint(
                name="pre_deployment_safety_check",
                phase=DeploymentPhase.PRE_DEPLOYMENT,
                description="Validate system safety and create backup",
                script_command="python rollback_safety_procedures.py --validate-safety phase2_deployment",
                success_criteria=[
                    "Safety validation passes with no blocking issues",
                    "System resources within acceptable limits",
                    "Database connections successful"
                ],
                failure_actions=[
                    "Address blocking safety issues",
                    "Stop deployment immediately"
                ],
                timeout_minutes=10,
                critical=True,
                rollback_on_failure=False
            ),
            DeploymentCheckpoint(
                name="create_system_backup",
                phase=DeploymentPhase.PRE_DEPLOYMENT,
                description="Create comprehensive system backup",
                script_command="python rollback_safety_procedures.py --create-backup automated_deployment_backup",
                success_criteria=[
                    "Backup completed successfully",
                    "Backup integrity validated",
                    "Backup size > 100MB"
                ],
                failure_actions=[
                    "Investigate backup failure",
                    "Stop deployment until backup succeeds"
                ],
                timeout_minutes=20,
                critical=True,
                rollback_on_failure=False
            ),
            
            # PHASE 2 GRAPH RECONSTRUCTION
            DeploymentCheckpoint(
                name="phase2_graph_reconstruction",
                phase=DeploymentPhase.PHASE2_GRAPH,
                description="Execute Phase 2 graph reconstruction",
                script_command="python prepare_phase2.py --execute --automated",
                success_criteria=[
                    "Color nodes created (>10)",
                    "Brand nodes created (>50)",
                    "Style nodes created (>20)",
                    "Product relationships created (>1M)",
                    "No critical errors"
                ],
                failure_actions=[
                    "Execute Phase 2 rollback",
                    "Investigate specific failures",
                    "Consider partial retry"
                ],
                timeout_minutes=180,  # 3 hours
                critical=True,
                rollback_on_failure=True
            ),
            DeploymentCheckpoint(
                name="validate_phase2_completion",
                phase=DeploymentPhase.PHASE2_GRAPH,
                description="Validate Phase 2 graph reconstruction results",
                script_command="python validate_phase2_completion.py --comprehensive --automated",
                success_criteria=[
                    "Node count validation passes",
                    "Relationship validation passes", 
                    "Data integrity checks pass",
                    "No orphaned nodes or relationships"
                ],
                failure_actions=[
                    "Review validation failures",
                    "Execute rollback if critical issues",
                    "Fix minor issues if possible"
                ],
                timeout_minutes=30,
                critical=True,
                rollback_on_failure=True
            ),
            DeploymentCheckpoint(
                name="phase2_performance_check",
                phase=DeploymentPhase.PHASE2_GRAPH,
                description="Verify performance impact of Phase 2 changes",
                script_command="python performance_benchmarking.py --suite neo4j_performance --automated",
                success_criteria=[
                    "Query performance within acceptable limits",
                    "No significant degradation (>50%)",
                    "System resources stable"
                ],
                failure_actions=[
                    "Investigate performance issues",
                    "Consider performance optimizations",
                    "Execute rollback if severe degradation"
                ],
                timeout_minutes=15,
                critical=False,
                rollback_on_failure=False
            ),
            
            # VECTOR RE-EMBEDDING PHASE
            DeploymentCheckpoint(
                name="pre_embedding_validation",
                phase=DeploymentPhase.VECTOR_EMBEDDING,
                description="Validate readiness for vector re-embedding",
                script_command="python rollback_safety_procedures.py --validate-safety vector_re_embedding",
                success_criteria=[
                    "Embedding safety checks pass",
                    "OpenAI API connectivity confirmed",
                    "Cost estimates within budget"
                ],
                failure_actions=[
                    "Resolve API connectivity issues",
                    "Confirm budget approval",
                    "Address safety concerns"
                ],
                timeout_minutes=10,
                critical=True,
                rollback_on_failure=False
            ),
            DeploymentCheckpoint(
                name="backup_qdrant_collection",
                phase=DeploymentPhase.VECTOR_EMBEDDING,
                description="Backup current Qdrant collection",
                script_command="python rollback_safety_procedures.py --create-backup qdrant_pre_reembedding",
                success_criteria=[
                    "Qdrant backup completed",
                    "Sample vectors exported"
                ],
                failure_actions=[
                    "Investigate backup failure",
                    "Ensure sufficient storage space"
                ],
                timeout_minutes=30,
                critical=True,
                rollback_on_failure=False
            ),
            DeploymentCheckpoint(
                name="execute_vector_reembedding",
                phase=DeploymentPhase.VECTOR_EMBEDDING,
                description="Execute complete vector re-embedding with UUID sync",
                script_command="python proper_embedding_with_uuid_sync.py --execute --batch-size 100 --automated",
                success_criteria=[
                    "All products re-embedded successfully",
                    "Perfect UUID correlation maintained",
                    "Vector count matches product count",
                    "No API timeout errors"
                ],
                failure_actions=[
                    "Resume from checkpoint if interrupted",
                    "Execute Qdrant rollback if critical failure",
                    "Monitor API costs and limits"
                ],
                timeout_minutes=360,  # 6 hours
                critical=True,
                rollback_on_failure=True
            ),
            DeploymentCheckpoint(
                name="validate_uuid_synchronization",
                phase=DeploymentPhase.VECTOR_EMBEDDING,
                description="Validate UUID synchronization after re-embedding",
                script_command="python validate_uuid_synchronization.py --comprehensive --automated",
                success_criteria=[
                    "UUID correlation accuracy >99%",
                    "No orphaned vectors",
                    "All products have corresponding vectors",
                    "Payload consistency maintained"
                ],
                failure_actions=[
                    "Investigate correlation failures",
                    "Re-run embedding for failed products",
                    "Execute rollback if correlation <95%"
                ],
                timeout_minutes=30,
                critical=True,
                rollback_on_failure=True
            ),
            
            # SYSTEM VALIDATION PHASE
            DeploymentCheckpoint(
                name="search_quality_validation",
                phase=DeploymentPhase.VALIDATION,
                description="Validate search functionality and quality",
                script_command="python validate_search_quality.py --full-suite --automated",
                success_criteria=[
                    "All search quality tests pass",
                    "Color searches return correct results",
                    "Brand searches work correctly",
                    "Multi-attribute searches function properly"
                ],
                failure_actions=[
                    "Investigate search quality issues",
                    "Debug specific test failures",
                    "Consider partial rollback"
                ],
                timeout_minutes=30,
                critical=True,
                rollback_on_failure=False
            ),
            DeploymentCheckpoint(
                name="comprehensive_performance_validation",
                phase=DeploymentPhase.VALIDATION,
                description="Run comprehensive performance benchmarks",
                script_command="python performance_benchmarking.py --comprehensive --automated",
                success_criteria=[
                    "All performance benchmarks pass",
                    "Response times within targets",
                    "System throughput acceptable",
                    "Concurrent load handling verified"
                ],
                failure_actions=[
                    "Investigate performance regressions",
                    "Optimize slow queries",
                    "Consider system resource scaling"
                ],
                timeout_minutes=45,
                critical=False,
                rollback_on_failure=False
            ),
            DeploymentCheckpoint(
                name="live_integration_testing",
                phase=DeploymentPhase.VALIDATION,
                description="Run live integration tests",
                script_command="python live_integration_test.py --automated",
                success_criteria=[
                    "Integration tests pass",
                    "End-to-end workflows functional",
                    "Database correlation working"
                ],
                failure_actions=[
                    "Debug integration failures",
                    "Verify database connections",
                    "Check system configuration"
                ],
                timeout_minutes=20,
                critical=True,
                rollback_on_failure=False
            ),
            DeploymentCheckpoint(
                name="api_integration_readiness",
                phase=DeploymentPhase.VALIDATION,
                description="Validate API integration readiness",
                script_command="python api_integration_prep.py --validate-readiness --automated",
                success_criteria=[
                    "API integration validation passes",
                    "All required data available",
                    "Schema validation successful"
                ],
                failure_actions=[
                    "Address API readiness issues",
                    "Verify data completeness",
                    "Update schemas if needed"
                ],
                timeout_minutes=15,
                critical=False,
                rollback_on_failure=False
            ),
            
            # PRODUCTION MONITORING SETUP
            DeploymentCheckpoint(
                name="initialize_production_monitoring",
                phase=DeploymentPhase.MONITORING_SETUP,
                description="Initialize production monitoring system",
                script_command="python production_monitoring.py --initialize --automated",
                success_criteria=[
                    "Monitoring initialized successfully",
                    "Alert system functional",
                    "Baseline metrics established"
                ],
                failure_actions=[
                    "Debug monitoring setup issues",
                    "Verify monitoring configuration",
                    "Test alert notifications"
                ],
                timeout_minutes=15,
                critical=False,
                rollback_on_failure=False
            ),
            
            # POST-DEPLOYMENT VALIDATION
            DeploymentCheckpoint(
                name="final_system_health_check",
                phase=DeploymentPhase.POST_DEPLOYMENT,
                description="Final comprehensive system health validation",
                script_command="python production_monitoring.py --comprehensive-health-check --automated",
                success_criteria=[
                    "All systems healthy",
                    "Performance within normal ranges",
                    "No critical alerts active",
                    "All major functionality verified"
                ],
                failure_actions=[
                    "Investigate health issues",
                    "Address any critical problems",
                    "Document any remaining issues"
                ],
                timeout_minutes=20,
                critical=True,
                rollback_on_failure=False
            )
        ]
    
    def connect_databases(self):
        """Connect to databases for validation"""
        print("🔌 Connecting to databases for deployment validation...")
        
        self.neo4j_driver = GraphDatabase.driver(
            self.neo4j_url,
            auth=(self.neo4j_user, self.neo4j_password)
        )
        
        self.qdrant_client = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key
        )
        
        print("✅ Database connections established")
    
    def log_message(self, message: str, level: str = "INFO"):
        """Log message to console and file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] {level}: {message}"
        
        print(formatted_message)
        
        with open(self.log_file, 'a') as f:
            f.write(formatted_message + '\n')
    
    def execute_checkpoint(self, checkpoint: DeploymentCheckpoint) -> DeploymentResult:
        """Execute a single deployment checkpoint"""
        self.log_message(f"🔄 Executing checkpoint: {checkpoint.name}")
        self.log_message(f"   Description: {checkpoint.description}")
        
        if self.dry_run:
            self.log_message("   🔍 DRY RUN: Simulating checkpoint execution")
            return DeploymentResult(
                checkpoint_name=checkpoint.name,
                status=CheckpointStatus.PASSED,
                execution_time_seconds=1.0,
                output="DRY RUN: Checkpoint simulated successfully",
                timestamp=datetime.now()
            )
        
        start_time = time.time()
        
        try:
            # Execute the checkpoint command
            self.log_message(f"   Command: {checkpoint.script_command}")
            
            # Change to working directory
            original_cwd = Path.cwd()
            if self.working_directory.exists():
                import os
                os.chdir(self.working_directory)
            
            # Run the command with timeout
            result = subprocess.run(
                checkpoint.script_command.split(),
                capture_output=True,
                text=True,
                timeout=checkpoint.timeout_minutes * 60,
                cwd=self.working_directory
            )
            
            # Restore original directory
            import os
            os.chdir(original_cwd)
            
            execution_time = time.time() - start_time
            
            # Check if command was successful
            if result.returncode == 0:
                # Validate success criteria
                success_criteria_met = self._validate_success_criteria(checkpoint, result.stdout)
                
                if success_criteria_met['all_met']:
                    self.log_message(f"   ✅ Checkpoint PASSED: {checkpoint.name}")
                    return DeploymentResult(
                        checkpoint_name=checkpoint.name,
                        status=CheckpointStatus.PASSED,
                        execution_time_seconds=execution_time,
                        output=result.stdout,
                        timestamp=datetime.now(),
                        success_criteria_met=success_criteria_met
                    )
                else:
                    self.log_message(f"   ⚠️ Checkpoint FAILED: Success criteria not met")
                    return DeploymentResult(
                        checkpoint_name=checkpoint.name,
                        status=CheckpointStatus.FAILED,
                        execution_time_seconds=execution_time,
                        output=result.stdout,
                        error="Success criteria not met",
                        timestamp=datetime.now(),
                        success_criteria_met=success_criteria_met
                    )
            else:
                self.log_message(f"   ❌ Checkpoint FAILED: Command returned {result.returncode}")
                return DeploymentResult(
                    checkpoint_name=checkpoint.name,
                    status=CheckpointStatus.FAILED,
                    execution_time_seconds=execution_time,
                    output=result.stdout,
                    error=result.stderr,
                    timestamp=datetime.now()
                )
                
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            self.log_message(f"   ⏰ Checkpoint TIMEOUT: {checkpoint.name} after {checkpoint.timeout_minutes} minutes")
            return DeploymentResult(
                checkpoint_name=checkpoint.name,
                status=CheckpointStatus.FAILED,
                execution_time_seconds=execution_time,
                output="",
                error=f"Timeout after {checkpoint.timeout_minutes} minutes",
                timestamp=datetime.now()
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.log_message(f"   💥 Checkpoint ERROR: {checkpoint.name} - {str(e)}")
            return DeploymentResult(
                checkpoint_name=checkpoint.name,
                status=CheckpointStatus.FAILED,
                execution_time_seconds=execution_time,
                output="",
                error=str(e),
                timestamp=datetime.now()
            )
    
    def _validate_success_criteria(self, checkpoint: DeploymentCheckpoint, output: str) -> Dict:
        """Validate checkpoint success criteria"""
        validation_result = {
            'all_met': True,
            'criteria_results': {},
            'met_count': 0,
            'total_count': len(checkpoint.success_criteria)
        }
        
        # Basic validation based on output content and checkpoint type
        for criteria in checkpoint.success_criteria:
            criteria_met = False
            
            # Simple heuristic validation based on criteria text
            if "passes" in criteria.lower() or "successful" in criteria.lower():
                criteria_met = "pass" in output.lower() or "success" in output.lower() or "✅" in output
            elif "error" in criteria.lower():
                criteria_met = "error" not in output.lower() and "❌" not in output
            elif "created" in criteria.lower():
                criteria_met = "created" in output.lower() or "generated" in output.lower()
            elif "connectivity" in criteria.lower():
                criteria_met = "connected" in output.lower() or "connection" in output.lower()
            else:
                # Default: assume criteria is met if no obvious failure indicators
                criteria_met = "error" not in output.lower() and "failed" not in output.lower()
            
            validation_result['criteria_results'][criteria] = criteria_met
            if criteria_met:
                validation_result['met_count'] += 1
            else:
                validation_result['all_met'] = False
        
        return validation_result
    
    def handle_checkpoint_failure(self, checkpoint: DeploymentCheckpoint, result: DeploymentResult) -> bool:
        """Handle checkpoint failure and decide whether to continue or rollback"""
        self.log_message(f"🚨 Handling failure for checkpoint: {checkpoint.name}", "ERROR")
        
        # If it's not critical, we can potentially continue
        if not checkpoint.critical:
            self.log_message("   ⚠️ Non-critical checkpoint failed - continuing deployment")
            return True  # Continue deployment
        
        # For critical checkpoints, decide based on rollback policy
        if checkpoint.rollback_on_failure:
            self.log_message("   🔄 Critical checkpoint failed - executing rollback")
            
            if not self.skip_confirmations and not self.dry_run:
                response = input("Critical checkpoint failed. Execute rollback? (y/n): ")
                if response.lower() != 'y':
                    self.log_message("   ⏹️ User chose not to rollback - stopping deployment")
                    return False
            
            # Execute appropriate rollback
            rollback_success = self._execute_rollback(checkpoint.phase)
            if rollback_success:
                self.log_message("   ✅ Rollback completed successfully")
            else:
                self.log_message("   ❌ Rollback failed - manual intervention required", "ERROR")
            
            return False  # Stop deployment
        else:
            # Critical but no rollback - just stop
            self.log_message("   ⏹️ Critical checkpoint failed - stopping deployment")
            return False
    
    def _execute_rollback(self, failed_phase: DeploymentPhase) -> bool:
        """Execute appropriate rollback based on failed phase"""
        self.log_message(f"🔄 Executing rollback for phase: {failed_phase.value}")
        
        try:
            if failed_phase == DeploymentPhase.PHASE2_GRAPH:
                # Rollback Phase 2 changes
                rollback_command = "python rollback_safety_procedures.py --execute-rollback automated_deployment_backup --scope neo4j"
            elif failed_phase == DeploymentPhase.VECTOR_EMBEDDING:
                # Rollback vector changes
                rollback_command = "python rollback_safety_procedures.py --execute-rollback qdrant_pre_reembedding --scope qdrant"
            else:
                # General system rollback
                rollback_command = "python rollback_safety_procedures.py --execute-rollback automated_deployment_backup --scope full"
            
            if self.dry_run:
                self.log_message(f"   🔍 DRY RUN: Would execute rollback: {rollback_command}")
                return True
            
            # Execute rollback command
            result = subprocess.run(
                rollback_command.split(),
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minutes timeout for rollback
                cwd=self.working_directory
            )
            
            if result.returncode == 0:
                self.log_message("   ✅ Rollback command completed successfully")
                return True
            else:
                self.log_message(f"   ❌ Rollback command failed: {result.stderr}", "ERROR")
                return False
                
        except Exception as e:
            self.log_message(f"   💥 Rollback execution error: {str(e)}", "ERROR")
            return False
    
    def run_deployment(self) -> Dict:
        """Run the complete deployment sequence"""
        self.log_message("🚀 Starting Automated Deployment Orchestration")
        self.log_message(f"   Deployment ID: {self.deployment_id}")
        self.log_message(f"   Working Directory: {self.working_directory}")
        self.log_message(f"   Dry Run: {self.dry_run}")
        self.log_message("=" * 60)
        
        self.deployment_start_time = datetime.now()
        self.deployment_status = "running"
        
        # Start monitoring thread
        self._start_monitoring()
        
        deployment_report = {
            'deployment_id': self.deployment_id,
            'start_time': self.deployment_start_time.isoformat(),
            'dry_run': self.dry_run,
            'checkpoints': {},
            'summary': {}
        }
        
        try:
            # Execute each checkpoint in sequence
            total_checkpoints = len(self.checkpoints)
            completed_checkpoints = 0
            failed_checkpoints = 0
            
            for i, checkpoint in enumerate(self.checkpoints):
                self.current_phase = checkpoint.phase
                
                # Show progress
                progress = (i / total_checkpoints) * 100
                self.log_message(f"📊 Progress: {progress:.1f}% ({i}/{total_checkpoints})")
                
                # Execute checkpoint
                result = self.execute_checkpoint(checkpoint)
                self.deployment_results.append(result)
                
                # Store result in report
                deployment_report['checkpoints'][checkpoint.name] = {
                    'phase': checkpoint.phase.value,
                    'description': checkpoint.description,
                    'status': result.status.value,
                    'execution_time_seconds': result.execution_time_seconds,
                    'timestamp': result.timestamp.isoformat() if result.timestamp else None,
                    'error': result.error,
                    'success_criteria_met': result.success_criteria_met
                }
                
                # Handle results
                if result.status == CheckpointStatus.PASSED:
                    completed_checkpoints += 1
                    self.log_message(f"   ✅ Checkpoint completed successfully")
                elif result.status == CheckpointStatus.FAILED:
                    failed_checkpoints += 1
                    
                    # Handle failure
                    continue_deployment = self.handle_checkpoint_failure(checkpoint, result)
                    if not continue_deployment:
                        self.deployment_status = "failed"
                        break
                
                # Brief pause between checkpoints
                if not self.dry_run:
                    time.sleep(2)
            
            # Calculate final status
            if self.deployment_status != "failed":
                if failed_checkpoints == 0:
                    self.deployment_status = "completed_successfully"
                elif failed_checkpoints <= 2:  # Allow minor failures
                    self.deployment_status = "completed_with_warnings"
                else:
                    self.deployment_status = "completed_with_errors"
            
            # Generate summary
            deployment_end_time = datetime.now()
            total_duration = (deployment_end_time - self.deployment_start_time).total_seconds()
            
            deployment_report['summary'] = {
                'status': self.deployment_status,
                'end_time': deployment_end_time.isoformat(),
                'total_duration_seconds': total_duration,
                'total_checkpoints': total_checkpoints,
                'completed_checkpoints': completed_checkpoints,
                'failed_checkpoints': failed_checkpoints,
                'success_rate': (completed_checkpoints / total_checkpoints * 100) if total_checkpoints > 0 else 0
            }
            
            self.log_message("\n🎯 DEPLOYMENT SUMMARY")
            self.log_message("=" * 40)
            self.log_message(f"Status: {self.deployment_status.upper()}")
            self.log_message(f"Duration: {total_duration/3600:.1f} hours")
            self.log_message(f"Success Rate: {deployment_report['summary']['success_rate']:.1f}%")
            self.log_message(f"Completed: {completed_checkpoints}/{total_checkpoints} checkpoints")
            
            if self.deployment_status == "completed_successfully":
                self.log_message("🎉 DEPLOYMENT COMPLETED SUCCESSFULLY!")
            elif "completed" in self.deployment_status:
                self.log_message("⚠️ DEPLOYMENT COMPLETED WITH ISSUES - Review required")
            else:
                self.log_message("❌ DEPLOYMENT FAILED - System may require manual recovery")
            
            return deployment_report
            
        except Exception as e:
            self.log_message(f"💥 CRITICAL DEPLOYMENT ERROR: {str(e)}", "ERROR")
            self.deployment_status = "critical_failure"
            deployment_report['summary'] = {
                'status': self.deployment_status,
                'error': str(e)
            }
            return deployment_report
            
        finally:
            self._stop_monitoring()
            self._save_deployment_report(deployment_report)
    
    def _start_monitoring(self):
        """Start deployment monitoring thread"""
        self.monitoring_active = True
        
        def monitoring_loop():
            while self.monitoring_active:
                try:
                    # Monitor system health during deployment
                    if hasattr(self, 'neo4j_driver'):
                        # Quick health check
                        with self.neo4j_driver.session() as session:
                            result = session.run("RETURN 1 as health")
                            if not result.single():
                                self.log_message("⚠️ Neo4j connectivity issue detected", "WARNING")
                    
                    time.sleep(60)  # Check every minute
                    
                except Exception as e:
                    self.log_message(f"Monitoring error: {e}", "WARNING")
                    time.sleep(60)
        
        self.monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self.monitoring_thread.start()
    
    def _stop_monitoring(self):
        """Stop deployment monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
    
    def _save_deployment_report(self, report: Dict):
        """Save deployment report to file"""
        report_file = self.logs_directory / f"{self.deployment_id}_report.json"
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        self.log_message(f"💾 Deployment report saved: {report_file}")
    
    def get_deployment_status(self) -> Dict:
        """Get current deployment status"""
        if not self.deployment_start_time:
            return {'status': 'not_started'}
        
        current_time = datetime.now()
        elapsed_time = (current_time - self.deployment_start_time).total_seconds()
        
        completed_checkpoints = len([r for r in self.deployment_results if r.status == CheckpointStatus.PASSED])
        failed_checkpoints = len([r for r in self.deployment_results if r.status == CheckpointStatus.FAILED])
        
        return {
            'deployment_id': self.deployment_id,
            'status': self.deployment_status,
            'current_phase': self.current_phase.value if self.current_phase else None,
            'elapsed_time_seconds': elapsed_time,
            'progress': {
                'total_checkpoints': len(self.checkpoints),
                'completed': completed_checkpoints,
                'failed': failed_checkpoints,
                'remaining': len(self.checkpoints) - completed_checkpoints - failed_checkpoints
            }
        }


def main():
    """Run automated deployment orchestration"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Automated Deployment Orchestrator")
    parser.add_argument('--dry-run', action='store_true', help='Simulate deployment without executing commands')
    parser.add_argument('--skip-confirmations', action='store_true', help='Skip user confirmations (use with caution)')
    parser.add_argument('--status', action='store_true', help='Check status of running deployment')
    
    args = parser.parse_args()
    
    if args.status:
        # Check for running deployment
        logs_dir = Path("./deployment_logs")
        if logs_dir.exists():
            recent_logs = sorted(logs_dir.glob("deployment_*.log"))
            if recent_logs:
                print(f"Most recent deployment log: {recent_logs[-1]}")
                with open(recent_logs[-1], 'r') as f:
                    lines = f.readlines()
                    print("Last 10 log lines:")
                    for line in lines[-10:]:
                        print(line.strip())
        return
    
    # Create and run orchestrator
    orchestrator = AutomatedDeploymentOrchestrator(
        dry_run=args.dry_run,
        skip_confirmations=args.skip_confirmations
    )
    
    try:
        # Connect to databases for validation
        orchestrator.connect_databases()
        
        # Run deployment
        report = orchestrator.run_deployment()
        
        # Return appropriate exit code
        if report['summary'].get('status') == 'completed_successfully':
            return 0
        elif 'completed' in report['summary'].get('status', ''):
            return 1  # Completed with issues
        else:
            return 2  # Failed
            
    except Exception as e:
        print(f"❌ Orchestrator failed to start: {e}")
        return 3
    
    finally:
        if hasattr(orchestrator, 'neo4j_driver'):
            orchestrator.neo4j_driver.close()


if __name__ == "__main__":
    exit(main())