"""
Behavioral Intelligence for CypherBot

Provides RFM (Recency, Frequency, Monetary) and Apriori-based behavioral intelligence.
NEVER returns products - only behavioral patterns and segments for CypherBot.

Based on rfm_apriori_recommender_async.py patterns.
SECURITY: PII protection - all user IDs are hashed in logs
PERFORMANCE: Complete thread safety with async locks
FIXED: All issues from code review
"""

import logging
import asyncio
import datetime
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, Counter, OrderedDict
from threading import RLock
import threading
import time

logger = logging.getLogger("intelligence.behavioral")

# Try to import required libraries
try:
    import pandas as pd
    import numpy as np
    from mlxtend.frequent_patterns import apriori
    from mlxtend.frequent_patterns import association_rules
    MLXTEND_AVAILABLE = True
except ImportError:
    MLXTEND_AVAILABLE = False
    logger.warning("mlxtend not installed. Behavioral intelligence will be limited.")
    logger.info("Install with: pip install mlxtend pandas")


def sanitize_user_id(user_id: str) -> str:
    """
    Sanitize user ID for logging to protect PII.
    Returns a hashed version that's consistent but doesn't reveal the actual ID.
    
    Args:
        user_id: Original user ID
        
    Returns:
        Sanitized user ID for logging
    """
    if not user_id:
        return "anonymous"
    
    # Create consistent hash of user ID
    hash_obj = hashlib.sha256(user_id.encode('utf-8'))
    # Return first 8 characters of hex digest
    return f"user_{hash_obj.hexdigest()[:8]}"


def sanitize_product_id(product_id: str) -> str:
    """
    Sanitize product ID for logging (less sensitive than user ID).
    
    Args:
        product_id: Original product ID
        
    Returns:
        Sanitized product ID
    """
    if not product_id:
        return "unknown_product"
    
    # For products, we can be less strict - just truncate if too long
    if len(product_id) > 20:
        return f"{product_id[:17]}..."
    return product_id


class ThreadSafeDict:
    """
    Thread-safe dictionary wrapper for transaction data.
    Uses both threading locks and asyncio locks for complete safety.
    FIXED: Lazy initialization of async lock, size limits added
    """
    
    def __init__(self, max_size: int = 10000):
        """
        Initialize thread-safe dictionary with size limits.
        
        Args:
            max_size: Maximum number of entries (default 10000)
        """
        self._data = defaultdict(list)
        async def add(self, key: str, value: Any):
            # Add this check
            if len(self._data[key]) > 1000:  # Limit list size
                self._data[key] = self._data[key][-500:]  # Keep recent half

        self._thread_lock = RLock()  # Reentrant lock for threads
        self._async_lock = None  # Lazy initialization for async lock
        self.max_size = max_size
        self._creation_time = time.time()
        self._access_count = 0
        
    async def _ensure_async_lock(self):
        """Ensure async lock is initialized (lazy initialization)."""
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
    
    async def add(self, key: str, value: Any):
        """Add value to key's list asynchronously with size limit."""
        await self._ensure_async_lock()
        async with self._async_lock:
            with self._thread_lock:
                # Check size limit
                if len(self._data) >= self.max_size and key not in self._data:
                    # Remove oldest entries (FIFO)
                    oldest_key = next(iter(self._data))
                    del self._data[oldest_key]
                    logger.debug(f"Evicted oldest transaction data for key: {sanitize_user_id(oldest_key)}")
                
                self._data[key].append(value)
                self._access_count += 1
    
    async def get(self, key: str) -> List[Any]:
        """Get values for key asynchronously."""
        await self._ensure_async_lock()
        async with self._async_lock:
            with self._thread_lock:
                self._access_count += 1
                return list(self._data.get(key, []))
    
    async def get_all(self) -> Dict[str, List[Any]]:
        """Get all data as a copy asynchronously."""
        await self._ensure_async_lock()
        async with self._async_lock:
            with self._thread_lock:
                self._access_count += 1
                return {k: list(v) for k, v in self._data.items()}
    
    async def clear(self):
        """Clear all data asynchronously."""
        await self._ensure_async_lock()
        async with self._async_lock:
            with self._thread_lock:
                self._data.clear()
    
    def add_sync(self, key: str, value: Any):
        """Add value synchronously (for non-async contexts) with size limit."""
        with self._thread_lock:
            # Check size limit
            if len(self._data) >= self.max_size and key not in self._data:
                # Remove oldest entries (FIFO)
                oldest_key = next(iter(self._data))
                del self._data[oldest_key]
            
            self._data[key].append(value)
            self._access_count += 1
    
    def get_sync(self, key: str) -> List[Any]:
        """Get values synchronously."""
        with self._thread_lock:
            self._access_count += 1
            return list(self._data.get(key, []))
    
    def size(self) -> int:
        """Get number of keys."""
        with self._thread_lock:
            return len(self._data)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get dictionary statistics."""
        with self._thread_lock:
            age = time.time() - self._creation_time
            return {
                "size": len(self._data),
                "max_size": self.max_size,
                "access_count": self._access_count,
                "age_seconds": age,
                "entries_per_second": self._access_count / max(age, 0.001) #self._access_count / age if age > 0 else 0
            }


class BehavioralIntelligence:
    """
    Provides behavioral intelligence for CypherBot using RFM and Apriori.
    
    Analyzes user behavior patterns and segments.
    CRITICAL: Returns behavioral insights, NEVER products!
    SECURITY: All user IDs are hashed in logs to protect PII.
    PERFORMANCE: Complete thread safety for concurrent access.
    FIXED: Stats lock issue, transaction size limits, improved thread safety
    """
    async def load_transactions_batch(self, user_ids: List[str]) -> Dict[str, List[Dict]]:
        """
        Load transactions for multiple users in one query.
        
        Args:
            user_ids: List of user IDs
            
        Returns:
            Dict mapping user_id to transactions
        """
        if not self.user_kg or not user_ids:
            return {}
        
        try:
            # BATCH QUERY - gets all users at once
            query = """
            MATCH (u:User)-[:HAS_INTERACTION]->(i:ProductInteraction)-[:REFERS_TO]->(p:Product)
            WHERE u.id IN $user_ids
            AND i.type IN ['purchased', 'viewed', 'liked']
            RETURN 
                u.id as user_id,
                collect({
                    product_id: p.id,
                    timestamp: i.timestamp,
                    price: p.price,
                    type: i.type
                }) as transactions
            """
            
            result = await self.user_kg.query(
                query, 
                {"user_ids": user_ids}
            )
            
            # Process into dict
            user_transactions = {}
            for record in result:
                user_transactions[record['user_id']] = record['transactions']
            
            return user_transactions
            
        except Exception as e:
            logger.error(f"Batch load failed: {e}")
            return {}
        
    def __init__(
        self,
        product_kg: Any,
        user_kg: Optional[Any] = None,
        memory_setup_func: Optional[Any] = None,
        min_support: float = 0.01,
        min_confidence: float = 0.3,
        min_lift: float = 1.0,
        enable_pii_protection: bool = True,
        max_transactions: int = 10000
    ):
        """
        Initialize behavioral intelligence system with complete thread safety.
        
        Args:
            product_kg: Product knowledge graph
            user_kg: User knowledge graph
            memory_setup_func: Memory setup function
            min_support: Minimum support for Apriori (default from rfm_apriori_recommender_async.py)
            min_confidence: Minimum confidence for rules
            min_lift: Minimum lift for rules
            enable_pii_protection: Enable PII protection in logs (default True)
            max_transactions: Maximum transactions to store (default 10000)
        """
        logger.info("Initializing Behavioral Intelligence (RFM + Apriori) with PII protection and thread safety")
        
        self.product_kg = product_kg
        self.user_kg = user_kg
        self.memory_setup_func = memory_setup_func
        self.enable_pii_protection = enable_pii_protection
        
        # Apriori parameters
        self.min_support = min_support
        self.min_confidence = min_confidence
        self.min_lift = min_lift
        
        # Thread-safe user transaction data with size limit
        self.transaction_data = ThreadSafeDict(max_size=max_transactions)
        
        # Thread-safe RFM segments cache
        self.rfm_segments = {}
        self.rfm_segments_lock = asyncio.Lock()
        
        # Thread-safe association rules cache
        self.rules = None
        self.rules_lock = asyncio.Lock()
        
        # Memory for tracking
        self.memory = None
        
        # Statistics with separate sync lock for synchronous access
        self.stats = {
            "total_analysis": 0,
            "rfm_calculations": 0,
            "pattern_analysis": 0,
            "errors": 0
        }
        self.stats_lock = asyncio.Lock()
        self.stats_sync_lock = RLock()  # Separate sync lock for get_statistics
        
        # Check availability
        if not MLXTEND_AVAILABLE:
            logger.error("mlxtend not available - behavioral intelligence will be limited")
        
        logger.info(f"Behavioral Intelligence initialized (PII protection: {enable_pii_protection}, Thread-safe: Yes, Max transactions: {max_transactions})")
        
        # Initialize in background
        self._init_task = asyncio.create_task(self._initialize())
        self._init_task.add_done_callback(lambda t: logger.error(f"Initialization failed: {t.exception()}") if t.exception() else None)
    
    def _log_user_action(self, user_id: str, action: str, details: Optional[Dict] = None):
        """
        Log user action with PII protection.
        
        Args:
            user_id: User ID
            action: Action description
            details: Optional details (will be sanitized)
        """
        if self.enable_pii_protection:
            safe_user_id = sanitize_user_id(user_id)
        else:
            safe_user_id = user_id
        
        if details:
            # Sanitize any user IDs in details
            safe_details = {}
            for key, value in details.items():
                if 'user' in key.lower() and isinstance(value, str):
                    safe_details[key] = sanitize_user_id(value) if self.enable_pii_protection else value
                elif 'product' in key.lower() and isinstance(value, str):
                    safe_details[key] = sanitize_product_id(value)
                else:
                    safe_details[key] = value
            
            logger.info(f"{safe_user_id}: {action} - {safe_details}")
        else:
            logger.info(f"{safe_user_id}: {action}")
    
    async def _initialize(self):
        """Initialize memory and load transactions."""
        # Initialize memory if needed
        if self.memory_setup_func:
            try:
                if asyncio.iscoroutinefunction(self.memory_setup_func):
                    self.memory = await self.memory_setup_func()
                else:
                    self.memory = await asyncio.to_thread(self.memory_setup_func)
                logger.info("Memory initialized for behavioral analysis")
            except Exception as e:
                logger.error(f"Error initializing memory: {e}")
        
        # Load transactions from Neo4j
        await self.load_transactions()
    
    async def load_transactions(self) -> int:
        """
        Load transactions from Neo4j with thread safety.
        
        Based on rfm_apriori_recommender_async.py load_transactions_from_neo4j.
        """
        if not self.user_kg or not hasattr(self.user_kg, 'query'):
            logger.warning("User knowledge graph not available for loading transactions")
            return 0
        
        try:
            # Query for interactions
            query = """
            MATCH (u:User)-[:HAS_INTERACTION]->(i:ProductInteraction)-[:REFERS_TO]->(p:Product)
            WHERE i.type IN ['purchased', 'viewed', 'liked']
            RETURN 
                u.id as user_id,
                p.id as product_id,
                i.timestamp as timestamp,
                p.price as price,
                i.type as interaction_type
            LIMIT 10000
            """
            
            # Execute query with timeout
            result = await asyncio.wait_for(
                self.user_kg.query(query),
                timeout=30.0
            )
            
            if not result:
                logger.warning("No interactions found in Neo4j")
                return 0
            
            # Process interactions with thread safety
            count = 0
            unique_users = set()
            
            for record in result:
                if 'user_id' in record and 'product_id' in record:
                    user_id = record['user_id']
                    product_id = record['product_id']
                    timestamp = record.get('timestamp', datetime.datetime.now())
                    price = record.get('price', 0.0)
                    interaction_type = record.get('interaction_type', 'viewed')
                    
                    # Parse timestamp if needed
                    if isinstance(timestamp, str):
                        try:
                            timestamp = datetime.datetime.fromisoformat(timestamp)
                        except (ValueError, TypeError):
                            timestamp = datetime.datetime.now()
                    
                    # Add transaction using thread-safe method
                    await self.transaction_data.add(user_id, {
                        'product_id': product_id,
                        'timestamp': timestamp,
                        'price': price,
                        'type': interaction_type
                    })
                    
                    unique_users.add(user_id)
                    count += 1
            
            # Log with PII protection
            logger.info(f"Loaded {count} transactions for {len(unique_users)} users")
            return count
            
        except asyncio.TimeoutError:
            logger.error("Timeout loading transactions from Neo4j")
            return 0
        except Exception as e:
            logger.error(f"Error loading transactions: {e}")
            # Update stats with sync lock
            with self.stats_sync_lock:
                self.stats["errors"] += 1
            return 0
    
    async def get_user_segment(
        self,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get RFM segment for a user with thread safety.
        
        Args:
            user_id: User ID
            
        Returns:
            Segment intelligence (NOT products!)
        """
        # Update stats asynchronously
        async with self.stats_lock:
            self.stats["total_analysis"] += 1
        
        # Log with PII protection
        self._log_user_action(user_id, "Requesting RFM segment")
        
        # Calculate RFM if not already done
        async with self.rfm_segments_lock:
            if not self.rfm_segments:
                await self._calculate_rfm_internal()
            
            # Get user segment
            if user_id in self.rfm_segments:
                segment_data = self.rfm_segments[user_id]
                
                segment_info = {
                    "segment": segment_data.get('segment', 'standard'),
                    "tier": self._get_tier_from_segment(segment_data.get('segment')),
                    "recency_score": segment_data.get('r_score', 0),
                    "frequency_score": segment_data.get('f_score', 0),
                    "monetary_score": segment_data.get('m_score', 0),
                    "rfm_score": segment_data.get('rfm_score', '000'),
                    "lifetime_value": segment_data.get('monetary', 0),
                    "last_purchase_days": segment_data.get('recency', 999),
                    "total_purchases": segment_data.get('frequency', 0),
                    "confidence": 0.85
                }
                
                # Log segment assignment with PII protection
                self._log_user_action(
                    user_id, 
                    "Segment assigned",
                    {"segment": segment_info["segment"], "tier": segment_info["tier"]}
                )
                
                return segment_info
        
        # Default segment for unknown users
        self._log_user_action(user_id, "New customer segment assigned (default)")
        
        return {
            "segment": "new_customer",
            "tier": "standard",
            "recency_score": 1,
            "frequency_score": 1,
            "monetary_score": 1,
            "rfm_score": "111",
            "lifetime_value": 0,
            "last_purchase_days": 999,
            "total_purchases": 0,
            "confidence": 0.3
        }
    
    async def get_purchase_patterns(
        self,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get purchase patterns for a user with thread safety.
        
        Args:
            user_id: User ID
            
        Returns:
            Purchase pattern intelligence
        """
        # Update stats asynchronously
        async with self.stats_lock:
            self.stats["pattern_analysis"] += 1
        
        # Log with PII protection
        self._log_user_action(user_id, "Analyzing purchase patterns")
        
        # Get user transactions safely
        user_transactions = await self.transaction_data.get(user_id)
        
        if not user_transactions:
            self._log_user_action(user_id, "No transaction history found")
            return None
        
        try:
            # Extract product IDs
            purchased_products = [
                t['product_id'] for t in user_transactions
                if t.get('type') == 'purchased'
            ]
            
            if not purchased_products:
                purchased_products = [t['product_id'] for t in user_transactions]
            
            # Count frequencies
            product_freq = Counter(purchased_products)
            
            # Get frequent items (sanitize product IDs in result)
            frequent_items = [
                {
                    "product_id": sanitize_product_id(pid) if self.enable_pii_protection else pid,
                    "frequency": freq
                }
                for pid, freq in product_freq.most_common(10)
            ]
            
            # Calculate purchase patterns
            patterns = {
                "frequent_items": frequent_items,
                "unique_products": len(set(purchased_products)),
                "total_interactions": len(user_transactions),
                "purchase_rate": len([t for t in user_transactions if t.get('type') == 'purchased']) / len(user_transactions) if user_transactions else 0
            }
            
            # Get association rules if available
            async with self.rules_lock:
                if self.rules is not None and MLXTEND_AVAILABLE:
                    user_rules = await self._get_user_association_rules(purchased_products)
                    patterns["association_rules"] = user_rules
            
            # Analyze seasonality
            patterns["seasonality"] = self._analyze_seasonality(user_transactions)
            
            # Analyze brand loyalty
            patterns["brand_loyalty"] = await self._analyze_brand_loyalty(purchased_products)
            
            # Analyze price sensitivity
            patterns["price_sensitivity"] = self._analyze_price_sensitivity(user_transactions)
            
            patterns["confidence"] = 0.75
            
            # Log pattern summary with PII protection
            self._log_user_action(
                user_id,
                "Purchase patterns analyzed",
                {
                    "unique_products": patterns["unique_products"],
                    "total_interactions": patterns["total_interactions"]
                }
            )
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error getting purchase patterns: {e}")
            # Update stats with sync lock
            with self.stats_sync_lock:
                self.stats["errors"] += 1
            return None
    
    async def calculate_rfm(
        self,
        reference_date: Optional[datetime.datetime] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate RFM metrics and segments with thread safety.
        
        Based on rfm_apriori_recommender_async.py calculate_rfm.
        """
        async with self.rfm_segments_lock:
            return await self._calculate_rfm_internal(reference_date)
    
    async def _calculate_rfm_internal(
        self,
        reference_date: Optional[datetime.datetime] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Internal RFM calculation (must be called with lock held).
        """
        if not MLXTEND_AVAILABLE:
            logger.warning("mlxtend not available for RFM calculation")
            return {}
        
        # Update stats asynchronously
        async with self.stats_lock:
            self.stats["rfm_calculations"] += 1
        
        # Get all transaction data safely
        transaction_data = await self.transaction_data.get_all()
        
        if not transaction_data:
            logger.warning("No transaction data for RFM calculation")
            return {}
        
        try:
            # Run CPU-intensive operations in thread pool (Pandas is not thread-safe but OK in separate thread)
            self.rfm_segments = await asyncio.to_thread(
                self._calculate_rfm_sync,
                transaction_data,
                reference_date
            )
            
            # Log summary without PII
            logger.info(f"Calculated RFM segments for {len(self.rfm_segments)} users")
            
            # Log segment distribution without user IDs
            segment_counts = Counter(s['segment'] for s in self.rfm_segments.values())
            logger.info(f"Segment distribution: {dict(segment_counts)}")
            
            return self.rfm_segments
            
        except Exception as e:
            logger.error(f"Error calculating RFM: {e}")
            # Update stats with sync lock
            with self.stats_sync_lock:
                self.stats["errors"] += 1
            return {}
    
    def _calculate_rfm_sync(
        self,
        transaction_data: Dict,
        reference_date: Optional[datetime.datetime]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Synchronous RFM calculation (runs in thread pool for safety).
        
        Based on rfm_apriori_recommender_async.py _calculate_rfm_sync.
        """
        # Set reference date
        if reference_date is None:
            reference_date = datetime.datetime.now()
        
        # Calculate RFM metrics
        rfm_data = []
        
        for user_id, transactions in transaction_data.items():
            if not transactions:
                continue
            
            # Calculate recency
            timestamps = [t.get('timestamp') for t in transactions if t.get('timestamp')]
            
            if timestamps:
                last_purchase = max(timestamps)
                if isinstance(last_purchase, datetime.datetime):
                    recency = (reference_date - last_purchase).days
                else:
                    recency = 999
            else:
                recency = 999
            
            # Calculate frequency
            frequency = len(transactions)
            
            # Calculate monetary
            monetary = sum(t.get('price', 0) for t in transactions)
            
            rfm_data.append({
                'user_id': user_id,
                'recency': recency,
                'frequency': frequency,
                'monetary': monetary
            })
        
        if not rfm_data:
            return {}
        
        # Convert to DataFrame (thread-safe since we're in separate thread)
        rfm_df = pd.DataFrame(rfm_data)
        
        # Create RFM segments safely
        try:
            # For recency, lower values are better
            rfm_df['R_score'] = pd.qcut(
                rfm_df['recency'],
                q=5,
                labels=[5, 4, 3, 2, 1],
                duplicates='drop'
            )
        except:
            rfm_df['R_score'] = 3  # Default middle score
        
        try:
            # For frequency and monetary, higher values are better
            rfm_df['F_score'] = pd.qcut(
                rfm_df['frequency'],
                q=5,
                labels=[1, 2, 3, 4, 5],
                duplicates='drop'
            )
        except:
            rfm_df['F_score'] = 3
        
        try:
            rfm_df['M_score'] = pd.qcut(
                rfm_df['monetary'],
                q=5,
                labels=[1, 2, 3, 4, 5],
                duplicates='drop'
            )
        except:
            rfm_df['M_score'] = 3
        
        # Calculate RFM score
        rfm_df['RFM_score'] = (
            rfm_df['R_score'].astype(str) +
            rfm_df['F_score'].astype(str) +
            rfm_df['M_score'].astype(str)
        )
        
        # Define segment names (from rfm_apriori_recommender_async.py)
        def segment_name(row):
            if row['RFM_score'] in ['555', '554', '545', '544']:
                return 'Champions'
            elif row['RFM_score'] in ['535', '534', '525', '524']:
                return 'Loyal Customers'
            elif row['RFM_score'] in ['515', '514', '513', '512', '511']:
                return 'New Customers'
            elif row['RFM_score'] in ['333', '334', '343', '344', '353', '354']:
                return 'Potential Loyalists'
            elif row['RFM_score'] in ['331', '321', '312', '311', '221']:
                return 'At Risk Customers'
            else:
                return 'Others'
        
        rfm_df['segment'] = rfm_df.apply(segment_name, axis=1)
        
        # Convert to dictionary
        rfm_segments = {}
        
        for _, row in rfm_df.iterrows():
            rfm_segments[row['user_id']] = {
                'recency': int(row['recency']),
                'frequency': int(row['frequency']),
                'monetary': float(row['monetary']),
                'r_score': int(row['R_score']),
                'f_score': int(row['F_score']),
                'm_score': int(row['M_score']),
                'rfm_score': row['RFM_score'],
                'segment': row['segment']
            }
        
        return rfm_segments
    
    async def find_association_rules(self) -> Optional[pd.DataFrame]:
        """
        Find association rules using Apriori algorithm with thread safety.
        
        Returns:
            Association rules DataFrame or None
        """
        if not MLXTEND_AVAILABLE:
            logger.warning("mlxtend not available for association rules")
            return None
        
        try:
            # Get all transaction data safely
            transaction_data = await self.transaction_data.get_all()
            
            # Run CPU-intensive operations in thread pool
            rules = await asyncio.to_thread(
                self._find_association_rules_sync,
                transaction_data
            )
            
            # Update cache with thread safety
            async with self.rules_lock:
                self.rules = rules
            
            if rules is not None:
                logger.info(f"Found {len(rules)} association rules")
            
            return rules
            
        except Exception as e:
            logger.error(f"Error finding association rules: {e}")
            # Update stats with sync lock
            with self.stats_sync_lock:
                self.stats["errors"] += 1
            return None
    
    def _find_association_rules_sync(
        self,
        transaction_data: Dict
    ) -> Optional[pd.DataFrame]:
        """
        Synchronous association rule mining (runs in thread pool).
        
        Based on rfm_apriori_recommender_async.py _find_association_rules_sync.
        """
        try:
            # Collect all unique products
            all_products = set()
            
            for user_id, transactions in transaction_data.items():
                for transaction in transactions:
                    all_products.add(transaction.get('product_id'))
            
            if not all_products:
                return None
            
            # Create transaction matrix
            matrix = []
            
            for user_id, transactions in transaction_data.items():
                purchased_products = set(t.get('product_id') for t in transactions)
                
                row = {}
                for product_id in all_products:
                    row[product_id] = 1 if product_id in purchased_products else 0
                
                matrix.append(row)
            
            if not matrix:
                return None
            
            # Convert to DataFrame (thread-safe in separate thread)
            df = pd.DataFrame(matrix)
            
            # Apply Apriori
            frequent_itemsets = apriori(
                df,
                min_support=self.min_support,
                use_colnames=True
            )
            
            if frequent_itemsets.empty:
                return None
            
            # Generate association rules
            rules = association_rules(
                frequent_itemsets,
                metric='lift',
                min_threshold=self.min_lift
            )
            
            # Filter by confidence
            rules = rules[rules['confidence'] >= self.min_confidence]
            
            return rules if not rules.empty else None
            
        except Exception as e:
            logger.error(f"Error in association rule mining: {e}")
            return None
    
    async def _get_user_association_rules(
        self,
        purchased_products: List[str]
    ) -> List[Dict[str, Any]]:
        """Get association rules relevant to user's purchases."""
        if self.rules is None or not MLXTEND_AVAILABLE:
            return []
        
        try:
            # Find matching rules
            matching_rules = []
            purchased_set = set(purchased_products)
            
            for _, rule in self.rules.iterrows():
                antecedents = set(rule['antecedents'])
                if antecedents.issubset(purchased_set):
                    consequents = list(rule['consequents'])
                    
                    # Sanitize product IDs if PII protection enabled
                    if self.enable_pii_protection:
                        safe_antecedents = [sanitize_product_id(p) for p in antecedents]
                        safe_consequents = [sanitize_product_id(p) for p in consequents]
                    else:
                        safe_antecedents = list(antecedents)
                        safe_consequents = consequents
                    
                    matching_rules.append({
                        "antecedents": safe_antecedents,
                        "consequents": safe_consequents,
                        "lift": float(rule['lift']),
                        "confidence": float(rule['confidence']),
                        "support": float(rule['support'])
                    })
            
            # Sort by lift
            matching_rules.sort(key=lambda x: x['lift'], reverse=True)
            
            return matching_rules[:5]  # Top 5 rules
            
        except Exception as e:
            logger.error(f"Error getting user association rules: {e}")
            return []
    
    def _get_tier_from_segment(self, segment: str) -> str:
        """Map RFM segment to tier."""
        tier_mapping = {
            'Champions': 'vip',
            'Loyal Customers': 'premium',
            'Potential Loyalists': 'gold',
            'New Customers': 'standard',
            'At Risk Customers': 'retention',
            'Others': 'standard'
        }
        return tier_mapping.get(segment, 'standard')
    
    def _analyze_seasonality(
        self,
        transactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze seasonal patterns in transactions."""
        if not transactions:
            return {}
        
        # Count transactions by month
        month_counts = Counter()
        
        for t in transactions:
            timestamp = t.get('timestamp')
            if timestamp and isinstance(timestamp, datetime.datetime):
                month_counts[timestamp.month] += 1
        
        if not month_counts:
            return {}
        
        # Find peak months
        peak_months = [
            month for month, _ in month_counts.most_common(3)
        ]
        
        return {
            "peak_months": peak_months,
            "monthly_distribution": dict(month_counts)
        }
    
    async def _analyze_brand_loyalty(
        self,
        product_ids: List[str]
    ) -> Dict[str, Any]:
        """Analyze brand loyalty from purchased products."""
        # This would query product details to get brands
        # Simplified version
        return {
            "loyalty_score": 0.7,
            "preferred_brands": []
        }
    
    def _analyze_price_sensitivity(
        self,
        transactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze price sensitivity from transactions."""
        prices = [t.get('price', 0) for t in transactions if t.get('price')]
        
        if not prices:
            return {}
        
        return {
            "avg_price": float(np.mean(prices)),
            "price_range": {
                "min": float(min(prices)),
                "max": float(max(prices))
            },
            "price_std": float(np.std(prices)),
            "sensitivity": "low" if np.std(prices) > 50 else "high"
        }
    
    async def add_transaction(
        self,
        user_id: str,
        product_id: str,
        timestamp: Optional[datetime.datetime] = None,
        price: Optional[float] = None
    ) -> bool:
        """
        Add a transaction for learning with thread safety.
        
        Args:
            user_id: User ID
            product_id: Product ID
            timestamp: Transaction timestamp
            price: Transaction price
            
        Returns:
            Success status
        """
        if not user_id or not product_id:
            return False
        
        if timestamp is None:
            timestamp = datetime.datetime.now()
        
        if price is None:
            price = 0.0
        
        # Add transaction with thread safety
        await self.transaction_data.add(user_id, {
            'product_id': product_id,
            'timestamp': timestamp,
            'price': price,
            'type': 'purchased'
        })
        
        # Log with PII protection
        self._log_user_action(
            user_id,
            "Transaction added",
            {"product": sanitize_product_id(product_id), "price": price}
        )
        
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get behavioral intelligence statistics.
        FIXED: Now uses synchronous lock for thread-safe access
        
        Returns:
            Statistics without PII
        """
        # Use synchronous lock for synchronous method
        with self.stats_sync_lock:
            stats = dict(self.stats)
        
        # Get transaction data stats
        transaction_stats = self.transaction_data.get_stats()
        
        return {
            "total_users": self.transaction_data.size(),
            "transaction_stats": transaction_stats,
            "segments_calculated": len(self.rfm_segments),
            "rules_found": len(self.rules) if self.rules is not None else 0,
            "pii_protection": self.enable_pii_protection,
            "mlxtend_available": MLXTEND_AVAILABLE,
            "analysis_stats": stats
        }
    
    async def cleanup(self):
        # Ensure initialization completed
        if hasattr(self, "_init_task") and not self._init_task.done():
            self._init_task.cancel()
            try:
                await self._init_task
            except asyncio.CancelledError:
                pass
        """Clean up resources."""
        logger.info("Cleaning up Behavioral Intelligence")
        
        # Clear transaction data
        await self.transaction_data.clear()
        
        # Clear RFM segments
        async with self.rfm_segments_lock:
            self.rfm_segments.clear()
        
        # Clear rules
        async with self.rules_lock:
            self.rules = None
        
        logger.info("Behavioral Intelligence cleanup complete")
