import os
import logging
import json
from typing import Dict, List, Any, Optional


# Add this at the very top of product_retriever.py, before other imports
try:
    from openai_embedding_adapter import initialization_result
    if initialization_result:
        logging.info("ProductRetriever: OpenAI embedding adapter initialized")
    else:
        logging.warning("ProductRetriever: OpenAI embedding adapter initialization failed")
except Exception as e:
    logging.warning(f"ProductRetriever: Failed to import OpenAI embedding adapter: {e}")


from camel.retrievers import AutoRetriever
from camel.types import StorageType, EmbeddingModelType
from camel.embeddings import OpenAIEmbedding
from camel.toolkits import RetrievalToolkit

# Try to import qdrant_client for direct remote access
try:
    import qdrant_client
    from qdrant_client.http import models
    QDRANT_CLIENT_AVAILABLE = True
except ImportError:
    QDRANT_CLIENT_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("product_retriever")

class ProductRetriever:
    """
    Product retriever using CAMEL's AutoRetriever to access products from Neo4j.
    Provides vector-based semantic search capabilities.
    
    Supports both local storage and remote Qdrant (if qdrant_client is available).
    """
    
    def __init__(self, vector_storage_path="product_data/embeddings", 
                 qdrant_url=None, qdrant_api_key=None, qdrant_collection_name="products"):
        """
        Initialize the product retriever.
        
        Args:
            vector_storage_path: Path to store vector embeddings locally
            qdrant_url: URL for remote Qdrant server (if None, use local storage)
            qdrant_api_key: API key for remote Qdrant authentication
            qdrant_collection_name: Name of the collection in Qdrant
        """
        self.using_remote = bool(qdrant_url) and QDRANT_CLIENT_AVAILABLE
        self.qdrant_collection_name = qdrant_collection_name
        
        if self.using_remote:
            logger.info(f"Initializing ProductRetriever with remote Qdrant at: {qdrant_url}")
        else:
            logger.info(f"Initializing ProductRetriever with local storage path: {vector_storage_path}")
            # Ensure the vector storage directory exists for local mode
            os.makedirs(os.path.dirname(vector_storage_path), exist_ok=True)
        
        try: 
            # Initialize embedding model - using our adapter
            self.embedding_model = OpenAIEmbedding(
                model_type=EmbeddingModelType.TEXT_EMBEDDING_ADA_2,
                # The adapter will handle ensuring the correct request format
            )
         
         
            # Initialize direct Qdrant client for remote connections
            if self.using_remote:
                self.qdrant_client = qdrant_client.QdrantClient(
                    url=qdrant_url,
                    api_key=qdrant_api_key
                )
                logger.info(f"Connected to remote Qdrant instance: {qdrant_url}")
                
                # Check if collection exists, create if it doesn't
                self._ensure_collection_exists()
            
            # Initialize retriever for local mode only
            # (For remote, we'll use direct Qdrant client)
            if not self.using_remote:
                self.retriever = AutoRetriever(
                    vector_storage_local_path=vector_storage_path,
                    storage_type=StorageType.QDRANT,
                    embedding_model=self.embedding_model,
                )
                logger.info("Initialized local AutoRetriever")
            else:
                # For remote, we'll use our own implementation
                self.retriever = None
            
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
            if self.using_remote:
                self.qdrant_client = None
    
    def _ensure_collection_exists(self):
        """Ensure that the collection exists, creating it if necessary"""
        if not self.using_remote or not hasattr(self, 'qdrant_client'):
            return False
            
        try:
            # Check if collection exists
            collections = self.qdrant_client.get_collections()
            collection_exists = any(c.name == self.qdrant_collection_name for c in collections.collections)
            
            if not collection_exists:
                logger.info(f"Creating collection '{self.qdrant_collection_name}'...")
                # Create the collection
                self.qdrant_client.create_collection(
                    collection_name=self.qdrant_collection_name,
                    vectors_config=models.VectorParams(
                        size=1536,  # OpenAI embedding size
                        distance=models.Distance.COSINE
                    )
                )
                logger.info(f"Collection '{self.qdrant_collection_name}' created successfully")
                return True
            return True
        except Exception as e:
            logger.error(f"Error ensuring collection exists: {e}")
            return False
    
    def setup_product_indexing(self, neo4j_connection):
        """
        Index product data from Neo4j to vector store.
        Works with both local and remote Qdrant instances.
        
        Args:
            neo4j_connection: Neo4j connection instance
        """
        logger.info("Indexing product data from Neo4j to vector store...")
        
        if not self.embedding_model or (self.using_remote and not hasattr(self, 'qdrant_client')) or \
           (not self.using_remote and not self.retriever):
            logger.error("Vector store not properly initialized, cannot index products")
            return
        
        try:
            # Query products from Neo4j with actual schema
            products = self._get_products_from_neo4j(neo4j_connection)
            
            # Check if we have products
            if not products:
                logger.warning("No products found in Neo4j database")
                return
                
            logger.info(f"Found {len(products)} products in database")
            
            if self.using_remote:
                # Make sure collection exists
                self._ensure_collection_exists()
                
                # Get list of already indexed product IDs
                indexed_product_ids = self._get_indexed_product_ids()
                logger.info(f"Found {len(indexed_product_ids)} products already indexed in Qdrant")
                
                # Filter out already indexed products
                products_to_index = [p for p in products if p.get('id', '') not in indexed_product_ids]
                
                skipped_count = len(products) - len(products_to_index)
                logger.info(f"Skipping {skipped_count} already indexed products")
                logger.info(f"Need to index {len(products_to_index)} new products")
                
                # For remote Qdrant, index directly using the client
                if products_to_index:
                    self._index_to_remote_qdrant(products_to_index)
                else:
                    logger.info("All products are already indexed, nothing to do")
            else:
                # Local indexing
                # Create temporary descriptions file for local indexing
                product_data_dir = "product_data"
                os.makedirs(product_data_dir, exist_ok=True)
                descriptions_file = os.path.join(product_data_dir, "descriptions.txt")
                
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
                    logger.info("Local indexing complete!")
                except Exception as e:
                    logger.error(f"Error processing with AutoRetriever: {e}")
                    # Try alternative method if direct processing fails
                    self._alternative_indexing(descriptions_file)
                
        except Exception as e:
            logger.error(f"Error indexing product data: {e}")
    
    def _get_indexed_product_ids(self):
        """
        Get list of product IDs that are already indexed in Qdrant
        
        Returns:
            Set of product IDs already in Qdrant
        """
        if not self.using_remote or not hasattr(self, 'qdrant_client'):
            return set()
            
        try:
            # Ensure collection exists
            if not self._ensure_collection_exists():
                return set()
            
            # Get collection info to determine size
            collection_info = self.qdrant_client.get_collection(self.qdrant_collection_name)
            total_points = collection_info.vectors_count
            
            if total_points == 0:
                return set()
                
            logger.info(f"Collection has {total_points} points, retrieving product IDs...")
            
            # Use scrolling to get all points in batches
            product_ids = set()
            limit = 100
            offset = None
            
            while True:
                # Get a batch of points
                results = self.qdrant_client.scroll(
                    collection_name=self.qdrant_collection_name,
                    limit=limit,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False
                )
                
                # Extract IDs from points
                batch_points = results[0]
                if not batch_points:
                    break
                    
                for point in batch_points:
                    if point.payload and "product_id" in point.payload:
                        product_ids.add(point.payload["product_id"])
                
                # Get offset for next batch
                offset = results[1]  # This is the next offset for scrolling
                
                # Print progress
                logger.info(f"Retrieved {len(product_ids)} product IDs so far...")
                
                # Exit if we're out of points
                if offset is None or len(batch_points) < limit:
                    break
            
            logger.info(f"Retrieved {len(product_ids)} unique product IDs from Qdrant")
            return product_ids
            
        except Exception as e:
            logger.error(f"Error getting indexed product IDs: {e}")
            return set()
    
    def _index_to_remote_qdrant(self, products):
        """
        Index products directly to remote Qdrant instance
        
        Args:
            products: List of product dictionaries
        """
        if not self.using_remote or not hasattr(self, 'qdrant_client') or not self.embedding_model:
            logger.error("Remote Qdrant or embedding model not available")
            return
            
        try:
            total_products = len(products)
            logger.info(f"Starting indexing of {total_products} products to collection: {self.qdrant_collection_name}")
            
            # Track progress
            indexed_count = 0
            batch_size = 50  # Reduced batch size for more frequent updates
            
            for i in range(0, total_products, batch_size):
                # Calculate progress percentage
                progress_pct = (indexed_count / total_products) * 100
                logger.info(f"Progress: {indexed_count}/{total_products} products ({progress_pct:.1f}%)")
                
                # Get current batch
                batch = products[i:i+batch_size]
                batch_count = len(batch)
                
                # Prepare batch points
                logger.info(f"Preparing batch {i//batch_size + 1} ({batch_count} products)...")
                points = []
                
                for idx, product in enumerate(batch):
                    # Create text representation
                    text_repr = self._create_product_text_representation(product)
                    
                    # Generate embedding
                    logger.info(f"Generating embedding for product {i+idx+1}/{total_products}...")
                    embedding = self.embedding_model.embed_list([text_repr])[0]
                    
                    # Create point with a unique ID
                    import uuid
                    point_id = str(uuid.uuid4())
                    points.append(models.PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "text": text_repr,
                            "product_id": product.get('id', ''),
                            "title": product.get('title', ''),
                            "price": product.get('price', 0),
                            "categories": product.get('categories', []),
                            "collections": product.get('collections', []),
                            "tags": product.get('tags', [])
                        }
                    ))
                
                # Upload batch
                logger.info(f"Uploading batch {i//batch_size + 1} to Qdrant...")
                self.qdrant_client.upsert(
                    collection_name=self.qdrant_collection_name,
                    points=points
                )
                
                # Update progress
                indexed_count += batch_count
                logger.info(f"Indexed batch {i//batch_size + 1}/{(total_products-1)//batch_size + 1} - Total progress: {indexed_count}/{total_products}")
            
            logger.info(f"Indexing complete! {total_products} products indexed to Qdrant collection '{self.qdrant_collection_name}'")
            
        except Exception as e:
            logger.error(f"Error indexing to remote Qdrant: {e}")
    
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
        
        if not query or len(query.strip()) == 0:
            logger.warning("Empty query provided")
            return []
        
        try:
            if self.using_remote and hasattr(self, 'qdrant_client') and self.embedding_model:
                # Use direct Qdrant client for remote search
                return self._search_remote_qdrant(query, limit, similarity_threshold)
            elif not self.using_remote and self.retriever:
                # Use CAMEL's AutoRetriever for local search
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
            else:
                logger.error("No search capabilities available")
                return []
                
        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return []
    
    def _search_remote_qdrant(self, query, limit=5, similarity_threshold=0.7):
        """
        Search products in remote Qdrant instance
        
        Args:
            query: Search query
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score
            
        Returns:
            Retrieved product information
        """
        if not self.using_remote or not hasattr(self, 'qdrant_client') or not self.embedding_model:
            logger.error("Remote Qdrant or embedding model not available")
            return []
            
        try:
            # Ensure collection exists
            if not self._ensure_collection_exists():
                logger.error("Unable to ensure collection exists, aborting search")
                return []

            # Generate embedding for query
            logger.info("Generating embedding for search query")
            query_embedding = self.embedding_model.embed(query)  # Use embed instead of embed_list for single query
                        
            # Search in Qdrant
            search_results = self.qdrant_client.search(
                collection_name=self.qdrant_collection_name,
                query_vector=query_embedding,
                limit=limit,
                score_threshold=similarity_threshold
            )
            
            logger.info(f"Found {len(search_results)} results in remote Qdrant")
            
            # Format results
            formatted_results = []
            for result in search_results:
                payload = result.payload
                product_info = {
                    "id": payload.get("product_id", ""),
                    "title": payload.get("title", "Untitled Product"),
                    "price": payload.get("price", 0.0),
                    "description": "",  # Extract from text if needed
                    "categories": payload.get("categories", []),
                    "collections": payload.get("collections", []),
                    "tags": payload.get("tags", []),
                    "features": payload.get("tags", []),  # Use tags as features
                    "similarity_score": result.score
                }
                
                # Try to extract description from text
                if "text" in payload:
                    text_lines = payload["text"].split('\n')
                    for line in text_lines:
                        if line.startswith("Description:"):
                            product_info["description"] = line[12:].strip()
                            break
                
                formatted_results.append(product_info)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching in remote Qdrant: {e}")
            return []
    
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
        Ensures the text stays under the token limit for embedding.
        
        Args:
            product: Product dictionary
            
        Returns:
            Text representation of the product
        """
        # Build a rich text description with all product attributes
        lines = []
        
        # Essential information (must keep)
        lines.append(f"Product ID: {product.get('id', '')}")
        lines.append(f"Product: {product.get('title', 'Untitled Product')}")
        lines.append(f"Price: ${product.get('price', 0.0)}")
        
        # Important but can be shortened if needed
        if product.get("categories"):
            categories = ", ".join(product.get("categories"))
            lines.append(f"Categories: {categories}")
        
        if product.get("collections"):
            collections = ", ".join(product.get("collections"))
            lines.append(f"Collections: {collections}")
        
        if product.get("tags"):
            tags = ", ".join(product.get("tags"))
            lines.append(f"Tags: {tags}")
        
        # Description (most likely to be truncated)
        description = product.get("description", "").strip()
        if description:
            # Limit description length to approximately 1000 characters
            if len(description) > 1000:
                description = description[:997] + "..."
            lines.append(f"Description: {description}")
        else:
            # Create a synthetic description from categories, collections and tags
            synthetic_parts = []
            if product.get("categories"):
                synthetic_parts.append(f"a {', '.join(product.get('categories', []))} product")
            if product.get("collections"):
                synthetic_parts.append(f"from the {', '.join(product.get('collections'))} collection")
            if product.get("tags"):
                synthetic_parts.append(f"featuring {', '.join(product.get('tags', []))}")
            
            if synthetic_parts:
                synthetic_description = " ".join(synthetic_parts)
                lines.append(f"Description: {synthetic_description}")
        
        # Join lines with newlines
        text = "\n".join(lines)
        
        # Additional safety truncation - limit to ~4000 chars (well under token limit)
        if len(text) > 4000:
            logger.warning(f"Truncating very long product text for ID {product.get('id', '')}")
            text = text[:3997] + "..."
        
        return text
    
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
        
        if not product_id:
            logger.error("No product ID provided")
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