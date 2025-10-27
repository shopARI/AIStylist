"""
Enhanced User Service - Stores sophisticated user profiles in Neo4j.
Supports spectrum-based profiling, psychographics, and nuanced style preferences.

Schema maps the Product team's user data wishlist to Neo4j graph structure.
"""

import logging
import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger("services.enhanced_user")

# Import base service to extend
import sys
sys.path.insert(0, '/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27')
from services.user.knowledge_graph import UserKnowledgeGraphService


class EnhancedUserService(UserKnowledgeGraphService):
    """
    Enhanced user service with sophisticated profiling.

    Extends UserKnowledgeGraphService with:
    - Style Autonomy spectrum storage
    - Gender expression spectrum
    - Psychographic profiling
    - Social handle integration
    - Values & motivations tracking
    - Budget segmentation
    - Metrics tracking
    """

    async def ensure_enhanced_schema(self) -> bool:
        """
        Create enhanced schema for sophisticated user profiling.

        Schema Structure:
        (:User) - Center node
          ├─[:HAS_AUTONOMY_PROFILE]→(:StyleAutonomy)
          ├─[:HAS_EXPRESSION_PROFILE]→(:GenderExpression)
          ├─[:HAS_SELF_EXPRESSION]→(:SelfExpression)
          ├─[:HAS_LIFESTYLE]→(:LifestyleContext)
          ├─[:HAS_VALUES]→(:ValuesProfile)
          ├─[:HAS_BUDGET]→(:BudgetProfile)
          ├─[:CONNECTED_TO {platform}]→(:SocialHandle)
          ├─[:LOVES_BRAND]→(:Brand)
          ├─[:PREFERS_COLOR]→(:Color)
          └─[:DRESSES_FOR]→(:Occasion)
        """

        constraints = [
            # Core nodes
            "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
            "CREATE CONSTRAINT user_email_unique IF NOT EXISTS FOR (u:User) REQUIRE u.email IS UNIQUE",

            # Profile nodes
            "CREATE CONSTRAINT style_autonomy_id IF NOT EXISTS FOR (sa:StyleAutonomy) REQUIRE sa.id IS UNIQUE",
            "CREATE CONSTRAINT gender_expression_id IF NOT EXISTS FOR (ge:GenderExpression) REQUIRE ge.id IS UNIQUE",
            "CREATE CONSTRAINT self_expression_id IF NOT EXISTS FOR (se:SelfExpression) REQUIRE se.id IS UNIQUE",
            "CREATE CONSTRAINT lifestyle_id IF NOT EXISTS FOR (lc:LifestyleContext) REQUIRE lc.id IS UNIQUE",
            "CREATE CONSTRAINT values_profile_id IF NOT EXISTS FOR (vp:ValuesProfile) REQUIRE vp.id IS UNIQUE",
            "CREATE CONSTRAINT budget_profile_id IF NOT EXISTS FOR (bp:BudgetProfile) REQUIRE bp.id IS UNIQUE",

            # Reference nodes
            "CREATE CONSTRAINT brand_name_unique IF NOT EXISTS FOR (b:Brand) REQUIRE b.name IS UNIQUE",
            "CREATE CONSTRAINT color_name_unique IF NOT EXISTS FOR (c:Color) REQUIRE c.name IS UNIQUE",
            "CREATE CONSTRAINT occasion_name_unique IF NOT EXISTS FOR (o:Occasion) REQUIRE o.name IS UNIQUE",
            "CREATE CONSTRAINT social_handle_id IF NOT EXISTS FOR (sh:SocialHandle) REQUIRE sh.id IS UNIQUE",
        ]

        indexes = [
            # User indexes
            "CREATE INDEX user_email_idx IF NOT EXISTS FOR (u:User) ON (u.email)",
            "CREATE INDEX user_username_idx IF NOT EXISTS FOR (u:User) ON (u.username)",
            "CREATE INDEX user_created_idx IF NOT EXISTS FOR (u:User) ON (u.created_at)",

            # Vector index for similarity (1536-dim for OpenAI embeddings)
            """CREATE VECTOR INDEX user_style_embedding_idx IF NOT EXISTS
               FOR (u:User) ON (u.style_embedding)
               OPTIONS {indexConfig: {
                   `vector.dimensions`: 1536,
                   `vector.similarity_function`: 'cosine'
               }}""",

            # Brand/Color/Occasion for fast lookups
            "CREATE INDEX brand_name_idx IF NOT EXISTS FOR (b:Brand) ON (b.name)",
            "CREATE INDEX color_name_idx IF NOT EXISTS FOR (c:Color) ON (c.name)",
            "CREATE INDEX occasion_name_idx IF NOT EXISTS FOR (o:Occasion) ON (o.name)",
        ]

        try:
            # Execute constraints
            for constraint in constraints:
                try:
                    await self.query(constraint)
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Constraint creation warning: {e}")

            # Execute indexes
            for index in indexes:
                try:
                    await self.query(index)
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Index creation warning: {e}")

            logger.info("Enhanced schema creation completed")
            return True

        except Exception as e:
            logger.error(f"Error creating enhanced schema: {e}")
            return False

    async def create_user_from_onboarding(
        self,
        username: str,
        onboarding_responses: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create comprehensive user profile from onboarding responses.

        Args:
            username: Unique username
            onboarding_responses: Complete onboarding data from JSON-based flow

        Returns:
            Created user profile dict
        """

        user_id = f"user_{uuid.uuid4()}"
        timestamp = datetime.utcnow().isoformat()

        # Extract data by category
        autonomy = onboarding_responses.get("style_autonomy", {})
        expression = onboarding_responses.get("gender_expression", {})
        self_expr = onboarding_responses.get("self_expression", {})
        lifestyle = onboarding_responses.get("lifestyle_context", {})
        values = onboarding_responses.get("values_shopping", {})
        budget = onboarding_responses.get("budget", {})
        demographics = onboarding_responses.get("demographics_contact", {})

        # Main user node creation
        query = """
        // Create User node
        CREATE (u:User {
            id: $user_id,
            username: $username,
            email: $email,
            age_range: $age_range,
            location: $location,
            created_at: $timestamp,
            last_active: $timestamp,
            onboarding_completed: true,
            onboarding_version: $onboarding_version
        })

        // Create StyleAutonomy profile
        CREATE (sa:StyleAutonomy {
            id: $user_id + '_autonomy',
            advice_receptiveness: $advice_receptiveness,
            creative_control: $creative_control,
            risk_tolerance: $risk_tolerance,
            decision_making_style: $decision_making_style,
            created_at: $timestamp
        })
        CREATE (u)-[:HAS_AUTONOMY_PROFILE]->(sa)

        // Create GenderExpression profile
        CREATE (ge:GenderExpression {
            id: $user_id + '_expression',
            expression_spectrum: $expression_spectrum,
            style_adjectives: $style_adjectives,
            fit_preferences: $fit_preferences,
            inspiration_sources: $inspiration_sources,
            occasion_flexibility: $occasion_flexibility,
            created_at: $timestamp
        })
        CREATE (u)-[:HAS_EXPRESSION_PROFILE]->(ge)

        // Create SelfExpression profile
        CREATE (se:SelfExpression {
            id: $user_id + '_self_expression',
            statement_level: $statement_level,
            change_readiness: $change_readiness,
            confidence_areas: $confidence_areas,
            pain_points: $pain_points,
            aspiration_mapping: $aspiration_mapping,
            created_at: $timestamp
        })
        CREATE (u)-[:HAS_SELF_EXPRESSION]->(se)

        // Create LifestyleContext profile
        CREATE (lc:LifestyleContext {
            id: $user_id + '_lifestyle',
            life_stage: $life_stage,
            workplace_context: $workplace_context,
            social_occasions: $social_occasions,
            style_motivation: $style_motivation,
            created_at: $timestamp
        })
        CREATE (u)-[:HAS_LIFESTYLE]->(lc)

        // Create ValuesProfile
        CREATE (vp:ValuesProfile {
            id: $user_id + '_values',
            values_alignment: $values_alignment,
            shopping_behavior: $shopping_behavior,
            brand_loyalty: $brand_loyalty,
            shopping_frequency: $shopping_frequency,
            created_at: $timestamp
        })
        CREATE (u)-[:HAS_VALUES]->(vp)

        // Create BudgetProfile
        CREATE (bp:BudgetProfile {
            id: $user_id + '_budget',
            monthly_budget_min: $monthly_budget_min,
            monthly_budget_max: $monthly_budget_max,
            tops_budget: $tops_budget,
            bottoms_budget: $bottoms_budget,
            outerwear_budget: $outerwear_budget,
            shoes_budget: $shoes_budget,
            splurge_save_preference: $splurge_save_preference,
            value_perception: $value_perception,
            created_at: $timestamp
        })
        CREATE (u)-[:HAS_BUDGET]->(bp)

        RETURN u.id as user_id, u.username as username
        """

        params = {
            "user_id": user_id,
            "username": username,
            "email": demographics.get("email", ""),
            "age_range": demographics.get("age_range", ""),
            "location": demographics.get("location", ""),
            "timestamp": timestamp,
            "onboarding_version": "1.0",

            # Style Autonomy
            "advice_receptiveness": autonomy.get("advice_receptiveness", 5),
            "creative_control": autonomy.get("creative_control", 5),
            "risk_tolerance": autonomy.get("risk_tolerance", 5),
            "decision_making_style": autonomy.get("decision_making_style", "curated_options"),

            # Gender Expression
            "expression_spectrum": expression.get("expression_spectrum", 5),
            "style_adjectives": json.dumps(expression.get("style_adjectives", [])),
            "fit_preferences": json.dumps(expression.get("fit_preferences", [])),
            "inspiration_sources": expression.get("inspiration_sources", ""),
            "occasion_flexibility": expression.get("occasion_flexibility", 5),

            # Self Expression
            "statement_level": self_expr.get("statement_level", 5),
            "change_readiness": self_expr.get("change_readiness", "evolve"),
            "confidence_areas": self_expr.get("confidence_areas", ""),
            "pain_points": self_expr.get("pain_points", ""),
            "aspiration_mapping": self_expr.get("aspiration_mapping", ""),

            # Lifestyle
            "life_stage": json.dumps(lifestyle.get("life_stage", [])),
            "workplace_context": lifestyle.get("workplace_context", "casual"),
            "social_occasions": json.dumps(lifestyle.get("social_occasions", [])),
            "style_motivation": json.dumps(lifestyle.get("style_motivation", [])),

            # Values
            "values_alignment": json.dumps(values.get("values_alignment", [])),
            "shopping_behavior": values.get("shopping_behavior", "mixed"),
            "brand_loyalty": values.get("brand_loyalty", 5),
            "shopping_frequency": values.get("shopping_frequency", "monthly"),

            # Budget
            "monthly_budget_min": budget.get("monthly_budget", {}).get("min", 100),
            "monthly_budget_max": budget.get("monthly_budget", {}).get("max", 500),
            "tops_budget": budget.get("item_investment", {}).get("Tops/Shirts", "$30-75"),
            "bottoms_budget": budget.get("item_investment", {}).get("Bottoms/Pants", "$50-100"),
            "outerwear_budget": budget.get("item_investment", {}).get("Outerwear", "$100-250"),
            "shoes_budget": budget.get("item_investment", {}).get("Shoes", "$50-150"),
            "splurge_save_preference": budget.get("splurge_save_preference", ""),
            "value_perception": budget.get("value_perception", 5),
        }

        result = await self.query(query, params)

        # Add social handles
        await self._add_social_handles(user_id, demographics.get("social_handles", {}))

        # Create Brand/Color/Occasion relationships
        await self._link_preferences(user_id, onboarding_responses)

        # Generate embeddings
        await self.generate_user_embeddings(user_id)

        # Find similar users
        await self.link_similar_users(user_id)

        logger.info(f"Created enhanced user profile: {username} ({user_id})")

        return {
            "user_id": user_id,
            "username": username,
            "status": "created",
            "onboarding_completed": True
        }

    async def _add_social_handles(self, user_id: str, social_handles: Dict[str, str]) -> bool:
        """Add social media handles as nodes."""

        for platform, handle in social_handles.items():
            if handle and handle.strip():
                query = """
                MATCH (u:User {id: $user_id})
                CREATE (sh:SocialHandle {
                    id: $handle_id,
                    platform: $platform,
                    handle: $handle,
                    created_at: $timestamp
                })
                CREATE (u)-[:CONNECTED_TO {platform: $platform}]->(sh)
                """

                await self.query(query, {
                    "user_id": user_id,
                    "handle_id": f"{user_id}_{platform}",
                    "platform": platform,
                    "handle": handle,
                    "timestamp": datetime.utcnow().isoformat()
                })

        return True

    async def _link_preferences(self, user_id: str, responses: Dict[str, Any]) -> bool:
        """Create relationships to Brand, Color, Occasion nodes."""

        # Extract brands from style adjectives or custom inputs
        # For MVP, we'll link explicitly mentioned brands

        # Example: Link to occasions from social_occasions
        occasions = responses.get("lifestyle_context", {}).get("social_occasions", [])
        for occasion in occasions:
            query = """
            MATCH (u:User {id: $user_id})
            MERGE (o:Occasion {name: $occasion})
            ON CREATE SET o.created_at = $timestamp
            MERGE (u)-[:DRESSES_FOR {frequency: 'regular'}]->(o)
            """

            await self.query(query, {
                "user_id": user_id,
                "occasion": occasion,
                "timestamp": datetime.utcnow().isoformat()
            })

        return True

    async def generate_user_embeddings(self, user_id: str) -> bool:
        """
        Generate vector embeddings from user profile.
        Uses OpenAI to create semantic representation.
        """

        # Get full user profile
        profile = await self.get_enhanced_user_profile(user_id)

        # Build rich text representation
        profile_text = self._build_embedding_text(profile)

        # Generate embedding
        try:
            import openai
            import os

            openai.api_key = os.getenv("OPENAI_API_KEY")

            response = await openai.embeddings.create(
                model="text-embedding-3-large",
                input=profile_text
            )

            embedding = response.data[0].embedding

            # Store in Neo4j
            query = """
            MATCH (u:User {id: $user_id})
            SET u.style_embedding = $embedding,
                u.embedding_generated_at = $timestamp,
                u.embedding_text = $profile_text
            """

            await self.query(query, {
                "user_id": user_id,
                "embedding": embedding,
                "profile_text": profile_text,
                "timestamp": datetime.utcnow().isoformat()
            })

            logger.info(f"Generated embeddings for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return False

    def _build_embedding_text(self, profile: Dict[str, Any]) -> str:
        """Build rich text representation for embedding."""

        parts = []

        # Demographics
        if profile.get("age_range"):
            parts.append(f"Age: {profile['age_range']}")
        if profile.get("location"):
            parts.append(f"Location: {profile['location']}")

        # Style identity
        if profile.get("style_adjectives"):
            parts.append(f"Style: {', '.join(profile['style_adjectives'][:5])}")

        # Aspirations
        if profile.get("aspiration_mapping"):
            parts.append(f"Wants to be seen as: {profile['aspiration_mapping']}")

        # Values
        if profile.get("values_alignment"):
            parts.append(f"Values: {', '.join(profile['values_alignment'][:3])}")

        # Occasions
        if profile.get("social_occasions"):
            parts.append(f"Dresses for: {', '.join(profile['social_occasions'][:3])}")

        # Autonomy
        if profile.get("advice_receptiveness"):
            level = "likes new ideas" if profile["advice_receptiveness"] < 5 else "refines existing style"
            parts.append(f"Style approach: {level}")

        return " | ".join(parts)

    async def get_enhanced_user_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Retrieve complete enhanced user profile.

        Returns comprehensive profile including all spectrum scores,
        psychographics, and preferences.
        """

        query = """
        MATCH (u:User {id: $user_id})
        OPTIONAL MATCH (u)-[:HAS_AUTONOMY_PROFILE]->(sa:StyleAutonomy)
        OPTIONAL MATCH (u)-[:HAS_EXPRESSION_PROFILE]->(ge:GenderExpression)
        OPTIONAL MATCH (u)-[:HAS_SELF_EXPRESSION]->(se:SelfExpression)
        OPTIONAL MATCH (u)-[:HAS_LIFESTYLE]->(lc:LifestyleContext)
        OPTIONAL MATCH (u)-[:HAS_VALUES]->(vp:ValuesProfile)
        OPTIONAL MATCH (u)-[:HAS_BUDGET]->(bp:BudgetProfile)
        OPTIONAL MATCH (u)-[:CONNECTED_TO]->(sh:SocialHandle)
        OPTIONAL MATCH (u)-[:DRESSES_FOR]->(o:Occasion)

        RETURN
            u.id as user_id,
            u.username as username,
            u.email as email,
            u.age_range as age_range,
            u.location as location,
            u.created_at as created_at,

            sa {.*} as style_autonomy,
            ge {.*} as gender_expression,
            se {.*} as self_expression,
            lc {.*} as lifestyle_context,
            vp {.*} as values_profile,
            bp {.*} as budget_profile,

            collect(DISTINCT sh {.platform, .handle}) as social_handles,
            collect(DISTINCT o.name) as occasions
        """

        result = await self.query(query, {"user_id": user_id})

        if not result:
            return None

        profile = result[0]

        # Parse JSON fields
        if profile.get("gender_expression"):
            ge = profile["gender_expression"]
            if ge.get("style_adjectives"):
                ge["style_adjectives"] = json.loads(ge["style_adjectives"])
            if ge.get("fit_preferences"):
                ge["fit_preferences"] = json.loads(ge["fit_preferences"])

        if profile.get("lifestyle_context"):
            lc = profile["lifestyle_context"]
            if lc.get("life_stage"):
                lc["life_stage"] = json.loads(lc["life_stage"])
            if lc.get("social_occasions"):
                lc["social_occasions"] = json.loads(lc["social_occasions"])
            if lc.get("style_motivation"):
                lc["style_motivation"] = json.loads(lc["style_motivation"])

        if profile.get("values_profile"):
            vp = profile["values_profile"]
            if vp.get("values_alignment"):
                vp["values_alignment"] = json.loads(vp["values_alignment"])

        return profile

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username."""

        query = """
        MATCH (u:User {username: $username})
        RETURN u.id as user_id, u.username as username, u.email as email
        """

        result = await self.query(query, {"username": username})
        return result[0] if result else None

    async def link_similar_users(self, user_id: str, limit: int = 20) -> bool:
        """
        Create SIMILAR_TO relationships based on embeddings.
        Uses vector similarity to find style matches.
        """

        query = """
        MATCH (u1:User {id: $user_id})
        WHERE u1.style_embedding IS NOT NULL

        CALL db.index.vector.queryNodes(
            'user_style_embedding_idx',
            $limit * 2,
            u1.style_embedding
        ) YIELD node as u2, score

        WHERE u2.id <> $user_id AND score >= 0.7

        WITH u1, u2, score
        MERGE (u1)-[r:SIMILAR_TO]->(u2)
        SET r.score = score,
            r.basis = 'style_embedding',
            r.computed_at = datetime()

        RETURN count(r) as links_created
        """

        try:
            result = await self.query(query, {
                "user_id": user_id,
                "limit": limit
            })

            if result:
                logger.info(f"Created {result[0]['links_created']} similarity links for user {user_id}")

            return True

        except Exception as e:
            logger.error(f"Error linking similar users: {e}")
            return False

    async def get_recommendation_personalization(self, user_id: str) -> Dict[str, Any]:
        """
        Get personalization settings for product recommendations.
        Based on user's autonomy profile and preferences.

        Returns settings like:
        - recommendation_count: How many products to show
        - explanation_depth: How detailed to be
        - bold_suggestions: Whether to suggest experimental items
        - budget_filter: Price range constraints
        """

        profile = await self.get_enhanced_user_profile(user_id)

        if not profile:
            return self._get_default_personalization()

        autonomy = profile.get("style_autonomy", {})
        budget = profile.get("budget_profile", {})
        self_expr = profile.get("self_expression", {})

        # Apply personalization rules (from onboarding_config.json)
        advice_receptiveness = autonomy.get("advice_receptiveness", 5)
        creative_control = autonomy.get("creative_control", 5)
        risk_tolerance = autonomy.get("risk_tolerance", 5)

        # High autonomy: Show more options, detailed explanations
        if advice_receptiveness > 7 and creative_control > 7:
            recommendation_count = 8
            explanation_depth = "detailed"
            show_alternatives = True

        # Low autonomy: Curated selection, concise explanations
        elif advice_receptiveness < 4 and creative_control < 4:
            recommendation_count = 2
            explanation_depth = "concise"
            show_alternatives = False

        # Balanced
        else:
            recommendation_count = 4
            explanation_depth = "balanced"
            show_alternatives = True

        # Experimental users get bold suggestions
        bold_suggestions = (
            risk_tolerance < 4 or
            self_expr.get("change_readiness") == "transform"
        )

        return {
            "recommendation_count": recommendation_count,
            "explanation_depth": explanation_depth,
            "show_alternatives": show_alternatives,
            "bold_suggestions": bold_suggestions,
            "budget_min": budget.get("monthly_budget_min", 0),
            "budget_max": budget.get("monthly_budget_max", 1000),
            "preferred_occasions": profile.get("occasions", []),
            "style_adjectives": profile.get("gender_expression", {}).get("style_adjectives", [])
        }

    def _get_default_personalization(self) -> Dict[str, Any]:
        """Default personalization for new/unknown users."""
        return {
            "recommendation_count": 4,
            "explanation_depth": "balanced",
            "show_alternatives": True,
            "bold_suggestions": False,
            "budget_min": 0,
            "budget_max": 1000,
            "preferred_occasions": [],
            "style_adjectives": []
        }
