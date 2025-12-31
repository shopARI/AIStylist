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

from models.types import SearchIntent
from services.nlp.intent_detector import IntentDetector, IntentResult
from services.nlp.parameter_extractor import ParameterExtractor

# Import LLM components
try:
    from services.nlp.llm_intent_detector import LLMIntentDetector, LLMIntentResult, get_llm_intent_detector
    LLM_AVAILABLE = True
except ImportError as e:
    logger.warning(f"LLM intent detector not available: {e}")
    LLM_AVAILABLE = False

logger = logging.getLogger("services.nlp.hybrid_intent_detector")

class DetectionStrategy(Enum):
    """Strategy for intent detection"""
    LLM_FIRST = "llm_first"          # Try LLM first, fallback to hardcoded
    HARDCODED_FIRST = "hardcoded_first"  # Try hardcoded first, LLM for complex queries
    LLM_ONLY = "llm_only"            # LLM only (no fallback)
    HARDCODED_ONLY = "hardcoded_only"  # Hardcoded only (current system)
    PARALLEL = "parallel"            # Run both, compare results

@dataclass
class HybridResult:
    """Result from hybrid intent detection"""
    primary_intent: SearchIntent
    confidence: float
    extracted_parameters: Dict[str, Any]
    detection_method: str  # "llm", "hardcoded", "hybrid"
    processing_time: float
    llm_result: Optional[LLMIntentResult] = None
    hardcoded_result: Optional[IntentResult] = None
    fallback_used: bool = False
    comparison_data: Optional[Dict[str, Any]] = None

class HybridIntentDetector:
    """
    Hybrid intent detector that combines LLM and hardcoded approaches.
    Provides multiple strategies for different use cases.
    """
    
    def __init__(
        self,
        strategy: DetectionStrategy = DetectionStrategy.LLM_ONLY,
        llm_confidence_threshold: float = 0.7,
        enable_comparison_logging: bool = True
    ):
        """
        Initialize hybrid detector with specified strategy.
        
        Args:
            strategy: Detection strategy to use
            llm_confidence_threshold: Minimum confidence to trust LLM results
            enable_comparison_logging: Whether to log detailed comparisons
        """
        self.strategy = strategy
        self.llm_confidence_threshold = llm_confidence_threshold
        self.enable_comparison_logging = enable_comparison_logging
        
        # Initialize hardcoded components (always available)
        self.hardcoded_detector = IntentDetector()
        self.parameter_extractor = ParameterExtractor()
        
        # Initialize LLM components (if available)
        self.llm_detector = None
        if LLM_AVAILABLE and strategy != DetectionStrategy.HARDCODED_ONLY:
            try:
                self.llm_detector = get_llm_intent_detector()
                logger.info(f"Hybrid detector initialized with strategy: {strategy.value}")
            except Exception as e:
                logger.error(f"Failed to initialize LLM detector: {e}")
                # Fallback to hardcoded only
                if strategy == DetectionStrategy.LLM_ONLY:
                    raise RuntimeError("LLM_ONLY strategy requested but LLM unavailable")
                self.strategy = DetectionStrategy.HARDCODED_ONLY
        else:
            if strategy not in [DetectionStrategy.HARDCODED_ONLY]:
                logger.warning(f"LLM not available, falling back to HARDCODED_ONLY")
                self.strategy = DetectionStrategy.HARDCODED_ONLY
        
        # Performance tracking
        self.stats = {
            "total_queries": 0,
            "llm_used": 0,
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
        """Try LLM first, fallback to hardcoded if confidence too low"""
        
        if not self.llm_detector:
            return await self._hardcoded_only_strategy(query, start_time)
        
        try:
            # Try LLM detection
            llm_result = await self.llm_detector.detect_intent_and_extract(query)
            self.stats["llm_used"] += 1
            
            # Check if LLM result is confident enough
            if llm_result.confidence >= self.llm_confidence_threshold:
                return HybridResult(
                    primary_intent=llm_result.primary_intent,
                    confidence=llm_result.confidence,
                    extracted_parameters=llm_result.extracted_parameters,
                    detection_method="llm",
                    processing_time=time.time() - start_time,
                    llm_result=llm_result,
                    fallback_used=False
                )
            
            # LLM confidence too low, fallback to hardcoded
            logger.debug(f"LLM confidence {llm_result.confidence:.2f} below threshold {self.llm_confidence_threshold}, using hardcoded fallback")
            hardcoded_result = await self.hardcoded_detector.detect_intent(query)
            hardcoded_params = self.parameter_extractor.extract_parameters(query)
            
            self.stats["fallbacks"] += 1
            
            return HybridResult(
                primary_intent=hardcoded_result.primary_intent,
                confidence=hardcoded_result.confidence,
                extracted_parameters=hardcoded_params,
                detection_method="hardcoded_fallback",
                processing_time=time.time() - start_time,
                llm_result=llm_result,
                fallback_used=True
            )
            
        except Exception as e:
            logger.error(f"LLM detection failed: {e}")
            # Fallback to hardcoded
            return await self._hardcoded_only_strategy(query, start_time)
    
    async def _hardcoded_first_strategy(self, query: str, start_time: float) -> HybridResult:
        """Try hardcoded first, use LLM for complex queries"""
        
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
        
        # Hardcoded results weak, try LLM if available
        if self.llm_detector:
            try:
                llm_result = await self.llm_detector.detect_intent_and_extract(query)
                self.stats["llm_used"] += 1
                
                return HybridResult(
                    primary_intent=llm_result.primary_intent,
                    confidence=llm_result.confidence,
                    extracted_parameters=llm_result.extracted_parameters,
                    detection_method="llm_enhancement",
                    processing_time=time.time() - start_time,
                    hardcoded_result=hardcoded_result,
                    llm_result=llm_result,
                    fallback_used=True
                )
                
            except Exception as e:
                logger.error(f"LLM enhancement failed: {e}")
        
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
        """Use LLM only"""
        if not self.llm_detector:
            raise RuntimeError("LLM detector not available for LLM_ONLY strategy")
        
        llm_result = await self.llm_detector.detect_intent_and_extract(query)
        self.stats["llm_used"] += 1
        
        return HybridResult(
            primary_intent=llm_result.primary_intent,
            confidence=llm_result.confidence,
            extracted_parameters=llm_result.extracted_parameters,
            detection_method="llm",
            processing_time=time.time() - start_time,
            llm_result=llm_result,
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
        
        # Run LLM if available
        if self.llm_detector:
            tasks.append(asyncio.create_task(self._run_llm(query)))
        
        # Wait for all results
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        hardcoded_result, hardcoded_params = results[0] if not isinstance(results[0], Exception) else (None, {})
        llm_result = results[1] if len(results) > 1 and not isinstance(results[1], Exception) else None
        
        self.stats["hardcoded_used"] += 1
        if llm_result:
            self.stats["llm_used"] += 1
        
        # Choose best result
        chosen_method, chosen_intent, chosen_confidence, chosen_params = self._choose_best_result(
            hardcoded_result, hardcoded_params, llm_result
        )
        
        # Log comparison if enabled
        comparison_data = None
        if self.enable_comparison_logging:
            comparison_data = self._create_comparison_data(hardcoded_result, hardcoded_params, llm_result)
        
        return HybridResult(
            primary_intent=chosen_intent,
            confidence=chosen_confidence,
            extracted_parameters=chosen_params,
            detection_method=chosen_method,
            processing_time=time.time() - start_time,
            hardcoded_result=hardcoded_result,
            llm_result=llm_result,
            fallback_used=False,
            comparison_data=comparison_data
        )
    
    async def _run_hardcoded(self, query: str) -> Tuple[IntentResult, Dict[str, Any]]:
        """Run hardcoded detection"""
        intent_result = await self.hardcoded_detector.detect_intent(query)
        params = self.parameter_extractor.extract_parameters(query)
        return intent_result, params
    
    async def _run_llm(self, query: str) -> LLMIntentResult:
        """Run LLM detection"""
        return await self.llm_detector.detect_intent_and_extract(query)
    
    def _choose_best_result(
        self,
        hardcoded_result: Optional[IntentResult],
        hardcoded_params: Dict[str, Any],
        llm_result: Optional[LLMIntentResult]
    ) -> Tuple[str, SearchIntent, float, Dict[str, Any]]:
        """Choose the best result from parallel detection"""
        
        # If only one method succeeded, use it
        if hardcoded_result and not llm_result:
            return "hardcoded", hardcoded_result.primary_intent, hardcoded_result.confidence, hardcoded_params
        
        if llm_result and not hardcoded_result:
            return "llm", llm_result.primary_intent, llm_result.confidence, llm_result.extracted_parameters
        
        if not hardcoded_result and not llm_result:
            # Both failed, return default
            return "fallback", SearchIntent.BROWSE, 0.1, {}
        
        # Both succeeded, choose based on confidence and parameter richness
        hardcoded_score = hardcoded_result.confidence
        llm_score = llm_result.confidence
        
        # Boost score for parameter richness
        hardcoded_param_count = sum(1 for v in hardcoded_params.values() if v)
        llm_param_count = sum(1 for v in llm_result.extracted_parameters.values() if v)
        
        hardcoded_score += min(hardcoded_param_count * 0.1, 0.3)
        llm_score += min(llm_param_count * 0.1, 0.3)
        
        if llm_score > hardcoded_score + 0.1:  # Small bias toward LLM for ties
            return "llm", llm_result.primary_intent, llm_result.confidence, llm_result.extracted_parameters
        else:
            return "hardcoded", hardcoded_result.primary_intent, hardcoded_result.confidence, hardcoded_params
    
    def _create_comparison_data(
        self,
        hardcoded_result: Optional[IntentResult],
        hardcoded_params: Dict[str, Any],
        llm_result: Optional[LLMIntentResult]
    ) -> Dict[str, Any]:
        """Create comparison data for analysis"""
        return {
            "hardcoded": {
                "intent": hardcoded_result.primary_intent.name if hardcoded_result else None,
                "confidence": hardcoded_result.confidence if hardcoded_result else 0,
                "param_count": sum(1 for v in hardcoded_params.values() if v)
            },
            "llm": {
                "intent": llm_result.primary_intent.name if llm_result else None,
                "confidence": llm_result.confidence if llm_result else 0,
                "param_count": sum(1 for v in llm_result.extracted_parameters.values() if v) if llm_result else 0
            },
            "intents_match": (
                hardcoded_result and llm_result and 
                hardcoded_result.primary_intent == llm_result.primary_intent
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
            "llm_available": self.llm_detector is not None,
            "llm_confidence_threshold": self.llm_confidence_threshold
        }
    
    def reset_stats(self):
        """Reset performance statistics"""
        self.stats = {
            "total_queries": 0,
            "llm_used": 0,
            "hardcoded_used": 0,
            "fallbacks": 0,
            "average_processing_time": 0.0
        }


# Global instance
_hybrid_detector: Optional[HybridIntentDetector] = None


def get_hybrid_intent_detector(
    strategy: DetectionStrategy = DetectionStrategy.LLM_ONLY
) -> HybridIntentDetector:
    """Get singleton hybrid intent detector"""
    global _hybrid_detector
    
    if _hybrid_detector is None:
        _hybrid_detector = HybridIntentDetector(strategy=strategy)
    
    return _hybrid_detector


# Export
__all__ = [
    'HybridIntentDetector',
    'HybridResult',
    'DetectionStrategy',
    'get_hybrid_intent_detector'
]