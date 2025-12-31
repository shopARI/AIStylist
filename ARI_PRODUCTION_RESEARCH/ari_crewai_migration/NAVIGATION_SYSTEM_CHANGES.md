# Navigation System Changes

Date: 2025-12-30

---

## The Core Idea Remains

North Star: Find the best product for each individual.

How: By representing style as a multi-dimensional space, alongside tangential spaces (demographics, psychometrics, psychology, life context), and using the LLM to traverse all of these simultaneously.

The LLM receives historical data, personalization metrics, and behavioral patterns across all these spaces. It synthesizes them to determine the path. This framing is both conceptual (style as terrain) and mathematical (coordinates, trajectories, distances). ARI - as companion and stylist - helps users navigate.

This does not change.

---

## The Reality of Style

Context shapes everything. A user's formality for a wedding is different from brunch. A single stored value loses that nuance.

Budget is situational. $50 for a casual tee, $500 for a wedding outfit - same person, different context.

Preferences evolve. What someone wanted 6 months ago may not reflect who they are now.

---

## What We're Changing

Instead of storing fixed preferences, we store raw behavioral data and compute preferences at query time based on context.

**Before:** Store "user prefers minimalist style"
**After:** Compute from behavior that user has consistently chosen minimalist pieces, weighted by recency and context

This better serves "evolved preferences unique to their path" - preferences that actually evolve, not sit frozen in a database.

---

## What We're Keeping

The navigation paradigm is intact:

- Position: Where you are in style space (computed from your history)
- Trajectory: Direction and speed of your style evolution (computed from patterns)
- Destination: Where you want to go (understood from your query)
- Path: The route to get there, with comfortable step sizes

The multi-modal intelligence remains: embeddings plus deterministic features (color science, shape, texture).

---

## The Three Pillars

The ML Intelligence layer that feeds the LLM remains intact. Three pillars provide the knowledge:

**Pillar 1: Personalization**
User-specific data from the graph - body data, interaction history, computed position and trajectory. Raw data, not fixed inferences.

**Pillar 2: Stylist Knowledge**
RAG over fashion literature - color theory, body type rules, occasion appropriateness, silhouette science. Domain expertise the LLM can retrieve.

**Pillar 3: User Activity**
Behavioral patterns - what they view, like, purchase, reject. Preference drift detection. Recommendation feedback history.

These three pillars feed into the LLM, which synthesizes them to navigate the user through style space.

---

## How It Works

1. User asks for something
2. **Pillar 1:** Load raw user data (interactions, conversations, body data)
3. **Pillar 3:** Compute position and trajectory from behavioral patterns
4. **Pillar 2:** Retrieve relevant stylist knowledge (body type rules, occasion rules, color guidance)
5. **LLM:** Synthesize all pillars, understand destination, determine path
6. **Agents:** Find products along that path
7. **Judge:** Score and select the best ones

The LLM receives all three pillars and synthesizes them. The agents retrieve products. The scoring is deterministic - fast, consistent, reproducible.

---

## Agent Configuration

Two primary agents do the product finding:
- Semantic search (finds things that match the vibe)
- Visual search (finds things that look right)

A third agent (graph-based search) is available for specific queries like "Nike shoes under $150" but stays off by default to keep things simple initially.

---

## Addition: The Journey Narrative

For some users, the style journey is also a psychological journey - empowerment, self-discovery, reinvention. The products are waypoints, but the story matters.

The system should not just return products. It should explain the path:

"You're currently in a minimalist, neutral space. For this wedding, we're navigating toward something more elegant and structured. These pieces bridge where you are and where you want to be - each one is a comfortable step that still feels like you."

This translation of navigation into narrative is where ARI becomes a stylist, not just an algorithm.


NOTES:




Preferences are context-dependent --> Compute from behavior at query time, filtered by context 

Keep it simple for testing --> Start with two primary agents, add complexity as needed 

The original navigation paradigm - position, trajectory, destination, path - remains the foundation but we are refining how we compute it
