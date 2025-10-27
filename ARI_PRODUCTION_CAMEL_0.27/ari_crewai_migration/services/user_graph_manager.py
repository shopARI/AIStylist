"""
User Graph Manager

Handles all Neo4j operations for the user graph database (productionbackup2_user).
Provides methods for creating user profiles, managing relationships, tracking behavior,
and calculating observed preferences.
"""

import os
import uuid
from typing import List, Dict, Optional, Any
from datetime import datetime
from neo4j import GraphDatabase, AsyncGraphDatabase
from dotenv import load_dotenv

load_dotenv()


class UserGraphManager:
    """Manages Neo4j user graph operations."""

    def __init__(self):
        """Initialize connection to user graph database."""
        self.uri = os.getenv("NEO4J_USER_URI", os.getenv("NEO4J_URI"))
        self.username = os.getenv("NEO4J_USER_USERNAME", os.getenv("NEO4J_USERNAME"))
        self.password = os.getenv("NEO4J_USER_PASSWORD", os.getenv("NEO4J_PASSWORD"))
        self.database = os.getenv("NEO4J_USER_DATABASE", "productionbackup2_user")

        self.driver = GraphDatabase.driver(
            self.uri,
            auth=(self.username, self.password)
        )

    def close(self):
        """Close the database connection."""
        if self.driver:
            self.driver.close()

    # ======================
    # INPUT VALIDATION
    # ======================

    @staticmethod
    def _validate_string_list(value: Any, param_name: str) -> None:
        """Validate that a parameter is a list of strings."""
        if not isinstance(value, list):
            raise TypeError(f"{param_name} must be a list, got {type(value).__name__}")
        if not all(isinstance(item, str) for item in value):
            raise TypeError(f"All items in {param_name} must be strings")

    @staticmethod
    def _validate_int_list(value: Any, param_name: str) -> None:
        """Validate that a parameter is a list of integers."""
        if not isinstance(value, list):
            raise TypeError(f"{param_name} must be a list, got {type(value).__name__}")
        if not all(isinstance(item, int) for item in value):
            raise TypeError(f"All items in {param_name} must be integers")

    @staticmethod
    def _validate_user_id(user_id: Any) -> None:
        """Validate that user_id is a string."""
        if not isinstance(user_id, str):
            raise TypeError(f"user_id must be a string, got {type(user_id).__name__}")
        if not user_id.strip():
            raise ValueError("user_id cannot be empty")

    # ======================
    # USER CREATION
    # ======================

    def create_user_node(self, user_data: Dict[str, Any]) -> str:
        """
        Create a new User node in the graph.

        Args:
            user_data: Dictionary with user properties

        Returns:
            user_id: The created user's ID
        """
        with self.driver.session(database=self.database) as session:
            result = session.run("""
                CREATE (u:User {
                    id: $id,
                    username: $username,
                    email: $email,
                    created_at: datetime(),
                    updated_at: datetime(),
                    last_active: datetime(),
                    onboarding_completed: false,

                    total_searches: 0,
                    total_products_viewed: 0,
                    total_products_saved: 0,
                    total_purchases: 0
                })
                RETURN u.id as user_id
            """, id=user_data.get('id', str(uuid.uuid4())),
                username=user_data['username'],
                email=user_data['email'])

            return result.single()['user_id']

    def update_user_profile(self, user_id: str, profile_data: Dict[str, Any]) -> bool:
        """
        Update user profile properties.

        Args:
            user_id: User ID
            profile_data: Dictionary of properties to update

        Returns:
            Success boolean
        """
        # Build SET clause dynamically
        set_clauses = []
        params = {'user_id': user_id, 'updated_at': datetime.now()}

        for key, value in profile_data.items():
            if value is not None:
                params[key] = value
                set_clauses.append(f"u.{key} = ${key}")

        if not set_clauses:
            return True

        set_clauses.append("u.updated_at = $updated_at")
        query = f"""
            MATCH (u:User {{id: $user_id}})
            SET {', '.join(set_clauses)}
            RETURN u
        """

        with self.driver.session(database=self.database) as session:
            result = session.run(query, **params)
            return result.single() is not None

    # ======================
    # RELATIONSHIPS
    # ======================

    def add_style_adjectives(self, user_id: str, adjectives: List[str], priorities: Optional[List[int]] = None):
        """Add style adjectives with priorities."""
        self._validate_user_id(user_id)
        self._validate_string_list(adjectives, "adjectives")

        if priorities is None:
            priorities = list(range(1, len(adjectives) + 1))
        else:
            self._validate_int_list(priorities, "priorities")
            if len(priorities) != len(adjectives):
                raise ValueError(f"priorities length ({len(priorities)}) must match adjectives length ({len(adjectives)})")

        with self.driver.session(database=self.database) as session:
            for adj, priority in zip(adjectives, priorities):
                session.run("""
                    MATCH (u:User {id: $user_id})
                    MERGE (s:StyleAdjective {name: $adjective})
                    MERGE (u)-[r:IDENTIFIES_WITH]->(s)
                    SET r.priority = $priority
                """, user_id=user_id, adjective=adj, priority=priority)

    def add_fit_preferences(self, user_id: str, fits: List[str]):
        """Add fit preferences."""
        self._validate_user_id(user_id)
        self._validate_string_list(fits, "fits")

        with self.driver.session(database=self.database) as session:
            for fit in fits:
                session.run("""
                    MATCH (u:User {id: $user_id})
                    MERGE (f:FitPreference {name: $fit})
                    MERGE (u)-[:PREFERS_FIT]->(f)
                """, user_id=user_id, fit=fit)

    def add_life_stages(self, user_id: str, life_stages: List[str]):
        """Add life stages."""
        self._validate_user_id(user_id)
        self._validate_string_list(life_stages, "life_stages")

        with self.driver.session(database=self.database) as session:
            for stage in life_stages:
                session.run("""
                    MATCH (u:User {id: $user_id})
                    MERGE (l:LifeStage {name: $stage})
                    MERGE (u)-[:IN_LIFE_STAGE]->(l)
                """, user_id=user_id, stage=stage)

    def add_occasions(self, user_id: str, occasions: List[str], frequencies: Optional[List[str]] = None):
        """Add occasions with optional frequencies."""
        self._validate_user_id(user_id)
        self._validate_string_list(occasions, "occasions")

        if frequencies is None:
            frequencies = ['weekly'] * len(occasions)
        else:
            self._validate_string_list(frequencies, "frequencies")
            if len(frequencies) != len(occasions):
                raise ValueError(f"frequencies length ({len(frequencies)}) must match occasions length ({len(occasions)})")

        with self.driver.session(database=self.database) as session:
            for occasion, frequency in zip(occasions, frequencies):
                session.run("""
                    MATCH (u:User {id: $user_id})
                    MERGE (o:Occasion {name: $occasion})
                    MERGE (u)-[r:DRESSES_FOR]->(o)
                    SET r.frequency = $frequency
                """, user_id=user_id, occasion=occasion, frequency=frequency)

    def add_values(self, user_id: str, values: List[str], importance: Optional[List[int]] = None):
        """Add value priorities with importance rankings."""
        self._validate_user_id(user_id)
        self._validate_string_list(values, "values")

        if importance is None:
            importance = list(range(1, len(values) + 1))
        else:
            self._validate_int_list(importance, "importance")
            if len(importance) != len(values):
                raise ValueError(f"importance length ({len(importance)}) must match values length ({len(values)})")

        with self.driver.session(database=self.database) as session:
            for value, imp in zip(values, importance):
                session.run("""
                    MATCH (u:User {id: $user_id})
                    MERGE (v:ValuePriority {name: $value})
                    MERGE (u)-[r:VALUES]->(v)
                    SET r.importance = $importance
                """, user_id=user_id, value=value, importance=imp)

    def add_motivations(self, user_id: str, motivations: List[str]):
        """Add style motivations."""
        self._validate_user_id(user_id)
        self._validate_string_list(motivations, "motivations")

        with self.driver.session(database=self.database) as session:
            for motivation in motivations:
                session.run("""
                    MATCH (u:User {id: $user_id})
                    MERGE (m:StyleMotivation {name: $motivation})
                    MERGE (u)-[:MOTIVATED_BY]->(m)
                """, user_id=user_id, motivation=motivation)

    def add_budget_categories(self, user_id: str, budgets: List[Dict[str, Any]]):
        """
        Add budget categories.

        Args:
            budgets: List of dicts with keys: category, min_price, max_price
        """
        self._validate_user_id(user_id)
        if not isinstance(budgets, list):
            raise TypeError(f"budgets must be a list, got {type(budgets).__name__}")

        # Validate each budget dict
        for i, budget in enumerate(budgets):
            if not isinstance(budget, dict):
                raise TypeError(f"budgets[{i}] must be a dict, got {type(budget).__name__}")
            required_keys = ['category', 'min_price', 'max_price']
            for key in required_keys:
                if key not in budget:
                    raise ValueError(f"budgets[{i}] missing required key: {key}")
            if not isinstance(budget['category'], str):
                raise TypeError(f"budgets[{i}]['category'] must be a string")
            if not isinstance(budget['min_price'], (int, float)):
                raise TypeError(f"budgets[{i}]['min_price'] must be a number")
            if not isinstance(budget['max_price'], (int, float)):
                raise TypeError(f"budgets[{i}]['max_price'] must be a number")

        with self.driver.session(database=self.database) as session:
            for budget in budgets:
                session.run("""
                    MATCH (u:User {id: $user_id})
                    MERGE (b:BudgetCategory {
                        user_id: $user_id,
                        category: $category
                    })
                    SET b.min_price = $min_price,
                        b.max_price = $max_price
                    MERGE (u)-[:HAS_BUDGET]->(b)
                """, user_id=user_id,
                    category=budget['category'],
                    min_price=budget['min_price'],
                    max_price=budget['max_price'])

    # ======================
    # BEHAVIORAL TRACKING
    # ======================

    def record_product_view(self, user_id: str, product_id: str, session_id: str, product_title: str = "", product_category: str = ""):
        """Record a product view."""
        with self.driver.session(database=self.database) as session:
            session.run("""
                MATCH (u:User {id: $user_id})
                MERGE (p:ProductRef {product_id: $product_id})
                ON CREATE SET p.product_title = $product_title,
                              p.product_category = $product_category
                MERGE (u)-[r:VIEWED]->(p)
                ON CREATE SET r.timestamp = datetime(),
                              r.session_id = $session_id,
                              r.count = 1
                ON MATCH SET r.count = r.count + 1,
                             r.last_viewed = datetime()

                WITH u
                SET u.total_products_viewed = u.total_products_viewed + 1
            """, user_id=user_id, product_id=product_id, session_id=session_id,
                product_title=product_title, product_category=product_category)

    def record_product_save(self, user_id: str, product_id: str, collection: str = "", product_title: str = "", product_category: str = ""):
        """Record a product save/favorite."""
        with self.driver.session(database=self.database) as session:
            session.run("""
                MATCH (u:User {id: $user_id})
                MERGE (p:ProductRef {product_id: $product_id})
                ON CREATE SET p.product_title = $product_title,
                              p.product_category = $product_category
                MERGE (u)-[r:SAVED]->(p)
                SET r.timestamp = datetime(),
                    r.collection = $collection

                WITH u
                SET u.total_products_saved = u.total_products_saved + 1
            """, user_id=user_id, product_id=product_id, collection=collection,
                product_title=product_title, product_category=product_category)

    def record_purchase(self, user_id: str, product_id: str, price: float, occasion: str = "", product_title: str = "", product_category: str = ""):
        """Record a product purchase."""
        with self.driver.session(database=self.database) as session:
            session.run("""
                MATCH (u:User {id: $user_id})
                MERGE (p:ProductRef {product_id: $product_id})
                ON CREATE SET p.product_title = $product_title,
                              p.product_category = $product_category
                MERGE (u)-[r:PURCHASED]->(p)
                SET r.timestamp = datetime(),
                    r.price = $price,
                    r.occasion = $occasion

                WITH u
                SET u.total_purchases = u.total_purchases + 1
            """, user_id=user_id, product_id=product_id, price=price, occasion=occasion,
                product_title=product_title, product_category=product_category)

    def record_search(self, user_id: str, query: str, category: str = "", result_count: int = 0):
        """Record a search query."""
        with self.driver.session(database=self.database) as session:
            session.run("""
                MATCH (u:User {id: $user_id})
                SET u.total_searches = u.total_searches + 1

                CREATE (s:Search {
                    user_id: $user_id,
                    query: $query,
                    category: $category,
                    result_count: $result_count,
                    timestamp: datetime()
                })
            """, user_id=user_id, query=query, category=category, result_count=result_count)

    # ======================
    # OBSERVED PREFERENCES CALCULATION
    # ======================

    def calculate_observed_expression_spectrum(self, user_id: str) -> Optional[float]:
        """
        Calculate observed expression spectrum based on viewed categories.
        Maps categories to spectrum: blazers=3, dresses=8, etc.
        """
        # Category mapping (Structured <-> Fluid <-> Soft)
        category_spectrum = {
            'blazers': 3.0, 'suits': 2.0, 'button-up shirts': 3.5,
            'trousers': 3.0, 'structured coats': 2.5,
            'casual shirts': 5.0, 'jeans': 5.0, 't-shirts': 6.0,
            'dresses': 8.0, 'skirts': 7.5, 'flowing tops': 8.5,
            'cardigans': 7.0, 'soft sweaters': 8.0
        }

        with self.driver.session(database=self.database) as session:
            result = session.run("""
                MATCH (u:User {id: $user_id})-[v:VIEWED]->(p:ProductRef)
                WHERE p.product_category IS NOT NULL
                RETURN p.product_category as category, sum(v.count) as view_count
                ORDER BY view_count DESC
                LIMIT 20
            """, user_id=user_id)

            records = list(result)

            if not records:
                return None

            # Calculate weighted average
            total_views = 0
            weighted_sum = 0

            for record in records:
                category = record['category'].lower()
                view_count = record['view_count']

                # Find matching spectrum value
                spectrum_value = 5.0  # default middle
                for cat_key, value in category_spectrum.items():
                    if cat_key in category:
                        spectrum_value = value
                        break

                weighted_sum += spectrum_value * view_count
                total_views += view_count

            if total_views > 0:
                observed = weighted_sum / total_views

                # Update user node
                session.run("""
                    MATCH (u:User {id: $user_id})
                    SET u.observed_expression_spectrum = $observed,
                        u.observation_confidence = $confidence,
                        u.updated_at = datetime()
                """, user_id=user_id, observed=observed, confidence=min(total_views / 50.0, 1.0))

                return observed

        return None

    def calculate_observed_risk_tolerance(self, user_id: str) -> Optional[float]:
        """
        Calculate observed risk tolerance based on purchase/view patterns.
        Low score = experimental (unconventional items), High score = safe (popular items)
        """
        with self.driver.session(database=self.database) as session:
            # Count unconventional vs safe category interactions
            result = session.run("""
                MATCH (u:User {id: $user_id})-[:VIEWED|PURCHASED]->(p:ProductRef)
                WHERE p.product_category IS NOT NULL
                WITH p.product_category as category, count(*) as interaction_count
                RETURN category, interaction_count
                ORDER BY interaction_count DESC
            """, user_id=user_id)

            records = list(result)

            if not records:
                return None

            # Simple heuristic: if top categories are diverse, lower score (experimental)
            # If concentrated in few categories, higher score (safe)
            total_interactions = sum(r['interaction_count'] for r in records)
            top_3_interactions = sum(r['interaction_count'] for r in records[:3])

            concentration_ratio = top_3_interactions / total_interactions if total_interactions > 0 else 0

            # Convert to risk tolerance (0-10 scale)
            # High concentration = high risk tolerance (safe choices) = high score
            observed = concentration_ratio * 10

            # Update user node
            session.run("""
                MATCH (u:User {id: $user_id})
                SET u.observed_risk_tolerance = $observed,
                    u.updated_at = datetime()
            """, user_id=user_id, observed=observed)

            return observed

        return None

    def calculate_observed_advice_receptiveness(self, user_id: str) -> Optional[float]:
        """
        Calculate if user explores new categories (low score) vs filters to familiar (high score).
        """
        with self.driver.session(database=self.database) as session:
            result = session.run("""
                MATCH (u:User {id: $user_id})-[v:VIEWED]->(p:ProductRef)
                WITH u, count(DISTINCT p.product_category) as unique_categories, count(v) as total_views
                RETURN unique_categories, total_views
            """, user_id=user_id)

            record = result.single()

            if not record or record['total_views'] == 0:
                return None

            unique_categories = record['unique_categories']
            total_views = record['total_views']

            # Calculate exploration ratio
            exploration_ratio = unique_categories / total_views if total_views > 0 else 0

            # Convert to advice receptiveness (0-10 scale)
            # High exploration = low receptiveness (wants new ideas) = low score
            # Low exploration = high receptiveness (refine existing) = high score
            observed = max(1.0, min(10.0, (1 - exploration_ratio) * 10))

            # Update user node
            session.run("""
                MATCH (u:User {id: $user_id})
                SET u.observed_advice_receptiveness = $observed,
                    u.updated_at = datetime()
            """, user_id=user_id, observed=observed)

            return observed

        return None

    def calculate_preference_drift(self, user_id: str) -> Optional[float]:
        """
        Calculate drift between stated and observed preferences.
        Returns average absolute difference across all preference dimensions.
        """
        with self.driver.session(database=self.database) as session:
            result = session.run("""
                MATCH (u:User {id: $user_id})
                WHERE u.observed_expression_spectrum IS NOT NULL
                  AND u.stated_expression_spectrum IS NOT NULL
                WITH u,
                     abs(u.observed_expression_spectrum - u.stated_expression_spectrum) as expr_diff,
                     CASE WHEN u.observed_risk_tolerance IS NOT NULL AND u.stated_risk_tolerance IS NOT NULL
                          THEN abs(u.observed_risk_tolerance - u.stated_risk_tolerance)
                          ELSE null END as risk_diff,
                     CASE WHEN u.observed_advice_receptiveness IS NOT NULL AND u.stated_advice_receptiveness IS NOT NULL
                          THEN abs(u.observed_advice_receptiveness - u.stated_advice_receptiveness)
                          ELSE null END as advice_diff
                WITH [expr_diff, risk_diff, advice_diff] as diffs
                RETURN reduce(sum = 0.0, d IN [x IN diffs WHERE x IS NOT NULL] | sum + d) /
                       size([x IN diffs WHERE x IS NOT NULL]) as avg_drift
            """, user_id=user_id)

            record = result.single()

            if record and record['avg_drift'] is not None:
                drift = record['avg_drift']

                # Update user node
                session.run("""
                    MATCH (u:User {id: $user_id})
                    SET u.preference_drift = $drift,
                        u.updated_at = datetime()
                """, user_id=user_id, drift=drift)

                return drift

        return None

    # ======================
    # QUERIES
    # ======================

    def get_user_style_profile(self, user_id: str) -> Dict[str, Any]:
        """Get complete user style profile."""
        with self.driver.session(database=self.database) as session:
            # Get user node
            user_result = session.run("""
                MATCH (u:User {id: $user_id})
                RETURN u
            """, user_id=user_id)

            user_record = user_result.single()
            if not user_record:
                return {}

            user_node = dict(user_record['u'])

            # Get style adjectives
            adjectives_result = session.run("""
                MATCH (u:User {id: $user_id})-[r:IDENTIFIES_WITH]->(s:StyleAdjective)
                RETURN s.name as name, r.priority as priority
                ORDER BY r.priority
            """, user_id=user_id)
            adjectives = [dict(r) for r in adjectives_result]

            # Get fit preferences
            fits_result = session.run("""
                MATCH (u:User {id: $user_id})-[:PREFERS_FIT]->(f:FitPreference)
                RETURN f.name as name
            """, user_id=user_id)
            fits = [r['name'] for r in fits_result]

            # Get occasions
            occasions_result = session.run("""
                MATCH (u:User {id: $user_id})-[r:DRESSES_FOR]->(o:Occasion)
                RETURN o.name as name, r.frequency as frequency
            """, user_id=user_id)
            occasions = [dict(r) for r in occasions_result]

            # Get values
            values_result = session.run("""
                MATCH (u:User {id: $user_id})-[r:VALUES]->(v:ValuePriority)
                RETURN v.name as name, r.importance as importance
                ORDER BY r.importance
            """, user_id=user_id)
            values = [dict(r) for r in values_result]

            # Get budgets
            budgets_result = session.run("""
                MATCH (u:User {id: $user_id})-[:HAS_BUDGET]->(b:BudgetCategory)
                RETURN b.category as category, b.min_price as min_price, b.max_price as max_price
            """, user_id=user_id)
            budgets = [dict(r) for r in budgets_result]

            return {
                'user': user_node,
                'style_adjectives': adjectives,
                'fit_preferences': fits,
                'occasions': occasions,
                'values': values,
                'budgets': budgets
            }

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username."""
        with self.driver.session(database=self.database) as session:
            result = session.run("""
                MATCH (u:User {username: $username})
                RETURN u
            """, username=username)

            record = result.single()
            return dict(record['u']) if record else None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        with self.driver.session(database=self.database) as session:
            result = session.run("""
                MATCH (u:User {id: $user_id})
                RETURN u
            """, user_id=user_id)

            record = result.single()
            return dict(record['u']) if record else None

    def user_exists(self, username: str) -> bool:
        """Check if user exists."""
        return self.get_user_by_username(username) is not None

    def mark_onboarding_complete(self, user_id: str) -> bool:
        """Mark user onboarding as complete."""
        with self.driver.session(database=self.database) as session:
            result = session.run("""
                MATCH (u:User {id: $user_id})
                SET u.onboarding_completed = true,
                    u.onboarding_completed_at = datetime(),
                    u.updated_at = datetime()
                RETURN u
            """, user_id=user_id)

            return result.single() is not None

    def update_last_active(self, user_id: str) -> bool:
        """Update user's last active timestamp."""
        with self.driver.session(database=self.database) as session:
            result = session.run("""
                MATCH (u:User {id: $user_id})
                SET u.last_active = datetime()
                RETURN u
            """, user_id=user_id)

            return result.single() is not None
