"""
Unit tests for Pydantic models.
Tests validation, defaults, and model constraints.
"""
import pytest
from pydantic import ValidationError
from models.product_models import (
    Product,
    GraphSearchResult,
    VectorSearchResult,
    VisualSearchResult,
    JudgmentResult,
    ProductSearchState,
    ProductSearchResult
)


class TestProduct:
    """Test Product model validation."""

    def test_valid_product_creation(self):
        """Test creating a valid product."""
        product = Product(
            id="test-123",
            title="Red Dress",
            price=99.99,
            category="dresses"
        )
        assert product.id == "test-123"
        assert product.title == "Red Dress"
        assert product.price == 99.99
        assert product.category == "dresses"
        assert product.images == []  # Default

    def test_product_with_scores(self):
        """Test product with agent scores."""
        product = Product(
            id="test-123",
            title="Red Dress",
            price=99.99,
            category="dresses",
            cypher_score=0.85,
            vibe_score=0.92,
            visual_score=0.78,
            judge_score=0.88
        )
        assert product.cypher_score == 0.85
        assert product.vibe_score == 0.92
        assert product.visual_score == 0.78
        assert product.judge_score == 0.88

    def test_product_price_validation(self):
        """Test price must be positive."""
        with pytest.raises(ValidationError) as exc_info:
            Product(
                id="test-123",
                title="Red Dress",
                price=-10.0,  # Invalid
                category="dresses"
            )
        assert "greater than 0" in str(exc_info.value)

    def test_product_score_validation(self):
        """Test scores must be 0-1."""
        # Test score > 1
        with pytest.raises(ValidationError):
            Product(
                id="test-123",
                title="Red Dress",
                price=99.99,
                category="dresses",
                cypher_score=1.5  # Invalid
            )

        # Test score < 0
        with pytest.raises(ValidationError):
            Product(
                id="test-123",
                title="Red Dress",
                price=99.99,
                category="dresses",
                vibe_score=-0.1  # Invalid
            )

    def test_product_images_list(self):
        """Test images field accepts list."""
        product = Product(
            id="test-123",
            title="Red Dress",
            price=99.99,
            category="dresses",
            images=["img1.jpg", "img2.jpg"]
        )
        assert len(product.images) == 2
        assert "img1.jpg" in product.images


class TestGraphSearchResult:
    """Test GraphSearchResult model."""

    def test_valid_graph_result(self):
        """Test creating valid graph search result."""
        products = [
            Product(id="1", title="Product 1", price=50.0, category="test"),
            Product(id="2", title="Product 2", price=75.0, category="test")
        ]
        result = GraphSearchResult(
            products=products,
            search_strategy="COLLABORATIVE",
            reasoning="Found products through collaborative filtering",
            execution_time=1.23,
            products_found=2
        )
        assert len(result.products) == 2
        assert result.search_strategy == "COLLABORATIVE"
        assert result.products_found == 2

    def test_empty_products_list(self):
        """Test graph result with no products."""
        result = GraphSearchResult(
            products=[],
            search_strategy="GENERAL",
            reasoning="No products found",
            execution_time=0.5,
            products_found=0
        )
        assert result.products == []
        assert result.products_found == 0


class TestVectorSearchResult:
    """Test VectorSearchResult model."""

    def test_valid_vector_result(self):
        """Test creating valid vector search result."""
        products = [
            Product(id="1", title="Product 1", price=50.0, category="test")
        ]
        result = VectorSearchResult(
            products=products,
            search_strategy="SEMANTIC",
            reasoning="Semantic similarity search",
            execution_time=0.89,
            products_found=1
        )
        assert result.search_strategy == "SEMANTIC"
        assert result.products_found == 1


class TestVisualSearchResult:
    """Test VisualSearchResult model."""

    def test_valid_visual_result(self):
        """Test creating valid visual search result."""
        products = [
            Product(id="1", title="Product 1", price=50.0, category="test")
        ]
        result = VisualSearchResult(
            products=products,
            search_strategy="VISUAL_SIMILARITY",
            reasoning="Visual embedding similarity",
            execution_time=1.45,
            products_found=1
        )
        assert result.search_strategy == "VISUAL_SIMILARITY"


class TestJudgmentResult:
    """Test JudgmentResult model."""

    def test_valid_judgment_result(self):
        """Test creating valid judgment result."""
        products = [
            Product(id="1", title="Product 1", price=50.0, category="test", judge_score=0.95)
        ]
        result = JudgmentResult(
            final_products=products,
            quality_assessments={"1": 0.95},
            consensus_products=["1"],
            rejected_products=[],
            judgment_confidence=0.9,
            detailed_reasoning="High quality consensus product",
            execution_time=0.67
        )
        assert len(result.final_products) == 1
        assert result.judgment_confidence == 0.9
        assert "1" in result.consensus_products

    def test_judgment_confidence_validation(self):
        """Test confidence must be 0-1."""
        with pytest.raises(ValidationError):
            JudgmentResult(
                final_products=[],
                quality_assessments={},
                consensus_products=[],
                rejected_products=[],
                judgment_confidence=1.5,  # Invalid
                detailed_reasoning="Test",
                execution_time=0.5
            )


class TestProductSearchState:
    """Test ProductSearchState model."""

    def test_state_initialization(self):
        """Test state with defaults."""
        state = ProductSearchState(query="red dress")
        assert state.query == "red dress"
        assert state.filters == {}
        assert state.limit == 5
        assert state.individual_crew_timeout == 30
        assert state.graph_result is None

    def test_state_with_filters(self):
        """Test state with custom filters."""
        state = ProductSearchState(
            query="blue jeans",
            filters={"category": "jeans", "color": "blue"},
            limit=10
        )
        assert state.filters["category"] == "jeans"
        assert state.limit == 10

    def test_state_limit_validation(self):
        """Test limit must be 1-50."""
        # Test limit < 1
        with pytest.raises(ValidationError):
            ProductSearchState(query="test", limit=0)

        # Test limit > 50
        with pytest.raises(ValidationError):
            ProductSearchState(query="test", limit=100)

    def test_state_with_results(self):
        """Test state after storing crew results."""
        state = ProductSearchState(query="test")

        # Simulate storing graph result
        graph_result = GraphSearchResult(
            products=[],
            search_strategy="GENERAL",
            reasoning="Test",
            execution_time=1.0,
            products_found=0
        )
        state.graph_result = graph_result

        assert state.graph_result is not None
        assert state.graph_result.search_strategy == "GENERAL"


class TestProductSearchResult:
    """Test ProductSearchResult final output model."""

    def test_valid_final_result(self):
        """Test creating valid final result."""
        products = [
            Product(id="1", title="Product 1", price=50.0, category="test")
        ]
        result = ProductSearchResult(
            products=products,
            reasoning="Found 1 high-quality product",
            metadata={"total_searched": 100},
            execution_time=5.23,
            graph_count=10,
            vector_count=15,
            visual_count=12,
            consensus_count=1,
            quality_controlled=True
        )
        assert len(result.products) == 1
        assert result.graph_count == 10
        assert result.quality_controlled is True

    def test_final_result_defaults(self):
        """Test final result with defaults."""
        result = ProductSearchResult(
            products=[],
            reasoning="No products found",
            metadata={},
            execution_time=2.0
        )
        assert result.graph_count == 0
        assert result.vector_count == 0
        assert result.consensus_count == 0
        assert result.quality_controlled is False


class TestModelSerialization:
    """Test model serialization to dict/JSON."""

    def test_product_dict_serialization(self):
        """Test Product.dict() works."""
        product = Product(
            id="test-123",
            title="Red Dress",
            price=99.99,
            category="dresses",
            cypher_score=0.85
        )
        data = product.dict()
        assert data["id"] == "test-123"
        assert data["price"] == 99.99
        assert data["cypher_score"] == 0.85

    def test_nested_model_serialization(self):
        """Test nested models serialize correctly."""
        products = [
            Product(id="1", title="Product 1", price=50.0, category="test")
        ]
        result = ProductSearchResult(
            products=products,
            reasoning="Test",
            metadata={"key": "value"},
            execution_time=1.0
        )
        data = result.dict()
        assert len(data["products"]) == 1
        assert data["products"][0]["id"] == "1"
        assert data["metadata"]["key"] == "value"
