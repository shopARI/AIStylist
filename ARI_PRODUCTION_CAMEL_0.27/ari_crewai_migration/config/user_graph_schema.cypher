// ==================================================
// ARI USER GRAPH SCHEMA
// Database: productionbackup2_user
// Purpose: User profiles, onboarding data, and behavioral tracking
// ==================================================

// Create database (run this in system database)
// CREATE DATABASE productionbackup2_user IF NOT EXISTS;

// Switch to user database before running rest of script
// :use productionbackup2_user

// ==================================================
// CONSTRAINTS & INDEXES
// ==================================================

// User node constraints
CREATE CONSTRAINT user_id_unique IF NOT EXISTS
FOR (u:User) REQUIRE u.id IS UNIQUE;

CREATE CONSTRAINT user_username_unique IF NOT EXISTS
FOR (u:User) REQUIRE u.username IS UNIQUE;

CREATE CONSTRAINT user_email_unique IF NOT EXISTS
FOR (u:User) REQUIRE u.email IS UNIQUE;

// Indexes for fast lookups
CREATE INDEX user_created_at IF NOT EXISTS
FOR (u:User) ON (u.created_at);

CREATE INDEX user_last_active IF NOT EXISTS
FOR (u:User) ON (u.last_active);

CREATE INDEX user_onboarding_completed IF NOT EXISTS
FOR (u:User) ON (u.onboarding_completed);

// Style & Preference Nodes
CREATE CONSTRAINT style_adjective_name_unique IF NOT EXISTS
FOR (s:StyleAdjective) REQUIRE s.name IS UNIQUE;

CREATE CONSTRAINT fit_preference_name_unique IF NOT EXISTS
FOR (f:FitPreference) REQUIRE f.name IS UNIQUE;

CREATE CONSTRAINT life_stage_name_unique IF NOT EXISTS
FOR (l:LifeStage) REQUIRE l.name IS UNIQUE;

CREATE CONSTRAINT occasion_name_unique IF NOT EXISTS
FOR (o:Occasion) REQUIRE o.name IS UNIQUE;

CREATE CONSTRAINT value_priority_name_unique IF NOT EXISTS
FOR (v:ValuePriority) REQUIRE v.name IS UNIQUE;

CREATE CONSTRAINT style_motivation_name_unique IF NOT EXISTS
FOR (s:StyleMotivation) REQUIRE s.name IS UNIQUE;

// BudgetCategory uses composite constraint
CREATE CONSTRAINT budget_category_composite IF NOT EXISTS
FOR (b:BudgetCategory) REQUIRE (b.user_id, b.category) IS UNIQUE;

// ==================================================
// PRE-POPULATE REFERENCE DATA
// ==================================================

// Style Adjectives (from onboarding_config.json)
MERGE (s:StyleAdjective {name: "Androgynous"});
MERGE (s:StyleAdjective {name: "Edgy"});
MERGE (s:StyleAdjective {name: "Classic"});
MERGE (s:StyleAdjective {name: "Fluid"});
MERGE (s:StyleAdjective {name: "Minimalist"});
MERGE (s:StyleAdjective {name: "Maximalist"});
MERGE (s:StyleAdjective {name: "Romantic"});
MERGE (s:StyleAdjective {name: "Streetwear"});
MERGE (s:StyleAdjective {name: "Professional"});
MERGE (s:StyleAdjective {name: "Bohemian"});
MERGE (s:StyleAdjective {name: "Athletic"});
MERGE (s:StyleAdjective {name: "Avant-garde"});
MERGE (s:StyleAdjective {name: "Vintage"});
MERGE (s:StyleAdjective {name: "Contemporary"});
MERGE (s:StyleAdjective {name: "Understated"});
MERGE (s:StyleAdjective {name: "Bold"});

// Fit Preferences
MERGE (f:FitPreference {name: "Oversized"});
MERGE (f:FitPreference {name: "Relaxed"});
MERGE (f:FitPreference {name: "Tailored"});
MERGE (f:FitPreference {name: "Form-fitting"});
MERGE (f:FitPreference {name: "Flowing"});
MERGE (f:FitPreference {name: "Structured"});
MERGE (f:FitPreference {name: "Layered"});

// Life Stages
MERGE (l:LifeStage {name: "Student"});
MERGE (l:LifeStage {name: "Early Career Professional"});
MERGE (l:LifeStage {name: "Established Professional"});
MERGE (l:LifeStage {name: "Creative/Freelancer"});
MERGE (l:LifeStage {name: "Entrepreneur"});
MERGE (l:LifeStage {name: "Parent"});
MERGE (l:LifeStage {name: "Career Changer"});
MERGE (l:LifeStage {name: "Retired/Semi-retired"});

// Occasions
MERGE (o:Occasion {name: "Work/Professional"});
MERGE (o:Occasion {name: "Casual Daily"});
MERGE (o:Occasion {name: "Date Nights"});
MERGE (o:Occasion {name: "Social Events"});
MERGE (o:Occasion {name: "Formal Events"});
MERGE (o:Occasion {name: "Creative/Networking"});
MERGE (o:Occasion {name: "Athletic/Active"});
MERGE (o:Occasion {name: "Travel"});
MERGE (o:Occasion {name: "Cultural/Religious Events"});

// Value Priorities
MERGE (v:ValuePriority {name: "Sustainability"});
MERGE (v:ValuePriority {name: "Ethical manufacturing"});
MERGE (v:ValuePriority {name: "Local/small designers"});
MERGE (v:ValuePriority {name: "Quality over quantity"});
MERGE (v:ValuePriority {name: "Affordability"});
MERGE (v:ValuePriority {name: "Trendiness"});
MERGE (v:ValuePriority {name: "Versatility"});
MERGE (v:ValuePriority {name: "Brand heritage"});
MERGE (v:ValuePriority {name: "Innovation/tech fabrics"});

// Style Motivations
MERGE (m:StyleMotivation {name: "Professional advancement"});
MERGE (m:StyleMotivation {name: "Self-expression"});
MERGE (m:StyleMotivation {name: "Confidence building"});
MERGE (m:StyleMotivation {name: "Social belonging"});
MERGE (m:StyleMotivation {name: "Creative exploration"});
MERGE (m:StyleMotivation {name: "Comfort"});
MERGE (m:StyleMotivation {name: "Attracting romantic interest"});
MERGE (m:StyleMotivation {name: "Standing out"});
MERGE (m:StyleMotivation {name: "Blending in"});

// ==================================================
// SAMPLE USER NODE (for testing)
// ==================================================

// Create a test user with full profile
MERGE (u:User {
  id: "test_user_001",
  username: "test_user",
  email: "test@example.com",
  created_at: datetime(),
  updated_at: datetime(),
  last_active: datetime(),
  onboarding_completed: true,
  onboarding_completed_at: datetime(),

  // Demographics
  age_range: "25-34",
  location: "New York, USA",

  // Style Autonomy - Stated
  stated_advice_receptiveness: 7.0,
  stated_creative_control: 6.0,
  stated_risk_tolerance: 5.0,
  decision_making_style: "curated_options",

  // Style Autonomy - Observed (initially null)
  observed_advice_receptiveness: null,
  observed_creative_control: null,
  observed_risk_tolerance: null,
  observation_confidence: 0.0,
  preference_drift: null,

  // Expression
  stated_expression_spectrum: 5.0,
  observed_expression_spectrum: null,

  // Self Expression
  statement_level: 6.0,
  change_readiness: "evolve",
  aspiration_text: "Confident, approachable, and put-together",

  // Lifestyle
  workplace_context: "business_casual",
  occasion_flexibility: 7.0,

  // Shopping
  shopping_behavior: "planned_online",
  brand_loyalty: 5.0,
  shopping_frequency: "monthly",

  // Budget
  monthly_budget_min: 200,
  monthly_budget_max: 600,
  value_perception: 7.0,

  // Metrics
  total_searches: 0,
  total_products_viewed: 0,
  total_products_saved: 0,
  total_purchases: 0,

  // Free text
  confidence_areas: "I know what colors work for me",
  pain_points: "Finding the right fit for pants",
  inspiration_sources: "Minimalist fashion bloggers",
  splurge_save_preference: "Splurge on outerwear, save on basics"
});

// Connect test user to style preferences
MATCH (u:User {id: "test_user_001"})
MATCH (s1:StyleAdjective {name: "Minimalist"})
MATCH (s2:StyleAdjective {name: "Professional"})
MATCH (s3:StyleAdjective {name: "Contemporary"})
MERGE (u)-[:IDENTIFIES_WITH {priority: 1}]->(s1)
MERGE (u)-[:IDENTIFIES_WITH {priority: 2}]->(s2)
MERGE (u)-[:IDENTIFIES_WITH {priority: 3}]->(s3);

// Connect to fit preferences
MATCH (u:User {id: "test_user_001"})
MATCH (f1:FitPreference {name: "Tailored"})
MATCH (f2:FitPreference {name: "Relaxed"})
MERGE (u)-[:PREFERS_FIT]->(f1)
MERGE (u)-[:PREFERS_FIT]->(f2);

// Connect to life stages
MATCH (u:User {id: "test_user_001"})
MATCH (l:LifeStage {name: "Early Career Professional"})
MERGE (u)-[:IN_LIFE_STAGE]->(l);

// Connect to occasions
MATCH (u:User {id: "test_user_001"})
MATCH (o1:Occasion {name: "Work/Professional"})
MATCH (o2:Occasion {name: "Casual Daily"})
MATCH (o3:Occasion {name: "Social Events"})
MERGE (u)-[:DRESSES_FOR {frequency: "daily"}]->(o1)
MERGE (u)-[:DRESSES_FOR {frequency: "daily"}]->(o2)
MERGE (u)-[:DRESSES_FOR {frequency: "weekly"}]->(o3);

// Connect to values
MATCH (u:User {id: "test_user_001"})
MATCH (v1:ValuePriority {name: "Quality over quantity"})
MATCH (v2:ValuePriority {name: "Versatility"})
MERGE (u)-[:VALUES {importance: 1}]->(v1)
MERGE (u)-[:VALUES {importance: 2}]->(v2);

// Connect to motivations
MATCH (u:User {id: "test_user_001"})
MATCH (m1:StyleMotivation {name: "Professional advancement"})
MATCH (m2:StyleMotivation {name: "Confidence building"})
MERGE (u)-[:MOTIVATED_BY]->(m1)
MERGE (u)-[:MOTIVATED_BY]->(m2);

// Create budget categories for test user
MERGE (b1:BudgetCategory {
  user_id: "test_user_001",
  category: "Tops/Shirts",
  min_price: 30,
  max_price: 75
});
MATCH (u:User {id: "test_user_001"})
MATCH (b:BudgetCategory {user_id: "test_user_001", category: "Tops/Shirts"})
MERGE (u)-[:HAS_BUDGET]->(b);

MERGE (b2:BudgetCategory {
  user_id: "test_user_001",
  category: "Bottoms/Pants",
  min_price: 50,
  max_price: 100
});
MATCH (u:User {id: "test_user_001"})
MATCH (b:BudgetCategory {user_id: "test_user_001", category: "Bottoms/Pants"})
MERGE (u)-[:HAS_BUDGET]->(b);

MERGE (b3:BudgetCategory {
  user_id: "test_user_001",
  category: "Outerwear",
  min_price: 100,
  max_price: 250
});
MATCH (u:User {id: "test_user_001"})
MATCH (b:BudgetCategory {user_id: "test_user_001", category: "Outerwear"})
MERGE (u)-[:HAS_BUDGET]->(b);

MERGE (b4:BudgetCategory {
  user_id: "test_user_001",
  category: "Shoes",
  min_price: 50,
  max_price: 150
});
MATCH (u:User {id: "test_user_001"})
MATCH (b:BudgetCategory {user_id: "test_user_001", category: "Shoes"})
MERGE (u)-[:HAS_BUDGET]->(b);

// ==================================================
// VERIFICATION QUERIES
// ==================================================

// Verify schema
// CALL db.schema.visualization();

// Count nodes by type
// MATCH (n:User) RETURN "User", count(n);
// MATCH (n:StyleAdjective) RETURN "StyleAdjective", count(n);
// MATCH (n:FitPreference) RETURN "FitPreference", count(n);
// MATCH (n:LifeStage) RETURN "LifeStage", count(n);
// MATCH (n:Occasion) RETURN "Occasion", count(n);
// MATCH (n:ValuePriority) RETURN "ValuePriority", count(n);
// MATCH (n:StyleMotivation) RETURN "StyleMotivation", count(n);
// MATCH (n:BudgetCategory) RETURN "BudgetCategory", count(n);

// View test user profile
// MATCH (u:User {username: "test_user"})-[r]->(n)
// RETURN u, r, n;

// ==================================================
// CROSS-DATABASE REFERENCE NOTES
// ==================================================

// To reference products from productionbackup2 database:
// Product IDs will be stored as strings in relationships
// When querying products, use federated queries or application-level joins
// Example:
//   MATCH (u:User {id: $user_id})-[v:VIEWED]->(ref:ProductRef)
//   // In application: fetch product details from productionbackup2 using ref.product_id
