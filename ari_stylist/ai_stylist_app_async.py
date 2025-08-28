"""
Enhanced Asynchronous AI Stylist Application - SEASON 3 COMPLETE

FIXED #1: Async/sync bug with deferred agent factory initialization  
FIXED #4: Battle optimization (NEVER skips, only optimizes parameters)
FIXED #7: Environment variables required (no hardcoded credentials)
Currently on CAMEL-AI 0.2.64, ready for 0.2.7 upgrade
"""

import os
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
import httpx
import datetime
import uuid

# Configure logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_stylist_app_async")

# Import agent factory
from agent_factory import get_agent_factory

# Import memory integration
from memory_integration_async import (
    MemoryManager,
    setup_stylist_memory_async,
    save_memory_for_user_async,
    optimize_memory_async,
    extract_preferences_from_memory_async
)

# Import stylist agent
from stylist_agent_async import create_stylist_agent_async

# Import data stores
from user_knowledge_graph_async import UserKnowledgeGraphAsync
from hybrid_data_store import HybridDataStore
from product_retriever_async import ProductRetrieverAsync

# Import battle system
from battle_agents import BattleAgents
from competitive_search_system import CompetitiveSearchSystem

# Import chat manager
from chat_session_manager_async import EnhancedChatManagerAsync

# Import recommender manager
from enhanced_recommender_manager_async import EnhancedRecommenderManagerAsync


class EnhancedAIStylistApp:
    """
    Enhanced AI Stylist application with ALL Season 3 fixes.
    FIXED #1: Async/sync initialization bug
    FIXED #4: Battle optimization for luxury fashion
    FIXED #7: Secure environment configuration
    Currently: CAMEL 0.2.64
    Target: CAMEL 0.2.7 for Anthropic support
    """
    
    def __init__(self, neo4j_url=None, neo4j_username=None, neo4j_password=None):
        """
        Initialize with Season 3 fixes:
        - Fix #1: Defer agent factory for async initialization
        - Fix #7: Require environment variables
        """
        logger.info("Initializing AI Stylist with Season 3 fixes...")
        
        # VERIFY CAMEL VERSION
        try:
            from camel import __version__ as camel_version
            logger.info(f"CAMEL-AI version detected: {camel_version}")
            
            # Check version compatibility
            if camel_version.startswith('0.2.64'):
                logger.info("✅ Running on CAMEL 0.2.64 (current supported version)")
            elif camel_version.startswith('0.2.7'):
                logger.info("✅ Running on CAMEL 0.2.7 (target version with Anthropic)")
            else:
                logger.warning(f"⚠️ CAMEL {camel_version} may have compatibility issues")
                logger.warning("Supported versions: 0.2.64 (current), 0.2.7 (target)")
        except:
            logger.warning("Could not verify CAMEL-AI version")
        
        # FIX #7: REQUIRE environment variables (no hardcoded defaults)
        self.neo4j_url = neo4j_url or os.environ.get("NEO4J_URL")
        self.neo4j_username = neo4j_username or os.environ.get("NEO4J_USERNAME")
        self.neo4j_password = neo4j_password or os.environ.get("NEO4J_PASSWORD")
        
        # Validate required credentials
        if not self.neo4j_url:
            raise ValueError(
                "NEO4J_URL is required. Set it as environment variable or pass as parameter.\n"
                "Example: export NEO4J_URL='bolt://your-server:7687'"
            )
        if not self.neo4j_username:
            raise ValueError(
                "NEO4J_USERNAME is required. Set it as environment variable or pass as parameter.\n"
                "Example: export NEO4J_USERNAME='neo4j'"
            )
        if not self.neo4j_password:
            raise ValueError(
                "NEO4J_PASSWORD is required. Set it as environment variable or pass as parameter.\n"
                "Example: export NEO4J_PASSWORD='your-secure-password'"
            )
        
        # Log connection info (without password)
        logger.info(f"Connecting to Neo4j at {self.neo4j_url} as {self.neo4j_username}")
        
        # Read Qdrant configuration
        self.qdrant_url = os.environ.get("QDRANT_URL")
        self.qdrant_api_key = os.environ.get("QDRANT_API_KEY")
        self.qdrant_collection_name = os.environ.get("QDRANT_COLLECTION_NAME", "fashion_products")
        
        # Set up UserKnowledgeGraph
        self.user_kg = UserKnowledgeGraphAsync(
            url=self.neo4j_url,
            username=self.neo4j_username,
            password=self.neo4j_password
        )
        
        # Set up ProductRetriever
        logger.info("Initializing product retriever...")
        if self.qdrant_url and self.qdrant_api_key:
            logger.info(f"Using remote Qdrant at {self.qdrant_url}")
            self.product_retriever = ProductRetrieverAsync(
                qdrant_url=self.qdrant_url,
                qdrant_api_key=self.qdrant_api_key,
                collection_name=self.qdrant_collection_name
            )
        else:
            logger.info("Using local Qdrant instance")
            self.product_retriever = ProductRetrieverAsync(
                collection_name=self.qdrant_collection_name
            )
        
        # Initialize HybridDataStore
        logger.info("Initializing HybridDataStore...")
        self.data_store = HybridDataStore(
            neo4j_client=self.user_kg,
            qdrant_client=self.product_retriever
        )
        
        # Initialize Battle System
        logger.info("Initializing Battle System...")
        self.battle_agents = BattleAgents(
            neo4j_client=self.user_kg,
            qdrant_retriever=self.product_retriever
        )
        self.competitive_search = CompetitiveSearchSystem(self.battle_agents)
        
        # FIX #1: DEFER agent factory initialization
        # Will be initialized asynchronously in _ensure_agent_factory()
        self.agent_factory = None
        self._agent_factory_initialized = False
        self._agent_factory_lock = asyncio.Lock()
        
        # Initialize MemoryManager
        self.memory_manager = MemoryManager(self.user_kg)
        logger.info("Initialized MemoryManager")
        
        # Setup memory function
        self.memory_setup_func = self._setup_memory_for_user
        
        # Initialize recommender manager (will get agent factory later)
        logger.info("Initializing recommender manager...")
        self.enhanced_recommender_manager = EnhancedRecommenderManagerAsync(
            data_store=self.data_store,
            user_kg=self.user_kg,
            product_retriever=self.product_retriever,
            memory_setup_func=self.memory_setup_func,
            stylist_agent=None,
            competitive_search=self.competitive_search
        )
        
        # Initialize chat manager (will get agent factory later)
        logger.info("Creating chat manager...")
        self.chat_manager = EnhancedChatManagerAsync(
            stylist_agent=None,
            user_kg=self.user_kg,
            data_store=self.data_store,
            product_retriever=self.product_retriever,
            memory_setup_func=self.memory_setup_func,
            parent_app=self,
            competitive_search=self.competitive_search
        )
        
        # Track active sessions with size limit
        self.active_sessions = {}
        self.max_sessions = 100
        
        # User registry
        self.registered_users = {}
        
        # Memory optimization settings
        self.memory_optimization_interval = 3600
        self.memory_optimization_task = None
        
        # Start optimization task
        self.memory_optimization_task = asyncio.create_task(self._memory_optimization_worker())
        
        # Verify database schema
        asyncio.create_task(self._setup_database_schema())
        
        logger.info("✅ AI Stylist initialized with Season 3 fixes!")
    
    async def _ensure_agent_factory(self):
        """
        FIX #1: Ensure agent factory is initialized (async-safe)
        This solves the async/sync initialization issue
        """
        if not self._agent_factory_initialized:
            async with self._agent_factory_lock:
                if not self._agent_factory_initialized:
                    logger.info("Initializing AgentFactory asynchronously...")
                    try:
                        # Use async version if available
                        from agent_factory import get_agent_factory_async
                        self.agent_factory = await get_agent_factory_async()
                    except ImportError:
                        # Fall back to sync version
                        self.agent_factory = get_agent_factory()
                    
                    self._agent_factory_initialized = True
                    logger.info("✅ AgentFactory initialized successfully")
        
        return self.agent_factory
    
    async def _setup_memory_for_user(self, user_id=None, neo4j_client=None):
        """Setup memory for user"""
        return await self.memory_manager.create_memory(
            user_id=user_id,
            enable_mcp=True
        )
    
    async def _setup_database_schema(self):
        """Set up and verify the database schema"""
        try:
            if hasattr(self.user_kg, 'ensure_schema'):
                await self.user_kg.ensure_schema()
            
            stats = await self.data_store.get_stats()
            logger.info(f"HybridDataStore statistics: {stats}")
        except Exception as e:
            logger.error(f"Error setting up database schema: {e}")
            logger.warning("Continuing with limited database functionality")
    
    async def _memory_optimization_worker(self):
        """Background task to periodically optimize memory"""
        try:
            while True:
                await asyncio.sleep(self.memory_optimization_interval)
                
                # Clean up old sessions
                await self._cleanup_old_sessions()
                
                # Get active sessions with persistent memory
                persistent_sessions = {
                    session_id: session
                    for session_id, session in self.active_sessions.items()
                    if hasattr(session, 'user_id') and session.user_id 
                    and hasattr(session, 'memory') and session.memory
                }
                
                logger.info(f"Optimizing memory for {len(persistent_sessions)} sessions")
                
                for session_id, session in persistent_sessions.items():
                    try:
                        await optimize_memory_async(
                            memory=session.memory,
                            user_id=session.user_id,
                            neo4j_client=self.user_kg
                        )
                    except Exception as e:
                        logger.error(f"Error optimizing memory for session {session_id}: {e}")
                
        except asyncio.CancelledError:
            logger.info("Memory optimization task cancelled")
        except Exception as e:
            logger.error(f"Error in memory optimization worker: {e}")
    
    async def _cleanup_old_sessions(self):
        """Clean up old sessions to prevent memory leak"""
        if len(self.active_sessions) > self.max_sessions:
            sorted_sessions = sorted(
                self.active_sessions.items(),
                key=lambda x: getattr(x[1], 'last_activity_time', datetime.datetime.min)
            )
            
            to_remove = len(self.active_sessions) - int(self.max_sessions * 0.8)
            for session_id, _ in sorted_sessions[:to_remove]:
                del self.active_sessions[session_id]
                logger.info(f"Cleaned up old session: {session_id}")
    
    async def create_session(self, user_id=None):
        """
        Create a new chat session
        FIX #1: Ensure agent factory is initialized before use
        """
        try:
            # FIX #1: Ensure agent factory exists
            await self._ensure_agent_factory()
            
            # Check existing sessions
            if user_id and user_id in self.registered_users:
                existing_session_id = self.registered_users[user_id]
                if existing_session_id in self.active_sessions:
                    return existing_session_id
            
            # Create session
            session = await self.chat_manager.get_or_create_session(user_id=user_id)
            
            if not hasattr(session, 'session_id') or not session.session_id:
                session.session_id = str(uuid.uuid4())
            
            # Create memory and agent
            if not hasattr(session, 'memory') or not session.memory:
                memory = await self.memory_manager.create_memory(
                    user_id=user_id, enable_mcp=True
                )
                session.memory = memory
            
            if not hasattr(session, 'stylist_agent') or not session.stylist_agent:
                stylist_agent = await self.agent_factory.create_stylist_agent(
                    memory=session.memory, enable_mcp=True
                )
                session.stylist_agent = stylist_agent
            
            # Store session with cleanup check
            if len(self.active_sessions) >= self.max_sessions:
                await self._cleanup_old_sessions()
            
            self.active_sessions[session.session_id] = session
            if user_id:
                self.registered_users[user_id] = session.session_id
            
            # Update recommender manager
            if self.enhanced_recommender_manager and hasattr(self.enhanced_recommender_manager, 'ensemble'):
                self.enhanced_recommender_manager.ensemble.stylist_agent = session.stylist_agent
            
            logger.info(f"Created session: {session.session_id} for user: {user_id}")
            return session.session_id
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return str(uuid.uuid4())
    
    def _optimize_battle_parameters(self, query: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        FIX #4: Optimize battle parameters based on query type
        NEVER skips battles - only optimizes HOW the battle runs
        
        For luxury fashion context, adjusts:
        - Prefetch limits (more for browsing, less for specific items)
        - Timeout (longer for complex queries)
        - Detail level (higher for VIP clients)
        """
        params = {
            "prefetch_limit": 10,  # Default
            "timeout": 5.0,  # Default 5 seconds
            "include_details": True,
            "quality_threshold": 0.7
        }
        
        query_lower = query.lower()
        
        # Luxury context adjustments
        luxury_keywords = ["couture", "designer", "luxury", "high-end", "exclusive", "bespoke"]
        if any(word in query_lower for word in luxury_keywords):
            params["prefetch_limit"] = 20  # Get more options for luxury searches
            params["quality_threshold"] = 0.9  # Higher quality bar
            params["include_details"] = True
            logger.info("🎯 Luxury context detected - optimizing for premium results")
        
        # Specific item optimization
        specific_items = ["dress", "gown", "suit", "jacket", "coat"]
        if any(item in query_lower for item in specific_items):
            params["prefetch_limit"] = 15  # Moderate prefetch
            params["timeout"] = 4.0  # Slightly faster
            logger.info("🎯 Specific item search - balanced optimization")
        
        # Occasion-based optimization
        occasions = ["wedding", "gala", "event", "party", "formal"]
        if any(occ in query_lower for occ in occasions):
            params["prefetch_limit"] = 25  # More options for occasions
            params["timeout"] = 6.0  # More time for complex matching
            params["include_details"] = True
            params["quality_threshold"] = 0.8
            logger.info("🎯 Occasion search - optimizing for variety")
        
        # VIP client optimization
        if user_context and user_context.get("vip_status"):
            params["prefetch_limit"] = 30  # Maximum options
            params["timeout"] = 8.0  # No rush for VIP
            params["quality_threshold"] = 0.95  # Only the best
            logger.info("🎯 VIP client - maximum quality optimization")
        
        # Wardrobe building optimization
        if "wardrobe" in query_lower or "capsule" in query_lower or "collection" in query_lower:
            params["prefetch_limit"] = 40  # Need variety for wardrobe
            params["timeout"] = 10.0  # Complex coordination
            params["include_coordination"] = True
            logger.info("🎯 Wardrobe building - optimizing for coordination")
        
        return params
    
    def _apply_luxury_filters(self, filters: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        FIX #4: Apply luxury-specific filters
        """
        luxury_filters = filters.copy()
        
        # Luxury brand tiers
        luxury_brands = [
            "Chanel", "Dior", "Gucci", "Prada", "Versace", "Balenciaga",
            "Saint Laurent", "Bottega Veneta", "Burberry", "Givenchy"
        ]
        
        # Add brand filter if user has brand preferences
        if user_context.get('preferred_brands'):
            luxury_filters['brands'] = user_context['preferred_brands']
        else:
            # Suggest luxury brands by default for high-quality searches
            luxury_filters['suggested_brands'] = luxury_brands[:5]
        
        # Adjust price range for luxury items
        if not luxury_filters.get('min_price'):
            luxury_filters['min_price'] = 500  # Minimum for luxury items
        
        return luxury_filters
    
    async def send_message(self, session_id, message):
        """Send a message to the stylist"""
        if not session_id:
            return "I'm sorry, there was an issue with your session.", {"error": "No session ID"}
        
        # Ensure agent factory is ready
        await self._ensure_agent_factory()
        
        # Get or recover session
        if session_id not in self.active_sessions:
            try:
                session = await self.chat_manager.get_or_create_session(session_id=session_id)
                
                if not hasattr(session, 'stylist_agent'):
                    memory = await self.memory_manager.create_memory(enable_mcp=True)
                    stylist_agent = await self.agent_factory.create_stylist_agent(
                        memory=memory, enable_mcp=True
                    )
                    session.stylist_agent = stylist_agent
                    session.memory = memory
                
                self.active_sessions[session_id] = session
                
            except Exception as e:
                logger.error(f"Error recovering session {session_id}: {e}")
                return "Let's start a new conversation.", {"error": f"Session not found: {session_id}"}
        
        # Process message
        session = self.active_sessions[session_id]
        
        try:
            logger.info(f"🚀 Processing message with BATTLE SYSTEM for session {session_id}")
            response, data = await self.chat_manager.process_message(
                session_id=session_id,
                user_id=session.user_id if hasattr(session, 'user_id') else None,
                message=message
            )
            
            # Record interactions
            if 'products' in data and session_id in self.active_sessions:
                user_id = session.user_id if hasattr(session, 'user_id') else None
                if user_id and hasattr(session, 'record_product_interaction'):
                    for product in data['products']:
                        if 'id' in product:
                            await session.record_product_interaction(
                                product_id=product['id'],
                                interaction_type="recommended"
                            )
            
            # Save memory state
            if hasattr(session, 'user_id') and session.user_id and hasattr(session, 'memory'):
                try:
                    await self.memory_manager.save_memory(session.memory, session.user_id)
                except Exception as e:
                    logger.error(f"Error saving memory: {e}")
            
            return response, data
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return "I encountered an issue. Could you try rephrasing?", {"error": str(e)}
    
    async def get_product_recommendations(self, session_id, product_id=None, query=None, limit=5, occasion=None):
        """
        Get product recommendations using BATTLE SYSTEM
        FIX #4: ALWAYS uses battle system with optimized parameters
        """
        session = await self.get_session(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return []
        
        user_id = session.user_id if hasattr(session, 'user_id') else None
        
        # Get user context for optimization
        user_context = {}
        if hasattr(session, 'get_or_fetch_user_preferences'):
            user_context = await session.get_or_fetch_user_preferences()
        
        # Check VIP status
        if user_id and self.user_kg:
            try:
                user_details = await self.user_kg.get_user_details(user_id)
                if user_details and user_details.get('vip_status'):
                    user_context['vip_status'] = True
            except:
                pass
        
        # Extract occasion from query
        if query and not occasion:
            occasions = ["wedding", "party", "work", "casual", "formal", "date", "dinner", "beach", "gala"]
            query_lower = query.lower()
            for occ in occasions:
                if occ in query_lower:
                    occasion = occ
                    break
        
        # Build the full query
        full_query = query or occasion or "stylish recommendations"
        
        # FIX #4: Get optimized battle parameters
        battle_params = self._optimize_battle_parameters(full_query, user_context)
        
        # ALWAYS use battle system for queries
        try:
            logger.info(f"🎯 Executing OPTIMIZED Battle for: {full_query}")
            logger.info(f"Battle parameters: {battle_params}")
            
            # Build filters
            filters = {}
            if occasion:
                filters['occasion'] = occasion
            
            # Apply luxury filters if detected
            if battle_params.get('quality_threshold', 0.7) > 0.8:
                filters = self._apply_luxury_filters(filters, user_context)
            
            if user_context.get('budget_range'):
                filters['min_price'] = user_context['budget_range'].get('min')
                filters['max_price'] = user_context['budget_range'].get('max')
            
            # Execute battle with optimized parameters
            battle_results = await self.competitive_search.execute_battle(
                query=full_query,
                filters=filters,
                limit=limit,
                user_context=user_context,
                **battle_params  # Pass optimization parameters
            )
            
            # Get winner's results
            judgment = battle_results.get('judgment', {})
            winner = judgment.get('winner', 'vector')
            
            if winner == 'cypher':
                results = battle_results['agents']['cypher']['products']
                logger.info(f"🏆 CypherBot won with {len(results)} products")
            else:
                results = battle_results['agents']['vector']['products']
                logger.info(f"🏆 VibeBot won with {len(results)} products")
            
            if results:
                filtered = self._filter_valid_products(results)
                if filtered:
                    await self._record_product_interactions(session, filtered)
                    return filtered[:limit]
            
            logger.warning("Battle system returned no results")
            return []
            
        except Exception as e:
            logger.error(f"Battle system error: {e}")
            return []
    
    async def get_session(self, session_id):
        """Get a session by ID"""
        if not session_id:
            return None
        
        if session_id in self.active_sessions:
            return self.active_sessions[session_id]
        
        try:
            session = await self.chat_manager.get_or_create_session(session_id=session_id)
            if session:
                self.active_sessions[session_id] = session
                return session
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}")
        
        return None
    
    def _filter_valid_products(self, products):
        """Filter out invalid products"""
        if not products:
            return []
        
        return [
            product for product in products
            if product.get('price', 0) > 0 
            and product.get('title')
            and 'test' not in product.get('title', '').lower()
            and 'untitled' not in product.get('title', '').lower()
        ]
    
    async def _record_product_interactions(self, session, products):
        """Record product interactions"""
        try:
            if hasattr(session, 'record_product_interaction'):
                for product in products:
                    if 'id' in product:
                        await session.record_product_interaction(
                            product_id=product['id'],
                            interaction_type="recommended"
                        )
        except Exception as e:
            logger.error(f"Error recording interactions: {e}")
    
    async def record_product_interaction(self, session_id, product_id, interaction_type="viewed"):
        """Record a product interaction for a user"""
        session = await self.get_session(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return False
        
        try:
            if hasattr(session, 'record_product_interaction'):
                return await session.record_product_interaction(
                    product_id=product_id,
                    interaction_type=interaction_type
                )
            
            user_id = session.user_id if hasattr(session, 'user_id') else None
            
            if not user_id:
                logger.warning(f"Cannot record interaction: no user ID for session {session_id}")
                return False
            
            return await self.data_store.record_interaction(
                user_id=user_id,
                product_id=product_id,
                interaction_type=interaction_type
            )
            
        except Exception as e:
            logger.error(f"Error recording product interaction: {e}")
            return False
    
    async def add_user_preference(self, session_id, preference_type, preference_value):
        """Add a user preference"""
        session = await self.get_session(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return False
        
        try:
            if hasattr(session, 'add_preference'):
                return await session.add_preference(
                    preference_type=preference_type,
                    preference_value=preference_value
                )
            
            user_id = session.user_id if hasattr(session, 'user_id') else None
            
            if not user_id:
                logger.warning(f"Cannot add preference: no user ID for session {session_id}")
                return False
            
            return await self.user_kg.update_user_preference(
                user_id=user_id,
                preference_type=preference_type,
                preference_value=preference_value
            )
            
        except Exception as e:
            logger.error(f"Error adding user preference: {e}")
            return False
    
    async def get_user_preferences(self, session_id):
        """Get user preferences for a session"""
        session = await self.get_session(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return {}
        
        try:
            if hasattr(session, 'get_or_fetch_user_preferences'):
                return await session.get_or_fetch_user_preferences()
            
            user_id = session.user_id if hasattr(session, 'user_id') else None
            
            if not user_id:
                logger.warning(f"Cannot get preferences: no user ID for session {session_id}")
                return {}
            
            preferences = await self.user_kg.get_user_preferences(user_id)
            return preferences
            
        except Exception as e:
            logger.error(f"Error getting user preferences: {e}")
            return {}
    
    async def close(self):
        """Clean up resources and close connections"""
        try:
            # Cancel optimization task
            if self.memory_optimization_task:
                self.memory_optimization_task.cancel()
                try:
                    await self.memory_optimization_task
                except asyncio.CancelledError:
                    pass
            
            # Save all memory states
            for session_id, session in self.active_sessions.items():
                if hasattr(session, 'user_id') and session.user_id and hasattr(session, 'memory'):
                    try:
                        await self.memory_manager.save_memory(session.memory, session.user_id)
                    except Exception as e:
                        logger.error(f"Error saving memory for {session_id}: {e}")
            
            # Close sessions
            for session_id, session in self.active_sessions.items():
                if hasattr(session, 'close'):
                    try:
                        await session.close()
                    except Exception as e:
                        logger.error(f"Error closing session {session_id}: {e}")
            
            # Clear session pool
            self.active_sessions.clear()
            
            # Close connections
            if hasattr(self.user_kg, 'close'):
                await self.user_kg.close()
            
            # Clean up agent factory if it was initialized
            if self.agent_factory:
                await self.agent_factory.cleanup()
            
            # Close recommenders
            if hasattr(self, 'enhanced_recommender_manager'):
                for name, recommender in self.enhanced_recommender_manager.recommenders.items():
                    if hasattr(recommender, 'close'):
                        try:
                            await recommender.close()
                        except Exception as e:
                            logger.error(f"Error closing recommender {name}: {e}")
            
            logger.info("✅ Closed AI Stylist resources")
            
        except Exception as e:
            logger.error(f"Error closing resources: {e}")