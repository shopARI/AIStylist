# Judge Learning Integration Plan

## Goal
Add learning features from `judge_modernized.py` into production `judge.py`

## Step-by-Step Integration

### Step 1: Add Judgment History Storage (5 min)

Add to `agents/judge.py` __init__ (around line 59):

```python
# After self.stats_lock = RLock()
self.judgment_history = []  # Track last 50 judgments for learning
```

### Step 2: Add Learning Methods (15 min)

Copy these 4 methods from `judge_modernized.py` to `agents/judge.py`:

```python
# Copy from judge_modernized.py lines 312-383:

def _get_memory_insights(self, query: str, strategy: str) -> str:
    """Extract insights from memory for enhanced judgment."""
    if len(self.judgment_history) == 0:
        return "(first judgment - no history available)"

    recent = self.judgment_history[-5:]
    successful_strategies = [j['winner'] for j in recent if j.get('successful', True)]

    if successful_strategies:
        common_strategy = Counter(successful_strategies).most_common(1)[0][0]
        return f"(memory suggests {common_strategy} works well for similar queries)"

    return "(memory analysis applied)"

def _apply_learning_strategy(
    self,
    cypher_results: List[Dict[str, Any]],
    vibe_results: List[Dict[str, Any]]
) -> str:
    """Apply learning from judgment history."""
    if len(self.judgment_history) == 0:
        return "balanced"

    recent_success = [j for j in self.judgment_history[-10:] if j.get('successful', True)]

    if recent_success:
        strategy_success = Counter([j['winner'] for j in recent_success])
        best_strategy = strategy_success.most_common(1)[0][0]
        logger.info(f"Learning strategy selected: {best_strategy}")
        return best_strategy

    return "balanced"

def _store_judgment_for_learning(
    self,
    judgment: Dict[str, Any],
    query: str,
    strategy: str
):
    """Store judgment in history for learning."""
    judgment_record = {
        'timestamp': datetime.now().isoformat(),
        'query': query,
        'strategy': strategy,
        'winner': judgment['winner'],
        'confidence': judgment['judgment_confidence'],
        'product_count': len(judgment['products']),
        'successful': judgment['judgment_confidence'] > 0.7
    }

    self.judgment_history.append(judgment_record)

    # Keep only last 50
    if len(self.judgment_history) > 50:
        self.judgment_history = self.judgment_history[-50:]

def _get_recent_patterns(self) -> str:
    """Get patterns from recent judgments."""
    if len(self.judgment_history) < 3:
        return "insufficient data"

    recent = self.judgment_history[-5:]
    winners = [j['winner'] for j in recent]
    winner_counts = Counter(winners)

    if winner_counts:
        most_common = winner_counts.most_common(1)[0][0]
        return f"recently favoring {most_common}"

    return "mixed patterns"
```

### Step 3: Hook Learning into Evaluation (10 min)

In `agents/judge.py` evaluate() method (around line 212):

```python
# After judgment creation, BEFORE updating stats:
# ADD:
self._store_judgment_for_learning(judgment, query, strategy)
```

### Step 4: Add Learning Strategy Option (10 min)

In `agents/judge.py` _execute_judgment() (around line 440):

```python
# In the strategy decision logic, ADD:
elif "learning" in strategy.lower():
    winner = self._apply_learning_strategy(cypher_results, vibe_results)
    reasoning = f"Learning-based selection using historical success patterns"
```

### Step 5: Add Memory Context to Strategy (10 min)

In `agents/judge.py` _get_judgment_strategy() (around line 370):

```python
# After finding consensus_count, ADD:
memory_insights = self._get_memory_insights(query, "")
recent_patterns = self._get_recent_patterns()

context += f"""

HISTORICAL CONTEXT:
- Previous judgments: {len(self.judgment_history)}
- Recent patterns: {recent_patterns}
- Memory insights: {memory_insights}
"""
```

### Step 6: Update Stats (5 min)

In `agents/judge.py` get_stats() (around line 1286):

```python
# ADD to return dict:
"judgment_history_size": len(self.judgment_history),
"learning_rate": (
    self.stats.get('learning_interactions', 0) / total
    if total > 0 else 0
)
```

### Step 7: Add Learning Stat Tracking (5 min)

In `agents/judge.py` __init__ stats dict (around line 49):

```python
self.stats = {
    # ... existing stats ...
    "learning_interactions": 0  # ADD THIS
}
```

### Step 8: Test (30 min)

```bash
# Run tests
python -m pytest tests/test_judge.py -v

# Check learning works
python -c "
from agents.judge import JudgeAriAgent
judge = JudgeAriAgent()
print(f'History: {len(judge.judgment_history)}')
print(f'Stats: {judge.stats}')
"
```

## Total Time: ~1.5 hours

## Result

Production judge.py will have:
- All existing features (VisionBot, quality control, ML)
- PLUS learning from past judgments
- PLUS pattern recognition
- PLUS memory insights

## Rollback Plan

If anything breaks:
```bash
git checkout agents/judge.py
```

## Success Metrics

After 50 judgments, judge should:
1. Have `judgment_history` with 50 records
2. Show learning patterns in logs
3. Use learning strategy when confidence is high
4. Get smarter over time (track win rates)

## Files Modified
- `agents/judge.py` (add ~100 lines)

## Files NOT Modified
- di/container.py (no change needed)
- All other files (no change)
