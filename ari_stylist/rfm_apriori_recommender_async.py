"""
Asynchronous RFM-Apriori Recommendation System for AI Stylist.

This module implements a recommendation system that combines RFM (Recency,
Frequency, Monetary) analysis with association rule mining using the Apriori
algorithm for personalized fashion recommendations.
Compatible with CAMEL-AI 0.2.59+.

MIGRATED: Now uses AgentFactory instead of AsyncCAMELService for CAMEL 0.2.59+ compatibility.
"""

import logging
import datetime
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import defaultdict

# MIGRATED: Import AgentFactory instead of AsyncCAMELService
from agent_factory import get_agent_factory

try:
    import pandas as pd
    import numpy as np
    from mlxtend.frequent_patterns import apriori
    from mlxtend.frequent_patterns import association_rules
    MLXTEND_AVAILABLE = True
except ImportError:
    MLXTEND_AVAILABLE = False
    logging.warning("mlxtend not installed. Please install with: pip install mlxtend pandas")

# MIGRATED: Updated imports for CAMEL 0.2.59+
from camel_imports import (
    ChatAgent,
    AgentMemory,
    CAMEL_AVAILABLE
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rfm_apriori_recommender_async")

class RFMAprioriRecommenderAsync:
    """
    Implements an asynchronous recommendation system that combines RFM (Recency, Frequency,
    Monetary) analysis with association rule mining using the Apriori algorithm.
    
    MIGRATED: Now uses AgentFactory for CAMEL 0.2.59+ compatibility.
    """
    
    def __init__(
        self, 
        product_kg, 
        memory_setup_func=None,
        min_support=0.01,
        min_confidence=0.3,
        min_lift=1.0
    ):
        """
        Initialize the RFM-Apriori recommender.
        
        Args:
            product_kg: Neo4j product knowledge graph instance
            memory_setup_func: Function to set up CAMEL memory
            min_support: Minimum support for Apriori algorithm
            min_confidence: Minimum confidence for association rules
            min_lift: Minimum lift for association rules
        """
        logger.info("Initializing RFMAprioriRecommenderAsync with CAMEL 0.2.59+ support")
        self.product_kg = product_kg
        self.memory_setup_func = memory_setup_func
        
        # Apriori parameters
        self.min_support = min_support
        self.min_confidence = min_confidence
        self.min_lift = min_lift
        
        # User transaction data
        self.transaction_data = defaultdict(list)
        
        # RFM data
        self.rfm_segments = {}
        
        # Association rules
        self.rules = None
        
        # Memory for tracking user preferences
        self.memory = None
        
        # MIGRATED: Use AgentFactory instead of AsyncCAMELService
        self.agent_factory = get_agent_factory()
        
        # Lock for transaction access
        self.transaction_lock = asyncio.Lock()
        
        # Initialize in background
        asyncio.create_task(self._initialize())
    
    async def _initialize(self):
        """Initialize memory and load transactions"""
        # Initialize memory
        if self.memory_setup_func:
            try:
                self.memory = await self.memory_setup_func()
                logger.info("Memory initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing memory: {e}")
                self.memory = None
        
        # Load transactions
        await self.load_transactions_from_neo4j()
    
    async def add_transaction(self, user_id: str, product_id: str, timestamp=None, price=None) -> bool:
        """
        Add a transaction to the user's history asynchronously.
        
        Args:
            user_id: User ID
            product_id: Product ID
            timestamp: Transaction timestamp (optional)
            price: Transaction price (optional)
            
        Returns:
            True if successful, False otherwise
        """
        if not user_id or not product_id:
            return False
            
        # Get transaction timestamp
        if timestamp is None:
            timestamp = datetime.datetime.now()
        
        # Get product details if price is not provided
        if price is None:
            product = await self.product_kg.get_product_details(product_id)
            if product:
                price = product.get('price', 0.0)
            else:
                price = 0.0
        
        # Add transaction with lock to avoid concurrent modification
        async with self.transaction_lock:
            self.transaction_data[user_id].append({
                'product_id': product_id,
                'timestamp': timestamp,
                'price': price
            })
        
        logger.info(f"Added transaction for user {user_id}: product {product_id}")
        return True
    
    async def load_transactions_from_neo4j(self) -> int:
        """
        Load transactions from Neo4j asynchronously.
        
        Returns:
            Number of transactions loaded
        """
        if not hasattr(self.product_kg, 'query'):
            logger.warning("Product knowledge graph does not support queries")
            return 0
            
        try:
            # Check if there's a Purchase relationship type
            check_query = """
            CALL db.relationshipTypes() YIELD relationshipType
            WHERE relationshipType = 'PURCHASED'
            RETURN count(*) as count
            """
            
            result = await self.product_kg.query(check_query)
            
            if not result or result[0].get('count', 0) == 0:
                logger.warning("No PURCHASED relationship type found in Neo4j")
                
                # Check for interaction relationships as alternative
                check_query = """
                CALL db.relationshipTypes() YIELD relationshipType
                WHERE relationshipType = 'HAS_INTERACTION'
                RETURN count(*) as count
                """
                
                result = await self.product_kg.query(check_query)
                
                if not result or result[0].get('count', 0) == 0:
                    logger.warning("No interaction relationships found in Neo4j")
                    return 0
                
                # Query interactions
                query = """
                MATCH (u:User)-[:HAS_INTERACTION]->(i:ProductInteraction)-[:REFERS_TO]->(product:Product)
                WHERE i.type = 'purchased' OR i.type = 'viewed' OR i.type = 'liked'
                RETURN 
                    u.id as user_id,
                    product.id as product_id,
                    i.timestamp as timestamp,
                    product.price as price,
                    i.type as interaction_type
                """
                
                result = await self.product_kg.query(query)
                
                if not result:
                    logger.warning("No interactions found in Neo4j")
                    return 0
                    
                # Process interactions - weigh purchase interactions higher
                async with self.transaction_lock:
                    count = 0
                    for record in result:
                        if 'user_id' in record and 'product_id' in record:
                            user_id = record['user_id']
                            product_id = record['product_id']
                            timestamp = record.get('timestamp')
                            price = record.get('price', 0.0)
                            interaction_type = record.get('interaction_type', 'viewed')
                            
                            # Parse timestamp if needed
                            if timestamp and isinstance(timestamp, str):
                                try:
                                    timestamp = datetime.datetime.fromisoformat(timestamp)
                                except (ValueError, TypeError):
                                    timestamp = datetime.datetime.now()
                            
                            # Add transaction
                            self.transaction_data[user_id].append({
                                'product_id': product_id,
                                'timestamp': timestamp,
                                'price': price,
                                'type': interaction_type
                            })
                            count += 1
                    
                    logger.info(f"Loaded {count} interactions from Neo4j")
                    return count
                
            # If PURCHASED relationship exists, query all purchases
            query = """
            MATCH (u:User)-[p:PURCHASED]->(product:Product)
            RETURN 
                u.id as user_id,
                product.id as product_id,
                p.timestamp as timestamp,
                product.price as price
            """
            
            result = await self.product_kg.query(query)
            
            if not result:
                logger.warning("No purchase transactions found in Neo4j")
                return 0
                
            # Process transactions
            async with self.transaction_lock:
                count = 0
                for record in result:
                    if 'user_id' in record and 'product_id' in record:
                        user_id = record['user_id']
                        product_id = record['product_id']
                        timestamp = record.get('timestamp')
                        price = record.get('price', 0.0)
                        
                        # Parse timestamp if needed
                        if timestamp and isinstance(timestamp, str):
                            try:
                                timestamp = datetime.datetime.fromisoformat(timestamp)
                            except (ValueError, TypeError):
                                timestamp = datetime.datetime.now()
                        
                        # Add transaction
                        self.transaction_data[user_id].append({
                            'product_id': product_id,
                            'timestamp': timestamp,
                            'price': price
                        })
                        count += 1
                
                logger.info(f"Loaded {count} transactions from Neo4j")
                return count
                
        except Exception as e:
            logger.error(f"Error loading transactions from Neo4j: {e}")
            return 0
    
    async def calculate_rfm(self, reference_date=None) -> Dict[str, Dict[str, Any]]:
        """
        Calculate RFM metrics and segments for users asynchronously.
        
        Args:
            reference_date: Reference date for recency calculation (optional)
            
        Returns:
            Dictionary of user RFM segments
        """
        if not MLXTEND_AVAILABLE:
            logger.warning("mlxtend not available for RFM calculation")
            return {}
            
        async with self.transaction_lock:
            transaction_data = dict(self.transaction_data)
        
        if not transaction_data:
            logger.warning("No transaction data available for RFM calculation")
            return {}
            
        try:
            # Run CPU-intensive operations in a thread pool
            return await asyncio.to_thread(
                self._calculate_rfm_sync,
                transaction_data,
                reference_date
            )
        except Exception as e:
            logger.error(f"Error calculating RFM segments: {e}")
            return {}
    
    def _calculate_rfm_sync(self, transaction_data, reference_date=None):
        """
        Synchronous RFM calculation (runs in thread pool).
        
        Args:
            transaction_data: Dictionary of user transactions
            reference_date: Reference date for recency calculation
            
        Returns:
            Dictionary of user RFM segments
        """
        # Set reference date
        if reference_date is None:
            reference_date = datetime.datetime.now()
            
        # Convert to pandas datetime if string
        if isinstance(reference_date, str):
            reference_date = pd.to_datetime(reference_date)
        
        # Calculate RFM metrics
        rfm_data = []
        
        for user_id, transactions in transaction_data.items():
            if not transactions:
                continue
                
            # Calculate recency (days since last purchase)
            timestamps = [t.get('timestamp') for t in transactions if t.get('timestamp')]
            
            if timestamps:
                last_purchase = max(timestamps)
                if isinstance(last_purchase, datetime.datetime):
                    recency = (reference_date - last_purchase).days
                else:
                    recency = 999  # Default high value
            else:
                recency = 999
                
            # Calculate frequency (number of purchases)
            frequency = len(transactions)
            
            # Calculate monetary (total spending)
            monetary = sum(t.get('price', 0) for t in transactions)
            
            rfm_data.append({
                'user_id': user_id,
                'recency': recency,
                'frequency': frequency,
                'monetary': monetary
            })
        
        # Convert to DataFrame
        rfm_df = pd.DataFrame(rfm_data)
        
        if rfm_df.empty:
            logger.warning("No valid RFM data found")
            return {}
            
        # Create RFM segments
        # For recency, lower values are better (more recent)
        rfm_df['R_score'] = pd.qcut(
            rfm_df['recency'], 
            q=5, 
            labels=[5, 4, 3, 2, 1],
            duplicates='drop'
        )
        
        # For frequency and monetary, higher values are better
        rfm_df['F_score'] = pd.qcut(
            rfm_df['frequency'], 
            q=5, 
            labels=[1, 2, 3, 4, 5],
            duplicates='drop'
        )
        
        rfm_df['M_score'] = pd.qcut(
            rfm_df['monetary'], 
            q=5, 
            labels=[1, 2, 3, 4, 5],
            duplicates='drop'
        )
        
        # Calculate RFM score
        rfm_df['RFM_score'] = rfm_df['R_score'].astype(str) + rfm_df['F_score'].astype(str) + rfm_df['M_score'].astype(str)
        
        # Define segment names
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
                'recency': row['recency'],
                'frequency': row['frequency'],
                'monetary': row['monetary'],
                'r_score': row['R_score'],
                'f_score': row['F_score'],
                'm_score': row['M_score'],
                'rfm_score': row['RFM_score'],
                'segment': row['segment']
            }
        
        logger.info(f"Calculated RFM segments for {len(rfm_segments)} users")
        return rfm_segments
    
    async def find_association_rules(self) -> pd.DataFrame:
        """
        Find association rules using Apriori algorithm asynchronously.
        
        Returns:
            Association rules as pandas DataFrame
        """
        if not MLXTEND_AVAILABLE:
            logger.warning("mlxtend not available for association rule mining")
            return None
            
        try:
            # Prepare transaction matrix
            async with self.transaction_lock:
                transaction_data = dict(self.transaction_data)
            
            # Run CPU-intensive operations in a thread pool
            rules = await asyncio.to_thread(
                self._find_association_rules_sync,
                transaction_data
            )
            
            # Store rules
            self.rules = rules
            
            logger.info(f"Found {len(rules) if rules is not None else 0} association rules")
            return rules
            
        except Exception as e:
            logger.error(f"Error finding association rules: {e}")
            return None
    
    def _find_association_rules_sync(self, transaction_data):
        """
        Synchronous association rule mining (runs in thread pool).
        
        Args:
            transaction_data: Dictionary of user transactions
            
        Returns:
            Association rules as pandas DataFrame
        """
        try:
            # Collect all unique product IDs
            all_products = set()
            
            for user_id, transactions in transaction_data.items():
                for transaction in transactions:
                    all_products.add(transaction.get('product_id'))
            
            # Create transaction matrix
            matrix = []
            user_ids = []
            
            for user_id, transactions in transaction_data.items():
                # Get user's purchased product IDs
                purchased_products = set(t.get('product_id') for t in transactions)
                
                # Create row
                row = {}
                
                for product_id in all_products:
                    row[product_id] = 1 if product_id in purchased_products else 0
                
                matrix.append(row)
                user_ids.append(user_id)
            
            # Convert to DataFrame
            df = pd.DataFrame(matrix, index=user_ids)
            
            if df.empty:
                logger.warning("No transaction matrix available for association rule mining")
                return None
                
            # Apply Apriori algorithm
            frequent_itemsets = apriori(
                df,
                min_support=self.min_support,
                use_colnames=True
            )
            
            if frequent_itemsets.empty:
                logger.warning("No frequent itemsets found")
                return None
                
            # Generate association rules
            rules = association_rules(
                frequent_itemsets,
                metric='lift',
                min_threshold=self.min_lift
            )
            
            # Filter by confidence
            rules = rules[rules['confidence'] >= self.min_confidence]
            
            if rules.empty:
                logger.warning("No association rules found")
                return None
                
            return rules
        
        except Exception as e:
            logger.error(f"Error in synchronous association rule mining: {e}")
            return None
    
    async def get_cluster_rules(self, segment: str) -> pd.DataFrame:
        """
        Get association rules for a specific RFM segment asynchronously.
        
        Args:
            segment: RFM segment name
            
        Returns:
            Association rules for the segment
        """
        if not MLXTEND_AVAILABLE or self.rules is None:
            logger.warning("No association rules available")
            return None
            
        try:
            # Get users in the segment
            segment_users = [
                user_id for user_id, data in self.rfm_segments.items()
                if data.get('segment') == segment
            ]
            
            if not segment_users:
                logger.warning(f"No users found in segment: {segment}")
                return self.rules  # Return all rules as fallback
                
            # Prepare transaction matrix for segment users
            async with self.transaction_lock:
                segment_transactions = {
                    user_id: transactions
                    for user_id, transactions in self.transaction_data.items()
                    if user_id in segment_users
                }
            
            # Run CPU-intensive operations in a thread pool
            segment_rules = await asyncio.to_thread(
                self._find_association_rules_sync,
                segment_transactions
            )
            
            if segment_rules is None or len(segment_rules) == 0:
                logger.warning(f"No association rules found for segment: {segment}")
                return self.rules  # Return all rules as fallback
                
            return segment_rules
            
        except Exception as e:
            logger.error(f"Error getting cluster rules: {e}")
            return self.rules  # Return all rules as fallback
    
    async def get_personalized_recommendations(
        self, 
        user_id: str, 
        limit: int = 5,
        use_cluster_rules: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get personalized recommendations for a user asynchronously.
        
        Args:
            user_id: User ID
            limit: Maximum number of recommendations
            use_cluster_rules: Whether to use cluster-specific rules
            
        Returns:
            List of recommended products
        """
        logger.info(f"Getting personalized recommendations for user {user_id}")
        
        # Check if we have transaction data for this user
        async with self.transaction_lock:
            user_transactions = self.transaction_data.get(user_id, [])
        
        if not user_transactions:
            logger.warning(f"No transaction data found for user {user_id}")
            
            # Fallback to popular products
            if hasattr(self.product_kg, 'get_popular_products'):
                return await self.product_kg.get_popular_products(limit)
            else:
                return []
        
        try:
            # Get user's purchased products
            purchased_products = set(t.get('product_id') for t in user_transactions)
            
            # Get appropriate rules - this might involve CPU-intensive operations
            rules_df = None
            
            if use_cluster_rules and self.rfm_segments and user_id in self.rfm_segments:
                segment = self.rfm_segments[user_id].get('segment')
                if segment:
                    rules_df = await self.get_cluster_rules(segment)
            
            if rules_df is None:
                # Use global rules
                if self.rules is None:
                    await self.find_association_rules()
                rules_df = self.rules
            
            if rules_df is None or len(rules_df) == 0:
                logger.warning("No association rules available")
                
                # Fallback to similar products from most recent purchase
                if purchased_products:
                    # Get most recent purchase
                    sorted_transactions = sorted(
                        user_transactions,
                        key=lambda t: t.get('timestamp', datetime.datetime.min),
                        reverse=True
                    )
                    
                    recent_product_id = sorted_transactions[0].get('product_id')
                    
                    if recent_product_id:
                        return await self.product_kg.get_similar_products(recent_product_id, limit)
                
                # Fallback to popular products
                if hasattr(self.product_kg, 'get_popular_products'):
                    return await self.product_kg.get_popular_products(limit)
                else:
                    return []
            
            # Run matching algorithm in thread pool
            recommended_ids = await asyncio.to_thread(
                self._match_rules_to_user,
                rules_df,
                purchased_products,
                limit
            )
            
            # Get product details
            recommendations = []
            
            for product_id in recommended_ids:
                product = await self.product_kg.get_product_details(product_id)
                if product:
                    recommendations.append(product)
            
            logger.info(f"Found {len(recommendations)} personalized recommendations")
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting personalized recommendations: {e}")
            
            # Fallback to popular products
            if hasattr(self.product_kg, 'get_popular_products'):
                return await self.product_kg.get_popular_products(limit)
            else:
                return []
    
    def _match_rules_to_user(self, rules_df, purchased_products, limit):
        """
        Match association rules to user's purchases (runs in thread pool).
        
        Args:
            rules_df: Association rules DataFrame
            purchased_products: Set of product IDs purchased by the user
            limit: Maximum number of recommendations
            
        Returns:
            List of recommended product IDs
        """
        # Find matching rules
        matching_rules = []
        
        for _, rule in rules_df.iterrows():
            antecedents = set(rule['antecedents'])
            if antecedents.issubset(purchased_products):
                # Extract consequents
                consequents = set(rule['consequents'])
                
                # Skip if already purchased
                if any(c in purchased_products for c in consequents):
                    continue
                    
                # Add rule with metrics
                matching_rules.append({
                    'consequents': list(consequents),
                    'lift': rule['lift'],
                    'confidence': rule['confidence'],
                    'support': rule['support']
                })
        
        if not matching_rules:
            return []
        
        # Sort rules by lift
        matching_rules.sort(key=lambda x: x['lift'], reverse=True)
        
        # Get recommended product IDs
        recommended_ids = []
        
        for rule in matching_rules:
            recommended_ids.extend(rule['consequents'])
            
            # Break if we have enough recommendations
            if len(recommended_ids) >= limit:
                break
        
        # Remove duplicates
        recommended_ids = list(dict.fromkeys(recommended_ids))[:limit]
        
        return recommended_ids
    
    async def get_user_segment(self, user_id: str) -> Dict[str, Any]:
        """
        Get RFM segment for a user asynchronously.
        
        Args:
            user_id: User ID
            
        Returns:
            RFM segment data or empty dict if not available
        """
        if not self.rfm_segments:
            await self.calculate_rfm()
            
        return self.rfm_segments.get(user_id, {})
    
    async def close(self):
        """Clean up resources"""
        # MIGRATED: Clean up AgentFactory resources
        await self.agent_factory.cleanup()
