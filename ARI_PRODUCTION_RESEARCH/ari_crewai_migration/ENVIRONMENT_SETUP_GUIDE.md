# Environment Setup Guide - Fix CrewAI Dependencies

**Issue:** CrewAI imports failing due to missing dependencies and corrupted metadata

---

## Quick Fix (Recommended)

### Step 1: Fix Corrupted Package

```bash
# Remove corrupted prompt-toolkit
pip uninstall prompt-toolkit -y

# Reinstall it cleanly
pip install prompt-toolkit
```

### Step 2: Install Missing CrewAI Dependencies

```bash
# Install required packages
pip install --break-system-packages appdirs pyvis tomli-w uv

# Or if that doesn't work:
python -m pip install --user appdirs pyvis tomli-w uv
```

### Step 3: Verify CrewAI Works

```bash
python -c "from crewai import Agent, Task, LLM; print(' CrewAI working!')"
```

If you see " CrewAI working!" - you're done!

---

## If Quick Fix Doesn't Work

### Option A: Reinstall CrewAI

```bash
# Uninstall CrewAI
pip uninstall crewai -y

# Clear pip cache
pip cache purge

# Reinstall CrewAI
pip install crewai>=0.203.1
```

### Option B: Fresh Virtual Environment (Clean Slate)

```bash
# Go to project directory
cd /home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27

# Create new virtual environment
python -m venv crewai_venv

# Activate it
source crewai_venv/bin/activate

# Install dependencies
pip install crewai>=0.203.1
pip install python-dotenv
pip install chromadb

# Test it
python -c "from crewai import Agent; print(' Clean environment working!')"
```

---

## Test Intent Detection After Fix

### Run Quick Test

```bash
cd /home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/ari_crewai_migration

# Load environment and test
python tests/test_crewai_intent.py
```

### Expected Output

```
================================================================================
CREWAI INTENT DETECTION - QUICK TEST
================================================================================

Environment Check:
  OpenAI API Key:  Configured
  CrewAI:  Installed

================================================================================
Testing Hybrid Detector (LLM_FIRST with CrewAI)
================================================================================

Query: 'black shirt for interview'
Expected: SPECIFIC_ITEM
 Got: SPECIFIC_ITEM
  Confidence: 0.95
  Method: crewai
  Params: {'colors': ['black'], 'categories': ['shirts'], 'occasions': ['interview']}

Query: 'what did I ask earlier'
Expected: CONVERSATION_HISTORY
 Got: CONVERSATION_HISTORY
  Confidence: 0.92
  Method: crewai

Query: 'what day is it'
Expected: GENERAL_CONVERSATION
 Got: GENERAL_CONVERSATION
  Confidence: 0.98
  Method: crewai

================================================================================
Performance Stats:
  Total Queries: 3
  CrewAI Used: 3
  Hardcoded Used: 0
  Fallbacks: 0
  Strategy: llm_first
  CrewAI Available: True
================================================================================
```

---

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'appdirs'"

**Solution:**
```bash
pip install --break-system-packages appdirs
# or
python -m pip install --user appdirs
```

### Issue: "ModuleNotFoundError: No module named 'chromadb'"

**Solution:**
```bash
pip install chromadb
```

### Issue: "OSError: No such file or directory: 'prompt_toolkit...METADATA'"

**Solution:**
```bash
# Remove and reinstall
pip uninstall prompt-toolkit -y
pip cache purge
pip install prompt-toolkit
```

### Issue: Still not working after all fixes

**Solution: Use existing conda environment or system Python**
```bash
# Check if conda is available
which conda

# If yes, create conda environment
conda create -n crewai python=3.10 -y
conda activate crewai
pip install crewai>=0.203.1 python-dotenv chromadb
```

---

## Verify Full Setup

### Test Script

Save this as `test_full_setup.py`:

```python
#!/usr/bin/env python3
"""Test full CrewAI setup"""

print("="*80)
print("TESTING FULL CREWAI SETUP")
print("="*80)

# Test 1: Import CrewAI
print("\n[1/5] Testing CrewAI imports...")
try:
    from crewai import Agent, Task, Crew, LLM
    print(" CrewAI imports successful")
except ImportError as e:
    print(f" CrewAI import failed: {e}")
    exit(1)

# Test 2: Load environment
print("\n[2/5] Testing environment loading...")
try:
    from dotenv import load_dotenv
    import os
    load_dotenv('/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/.env')

    if os.getenv('OPENAI_API_KEY'):
        print(" Environment loaded (OPENAI_API_KEY found)")
    else:
        print("  Environment loaded but OPENAI_API_KEY missing")
except Exception as e:
    print(f" Environment loading failed: {e}")
    exit(1)

# Test 3: Create LLM
print("\n[3/5] Testing CrewAI LLM creation...")
try:
    llm = LLM(model="gpt-4o-mini", temperature=0.3)
    print(" CrewAI LLM created")
except Exception as e:
    print(f" LLM creation failed: {e}")
    exit(1)

# Test 4: Create Agent
print("\n[4/5] Testing CrewAI Agent creation...")
try:
    agent = Agent(
        role="Test Agent",
        goal="Test goal",
        backstory="Test backstory",
        llm=llm,
        verbose=False
    )
    print(" CrewAI Agent created")
except Exception as e:
    print(f" Agent creation failed: {e}")
    exit(1)

# Test 5: Import intent detection
print("\n[5/5] Testing intent detection imports...")
try:
    import sys
    sys.path.insert(0, '.')
    sys.path.insert(0, '/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27')

    from nlp.hybrid_intent_detector import get_hybrid_intent_detector, DetectionStrategy
    print(" Intent detection imports successful")
except ImportError as e:
    print(f" Intent detection import failed: {e}")
    exit(1)

print("\n" + "="*80)
print(" ALL TESTS PASSED - Environment is ready!")
print("="*80)
print("\nYou can now run:")
print("  python tests/test_crewai_intent.py")
```

Run it:
```bash
cd /home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/ari_crewai_migration
python test_full_setup.py
```

---

## What I Need From You

### Option 1: Quick Fix (5 minutes)

Run these commands and send me the output:

```bash
# Fix corrupted package
pip uninstall prompt-toolkit -y
pip install prompt-toolkit

# Install missing deps
pip install --break-system-packages appdirs pyvis tomli-w

# Test
python -c "from crewai import Agent; print(' Working!')"
```

### Option 2: Fresh Environment (10 minutes)

Run these commands and send me the output:

```bash
cd /home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27

# Create venv
python -m venv crewai_venv
source crewai_venv/bin/activate

# Install
pip install crewai>=0.203.1 python-dotenv chromadb

# Test
python -c "from crewai import Agent; print(' Working!')"
```

### Option 3: Just Run Test (2 minutes)

Try running the test directly and send me what happens:

```bash
cd /home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/ari_crewai_migration
python tests/test_crewai_intent.py
```

---

## Once Environment Works

I can then:

1.  Test CrewAI intent detection with real API calls
2.  Measure accuracy on all 13 intent types
3.  Verify common sense reasoning works
4.  Benchmark performance vs pattern-based
5.  Proceed with orchestrator integration
6.  Create conversation handler crews

---

## Summary

**Quickest Path:** Try Option 3 first (just run the test)

If it fails, try Option 1 (quick fix)

If still fails, try Option 2 (fresh venv)

**Let me know which option you'd like to try, or just send me the output from any of them!**
