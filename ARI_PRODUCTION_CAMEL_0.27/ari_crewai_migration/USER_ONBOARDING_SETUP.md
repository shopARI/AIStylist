# USER ONBOARDING SYSTEM - SETUP GUIDE

## Overview

This document describes the complete user onboarding system that transforms ARI from a simple product search into a user-aware, personalized fashion recommendation platform.

## Architecture

**Two-Database System:**
- `productionbackup2` - Product graph (6.4M+ products) - READ ONLY
- `productionbackup2_user` - User graph (profiles, preferences, behavior) - NEW

**Cross-Database Integration:**
- User graph stores ProductRef nodes with product IDs
- Application-level joins connect users to products
- Clean separation of concerns (user PII isolated from products)

## Setup Steps

### 1. Environment Configuration

The `.env` file has been updated with user database credentials:

```bash
# Product Graph (existing)
NEO4J_URL=neo4j://34.135.40.119:7687
NEO4J_DATABASE=productionbackup2

# User Graph (new)
NEO4J_USER_URL=neo4j://34.135.40.119:7687
NEO4J_USER_DATABASE=productionbackup2_user
```

### 2. Create User Database

Run the setup script to create the user database and schema:

```bash
python setup_user_database.py
```

This will:
- Create `productionbackup2_user` database
- Set up node constraints and indexes
- Pre-populate reference data (StyleAdjective, FitPreference, etc.)
- Create a test user for verification

### 3. Verify Setup

Check that the database was created successfully:

```bash
# The setup script will show verification output
# You should see node counts for all types
```

### 4. Test the System

Run the enhanced chat interface:

```bash
python cli/chat_interface_v2.py
```

**First-Time User Flow:**
1. Enter username (new user)
2. Enter email
3. Complete 7-step onboarding (3 minutes)
4. Start personalized chat

**Returning User Flow:**
1. Enter username (existing user)
2. View personalized welcome
3. Start chat with profile-aware recommendations

## Components

### Phase 1: User Graph Foundation

**Files:**
- `services/user_graph_manager.py` - Neo4j operations
- `config/user_graph_schema.cypher` - Database schema
- `config/user_graph_schema.json` - Schema documentation

**Neo4j Schema:**
- User node with 40+ properties (stated + observed preferences)
- 7 reference node types (StyleAdjective, FitPreference, etc.)
- 9 relationship types
- Constraints and indexes for performance

### Phase 2: User Service Layer

**Files:**
- `services/user_service.py` - High-level user operations
- `models/user_models.py` - Pydantic models
- `models/onboarding_models.py` - Onboarding data models

**Features:**
- User CRUD operations
- Authentication by username
- Profile management
- Behavioral tracking
- Observed preference calculation

### Phase 3: Onboarding Flow

**Files:**
- `services/onboarding_service.py` - Orchestration
- `utils/onboarding_loader.py` - Config loading
- `cli/onboarding_cli.py` - Terminal UI
- `config/onboarding_config.json` - 7 steps, 32 questions

**Flow:**
1. Style Autonomy (4 questions)
2. Gender Expression & Style (5 questions)
3. Self Expression (5 questions)
4. Lifestyle Context (4 questions)
5. Values & Shopping (4 questions)
6. Budget & Investment (4 questions)
7. Demographics (4 questions)

### Phase 4: Chat Interface Integration

**Files:**
- `cli/chat_interface_v2.py` - Enhanced chat interface

**Features:**
- Username authentication
- New user onboarding
- Personalized result limits (2-8 based on decision style)
- User-specific filters (budget constraints)
- Interaction tracking (views, searches)
- Observed preference updates (every 5 searches)
- Profile and stats commands

## Usage

### Basic Chat Commands

```
You: black dress for wedding
  Shows personalized results (2-8 products based on your style)

You: profile
  Shows your complete style profile

You: stats
  Shows your usage statistics and preference drift

You: quit
  Exit the chat
```

### Personalization Features

**Adaptive Result Count:**
- "tell_me" style: 2 products (you trust recommendations)
- "curated_options": 5 products (balanced)
- "many_options": 8 products (you want choices)

**Budget Filtering:**
- Auto-applies max_price based on monthly budget / 4
- Prevents showing unaffordable items

**Style Context:**
- Agents receive your style adjectives, fit preferences
- Judge evaluates based on your aspirations
- Search considers your risk tolerance

### Behavioral Learning

The system tracks:
- Product views
- Product saves
- Purchases
- Search queries

And calculates:
- Observed expression spectrum (from viewed categories)
- Observed risk tolerance (from purchase patterns)
- Observed advice receptiveness (from exploration behavior)
- Preference drift (stated vs observed)

## Database Schema

### User Node (40+ properties)

```cypher
User {
  id, username, email, created_at, updated_at,

  // Style Autonomy
  stated_advice_receptiveness, stated_creative_control, stated_risk_tolerance,
  observed_advice_receptiveness, observed_creative_control, observed_risk_tolerance,
  observation_confidence, preference_drift,

  // Expression
  stated_expression_spectrum, observed_expression_spectrum,

  // Lifestyle
  workplace_context, occasion_flexibility,

  // Shopping
  shopping_behavior, brand_loyalty, shopping_frequency,
  monthly_budget_min, monthly_budget_max,

  // Metrics
  total_searches, total_products_viewed, total_products_saved, total_purchases
}
```

### Relationships

```cypher
(User)-[:IDENTIFIES_WITH {priority}]->(StyleAdjective)
(User)-[:PREFERS_FIT]->(FitPreference)
(User)-[:IN_LIFE_STAGE]->(LifeStage)
(User)-[:DRESSES_FOR {frequency}]->(Occasion)
(User)-[:VALUES {importance}]->(ValuePriority)
(User)-[:MOTIVATED_BY]->(StyleMotivation)
(User)-[:HAS_BUDGET]->(BudgetCategory)
(User)-[:VIEWED {timestamp, count}]->(ProductRef)
(User)-[:SAVED {timestamp}]->(ProductRef)
(User)-[:PURCHASED {timestamp, price}]->(ProductRef)
```

## Testing

### Test User

The setup script creates a test user:
- Username: `test_user`
- Complete profile with all relationships
- Can be used for testing the system

### Manual Testing

1. Create a new user through onboarding
2. Complete all 7 steps
3. Search for products
4. Check profile and stats
5. Verify observed preferences update after 5+ searches

## Troubleshooting

### Database Connection Issues

If you get connection errors:
```bash
# Check Neo4j is running
# Verify credentials in .env
# Ensure productionbackup2_user database exists
```

### Onboarding Errors

If onboarding fails:
- Check all required questions are answered
- Verify Neo4j connection
- Check console for validation errors

### Missing Preferences

If observed preferences are null:
- User needs more interaction data (views, searches)
- Requires 10+ interactions for meaningful calculations
- Check observation_confidence (increases with data)

## Future Enhancements

### Planned Features

1. **Preference Drift Alerts** - Notify when stated vs observed diverges significantly
2. **Profile Update Prompts** - Suggest profile updates based on behavior
3. **Collaborative Filtering** - Find similar users for recommendations
4. **Social Graph** - Connect users with similar styles
5. **Product History** - Track purchases and saved items
6. **Occasion-Based Recommendations** - Context-aware search

### Extension Points

- Add more question types to onboarding
- Expand observed preference calculations
- Integrate with external style APIs
- Add machine learning for preference prediction

## Support

For issues or questions:
1. Check this documentation
2. Review code comments in services/
3. Check validation errors in console output
4. Verify database schema with `user_graph_schema.json`

## Summary

The user onboarding system provides:
- Complete user profile capture (7 steps, 32 questions)
- Separate user database for data isolation
- Behavioral learning and preference tracking
- Personalized product recommendations
- Adaptive UI based on user style
- Production-ready infrastructure

**Status:** All phases complete and ready for testing
