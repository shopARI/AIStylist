# Phase 1: Data Extraction Pipeline
**100% Read-Only - Safe to Run on Production Database**

## 🎯 What This Does
- Extracts colors, brands, styles from 6.4M products  
- Uses AI + rule-based fallbacks for reliability
- Creates structured JSON data for Phase 2
- **NO database writes** - completely safe

## 🚀 Quick Start

### Run Test (100 products):
```bash
cd /home/leo/AIStylist/graph/phase1
source .env
python -m data_extraction.test_extraction_pipeline
```

### Run Full Production (6.4M products):
```bash
cd /home/leo/AIStylist/graph/phase1
source .env
python -m data_extraction.production_run
```

## 📁 Directory Structure
```
phase1/
├── data_extraction/           # Main extraction pipeline
│   ├── extractor_base.py     # Database connectivity
│   ├── color_extractor.py    # Color detection
│   ├── brand_extractor.py    # Brand identification  
│   ├── style_extractor.py    # Style classification
│   └── test_extraction_pipeline.py
├── camel/                     # AI framework
├── .env                       # Database credentials
├── neo4j_connect.sh          # Database connection
└── reports/                   # Analysis documents
```

## 🔒 Safety Guarantee
- Only reads from database (MATCH queries)
- Never writes or modifies data
- Creates local JSON files only
- Full rollback capability

## 📊 Expected Output
- Structured metadata for each product
- Confidence scores for quality control
- Statistics and performance metrics  
- JSON files ready for Phase 2