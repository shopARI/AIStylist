"""
Hybrid Intent Detector - Phase 1 Implementation
Combines LLM-based detection with hardcoded fallback for reliability
"""

import logging
import asyncio
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Import from parent directory for SearchIntent
import sys
sys.path.append('/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27')
from models.types import SearchIntent

# Import from local nlp module
from .intent_detector import IntentDetector, IntentResult
from .parameter_extractor import ParameterExtractor

# Import CrewAI components
try:
    from .crewai_intent_detector import CrewAIIntentDetector, CrewAIIntentResult, get_crewai_intent_detector
    CREWAI_AVAILABLE = True
except ImportError as e:
    logger = logging.getLogger("ari_crewai.nlp.hybrid_intent_detector")
    logger.warning(f"CrewAI intent detector not available: {e}")
    CREWAI_AVAILABLE = False

logger = logging.getLogger("ari_crewai.nlp.hybrid_intent_detector")

class DetectionStrategy(Enum):
    """Strategy for intent detection"""
    LLM_FIRST = "llm_first"          # Try CrewAI first, fallback to hardcoded
    HARDCODED_FIRST = "hardcoded_first"  # Try hardcoded first, CrewAI for complex queries
    LLM_ONLY = "llm_only"            # CrewAI only (no fallback)
    HARDCODED_ONLY = "hardcoded_only"  # Hardcoded only (current system)
    PARALLEL = "parallel"            # Run both, compare results

@dataclass
class HybridResult:
    """Result from hybrid intent detection"""
    primary_intent: SearchIntent
    confidence: float
    extracted_parameters: Dict[str, Any]
    detection_method: str  # "crewai", "hardcoded", "hybrid"
    processing_time: float
    crewai_result: Optional[CrewAIIntentResult] = None
    hardcoded_result: Optional[IntentResult] = None
    fallback_used: bool = False
    comparison_data: Optional[Dict[str, Any]] = None

class HybridIntentDetector:
    """
    Hybrid intent detector that combines CrewAI agents and hardcoded approaches.
    Provides multiple strategies for different use cases.
    """

    def __init__(
        self,
        strategy: DetectionStrategy = DetectionStrategy.LLM_FIRST,
        crewai_confidence_threshold: float = 0.7,
        enable_comparison_logging: bool = True
    ):
        """
        Initialize hybrid detector with specified strategy.

        Args:
            strategy: Detection strategy to use
            crewai_confidence_threshold: Minimum confidence to trust CrewAI results
            enable_comparison_logging: Whether to log detailed comparisons
        """
        self.strategy = strategy
        self.crewai_confidence_threshold = crewai_confidence_threshold
        self.enable_comparison_logging = enable_comparison_logging

        # Initialize hardcoded components (always available)
        self.hardcoded_detector = IntentDetector()
        self.parameter_extractor = ParameterExtractor()

        # Initialize CrewAI components (if available)
        self.crewai_detector = None
        if CREWAI_AVAILABLE and strategy != DetectionStrategy.HARDCODED_ONLY:
            try:
                self.crewai_detector = get_crewai_intent_detector()
                logger.info(f"Hybrid detector initialized with strategy: {strategy.value}")
            except Exception as e:
                logger.error(f"Failed to initialize CrewAI detector: {e}")
                # Fallback to hardcoded only
                if strategy == DetectionStrategy.LLM_ONLY:
                    raise RuntimeError("LLM_ONLY strategy requested but CrewAI unavailable")
                self.strategy = DetectionStrategy.HARDCODED_ONLY
        else:
            if strategy not in [DetectionStrategy.HARDCODED_ONLY]:
                logger.warning(f"CrewAI not available, falling back to HARDCODED_ONLY")
                self.strategy = DetectionStrategy.HARDCODED_ONLY
        
        # Performance tracking
        self.stats = {
            "total_queries": 0,
            "crewai_used": 0,
            "hardcoded_used": 0,
            "fallbacks": 0,
            "average_processing_time": 0.0
        }
    
    async def detect_intent_and_extract(self, query: str) -> HybridResult:
        """
        Main detection method using the configured strategy.
        
        Args:
            query: User's natural language query
            
        Returns:
            HybridResult with intent, parameters, and method metadata
        """
        start_time = time.time()
        self.stats["total_queries"] += 1
        
        try:
            if self.strategy == DetectionStrategy.LLM_FIRST:
                return await self._llm_first_strategy(query, start_time)
            elif self.strategy == DetectionStrategy.HARDCODED_FIRST:
                return await self._hardcoded_first_strategy(query, start_time)
            elif self.strategy == DetectionStrategy.LLM_ONLY:
                return await self._llm_only_strategy(query, start_time)
            elif self.strategy == DetectionStrategy.HARDCODED_ONLY:
                return await self._hardcoded_only_strategy(query, start_time)
            elif self.strategy == DetectionStrategy.PARALLEL:
                return await self._parallel_strategy(query, start_time)
            else:
                raise ValueError(f"Unknown strategy: {self.strategy}")
                
        except Exception as e:
            logger.error(f"Hybrid detection failed: {e}", exc_info=True)
            # Emergency fallback to hardcoded
            return await self._emergency_fallback(query, start_time)
    
    async def _llm_first_strategy(self, query: str, start_time: float) -> HybridResult:
        """Try CrewAI first, fallback to hardcoded if confidence too low"""
        
        if not self.crewai_detector:
            return await self._hardcoded_only_strategy(query, start_time)
        
        try:
            # Try CrewAI detection
            crewai_result = await self.crewai_detector.detect_intent_and_extract(query)
            self.stats["crewai_used"] += 1
            
            # Check if CrewAI result is confident enough
            if crewai_result.confidence >= self.crewai_confidence_threshold:
                return HybridResult(
                    primary_intent=crewai_result.primary_intent,
                    confidence=crewai_result.confidence,
                    extracted_parameters=crewai_result.extracted_parameters,
                    detection_method="crewai",
                    processing_time=time.time() - start_time,
                    crewai_result=crewai_result,
                    fallback_used=False
                )
            
            # CrewAI confidence too low, fallback to hardcoded
            logger.debug(f"CrewAI confidence {crewai_result.confidence:.2f} below threshold {self.crewai_confidence_threshold}, using hardcoded fallback")
            hardcoded_result = await self.hardcoded_detector.detect_intent(query)
            hardcoded_params = self.parameter_extractor.extract_parameters(query)
            
            self.stats["fallbacks"] += 1
            
            return HybridResult(
                primary_intent=hardcoded_result.primary_intent,
                confidence=hardcoded_result.confidence,
                extracted_parameters=hardcoded_params,
                detection_method="hardcoded_fallback",
                processing_time=time.time() - start_time,
                crewai_result=crewai_result,
                fallback_used=True
            )
            
        except Exception as e:
            logger.error(f"CrewAI detection failed: {e}")
            # Fallback to hardcoded
            return await self._hardcoded_only_strategy(query, start_time)
    
    async def _hardcoded_first_strategy(self, query: str, start_time: float) -> HybridResult:
        """Try hardcoded first, use CrewAI for complex queries"""
        
        # Try hardcoded detection
        hardcoded_result = await self.hardcoded_detector.detect_intent(query)
        hardcoded_params = self.parameter_extractor.extract_parameters(query)
        self.stats["hardcoded_used"] += 1
        
        # If hardcoded found good results, use them
        if (hardcoded_result.confidence > 0.8 and 
            (hardcoded_params.get("categories") or hardcoded_params.get("occasions"))):
            
            return HybridResult(
                primary_intent=hardcoded_result.primary_intent,
                confidence=hardcoded_result.confidence,
                extracted_parameters=hardcoded_params,
                detection_method="hardcoded",
                processing_time=time.time() - start_time,
                hardcoded_result=hardcoded_result,
                fallback_used=False
            )
        
        # Hardcoded results weak, try CrewAI if available
        if self.crewai_detector:
            try:
                crewai_result = await self.crewai_detector.detect_intent_and_extract(query)
                self.stats["crewai_used"] += 1
                
                return HybridResult(
                    primary_intent=crewai_result.primary_intent,
                    confidence=crewai_result.confidence,
                    extracted_parameters=crewai_result.extracted_parameters,
                    detection_method="llm_enhancement",
                    processing_time=time.time() - start_time,
                    hardcoded_result=hardcoded_result,
                    crewai_result=crewai_result,
                    fallback_used=True
                )
                
            except Exception as e:
                logger.error(f"CrewAI enhancement failed: {e}")
        
        # Return hardcoded results as fallback
        return HybridResult(
            primary_intent=hardcoded_result.primary_intent,
            confidence=hardcoded_result.confidence,
            extracted_parameters=hardcoded_params,
            detection_method="hardcoded",
            processing_time=time.time() - start_time,
            hardcoded_result=hardcoded_result,
            fallback_used=False
        )
    
    async def _llm_only_strategy(self, query: str, start_time: float) -> HybridResult:
        """Use CrewAI only"""
        if not self.crewai_detector:
            raise RuntimeError("CrewAI detector not available for LLM_ONLY strategy")
        
        crewai_result = await self.crewai_detector.detect_intent_and_extract(query)
        self.stats["crewai_used"] += 1
        
        return HybridResult(
            primary_intent=crewai_result.primary_intent,
            confidence=crewai_result.confidence,
            extracted_parameters=crewai_result.extracted_parameters,
            detection_method="crewai",
            processing_time=time.time() - start_time,
            crewai_result=crewai_result,
            fallback_used=False
        )
    
    async def _hardcoded_only_strategy(self, query: str, start_time: float) -> HybridResult:
        """Use hardcoded only (current system)"""
        hardcoded_result = await self.hardcoded_detector.detect_intent(query)
        hardcoded_params = self.parameter_extractor.extract_parameters(query)
        self.stats["hardcoded_used"] += 1
        
        return HybridResult(
            primary_intent=hardcoded_result.primary_intent,
            confidence=hardcoded_result.confidence,
            extracted_parameters=hardcoded_params,
            detection_method="hardcoded",
            processing_time=time.time() - start_time,
            hardcoded_result=hardcoded_result,
            fallback_used=False
        )
    
    async def _parallel_strategy(self, query: str, start_time: float) -> HybridResult:
        """Run both methods in parallel and compare"""
        
        tasks = []
        
        # Always run hardcoded
        tasks.append(asyncio.create_task(self._run_hardcoded(query)))
        
        # Run CrewAI if available
        if self.crewai_detector:
            tasks.append(asyncio.create_task(self._run_llm(query)))
        
        # Wait for all results
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        hardcoded_result, hardcoded_params = results[0] if not isinstance(results[0], Exception) else (None, {})
        crewai_result = results[1] if len(results) > 1 and not isinstance(results[1], Exception) else None
        
        self.stats["hardcoded_used"] += 1
        if crewai_result:
            self.stats["crewai_used"] += 1
        
        # Choose best result
        chosen_method, chosen_intent, chosen_confidence, chosen_params = self._choose_best_result(
            hardcoded_result, hardcoded_params, crewai_result
        )
        
        # Log comparison if enabled
        comparison_data = None
        if self.enable_comparison_logging:
            comparison_data = self._create_comparison_data(hardcoded_result, hardcoded_params, crewai_result)
        
        return HybridResult(
            primary_intent=chosen_intent,
            confidence=chosen_confidence,
            extracted_parameters=chosen_params,
            detection_method=chosen_method,
            processing_time=time.time() - start_time,
            hardcoded_result=hardcoded_result,
            crewai_result=crewai_result,
            fallback_used=False,
            comparison_data=comparison_data
        )
    
    async def _run_hardcoded(self, query: str) -> Tuple[IntentResult, Dict[str, Any]]:
        """Run hardcoded detection"""
        intent_result = await self.hardcoded_detector.detect_intent(query)
        params = self.parameter_extractor.extract_parameters(query)
        return intent_result, params
    
    async def _run_llm(self, query: str) -> CrewAIIntentResult:
        """Run CrewAI detection"""
        return await self.crewai_detector.detect_intent_and_extract(query)
    
    def _choose_best_result(
        self,
        hardcoded_result: Optional[IntentResult],
        hardcoded_params: Dict[str, Any],
        crewai_result: Optional[CrewAIIntentResult]
    ) -> Tuple[str, SearchIntent, float, Dict[str, Any]]:
        """Choose the best result from parallel detection"""
        
        # If only one method succeeded, use it
        if hardcoded_result and not crewai_result:
            return "hardcoded", hardcoded_result.primary_intent, hardcoded_result.confidence, hardcoded_params
        
        if crewai_result and not hardcoded_result:
            return "crewai", crewai_result.primary_intent, crewai_result.confidence, crewai_result.extracted_parameters
        
        if not hardcoded_result and not crewai_result:
            # Both failed, return default
            return "fallback", SearchIntent.BROWSE, 0.1, {}
        
        # Both succeeded, choose based on confidence and parameter richness
        hardcoded_score = hardcoded_result.confidence
        llm_score = crewai_result.confidence
        
        # Boost score for parameter richness
        hardcoded_param_count = sum(1 for v in hardcoded_params.values() if v)
        llm_param_count = sum(1 for v in crewai_result.extracted_parameters.values() if v)
        
        hardcoded_score += min(hardcoded_param_count * 0.1, 0.3)
        llm_score += min(llm_param_count * 0.1, 0.3)
        
        if llm_score > hardcoded_score + 0.1:  # Small bias toward CrewAI for ties
            return "crewai", crewai_result.primary_intent, crewai_result.confidence, crewai_result.extracted_parameters
        else:
            return "hardcoded", hardcoded_result.primary_intent, hardcoded_result.confidence, hardcoded_params
    
    def _create_comparison_data(
        self,
        hardcoded_result: Optional[IntentResult],
        hardcoded_params: Dict[str, Any],
        crewai_result: Optional[CrewAIIntentResult]
    ) -> Dict[str, Any]:
        """Create comparison data for analysis"""
        return {
            "hardcoded": {
                "intent": hardcoded_result.primary_intent.name if hardcoded_result else None,
                "confidence": hardcoded_result.confidence if hardcoded_result else 0,
                "param_count": sum(1 for v in hardcoded_params.values() if v)
            },
            "crewai": {
                "intent": crewai_result.primary_intent.name if crewai_result else None,
                "confidence": crewai_result.confidence if crewai_result else 0,
                "param_count": sum(1 for v in crewai_result.extracted_parameters.values() if v) if crewai_result else 0
            },
            "intents_match": (
                hardcoded_result and crewai_result and 
                hardcoded_result.primary_intent == crewai_result.primary_intent
            )
        }
    
    async def _emergency_fallback(self, query: str, start_time: float) -> HybridResult:
        """Emergency fallback when everything fails"""
        logger.error("Emergency fallback activated")
        
        return HybridResult(
            primary_intent=SearchIntent.BROWSE,
            confidence=0.1,
            extracted_parameters={},
            detection_method="emergency_fallback",
            processing_time=time.time() - start_time,
            fallback_used=True
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        return {
            **self.stats,
            "strategy": self.strategy.value,
            "crewai_available": self.crewai_detector is not None,
            "crewai_confidence_threshold": self.crewai_confidence_threshold
        }
    
    def reset_stats(self):
        """Reset performance statistics"""
        self.stats = {
            "total_queries": 0,
            "crewai_used": 0,
            "hardcoded_used": 0,
            "fallbacks": 0,
            "average_processing_time": 0.0
        }


# Global instance
_hybrid_detector: Optional[HybridIntentDetector] = None
_hybrid_detector_strategy: Optional[DetectionStrategy] = None


def get_hybrid_intent_detector(
    strategy: DetectionStrategy = DetectionStrategy.LLM_FIRST
) -> HybridIntentDetector:
    """Get singleton hybrid intent detector (recreates if strategy changes)"""
    global _hybrid_detector, _hybrid_detector_strategy

    # Recreate if strategy changed or doesn't exist
    if _hybrid_detector is None or _hybrid_detector_strategy != strategy:
        _hybrid_detector = HybridIntentDetector(strategy=strategy)
        _hybrid_detector_strategy = strategy

    return _hybrid_detector


# Export
__all__ = [
    'HybridIntentDetector',
    'HybridResult',
    'DetectionStrategy',
    'get_hybrid_intent_detector'
]