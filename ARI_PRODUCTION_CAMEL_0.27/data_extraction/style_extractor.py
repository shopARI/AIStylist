"""
Style Classification using ML + LLM
Phase 1: Read-only style classification from product text and embeddings
"""

import asyncio
import json
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import requests
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MultiLabelBinarizer
import pickle
import os

from lib.camel.v070 import (
    create_agent,
    create_user_message,
    BaseMessage,
    ModelType,
    CAMEL_AVAILABLE
)

from .extractor_base import BaseExtractor, ProductData

# Fashion style taxonomy
STYLE_CATEGORIES = {
    # Core styles
    'casual': ['casual', 'everyday', 'relaxed', 'comfortable', 'laid-back', 'effortless'],
    'formal': ['formal', 'dressy', 'elegant', 'sophisticated', 'polished', 'refined'],
    'business': ['business', 'professional', 'office', 'work', 'corporate', 'executive'],
    'athletic': ['athletic', 'sporty', 'activewear', 'gym', 'workout', 'performance'],
    
    # Fashion forward styles
    'trendy': ['trendy', 'fashionable', 'modern', 'contemporary', 'current', 'stylish'],
    'vintage': ['vintage', 'retro', 'classic', 'timeless', 'traditional', 'heritage'],
    'bohemian': ['bohemian', 'boho', 'free-spirited', 'artistic', 'eclectic', 'hippie'],
    'minimalist': ['minimalist', 'simple', 'clean', 'sleek', 'understated', 'basic'],
    
    # Youth/street styles
    'streetwear': ['streetwear', 'urban', 'edgy', 'hip-hop', 'street', 'underground'],
    'punk': ['punk', 'grunge', 'alternative', 'rebel', 'rock', 'gothic'],
    'preppy': ['preppy', 'ivy league', 'collegiate', 'nautical', 'country club', 'tennis'],
    
    # Aesthetic styles
    'romantic': ['romantic', 'feminine', 'soft', 'dreamy', 'flowy', 'delicate'],
    'glamorous': ['glamorous', 'luxurious', 'opulent', 'extravagant', 'statement', 'dramatic'],
    'edgy': ['edgy', 'bold', 'daring', 'provocative', 'unconventional', 'avant-garde']
}

# Style keywords for different product types
PRODUCT_TYPE_STYLE_MAPPING = {
    'dress': {
        'casual': ['sundress', 'shirt dress', 'maxi dress', 'wrap dress'],
        'formal': ['cocktail dress', 'evening gown', 'little black dress', 'formal dress'],
        'business': ['sheath dress', 'shift dress', 'blazer dress', 'midi dress']
    },
    'top': {
        'casual': ['t-shirt', 'tank top', 'blouse', 'sweater'],
        'formal': ['silk blouse', 'dress shirt', 'button-up', 'camisole'],
        'athletic': ['sports bra', 'workout top', 'performance tee', 'athletic tank']
    },
    'bottom': {
        'casual': ['jeans', 'leggings', 'shorts', 'joggers'],
        'formal': ['dress pants', 'slacks', 'trousers', 'pencil skirt'],
        'athletic': ['yoga pants', 'running shorts', 'athletic leggings', 'track pants']
    }
}

class StyleExtractor(BaseExtractor):
    """Extract style classification using ML + LLM approach"""
    
    def __init__(self, use_llm: bool = True, model_type: ModelType = ModelType.GPT_4O_MINI):
        super().__init__("style_extractor")
        
        self.use_llm = use_llm and CAMEL_AVAILABLE
        self.model_type = model_type
        
        # Initialize style classifier (will train on first use)
        self.text_classifier = None
        self.vectorizer = None
        self.label_binarizer = None
        self.is_trained = False
        
        if self.use_llm:
            self.llm_agent = self._create_style_agent()
            self.logger.info("Initialized Style Extractor with LLM + ML classification")
        else:
            self.logger.info("Initialized Style Extractor with ML classification only")
    
    def _create_style_agent(self):
        """Create CAMEL agent specialized for style classification"""
        
        style_list = list(STYLE_CATEGORIES.keys())
        
        system_message = f"""You are a fashion style classification expert. Your job is to classify products into style categories based on their title and description.

AVAILABLE STYLE CATEGORIES:
{', '.join(style_list)}

CLASSIFICATION RULES:
1. Products can have multiple style classifications (e.g., "casual" + "trendy")
2. Focus on the overall aesthetic and target use case
3. Consider product type, materials, cut, and described features
4. Return 1-3 most relevant styles, prioritized by relevance
5. Return as JSON list format

EXAMPLES:

Input: "Nike Air Force 1 Sneakers"
Output: ["casual", "athletic"]

Input: "Little Black Cocktail Dress with Sequins"
Output: ["formal", "glamorous"]

Input: "Vintage Levi's 501 Jeans"
Output: ["casual", "vintage"]

Input: "Minimalist White Button-Up Shirt"
Output: ["business", "minimalist"]

Input: "Bohemian Flowy Maxi Dress with Floral Print"
Output: ["bohemian", "romantic"]

Input: "Edgy Black Leather Jacket with Studs"
Output: ["edgy", "punk"]

Input: "Classic Navy Blazer"
Output: ["business", "formal"]

IMPORTANT:
- Return valid JSON list: ["style1", "style2"]
- Use only the predefined style categories
- If unsure, default to most likely single style
- Consider target audience and occasion
"""
        
        return create_agent(
            system_message=system_message,
            model_type=self.model_type,
            temperature=0.2,
            max_tokens=300    # Sufficient for style classification JSON
        )
    
    async def extract(self, product: ProductData) -> Dict[str, Any]:
        """Extract style classification from product"""
        
        text_content = f"{product.title} {product.description}".strip()
        
        if not text_content:
            return {
                'styles': [],
                'confidence_scores': {'style_classification': 0.0}
            }
        
        extracted_styles = []
        confidence = 0.0
        
        # Method 1: LLM classification (primary)
        if self.use_llm:
            llm_styles, llm_confidence = await self._classify_style_llm(text_content)
            if llm_styles:
                extracted_styles = llm_styles
                confidence = llm_confidence
        
        # Method 2: Rule-based classification (fallback)
        if not extracted_styles:
            rule_styles = self._classify_style_rules(text_content)
            if rule_styles:
                extracted_styles = rule_styles
                confidence = 0.6
        
        # Method 3: ML classification (if trained and available)
        if not extracted_styles and self.is_trained:
            ml_styles = self._classify_style_ml(text_content)
            if ml_styles:
                extracted_styles = ml_styles
                confidence = 0.7
        
        # Fallback to basic classification
        if not extracted_styles:
            extracted_styles = self._basic_style_classification(text_content)
            confidence = 0.3
        
        return {
            'styles': extracted_styles,
            'confidence_scores': {'style_classification': confidence}
        }
    
    async def _classify_style_llm(self, text: str) -> Tuple[List[str], float]:
        """Classify style using LLM"""
        
        try:
            user_message = create_user_message(f"Classify style for: {text}")
            
            # Use compatibility bridge for async method
            from lib.camel.v070 import CompatibilityBridge
            async_method = CompatibilityBridge.check_async_method(self.llm_agent)
            
            if async_method == 'step_async':
                response = await self.llm_agent.step_async(user_message)
            elif async_method == 'astep':
                response = await self.llm_agent.astep(user_message)
            else:
                response = self.llm_agent.step(user_message)
            
            # Parse response content
            if hasattr(response, 'content'):
                response_content = response.content
            elif hasattr(response, 'msg'):
                response_content = response.msg.content if hasattr(response.msg, 'content') else str(response.msg)
            elif hasattr(response, 'message'):
                response_content = response.message.content if hasattr(response.message, 'content') else str(response.message)
            else:
                response_content = str(response)
            
            # Parse JSON response
            styles = self._parse_llm_style_response(response_content)
            confidence = 0.85 if styles else 0.1
            
            return styles, confidence
            
        except Exception as e:
            self.logger.error(f"LLM style classification failed: {e}")
            return [], 0.0
    
    def _parse_llm_style_response(self, response_content: str) -> List[str]:
        """Parse LLM JSON response to extract styles"""
        
        try:
            # Clean response content
            response_content = response_content.strip()
            
            # Handle potential markdown code blocks
            if "```json" in response_content:
                start = response_content.find("```json") + 7
                end = response_content.find("```", start)
                json_str = response_content[start:end].strip()
            elif "```" in response_content:
                start = response_content.find("```") + 3
                end = response_content.rfind("```")
                json_str = response_content[start:end].strip()
            else:
                json_str = response_content
            
            # Find JSON array in response
            if '[' in json_str and ']' in json_str:
                start = json_str.find('[')
                end = json_str.rfind(']') + 1
                json_str = json_str[start:end]
            
            # Parse JSON
            styles = json.loads(json_str)
            
            # Validate and clean
            if isinstance(styles, list):
                valid_styles = []
                for style in styles:
                    style_str = str(style).lower().strip()
                    if style_str in STYLE_CATEGORIES:
                        valid_styles.append(style_str)
                return valid_styles[:3]  # Limit to 3 styles
            else:
                return []
                
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            self.logger.warning(f"Failed to parse LLM style response: {e}")
            return []
    
    def _classify_style_rules(self, text: str) -> List[str]:
        """Classify style using keyword-based rules"""
        
        text_lower = text.lower()
        detected_styles = []
        style_scores = {}
        
        # Score each style category based on keyword matches
        for style_category, keywords in STYLE_CATEGORIES.items():
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 1
            
            if score > 0:
                style_scores[style_category] = score
        
        # Also check product-type specific mappings
        for product_type, style_mappings in PRODUCT_TYPE_STYLE_MAPPING.items():
            if product_type in text_lower:
                for style, type_keywords in style_mappings.items():
                    for keyword in type_keywords:
                        if keyword in text_lower:
                            style_scores[style] = style_scores.get(style, 0) + 2
        
        # Return top scoring styles
        if style_scores:
            sorted_styles = sorted(style_scores.items(), key=lambda x: x[1], reverse=True)
            detected_styles = [style for style, score in sorted_styles[:3]]
        
        return detected_styles
    
    def _classify_style_ml(self, text: str) -> List[str]:
        """Classify style using trained ML model"""
        
        if not self.is_trained or not self.text_classifier:
            return []
        
        try:
            # Vectorize text
            text_features = self.vectorizer.transform([text])
            
            # Predict styles
            predictions = self.text_classifier.predict(text_features)
            predicted_styles = self.label_binarizer.inverse_transform(predictions)
            
            if predicted_styles and predicted_styles[0]:
                return list(predicted_styles[0])
            else:
                return []
                
        except Exception as e:
            self.logger.error(f"ML style classification failed: {e}")
            return []
    
    def _basic_style_classification(self, text: str) -> List[str]:
        """Basic fallback style classification"""
        
        text_lower = text.lower()
        
        # Simple keyword-based classification
        if any(word in text_lower for word in ['dress', 'formal', 'elegant', 'cocktail']):
            return ['formal']
        elif any(word in text_lower for word in ['jean', 'casual', 't-shirt', 'sneaker']):
            return ['casual']
        elif any(word in text_lower for word in ['sport', 'athletic', 'gym', 'workout']):
            return ['athletic']
        elif any(word in text_lower for word in ['business', 'office', 'professional', 'blazer']):
            return ['business']
        else:
            return ['casual']  # Default fallback
    
    def train_ml_classifier(self, training_data: List[Tuple[str, List[str]]]):
        """Train ML classifier on labeled data"""
        
        if not training_data:
            self.logger.warning("No training data provided for style classifier")
            return
        
        try:
            # Prepare training data
            texts = [text for text, styles in training_data]
            style_lists = [styles for text, styles in training_data]
            
            # Initialize components
            self.vectorizer = TfidfVectorizer(max_features=5000, stop_words='english')
            self.label_binarizer = MultiLabelBinarizer()
            
            # Fit vectorizer and label binarizer
            text_features = self.vectorizer.fit_transform(texts)
            style_labels = self.label_binarizer.fit_transform(style_lists)
            
            # Train classifier
            self.text_classifier = LogisticRegression(random_state=42, max_iter=1000)
            self.text_classifier.fit(text_features, style_labels)
            
            self.is_trained = True
            self.logger.info(f"Trained style classifier on {len(training_data)} samples")
            
        except Exception as e:
            self.logger.error(f"Failed to train style classifier: {e}")
            self.is_trained = False
    
    def save_model(self, filepath: str):
        """Save trained model to disk"""
        
        if not self.is_trained:
            self.logger.warning("No trained model to save")
            return
        
        model_data = {
            'classifier': self.text_classifier,
            'vectorizer': self.vectorizer,
            'label_binarizer': self.label_binarizer
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        
        self.logger.info(f"Saved style classification model to {filepath}")
    
    def load_model(self, filepath: str):
        """Load trained model from disk"""
        
        if not os.path.exists(filepath):
            self.logger.warning(f"Model file not found: {filepath}")
            return
        
        try:
            with open(filepath, 'rb') as f:
                model_data = pickle.load(f)
            
            self.text_classifier = model_data['classifier']
            self.vectorizer = model_data['vectorizer'] 
            self.label_binarizer = model_data['label_binarizer']
            self.is_trained = True
            
            self.logger.info(f"Loaded style classification model from {filepath}")
            
        except Exception as e:
            self.logger.error(f"Failed to load model: {e}")
            self.is_trained = False

# Test function
def test_style_classification():
    """Test style classification on sample data"""
    
    test_products = [
        ProductData("1", "Nike Air Force 1 Sneakers", "Classic white athletic sneakers for everyday wear", 90.00),
        ProductData("2", "Little Black Cocktail Dress", "Elegant black dress with sequins for formal occasions", 150.00),
        ProductData("3", "Vintage Levi's 501 Jeans", "Classic vintage denim jeans in authentic wash", 85.00),
        ProductData("4", "Minimalist White Button-Up", "Clean lines white shirt for professional settings", 65.00),
        ProductData("5", "Bohemian Flowy Maxi Dress", "Free-spirited maxi dress with floral print", 120.00),
        ProductData("6", "Edgy Leather Jacket", "Black leather jacket with silver studs and zippers", 200.00)
    ]
    
    return test_products

if __name__ == "__main__":
    # Test the style extractor
    async def test():
        extractor = StyleExtractor()
        test_data = test_style_classification()
        
        for product in test_data:
            result = await extractor.extract(product)
            print(f"Product: {product.title}")
            print(f"Styles: {result['styles']}")
            print(f"Confidence: {result['confidence_scores']['style_classification']:.2f}")
            print("---")
    
    asyncio.run(test())