import os
import logging
import json
from typing import Dict, List, Any, Optional
from camel.retrievers import AutoRetriever
from camel.types import StorageType, EmbeddingModelType
from camel.embeddings import OpenAIEmbedding
from camel.toolkits import RetrievalToolkit

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("product_retriever")

class ProductRetriever:
    """
    Product retriever using CAMEL's AutoRetriever to access products from Neo4j.
    Provides vector-based semantic search capabilities.
    """
    
    def __init__(self, vector_storage_path="product_data/embeddings"):
        """
        Initialize the product retriever.
        
        Args:
            vector_storage_path: Path to store vector embeddings
        """
        logger.info(f"Initializing ProductRetriever with storage path: {vector_storage_path}")
        
        # Ensure the vector storage directory exists
        os.makedirs(os.path.dirname(vector_storage_path), exist_ok=True)
        
        try:
            # Initialize embedding model
            self.embedding_model = OpenAIEmbedding(
                model_type=EmbeddingModelType.TEXT_EMBEDDING_ADA_2
            )
            
            # Initialize auto retriever
            self.retriever = AutoRetriever(
                vector_storage_local_path=vector_storage_path,
                storage_type=StorageType.QDRANT,
                embedding_model=self.embedding_model,
            )
            
            # Set up retrieval toolkit for function calling
            self.retrieval_toolkit = RetrievalToolkit()
            self.retrieval_tools = self.retrieval_toolkit.get_tools()
            
            logger.info("ProductRetriever initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing ProductRetriever: {e}")
            # Create empty placeholders for graceful degradation
            self.embedding_model = None
            self.retriever = None
            self.retrieval_toolkit = None
            self.retrieval_tools = []
    
    def setup_product_indexing(self, neo4j_connection):
        """
        Index product data from Neo4j to vector store.
        
        Args:
            neo4j_connection: Neo4j connection instance
        """
        logger.info("Indexing product data from Neo4j to vector store...")
        
        if not self.retriever or not self.embedding_model:
            logger.error("Retriever not properly initialized, cannot index products")
            return
            
        try:
            # Create temporary descriptions file
            product_data_dir = "product_data"
            os.makedirs(product_data_dir, exist_ok=True)
            descriptions_file = os.path.join(product_data_dir, "descriptions.txt")
            
            # Query products from Neo4j with actual schema
            products = self._get_products_from_neo4j(neo4j_connection)
            
            # Check if we have products
            if not products:
                logger.warning("No products found in Neo4j database")
                return
                
            logger.info(f"Found {len(products)} products to index")
            
            # Create a text file with product descriptions for vector indexing
            with open(descriptions_file, "w", encoding="utf-8") as f:
                for product in products:
                    # Create rich text representation of each product
                    f.write(self._create_product_text_representation(product))
                    f.write("\n\n") # Add separation between products
            
            # Process the file with the retriever
            try:
                logger.info(f"Processing {descriptions_file} with AutoRetriever")
                self.retriever.process(descriptions_file)
                logger.info("Indexing complete!")
            except Exception as e:
                logger.error(f"Error processing with AutoRetriever: {e}")
                # Try alternative method if direct processing fails
                self._alternative_indexing(descriptions_file)
                
        except Exception as e:
            logger.error(f"Error indexing product data: {e}")
    
    def _get_products_from_neo4j(self, neo4j_connection):
        """
        Get products from Neo4j for indexing.
        
        Args:
            neo4j_connection: Neo4j connection instance
            
        Returns:
            List of product dictionaries
        """
        try:
            # Query that works with actual database schema
            query = """
            MATCH (p:Product)
            OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
            OPTIONAL MATCH (p)-[:IN_COLLECTION]->(col:Collection)
            OPTIONAL MATCH (p)-[:TAGGED_WITH]->(t:Tag)
            RETURN 
                p.id as id, 
                p.title as title, 
                p.description as description,
                p.price as price, 
                p.images as images,
                collect(distinct c.title) as categories,
                collect(distinct col.title) as collections,
                collect(distinct t.title) as tags
            """
            
            # Execute query
            result = neo4j_connection.query(query)
            
            if not result:
                logger.warning("No products returned from Neo4j query")
                return []
                
            # Process and clean up the results
            products = []
            for record in result:
                # Filter empty collections
                categories = [c for c in record.get("categories", []) if c]
                collections = [c for c in record.get("collections", []) if c]
                tags = [t for t in record.get("tags", []) if t]
                
                # Parse images
                images = []
                try:
                    image_str = record.get("images", "[]")
                    if image_str:
                        # Try to parse as JSON
                        if isinstance(image_str, str):
                            image_str = image_str.replace("'", '"')
                            images = json.loads(image_str)
                        elif isinstance(image_str, list):
                            images = image_str
                except Exception as e:
                    logger.warning(f"Failed to parse images for product {record.get('id')}: {e}")
                
                # Create product dictionary
                product = {
                    "id": record.get("id", ""),
                    "title": record.get("title", "Untitled Product"),
                    "description": record.get("description", ""),
                    "price": record.get("price", 0.0),
                    "images": images,
                    "categories": categories,
                    "collections": collections,
                    "tags": tags
                }
                
                products.append(product)
            
            return products
        
        except Exception as e:
            logger.error(f"Error getting products from Neo4j: {e}")
            return []
    
    def _create_product_text_representation(self, product):
        """
        Create a text representation of a product for vector indexing.
        
        Args:
            product: Product dictionary
            
        Returns:
            Text representation of the product
        """
        # Build a rich text description with all product attributes
        lines = []
        
        # Add product ID for retrieval
        lines.append(f"Product ID: {product.get('id', '')}")
        
        # Add title
        lines.append(f"Product: {product.get('title', 'Untitled Product')}")
        
        # Add price
        lines.append(f"Price: ${product.get('price', 0.0)}")
        
        # Add categories if available
        if product.get("categories"):
            categories = ", ".join(product.get("categories"))
            lines.append(f"Categories: {categories}")
        
        # Add collections if available
        if product.get("collections"):
            collections = ", ".join(product.get("collections"))
            lines.append(f"Collections: {collections}")
        
        # Add tags if available
        if product.get("tags"):
            tags = ", ".join(product.get("tags"))
            lines.append(f"Tags: {tags}")
        
        # Add image URLs if available
        if product.get("images"):
            if isinstance(product.get("images"), list) and len(product.get("images")) > 0:
                lines.append(f"Images: {len(product.get('images'))} available")
            else:
                lines.append("Images: Available")
        
        # Add description if available
        description = product.get("description", "").strip()
        if description:
            lines.append(f"Description: {description}")
        else:
            # Create a synthetic description from categories, collections and tags
            synthetic_description = f"A {', '.join(product.get('categories', []))} product"
            if product.get("collections"):
                synthetic_description += f" from the {', '.join(product.get('collections'))} collection"
            if product.get("tags"):
                synthetic_description += f" featuring {', '.join(product.get('tags', []))}"
            lines.append(f"Description: {synthetic_description}")
        
        # Join lines with newlines
        return "\n".join(lines)
    
    def _alternative_indexing(self, descriptions_file):
        """
        Alternative indexing method if direct processing fails.
        
        Args:
            descriptions_file: Path to descriptions file
        """
        logger.info("Using alternative indexing method")
        
        try:
            # Read the file
            with open(descriptions_file, "r", encoding="utf-8") as f:
                text = f.read()
            
            # Split into product chunks
            product_chunks = text.split("\n\n")
            logger.info(f"Split descriptions into {len(product_chunks)} chunks")
            
            # Code here would use alternative indexing method
            # For now, just log that it's ready for indexing
            logger.info(f"File created for retrieval: {descriptions_file}")
            logger.info("Alternative indexing would process these chunks")
            
        except Exception as e:
            logger.error(f"Alternative indexing failed: {e}")
    
    def search_products(self, query, limit=5, similarity_threshold=0.7):
        """
        Search for products based on a query using vector similarity.
        
        Args:
            query: Search query
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score
            
        Returns:
            Retrieved product information
        """
        logger.info(f"Searching products with query: '{query}'")
        
        if not self.retriever:
            logger.error("Retriever not properly initialized, cannot search products")
            return []
            
        try:
            # Ensure query is not empty
            if not query or len(query.strip()) == 0:
                logger.warning("Empty query provided")
                return []
                
            # Run the vector retriever
            retrieved_info = self.retriever.run_vector_retriever(
                query=query,
                contents=["product_data/descriptions.txt"],
                top_k=limit,
                similarity_threshold=similarity_threshold,
                return_detailed_info=True
            )
            
            logger.info(f"Found {len(retrieved_info) if isinstance(retrieved_info, list) else 0} results")
            
            # Format results for compatibility with the rest of the system
            formatted_results = self._process_retrieval_results(retrieved_info)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return []
    
    def _process_retrieval_results(self, retrieved_info):
        """
        Process retrieval results into standardized product format.
        
        Args:
            retrieved_info: Results from retriever
            
        Returns:
            List of formatted product dictionaries
        """
        formatted_results = []
        
        # Handle different return types from the retriever
        if isinstance(retrieved_info, list):
            # Process list of results
            for item in retrieved_info:
                product_info = self._parse_product_from_text(item.get('content', ''))
                if product_info:
                    formatted_results.append(product_info)
        elif isinstance(retrieved_info, dict):
            # Process dictionary results
            for key, value in retrieved_info.items():
                if isinstance(value, dict) and 'content' in value:
                    product_info = self._parse_product_from_text(value['content'])
                    if product_info:
                        formatted_results.append(product_info)
        
        return formatted_results
    
    def _parse_product_from_text(self, text):
        """
        Parse product information from retrieved text blocks.
        
        Args:
            text: Retrieved text content
            
        Returns:
            Dictionary with product details
        """
        if not text:
            return None
            
        lines = text.strip().split('\n')
        product = {}
        
        # Parse each line based on the format created during indexing
        for line in lines:
            line = line.strip()
            
            if line.startswith("Product ID:"):
                product["id"] = line[11:].strip()
            elif line.startswith("Product:"):
                product["title"] = line[8:].strip()
            elif line.startswith("Price:"):
                try:
                    # Extract price value (remove $ and convert to float)
                    price_str = line[6:].strip().replace('$', '')
                    product["price"] = float(price_str)
                except (ValueError, TypeError):
                    product["price"] = 0
            elif line.startswith("Categories:"):
                product["categories"] = [cat.strip() for cat in line[11:].split(',') if cat.strip()]
            elif line.startswith("Collections:"):
                product["collections"] = [col.strip() for col in line[12:].split(',') if col.strip()]
            elif line.startswith("Tags:"):
                product["tags"] = [tag.strip() for tag in line[5:].split(',') if tag.strip()]
                # Use tags as features for compatibility
                product["features"] = product["tags"]
            elif line.startswith("Description:"):
                product["description"] = line[12:].strip()
        
        # Ensure we have required fields
        if "id" not in product or "title" not in product:
            return None
        
        # Set default values for missing fields
        product.setdefault("price", 0.0)
        product.setdefault("description", "")
        product.setdefault("categories", [])
        product.setdefault("collections", [])
        product.setdefault("tags", [])
        product.setdefault("features", [])
        product.setdefault("images", [])
        
        # Set brand from tags if available
        if product.get("tags"):
            # Simple heuristic: first capitalized tag might be a brand
            for tag in product.get("tags"):
                if tag and tag[0].isupper():
                    product["brand"] = tag
                    break
        
        return product
    
    def search_similar_products(self, product_id, limit=5):
        """
        Find products similar to a given product ID.
        
        Args:
            product_id: ID of the reference product
            limit: Maximum number of results
            
        Returns:
            List of similar products
        """
        logger.info(f"Searching for products similar to ID: {product_id}")
        
        if not self.retriever:
            logger.error("Retriever not properly initialized, cannot search similar products")
            return []
            
        try:
            # Create a query using the product ID
            query = f"Product ID: {product_id}"
            
            # Run the search
            results = self.search_products(
                query=query,
                limit=limit+1,  # Add 1 to account for the product itself
                similarity_threshold=0.6  # Lower threshold for similar products
            )
            
            # Remove the reference product from results
            filtered_results = [p for p in results if p.get("id") != product_id]
            
            # Limit to requested count
            return filtered_results[:limit]
            
        except Exception as e:
            logger.error(f"Error finding similar products: {e}")
            return []
    
    def search_by_natural_language(self, nl_query, limit=5):
        """
        Search products using a natural language query.
        
        Args:
            nl_query: Natural language query
            limit: Maximum number of results
            
        Returns:
            List of matching products
        """
        logger.info(f"Searching with natural language query: '{nl_query}'")
        
        if not nl_query:
            logger.error("Empty natural language query")
            return []
            
        # Enhance the query with some context about product attributes
        enhanced_query = f"Find a product that is {nl_query}. Consider categories, collections, tags, and description."
        
        # Run the search with the enhanced query
        return self.search_products(
            query=enhanced_query,
            limit=limit,
            similarity_threshold=0.6  # Lower threshold for natural language queries
        )
    
    def get_tools(self):
        """
        Get the retrieval tools for function calling.
        
        Returns:
            List of retrieval tools
        """
        return self.retrieval_tools
