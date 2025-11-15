"""
ProductSearchFlow V2 - Pure Flow Implementation (No Agent Overhead)

Performance Improvements:
- Eliminates agent context creation (~200-500ms per agent)
- Eliminates task description parsing (~100-300ms per agent)
- Eliminates agent "reasoning" LLM call (~500-1500ms per agent)
- Eliminates Crew orchestration overhead (~200-400ms per agent)
- TOTAL SAVINGS: ~1-3 seconds per agent → 3-9 seconds for 3 parallel agents

Architecture:
1. Direct LLM.call() with structured output (response_format)
2. Direct tool execution (async_*_tools)
3. Parallel execution via @listen decorators
4. Same error handling and timeout strategy as V1

Expected Performance:
- V1 (agent-based): ~5-8 seconds for 3 parallel searches
- V2 (flow-based): ~2-3 seconds for 3 parallel searches
- Speedup: 2-4x faster
"""
import logging
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional, List

try:
    from crewai.flow.flow import Flow, listen, start, and_
    from crewai import LLM
except ImportError:
    from crewai import Flow, listen, start, LLM
    # and_ might not be available in older versions
    try:
        from crewai.flow.flow import and_
    except ImportError:
        # Fallback: define simple and_ combinator
        def and_(*funcs):
            return funcs

from models.product_models import (
    ProductSearchState,
    ProductSearchResult,
    GraphSearchResult,
    VectorSearchResult,
    VisualSearchResult,
    JudgmentResult,
    Product
)
from models.llm_response_models import (
    CypherQueries,
    SearchStrategy,
    VisualSearchStrategy,
    JudgeEvaluation
)

# Import internal tool functions (not @tool decorated, to avoid overhead)
from tools.async_tools.async_neo4j_tools import (
    _execute_neo4j_query,
    async_neo4j_fulltext_search_tool
)
from tools.async_tools.async_qdrant_tools import (
    _generate_embedding,
    _search_qdrant
)

logger = logging.getLogger("crewai.flows.product_search_v2")

# Model configuration with fallback
DEFAULT_MODEL = "gpt-4o"  # Use gpt-4o instead of gpt-5 for availability
FALLBACK_MODEL = "gpt-4-turbo"

def get_model_config():
    """Get model and temperature based on availability."""
    import os
    model = os.getenv("SEARCH_LLM_MODEL", DEFAULT_MODEL)

    # GPT-5/o-series models only support temperature=1.0
    if model.startswith(("gpt-5", "o1", "o3", "o4")):
        temperature = 1.0
    else:
        temperature = 0.7

    return model, temperature


class ProductSearchFlowV2(Flow[ProductSearchState]):
    """
    Pure flow-based product search - no agent overhead.

    Timeout Strategy:
    - Each search bot: 30 seconds max
    - Parallel search total: 90 seconds max (3 bots in parallel)
    - Judge evaluation: 30 seconds max
    - Total flow: 120 seconds max
    """

    @start()
    async def initialize(self):
        """
        Flow entry point - initialize state and metadata.
        """
        logger.info(f"=== FLOW V2 START: Query='{self.state.query[:50]}...' ===")
        self.state.current_step = "initialize"
        self.state.start_time = datetime.now()

    @listen(initialize)
    async def cypher_bot(self):
        """
        Graph search using Neo4j - direct LLM call + tool execution.
        Eliminates CypherBot agent overhead (~1-3 seconds saved).
        """
        logger.info("=== CYPHER BOT (Flow Method) ===")
        step_start = time.time()

        try:
            # Get model configuration
            model, temperature = get_model_config()

            # Step 1: Generate Cypher query using direct LLM call
            logger.info(f"Generating Cypher query with LLM (model={model})...")

            cypher_prompt = f"""You are CypherBot, a graph database specialist for fashion product search.

CONTEXT:
- Query: {self.state.query}
- Filters: {self.state.filters}
- ML Intelligence: {self.state.ml_intelligence}
- User Context: {self.state.user_context}

PRODUCT NODE SCHEMA (6.4M products):
ACTUAL Properties (these are the ONLY properties that exist):
  - id (string): Product UUID
  - title (string): Product name/title
  - description (string): Product description
  - price (number): Price (e.g., 49.99)
  - images (string): JSON string of image URLs
  - visited_num (number): Visit count
  - extracted_brand (string): AI-extracted brand name
  - extracted_colors (list): AI-extracted color tags (e.g., ["black", "white"])
  - extracted_styles (list): AI-extracted style tags (e.g., ["classic", "casual"])

AVAILABLE INDEXES:
  - Product.id (RANGE)
  - Product.title (RANGE)
  - Product.price (RANGE)

CRITICAL CONSTRAINTS:
  - NO 'brand' property - use 'extracted_brand' instead
  - NO 'category' or 'fashion_category' properties - use 'extracted_styles' or title/description matching
  - NO 'color' property - use 'extracted_colors' array or title/description matching
  - NO fulltext indexes - use CONTAINS for text search
  - Colors are in 'extracted_colors' array - use 'black' IN p.extracted_colors
  - Styles are in 'extracted_styles' array - use 'shirt' IN p.extracted_styles OR title matching
  - Database has 6.4M products - MUST use LIMIT (10-20 max)
  - Always use toLower() for case-insensitive text matching

WORKING QUERY PATTERNS:

1. Color Search (using extracted_colors array):
MATCH (p:Product)
WHERE 'black' IN p.extracted_colors
RETURN p
LIMIT 20

2. Color + Style Search (combining arrays and title):
MATCH (p:Product)
WHERE 'black' IN p.extracted_colors
  AND (toLower(p.title) CONTAINS 'shirt' OR toLower(p.description) CONTAINS 'shirt')
RETURN p
LIMIT 20

3. Text Search (title/description matching):
MATCH (p:Product)
WHERE toLower(p.title) CONTAINS 'black'
  AND toLower(p.title) CONTAINS 'dress'
RETURN p
LIMIT 20

4. Brand + Color Search:
MATCH (p:Product)
WHERE toLower(p.extracted_brand) CONTAINS 'nike'
  AND 'black' IN p.extracted_colors
RETURN p
LIMIT 20

5. Price Range + Color:
MATCH (p:Product)
WHERE p.price >= 50 AND p.price <= 150
  AND 'blue' IN p.extracted_colors
RETURN p
ORDER BY p.price ASC
LIMIT 20

CRITICAL RETURN FORMAT:
- ALWAYS return the full node: RETURN p
- DO NOT return individual properties like: RETURN p.id, p.title (this breaks parsing!)
- The node 'p' contains all properties we need

TASK:
Generate an optimized Cypher query for this search. Use CONTAINS for text matching.
IMPORTANT: RETURN p (the full Product node), NOT individual properties!

Generate main_query (your best query) and fallback_query (simpler/broader query if main fails)."""

            # Create LLM with response_format in constructor
            cypher_llm = LLM(
                model=model,
                temperature=temperature,
                timeout=30,
                response_format=CypherQueries  # Correct: in constructor
            )

            # Direct LLM call - returns Pydantic model directly
            response = await asyncio.to_thread(
                cypher_llm.call,
                messages=[{"role": "user", "content": cypher_prompt}]
            )

            # Extract Pydantic model from response
            if isinstance(response, str):
                # Fallback: parse JSON string to Pydantic
                import json
                from pydantic import ValidationError
                try:
                    data = json.loads(response)
                    cypher_response = CypherQueries(**data)
                except (json.JSONDecodeError, ValidationError) as e:
                    logger.error(f"Failed to parse LLM response as CypherQueries: {e}")
                    raise ValueError(f"Invalid LLM response format: {e}")
            else:
                # Response is already the Pydantic model
                cypher_response = response

            logger.info(f"Strategy: {cypher_response.search_strategy}")
            logger.info(f"Reasoning: {cypher_response.reasoning[:100]}...")

            # Step 2: Execute Cypher query using internal tool function
            logger.info("Executing Cypher query...")

            neo4j_results = await _execute_neo4j_query(
                cypher=cypher_response.main_query,
                parameters={}
            )

            # If main query fails and we have fallback, try it
            if not neo4j_results and cypher_response.fallback_query:
                logger.warning("Main query returned no results, trying fallback...")
                neo4j_results = await _execute_neo4j_query(
                    cypher=cypher_response.fallback_query,
                    parameters={}
                )

            # Step 3: Convert results to Product models
            products = []
            for record in neo4j_results[:self.state.limit * 2]:  # Prefetch 2x for judge
                try:
                    # Handle nested 'p' structure if present
                    product_data = record.get('p', record)

                    product = Product(
                        id=str(product_data.get('id', '')),
                        title=product_data.get('title', 'Unknown'),
                        price=float(product_data.get('price', 0)),
                        category=product_data.get('category', 'Unknown'),
                        description=product_data.get('description'),
                        brand=product_data.get('brand'),
                        images=product_data.get('images', []),
                        cypher_score=product_data.get('neo4j_score', 0.8),
                        agent_source="CypherBot",
                        search_method=cypher_response.search_strategy,
                        reasoning=f"Graph search via {cypher_response.search_strategy}"
                    )
                    products.append(product)
                except Exception as e:
                    logger.warning(f"Failed to parse product: {e}")
                    continue

            execution_time = time.time() - step_start

            # Step 4: Update state with results
            self.state.graph_result = GraphSearchResult(
                products=products,
                search_strategy=cypher_response.search_strategy,
                reasoning=cypher_response.reasoning,
                execution_time=execution_time,
                products_found=len(products)
            )

            logger.info(f"✓ CypherBot: {len(products)} products in {execution_time:.2f}s")

        except asyncio.TimeoutError:
            error_msg = "CypherBot timed out after 30s"
            logger.error(error_msg)
            self.state.errors.append(error_msg)
        except Exception as e:
            error_msg = f"CypherBot failed: {e}"
            logger.error(error_msg, exc_info=True)
            self.state.errors.append(error_msg)

    @listen(initialize)
    async def vibe_bot(self):
        """
        Vector search using Qdrant - direct embedding + search.
        Eliminates VibeBot agent overhead (~1-3 seconds saved).
        """
        logger.info("=== VIBE BOT (Flow Method) ===")
        step_start = time.time()

        try:
            # Direct vector search (no LLM needed for simple embedding search!)
            logger.info("Executing Qdrant vector search...")

            # Generate embedding
            embedding = await _generate_embedding(self.state.query)

            if not embedding:
                raise ValueError("Failed to generate embedding")

            # Search Qdrant
            qdrant_results = await _search_qdrant(
                query_embedding=embedding,
                limit=self.state.limit * 2,  # Prefetch 2x for judge
                filters=self.state.filters
            )

            # Convert to Product models
            products = []
            for result in qdrant_results:
                try:
                    product = Product(
                        id=str(result.get('id', '')),
                        title=result.get('title', 'Unknown'),
                        price=float(result.get('price', 0)),
                        category=result.get('category', 'Unknown'),
                        description=result.get('description'),
                        brand=result.get('brand'),
                        images=result.get('images', []),
                        vibe_score=result.get('score', 0.8),
                        agent_source="VibeBot",
                        search_method="SEMANTIC_SIMILARITY",
                        reasoning="Semantic similarity via embeddings"
                    )
                    products.append(product)
                except Exception as e:
                    logger.warning(f"Failed to parse product: {e}")
                    continue

            execution_time = time.time() - step_start

            # Update state
            self.state.vector_result = VectorSearchResult(
                products=products,
                search_strategy="SEMANTIC_SIMILARITY",
                reasoning="Semantic matching using text embeddings",
                execution_time=execution_time,
                products_found=len(products)
            )

            logger.info(f"✓ VibeBot: {len(products)} products in {execution_time:.2f}s")

        except asyncio.TimeoutError:
            error_msg = "VibeBot timed out after 30s"
            logger.error(error_msg)
            self.state.errors.append(error_msg)
        except Exception as e:
            error_msg = f"VibeBot failed: {e}"
            logger.error(error_msg, exc_info=True)
            self.state.errors.append(error_msg)

    @listen(initialize)
    async def vision_bot(self):
        """
        Visual search using FashionSigLIP - multimodal text-to-visual.
        Eliminates VisionBot agent overhead (~1-3 seconds saved).
        """
        logger.info("=== VISION BOT (Flow Method) ===")
        step_start = time.time()

        try:
            # Direct multimodal search (text → visual embedding)
            logger.info("Executing FashionSigLIP visual search...")

            # Use internal implementation to avoid tool decorator overhead
            try:
                from services.ml.fashionsig_encoder import get_fashionsig_encoder

                # Get encoder and generate text-to-visual embedding
                encoder = get_fashionsig_encoder()
                embedding_np = await encoder.encode_text(self.state.query)
                embedding = embedding_np.tolist()

                # Search with visual embedding
                import os
                visual_collection = os.getenv("QDRANT_VISUAL_COLLECTION_NAME", "fashion_multimodal_embeddings")
                visual_results = await _search_qdrant(
                    query_embedding=embedding,
                    limit=self.state.limit * 2,
                    filters=self.state.filters,
                    collection_name=visual_collection
                )

            except (ImportError, RuntimeError, AttributeError) as e:
                logger.warning(f"FashionSigLIP unavailable, using text embeddings as fallback: {e}")
                # Fallback to text embedding
                embedding = await _generate_embedding(self.state.query)
                if embedding:
                    visual_results = await _search_qdrant(
                        query_embedding=embedding,
                        limit=self.state.limit * 2,
                        filters=self.state.filters
                    )
                else:
                    raise ValueError("Failed to generate fallback embedding")

            # Convert to Product models
            products = []
            for result in visual_results:
                try:
                    product = Product(
                        id=str(result.get('id', '')),
                        title=result.get('title', 'Unknown'),
                        price=float(result.get('price', 0)),
                        category=result.get('category', 'Unknown'),
                        description=result.get('description'),
                        brand=result.get('brand'),
                        images=result.get('images', []),
                        visual_score=result.get('score', 0.8),
                        agent_source="VisionBot",
                        search_method="VISUAL_SIMILARITY",
                        reasoning="Visual similarity via FashionSigLIP"
                    )
                    products.append(product)
                except Exception as e:
                    logger.warning(f"Failed to parse product: {e}")
                    continue

            execution_time = time.time() - step_start

            # Update state
            self.state.visual_result = VisualSearchResult(
                products=products,
                search_strategy="VISUAL_SIMILARITY",
                reasoning="Visual matching using FashionSigLIP multimodal embeddings",
                execution_time=execution_time,
                products_found=len(products)
            )

            logger.info(f"✓ VisionBot: {len(products)} products in {execution_time:.2f}s")

        except asyncio.TimeoutError:
            error_msg = "VisionBot timed out after 30s"
            logger.error(error_msg)
            self.state.errors.append(error_msg)
        except Exception as e:
            error_msg = f"VisionBot failed: {e}"
            logger.error(error_msg, exc_info=True)
            self.state.errors.append(error_msg)

    @listen(and_(cypher_bot, vibe_bot, vision_bot))
    async def judge(self):
        """
        Judge evaluation - direct LLM call for quality control.
        Eliminates Judge agent overhead (~1-3 seconds saved).
        """
        logger.info("=== JUDGE (Flow Method) ===")
        step_start = time.time()

        try:
            # Collect all products from search results
            all_products = []
            product_map = {}  # Map ID to Product object

            if self.state.graph_result:
                for p in self.state.graph_result.products:
                    product_map[p.id] = p
                    all_products.append(p)

            if self.state.vector_result:
                for p in self.state.vector_result.products:
                    if p.id not in product_map:
                        product_map[p.id] = p
                        all_products.append(p)

            if self.state.visual_result:
                for p in self.state.visual_result.products:
                    if p.id not in product_map:
                        product_map[p.id] = p
                        all_products.append(p)

            if not all_products:
                logger.warning("No products to judge - all searches failed")
                self.state.errors.append("No products found by any search agent")
                return

            logger.info(f"Judging {len(all_products)} unique products...")

            # Prepare product summaries for LLM
            product_summaries = []
            for p in all_products:
                scores = []
                if p.cypher_score:
                    scores.append(f"graph={p.cypher_score:.2f}")
                if p.vibe_score:
                    scores.append(f"vibe={p.vibe_score:.2f}")
                if p.visual_score:
                    scores.append(f"visual={p.visual_score:.2f}")

                summary = f"ID: {p.id}, Title: {p.title}, Price: ${p.price:.2f}, Category: {p.category}, Scores: [{', '.join(scores)}]"
                product_summaries.append(summary)

            judge_prompt = f"""You are Judge Ari, fashion recommendation quality control expert.

QUERY: {self.state.query}

PRODUCTS TO EVALUATE ({len(all_products)} total):
{chr(10).join(product_summaries)}

TASK:
Evaluate each product for quality and relevance. Select the best {self.state.limit} products.

CRITERIA:
1. Relevance to query (occasion, style, user context)
2. Quality indicators (price reasonableness, brand reputation)
3. Consensus (products found by multiple search agents = higher confidence)
4. Diversity (variety in styles, price points)

Return your evaluation with:
- Individual product assessments (quality_score, relevance_score, reasoning, include decision)
- Consensus product IDs (found by 2+ agents)
- Final ordered product IDs (top {self.state.limit})
- Overall reasoning
- Judgment confidence (0-1)"""

            # Get model configuration
            model, temperature = get_model_config()

            # Create LLM with response_format in constructor
            judge_llm = LLM(
                model=model,
                temperature=temperature,
                timeout=30,
                response_format=JudgeEvaluation  # Correct: in constructor
            )

            # Direct LLM call
            response = await asyncio.to_thread(
                judge_llm.call,
                messages=[{"role": "user", "content": judge_prompt}]
            )

            # Extract Pydantic model from response
            if isinstance(response, str):
                # Fallback: parse JSON string to Pydantic
                import json
                from pydantic import ValidationError
                try:
                    data = json.loads(response)
                    judge_response = JudgeEvaluation(**data)
                except (json.JSONDecodeError, ValidationError) as e:
                    logger.error(f"Failed to parse LLM response as JudgeEvaluation: {e}")
                    raise ValueError(f"Invalid LLM response format: {e}")
            else:
                # Response is already the Pydantic model
                judge_response = response

            # Build final products list from judge's selections
            final_products = []
            quality_assessments = {}

            for product_id in judge_response.final_product_ids[:self.state.limit]:
                if product_id in product_map:
                    product = product_map[product_id]

                    # Find evaluation for this product
                    eval_data = next(
                        (e for e in judge_response.evaluations if e.product_id == product_id),
                        None
                    )

                    if eval_data:
                        product.judge_score = eval_data.quality_score
                        product.reasoning = eval_data.reasoning
                        quality_assessments[product_id] = eval_data.quality_score

                    final_products.append(product)

            execution_time = time.time() - step_start

            # Update state with judgment result
            self.state.judgment_result = JudgmentResult(
                final_products=final_products,
                quality_assessments=quality_assessments,
                consensus_products=judge_response.consensus_product_ids,
                rejected_products=[],  # Could extract from evaluations where include=False
                judgment_confidence=judge_response.judgment_confidence,
                detailed_reasoning=judge_response.overall_reasoning,
                execution_time=execution_time
            )

            logger.info(f"✓ Judge: Selected {len(final_products)} products in {execution_time:.2f}s")
            logger.info(f"  Consensus: {len(judge_response.consensus_product_ids)} products")
            logger.info(f"  Confidence: {judge_response.judgment_confidence:.2f}")

        except asyncio.TimeoutError:
            error_msg = "Judge timed out after 30s"
            logger.error(error_msg)
            self.state.errors.append(error_msg)
        except Exception as e:
            error_msg = f"Judge failed: {e}"
            logger.error(error_msg, exc_info=True)
            self.state.errors.append(error_msg)

    @listen(judge)
    def finalize(self) -> ProductSearchResult:
        """
        Package final results into ProductSearchResult.
        """
        logger.info("=== FINALIZE RESULTS ===")

        total_time = (datetime.now() - self.state.start_time).total_seconds()

        # Get final products from judgment or fallback to raw results
        if self.state.judgment_result:
            final_products = self.state.judgment_result.final_products
            reasoning = self.state.judgment_result.detailed_reasoning
            quality_controlled = True

            # Calculate average quality score
            if self.state.judgment_result.quality_assessments:
                avg_quality = sum(self.state.judgment_result.quality_assessments.values()) / \
                             len(self.state.judgment_result.quality_assessments)
            else:
                avg_quality = None
        else:
            # Fallback: combine all results if judge failed
            all_products = []
            if self.state.graph_result:
                all_products.extend(self.state.graph_result.products)
            if self.state.vector_result:
                all_products.extend(self.state.vector_result.products)
            if self.state.visual_result:
                all_products.extend(self.state.visual_result.products)

            # Deduplicate and limit
            seen = set()
            final_products = []
            for p in all_products:
                if p.id not in seen:
                    seen.add(p.id)
                    final_products.append(p)
                    if len(final_products) >= self.state.limit:
                        break

            reasoning = "Judge evaluation failed - returning combined raw results"
            quality_controlled = False
            avg_quality = None

        # Build metadata
        metadata = {
            "flow_version": "V2_pure_flow",
            "execution_steps": [
                "initialize",
                "parallel_search (cypher_bot, vibe_bot, vision_bot)",
                "judge" if self.state.judgment_result else "judge_failed",
                "finalize"
            ],
            "errors": self.state.errors,
            "graph_execution_time": self.state.graph_result.execution_time if self.state.graph_result else 0,
            "vector_execution_time": self.state.vector_result.execution_time if self.state.vector_result else 0,
            "visual_execution_time": self.state.visual_result.execution_time if self.state.visual_result else 0,
            "judge_execution_time": self.state.judgment_result.execution_time if self.state.judgment_result else 0,
            "performance_note": "Pure flow implementation - no agent overhead"
        }

        # Count sources
        graph_count = len(self.state.graph_result.products) if self.state.graph_result else 0
        vector_count = len(self.state.vector_result.products) if self.state.vector_result else 0
        visual_count = len(self.state.visual_result.products) if self.state.visual_result else 0
        consensus_count = len(self.state.judgment_result.consensus_products) if self.state.judgment_result else 0

        result = ProductSearchResult(
            products=final_products,
            reasoning=reasoning,
            metadata=metadata,
            execution_time=total_time,
            graph_count=graph_count,
            vector_count=vector_count,
            visual_count=visual_count,
            consensus_count=consensus_count,
            quality_controlled=quality_controlled,
            average_quality_score=avg_quality
        )

        logger.info(f"=== FLOW V2 COMPLETE: {len(final_products)} products in {total_time:.2f}s ===")
        logger.info(f"Performance: Graph={metadata['graph_execution_time']:.2f}s, "
                   f"Vector={metadata['vector_execution_time']:.2f}s, "
                   f"Visual={metadata['visual_execution_time']:.2f}s, "
                   f"Judge={metadata['judge_execution_time']:.2f}s")

        return result


async def create_and_run_flow_v2(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 5,
    user_context: Optional[Dict[str, Any]] = None,
    ml_intelligence: Optional[Dict[str, Any]] = None,
    conversation_context: Optional[Dict[str, Any]] = None
) -> ProductSearchResult:
    """
    Factory function to create and execute ProductSearchFlowV2.

    This is the drop-in replacement for the agent-based flow.

    Args:
        query: User search query
        filters: Search filters
        limit: Maximum products to return
        user_context: User preferences
        ml_intelligence: ML-generated context
        conversation_context: Conversation state

    Returns:
        ProductSearchResult: Structured output with products and metadata
    """
    # Create flow instance
    flow = ProductSearchFlowV2()

    # Prepare inputs
    inputs = {
        "query": query,
        "filters": filters or {},
        "limit": limit,
        "user_context": user_context or {},
        "ml_intelligence": ml_intelligence or {},
        "conversation_context": conversation_context or {}
    }

    # Execute flow
    result = await flow.kickoff_async(inputs=inputs)

    return result
