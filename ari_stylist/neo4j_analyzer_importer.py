import json
import logging
import re
import sys
import os
import time
from pathlib import Path
from collections import defaultdict, Counter
from neo4j import GraphDatabase, exceptions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("neo4j_analyzer_import.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class Neo4jProductImporter:
    """
    Analyzes a product dataset to discover relationships and imports them into Neo4j.
    Combines analysis and import in one unified workflow with optimized performance.
    """
    
    def __init__(self, uri, username, password, batch_size=500):
        """
        Initialize the importer with Neo4j connection details
        
        Args:
            uri: Neo4j server URI
            username: Neo4j username
            password: Neo4j password
            batch_size: Number of products to process in a single transaction
        """
        # Neo4j connection
        self.uri = uri
        self.username = username
        self.password = password
        self.driver = None
        self.batch_size = batch_size
        
        # Analysis collections
        self.found_relationships = {}
        self.relationship_counts = defaultdict(int)
        
        # Initialize reference lists for pattern matching
        self._initialize_reference_data()
        
        # Tracking collections for creating related products
        self.products_by_category = defaultdict(list)
        self.products_by_material = defaultdict(list)
        self.products_by_color = defaultdict(list)
        self.products_by_type = defaultdict(list)
        
        # Statistics
        self.total_products = 0
        self.stats = defaultdict(int)
        
        # Execution time tracking
        self.start_time = None
    
    def _initialize_reference_data(self):
        """Initialize lists of known materials, colors, etc. for pattern matching"""
        # Enhanced category mapping from product types
        self.category_mapping = {
            # Jewelry
            'earring': 'Earrings',
            'necklace': 'Necklaces',
            'bracelet': 'Bracelets',
            'ring': 'Rings',
            'anklet': 'Anklets',
            'choker': 'Necklaces',
            'pendant': 'Necklaces',
            'stud': 'Earrings',
            'hoop': 'Earrings',
            'huggie': 'Earrings',
            'chain': 'Necklaces',
            'charm': 'Jewelry Charms',
            'bangle': 'Bracelets',
            
            # Clothing
            'dress': 'Dresses',
            'pants': 'Pants',
            'cardigan': 'Sweaters',
            'shirt': 'Shirts',
            'hat': 'Hats',
            'socks': 'Socks',
            'jacket': 'Jackets',
            'skirt': 'Skirts',
            'leggings': 'Pants',
            'sweater': 'Sweaters',
            'blouse': 'Tops',
            'top': 'Tops'
        }
        
        # Materials
        self.known_materials = [
            "14K Gold", "Gold", "White Gold", "Rose Gold", "Silver", "Sterling Silver", 
            "Brass", "Brass Plated", "Gold Plated", "Gold Vermeil", "Polyester", "Spandex", 
            "Acrylic", "Cotton", "Silk", "Freshwater Pearl", "Pearl", "Diamond", "CZ", 
            "Crystal", "Titanium", "Stainless Steel", "Polymer", "Platinum", "Copper"
        ]
        
        # Colors
        self.known_colors = [
            "Gold", "Silver", "Black", "White", "Red", "Blue", "Green", "Yellow", 
            "Pink", "Purple", "Brown", "Orange", "Gray", "Grey", "Emerald Green", 
            "Sapphire Pink", "Rainbow", "Multi-Color", "Dusty Pink", "Clear",
            "Turquoise", "Magenta", "Neon", "Onyx", "Mint", "Lilac", "Light Blue",
            "Navy", "Beige", "Ivory", "Champagne"
        ]
        
        # Product Types
        self.known_product_types = {
            # Jewelry
            'earring': 'Earring',
            'necklace': 'Necklace',
            'bracelet': 'Bracelet',
            'ring': 'Ring',
            'anklet': 'Anklet',
            'choker': 'Choker',
            'pendant': 'Pendant',
            'stud': 'Stud',
            'hoop': 'Hoop',
            'huggie': 'Huggie',
            'chain': 'Chain',
            'charm': 'Charm',
            'bangle': 'Bangle',
            
            # Clothing
            'dress': 'Dress',
            'pants': 'Pants',
            'cardigan': 'Cardigan',
            'shirt': 'Shirt',
            'hat': 'Hat',
            'socks': 'Socks',
            'jacket': 'Jacket',
            'skirt': 'Skirt',
            'leggings': 'Leggings',
            'sweater': 'Sweater',
            'blouse': 'Blouse',
            'top': 'Top'
        }
        
        # Features
        self.known_features = [
            "Pocketed", "Drawstring", "Adjustable", "Beaded", "Chain Link", "CZ Stone",
            "Diamond", "Pearl", "Paperclip", "Drop Chain", "Open Hoop", "Pave", "Threaded",
            "Stretchy", "Buttoned", "Open Front", "Puff", "Engravable", "Personalized",
            "Monogram", "Script", "Bezel", "Toggle", "Box Clasp", "Hinge", "Eternity",
            "Tennis", "Statement", "Stackable", "Layered", "Dainty", "Chunky"
        ]
        
        # Gemstones
        self.known_gemstones = [
            "Diamond", "CZ", "Turquoise", "Onyx", "Pearl", "Emerald", "Sapphire", 
            "Ruby", "Crystal", "Topaz", "Amethyst", "Morganite", "Opal", "Lapis Lazuli",
            "Aquamarine", "Garnet"
        ]
        
        # Fabrics
        self.known_fabrics = [
            "Polyester", "Spandex", "Cotton", "Silk", "Acrylic", "Polymer", "Mesh",
            "Linen", "Wool", "Cashmere", "Nylon", "Satin", "Velvet", "Jersey", "Denim",
            "Twill", "Fleece", "Modal", "Lyocell", "Viscose", "Rayon"
        ]
        
        # Clasp types
        self.known_clasp_types = [
            "Toggle Clasp", "Box Clasp", "Lobster Clasp", "Spring Ring", 
            "Hook Clasp", "Magnetic Clasp", "Barrel Clasp", "S-Hook",
            "Slide Lock", "Fishhook", "Lever Back", "Kidney Wire",
            "Push Back", "Screw Back", "Clip-On", "Post Back"
        ]
        
        # Size patterns for extraction
        self.size_patterns = [
            r'Size: ([XSML\d]+)',
            r'Available In Sizes: ([\d-]+)',
            r'Size\n\n\n([\w/]+)',
            r'(\d+):Bottom Length',
            r'Size: ([\d.]+) MM'
        ]
        
        # Size standardization mappings
        self.standard_clothing_sizes = {
            # Numeric to standard
            "0": "XS",
            "2": "XS",
            "4": "S",
            "6": "S",
            "8": "M",
            "10": "M",
            "12": "L",
            "14": "L",
            "16": "XL",
            "18": "XL",
            "20": "XXL",
            "22": "XXL",
            "24": "XXXL",
            
            # Common variations
            "XXS": "XXS",
            "XS": "XS",
            "S": "S",
            "M": "M",
            "L": "L",
            "XL": "XL",
            "XXL": "XXL",
            "XXXL": "XXXL",
            "1X": "XL",
            "2X": "XXL",
            "3X": "XXXL",
            "SMALL": "S",
            "MEDIUM": "M",
            "LARGE": "L",
            "X-SMALL": "XS",
            "X-LARGE": "XL"
        }
        
        # Ring size standardization
        self.standard_ring_sizes = {str(i): str(i) for i in range(1, 15)}  # Keep numeric sizes as-is
        
        # Measurement patterns
        self.measurement_patterns = {
            'length': r'Length: ([\d.]+)"',
            'size': r'Size: ([\d.]+) MM',
            'bead_size': r'Bead Size: ([\d.]+) MM',
            'pearl_size': r'Pearl Size: ([\d.]+) MM',
            'chain_thickness': r'Chain Thickness: ([\d.]+) MM',
            'drop_chain': r'Drop Chain: ([\d.]+)"',
            'diameter': r'Diameter: ([\d.]+) MM',
            'thickness': r'Thickness: ([\d.]+) MM',
            'pendant_size': r'Pendant Size: ([\d.]+) MM',
            'hoop_size': r'Hoop Size: ([\d.]+) MM',
            'total_weight': r'Total Weight: ([\d.]+) G',
            'carats': r'([\d.]+) Carats'
        }
    
    def connect(self):
        """Connect to Neo4j database"""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info("Successfully connected to Neo4j database")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            return False
    
    def close(self):
        """Close Neo4j connection"""
        if hasattr(self, 'driver') and self.driver:
            self.driver.close()
            logger.info("Closed Neo4j connection")
    
    def load_products(self, file_path):
        """
        Load products from JSON file, handling both JSON Lines and regular JSON formats
        
        Args:
            file_path: Path to the JSON or JSONL file
            
        Returns:
            List of product dictionaries
        """
        products = []
        
        try:
            # Try to open as a regular JSON file first (array of objects)
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    if isinstance(data, list):
                        products = data
                        logger.info(f"Loaded {len(products)} products from JSON array")
                        return products
                except json.JSONDecodeError:
                    # Not a regular JSON file, try JSON Lines format
                    pass
            
            # Try JSON Lines format (one object per line)
            products = []
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line:  # Skip empty lines
                        try:
                            product = json.loads(line)
                            products.append(product)
                        except json.JSONDecodeError as e:
                            logger.warning(f"Error parsing JSON at line {line_num}: {e}")
            
            logger.info(f"Loaded {len(products)} products from JSON Lines format")
            return products
            
        except Exception as e:
            logger.error(f"Failed to load products from {file_path}: {e}")
            return []
    
    def analyze_products(self, products):
        """
        Analyze products to discover relationships and patterns
        
        Args:
            products: List of product dictionaries
        """
        self.start_time = time.time()
        logger.info(f"Analyzing {len(products)} products for relationships...")
        self.total_products = len(products)
        
        # Initialize counters for relationship types
        relationship_types = {
            "categories": Counter(),
            "materials": Counter(),
            "colors": Counter(),
            "product_types": Counter(),
            "features": Counter(),
            "sizes": Counter(),
            "standardized_sizes": Counter(),  # New counter for standardized sizes
            "gemstones": Counter(),
            "fabrics": Counter(),
            "clasp_types": Counter(),
            "dimensions": Counter(),
            "price_ranges": Counter(),
            "inventory_statuses": Counter()
        }
        
        # Track statistics about the dataset
        products_with_categories = 0
        products_with_empty_categories = 0
        products_with_descriptions = 0
        products_with_empty_descriptions = 0
        
        # Process each product
        for idx, product in enumerate(products):
            title = product.get('title', '').strip()
            description = product.get('description', '').strip()
            title_lower = title.lower()
            description_lower = description.lower()
            combined_text = f"{title_lower} {description_lower}"
            
            # Check category and description presence for statistics
            if product.get('category', '').strip():
                products_with_categories += 1
            else:
                products_with_empty_categories += 1
                
            if description:
                products_with_descriptions += 1
            else:
                products_with_empty_descriptions += 1
            
            # Analyze categories
            category = product.get('category', '').strip()
            if category:
                relationship_types["categories"][category] += 1
            else:
                # Try to infer category from title and description
                for keyword, category_name in self.category_mapping.items():
                    if keyword in combined_text:
                        relationship_types["categories"][category_name] += 1
                        break
            
            # Analyze materials
            for material in self.known_materials:
                if material.lower() in combined_text:
                    relationship_types["materials"][material] += 1
            
            # Analyze colors
            for color in self.known_colors:
                if color.lower() in combined_text:
                    relationship_types["colors"][color] += 1
            
            # Analyze product types
            for keyword, type_name in self.known_product_types.items():
                if keyword in combined_text:
                    relationship_types["product_types"][type_name] += 1
            
            # Analyze features
            for feature in self.known_features:
                if feature.lower() in combined_text:
                    relationship_types["features"][feature] += 1
            
            # Analyze sizes and standardize them
            found_sizes = set()
            for pattern in self.size_patterns:
                matches = re.findall(pattern, description)
                for match in matches:
                    size_value = match.strip()
                    if size_value:
                        relationship_types["sizes"][size_value] += 1
                        found_sizes.add(size_value)
            
            # Apply size standardization
            for size in found_sizes:
                # Check if this is a ring product
                is_ring = "ring" in combined_text
                
                # Apply appropriate standardization
                if is_ring and size in self.standard_ring_sizes:
                    std_size = self.standard_ring_sizes[size]
                    relationship_types["standardized_sizes"][f"Ring Size {std_size}"] += 1
                elif size in self.standard_clothing_sizes:
                    std_size = self.standard_clothing_sizes[size]
                    relationship_types["standardized_sizes"][std_size] += 1
                else:
                    # If we can't standardize, use the original
                    relationship_types["standardized_sizes"][size] += 1
            
            # Analyze gemstones
            for gemstone in self.known_gemstones:
                if gemstone.lower() in combined_text:
                    relationship_types["gemstones"][gemstone] += 1
            
            # Analyze fabrics
            for fabric in self.known_fabrics:
                if fabric.lower() in combined_text:
                    relationship_types["fabrics"][fabric] += 1
            
            # Analyze clasp types
            for clasp_type in self.known_clasp_types:
                if clasp_type.lower() in combined_text:
                    relationship_types["clasp_types"][clasp_type] += 1
            
            # Analyze dimensions
            for dim_type, pattern in self.measurement_patterns.items():
                matches = re.findall(pattern, description)
                if matches:
                    relationship_types["dimensions"][dim_type] += 1
            
            # Process price ranges
            price = float(product.get('price', 0)) if product.get('price') != '' else 0
            price_range = self._determine_price_range(price)
            relationship_types["price_ranges"][price_range] += 1
            
            # Process inventory status
            inventory = int(product.get('inventory', 0))
            active = bool(product.get('active', False))
            inventory_status = self._determine_inventory_status(inventory, active)
            relationship_types["inventory_statuses"][inventory_status] += 1
            
            # Log progress
            if (idx + 1) % 1000 == 0:
                elapsed = time.time() - self.start_time
                percent_complete = (idx + 1) / self.total_products * 100
                est_total_time = elapsed / percent_complete * 100
                est_remaining = est_total_time - elapsed
                
                logger.info(f"Analyzed {idx + 1}/{self.total_products} products ({percent_complete:.1f}%) - " +
                           f"Est. remaining: {est_remaining:.0f}s")
        
        # Log dataset statistics
        logger.info(f"Dataset statistics:")
        logger.info(f"- Products with categories: {products_with_categories} ({products_with_categories/self.total_products*100:.1f}%)")
        logger.info(f"- Products with empty categories: {products_with_empty_categories} ({products_with_empty_categories/self.total_products*100:.1f}%)")
        logger.info(f"- Products with descriptions: {products_with_descriptions} ({products_with_descriptions/self.total_products*100:.1f}%)")
        logger.info(f"- Products with empty descriptions: {products_with_empty_descriptions} ({products_with_empty_descriptions/self.total_products*100:.1f}%)")
        
        # Determine which relationships have enough data to be worth creating
        # using percentage-based thresholds
        for rel_type, counter in relationship_types.items():
            # Skip empty counters
            if len(counter) == 0:
                continue
                
            # Calculate percentage coverage
            total_occurrences = sum(counter.values())
            percentage_coverage = total_occurrences / self.total_products * 100
            
            # Adjust thresholds based on relationship type
            # Use lower thresholds for more important relationships
            min_distinct_values = 3
            min_percentage = 1.0  # At least 1% coverage by default
            
            # Adjust thresholds for specific relationship types
            if rel_type in ["categories", "product_types", "price_ranges", "inventory_statuses"]:
                min_percentage = 0.5  # More important relationships
            elif rel_type in ["clasp_types", "gemstones"]:
                min_percentage = 2.0  # Less important relationships
            
            # Check if relationship type meets the thresholds
            has_enough_data = (
                len(counter) >= min_distinct_values and 
                percentage_coverage >= min_percentage
            )
            
            # Always include certain relationship types
            always_include = ["categories", "price_ranges", "inventory_statuses", "standardized_sizes"]
            
            if has_enough_data or rel_type in always_include:
                logger.info(f"Found significant relationship type: {rel_type} with {len(counter)} distinct values ({percentage_coverage:.1f}% coverage)")
                self.found_relationships[rel_type] = counter
                
                # Log top values for each relationship type
                top_values = counter.most_common(5)
                value_info = ", ".join([f"{val}: {count}" for val, count in top_values])
                logger.info(f"  Top values: {value_info}")
        
        # Special case: If we found standardized sizes, remove the original sizes
        if "standardized_sizes" in self.found_relationships and "sizes" in self.found_relationships:
            logger.info("Using standardized sizes instead of raw sizes")
            del self.found_relationships["sizes"]
        
        logger.info(f"Analysis complete. Found {len(self.found_relationships)} significant relationship types")
    
    def clear_database(self):
        """Remove all nodes and relationships from the database"""
        try:
            with self.driver.session() as session:
                # Delete all relationships first
                result = session.run("MATCH ()-[r]-() DELETE r RETURN count(r) as deleted_relationships")
                deleted_rel_count = result.single()["deleted_relationships"]
                
                # Then delete all nodes
                result = session.run("MATCH (n) DELETE n RETURN count(n) as deleted_nodes")
                deleted_node_count = result.single()["deleted_nodes"]
                
                logger.info(f"Cleared database: {deleted_rel_count} relationships and {deleted_node_count} nodes deleted")
                return True
        except Exception as e:
            logger.error(f"Failed to clear database: {e}")
            return False
    
    def create_schema(self):
        """Create constraints and indexes for the discovered schema"""
        try:
            # First check for existing indexes to avoid redundant creation
            existing_indexes = self._get_existing_indexes()
            logger.info(f"Found {len(existing_indexes)} existing indexes")
            
            with self.driver.session() as session:
                # Basic indexes for core nodes
                indexes = [
                    # Product indexes
                    {"name": "product_price", "label": "Product", "property": "price"},
                    {"name": "product_visited_num", "label": "Product", "property": "visited_num"},
                    
                    # Category, Collection, Tag indexes
                    {"name": "category_title", "label": "Category", "property": "title"},
                    {"name": "collection_title", "label": "Collection", "property": "title"},
                    {"name": "tag_title", "label": "Tag", "property": "title"},
                ]
                
                # Add indexes for discovered relationship types
                relationship_indexes = {
                    "materials": {"name": "material_name", "label": "Material", "property": "name"},
                    "colors": {"name": "color_name", "label": "Color", "property": "name"},
                    "product_types": {"name": "product_type_name", "label": "ProductType", "property": "name"},
                    "features": {"name": "feature_name", "label": "Feature", "property": "name"},
                    "sizes": {"name": "size_value", "label": "Size", "property": "value"},
                    "standardized_sizes": {"name": "size_value", "label": "Size", "property": "value"},
                    "gemstones": {"name": "gemstone_name", "label": "Gemstone", "property": "name"},
                    "fabrics": {"name": "fabric_name", "label": "Fabric", "property": "name"},
                    "clasp_types": {"name": "clasp_type_name", "label": "ClaspType", "property": "name"},
                    "dimensions": {"name": "dimension_type", "label": "Dimension", "property": "type"},
                    "price_ranges": {"name": "price_range_name", "label": "PriceRange", "property": "name"},
                    "inventory_statuses": {"name": "status_name", "label": "Status", "property": "name"}
                }
                
                # Add indexes for found relationship types
                for rel_type in self.found_relationships.keys():
                    if rel_type in relationship_indexes:
                        indexes.append(relationship_indexes[rel_type])
                
                # Execute all indexes
                created_count = 0
                for index in indexes:
                    # Check if index already exists
                    index_key = f"{index['label']}.{index['property']}"
                    if index_key not in existing_indexes:
                        try:
                            session.run(
                                f"CREATE INDEX {index['name']} IF NOT EXISTS FOR (n:{index['label']}) ON (n.{index['property']})"
                            )
                            created_count += 1
                        except exceptions.ClientError as e:
                            # Handle syntax differences in older Neo4j versions
                            if "IF NOT EXISTS" in str(e):
                                alt_index = f"CREATE INDEX {index['name']} FOR (n:{index['label']}) ON (n.{index['property']})"
                                try:
                                    session.run(alt_index)
                                    created_count += 1
                                except exceptions.ClientError:
                                    logger.warning(f"Could not create index: {index['name']}")
                            else:
                                logger.warning(f"Could not create index: {index['name']}")
                
                logger.info(f"Created {created_count} new indexes for the schema")
                return True
        except Exception as e:
            logger.error(f"Failed to create schema: {e}")
            return False
    
    def _get_existing_indexes(self):
        """Get a list of existing indexes to avoid recreation"""
        existing_indexes = set()
        try:
            with self.driver.session() as session:
                # Query depends on Neo4j version, try the newer format first
                try:
                    result = session.run("SHOW INDEXES")
                    for record in result:
                        if 'labelsOrTypes' in record and 'properties' in record:
                            for label in record['labelsOrTypes']:
                                for prop in record['properties']:
                                    existing_indexes.add(f"{label}.{prop}")
                except:
                    # Try older format
                    try:
                        result = session.run("CALL db.indexes()")
                        for record in result:
                            if 'tokenNames' in record and 'propertyNames' in record:
                                for label in record['tokenNames']:
                                    for prop in record['propertyNames']:
                                        existing_indexes.add(f"{label}.{prop}")
                    except:
                        logger.warning("Could not retrieve existing indexes, will attempt to create all")
            
            return existing_indexes
        except Exception as e:
            logger.warning(f"Error retrieving existing indexes: {e}")
            return set()
    
    def import_products(self, products):
        """
        Import products and create relationships based on discovered patterns using batch processing
        
        Args:
            products: List of product dictionaries
        """
        self.start_time = time.time()
        logger.info(f"Importing {len(products)} products with discovered relationships using batch size {self.batch_size}...")
        
        # Initialize statistics
        self.stats = {
            "products": 0,
            "categories": 0,
            "collections": 0,
            "tags": 0,
            "materials": 0,
            "colors": 0,
            "product_types": 0,
            "features": 0,
            "sizes": 0,
            "gemstones": 0,
            "fabrics": 0,
            "clasp_types": 0,
            "dimensions": 0,
            "price_ranges": 0,
            "statuses": 0,
            "related_products": 0
        }
        
        # Process products in batches
        for batch_idx in range(0, len(products), self.batch_size):
            batch_end = min(batch_idx + self.batch_size, len(products))
            batch = products[batch_idx:batch_end]
            
            # Process this batch
            self._process_product_batch(batch, batch_idx)
            
            # Log progress
            elapsed = time.time() - self.start_time
            products_processed = batch_end
            percent_complete = products_processed / len(products) * 100
            products_per_second = products_processed / elapsed if elapsed > 0 else 0
            est_total_time = len(products) / products_per_second if products_per_second > 0 else 0
            est_remaining = est_total_time - elapsed
            
            logger.info(f"Imported {products_processed}/{len(products)} products ({percent_complete:.1f}%) - " +
                       f"Rate: {products_per_second:.1f} products/sec - Est. remaining: {est_remaining:.0f}s")
        
        # Create related product relationships
        self._create_related_products()
        
        # Log final statistics
        self._log_statistics()
        
        return True
    
    def _process_product_batch(self, batch, batch_start_idx):
        """Process a batch of products in a single transaction"""
        # Collect operations to perform in this batch
        operations = []
        
        for idx, product in enumerate(batch):
            product_idx = batch_start_idx + idx
            
            try:
                # Process price - handle string values
                if isinstance(product.get('price'), str):
                    try:
                        price = float(product.get('price', 0))
                    except ValueError:
                        price = 0.0
                else:
                    price = float(product.get('price', 0))
                
                # Process images - ensure it's stored as a JSON string
                images = product.get('images', [])
                if isinstance(images, list):
                    images_json = json.dumps(images)
                else:
                    # Already a string
                    images_json = images
                
                # Create product node with exact same structure
                product_id = product.get('id', '')
                if not product_id:
                    # Generate an ID if missing
                    product_id = f"product_{product_idx}"
                
                # Add operation to create product node
                operations.append({
                    "type": "create_product",
                    "product_id": product_id,
                    "product": {
                        'id': product_id,
                        'title': product.get('title', ''),
                        'price': price,
                        'description': product.get('description', ''),
                        'visited_num': product.get('visited_num', 0),
                        'images': images_json,
                        'inventory': product.get('inventory', 0),
                        'active': product.get('active', False)
                    }
                })
                
                # Extract key text for analysis
                title = product.get('title', '').strip()
                description = product.get('description', '').strip()
                title_lower = title.lower()
                description_lower = description.lower()
                combined_text = f"{title_lower} {description_lower}"
                
                # Add operations to create relationships
                self._add_relationship_operations(operations, product, product_id, combined_text, description)
                
            except Exception as e:
                logger.error(f"Failed to prepare product {product.get('id', '')}: {e}")
        
        # Execute all operations in a single transaction
        self._execute_batch_operations(operations)
    
    def _add_relationship_operations(self, operations, product, product_id, combined_text, description):
        """Add operations to create all relationships for a product"""
        # 1. Handle category relationship
        category = product.get('category', '').strip()
        inferred_category = None
        
        if category:
            operations.append({
                "type": "create_relationship",
                "relationship": "IN_CATEGORY",
                "from_id": product_id,
                "to_type": "Category",
                "to_properties": {"title": category}
            })
            self.stats["categories"] += 1
            inferred_category = category
            self.products_by_category[category].append(product_id)
        
        # If no category found, infer from product details
        if not inferred_category and "product_types" in self.found_relationships:
            # Use product types to infer category if possible
            for keyword, category_name in self.category_mapping.items():
                if keyword in combined_text:
                    operations.append({
                        "type": "create_relationship",
                        "relationship": "IN_CATEGORY",
                        "from_id": product_id,
                        "to_type": "Category",
                        "to_properties": {"title": category_name}
                    })
                    self.stats["categories"] += 1
                    inferred_category = category_name
                    self.products_by_category[category_name].append(product_id)
                    break
        
        # 2. Default Collection for all products
        operations.append({
            "type": "create_relationship",
            "relationship": "IN_COLLECTION",
            "from_id": product_id,
            "to_type": "Collection",
            "to_properties": {"title": "All Products"}
        })
        self.stats["collections"] += 1
        
        # 3. Handle brand (both as brand and as tag)
        brand = product.get('brand', '').strip()
        if brand:
            operations.append({
                "type": "create_relationship",
                "relationship": "BY_BRAND",
                "from_id": product_id,
                "to_type": "Brand",
                "to_properties": {"name": brand}
            })
            
            operations.append({
                "type": "create_relationship",
                "relationship": "TAGGED_WITH",
                "from_id": product_id,
                "to_type": "Tag",
                "to_properties": {"title": brand}
            })
            self.stats["tags"] += 1
        
        # 4. Create relationships based on discovered patterns
        # Create ProductType relationship if found
        if "product_types" in self.found_relationships:
            for keyword, type_name in self.known_product_types.items():
                if keyword in combined_text:
                    operations.append({
                        "type": "create_relationship",
                        "relationship": "IS_TYPE",
                        "from_id": product_id,
                        "to_type": "ProductType",
                        "to_properties": {"name": type_name}
                    })
                    self.stats["product_types"] += 1
                    self.products_by_type[type_name].append(product_id)
                    break
        
        # Create Material relationships if found
        if "materials" in self.found_relationships:
            for material in self.known_materials:
                if material.lower() in combined_text:
                    operations.append({
                        "type": "create_relationship",
                        "relationship": "MADE_OF",
                        "from_id": product_id,
                        "to_type": "Material",
                        "to_properties": {"name": material}
                    })
                    self.stats["materials"] += 1
                    self.products_by_material[material].append(product_id)
        
        # Create Color relationships if found
        if "colors" in self.found_relationships:
            for color in self.known_colors:
                if color.lower() in combined_text:
                    operations.append({
                        "type": "create_relationship",
                        "relationship": "HAS_COLOR",
                        "from_id": product_id,
                        "to_type": "Color",
                        "to_properties": {"name": color}
                    })
                    self.stats["colors"] += 1
                    self.products_by_color[color].append(product_id)
        
        # Create Feature relationships if found
        if "features" in self.found_relationships:
            for feature in self.known_features:
                if feature.lower() in combined_text:
                    operations.append({
                        "type": "create_relationship",
                        "relationship": "HAS_FEATURE",
                        "from_id": product_id,
                        "to_type": "Feature",
                        "to_properties": {"name": feature}
                    })
                    self.stats["features"] += 1
        
        # Create Gemstone relationships if found
        if "gemstones" in self.found_relationships:
            for gemstone in self.known_gemstones:
                if gemstone.lower() in combined_text:
                    operations.append({
                        "type": "create_relationship",
                        "relationship": "HAS_GEMSTONE",
                        "from_id": product_id,
                        "to_type": "Gemstone",
                        "to_properties": {"name": gemstone}
                    })
                    self.stats["gemstones"] += 1
        
        # Create Fabric relationships if found
        if "fabrics" in self.found_relationships:
            for fabric in self.known_fabrics:
                if fabric.lower() in combined_text:
                    operations.append({
                        "type": "create_relationship",
                        "relationship": "MADE_WITH_FABRIC",
                        "from_id": product_id,
                        "to_type": "Fabric",
                        "to_properties": {"name": fabric}
                    })
                    self.stats["fabrics"] += 1
        
        # Create ClaspType relationships if found
        if "clasp_types" in self.found_relationships:
            for clasp_type in self.known_clasp_types:
                if clasp_type.lower() in combined_text:
                    operations.append({
                        "type": "create_relationship",
                        "relationship": "HAS_CLASP",
                        "from_id": product_id,
                        "to_type": "ClaspType",
                        "to_properties": {"name": clasp_type}
                    })
                    self.stats["clasp_types"] += 1
        
        # Handle sizes - use standardized sizes if available
        if "standardized_sizes" in self.found_relationships:
            # Extract sizes
            found_sizes = set()
            for pattern in self.size_patterns:
                matches = re.findall(pattern, description)
                for match in matches:
                    size_value = match.strip()
                    if size_value:
                        found_sizes.add(size_value)
            
            # Apply size standardization
            for size in found_sizes:
                # Check if this is a ring product
                is_ring = "ring" in combined_text
                
                # Apply appropriate standardization
                if is_ring and size in self.standard_ring_sizes:
                    std_size = self.standard_ring_sizes[size]
                    final_size = f"Ring Size {std_size}"
                elif size in self.standard_clothing_sizes:
                    std_size = self.standard_clothing_sizes[size]
                    final_size = std_size
                else:
                    # If we can't standardize, use the original
                    final_size = size
                
                operations.append({
                    "type": "create_relationship",
                    "relationship": "AVAILABLE_IN_SIZE",
                    "from_id": product_id,
                    "to_type": "Size",
                    "to_properties": {"value": final_size}
                })
                self.stats["sizes"] += 1
        elif "sizes" in self.found_relationships:
            # Fall back to original sizes if standardization not available
            for pattern in self.size_patterns:
                matches = re.findall(pattern, description)
                for match in matches:
                    size_value = match.strip()
                    if size_value:
                        operations.append({
                            "type": "create_relationship",
                            "relationship": "AVAILABLE_IN_SIZE",
                            "from_id": product_id,
                            "to_type": "Size",
                            "to_properties": {"value": size_value}
                        })
                        self.stats["sizes"] += 1
        
        # Create Dimension relationships if found
        if "dimensions" in self.found_relationships:
            for dim_type, pattern in self.measurement_patterns.items():
                matches = re.findall(pattern, description)
                for match in matches:
                    try:
                        dim_value = float(match)
                        unit = "MM" if "MM" in pattern else "inches"
                        
                        operations.append({
                            "type": "create_relationship",
                            "relationship": "HAS_DIMENSION",
                            "from_id": product_id,
                            "to_type": "Dimension",
                            "to_properties": {
                                "type": dim_type,
                                "value": dim_value,
                                "unit": unit
                            }
                        })
                        self.stats["dimensions"] += 1
                    except (ValueError, IndexError):
                        pass
        
        # 5. Always create price range relationship
        price = float(product.get('price', 0)) if product.get('price') != '' else 0
        price_range = self._determine_price_range(price)
        
        # Find appropriate price range bounds
        price_min = 0
        price_max = 0
        
        if price_range == "Under $50":
            price_min = 0
            price_max = 50
        elif price_range == "$50-$100":
            price_min = 50
            price_max = 100
        elif price_range == "$100-$250":
            price_min = 100
            price_max = 250
        elif price_range == "$250-$500":
            price_min = 250
            price_max = 500
        elif price_range == "$500-$1000":
            price_min = 500
            price_max = 1000
        else:  # $500+
            price_min = 500
            price_max = 1000000
        
        operations.append({
            "type": "create_relationship",
            "relationship": "IN_PRICE_RANGE",
            "from_id": product_id,
            "to_type": "PriceRange",
            "to_properties": {
                "name": price_range,
                "min_price": price_min,
                "max_price": price_max
            }
        })
        
        # Also create collection for backward compatibility
        operations.append({
            "type": "create_relationship",
            "relationship": "IN_COLLECTION",
            "from_id": product_id,
            "to_type": "Collection",
            "to_properties": {"title": price_range}
        })
        self.stats["price_ranges"] += 1
        self.stats["collections"] += 1
        
        # 6. Always create inventory status relationship
        inventory = product.get('inventory', 0)
        active = product.get('active', False)
        
        status_name = self._determine_inventory_status(inventory, active)
        
        operations.append({
            "type": "create_relationship",
            "relationship": "HAS_STATUS",
            "from_id": product_id,
            "to_type": "Status",
            "to_properties": {"name": status_name}
        })
        self.stats["statuses"] += 1
    
    def _execute_batch_operations(self, operations):
        """Execute a batch of operations in a single transaction"""
        if not operations:
            return
                
        try:
            with self.driver.session() as session:
                tx = session.begin_transaction()
                try:
                    # Execute all operations in the transaction
                    for op in operations:
                        if op["type"] == "create_product":
                            tx.run("""
                                CREATE (p:Product {
                                    id: $id,
                                    title: $title,
                                    price: $price,
                                    description: $description,
                                    visited_num: $visited_num,
                                    images: $images,
                                    inventory: $inventory,
                                    active: $active
                                })
                            """, op["product"])
                            self.stats["products"] += 1
                            
                        elif op["type"] == "create_relationship":
                            # Handle different node types with their specific properties
                            to_type = op['to_type']
                            
                            # Build the MERGE clause based on the node type's properties
                            if to_type == "Category":
                                merge_clause = "MERGE (n:Category {title: $title})"
                            elif to_type == "Collection":
                                merge_clause = "MERGE (n:Collection {title: $title})"
                            elif to_type == "Tag":
                                merge_clause = "MERGE (n:Tag {title: $title})"
                            elif to_type == "Brand":
                                merge_clause = "MERGE (n:Brand {name: $name})"
                            elif to_type == "Material":
                                merge_clause = "MERGE (n:Material {name: $name})"
                            elif to_type == "Color":
                                merge_clause = "MERGE (n:Color {name: $name})"
                            elif to_type == "ProductType":
                                merge_clause = "MERGE (n:ProductType {name: $name})"
                            elif to_type == "Feature":
                                merge_clause = "MERGE (n:Feature {name: $name})"
                            elif to_type == "Size":
                                merge_clause = "MERGE (n:Size {value: $value})"
                            elif to_type == "Gemstone":
                                merge_clause = "MERGE (n:Gemstone {name: $name})"
                            elif to_type == "Fabric":
                                merge_clause = "MERGE (n:Fabric {name: $name})"
                            elif to_type == "ClaspType":
                                merge_clause = "MERGE (n:ClaspType {name: $name})"
                            elif to_type == "Dimension":
                                merge_clause = "MERGE (n:Dimension {type: $type, value: $value, unit: $unit})"
                            elif to_type == "PriceRange":
                                merge_clause = "MERGE (n:PriceRange {name: $name, min_price: $min_price, max_price: $max_price})"
                            elif to_type == "Status":
                                merge_clause = "MERGE (n:Status {name: $name})"
                            else:
                                # Default fallback, but this shouldn't happen
                                merge_clause = f"MERGE (n:{to_type} {{id: $id}})"
                            
                            # Execute with the correct merge clause
                            query = f"""
                                MATCH (p:Product {{id: $from_id}})
                                {merge_clause}
                                CREATE (p)-[:{op['relationship']}]->(n)
                            """
                            tx.run(query, {
                                'from_id': op['from_id'],
                                **op['to_properties']  # Unpack the properties
                            })
                    
                    # Commit the transaction
                    tx.commit()
                except Exception as e:
                    tx.rollback()
                    logger.error(f"Transaction failed: {e}")
                    raise
                    
        except Exception as e:
            logger.error(f"Failed to execute batch operations: {e}")
    
    def _determine_price_range(self, price):
        """Determine price range category for a product"""
        if price < 50:
            return "Under $50"
        elif price < 100:
            return "$50-$100"
        elif price < 250:
            return "$100-$250"
        elif price < 500:
            return "$250-$500"
        elif price < 1000:
            return "$500-$1000"
        else:
            return "$500+"
    
    def _determine_inventory_status(self, inventory, active):
        """Determine inventory status for a product"""
        if not active:
            return "Inactive"
        elif inventory <= 0:
            return "Out of Stock"
        elif inventory < 10:
            return "Low Stock"
        else:
            return "In Stock"
    
    def _create_related_products(self):
        """Create RELATED_TO relationships between similar products in batches"""
        logger.info("Creating RELATED_TO relationships between similar products...")
        start_time = time.time()
        
        # Total relationships to create
        total_relationships = 0
        relationships_created = 0
        
        # Create relationships by category
        for category, product_ids in self.products_by_category.items():
            # Skip if fewer than 2 products in category
            if len(product_ids) < 2:
                continue
                
            # For each product, relate to up to 5 other products in same category
            for i, product_id in enumerate(product_ids):
                # Get up to 5 other products from same category
                related_ids = product_ids.copy()
                related_ids.remove(product_id)  # Remove self
                
                # Limit to 5 related products
                related_ids = related_ids[:5]
                
                # Track total relationships
                total_relationships += len(related_ids)
        
        # Create relationships by material
        for material, product_ids in self.products_by_material.items():
            # Skip if fewer than 2 products with material
            if len(product_ids) < 2:
                continue
                
            # For each product, relate to up to 3 other products with same material
            for i, product_id in enumerate(product_ids):
                # Get up to 3 other products from same material
                related_ids = product_ids.copy()
                related_ids.remove(product_id)  # Remove self
                
                # Limit to 3 related products
                related_ids = related_ids[:3]
                
                # Track total relationships
                total_relationships += len(related_ids)
        
        # Create relationships by color
        for color, product_ids in self.products_by_color.items():
            # Skip if fewer than 2 products with color
            if len(product_ids) < 2:
                continue
                
            # For each product, relate to up to 2 other products with same color
            for i, product_id in enumerate(product_ids):
                # Get up to 2 other products from same color
                related_ids = product_ids.copy()
                related_ids.remove(product_id)  # Remove self
                
                # Limit to 2 related products
                related_ids = related_ids[:2]
                
                # Track total relationships
                total_relationships += len(related_ids)
        
        logger.info(f"Planning to create approximately {total_relationships} RELATED_TO relationships")
        
        # Process in batches
        # First by category
        relationships_created += self._create_related_products_batch(
            self.products_by_category, "Same category", 5, "category")
        
        # Then by material
        relationships_created += self._create_related_products_batch(
            self.products_by_material, "Same material", 3, "material")
        
        # Then by color
        relationships_created += self._create_related_products_batch(
            self.products_by_color, "Same color", 2, "color")
        
        elapsed = time.time() - start_time
        logger.info(f"Created {relationships_created} RELATED_TO relationships in {elapsed:.1f} seconds")
        self.stats["related_products"] = relationships_created
    
    def _create_related_products_batch(self, product_groups, reason_prefix, limit, group_type):
        """Create a batch of related product relationships for the given product groups"""
        # Track created relationships
        relationships_created = 0
        relationship_batch = []
        batch_size = 1000  # Process in batches of 1000 relationships
        
        # Create relationships by group
        for group_name, product_ids in product_groups.items():
            # Skip if fewer than 2 products in group
            if len(product_ids) < 2:
                continue
                
            # For each product, relate to up to 'limit' other products in same group
            for product_id in product_ids:
                # Get up to 'limit' other products from same group
                related_ids = product_ids.copy()
                try:
                    related_ids.remove(product_id)  # Remove self
                except ValueError:
                    continue  # Skip if product_id not in list
                
                # Limit to specified number of related products
                related_ids = related_ids[:limit]
                
                # Create relationships
                for related_id in related_ids:
                    relationship_batch.append({
                        "from_id": product_id,
                        "to_id": related_id,
                        "reason": f"{reason_prefix}: {group_name}"
                    })
                    
                    # If batch is full, process it
                    if len(relationship_batch) >= batch_size:
                        created = self._execute_related_batch(relationship_batch)
                        relationships_created += created
                        relationship_batch = []
                        logger.info(f"Created {relationships_created} relationships so far ({group_type})")
        
        # Process any remaining relationships
        if relationship_batch:
            created = self._execute_related_batch(relationship_batch)
            relationships_created += created
        
        return relationships_created
    
    def _execute_related_batch(self, relationship_batch):
        """Execute a batch of related product relationships"""
        if not relationship_batch:
            return 0
            
        created_count = 0
        try:
            with self.driver.session() as session:
                tx = session.begin_transaction()
                try:
                    # Execute all relationships in the transaction
                    for rel in relationship_batch:
                        result = tx.run("""
                            MATCH (p1:Product {id: $id1}), (p2:Product {id: $id2})
                            WHERE NOT (p1)-[:RELATED_TO]->(p2)
                            CREATE (p1)-[:RELATED_TO {reason: $reason}]->(p2)
                            RETURN count(*) as created
                        """, {
                            'id1': rel['from_id'],
                            'id2': rel['to_id'],
                            'reason': rel['reason']
                        })
                        
                        created_count += result.single()["created"]
                    
                    # Commit the transaction
                    tx.commit()
                except Exception as e:
                    tx.rollback()
                    logger.error(f"Transaction failed: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to execute related products batch: {e}")
        
        return created_count
    
    def _log_statistics(self):
        """Log statistics about the imported data"""
        stats_text = f"""
        Import complete:
        - {self.stats["products"]} products
        - {self.stats["categories"]} category relationships
        - {self.stats["collections"]} collection relationships
        - {self.stats["tags"]} tag relationships
        - {self.stats["materials"]} material relationships
        - {self.stats["colors"]} color relationships
        - {self.stats["product_types"]} product type relationships
        - {self.stats["features"]} feature relationships
        - {self.stats["sizes"]} size relationships
        - {self.stats["gemstones"]} gemstone relationships
        - {self.stats["fabrics"]} fabric relationships
        - {self.stats["clasp_types"]} clasp type relationships
        - {self.stats["dimensions"]} dimension relationships
        - {self.stats["price_ranges"]} price range relationships
        - {self.stats["statuses"]} status relationships
        - {self.stats["related_products"]} related product relationships
        """
        
        logger.info(stats_text)
    
    def analyze_database(self):
        """Print statistics about the imported data"""
        try:
            with self.driver.session() as session:
                # Count nodes by label
                result = session.run("MATCH (n) RETURN labels(n) AS label, count(*) AS count")
                print("\nNode counts:")
                for record in result:
                    print(f"  {record['label']}: {record['count']}")
                
                # Count relationships by type
                result = session.run("MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count")
                print("\nRelationship counts:")
                for record in result:
                    print(f"  {record['type']}: {record['count']}")
                
                # Collections
                result = session.run("""
                    MATCH (c:Collection)<-[:IN_COLLECTION]-(p:Product)
                    RETURN c.title AS collection, count(p) AS product_count
                    ORDER BY product_count DESC
                    LIMIT 5
                """)
                print("\nTop collections:")
                for record in result:
                    print(f"  {record['collection']}: {record['product_count']} products")
                
                # Categories
                result = session.run("""
                    MATCH (c:Category)<-[:IN_CATEGORY]-(p:Product)
                    RETURN c.title AS category, count(p) AS product_count
                    ORDER BY product_count DESC
                    LIMIT 5
                """)
                print("\nTop categories:")
                for record in result:
                    print(f"  {record['category']}: {record['product_count']} products")
                
                # Only analyze relationship types that were found during analysis
                if "materials" in self.found_relationships:
                    result = session.run("""
                        MATCH (m:Material)<-[:MADE_OF]-(p:Product)
                        RETURN m.name AS material, count(p) AS product_count
                        ORDER BY product_count DESC
                        LIMIT 5
                    """)
                    print("\nTop materials:")
                    for record in result:
                        print(f"  {record['material']}: {record['product_count']} products")
                
                if "colors" in self.found_relationships:
                    result = session.run("""
                        MATCH (c:Color)<-[:HAS_COLOR]-(p:Product)
                        RETURN c.name AS color, count(p) AS product_count
                        ORDER BY product_count DESC
                        LIMIT 5
                    """)
                    print("\nTop colors:")
                    for record in result:
                        print(f"  {record['color']}: {record['product_count']} products")
                
                if "features" in self.found_relationships:
                    result = session.run("""
                        MATCH (f:Feature)<-[:HAS_FEATURE]-(p:Product)
                        RETURN f.name AS feature, count(p) AS product_count
                        ORDER BY product_count DESC
                        LIMIT 5
                    """)
                    print("\nTop features:")
                    for record in result:
                        print(f"  {record['feature']}: {record['product_count']} products")
                
                if "product_types" in self.found_relationships:
                    result = session.run("""
                        MATCH (pt:ProductType)<-[:IS_TYPE]-(p:Product)
                        RETURN pt.name AS product_type, count(p) AS product_count
                        ORDER BY product_count DESC
                        LIMIT 5
                    """)
                    print("\nProduct types:")
                    for record in result:
                        print(f"  {record['product_type']}: {record['product_count']} products")
                
                # Status is always created
                result = session.run("""
                    MATCH (s:Status)<-[:HAS_STATUS]-(p:Product)
                    RETURN s.name AS status, count(p) AS product_count
                    ORDER BY status
                    LIMIT 5
                """)
                print("\nInventory status:")
                for record in result:
                    print(f"  {record['status']}: {record['product_count']} products")
                
                if "standardized_sizes" in self.found_relationships or "sizes" in self.found_relationships:
                    result = session.run("""
                        MATCH (s:Size)<-[:AVAILABLE_IN_SIZE]-(p:Product)
                        RETURN s.value AS size, count(p) AS product_count
                        ORDER BY size ASC
                        LIMIT 10
                    """)
                    print("\nAvailable sizes:")
                    for record in result:
                        print(f"  Size {record['size']}: {record['product_count']} products")
                
                if "dimensions" in self.found_relationships:
                    result = session.run("""
                        MATCH (d:Dimension)<-[:HAS_DIMENSION]-(p:Product)
                        RETURN d.type AS dimension_type, 
                               round(avg(d.value), 2) AS avg_value,
                               d.unit AS unit,
                               count(p) AS product_count
                        ORDER BY product_count DESC
                        LIMIT 10
                    """)
                    print("\nDimensions:")
                    for record in result:
                        print(f"  {record['dimension_type']}: avg {record['avg_value']} {record['unit']} ({record['product_count']} products)")
                
                # Price ranges are always created
                result = session.run("""
                    MATCH (pr:PriceRange)<-[:IN_PRICE_RANGE]-(p:Product)
                    RETURN pr.name AS price_range, count(p) AS product_count
                    ORDER BY pr.min_price ASC
                    LIMIT 10
                """)
                print("\nPrice ranges:")
                for record in result:
                    print(f"  {record['price_range']}: {record['product_count']} products")
                
                # Related Products
                result = session.run("""
                    MATCH (p:Product)-[r:RELATED_TO]->(p2:Product)
                    RETURN count(r) AS relation_count
                """)
                relation_count = result.single()["relation_count"]
                print(f"\nRelated product connections: {relation_count}")
                
                return True
        except Exception as e:
            logger.error(f"Failed to analyze database: {e}")
            return False

def format_time(seconds):
    """Format time in seconds to a human-readable string"""
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} hours"

def main():
    # Neo4j connection details - MODIFY THESE
    URI = "bolt://34.135.40.119:7687"  # Your Neo4j server URI
    USERNAME = "neo4j"                 # Your username
    PASSWORD = "shopari1234"           # Your password
    BATCH_SIZE = 500                   # Batch size for transactions
    
    # Get file path from command line argument
    if len(sys.argv) < 2:
        print("Usage: python neo4j_analyzer_import.py <path_to_json_file> [--no-clear] [--batch-size=N]")
        return
    
    file_path = sys.argv[1]
    clear_db = "--no-clear" not in sys.argv
    
    # Check for batch size parameter
    for arg in sys.argv:
        if arg.startswith("--batch-size="):
            try:
                BATCH_SIZE = int(arg.split("=")[1])
                if BATCH_SIZE < 1:
                    BATCH_SIZE = 500
            except:
                pass
    
    if not Path(file_path).exists():
        print(f"File not found: {file_path}")
        return
    
    # Create importer
    importer = Neo4jProductImporter(URI, USERNAME, PASSWORD, batch_size=BATCH_SIZE)
    
    try:
        # Start measuring total execution time
        overall_start_time = time.time()
        
        # Connect to Neo4j
        if not importer.connect():
            print("Failed to connect to Neo4j, exiting")
            return
        
        # Load products
        logger.info(f"Loading products from {file_path}")
        products = importer.load_products(file_path)
        
        if not products:
            logger.error("No products loaded, exiting")
            return
        
        # Step 1: Analyze products to discover relationships
        analysis_start = time.time()
        importer.analyze_products(products)
        analysis_time = time.time() - analysis_start
        logger.info(f"Analysis completed in {format_time(analysis_time)}")
        
        # Step 2: Clear database (if not disabled)
        if clear_db:
            clear_start = time.time()
            if not importer.clear_database():
                logger.error("Failed to clear database, exiting")
                return
            clear_time = time.time() - clear_start
            logger.info(f"Database cleared in {format_time(clear_time)}")
        
        # Step 3: Create schema based on discovered relationships
        schema_start = time.time()
        if not importer.create_schema():
            logger.error("Failed to create schema, exiting")
            return
        schema_time = time.time() - schema_start
        logger.info(f"Schema created in {format_time(schema_time)}")
        
        # Step 4: Import products with discovered relationships
        import_start = time.time()
        if not importer.import_products(products):
            logger.error("Failed to import products, exiting")
            return
        import_time = time.time() - import_start
        logger.info(f"Products imported in {format_time(import_time)}")
        
        # Step 5: Analyze the database
        analysis_start = time.time()
        if not importer.analyze_database():
            logger.warning("Failed to analyze database")
        analysis_time = time.time() - analysis_start
        logger.info(f"Database analysis completed in {format_time(analysis_time)}")
        
        # Calculate and log total execution time
        total_time = time.time() - overall_start_time
        logger.info(f"Total execution time: {format_time(total_time)}")
        
        logger.info("Import process completed successfully")
        print("\nDatabase import completed successfully! 🎉")
        print("The database has been rebuilt with dynamically discovered relationships.")
        print(f"Total execution time: {format_time(total_time)}")
        
    except Exception as e:
        logger.error(f"An error occurred during import: {e}")
        print("\nDatabase import failed. Check the log file for details.")
    finally:
        # Close connection
        importer.close()

if __name__ == "__main__":
    main()