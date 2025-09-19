"""
PyTorch Visual Intelligence for VibeBot

Provides visual similarity intelligence using PyTorch models.
NEVER returns products - only visual features and aesthetics for VibeBot.

Based on hybrid_visual_recommender.py patterns.
Uses PyTorch instead of TensorFlow for better performance.
SECURITY: URL validation, safe image downloading, and resource limits
PERFORMANCE: GPU memory management and batch processing
"""

import logging
import os
import json
import asyncio
import requests
import gc
import psutil
from io import BytesIO
from typing import List, Dict, Any, Optional, Set, Tuple
from urllib.parse import urlparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib

logger = logging.getLogger("intelligence.visual_pytorch")

# SECURITY: Allowed image domains (expandable via configuration)
DEFAULT_ALLOWED_DOMAINS = {
    # CDN providers
    'cdn.shopify.com',
    'cdn.example.com',
    'images.example.com',
    
    # Cloud storage
    's3.amazonaws.com',
    's3.us-east-1.amazonaws.com',
    's3.us-west-2.amazonaws.com',
    's3-eu-west-1.amazonaws.com',
    'storage.googleapis.com',
    'blob.core.windows.net',
    
    # Image services
    'images.unsplash.com',
    'images.pexels.com',
    'cloudinary.com',
    'imgix.net',
    'fastly.net',
    
    # E-commerce platforms
    'images.asos-media.com',
    'images.net-a-porter.com',
    'images.shopbop.com',
    'static.zara.net',
    'lp2.hm.com',
    
    # Add your specific domains here
    'your-cdn.example.com'
}

# SECURITY: Request limits
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_IMAGE_DIMENSION = 4096  # Maximum width or height
MIN_IMAGE_DIMENSION = 32  # Minimum width or height
REQUEST_TIMEOUT = 10  # seconds
MAX_REDIRECTS = 2  # Maximum redirects to follow

# SECURITY: Allowed content types
ALLOWED_CONTENT_TYPES = {
    'image/jpeg',
    'image/jpg', 
    'image/png',
    'image/webp',
    'image/gif'  # Added GIF support
}

# PERFORMANCE: GPU memory thresholds
GPU_MEMORY_THRESHOLD = 0.8  # Clear cache if GPU memory > 80%
BATCH_SIZE = 4  # Process images in batches

# Try to import PyTorch dependencies
try:
    import torch
    import torchvision.models as models
    import torchvision.transforms as transforms
    from torchvision.models import ResNet50_Weights, ResNet101_Weights, EfficientNet_B0_Weights, ViT_B_16_Weights
    from PIL import Image
    import numpy as np
    PYTORCH_AVAILABLE = True
    logger.info(f"PyTorch {torch.__version__} available for visual intelligence")
    
    # Check CUDA availability
    if torch.cuda.is_available():
        logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
        logger.info(f"CUDA memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f}GB")
    else:
        logger.info("CUDA not available, using CPU")
        
except ImportError:
    PYTORCH_AVAILABLE = False
    logger.warning("PyTorch not installed. Visual intelligence will be limited.")
    logger.info("Install with: pip install torch torchvision pillow")


@dataclass
class ImageProcessingResult:
    """Result of image processing."""
    embedding: Optional[List[float]]
    metadata: Dict[str, Any]
    error: Optional[str] = None
    processing_time: float = 0.0


class GPUMemoryManager:
    """Manages GPU memory for optimal performance."""
    
    def __init__(self, threshold: float = GPU_MEMORY_THRESHOLD):
        """
        Initialize GPU memory manager.
        
        Args:
            threshold: Memory usage threshold for cleanup
        """
        self.threshold = threshold
        self.cleanup_count = 0
        
    @contextmanager
    def managed_execution(self):
        """Context manager for GPU operations with automatic cleanup."""
        try:
            # Check memory before
            self.check_and_cleanup()
            yield
        finally:
            # Always clear cache after execution
            if torch.cuda.is_available():
                torch.cuda.synchronize()
                torch.cuda.empty_cache()
    
    def check_and_cleanup(self):
        """Check GPU memory and cleanup if needed."""
        if not torch.cuda.is_available():
            return
        
        # Get current memory usage
        allocated = torch.cuda.memory_allocated()
        reserved = torch.cuda.memory_reserved()
        total = torch.cuda.get_device_properties(0).total_memory
        
        usage_ratio = allocated / total
        
        if usage_ratio > self.threshold:
            logger.warning(f"GPU memory usage high: {usage_ratio:.1%}")
            self.force_cleanup()
    
    def force_cleanup(self):
        """Force GPU memory cleanup."""
        if torch.cuda.is_available():
            # Clear cache
            torch.cuda.empty_cache()
            
            # Force garbage collection
            gc.collect()
            
            # Synchronize
            torch.cuda.synchronize()
            
            self.cleanup_count += 1
            logger.info(f"GPU memory cleaned (cleanup #{self.cleanup_count})")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get current GPU memory statistics."""
        if not torch.cuda.is_available():
            return {"cuda_available": False}
        
        return {
            "cuda_available": True,
            "allocated": f"{torch.cuda.memory_allocated() / 1e9:.2f}GB",
            "reserved": f"{torch.cuda.memory_reserved() / 1e9:.2f}GB",
            "total": f"{torch.cuda.get_device_properties(0).total_memory / 1e9:.2f}GB",
            "cleanup_count": self.cleanup_count
        }


class VisualIntelligence:
    """
    Provides visual intelligence for VibeBot using PyTorch.
    
    Uses ResNet models for feature extraction.
    CRITICAL: Returns visual features, NEVER products!
    SECURITY: Validates all image URLs before downloading.
    PERFORMANCE: GPU memory management and batching.
    
    Based on hybrid_visual_recommender.py (lines 142-175 for model init).
    """
    
    def __init__(
        self,
        product_kg: Any,
        model_name: str = 'resnet50',
        device: str = 'auto',
        storage_path: str = "intelligence/visual_embeddings",
        allowed_domains: Optional[Set[str]] = None,
        max_image_size: int = MAX_IMAGE_SIZE,
        enable_caching: bool = True,
        cache_size: int = 1000,
        batch_size: int = BATCH_SIZE
    ):
        """
        Initialize PyTorch-based visual intelligence with enhanced features.
        
        Args:
            product_kg: Product knowledge graph
            model_name: Model to use ('resnet50', 'resnet101', 'efficientnet_b0', 'vit_b_16')
            device: Device to use ('auto', 'cpu', 'cuda')
            storage_path: Path to store visual embeddings
            allowed_domains: Additional allowed domains for images
            max_image_size: Maximum allowed image size in bytes
            enable_caching: Enable embedding cache
            cache_size: Maximum cache size
            batch_size: Batch size for processing
        """
        logger.info(f"Initializing Visual Intelligence with {model_name}")
        
        self.product_kg = product_kg
        self.model_name = model_name
        self.storage_path = storage_path
        self.max_image_size = max_image_size
        self.enable_caching = enable_caching
        self.batch_size = batch_size
        
        # SECURITY: Set up allowed domains
        self.allowed_domains = DEFAULT_ALLOWED_DOMAINS.copy()
        if allowed_domains:
            self.allowed_domains.update(allowed_domains)
        
        logger.info(f"URL validation enabled with {len(self.allowed_domains)} allowed domains")
        
        # Initialize PyTorch model if available
        self.image_model = None
        self.preprocess = None
        self.device = None
        self.embedding_dim = 2048  # Default for ResNet
        
        # GPU memory manager
        self.gpu_manager = GPUMemoryManager()
        
        if PYTORCH_AVAILABLE:
            try:
                self._initialize_pytorch_model(device)
                logger.info(f"PyTorch model ({model_name}) initialized successfully")
                
                # Initial GPU cleanup
                self.gpu_manager.force_cleanup()
                    
            except Exception as e:
                logger.error(f"Error initializing PyTorch model: {e}")
                self.image_model = None
        else:
            logger.warning("PyTorch not available for visual intelligence")
        
        # Cache for embeddings (LRU-style)
        if enable_caching:
            from collections import OrderedDict
            self.embedding_cache = OrderedDict()
            self.cache_hits = 0
            self.cache_misses = 0
        else:
            self.embedding_cache = None
        
        self.max_cache_size = cache_size
        
        # Statistics
        self.stats = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_processing_time": 0.0,
            "gpu_cleanups": 0
        }
        
        logger.info("Visual Intelligence initialized with enhanced security and performance features")
    
    def _validate_image_url(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        Validate image URL for security with detailed error reporting.
        
        Args:
            url: URL to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check URL length
            if len(url) > 2048:
                return False, "URL too long"
            
            parsed = urlparse(url)
            
            # Check scheme
            if parsed.scheme not in ['http', 'https']:
                return False, f"Invalid URL scheme: {parsed.scheme}"
            
            # Check for empty host
            if not parsed.netloc:
                return False, "No host in URL"
            
            # Extract domain
            domain = parsed.netloc.lower()
            
            # Remove port if present
            if ':' in domain:
                domain = domain.split(':')[0]
            
            # Check against allowed domains
            domain_allowed = False
            for allowed in self.allowed_domains:
                if domain == allowed or domain.endswith(f'.{allowed}'):
                    domain_allowed = True
                    break
            
            if not domain_allowed:
                return False, f"Domain not allowed: {domain}"
            
            # Check for suspicious patterns
            suspicious_patterns = [
                '../',  # Directory traversal
                '..\\',  # Windows directory traversal
                'file://',  # Local file access
                'javascript:',  # JavaScript injection
                'data:',  # Data URLs (except specific cases)
                '%00',  # Null byte
                '\x00',  # Null character
                '<script',  # Script injection
                'onerror=',  # Event handler injection
            ]
            
            url_lower = url.lower()
            for pattern in suspicious_patterns:
                if pattern in url_lower:
                    return False, f"Suspicious pattern detected: {pattern}"
            
            # Check for unusual characters
            if any(ord(c) > 127 for c in parsed.path):
                return False, "Non-ASCII characters in path"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error validating URL: {e}")
            return False, str(e)
    
    def _initialize_pytorch_model(self, device_preference: str = 'auto'):
        """
        Initialize the PyTorch model and preprocessing pipeline.
        
        Based on hybrid_visual_recommender.py _initialize_pytorch_model (lines 142-175).
        """
        # Determine device (GPU if available, else CPU)
        if device_preference == 'auto':
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        elif device_preference == 'cuda' and torch.cuda.is_available():
            self.device = torch.device('cuda')
        else:
            self.device = torch.device('cpu')
        
        logger.info(f"Using device: {self.device}")
        
        # Initialize model based on specified architecture
        with self.gpu_manager.managed_execution():
            if self.model_name == 'resnet50':
                # ResNet50 - good balance of speed and accuracy (default)
                self.image_model = models.resnet50(weights=ResNet50_Weights.DEFAULT)
                self.image_model = torch.nn.Sequential(*list(self.image_model.children())[:-1])
                self.embedding_dim = 2048
                
            elif self.model_name == 'resnet101':
                # ResNet101 - higher accuracy, slower
                self.image_model = models.resnet101(weights=ResNet101_Weights.DEFAULT)
                self.image_model = torch.nn.Sequential(*list(self.image_model.children())[:-1])
                self.embedding_dim = 2048
                
            elif self.model_name == 'efficientnet_b0':
                # EfficientNet - best efficiency
                try:
                    self.image_model = models.efficientnet_b0(weights=EfficientNet_B0_Weights.DEFAULT)
                    self.image_model.classifier = torch.nn.Identity()
                    self.embedding_dim = 1280
                except AttributeError:
                    # Fallback to ResNet50 if EfficientNet not available
                    logger.warning("EfficientNet not available, falling back to ResNet50")
                    self.image_model = models.resnet50(weights=ResNet50_Weights.DEFAULT)
                    self.image_model = torch.nn.Sequential(*list(self.image_model.children())[:-1])
                    self.embedding_dim = 2048
                    
            elif self.model_name == 'vit_b_16':
                # Vision Transformer - state of the art
                try:
                    self.image_model = models.vit_b_16(weights=ViT_B_16_Weights.DEFAULT)
                    self.image_model.heads = torch.nn.Identity()
                    self.embedding_dim = 768
                except AttributeError:
                    logger.warning("ViT not available, falling back to ResNet50")
                    self.image_model = models.resnet50(weights=ResNet50_Weights.DEFAULT)
                    self.image_model = torch.nn.Sequential(*list(self.image_model.children())[:-1])
                    self.embedding_dim = 2048
            else:
                # Default to ResNet50
                logger.warning(f"Unknown model {self.model_name}, using ResNet50")
                self.image_model = models.resnet50(weights=ResNet50_Weights.DEFAULT)
                self.image_model = torch.nn.Sequential(*list(self.image_model.children())[:-1])
                self.embedding_dim = 2048
            
            # Move model to device and set to evaluation mode
            self.image_model = self.image_model.to(self.device)
            self.image_model.eval()
            
            # Disable gradient computation for inference
            for param in self.image_model.parameters():
                param.requires_grad = False
        
        # Define preprocessing pipeline (EXACT from hybrid_visual_recommender.py lines 168-175)
        self.preprocess = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],  # ImageNet means
                std=[0.229, 0.224, 0.225]    # ImageNet stds
            )
        ])
        
        logger.info(f"Initialized {self.model_name} on {self.device} (embedding_dim={self.embedding_dim})")
    
    async def get_visual_features(
        self,
        product_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get visual features for a product.
        
        Args:
            product_id: Product ID
            
        Returns:
            Visual feature intelligence (NOT products!)
        """
        # Check cache first if enabled
        cache_key = f"features_{product_id}"
        if self.enable_caching and cache_key in self.embedding_cache:
            self.stats["cache_hits"] += 1
            self.cache_hits += 1
            logger.debug(f"Cache hit for product {product_id}")
            
            # Move to end (LRU)
            self.embedding_cache.move_to_end(cache_key)
            return self.embedding_cache[cache_key]
        
        self.stats["cache_misses"] += 1
        self.cache_misses += 1
        
        # Get product details
        product = await self._get_product_details(product_id)
        if not product:
            return None
        
        # Get image URLs
        image_urls = product.get('images', [])
        if not image_urls:
            logger.warning(f"No images for product {product_id}")
            return None
        
        # Ensure it's a list
        if isinstance(image_urls, str):
            image_urls = [image_urls]
        
        # Validate and find first valid URL
        valid_url = None
        validation_error = None
        
        for url in image_urls[:5]:  # Check up to 5 URLs
            is_valid, error = self._validate_image_url(url)
            if is_valid:
                valid_url = url
                break
            else:
                validation_error = error
        
        if not valid_url:
            logger.warning(f"No valid image URLs for product {product_id}: {validation_error}")
            return None
        
        # Process image
        result = await self._process_image(valid_url)
        
        if result.error:
            logger.error(f"Failed to process image for {product_id}: {result.error}")
            return None
        
        # Build features dictionary
        features = {
            "embedding_size": len(result.embedding) if result.embedding else 0,
            "dominant_colors": await self._extract_dominant_colors(valid_url),
            "style_attributes": self._infer_style_attributes(product),
            "aesthetic_score": self._calculate_aesthetic_score(result.embedding),
            "visual_complexity": self._estimate_complexity(result.embedding),
            "embedding_model": self.model_name,
            "device_used": str(self.device) if self.device else "cpu",
            "processing_time": result.processing_time,
            "metadata": result.metadata,
            "confidence": 0.85
        }
        
        # Cache the features if enabled
        if self.enable_caching:
            # Ensure cache doesn't grow too large
            if len(self.embedding_cache) >= self.max_cache_size:
                # Remove oldest (first item)
                self.embedding_cache.popitem(last=False)
            
            self.embedding_cache[cache_key] = features
        
        return features

    async def analyze_query_visual_patterns(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze query for visual patterns and provide visual search enhancement.

        Args:
            query: Search query to analyze
            context: Additional context (user preferences, etc.)

        Returns:
            Visual intelligence for query enhancement
        """
        # Handle None or empty queries
        if query is None:
            print("VISUAL INTELLIGENCE: Query is None, skipping analysis")
            return None

        if not query or not query.strip():
            print("VISUAL INTELLIGENCE: Empty query, providing minimal analysis")
            return {
                "visual_cues": {"colors": [], "patterns": [], "materials": [], "style_cues": [], "has_visual_intent": False},
                "style_analysis": {"occasions": [], "formality": "neutral", "mood": "neutral", "primary_style": "general", "style_confidence": 0.0},
                "search_enhancements": {"color_filters": [], "pattern_preferences": [], "material_preferences": [], "style_direction": "general", "occasion_context": [], "visual_priority": "low", "suggested_colors": ["black", "white", "blue", "red"]},
                "query_visual_score": 0.0,
                "confidence": 0.0,
                "source": "query_analysis"
            }

        try:
            print(f"VISUAL INTELLIGENCE: Analyzing query '{query}'")
            logger.info(f"Visual Intelligence analyzing query: '{query[:50]}...'")

            # Extract visual cues from query
            visual_cues = self._extract_visual_cues_from_query(query)
            print(f"   Visual Cues Found:")
            if visual_cues['colors']:
                print(f"      - Colors: {visual_cues['colors']}")
            if visual_cues['patterns']:
                print(f"      - Patterns: {visual_cues['patterns']}")
            if visual_cues['materials']:
                print(f"      - Materials: {visual_cues['materials']}")
            if visual_cues['style_cues']:
                print(f"      - Style Cues: {visual_cues['style_cues']}")

            # Get style analysis from query
            style_analysis = self._analyze_query_style_intent(query, context)
            print(f"   Style Analysis:")
            if style_analysis['occasions']:
                print(f"      - Occasions: {style_analysis['occasions']}")
            print(f"      - Formality: {style_analysis['formality']}")
            print(f"      - Mood: {style_analysis['mood']}")
            print(f"      - Primary Style: {style_analysis['primary_style']}")
            print(f"      - Style Confidence: {style_analysis['style_confidence']:.1%}")

            # Generate visual search suggestions
            search_enhancements = self._generate_visual_search_enhancements(query, visual_cues, style_analysis)
            print(f"   Search Enhancements:")
            if search_enhancements['color_filters']:
                print(f"      - Color Filters: {search_enhancements['color_filters']}")
            if search_enhancements['suggested_colors']:
                print(f"      - Suggested Colors: {search_enhancements['suggested_colors']}")
            print(f"      - Visual Priority: {search_enhancements['visual_priority']}")

            visual_relevance = self._calculate_query_visual_relevance(query)
            print(f"   Visual Relevance Score: {visual_relevance:.1%}")

            intelligence = {
                "visual_cues": visual_cues,
                "style_analysis": style_analysis,
                "search_enhancements": search_enhancements,
                "query_visual_score": visual_relevance,
                "confidence": 0.75,
                "source": "query_analysis"
            }

            print(f"   Visual Intelligence analysis complete!")
            logger.info(f"Query visual analysis completed: {len(visual_cues.get('colors', []))} colors, {len(visual_cues.get('style_cues', []))} style cues, primary_style={style_analysis.get('primary_style', 'unknown')}")

            return intelligence

        except Exception as e:
            logger.error(f"Error analyzing query visual patterns: {e}")
            return None

    async def analyze_search_results_visually(
        self,
        products: List[Dict[str, Any]],
        query: str,
        limit: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze search results visually to provide enhanced recommendations.

        Args:
            products: List of product dictionaries
            query: Original search query
            limit: Maximum products to analyze

        Returns:
            Visual intelligence about search results
        """
        try:
            if not products:
                return None

            logger.debug(f"Analyzing {min(len(products), limit)} products visually for query: '{query[:30]}...'")

            # Select products to analyze (prioritize those with images)
            products_to_analyze = []
            for product in products[:limit * 2]:  # Check more products to find ones with images
                if product.get('images') or product.get('image_url'):
                    products_to_analyze.append(product)
                    if len(products_to_analyze) >= limit:
                        break

            if not products_to_analyze:
                logger.warning("No products with images found for visual analysis")
                return None

            # Analyze visual features of products
            visual_analyses = []
            for product in products_to_analyze:
                product_id = product.get('id') or product.get('product_id')
                if product_id:
                    features = await self.get_visual_features(product_id)
                    if features:
                        visual_analyses.append({
                            "product_id": product_id,
                            "features": features,
                            "product_data": product
                        })

            if not visual_analyses:
                logger.warning("No visual features extracted from products")
                return None

            # Aggregate visual insights
            aggregated_insights = self._aggregate_visual_insights(visual_analyses, query)

            intelligence = {
                "analyzed_products": len(visual_analyses),
                "visual_insights": aggregated_insights,
                "dominant_patterns": self._extract_dominant_visual_patterns(visual_analyses),
                "style_recommendations": self._generate_style_recommendations(visual_analyses, query),
                "confidence": 0.8,
                "source": "search_results_analysis"
            }

            logger.info(f"Visual analysis of search results completed: {len(visual_analyses)} products analyzed")

            return intelligence

        except Exception as e:
            logger.error(f"Error analyzing search results visually: {e}")
            return None

    def _extract_visual_cues_from_query(self, query: str) -> Dict[str, Any]:
        """Extract visual cues from the search query."""
        query_lower = query.lower()

        # Color detection
        colors = []
        color_keywords = ['black', 'white', 'red', 'blue', 'green', 'yellow', 'pink', 'purple',
                         'orange', 'brown', 'gray', 'grey', 'navy', 'beige', 'gold', 'silver',
                         'maroon', 'teal', 'coral', 'turquoise', 'lavender', 'mint', 'cream',
                         'khaki', 'burgundy', 'olive', 'rose', 'tan', 'charcoal', 'ivory']

        for color in color_keywords:
            if color in query_lower:
                colors.append(color)

        # Pattern detection
        patterns = []
        pattern_keywords = ['striped', 'floral', 'polka dot', 'checkered', 'plaid', 'solid',
                           'printed', 'patterned', 'geometric', 'abstract', 'leopard', 'zebra']

        for pattern in pattern_keywords:
            if pattern in query_lower:
                patterns.append(pattern)

        # Material/texture detection
        materials = []
        material_keywords = ['cotton', 'silk', 'wool', 'leather', 'denim', 'lace', 'velvet',
                           'satin', 'chiffon', 'knit', 'mesh', 'sequin', 'metallic', 'sheer']

        for material in material_keywords:
            if material in query_lower:
                materials.append(material)

        # Style cues
        style_cues = []
        style_keywords = ['vintage', 'modern', 'classic', 'trendy', 'casual', 'formal',
                         'bohemian', 'minimalist', 'edgy', 'romantic', 'sporty', 'chic']

        for style in style_keywords:
            if style in query_lower:
                style_cues.append(style)

        return {
            "colors": colors,
            "patterns": patterns,
            "materials": materials,
            "style_cues": style_cues,
            "has_visual_intent": len(colors) > 0 or len(patterns) > 0 or len(materials) > 0
        }

    def _analyze_query_style_intent(self, query: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze the style intent from the query."""
        query_lower = query.lower()

        # Occasion detection
        occasions = []
        occasion_keywords = ['wedding', 'party', 'work', 'casual', 'formal', 'date', 'beach',
                           'evening', 'cocktail', 'business', 'vacation', 'gym', 'office', 'dinner']

        for occasion in occasion_keywords:
            if occasion in query_lower:
                occasions.append(occasion)

        # Formality level
        formality = "neutral"
        if any(word in query_lower for word in ['formal', 'dress up', 'elegant', 'sophisticated']):
            formality = "formal"
        elif any(word in query_lower for word in ['casual', 'relaxed', 'everyday', 'comfortable']):
            formality = "casual"

        # Style mood
        mood = "neutral"
        if any(word in query_lower for word in ['fun', 'playful', 'bright', 'colorful']):
            mood = "playful"
        elif any(word in query_lower for word in ['serious', 'professional', 'conservative']):
            mood = "serious"
        elif any(word in query_lower for word in ['romantic', 'feminine', 'soft', 'delicate']):
            mood = "romantic"

        # Primary style
        primary_style = "general"
        style_priority = ['bohemian', 'vintage', 'modern', 'minimalist', 'edgy', 'classic', 'trendy']
        for style in style_priority:
            if style in query_lower:
                primary_style = style
                break

        return {
            "occasions": occasions,
            "formality": formality,
            "mood": mood,
            "primary_style": primary_style,
            "style_confidence": 0.7 if occasions or formality != "neutral" else 0.4
        }

    def _generate_visual_search_enhancements(
        self,
        query: str,
        visual_cues: Dict[str, Any],
        style_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate visual search enhancements based on analysis."""

        enhancements = {
            "color_filters": visual_cues.get("colors", []),
            "pattern_preferences": visual_cues.get("patterns", []),
            "material_preferences": visual_cues.get("materials", []),
            "style_direction": style_analysis.get("primary_style", "general"),
            "occasion_context": style_analysis.get("occasions", []),
            "visual_priority": "high" if visual_cues.get("has_visual_intent") else "medium"
        }

        # Add style-specific visual recommendations
        if style_analysis.get("formality") == "formal":
            enhancements["suggested_colors"] = ["black", "navy", "white", "gray"]
            enhancements["avoid_patterns"] = ["cartoon", "very_casual"]
        elif style_analysis.get("formality") == "casual":
            enhancements["suggested_colors"] = ["bright", "colorful", "pastel", "bold"]
            enhancements["pattern_flexibility"] = "high"
            enhancements["color_flexibility"] = "high"
        else:
            # Default suggestions for neutral/unspecified formality
            enhancements["suggested_colors"] = ["black", "white", "blue", "red"]

        return enhancements

    def _calculate_query_visual_relevance(self, query: str) -> float:
        """Calculate how visually relevant a query is."""
        query_lower = query.lower()

        # Visual keywords weight
        visual_keywords = ['color', 'pattern', 'style', 'look', 'design', 'aesthetic', 'visual']
        visual_score = sum(1 for keyword in visual_keywords if keyword in query_lower) * 0.1

        # Specific visual terms weight
        specific_visual = ['striped', 'floral', 'solid', 'printed', 'black', 'white', 'red', 'blue',
                          'silk', 'cotton', 'leather', 'wool', 'gown', 'evening', 'formal', 'dress', 'shirt']
        specific_score = sum(1 for term in specific_visual if term in query_lower) * 0.1

        # Base relevance for fashion queries
        base_score = 0.3

        return round(min(base_score + visual_score + specific_score, 1.0), 3)

    def _aggregate_visual_insights(self, visual_analyses: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
        """Aggregate insights from multiple product analyses."""
        if not visual_analyses:
            return {}

        # Collect all colors
        all_colors = []
        all_styles = []
        aesthetic_scores = []

        for analysis in visual_analyses:
            features = analysis.get("features", {})
            if "dominant_colors" in features:
                all_colors.extend(features["dominant_colors"])
            if "style_attributes" in features:
                all_styles.extend(features["style_attributes"])
            if "aesthetic_score" in features:
                aesthetic_scores.append(features["aesthetic_score"])

        # Find most common elements
        from collections import Counter
        color_counts = Counter(all_colors)
        style_counts = Counter(all_styles)

        return {
            "dominant_colors": [color for color, count in color_counts.most_common(3)],
            "common_styles": [style for style, count in style_counts.most_common(3)],
            "average_aesthetic_score": sum(aesthetic_scores) / len(aesthetic_scores) if aesthetic_scores else 0.5,
            "visual_diversity": len(set(all_colors)) / max(len(all_colors), 1),
            "total_analyzed": len(visual_analyses)
        }

    def _extract_dominant_visual_patterns(self, visual_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract dominant visual patterns from the analyses."""
        if not visual_analyses:
            return {}

        # Analyze complexity distribution
        complexities = []
        for analysis in visual_analyses:
            features = analysis.get("features", {})
            if "visual_complexity" in features:
                complexities.append(features["visual_complexity"])

        # Find most common complexity
        from collections import Counter
        complexity_counts = Counter(complexities)
        dominant_complexity = complexity_counts.most_common(1)[0][0] if complexity_counts else "medium"

        return {
            "dominant_complexity": dominant_complexity,
            "complexity_distribution": dict(complexity_counts),
            "pattern_consistency": len(set(complexities)) <= 2  # True if most products have similar complexity
        }

    def _generate_style_recommendations(self, visual_analyses: List[Dict[str, Any]], query: str) -> List[str]:
        """Generate style recommendations based on visual analysis."""
        recommendations = []

        # Analyze the visual data
        all_styles = []
        for analysis in visual_analyses:
            features = analysis.get("features", {})
            if "style_attributes" in features:
                all_styles.extend(features["style_attributes"])

        # Generate recommendations based on common styles
        from collections import Counter
        style_counts = Counter(all_styles)

        if "luxury" in [style for style, count in style_counts.most_common(2)]:
            recommendations.append("Consider premium materials and refined details")

        if "casual" in [style for style, count in style_counts.most_common(2)]:
            recommendations.append("Focus on comfort and versatility")

        if "professional" in [style for style, count in style_counts.most_common(2)]:
            recommendations.append("Emphasize clean lines and sophisticated silhouettes")

        # Add query-specific recommendations
        if "party" in query.lower() or "evening" in query.lower():
            recommendations.append("Look for items with visual interest and elegant details")

        return recommendations[:3]  # Limit to top 3 recommendations

    async def _process_image(self, image_url: str) -> ImageProcessingResult:
        """
        Process a single image and extract embedding.
        
        Args:
            image_url: URL of image to process
            
        Returns:
            ImageProcessingResult with embedding or error
        """
        start_time = datetime.now()
        self.stats["total_processed"] += 1
        
        if not PYTORCH_AVAILABLE or self.image_model is None:
            return ImageProcessingResult(
                embedding=None,
                metadata={"error": "PyTorch not available"},
                error="PyTorch model not available"
            )
        
        try:
            # Download image with security checks
            image_data = await self._download_image_safely(image_url)
            if not image_data:
                return ImageProcessingResult(
                    embedding=None,
                    metadata={"error": "Download failed"},
                    error="Failed to download image"
                )
            
            # Load and validate image
            img = Image.open(BytesIO(image_data)).convert('RGB')
            
            # Validate dimensions
            if img.width > MAX_IMAGE_DIMENSION or img.height > MAX_IMAGE_DIMENSION:
                # Resize if too large
                img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.LANCZOS)
            
            if img.width < MIN_IMAGE_DIMENSION or img.height < MIN_IMAGE_DIMENSION:
                return ImageProcessingResult(
                    embedding=None,
                    metadata={"error": "Image too small"},
                    error=f"Image dimensions too small: {img.width}x{img.height}"
                )
            
            # Preprocess image
            img_tensor = self.preprocess(img).unsqueeze(0).to(self.device)
            
            # Generate embedding with GPU memory management
            with self.gpu_manager.managed_execution():
                with torch.no_grad():
                    # Set model to eval mode
                    self.image_model.eval()
                    
                    # Generate embedding
                    embedding = self.image_model(img_tensor)
                    
                    # Flatten the embedding
                    if len(embedding.shape) > 2:
                        embedding = torch.nn.functional.adaptive_avg_pool2d(embedding, (1, 1))
                        embedding = embedding.view(embedding.size(0), -1)
                    
                    # Convert to CPU and list
                    embedding = embedding.cpu().squeeze().numpy().tolist()
                    
                    # Ensure it's a list of floats
                    if isinstance(embedding, (int, float)):
                        embedding = [float(embedding)]
                    else:
                        embedding = [float(x) for x in embedding]
            
            processing_time = (datetime.now() - start_time).total_seconds()
            self.stats["successful"] += 1
            self.stats["total_processing_time"] += processing_time
            
            return ImageProcessingResult(
                embedding=embedding,
                metadata={
                    "image_size": f"{img.width}x{img.height}",
                    "embedding_dim": len(embedding),
                    "model": self.model_name
                },
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            self.stats["failed"] += 1
            
            return ImageProcessingResult(
                embedding=None,
                metadata={"error": str(e)},
                error=str(e),
                processing_time=(datetime.now() - start_time).total_seconds()
            )
    
    async def _download_image_safely(self, image_url: str) -> Optional[bytes]:
        """
        Download image with comprehensive security checks.
        
        Args:
            image_url: URL to download
            
        Returns:
            Image data as bytes or None if failed
        """
        try:
            # Validate URL first
            is_valid, error = self._validate_image_url(image_url)
            if not is_valid:
                logger.error(f"URL validation failed: {error}")
                return None
            
            # Prepare headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; AI-Stylist/2.0)',
                'Accept': ', '.join(ALLOWED_CONTENT_TYPES),
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'close',
                'Cache-Control': 'no-cache'
            }
            
            # Download with streaming and security checks
            response = await asyncio.to_thread(
                requests.get,
                image_url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                stream=True,
                allow_redirects=False
            )
            
            # Handle redirects manually (security)
            redirect_count = 0
            while response.status_code in [301, 302, 303, 307, 308]:
                if redirect_count >= MAX_REDIRECTS:
                    logger.warning("Too many redirects")
                    return None
                
                redirect_url = response.headers.get('location')
                if not redirect_url:
                    logger.warning("Redirect without location header")
                    return None
                
                # Validate redirect URL
                is_valid, error = self._validate_image_url(redirect_url)
                if not is_valid:
                    logger.warning(f"Redirect to invalid URL: {error}")
                    return None
                
                response = await asyncio.to_thread(
                    requests.get,
                    redirect_url,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                    stream=True,
                    allow_redirects=False
                )
                redirect_count += 1
            
            # Check status
            response.raise_for_status()
            
            # Validate content type
            content_type = response.headers.get('content-type', '').lower().split(';')[0]
            if content_type not in ALLOWED_CONTENT_TYPES:
                logger.warning(f"Unsupported content type: {content_type}")
                return None
            
            # Check content length
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > self.max_image_size:
                logger.warning(f"Image too large: {content_length} bytes")
                return None
            
            # Download with size limit
            image_data = BytesIO()
            downloaded = 0
            
            for chunk in response.iter_content(chunk_size=8192):
                downloaded += len(chunk)
                if downloaded > self.max_image_size:
                    logger.warning(f"Image exceeds size limit during download")
                    return None
                image_data.write(chunk)
            
            return image_data.getvalue()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error downloading image: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading image: {e}")
            return None
    
    async def process_batch(
        self,
        product_ids: List[str]
    ) -> List[Optional[Dict[str, Any]]]:
        """
        Process multiple products in batch for efficiency.
        
        Args:
            product_ids: List of product IDs
            
        Returns:
            List of feature dictionaries (None for failures)
        """
        results = []
        
        # Process in batches
        for i in range(0, len(product_ids), self.batch_size):
            batch = product_ids[i:i + self.batch_size]
            
            # Process batch in parallel
            tasks = [self.get_visual_features(pid) for pid in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle results
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch processing error: {result}")
                    results.append(None)
                else:
                    results.append(result)
            
            # GPU cleanup between batches
            if self.device and self.device.type == 'cuda':
                self.gpu_manager.check_and_cleanup()
        
        return results
    
    # Helper methods remain mostly the same with minor improvements
    async def _extract_dominant_colors(self, image_url: str) -> List[str]:
        """Extract dominant colors from image (simplified)."""
        # Only process if URL is valid
        is_valid, _ = self._validate_image_url(image_url)
        if not is_valid:
            return ["neutral", "unknown"]
        
        # In production, would use proper color clustering
        # For now, return common fashion colors
        return ["black", "white", "neutral"]
    
    def _infer_style_attributes(self, product: Dict[str, Any]) -> List[str]:
        """Infer style attributes from product data."""
        attributes = []
        
        # Infer from categories
        categories = product.get('categories', [])
        if isinstance(categories, str):
            categories = [categories]
            
        for category in categories:
            if 'dress' in category.lower():
                attributes.append('feminine')
            if 'suit' in category.lower():
                attributes.append('professional')
            if 'casual' in category.lower():
                attributes.append('casual')
        
        # Infer from tags
        tags = product.get('tags', [])
        if isinstance(tags, str):
            tags = [tags]
            
        for tag in tags:
            if tag.lower() in ['casual', 'formal', 'trendy', 'vintage', 'minimalist']:
                attributes.append(tag.lower())
        
        # Infer from price
        price = product.get('price', 0)
        if price > 500:
            attributes.append('luxury')
        elif price < 50:
            attributes.append('affordable')
        else:
            attributes.append('mid-range')
        
        # Deduplicate and limit
        return list(set(attributes))[:7]
    
    def _calculate_aesthetic_score(self, embedding: Optional[List[float]]) -> float:
        """Calculate aesthetic score from embedding."""
        if not embedding or len(embedding) == 0:
            return 0.5
        
        # Convert to numpy for calculations
        embedding_array = np.array(embedding)
        
        # Use statistical properties as proxy for aesthetics
        # This is simplified - in production, use a trained aesthetic model
        mean_val = np.mean(np.abs(embedding_array))
        std_val = np.std(embedding_array)
        
        # Calculate score based on distribution
        score = 1.0 / (1.0 + np.exp(-mean_val + std_val))
        
        # Add some variance based on embedding values
        if len(embedding) > 100:
            # Use percentiles for better scoring
            p25 = np.percentile(embedding_array, 25)
            p75 = np.percentile(embedding_array, 75)
            iqr = p75 - p25
            
            # Adjust score based on IQR
            score = score * 0.7 + (1.0 / (1.0 + np.exp(-iqr))) * 0.3
        
        return float(min(max(score, 0.0), 1.0))
    
    def _estimate_complexity(self, embedding: Optional[List[float]]) -> str:
        """Estimate visual complexity from embedding."""
        if not embedding or len(embedding) == 0:
            return "medium"
        
        # Use embedding statistics
        variance = np.var(embedding)
        entropy = -np.sum(np.abs(embedding) * np.log(np.abs(embedding) + 1e-10))
        
        # Classify complexity
        if variance < 0.1 and entropy < 100:
            return "simple"
        elif variance > 0.5 or entropy > 500:
            return "complex"
        else:
            return "medium"
    
    async def _get_product_details(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get product details from knowledge graph."""
        if not self.product_kg:
            return None
        
        try:
            if hasattr(self.product_kg, 'get_product'):
                return await self.product_kg.get_product(product_id)
            elif hasattr(self.product_kg, 'get_product_details'):
                return await self.product_kg.get_product_details(product_id)
            else:
                logger.warning("No method to get product details")
                return None
        except Exception as e:
            logger.error(f"Error getting product details: {e}")
            return None
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get comprehensive information about the current PyTorch model."""
        info = {
            "backend": "pytorch",
            "model_name": self.model_name,
            "embedding_dim": self.embedding_dim,
            "device": str(self.device) if self.device else "unknown",
            "available": PYTORCH_AVAILABLE and self.image_model is not None,
            "pytorch_version": torch.__version__ if PYTORCH_AVAILABLE else None,
            "cuda_available": torch.cuda.is_available() if PYTORCH_AVAILABLE else False,
            "security": {
                "url_validation": True,
                "allowed_domains": len(self.allowed_domains),
                "max_image_size": f"{self.max_image_size / 1e6:.1f}MB",
                "max_dimension": MAX_IMAGE_DIMENSION,
                "content_type_validation": True,
                "redirect_limit": MAX_REDIRECTS
            },
            "performance": {
                "caching_enabled": self.enable_caching,
                "cache_size": len(self.embedding_cache) if self.embedding_cache else 0,
                "max_cache_size": self.max_cache_size,
                "batch_size": self.batch_size
            },
            "statistics": self.stats
        }
        
        # Add GPU memory stats if available
        if self.gpu_manager:
            info["gpu_memory"] = self.gpu_manager.get_memory_stats()
        
        # Add cache statistics
        if self.enable_caching:
            cache_total = self.cache_hits + self.cache_misses
            info["performance"]["cache_hit_rate"] = (
                f"{self.cache_hits / cache_total * 100:.1f}%" 
                if cache_total > 0 else "0%"
            )
        
        return info
    
    def add_allowed_domain(self, domain: str):
        """
        Add an allowed domain for image URLs.
        
        Args:
            domain: Domain to allow
        """
        domain = domain.lower().strip()
        self.allowed_domains.add(domain)
        logger.info(f"Added allowed domain: {domain}")
    
    def remove_allowed_domain(self, domain: str):
        """
        Remove an allowed domain.
        
        Args:
            domain: Domain to remove
        """
        domain = domain.lower().strip()
        self.allowed_domains.discard(domain)
        logger.info(f"Removed allowed domain: {domain}")
    
    async def cleanup(self):
        """Clean up resources and GPU memory."""
        logger.info("Cleaning up Visual Intelligence resources")
        
        # Clear cache
        if self.embedding_cache:
            self.embedding_cache.clear()
        
        # Force GPU cleanup
        if self.gpu_manager:
            self.gpu_manager.force_cleanup()
        
        # Clear model from GPU if needed
        if self.image_model and self.device and self.device.type == 'cuda':
            self.image_model.cpu()
            del self.image_model
            self.image_model = None
            torch.cuda.empty_cache()
        
        logger.info("Visual Intelligence cleanup complete")