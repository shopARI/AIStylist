"""
Verbose Battle Executor - Shows detailed agent thought processes
Enhanced version that outputs what each agent is thinking during battles
"""

import logging
import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from services.battle.executor import BattleExecutor

logger = logging.getLogger("services.battle.verbose_executor")

class VerboseBattleExecutor(BattleExecutor):
    """
    Enhanced Battle Executor that shows detailed agent thought processes.
    Outputs real-time information about what each agent is thinking and doing.
    """
    
    def __init__(self, cypher_bot, vibe_bot, judge):
        super().__init__(cypher_bot, vibe_bot, judge)
        self.verbose = True
        logger.info("VerboseBattleExecutor initialized - agent minds will be visible")
    
    async def execute(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5,
        user_context: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        prefetch_limit: int = 10,
        quality_threshold: float = 0.5,
        require_consensus: bool = False
    ) -> Dict[str, Any]:
        """
        Execute a battle with verbose agent mind output.
        """
        start_time = time.time()
        self.stats["battles_executed"] += 1
        
        print(f"🥊 BATTLE ARENA: '{query[:50]}...'")
        print("=" * 80)
        
        try:
            # Show battle preparation
            self._show_battle_preparation(query, filters, ml_intelligence, user_context)
            
            # Prepare battle parameters
            battle_params = {
                "query": query,
                "limit": prefetch_limit,
                "filters": filters,
                "ml_intelligence": ml_intelligence,
                "user_context": user_context
            }
            
            # Execute parallel searches with mind visibility
            print("\n🚀 LAUNCHING PARALLEL AGENT SEARCHES...")
            print("-" * 50)
            cypher_results, vibe_results = await self._verbose_parallel_search(battle_params)
            
            print(f"\n📊 SEARCH RESULTS:")
            print(f"   🤖 CypherBot found: {len(cypher_results)} products")
            print(f"   🎯 VibeBot found: {len(vibe_results)} products")
            
            # Apply consensus requirement if needed
            if require_consensus:
                print(f"\n🤝 APPLYING CONSENSUS FILTER...")
                cypher_results, vibe_results = self._apply_consensus_filter(
                    cypher_results, vibe_results, limit
                )
                print(f"   After consensus: CypherBot={len(cypher_results)}, VibeBot={len(vibe_results)}")
            
            # Judge evaluation with mind visibility
            print(f"\n⚖️  JUDGE ARI EVALUATION PHASE...")
            print("-" * 50)
            judgment = await self._verbose_judge_evaluation(
                cypher_results, vibe_results, query, ml_intelligence, user_context, limit
            )
            
            # Apply quality threshold
            print(f"\n🎯 APPLYING QUALITY THRESHOLD ({quality_threshold})...")
            final_products = self._apply_quality_filter(
                judgment.get("products", []),
                quality_threshold
            )
            print(f"   Products after quality filter: {len(final_products)}")
            
            # Update statistics
            self._update_stats(judgment.get("winner", "unknown"))
            
            # Calculate execution time
            execution_time = time.time() - start_time
            self._update_avg_time(execution_time)
            
            # Show final battle summary
            self._show_battle_summary(judgment, execution_time, final_products)
            
            # Build result
            result = {
                "products": final_products,
                "cypher_count": len(cypher_results),
                "vibe_count": len(vibe_results),
                "winner": judgment.get("winner", "unknown"),
                "reasoning": judgment.get("reasoning", ""),
                "consensus_count": judgment.get("consensus_count", 0),
                "execution_time": execution_time,
                "quality_threshold_applied": quality_threshold,
                "ml_enhanced": bool(ml_intelligence),
                "agent_thoughts": {
                    "cypher_thoughts": getattr(self, '_cypher_thoughts', []),
                    "vibe_thoughts": getattr(self, '_vibe_thoughts', []),
                    "judge_thoughts": getattr(self, '_judge_thoughts', [])
                }
            }
            
            return result
            
        except Exception as e:
            print(f"\n❌ BATTLE SYSTEM ERROR: {e}")
            logger.error(f"Verbose battle execution error: {e}")
            self.stats["total_errors"] += 1
            
            return {
                "products": [],
                "cypher_count": 0,
                "vibe_count": 0,
                "winner": "error",
                "reasoning": str(e),
                "consensus_count": 0,
                "execution_time": time.time() - start_time,
                "error": True
            }
    
    def _show_battle_preparation(self, query, filters, ml_intelligence, user_context):
        """Show the battle preparation phase"""
        print(f"🎯 BATTLE PREPARATION:")
        print(f"   Query: '{query}'")
        
        if filters:
            print(f"   Filters Applied:")
            for key, value in filters.items():
                if value:  # Only show non-empty filters
                    print(f"      • {key}: {value}")
        
        if ml_intelligence:
            print(f"   🧠 ML Intelligence Enhanced: YES")
            self._show_detailed_ml_intelligence(ml_intelligence)
        else:
            print(f"   🧠 ML Intelligence Enhanced: NO")
        
        if user_context:
            print(f"   👤 User Context: Available ({len(user_context)} attributes)")
        else:
            print(f"   👤 User Context: None")
    
    async def _verbose_parallel_search(self, battle_params):
        """Execute searches with detailed agent mind output"""
        # Store thoughts for later display
        self._cypher_thoughts = []
        self._vibe_thoughts = []
        
        print(f"\n🤖 CYPHERBOT MIND:")
        print("   Thinking about graph relationships...")
        print("   Analyzing Neo4j query patterns...")
        print("   Considering user preferences and product connections...")
        
        print(f"\n🎯 VIBEBOT MIND:")
        print("   Processing semantic similarity...")
        print("   Analyzing vector embeddings...")
        print("   Matching aesthetic preferences...")
        
        # Create search tasks with progress tracking
        print(f"\n⏳ EXECUTING SEARCHES IN PARALLEL...")
        
        cypher_task = asyncio.create_task(
            self._track_cypher_search(battle_params)
        )
        
        vibe_task = asyncio.create_task(
            self._track_vibe_search(battle_params)
        )
        
        # Wait for both with error handling
        results = await asyncio.gather(
            cypher_task,
            vibe_task,
            return_exceptions=True
        )
        
        # Process results
        cypher_results = []
        vibe_results = []
        
        # Handle CypherBot results
        if isinstance(results[0], Exception):
            print(f"   ❌ CypherBot encountered error: {results[0]}")
            logger.error(f"CypherBot error: {results[0]}")
        else:
            cypher_results = results[0] if results[0] else []
            print(f"   ✅ CypherBot completed successfully")
        
        # Handle VibeBot results
        if isinstance(results[1], Exception):
            print(f"   ❌ VibeBot encountered error: {results[1]}")
            logger.error(f"VibeBot error: {results[1]}")
        else:
            vibe_results = results[1] if results[1] else []
            print(f"   ✅ VibeBot completed successfully")
        
        return cypher_results, vibe_results
    
    async def _track_cypher_search(self, battle_params):
        """Track CypherBot search with progress updates"""
        try:
            print(f"   🤖 CypherBot: Initiating graph search...")
            start_time = time.time()
            
            results = await self.cypher_bot.search(**battle_params)
            
            search_time = time.time() - start_time
            print(f"   🤖 CypherBot: Found {len(results) if results else 0} products in {search_time:.2f}s")
            
            # Show ML Intelligence usage
            ml_intel = battle_params.get('ml_intelligence')
            if ml_intel and ml_intel.get('cypher_intel'):
                self._show_agent_intelligence_usage("CypherBot", results, ml_intel)
            
            if results:
                print(f"   🤖 CypherBot: Top result confidence levels:")
                for i, product in enumerate(results[:3]):
                    score = product.get('neo4j_score', 0)
                    title = product.get('title', 'Unknown')[:40]
                    print(f"      #{i+1}: {title}... (score: {score:.3f})")
            
            self._cypher_thoughts.append(f"Searched graph in {search_time:.2f}s, found {len(results) if results else 0} matches")
            return results
            
        except Exception as e:
            print(f"   🤖 CypherBot: Error during search - {e}")
            self._cypher_thoughts.append(f"Search failed: {e}")
            raise
    
    async def _track_vibe_search(self, battle_params):
        """Track VibeBot search with progress updates"""
        try:
            print(f"   🎯 VibeBot: Initiating vector search...")
            print(f"   🎯 VibeBot: Battle params: {battle_params}")
            start_time = time.time()
            
            results = await self.vibe_bot.search(**battle_params)
            
            search_time = time.time() - start_time
            print(f"   🎯 VibeBot: Found {len(results) if results else 0} products in {search_time:.2f}s")
            
            # Show ML Intelligence usage
            ml_intel = battle_params.get('ml_intelligence')
            if ml_intel and ml_intel.get('vibe_intel'):
                self._show_agent_intelligence_usage("VibeBot", results, ml_intel)
            
            if results:
                print(f"   🎯 VibeBot: Top result similarity scores:")
                for i, product in enumerate(results[:3]):
                    score = product.get('qdrant_score', 0)
                    title = product.get('title', 'Unknown')[:40]
                    print(f"      #{i+1}: {title}... (similarity: {score:.3f})")
            else:
                print(f"   🎯 VibeBot: No results found - investigating...")
            
            self._vibe_thoughts.append(f"Vector search in {search_time:.2f}s, found {len(results) if results else 0} matches")
            return results
            
        except Exception as e:
            print(f"   🎯 VibeBot: Error during search - {e}")
            self._vibe_thoughts.append(f"Search failed: {e}")
            raise
    
    async def _verbose_judge_evaluation(self, cypher_results, vibe_results, query, ml_context, user_context, limit):
        """Judge evaluation with detailed thought process"""
        self._judge_thoughts = []
        
        print(f"⚖️  Judge Ari: Analyzing battle results...")
        print(f"⚖️  Judge Ari: Comparing {len(cypher_results)} vs {len(vibe_results)} products...")
        
        # Find overlapping products
        cypher_ids = {r.get('id') for r in cypher_results if r.get('id')}
        vibe_ids = {r.get('id') for r in vibe_results if r.get('id')}
        consensus_products = cypher_ids & vibe_ids
        
        if consensus_products:
            print(f"⚖️  Judge Ari: Found {len(consensus_products)} consensus products - strong agreement!")
        else:
            print(f"⚖️  Judge Ari: No consensus products - need to weigh different approaches...")
        
        print(f"⚖️  Judge Ari: Evaluating product quality and relevance...")
        start_time = time.time()
        
        try:
            judgment = await self.judge.evaluate(
                cypher_results=cypher_results,
                vibe_results=vibe_results,
                query=query,
                ml_context=ml_context,
                user_context=user_context,
                limit=limit
            )
            
            eval_time = time.time() - start_time
            print(f"⚖️  Judge Ari: Evaluation completed in {eval_time:.2f}s")
            
            winner = judgment.get('winner', 'unknown')
            reasoning = judgment.get('reasoning', '')
            
            print(f"⚖️  Judge Ari: VERDICT - Winner: {winner.upper()}")
            if reasoning:
                print(f"⚖️  Judge Ari: Reasoning: {reasoning[:100]}...")
            
            self._judge_thoughts.append(f"Evaluated in {eval_time:.2f}s, declared {winner} winner")
            return judgment
            
        except Exception as e:
            print(f"⚖️  Judge Ari: Error during evaluation - {e}")
            self._judge_thoughts.append(f"Evaluation failed: {e}")
            return {
                "products": cypher_results + vibe_results,
                "winner": "error",
                "reasoning": str(e),
                "consensus_count": len(consensus_products)
            }
    
    def _show_battle_summary(self, judgment, execution_time, final_products):
        """Show final battle summary"""
        print(f"\n" + "=" * 80)
        print(f"🏆 BATTLE SUMMARY")
        print("=" * 80)
        print(f"⏱️  Total Battle Time: {execution_time:.2f}s")
        print(f"🏆 Winner: {judgment.get('winner', 'unknown').upper()}")
        print(f"🎯 Final Products Selected: {len(final_products)}")
        
        if judgment.get('reasoning'):
            print(f"💭 Judge's Reasoning: {judgment['reasoning']}")
        
        print(f"🤝 Consensus Products: {judgment.get('consensus_count', 0)}")
        print("=" * 80)
    
    def _show_detailed_ml_intelligence(self, ml_intelligence):
        """Show detailed breakdown of what each ML Intelligence layer is doing"""
        print(f"      📊 ML INTELLIGENCE BREAKDOWN:")
        
        # CypherBot Intelligence
        if 'cypher_intel' in ml_intelligence and ml_intelligence['cypher_intel']:
            cypher_intel = ml_intelligence['cypher_intel']
            print(f"         🤖 CypherBot Intelligence ({len(cypher_intel)} sources):")
            
            for source_name, intel_data in cypher_intel.items():
                if isinstance(intel_data, dict):
                    # Show what intelligence types are available
                    intel_types = []
                    if 'user_patterns' in intel_data:
                        patterns = intel_data['user_patterns']
                        if patterns.get('popular_categories'):
                            intel_types.append(f"Popular categories: {patterns['popular_categories'][:2]}")
                        if patterns.get('common_purchases'):
                            intel_types.append(f"Purchase patterns detected")
                    if 'graph_insights' in intel_data:
                        intel_types.append("Graph relationship insights")
                    if 'behavioral_data' in intel_data:
                        intel_types.append("Behavioral analysis")
                    
                    if intel_types:
                        print(f"            • {source_name}: {', '.join(intel_types)}")
                    else:
                        print(f"            • {source_name}: Intelligence available")
        
        # VibeBot Intelligence  
        if 'vibe_intel' in ml_intelligence and ml_intelligence['vibe_intel']:
            vibe_intel = ml_intelligence['vibe_intel']
            print(f"         🎯 VibeBot Intelligence ({len(vibe_intel)} sources):")
            
            for source_name, intel_data in vibe_intel.items():
                if isinstance(intel_data, dict):
                    intel_types = []
                    if 'visual_features' in intel_data:
                        visual = intel_data['visual_features']
                        if visual.get('colors'):
                            intel_types.append(f"Colors: {visual['colors'][:2]}")
                        if visual.get('style_attributes'):
                            intel_types.append(f"Style attributes detected")
                    if 'style_analysis' in intel_data:
                        style = intel_data['style_analysis']
                        if style.get('mood'):
                            intel_types.append(f"Mood: {style['mood']}")
                        if style.get('formality'):
                            intel_types.append(f"Formality: {style['formality']}")
                    if 'aesthetic_preferences' in intel_data:
                        intel_types.append("Aesthetic preferences")
                    
                    if intel_types:
                        print(f"            • {source_name}: {', '.join(intel_types)}")
                    else:
                        print(f"            • {source_name}: Aesthetic intelligence available")
        
        # Shared Intelligence
        if 'shared_intel' in ml_intelligence and ml_intelligence['shared_intel']:
            shared_intel = ml_intelligence['shared_intel']
            print(f"         🔗 Shared Intelligence ({len(shared_intel)} sources):")
            
            for source_name, intel_data in shared_intel.items():
                if isinstance(intel_data, dict):
                    intel_types = []
                    if 'user_segmentation' in intel_data:
                        seg = intel_data['user_segmentation']
                        if seg.get('segments'):
                            intel_types.append(f"User segments: {seg['segments'][:2]}")
                    if 'trend_analysis' in intel_data:
                        intel_types.append("Trend analysis")
                    if 'cross_agent_insights' in intel_data:
                        intel_types.append("Cross-agent insights")
                    
                    if intel_types:
                        print(f"            • {source_name}: {', '.join(intel_types)}")
                    else:
                        print(f"            • {source_name}: Shared intelligence available")
        
        # Show if intelligence is actually being used
        total_sources = 0
        if ml_intelligence.get('cypher_intel'):
            total_sources += len(ml_intelligence['cypher_intel'])
        if ml_intelligence.get('vibe_intel'):
            total_sources += len(ml_intelligence['vibe_intel'])
        if ml_intelligence.get('shared_intel'):
            total_sources += len(ml_intelligence['shared_intel'])
            
        if total_sources == 0:
            print(f"         ⚠️  ML Intelligence initialized but no active sources")
        else:
            print(f"         ✅ Total Intelligence Sources: {total_sources}")
    
    def _show_agent_intelligence_usage(self, agent_name, results, ml_intelligence):
        """Show how agents are using ML Intelligence during search"""
        if not ml_intelligence:
            return
            
        print(f"      🧠 {agent_name} ML Intelligence Usage:")
        
        # Check if agent received specific intelligence
        agent_key = 'cypher_intel' if 'cypher' in agent_name.lower() else 'vibe_intel'
        
        if agent_key in ml_intelligence and ml_intelligence[agent_key]:
            intel_data = ml_intelligence[agent_key]
            print(f"         • Received {len(intel_data)} intelligence packets")
            print(f"         • Intelligence influenced search strategy")
            print(f"         • Results enhanced with ML insights")
        else:
            print(f"         • No specific intelligence available for {agent_name}")
        
        # Show shared intelligence usage
        if 'shared_intel' in ml_intelligence and ml_intelligence['shared_intel']:
            print(f"         • Using {len(ml_intelligence['shared_intel'])} shared intelligence sources")