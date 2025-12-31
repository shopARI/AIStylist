#!/usr/bin/env python3
"""
Final Graph Analysis - Post Enhancement Statistics
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.user.knowledge_graph import UserKnowledgeGraphService

async def comprehensive_graph_analysis():
    print(' COMPREHENSIVE GRAPH ANALYSIS - POST ENHANCEMENT')
    print('=' * 70)
    
    service = UserKnowledgeGraphService(
        url=os.getenv('NEO4J_URL'),
        username=os.getenv('NEO4J_USERNAME'), 
        password=os.getenv('NEO4J_PASSWORD')
    )
    await service.initialize()
    
    try:
        # === NODE ANALYSIS ===
        print('NODE ANALYSIS:')
        print('-' * 30)
        
        # Total nodes by type
        node_queries = [
            ('Products', 'MATCH (p:Product) RETURN count(p) as count'),
            ('Colors', 'MATCH (c:Color) RETURN count(c) as count'),  
            ('Styles', 'MATCH (s:Style) RETURN count(s) as count'),
            ('Brands', 'MATCH (b:Brand) RETURN count(b) as count'),
            ('Materials', 'MATCH (m:Material) RETURN count(m) as count'),
            ('Occasions', 'MATCH (o:Occasion) RETURN count(o) as count'),
            ('PriceTiers', 'MATCH (pt:PriceTier) RETURN count(pt) as count')
        ]
        
        total_nodes = 0
        for node_type, query in node_queries:
            result = await service.query(query)
            count = result[0]['count'] if result else 0
            total_nodes += count
            print(f'   {node_type}: {count:,}')
        
        print(f'   TOTAL NODES: {total_nodes:,}')
        
        # === PRODUCT ENHANCEMENT ANALYSIS ===
        print('\n AI ENHANCEMENT ANALYSIS:')
        print('-' * 35)
        
        # Products with AI extraction
        ai_queries = [
            ('With AI colors', 'MATCH (p:Product) WHERE p.extracted_colors IS NOT NULL RETURN count(p) as count'),
            ('With AI styles', 'MATCH (p:Product) WHERE p.extracted_styles IS NOT NULL RETURN count(p) as count'),
            ('With AI brands', 'MATCH (p:Product) WHERE p.extracted_brand IS NOT NULL RETURN count(p) as count'),
            ('With materials', 'MATCH (p:Product) WHERE p.materials IS NOT NULL RETURN count(p) as count'),
            ('With demographics', 'MATCH (p:Product) WHERE p.target_demographic IS NOT NULL RETURN count(p) as count'),
            ('With occasions', 'MATCH (p:Product) WHERE p.occasions IS NOT NULL RETURN count(p) as count')
        ]
        
        for desc, query in ai_queries:
            result = await service.query(query)
            count = result[0]['count'] if result else 0
            print(f'   {desc}: {count:,}')
        
        # === RELATIONSHIP ANALYSIS ===
        print('\n🔗 RELATIONSHIP ANALYSIS:')
        print('-' * 30)
        
        rel_queries = [
            ('HAS_COLOR', 'MATCH ()-[r:HAS_COLOR]->() RETURN count(r) as count'),
            ('HAS_STYLE', 'MATCH ()-[r:HAS_STYLE]->() RETURN count(r) as count'),
            ('HAS_BRAND', 'MATCH ()-[r:HAS_BRAND]->() RETURN count(r) as count'),
            ('MADE_OF', 'MATCH ()-[r:MADE_OF]->() RETURN count(r) as count'),
            ('COMPLEMENTS', 'MATCH ()-[r:COMPLEMENTS]->() RETURN count(r) as count'),
            ('COMPATIBLE_WITH', 'MATCH ()-[r:COMPATIBLE_WITH]->() RETURN count(r) as count'),
            ('SUITABLE_FOR', 'MATCH ()-[r:SUITABLE_FOR]->() RETURN count(r) as count')
        ]
        
        total_rels = 0
        for rel_type, query in rel_queries:
            result = await service.query(query)
            count = result[0]['count'] if result else 0
            total_rels += count
            print(f'   {rel_type}: {count:,}')
        
        # All relationships
        result = await service.query('MATCH ()-[r]->() RETURN count(r) as total_relationships')
        all_rels = result[0]['total_relationships'] if result else 0
        print(f'   TOTAL RELATIONSHIPS: {all_rels:,}')
        
        # === TOP ATTRIBUTES ANALYSIS ===
        print('\n TOP EXTRACTED ATTRIBUTES:')
        print('-' * 35)
        
        # Top colors
        print('   Top Colors:')
        result = await service.query('''
            MATCH (p:Product)-[:HAS_COLOR]->(c:Color) 
            RETURN c.name as color, count(p) as products 
            ORDER BY products DESC LIMIT 10
        ''')
        for record in (result or []):
            print(f'     {record["color"]}: {record["products"]:,} products')
        
        # Top styles  
        print('   Top Styles:')
        result = await service.query('''
            MATCH (p:Product)-[:HAS_STYLE]->(s:Style) 
            RETURN s.name as style, count(p) as products 
            ORDER BY products DESC LIMIT 10
        ''')
        for record in (result or []):
            print(f'     {record["style"]}: {record["products"]:,} products')
        
        # Top brands
        print('   Top Brands:')
        result = await service.query('''
            MATCH (p:Product)-[:HAS_BRAND]->(b:Brand) 
            RETURN b.name as brand, count(p) as products 
            ORDER BY products DESC LIMIT 5
        ''')
        for record in (result or []):
            print(f'     {record["brand"]}: {record["products"]:,} products')
        
        # === QUALITY METRICS ===
        print('\nDATA QUALITY METRICS:')
        print('-' * 30)
        
        # Products with titles
        result = await service.query('MATCH (p:Product) WHERE p.title IS NOT NULL AND p.title <> "" RETURN count(p) as count')
        with_titles = result[0]['count'] if result else 0
        
        # Products with descriptions  
        result = await service.query('MATCH (p:Product) WHERE p.description IS NOT NULL AND p.description <> "" RETURN count(p) as count')
        with_desc = result[0]['count'] if result else 0
        
        # Products with prices
        result = await service.query('MATCH (p:Product) WHERE p.price IS NOT NULL AND p.price > 0 RETURN count(p) as count')
        with_prices = result[0]['count'] if result else 0
        
        print(f'   Products with titles: {with_titles:,}')
        print(f'   Products with descriptions: {with_desc:,}')  
        print(f'   Products with prices: {with_prices:,}')
        
        # AI enhancement coverage
        result = await service.query('MATCH (p:Product) RETURN count(p) as count')
        total_prod_count = result[0]['count'] if result else 1
        
        result = await service.query('MATCH (p:Product) WHERE p.extracted_colors IS NOT NULL RETURN count(p) as count')
        ai_enhanced = result[0]['count'] if result else 0
        
        coverage = (ai_enhanced / total_prod_count * 100) if total_prod_count > 0 else 0
        print(f'   AI Enhancement Coverage: {coverage:.1f}% ({ai_enhanced:,}/{total_prod_count:,})')
        
        print('\n GRAPH ENHANCEMENT SUMMARY:')
        print('-' * 35)
        print(f'   Before: ~135 relationships, minimal metadata')
        print(f'   After: {all_rels:,} relationships, full AI metadata')
        print(f'   Improvement: {(all_rels/135):.0f}x more relationships!')
        print(f'   Cost: $1,062 for {ai_enhanced:,} products')
        print(f'   Model: GPT-4o with structured outputs')
        
    finally:
        await service.close()

if __name__ == "__main__":
    asyncio.run(comprehensive_graph_analysis())