#!/usr/bin/env python3
"""
Fashion Classification Pipeline v3
- Fixed double-counting bug
- Better stuck batch handling
- Accurate progress tracking
- Force completion for stuck batches
- Better error recovery
"""

import os
import json
import time
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple
import pandas as pd
from tqdm import tqdm
import openai
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from dotenv import load_dotenv
import logging
import math
import traceback
from dataclasses import dataclass, field
from collections import defaultdict
import hashlib

load_dotenv()

# Enhanced logging
log_dir = Path('./fashion_classification_pipeline/logs')
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / f'classifier_v3_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration with bug fixes
CONFIG = {
    'neo4j': {
        'url': os.getenv('NEO4J_URL', 'bolt://34.135.40.119:7687'),
        'username': os.getenv('NEO4J_USERNAME', 'neo4j'),
        'password': os.getenv('NEO4J_PASSWORD', 'shopari1234')
    },
    'openai': {
        'api_key': os.getenv('OPENAI_API_KEY'),
        'max_queue_tokens': 20_000_000,
        'tokens_per_request': 300,
        'safety_margin': 0.80,
        'model': 'gpt-4o-mini',
        'temperature': 0.1,
        'cost_per_1k_tokens': {
            'input': 0.00015,
            'output': 0.00060
        }
    },
    'qdrant': {
        'url': os.getenv('QDRANT_URL', 'https://9ac8ffa1-c5b7-47e2-a832-3ce559f42042.us-east4-0.gcp.cloud.qdrant.io'),
        'api_key': os.getenv('QDRANT_API_KEY'),
        'collection': 'fashion_products'
    },
    'batch': {
        'output_dir': './fashion_classification_pipeline',
        'requests_per_file': 2000,
        'db_chunk_size': 5000,
        'check_interval': 60,
        'max_concurrent_batches': 20,
        'batch_timeout_hours': 24,
        'stuck_batch_timeout_hours': 2,  # NEW: Force timeout for stuck batches
        'retry_failed_batches': True,
        'max_retries': 3
    },
    'classification': {
        'confidence_thresholds': {
            'high': 0.85,
            'medium': 0.70,
            'low': 0.50
        },
        'removal_threshold': 0.90,
        'manual_review_threshold': 0.70,
        'enable_removal': True,
        'archive_before_removal': True
    },
    'recovery': {
        'enable_force_completion': True,  # NEW: Allow forcing stuck batches
        'check_result_files_first': True,  # NEW: Check if results exist before API
        'skip_problematic_batches': True   # NEW: Skip batches that repeatedly fail
    }
}

# Category-specific prompts
CATEGORY_PROMPTS = {
    'beauty': """This is a Beauty category product. Note that:
- Fashion items: fashion-forward sunglasses, cosmetic bags, beauty organizers that are stylish accessories
- Non-fashion: makeup, skincare, fragrances, beauty tools, hair care products""",
    
    'sports': """This is a Sports category product. Note that:
- Fashion items: athletic wear, sports apparel, athletic shoes, gym bags, sports fashion
- Non-fashion: equipment, gear, tools, machines, accessories for sports (not worn)""",
    
    'travel': """This is a Travel category product. Note that:
- Fashion items: luggage, travel bags, passport holders, travel pouches (stylish/carried)
- Non-fashion: adapters, locks, travel gadgets, maps, guides""",
    
    'accessories': """This is an Accessories category product. Carefully distinguish:
- Fashion accessories: bags, belts, scarves, hats, fashion jewelry, wallets
- Non-fashion accessories: phone cases, computer accessories, home accessories"""
}


@dataclass
class BatchInfo:
    """Enhanced batch information"""
    filename: str
    path: str
    request_count: int
    status: str
    created_at: str
    batch_id: Optional[str] = None
    file_id: Optional[str] = None
    submitted_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    product_ids: List[str] = field(default_factory=list)
    estimated_cost: float = 0.0
    actual_cost: Optional[float] = None
    last_checked: Optional[str] = None  # NEW: Track when we last checked
    products_processed: int = 0  # NEW: Track actual processed count


class FashionClassifierV3:
    """Version 3 with bug fixes and better recovery"""
    
    def __init__(self):
        logger.info("Initializing Fashion Classifier v3 with bug fixes")
        
        # API clients
        self.client = openai.OpenAI(api_key=CONFIG['openai']['api_key'])
        self.neo4j_driver = GraphDatabase.driver(
            CONFIG['neo4j']['url'],
            auth=(CONFIG['neo4j']['username'], CONFIG['neo4j']['password'])
        )
        self.qdrant = QdrantClient(
            url=CONFIG['qdrant']['url'],
            api_key=CONFIG['qdrant']['api_key']
        )
        
        # Directory structure
        self.base_dir = Path(CONFIG['batch']['output_dir'])
        self.batch_dir = self.base_dir / 'batches'
        self.results_dir = self.base_dir / 'results'
        self.archive_dir = self.base_dir / 'archive'
        self.reports_dir = self.base_dir / 'reports'
        self.checkpoints_dir = self.base_dir / 'checkpoints'
        self.manual_review_dir = self.base_dir / 'manual_review'
        
        for dir in [self.batch_dir, self.results_dir, self.archive_dir, 
                    self.reports_dir, self.checkpoints_dir, self.manual_review_dir]:
            dir.mkdir(parents=True, exist_ok=True)
        
        # State management - v3 uses different file to avoid conflicts
        self.state_file = self.base_dir / 'pipeline_state_v3.json'
        self.state = self._load_state()
        
        # Product tracking
        self.processed_products_file = self.base_dir / 'processed_products_v3.json'
        self.processed_products = self._load_processed_products()
        
        # Statistics - fixed to avoid double counting
        self.stats = defaultdict(int)
        self.actual_counts = {
            'fashion': 0,
            'non_fashion': 0,
            'uncertain': 0,
            'manual_review': 0
        }
        
        # Calculate optimal parameters
        self._calculate_optimal_parameters()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load or initialize pipeline state"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    logger.info(f"Resumed from previous state: {state['current_phase']}")
                    # Migrate old state if needed
                    if 'actual_processed' not in state:
                        state['actual_processed'] = state.get('processed_products', 0)
                    return state
            except Exception as e:
                logger.warning(f"Could not load state file: {e}")
        
        return {
            'run_id': datetime.now().strftime('%Y%m%d_%H%M%S'),
            'status': 'initialized',
            'start_time': datetime.now().isoformat(),
            'total_products': 0,
            'needs_ai_products': 0,
            'processed_products': 0,  # This will track batch completion
            'actual_processed': 0,  # NEW: Track actual DB updates
            'fashion_products': 0,
            'non_fashion_products': 0,
            'uncertain_products': 0,
            'manual_review_products': 0,
            'batches': {},
            'current_phase': 'validation',
            'checkpoints': [],
            'errors': [],
            'warnings': [],
            'stuck_batches': []  # NEW: Track problematic batches
        }
    
    def _load_processed_products(self) -> Set[str]:
        """Load set of already processed product IDs"""
        if self.processed_products_file.exists():
            try:
                with open(self.processed_products_file, 'r') as f:
                    return set(json.load(f))
            except:
                pass
        return set()
    
    def _calculate_optimal_parameters(self):
        """Calculate optimal batch parameters"""
        max_tokens = CONFIG['openai']['max_queue_tokens'] * CONFIG['openai']['safety_margin']
        tokens_per_request = CONFIG['openai']['tokens_per_request']
        requests_per_batch = CONFIG['batch']['requests_per_file']
        
        tokens_per_batch = requests_per_batch * tokens_per_request
        max_concurrent = int(max_tokens / tokens_per_batch)
        
        CONFIG['batch']['max_concurrent_batches'] = min(
            max_concurrent,
            CONFIG['batch']['max_concurrent_batches']
        )
        
        logger.info("=== Optimal Parameters ===")
        logger.info(f"Max concurrent batches: {CONFIG['batch']['max_concurrent_batches']}")
        logger.info(f"Requests per batch: {requests_per_batch:,}")
        logger.info(f"Est. tokens per batch: {tokens_per_batch:,}")
    
    async def run(self):
        """Main pipeline execution"""
        logger.info("="*60)
        logger.info("Starting Fashion Classification Pipeline v3")
        logger.info(f"Run ID: {self.state['run_id']}")
        logger.info("="*60)
        
        try:
            # Phase 1: Validation
            if self.state['current_phase'] == 'validation':
                if not await self._phase1_validation():
                    logger.error("Validation failed!")
                    return
                self.state['current_phase'] = 'preparation'
                self._save_state()
            
            # Phase 2: Preparation (skip if resuming)
            if self.state['current_phase'] == 'preparation':
                if not self.state['batches']:  # Only prepare if no batches exist
                    await self._phase2_prepare_batches()
                else:
                    logger.info("Skipping preparation - batches already exist")
                self.state['current_phase'] = 'processing'
                self._save_state()
            
            # Phase 3: Processing with better recovery
            if self.state['current_phase'] == 'processing':
                await self._phase3_process_batches_with_recovery()
                self.state['current_phase'] = 'review'
                self._save_state()
            
            # Phase 4: Manual Review Export
            if self.state['current_phase'] == 'review':
                await self._phase4_export_review()
                self.state['current_phase'] = 'finalization'
                self._save_state()
            
            # Phase 5: Finalization
            if self.state['current_phase'] == 'finalization':
                await self._phase5_finalize()
                self.state['current_phase'] = 'complete'
                self._save_state()
            
            logger.info("\n✅ Pipeline completed successfully!")
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            logger.error(traceback.format_exc())
            self.state['errors'].append({
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'phase': self.state['current_phase'],
                'traceback': traceback.format_exc()
            })
            self._save_state()
            raise
        finally:
            self.neo4j_driver.close()
    
    async def _phase1_validation(self) -> bool:
        """Validate database state"""
        logger.info("\n=== PHASE 1: Validation ===")
        
        with self.neo4j_driver.session() as session:
            result = session.run("""
                MATCH (p:Product)
                RETURN 
                    count(p) as total,
                    sum(CASE WHEN p:NeedsAI THEN 1 ELSE 0 END) as needs_ai,
                    sum(CASE WHEN p:FashionProduct THEN 1 ELSE 0 END) as fashion,
                    sum(CASE WHEN p:MarkedForRemoval THEN 1 ELSE 0 END) as marked_removal,
                    sum(CASE WHEN p.classified_at IS NOT NULL THEN 1 ELSE 0 END) as already_classified
            """).single()
            
            total = result['total']
            needs_ai = result['needs_ai']
            
            logger.info(f"Database Status:")
            logger.info(f"  Total products: {total:,}")
            logger.info(f"  Needs AI classification: {needs_ai:,}")
            logger.info(f"  Already marked as fashion: {result['fashion']:,}")
            logger.info(f"  Already classified by AI: {result['already_classified']:,}")
            
            if needs_ai == 0:
                logger.error("No products found with :NeedsAI label!")
                return False
            
            # Update state
            self.state['total_products'] = total
            self.state['needs_ai_products'] = needs_ai
            self._save_state()
            
            return True
    
    async def _phase2_prepare_batches(self):
        """Prepare batch files"""
        logger.info("\n=== PHASE 2: Batch Preparation ===")
        
        # Get unprocessed NeedsAI products
        with self.neo4j_driver.session() as session:
            count_query = """
                MATCH (p:Product:NeedsAI)
                WHERE p.classified_at IS NULL
                RETURN count(p) as total
            """
            
            result = session.run(count_query).single()
            unprocessed_count = result['total']
        
        if unprocessed_count == 0:
            logger.info("No unprocessed NeedsAI products found!")
            return
        
        logger.info(f"Products to process: {unprocessed_count:,}")
        
        # Prompt template
        base_prompt = """Classify this product as fashion or non-fashion.

Product Information:
{product_info}

{category_specific_guidance}

Fashion items include: clothing, footwear, fashion accessories, fashion bags/jewelry
Non-fashion items include: home goods, electronics, tools, sports equipment, beauty products

Respond with ONLY a JSON object:
{{
    "is_fashion": true/false,
    "confidence": 0.0-1.0,
    "category": "specific category or null",
    "reasoning": "brief explanation (max 50 words)"
}}"""
        
        # Process in batches
        batch_num = 0
        processed = 0
        current_batch = []
        
        estimated_cost = self._estimate_cost(unprocessed_count)
        logger.info(f"Estimated API cost: ${estimated_cost:.2f}")
        
        with tqdm(total=unprocessed_count, desc="Creating batches") as pbar:
            while processed < unprocessed_count:
                with self.neo4j_driver.session() as session:
                    query = """
                    MATCH (p:Product:NeedsAI)
                    WHERE p.classified_at IS NULL
                    WITH p SKIP $skip LIMIT $limit
                    OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
                    OPTIONAL MATCH (p)-[:BY_BRAND]->(b:Brand)
                    RETURN p, c.name as category, b.name as brand
                    """
                    
                    results = session.run(
                        query,
                        skip=processed,
                        limit=CONFIG['batch']['db_chunk_size']
                    )
                    
                    chunk_count = 0
                    for record in results:
                        product = dict(record['p'])
                        product['category'] = record['category']
                        product['brand'] = record['brand']
                        
                        # Create request
                        request = self._create_enhanced_request(product, base_prompt)
                        current_batch.append(request)
                        chunk_count += 1
                        
                        # Save batch when full
                        if len(current_batch) >= CONFIG['batch']['requests_per_file']:
                            self._save_batch(batch_num, current_batch)
                            batch_num += 1
                            current_batch = []
                        
                        pbar.update(1)
                    
                    if chunk_count == 0:
                        break
                
                processed += CONFIG['batch']['db_chunk_size']
        
        # Save final batch
        if current_batch:
            self._save_batch(batch_num, current_batch)
        
        logger.info(f"\n✓ Created {len(self.state['batches'])} batch files")
    
    def _create_enhanced_request(self, product: Dict, base_prompt: str) -> Dict:
        """Create classification request"""
        info_parts = []
        
        if product.get('id'):
            info_parts.append(f"ID: {product['id']}")
        if product.get('title'):
            info_parts.append(f"Title: {product['title']}")
        if product.get('description'):
            desc = self._smart_truncate(product.get('description', ''), 400)
            info_parts.append(f"Description: {desc}")
        if product.get('category'):
            info_parts.append(f"Category: {product['category']}")
        if product.get('brand'):
            info_parts.append(f"Brand: {product['brand']}")
        if product.get('price'):
            info_parts.append(f"Price: ${product['price']}")
        
        product_info = "\n".join(info_parts)
        
        # Add category-specific guidance
        category_guidance = ""
        if product.get('category'):
            category_lower = product['category'].lower()
            for key, guidance in CATEGORY_PROMPTS.items():
                if key in category_lower:
                    category_guidance = guidance
                    break
        
        prompt = base_prompt.format(
            product_info=product_info,
            category_specific_guidance=category_guidance
        )
        
        return {
            "custom_id": f"product_{product['id']}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": CONFIG['openai']['model'],
                "messages": [{
                    "role": "user",
                    "content": prompt
                }],
                "temperature": CONFIG['openai']['temperature'],
                "response_format": {"type": "json_object"},
                "max_tokens": 100
            }
        }
    
    def _smart_truncate(self, text: str, max_length: int) -> str:
        """Intelligently truncate text"""
        if len(text) <= max_length:
            return text
        
        truncated = text[:max_length]
        last_period = truncated.rfind('.')
        if last_period > max_length * 0.8:
            return truncated[:last_period + 1]
        
        last_space = truncated.rfind(' ')
        if last_space > max_length * 0.9:
            return truncated[:last_space] + '...'
        
        return truncated + '...'
    
    def _estimate_cost(self, request_count: int) -> float:
        """Estimate API costs"""
        tokens_per_request = CONFIG['openai']['tokens_per_request']
        input_tokens = request_count * tokens_per_request * 0.8
        output_tokens = request_count * tokens_per_request * 0.2
        
        input_cost = (input_tokens / 1000) * CONFIG['openai']['cost_per_1k_tokens']['input']
        output_cost = (output_tokens / 1000) * CONFIG['openai']['cost_per_1k_tokens']['output']
        
        return input_cost + output_cost
    
    def _save_batch(self, batch_num: int, requests: List[Dict]):
        """Save batch file"""
        filename = f"batch_{batch_num:05d}.jsonl"
        filepath = self.batch_dir / filename
        
        product_ids = [r['custom_id'].replace('product_', '') for r in requests]
        
        with open(filepath, 'w') as f:
            for request in requests:
                f.write(json.dumps(request) + '\n')
        
        # Create batch info
        batch_info = {
            'path': str(filepath),
            'request_count': len(requests),
            'status': 'created',
            'created_at': datetime.now().isoformat(),
            'product_ids': product_ids,
            'estimated_cost': self._estimate_cost(len(requests)),
            'products_processed': 0  # NEW: Track actual processed
        }
        
        self.state['batches'][filename] = batch_info
        self._save_state()
    
    async def _phase3_process_batches_with_recovery(self):
        """Process batches with better recovery mechanisms"""
        logger.info("\n=== PHASE 3: Batch Processing with Recovery ===")
        
        total_batches = len(self.state['batches'])
        if total_batches == 0:
            logger.info("No batches to process!")
            return
        
        logger.info(f"Total batches: {total_batches}")
        
        # First, check for any completed batches we haven't processed
        await self._recover_completed_batches()
        
        # Count current status
        completed = sum(1 for b in self.state['batches'].values() if b['status'] == 'completed')
        failed = sum(1 for b in self.state['batches'].values() 
                    if b['status'] == 'failed' and b.get('retry_count', 0) >= CONFIG['batch']['max_retries'])
        
        start_time = time.time()
        
        # Progress tracking with actual counts
        with tqdm(total=total_batches, initial=completed, desc="Processing batches") as progress_bar:
            while completed + failed < total_batches:
                # Get current queue status
                active_batches = await self._get_active_batches_with_timeout_check()
                active_count = len(active_batches)
                
                # Check for stuck batches
                stuck_count = await self._handle_stuck_batches()
                if stuck_count > 0:
                    logger.warning(f"Force-completed {stuck_count} stuck batches")
                
                # Submit new batches
                available_slots = CONFIG['batch']['max_concurrent_batches'] - active_count
                if available_slots > 0:
                    submitted = await self._submit_new_batches(available_slots)
                    if submitted > 0:
                        logger.debug(f"Submitted {submitted} new batches")
                
                # Monitor and process completed batches
                completed_this_round = await self._monitor_and_process_batches_v3()
                if completed_this_round > 0:
                    completed += completed_this_round
                    progress_bar.update(completed_this_round)
                
                # Update counts
                failed = sum(1 for b in self.state['batches'].values() 
                           if b['status'] == 'failed' and b.get('retry_count', 0) >= CONFIG['batch']['max_retries'])
                
                # Update progress bar info
                progress_bar.set_postfix({
                    'Active': active_count,
                    'Failed': failed,
                    'Processed': f"{self.state['actual_processed']:,}"
                })
                
                # Save checkpoint periodically
                if completed % 10 == 0 and completed > 0:
                    self._save_checkpoint(f'processing_{completed}_batches')
                
                # Wait before next check
                if completed + failed < total_batches:
                    await asyncio.sleep(CONFIG['batch']['check_interval'])
        
        total_time = (time.time() - start_time) / 3600
        logger.info(f"\n✓ Batch processing complete!")
        logger.info(f"  Total time: {total_time:.1f} hours")
        logger.info(f"  Successful: {completed}")
        logger.info(f"  Failed: {failed}")
        logger.info(f"  Products processed: {self.state['actual_processed']:,}")
    
    async def _recover_completed_batches(self):
        """Check for completed batches we haven't processed yet"""
        logger.info("Checking for unprocessed completed batches...")
        
        recovered = 0
        for filename, batch_info in self.state['batches'].items():
            if batch_info['status'] in ['submitted', 'processing']:
                # Check if result file exists
                result_file = self.results_dir / f"results_{filename}"
                if result_file.exists() and batch_info.get('products_processed', 0) == 0:
                    logger.info(f"Found unprocessed results for {filename}")
                    # Process the results
                    if batch_info.get('batch_id'):
                        try:
                            batch = self.client.batches.retrieve(batch_info['batch_id'])
                            await self._process_batch_results_v3(filename, batch, force_process=True)
                            batch_info['status'] = 'completed'
                            recovered += 1
                        except:
                            pass
        
        if recovered > 0:
            logger.info(f"Recovered {recovered} completed batches")
            self._save_state()
    
    async def _get_active_batches_with_timeout_check(self) -> List[str]:
        """Get active batches and check for timeouts"""
        active = []
        try:
            batches = self.client.batches.list(limit=100)
            for batch in batches.data:
                if batch.status in ['validating', 'in_progress', 'finalizing']:
                    active.append(batch.id)
        except Exception as e:
            logger.error(f"Error getting active batches: {e}")
        
        return active
    
    async def _handle_stuck_batches(self) -> int:
        """Handle batches that are stuck"""
        if not CONFIG['recovery']['enable_force_completion']:
            return 0
        
        stuck_count = 0
        current_time = datetime.now()
        stuck_timeout = timedelta(hours=CONFIG['batch']['stuck_batch_timeout_hours'])
        
        for filename, batch_info in self.state['batches'].items():
            if batch_info['status'] in ['submitted', 'processing']:
                # Check if it's been stuck too long
                last_checked = batch_info.get('last_checked')
                if last_checked:
                    last_checked_time = datetime.fromisoformat(last_checked)
                    if current_time - last_checked_time > stuck_timeout:
                        # Check if result file exists
                        result_file = self.results_dir / f"results_{filename}"
                        if result_file.exists():
                            logger.warning(f"Force-completing stuck batch {filename}")
                            batch_info['status'] = 'force_completed'
                            stuck_count += 1
                            # Try to process results if they exist
                            if batch_info.get('batch_id'):
                                try:
                                    batch = self.client.batches.retrieve(batch_info['batch_id'])
                                    await self._process_batch_results_v3(filename, batch, force_process=True)
                                except:
                                    pass
        
        return stuck_count
    
    async def _submit_new_batches(self, limit: int) -> int:
        """Submit new batches"""
        submitted = 0
        
        for filename, batch_info in self.state['batches'].items():
            if submitted >= limit:
                break
            
            if batch_info['status'] not in ['created', 'retry']:
                continue
            
            if batch_info.get('retry_count', 0) >= CONFIG['batch']['max_retries']:
                continue
            
            try:
                # Upload file
                with open(batch_info['path'], 'rb') as f:
                    file_response = self.client.files.create(
                        file=f,
                        purpose="batch"
                    )
                
                # Create batch job
                batch_response = self.client.batches.create(
                    input_file_id=file_response.id,
                    endpoint="/v1/chat/completions",
                    completion_window="24h",
                    metadata={
                        "filename": filename,
                        "request_count": str(batch_info['request_count']),
                        "run_id": self.state['run_id']
                    }
                )
                
                # Update state
                batch_info.update({
                    'status': 'submitted',
                    'batch_id': batch_response.id,
                    'file_id': file_response.id,
                    'submitted_at': datetime.now().isoformat(),
                    'last_checked': datetime.now().isoformat(),
                    'retry_count': batch_info.get('retry_count', 0)
                })
                
                submitted += 1
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Failed to submit {filename}: {e}")
                batch_info['status'] = 'submission_failed'
                batch_info['error'] = str(e)
                batch_info['retry_count'] = batch_info.get('retry_count', 0) + 1
                
                if batch_info['retry_count'] < CONFIG['batch']['max_retries']:
                    batch_info['status'] = 'retry'
        
        self._save_state()
        return submitted
    
    async def _monitor_and_process_batches_v3(self) -> int:
        """Monitor batches with better error handling"""
        completed_count = 0
        
        for filename, batch_info in self.state['batches'].items():
            if batch_info['status'] not in ['submitted', 'processing']:
                continue
            
            # Update last checked time
            batch_info['last_checked'] = datetime.now().isoformat()
            
            try:
                # First check if result file exists (faster than API call)
                result_file = self.results_dir / f"results_{filename}"
                
                if CONFIG['recovery']['check_result_files_first'] and result_file.exists():
                    # Results exist, mark as completed
                    if batch_info.get('products_processed', 0) == 0:
                        logger.info(f"✓ Batch {filename} completed (found results)!")
                        
                        # Get batch object for cost tracking
                        if batch_info.get('batch_id'):
                            try:
                                batch = self.client.batches.retrieve(batch_info['batch_id'])
                                await self._process_batch_results_v3(filename, batch)
                            except:
                                # Process without batch object
                                await self._process_batch_results_v3(filename, None)
                        
                        batch_info['status'] = 'completed'
                        batch_info['completed_at'] = datetime.now().isoformat()
                        completed_count += 1
                
                else:
                    # Check via API
                    if batch_info.get('batch_id'):
                        batch = self.client.batches.retrieve(batch_info['batch_id'])
                        
                        if batch.status == 'completed':
                            logger.info(f"✓ Batch {filename} completed!")
                            await self._process_batch_results_v3(filename, batch)
                            batch_info['status'] = 'completed'
                            batch_info['completed_at'] = datetime.now().isoformat()
                            completed_count += 1
                            
                        elif batch.status == 'failed':
                            logger.error(f"✗ Batch {filename} failed!")
                            batch_info['status'] = 'failed'
                            batch_info['error'] = str(batch.errors) if hasattr(batch, 'errors') else 'Unknown error'
                            batch_info['retry_count'] = batch_info.get('retry_count', 0) + 1
                            
                            if CONFIG['batch']['retry_failed_batches'] and batch_info['retry_count'] < CONFIG['batch']['max_retries']:
                                batch_info['status'] = 'retry'
                            
                        elif batch.status in ['in_progress', 'finalizing']:
                            if batch_info['status'] != 'processing':
                                batch_info['status'] = 'processing'
                    
            except Exception as e:
                logger.error(f"Error monitoring {filename}: {e}")
                self.stats['monitoring_errors'] += 1
        
        self._save_state()
        return completed_count
    
    async def _process_batch_results_v3(self, filename: str, batch: Optional[Any], force_process: bool = False):
        """Process batch results with accurate counting"""
        logger.debug(f"Processing results for {filename}...")
        
        # Check if already processed
        batch_info = self.state['batches'].get(filename, {})
        if batch_info.get('products_processed', 0) > 0 and not force_process:
            logger.debug(f"Batch {filename} already processed")
            return
        
        result_file = self.results_dir / f"results_{filename}"
        
        try:
            # Download results if needed
            if not result_file.exists() and batch and hasattr(batch, 'output_file_id'):
                content = self.client.files.content(batch.output_file_id)
                with open(result_file, 'w') as f:
                    f.write(content.text)
            
            if not result_file.exists():
                logger.error(f"No result file for {filename}")
                return
            
            # Parse results
            classifications = []
            errors = 0
            
            with open(result_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        result = json.loads(line)
                        product_id = result['custom_id'].replace('product_', '')
                        
                        # Extract response
                        response_content = result['response']['body']['choices'][0]['message']['content']
                        response = json.loads(response_content)
                        
                        classifications.append({
                            'product_id': product_id,
                            'is_fashion': response.get('is_fashion', False),
                            'confidence': float(response.get('confidence', 0.0)),
                            'category': response.get('category'),
                            'reasoning': response.get('reasoning', '')
                        })
                        
                    except Exception as e:
                        errors += 1
                        logger.debug(f"Error parsing line {line_num}: {e}")
            
            if errors > 0:
                logger.warning(f"  {errors} errors while parsing {filename}")
            
            # Update database with results
            if classifications:
                processed_count = await self._update_products_batch_v3(classifications)
                
                # Update batch info with actual processed count
                batch_info['products_processed'] = processed_count
                self.state['actual_processed'] += processed_count
                
                logger.info(f"  Processed {processed_count} products from {filename}")
            
            # Save checkpoint periodically
            if self.state['actual_processed'] % 10000 == 0:
                self._save_checkpoint(f'processed_{self.state["actual_processed"]}_products')
            
        except Exception as e:
            logger.error(f"Failed to process results for {filename}: {e}")
            self.stats['processing_errors'] += 1
    
    async def _update_products_batch_v3(self, classifications: List[Dict]) -> int:
        """Update products with accurate counting - NO DOUBLE COUNTING"""
        # Categorize by confidence
        high_confidence_fashion = []
        high_confidence_non_fashion = []
        medium_confidence = []
        low_confidence = []
        
        for c in classifications:
            if c['confidence'] >= CONFIG['classification']['confidence_thresholds']['high']:
                if c['is_fashion']:
                    high_confidence_fashion.append(c)
                else:
                    high_confidence_non_fashion.append(c)
            elif c['confidence'] >= CONFIG['classification']['confidence_thresholds']['medium']:
                medium_confidence.append(c)
            else:
                low_confidence.append(c)
        
        total_processed = 0
        
        # Process each category and track actual updates
        if high_confidence_fashion:
            count = await self._update_fashion_products(high_confidence_fashion)
            self.actual_counts['fashion'] += count
            total_processed += count
        
        if high_confidence_non_fashion:
            if CONFIG['classification']['enable_removal']:
                count = await self._process_non_fashion_removal(high_confidence_non_fashion)
            else:
                count = await self._mark_non_fashion_products(high_confidence_non_fashion)
            self.actual_counts['non_fashion'] += count
            total_processed += count
        
        if medium_confidence:
            count = await self._mark_uncertain_products(medium_confidence)
            self.actual_counts['uncertain'] += count
            total_processed += count
        
        if low_confidence:
            count = await self._mark_manual_review(low_confidence)
            self.actual_counts['manual_review'] += count
            total_processed += count
        
        # Update state with ACTUAL counts, not classifications count
        self.state['fashion_products'] = self.actual_counts['fashion']
        self.state['non_fashion_products'] = self.actual_counts['non_fashion']
        self.state['uncertain_products'] = self.actual_counts['uncertain']
        self.state['manual_review_products'] = self.actual_counts['manual_review']
        
        self._save_state()
        
        return total_processed
    
    async def _update_fashion_products(self, products: List[Dict]) -> int:
        """Update fashion products and return actual count updated"""
        with self.neo4j_driver.session() as session:
            query = """
            UNWIND $products as item
            MATCH (p:Product {id: item.product_id})
            WHERE p:NeedsAI
            SET p:FashionProduct,
                p.is_fashion = true,
                p.fashion_confidence = item.confidence,
                p.fashion_category = item.category,
                p.classification_reasoning = item.reasoning,
                p.classified_at = datetime(),
                p.classified_by = 'ai_pipeline_v3',
                p.ready_for_embedding = true
            REMOVE p:NonFashionProduct, p:UncertainProduct, p:RequiresReview, p:NeedsAI
            RETURN count(p) as updated
            """
            
            products_dict = [
                {
                    'product_id': p['product_id'],
                    'confidence': p['confidence'],
                    'category': p['category'],
                    'reasoning': p['reasoning']
                }
                for p in products
            ]
            
            # Process in batches
            total_updated = 0
            batch_size = 1000
            for i in range(0, len(products_dict), batch_size):
                batch = products_dict[i:i + batch_size]
                result = session.run(query, products=batch)
                updated = sum(record['updated'] for record in result)
                total_updated += updated
            
            return total_updated
    
    async def _mark_non_fashion_products(self, products: List[Dict]) -> int:
        """Mark non-fashion products"""
        with self.neo4j_driver.session() as session:
            query = """
            UNWIND $products as item
            MATCH (p:Product {id: item.product_id})
            WHERE p:NeedsAI
            SET p:NonFashionProduct,
                p.is_fashion = false,
                p.fashion_confidence = item.confidence,
                p.classification_reasoning = item.reasoning,
                p.classified_at = datetime(),
                p.classified_by = 'ai_pipeline_v3'
            REMOVE p:FashionProduct, p:UncertainProduct, p:RequiresReview, p:NeedsAI
            RETURN count(p) as updated
            """
            
            products_dict = [
                {
                    'product_id': p['product_id'],
                    'confidence': p['confidence'],
                    'reasoning': p['reasoning']
                }
                for p in products
            ]
            
            result = session.run(query, products=products_dict)
            updated = sum(record['updated'] for record in result)
            return updated
    
    async def _process_non_fashion_removal(self, products: List[Dict]) -> int:
        """Archive and remove non-fashion products"""
        if CONFIG['classification']['archive_before_removal']:
            # Archive products
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_file = self.archive_dir / f"removed_products_{timestamp}.json"
            
            product_ids = [p['product_id'] for p in products]
            archived_data = []
            
            with self.neo4j_driver.session() as session:
                query = """
                MATCH (p:Product)
                WHERE p.id IN $ids AND p:NeedsAI
                OPTIONAL MATCH (p)-[r]->(related)
                RETURN p, collect({type: type(r), related: properties(related)}) as relationships
                """
                
                for i in range(0, len(product_ids), 100):
                    chunk_ids = product_ids[i:i + 100]
                    result = session.run(query, ids=chunk_ids)
                    
                    for record in result:
                        if record['p']:  # Check product exists
                            classification = next((p for p in products if p['product_id'] == record['p']['id']), None)
                            if classification:
                                archived_data.append({
                                    'product': dict(record['p']),
                                    'relationships': record['relationships'],
                                    'classification': {
                                        'is_fashion': classification['is_fashion'],
                                        'confidence': classification['confidence'],
                                        'reasoning': classification['reasoning']
                                    },
                                    'archived_at': datetime.now().isoformat()
                                })
            
            # Save archive
            if archived_data:
                with open(archive_file, 'w') as f:
                    json.dump(archived_data, f, indent=2)
                logger.info(f"Archived {len(archived_data)} products to {archive_file}")
        
        # Remove from database
        total_deleted = 0
        with self.neo4j_driver.session() as session:
            query = """
            UNWIND $ids as id
            MATCH (p:Product {id: id})
            WHERE p:NeedsAI
            DETACH DELETE p
            RETURN count(*) as deleted
            """
            
            product_ids = [p['product_id'] for p in products]
            batch_size = 100
            
            for i in range(0, len(product_ids), batch_size):
                batch_ids = product_ids[i:i + batch_size]
                result = session.run(query, ids=batch_ids)
                deleted = sum(record['deleted'] for record in result)
                total_deleted += deleted
        
        return total_deleted
    
    async def _mark_uncertain_products(self, products: List[Dict]) -> int:
        """Mark uncertain products"""
        with self.neo4j_driver.session() as session:
            query = """
            UNWIND $products as item
            MATCH (p:Product {id: item.product_id})
            WHERE p:NeedsAI
            SET p:UncertainProduct,
                p.is_fashion = item.is_fashion,
                p.fashion_confidence = item.confidence,
                p.fashion_category = item.category,
                p.classification_reasoning = item.reasoning,
                p.needs_review = true,
                p.classified_at = datetime(),
                p.classified_by = 'ai_pipeline_v3'
            REMOVE p:FashionProduct, p:NonFashionProduct, p:NeedsAI
            RETURN count(p) as updated
            """
            
            products_dict = [
                {
                    'product_id': p['product_id'],
                    'is_fashion': p['is_fashion'],
                    'confidence': p['confidence'],
                    'category': p.get('category'),
                    'reasoning': p['reasoning']
                }
                for p in products
            ]
            
            result = session.run(query, products=products_dict)
            updated = sum(record['updated'] for record in result)
            return updated
    
    async def _mark_manual_review(self, products: List[Dict]) -> int:
        """Mark products for manual review"""
        with self.neo4j_driver.session() as session:
            query = """
            UNWIND $products as item
            MATCH (p:Product {id: item.product_id})
            WHERE p:NeedsAI
            SET p:RequiresReview,
                p.is_fashion = item.is_fashion,
                p.fashion_confidence = item.confidence,
                p.classification_reasoning = item.reasoning,
                p.review_reason = 'Low confidence classification',
                p.classified_at = datetime(),
                p.classified_by = 'ai_pipeline_v3'
            REMOVE p:FashionProduct, p:NonFashionProduct, p:NeedsAI
            RETURN count(p) as updated
            """
            
            products_dict = [
                {
                    'product_id': p['product_id'],
                    'is_fashion': p['is_fashion'],
                    'confidence': p['confidence'],
                    'reasoning': p['reasoning']
                }
                for p in products
            ]
            
            result = session.run(query, products=products_dict)
            updated = sum(record['updated'] for record in result)
            return updated
    
    async def _phase4_export_review(self):
        """Export products needing manual review"""
        logger.info("\n=== PHASE 4: Export for Manual Review ===")
        
        with self.neo4j_driver.session() as session:
            result = session.run("""
                MATCH (p:Product)
                WHERE (p:UncertainProduct OR p:RequiresReview)
                AND p.classified_at IS NOT NULL
                OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
                OPTIONAL MATCH (p)-[:BY_BRAND]->(b:Brand)
                RETURN 
                    p.id as id,
                    p.title as title,
                    p.description as description,
                    c.name as category,
                    b.name as brand,
                    p.price as price,
                    p.is_fashion as ai_is_fashion,
                    p.fashion_confidence as confidence,
                    p.classification_reasoning as reasoning,
                    CASE 
                        WHEN p:UncertainProduct THEN 'uncertain'
                        WHEN p:RequiresReview THEN 'low_confidence'
                        ELSE 'unknown'
                    END as review_type
                ORDER BY p.fashion_confidence DESC
            """)
            
            review_data = []
            for record in result:
                review_data.append(dict(record))
            
            if review_data:
                df = pd.DataFrame(review_data)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                
                review_file = self.manual_review_dir / f'manual_review_{timestamp}.csv'
                df.to_csv(review_file, index=False)
                
                logger.info(f"Exported {len(review_data)} products for manual review")
                logger.info(f"Review file: {review_file}")
            else:
                logger.info("No products need manual review!")
    
    async def _phase5_finalize(self):
        """Final reporting and cleanup"""
        logger.info("\n=== PHASE 5: Finalization ===")
        
        # Verify database state
        await self._verify_final_state()
        
        # Generate reports
        self._generate_final_reports()
        
        # Setup Qdrant if needed
        await self._setup_qdrant_collection()
    
    async def _verify_final_state(self):
        """Verify final database state"""
        logger.info("\nVerifying final database state...")
        
        with self.neo4j_driver.session() as session:
            result = session.run("""
                MATCH (p:Product)
                RETURN 
                    count(p) as total,
                    sum(CASE WHEN p:FashionProduct THEN 1 ELSE 0 END) as fashion,
                    sum(CASE WHEN p:NonFashionProduct THEN 1 ELSE 0 END) as non_fashion,
                    sum(CASE WHEN p:UncertainProduct THEN 1 ELSE 0 END) as uncertain,
                    sum(CASE WHEN p:RequiresReview THEN 1 ELSE 0 END) as review,
                    sum(CASE WHEN p:NeedsAI AND p.classified_at IS NULL THEN 1 ELSE 0 END) as unprocessed
            """).single()
            
            logger.info("Database State:")
            logger.info(f"  Total products: {result['total']:,}")
            logger.info(f"  Fashion products: {result['fashion']:,}")
            logger.info(f"  Non-fashion products: {result['non_fashion']:,}")
            logger.info(f"  Uncertain products: {result['uncertain']:,}")
            logger.info(f"  Needs review: {result['review']:,}")
            logger.info(f"  Still unprocessed: {result['unprocessed']:,}")
            
            self.state['verified_counts'] = dict(result)
    
    async def _setup_qdrant_collection(self):
        """Setup Qdrant collection"""
        try:
            collections = self.qdrant.get_collections()
            exists = any(c.name == CONFIG['qdrant']['collection'] for c in collections.collections)
            
            if not exists:
                self.qdrant.create_collection(
                    collection_name=CONFIG['qdrant']['collection'],
                    vectors_config=VectorParams(
                        size=1536,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created Qdrant collection: {CONFIG['qdrant']['collection']}")
            else:
                logger.info(f"Qdrant collection already exists: {CONFIG['qdrant']['collection']}")
        except Exception as e:
            logger.error(f"Error setting up Qdrant: {e}")
    
    def _generate_final_reports(self):
        """Generate comprehensive reports"""
        logger.info("\nGenerating final reports...")
        
        start_time = datetime.fromisoformat(self.state['start_time'])
        total_hours = (datetime.now() - start_time).total_seconds() / 3600
        
        report = {
            'run_info': {
                'run_id': self.state['run_id'],
                'start_time': self.state['start_time'],
                'end_time': datetime.now().isoformat(),
                'total_hours': round(total_hours, 2)
            },
            'products': {
                'initial_needs_ai': self.state['needs_ai_products'],
                'processed': self.state['actual_processed'],
                'fashion_identified': self.actual_counts['fashion'],
                'non_fashion_identified': self.actual_counts['non_fashion'],
                'uncertain': self.actual_counts['uncertain'],
                'manual_review': self.actual_counts['manual_review']
            },
            'batches': {
                'total': len(self.state['batches']),
                'completed': sum(1 for b in self.state['batches'].values() if b['status'] == 'completed'),
                'failed': sum(1 for b in self.state['batches'].values() if b['status'] == 'failed')
            },
            'database_verification': self.state.get('verified_counts', {}),
            'errors': len(self.state.get('errors', [])),
            'warnings': len(self.state.get('warnings', []))
        }
        
        report_file = self.reports_dir / f'final_report_{self.state["run_id"]}.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        logger.info("\n" + "="*60)
        logger.info("PIPELINE COMPLETE - SUMMARY")
        logger.info("="*60)
        logger.info(f"Run ID: {self.state['run_id']}")
        logger.info(f"Total Runtime: {total_hours:.1f} hours")
        logger.info(f"Products Processed: {self.state['actual_processed']:,}")
        logger.info(f"Fashion Products: {self.actual_counts['fashion']:,}")
        logger.info(f"Non-Fashion Products: {self.actual_counts['non_fashion']:,}")
        logger.info(f"Uncertain Products: {self.actual_counts['uncertain']:,}")
        logger.info(f"Manual Review Needed: {self.actual_counts['manual_review']:,}")
        logger.info(f"\nReports saved to: {self.reports_dir}")
        logger.info("="*60)
    
    def _save_state(self):
        """Save pipeline state"""
        self.state['last_updated'] = datetime.now().isoformat()
        self.state['stats'] = dict(self.stats)
        
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def _save_checkpoint(self, checkpoint_name: str):
        """Save checkpoint"""
        checkpoint = {
            'name': checkpoint_name,
            'timestamp': datetime.now().isoformat(),
            'processed_products': self.state['actual_processed'],
            'state_snapshot': self.state.copy()
        }
        
        checkpoint_file = self.checkpoints_dir / f'{checkpoint_name}_{self.state["run_id"]}.json'
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)
        
        self.state['checkpoints'].append(checkpoint_name)
        logger.debug(f"Saved checkpoint: {checkpoint_name}")


async def main():
    """Main execution"""
    pipeline = FashionClassifierV3()
    await pipeline.run()


if __name__ == "__main__":
    asyncio.run(main())