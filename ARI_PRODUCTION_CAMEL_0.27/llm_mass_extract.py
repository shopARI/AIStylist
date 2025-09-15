#!/usr/bin/env python3
"""
Advanced LLM-Based Mass Data Extraction
Uses GPT-4o with structured outputs for intelligent fashion attribute extraction
"""

import asyncio
import os
import sys
import json
import time
from typing import List, Dict, Optional
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

load_dotenv()

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Structured output models using Pydantic
class ColorExtraction(BaseModel):
    """Extracted color information"""
    primary_colors: List[str] = Field(description="Main colors visible or mentioned", max_items=3)
    color_descriptions: List[str] = Field(description="Color descriptors like 'metallic', 'matte', 'glossy'", max_items=2)
    color_confidence: float = Field(description="Confidence in color extraction (0-1)")

class StyleExtraction(BaseModel):
    """Extracted style information"""
    fashion_styles: List[str] = Field(description="Fashion style categories", max_items=3)
    occasions: List[str] = Field(description="Suitable occasions for wearing", max_items=3)
    target_demographic: str = Field(description="Target demographic (men, women, unisex, kids)")
    formality_level: str = Field(description="Formality level (casual, business, formal, athletic)")

class MaterialExtraction(BaseModel):
    """Extracted material and construction info"""
    materials: List[str] = Field(description="Primary materials mentioned", max_items=3)
    construction_details: List[str] = Field(description="Construction details like 'waterproof', 'breathable'", max_items=2)

class BrandExtraction(BaseModel):
    """Extracted brand information"""
    brand_name: str = Field(description="Identified brand name, empty if not found")
    brand_confidence: float = Field(description="Confidence in brand identification (0-1)")
    brand_tier: str = Field(description="Brand positioning (luxury, premium, mid-range, budget, unknown)")

class ProductExtraction(BaseModel):
    """Complete product attribute extraction"""
    colors: ColorExtraction
    styles: StyleExtraction
    materials: MaterialExtraction
    brand: BrandExtraction
    category: str = Field(description="Main product category")
    season: str = Field(description="Suitable season (spring, summer, fall, winter, all-season)")
    price_perception: str = Field(description="Price perception based on description (budget, mid-range, premium, luxury)")
    key_features: List[str] = Field(description="Key product features mentioned", max_items=4)
    extraction_notes: str = Field(description="Any important notes about extraction quality or limitations")

class LLMExtractor:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = "gpt-4o-2024-08-06"  # Latest GPT-4o with structured outputs
        
    def create_extraction_prompt(self, title: str, description: str) -> str:
        """Create intelligent extraction prompt"""
        return f"""
You are a fashion expert AI analyzing product data for a fashion e-commerce platform. 
Extract detailed attributes from this fashion product information.

PRODUCT TITLE: {title}

PRODUCT DESCRIPTION: {description}

Extract comprehensive fashion attributes including:
- Colors (both explicit and implied from context)
- Style categories and fashion aesthetics
- Materials and construction details
- Brand identification and positioning
- Target demographic and occasions
- Seasonal appropriateness
- Key distinguishing features

Be intelligent about extracting information:
- Look for brand names in titles (even abbreviated or stylized)
- Infer colors from context (e.g., "midnight" = black, "rose" = pink)
- Understand fashion terminology and style implications
- Consider target audience from product positioning
- Extract materials even if not explicitly stated but implied

Provide confidence scores and note any limitations in your extraction.
"""

    async def extract_product_attributes(self, title: str, description: str) -> Optional[ProductExtraction]:
        """Extract attributes using GPT-4o with structured outputs"""
        try:
            prompt = self.create_extraction_prompt(title, description)
            
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a fashion expert AI that extracts detailed product attributes with high accuracy. Always provide structured, complete responses."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                response_format=ProductExtraction,
                temperature=0.3  # Low temperature for consistent extraction
            )
            
            return response.choices[0].message.parsed
            
        except Exception as e:
            print(f"⚠️ LLM extraction error: {e}")
            return None

    async def batch_extract(self, products: List[Dict]) -> List[Dict]:
        """Extract attributes for a batch of products"""
        results = []
        
        for product in products:
            title = product.get('title', '')
            description = product.get('description', '')
            product_id = product.get('id', '')
            
            if not title:
                continue
                
            # Extract using LLM
            extraction = await self.extract_product_attributes(title, description)
            
            if extraction:
                # Convert to Neo4j-friendly format
                result = {
                    'id': product_id,
                    'extracted_colors': extraction.colors.primary_colors,
                    'color_descriptions': extraction.colors.color_descriptions,
                    'color_confidence': extraction.colors.color_confidence,
                    
                    'extracted_styles': extraction.styles.fashion_styles,
                    'occasions': extraction.styles.occasions,
                    'target_demographic': extraction.styles.target_demographic,
                    'formality_level': extraction.styles.formality_level,
                    
                    'materials': extraction.materials.materials,
                    'construction_details': extraction.materials.construction_details,
                    
                    'extracted_brand': extraction.brand.brand_name,
                    'brand_confidence': extraction.brand.brand_confidence,
                    'brand_tier': extraction.brand.brand_tier,
                    
                    'ai_category': extraction.category,
                    'season': extraction.season,
                    'price_perception': extraction.price_perception,
                    'key_features': extraction.key_features,
                    'extraction_notes': extraction.extraction_notes,
                    'extraction_model': self.model,
                    'extraction_timestamp': time.time()
                }
                results.append(result)
                
        return results

async def llm_mass_extract():
    """Perform LLM-based mass data extraction"""
    print(" ADVANCED LLM MASS DATA EXTRACTION")
    print("=" * 60)
    print(f" Using Model: GPT-4o with Structured Outputs")
    print(f" Extraction Capabilities:")
    print("   • Intelligent color extraction with confidence scores")
    print("   • Fashion style classification with occasion mapping")
    print("   • Material and construction detail analysis")
    print("   • Advanced brand identification with tier classification")
    print("   • Target demographic and seasonal analysis")
    print("   • Key feature extraction with context understanding")
    print()
    
    try:
        from services.user.knowledge_graph import UserKnowledgeGraphService
        
        # Initialize connections
        neo4j_service = UserKnowledgeGraphService(
            url=os.getenv("NEO4J_URL"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD")
        )
        await neo4j_service.initialize()
        print(f" Connected to Neo4j: {os.getenv('NEO4J_DATABASE', 'default')}")
        
        extractor = LLMExtractor()
        print(f" Initialized LLM Extractor: {extractor.model}")
        
        # Get total count
        count_query = """
        MATCH (p:Product) 
        WHERE p.title IS NOT NULL 
        AND (p.extracted_colors IS NULL OR p.ai_category IS NULL)
        RETURN count(p) as total
        """
        count_result = await neo4j_service.query(count_query)
        total_products = count_result[0]['total'] if count_result else 0
        print(f"📊 Products to process: {total_products:,}")
        
        # Estimate cost
        estimated_cost = total_products * 0.015  # ~$0.015 per product with GPT-4o
        print(f"💰 Estimated cost: ${estimated_cost:.2f}")
        
        # Process in smaller batches for LLM processing
        batch_size = 50  # Smaller batches for LLM calls
        processed = 0
        updated = 0
        batch_num = 1
        
        # Rate limiting for OpenAI API
        requests_per_minute = 100  # Adjust based on your OpenAI tier
        batch_delay = (60 / requests_per_minute) * batch_size
        
        while processed < total_products:
            print(f"\n🔄 Processing LLM batch {batch_num} (products {processed + 1:,} - {min(processed + batch_size, total_products):,})")
            
            # Get batch of products
            batch_query = f"""
            MATCH (p:Product)
            WHERE p.title IS NOT NULL 
            AND (p.extracted_colors IS NULL OR p.ai_category IS NULL)
            RETURN p.id as id, p.title as title, p.description as description
            LIMIT {batch_size}
            """
            
            batch_result = await neo4j_service.query(batch_query)
            
            if not batch_result:
                print(" No more products to process")
                break
            
            # Process batch with LLM
            extractions = await extractor.batch_extract(batch_result)
            
            # Update database
            for extraction in extractions:
                update_query = """
                MATCH (p:Product {id: $product_id})
                SET p.extracted_colors = $colors,
                    p.color_descriptions = $color_descriptions,
                    p.color_confidence = $color_confidence,
                    p.extracted_styles = $styles,
                    p.occasions = $occasions,
                    p.target_demographic = $target_demographic,
                    p.formality_level = $formality_level,
                    p.materials = $materials,
                    p.construction_details = $construction_details,
                    p.extracted_brand = $brand,
                    p.brand_confidence = $brand_confidence,
                    p.brand_tier = $brand_tier,
                    p.ai_category = $category,
                    p.season = $season,
                    p.price_perception = $price_perception,
                    p.key_features = $key_features,
                    p.extraction_notes = $extraction_notes,
                    p.extraction_model = $extraction_model,
                    p.extraction_timestamp = $extraction_timestamp
                """
                
                await neo4j_service.query(update_query, {
                    'product_id': extraction['id'],
                    'colors': extraction['extracted_colors'],
                    'color_descriptions': extraction['color_descriptions'],
                    'color_confidence': extraction['color_confidence'],
                    'styles': extraction['extracted_styles'],
                    'occasions': extraction['occasions'],
                    'target_demographic': extraction['target_demographic'],
                    'formality_level': extraction['formality_level'],
                    'materials': extraction['materials'],
                    'construction_details': extraction['construction_details'],
                    'brand': extraction['extracted_brand'],
                    'brand_confidence': extraction['brand_confidence'],
                    'brand_tier': extraction['brand_tier'],
                    'category': extraction['ai_category'],
                    'season': extraction['season'],
                    'price_perception': extraction['price_perception'],
                    'key_features': extraction['key_features'],
                    'extraction_notes': extraction['extraction_notes'],
                    'extraction_model': extraction['extraction_model'],
                    'extraction_timestamp': extraction['extraction_timestamp']
                })
                
                updated += 1
            
            processed += len(batch_result)
            batch_num += 1
            
            # Progress update
            if batch_num % 5 == 0:
                percentage = (processed / total_products) * 100
                print(f"📈 Progress: {processed:,}/{total_products:,} ({percentage:.1f}%) - {updated:,} updated")
            
            # Rate limiting delay
            if batch_delay > 0:
                await asyncio.sleep(batch_delay)
        
        print(f"\n LLM MASS EXTRACTION COMPLETE!")
        print(f"📊 Total processed: {processed:,}")
        print(f"🔄 Total updated: {updated:,}")
        print(f" Model used: {extractor.model}")
        
        # Create enhanced relationships
        print(f"\n🔗 Creating enhanced relationships...")
        
        # Enhanced color relationships
        color_rel_query = """
        MATCH (p:Product), (c:Color)
        WHERE c.name IN p.extracted_colors
        MERGE (p)-[:HAS_COLOR {confidence: p.color_confidence}]->(c)
        """
        await neo4j_service.query(color_rel_query)
        
        # Enhanced style relationships
        style_rel_query = """
        MATCH (p:Product), (s:Style)
        WHERE s.name IN p.extracted_styles
        MERGE (p)-[:HAS_STYLE {formality: p.formality_level}]->(s)
        """
        await neo4j_service.query(style_rel_query)
        
        # Brand relationships
        brand_rel_query = """
        MATCH (p:Product)
        WHERE p.extracted_brand IS NOT NULL AND p.extracted_brand <> ''
        MERGE (b:Brand {name: p.extracted_brand, tier: p.brand_tier})
        MERGE (p)-[:HAS_BRAND {confidence: p.brand_confidence}]->(b)
        """
        await neo4j_service.query(brand_rel_query)
        
        # Material relationships
        material_rel_query = """
        MATCH (p:Product)
        WHERE p.materials IS NOT NULL AND size(p.materials) > 0
        UNWIND p.materials as material_name
        MERGE (m:Material {name: material_name})
        MERGE (p)-[:MADE_OF]->(m)
        """
        await neo4j_service.query(material_rel_query)
        
        print(f" Advanced LLM extraction complete! Enhanced fashion knowledge graph ready!")
        
    except Exception as e:
        print(f" LLM mass extraction failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(llm_mass_extract())