"""
Neo4j Database Statistics Generator

This script connects to the Neo4j database and generates comprehensive statistics 
about the product catalog, including distribution by category, collection, tag,
price range, and other attributes.
"""

import os
import logging
import sys
import time
import argparse
import json
import matplotlib.pyplot as plt
from typing import Dict, List, Any, Optional, Tuple
from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("neo4j_database_stats")

# Neo4j connection settings (from environment variables or defaults)
NEO4J_URI = os.environ.get("NEO4J_URL", "bolt://34.135.40.119:7687")
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "shopari1234")

class Neo4jDatabaseStats:
    """
    Analyzes Neo4j database to generate statistics about products, categories,
    brands, and other attributes.
    """
    
    def __init__(self, uri, username, password):
        """
        Initialize with Neo4j connection details
        
        Args:
            uri: Neo4j connection URI
            username: Neo4j username
            password: Neo4j password
        """
        logger.info(f"Connecting to Neo4j at {uri}")
        self.uri = uri
        self.username = username
        self.password = password
        
        try:
            self.driver = GraphDatabase.driver(uri, auth=(username, password))
            # Verify connection
            self._verify_connection()
            logger.info("Successfully connected to Neo4j database")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise ConnectionError(f"Could not connect to Neo4j: {e}")
    
    def _verify_connection(self):
        """Verify the Neo4j connection with a simple query"""
        with self.driver.session() as session:
            result = session.run("RETURN 1 as test")
            record = result.single()
            if not record or record.get("test") != 1:
                raise ConnectionError("Could not verify Neo4j connection")
    
    def close(self):
        """Close the Neo4j connection"""
        if hasattr(self, 'driver') and self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
    
    def query(self, cypher_query, params=None):
        """
        Execute a Cypher query against Neo4j
        
        Args:
            cypher_query: The Cypher query to execute
            params: Query parameters
            
        Returns:
            List of records as dictionaries
        """
        try:
            with self.driver.session() as session:
                result = session.run(cypher_query, params or {})
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Neo4j query failed: {e}")
            logger.error(f"Query: {cypher_query}")
            return []
    
    def get_basic_counts(self):
        """
        Get basic counts of products, categories, collections, and tags
        
        Returns:
            Dictionary with basic counts
        """
        logger.info("Getting basic counts...")
        
        counts = {}
        
        # Count Products
        product_count_query = "MATCH (p:Product) RETURN count(p) as count"
        result = self.query(product_count_query)
        counts["product_count"] = result[0]["count"] if result else 0
        
        # Count Categories
        category_count_query = "MATCH (c:Category) RETURN count(c) as count"
        result = self.query(category_count_query)
        counts["category_count"] = result[0]["count"] if result else 0
        
        # Count Collections
        collection_count_query = "MATCH (c:Collection) RETURN count(c) as count"
        result = self.query(collection_count_query)
        counts["collection_count"] = result[0]["count"] if result else 0
        
        # Count Tags
        tag_count_query = "MATCH (t:Tag) RETURN count(t) as count"
        result = self.query(tag_count_query)
        counts["tag_count"] = result[0]["count"] if result else 0
        
        return counts
    
    def get_category_distribution(self):
        """
        Get distribution of products by category
        
        Returns:
            Dictionary with category names and product counts
        """
        logger.info("Getting category distribution...")
        
        query = """
        MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
        RETURN c.title as category, count(p) as product_count
        ORDER BY product_count DESC
        """
        
        result = self.query(query)
        
        # Calculate total product count in categories
        total = sum(record["product_count"] for record in result)
        
        # Add percentage to each record
        distribution = []
        for record in result:
            percentage = (record["product_count"] / total * 100) if total > 0 else 0
            distribution.append({
                "category": record["category"],
                "product_count": record["product_count"],
                "percentage": round(percentage, 2)
            })
        
        return distribution
    
    def get_collection_distribution(self):
        """
        Get distribution of products by collection
        
        Returns:
            Dictionary with collection names and product counts
        """
        logger.info("Getting collection distribution...")
        
        query = """
        MATCH (p:Product)-[:IN_COLLECTION]->(c:Collection)
        RETURN c.title as collection, count(p) as product_count
        ORDER BY product_count DESC
        """
        
        result = self.query(query)
        
        # Calculate total product count in collections
        total = sum(record["product_count"] for record in result)
        
        # Add percentage to each record
        distribution = []
        for record in result:
            percentage = (record["product_count"] / total * 100) if total > 0 else 0
            distribution.append({
                "collection": record["collection"],
                "product_count": record["product_count"],
                "percentage": round(percentage, 2)
            })
        
        return distribution
    
    def get_tag_distribution(self):
        """
        Get distribution of products by tag
        
        Returns:
            Dictionary with tag names and product counts
        """
        logger.info("Getting tag distribution...")
        
        query = """
        MATCH (p:Product)-[:TAGGED_WITH]->(t:Tag)
        RETURN t.title as tag, count(p) as product_count
        ORDER BY product_count DESC
        """
        
        result = self.query(query)
        
        # Calculate total product count with tags
        total = sum(record["product_count"] for record in result)
        
        # Add percentage to each record
        distribution = []
        for record in result:
            percentage = (record["product_count"] / total * 100) if total > 0 else 0
            distribution.append({
                "tag": record["tag"],
                "product_count": record["product_count"],
                "percentage": round(percentage, 2)
            })
        
        return distribution
    
    def get_price_distribution(self):
        """
        Get distribution of products by price range
        
        Returns:
            Dictionary with price ranges and product counts
        """
        logger.info("Getting price distribution...")
        
        query = """
        MATCH (p:Product)
        WHERE p.price IS NOT NULL
        RETURN 
            CASE
                WHEN p.price < 50 THEN 'Under $50'
                WHEN p.price >= 50 AND p.price < 100 THEN '$50-$100'
                WHEN p.price >= 100 AND p.price < 250 THEN '$100-$250'
                WHEN p.price >= 250 AND p.price < 500 THEN '$250-$500'
                WHEN p.price >= 500 AND p.price < 1000 THEN '$500-$1000'
                ELSE '$1000+'
            END as price_range,
            count(p) as product_count
        ORDER BY 
            CASE price_range
                WHEN 'Under $50' THEN 0
                WHEN '$50-$100' THEN 1
                WHEN '$100-$250' THEN 2
                WHEN '$250-$500' THEN 3
                WHEN '$500-$1000' THEN 4
                ELSE 5
            END
        """
        
        result = self.query(query)
        
        # Calculate total product count with prices
        total = sum(record["product_count"] for record in result)
        
        # Add percentage to each record
        distribution = []
        for record in result:
            percentage = (record["product_count"] / total * 100) if total > 0 else 0
            distribution.append({
                "price_range": record["price_range"],
                "product_count": record["product_count"],
                "percentage": round(percentage, 2)
            })
        
        return distribution
    
    def get_brand_distribution(self):
        """
        Get distribution of products by brand (using tags)
        
        Returns:
            Dictionary with brand names and product counts
        """
        logger.info("Getting brand distribution...")
        
        # Since brands might be represented as tags, we'll query for potential brand tags
        # This is a heuristic approach as brands are commonly represented as proper nouns
        query = """
        MATCH (p:Product)-[:TAGGED_WITH]->(t:Tag)
        WHERE t.title =~ '.*[A-Z].*' AND NOT t.title =~ '(in|of|the|and|with|for|by|as|on|at).*'
        AND length(t.title) > 2
        RETURN t.title as brand, count(p) as product_count
        ORDER BY product_count DESC
        LIMIT 20
        """
        
        result = self.query(query)
        
        # Calculate total product count for these brands
        total = sum(record["product_count"] for record in result)
        
        # Add percentage to each record
        distribution = []
        for record in result:
            percentage = (record["product_count"] / total * 100) if total > 0 else 0
            distribution.append({
                "brand": record["brand"],
                "product_count": record["product_count"],
                "percentage": round(percentage, 2)
            })
        
        return distribution
    
    def get_product_type_distribution(self):
        """
        Get distribution of products by product type (extracted from titles and categories)
        
        Returns:
            Dictionary with product types and counts
        """
        logger.info("Getting product type distribution...")
        
        # Define common product types to search for
        product_types = [
            # Jewelry types
            "Earrings", "Necklace", "Bracelet", "Ring", "Anklet", "Choker", "Pendant", 
            "Studs", "Hoops", "Huggies", "Chain", "Charm", "Bangle",
            
            # Clothing types
            "Dress", "Shirt", "Pants", "Jeans", "Skirt", "Blouse", "Sweater", "Jacket", 
            "Coat", "Suit", "Blazer", "T-shirt", "Hoodie", "Shorts", "Swimwear", "Top",
            
            # Accessories
            "Hat", "Scarf", "Watch", "Sunglasses", "Shoes", "Boots", "Sneakers"
        ]
        
        # Build a query to count products by type
        query_parts = []
        
        for product_type in product_types:
            # Look for type in title, category, or tag
            query_part = f"""
            OPTIONAL MATCH (p:Product)
            WHERE toLower(p.title) CONTAINS toLower('{product_type}')
            OR (p)-[:IN_CATEGORY]->(:Category) WHERE toLower(Category.title) CONTAINS toLower('{product_type}')
            OR (p)-[:TAGGED_WITH]->(:Tag) WHERE toLower(Tag.title) CONTAINS toLower('{product_type}')
            WITH count(DISTINCT p) as {product_type.replace('-', '_').replace(' ', '_')}_count
            """
            query_parts.append(query_part)
        
        # Combine all query parts and return results
        full_query = "\n".join(query_parts)
        full_query += "\nRETURN " + ", ".join([f"{product_type.replace('-', '_').replace(' ', '_')}_count as {product_type.replace('-', '_').replace(' ', '_')}" for product_type in product_types])
        
        try:
            # If the query is too complex, we'll use a simpler approach
            # Query for products with type in title
            distribution = []
            total_count = 0
            
            for product_type in product_types:
                query = f"""
                MATCH (p:Product)
                WHERE toLower(p.title) CONTAINS toLower('{product_type}')
                RETURN count(p) as product_count
                """
                
                result = self.query(query)
                count = result[0]["product_count"] if result else 0
                total_count += count
                
                distribution.append({
                    "product_type": product_type,
                    "product_count": count
                })
            
            # Sort by count in descending order
            distribution.sort(key=lambda x: x["product_count"], reverse=True)
            
            # Add percentage to each record
            for item in distribution:
                percentage = (item["product_count"] / total_count * 100) if total_count > 0 else 0
                item["percentage"] = round(percentage, 2)
            
            # Filter out zero counts
            distribution = [item for item in distribution if item["product_count"] > 0]
            
            return distribution
        except Exception as e:
            logger.error(f"Error getting product type distribution: {e}")
            return []
    
    def generate_all_stats(self):
        """
        Generate all statistics about the database
        
        Returns:
            Dictionary with all statistics
        """
        logger.info("Generating all database statistics...")
        
        start_time = time.time()
        
        stats = {
            "basic_counts": self.get_basic_counts(),
            "category_distribution": self.get_category_distribution(),
            "collection_distribution": self.get_collection_distribution(),
            "tag_distribution": self.get_tag_distribution(),
            "price_distribution": self.get_price_distribution(),
            "brand_distribution": self.get_brand_distribution(),
            "product_type_distribution": self.get_product_type_distribution()
        }
        
        # Add timestamp and execution time
        stats["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
        stats["execution_time"] = time.time() - start_time
        
        logger.info(f"Statistics generated in {stats['execution_time']:.2f} seconds")
        
        return stats
    
    def print_stats_summary(self, stats):
        """
        Print a summary of the statistics to the console
        
        Args:
            stats: Dictionary with all statistics
        """
        print("\n" + "="*50)
        print(" DATABASE STATISTICS SUMMARY")
        print("="*50)
        
        # Basic counts
        print("\nBASIC COUNTS:")
        print(f"Total Products: {stats['basic_counts'].get('product_count', 0)}")
        print(f"Total Categories: {stats['basic_counts'].get('category_count', 0)}")
        print(f"Total Collections: {stats['basic_counts'].get('collection_count', 0)}")
        print(f"Total Tags: {stats['basic_counts'].get('tag_count', 0)}")
        
        # Category distribution
        print("\nCATEGORY DISTRIBUTION (Top 10):")
        for item in stats["category_distribution"][:10]:
            print(f"  {item['category']}: {item['product_count']} products ({item['percentage']}%)")
        
        # Collection distribution
        print("\nCOLLECTION DISTRIBUTION (Top 10):")
        for item in stats["collection_distribution"][:10]:
            print(f"  {item['collection']}: {item['product_count']} products ({item['percentage']}%)")
        
        # Tag distribution
        print("\nTAG DISTRIBUTION (Top 10):")
        for item in stats["tag_distribution"][:10]:
            print(f"  {item['tag']}: {item['product_count']} products ({item['percentage']}%)")
        
        # Price distribution
        print("\nPRICE DISTRIBUTION:")
        for item in stats["price_distribution"]:
            print(f"  {item['price_range']}: {item['product_count']} products ({item['percentage']}%)")
        
        # Brand distribution
        print("\nBRAND DISTRIBUTION (Top 10):")
        for item in stats["brand_distribution"][:10]:
            print(f"  {item['brand']}: {item['product_count']} products ({item['percentage']}%)")
        
        # Product type distribution
        print("\nPRODUCT TYPE DISTRIBUTION (Top 10):")
        for item in stats["product_type_distribution"][:10]:
            print(f"  {item['product_type']}: {item['product_count']} products ({item['percentage']}%)")
        
        print("\n" + "="*50)
        print(f"Statistics generated on: {stats['timestamp']}")
        print(f"Execution time: {stats['execution_time']:.2f} seconds")
        print("="*50 + "\n")
    
    def generate_visualizations(self, stats, output_dir="stats_visualizations"):
        """
        Generate visualizations of the statistics
        
        Args:
            stats: Dictionary with all statistics
            output_dir: Directory to save the visualizations
        """
        try:
            import matplotlib.pyplot as plt
            import numpy as np
            import os
            
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Set style
            plt.style.use('ggplot')
            
            # 1. Category Distribution Pie Chart
            if stats["category_distribution"]:
                plt.figure(figsize=(12, 8))
                
                # Get top categories (limit to 8 for readability)
                top_categories = stats["category_distribution"][:8]
                
                # Add "Other" category for the rest
                other_percent = sum(item["percentage"] for item in stats["category_distribution"][8:])
                if other_percent > 0:
                    top_categories.append({
                        "category": "Other",
                        "percentage": other_percent
                    })
                
                labels = [item["category"] for item in top_categories]
                sizes = [item["percentage"] for item in top_categories]
                
                plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, shadow=True)
                plt.axis('equal')
                plt.title('Product Distribution by Category')
                plt.tight_layout()
                plt.savefig(os.path.join(output_dir, 'category_distribution.png'))
                plt.close()
            
            # 2. Price Range Bar Chart
            if stats["price_distribution"]:
                plt.figure(figsize=(12, 8))
                
                labels = [item["price_range"] for item in stats["price_distribution"]]
                counts = [item["product_count"] for item in stats["price_distribution"]]
                
                plt.bar(labels, counts, color='skyblue')
                plt.xlabel('Price Range')
                plt.ylabel('Number of Products')
                plt.title('Product Distribution by Price Range')
                plt.xticks(rotation=45)
                plt.tight_layout()
                plt.savefig(os.path.join(output_dir, 'price_distribution.png'))
                plt.close()
            
            # 3. Product Type Distribution (Top 10)
            if stats["product_type_distribution"]:
                plt.figure(figsize=(12, 8))
                
                # Get top product types
                top_types = stats["product_type_distribution"][:10]
                
                labels = [item["product_type"] for item in top_types]
                counts = [item["product_count"] for item in top_types]
                
                # Sort by count for better visualization
                sorted_indices = np.argsort(counts)
                labels = [labels[i] for i in sorted_indices]
                counts = [counts[i] for i in sorted_indices]
                
                plt.barh(labels, counts, color='lightgreen')
                plt.xlabel('Number of Products')
                plt.ylabel('Product Type')
                plt.title('Top 10 Product Types')
                plt.tight_layout()
                plt.savefig(os.path.join(output_dir, 'product_type_distribution.png'))
                plt.close()
            
            # 4. Brand Distribution (Top 10)
            if stats["brand_distribution"]:
                plt.figure(figsize=(12, 8))
                
                # Get top brands
                top_brands = stats["brand_distribution"][:10]
                
                labels = [item["brand"] for item in top_brands]
                percentages = [item["percentage"] for item in top_brands]
                
                # Sort by percentage for better visualization
                sorted_indices = np.argsort(percentages)
                labels = [labels[i] for i in sorted_indices]
                percentages = [percentages[i] for i in sorted_indices]
                
                plt.barh(labels, percentages, color='salmon')
                plt.xlabel('Percentage of Products')
                plt.ylabel('Brand')
                plt.title('Top 10 Brands (% of Products)')
                plt.tight_layout()
                plt.savefig(os.path.join(output_dir, 'brand_distribution.png'))
                plt.close()
            
            logger.info(f"Visualizations saved to {output_dir}")
        except Exception as e:
            logger.error(f"Error generating visualizations: {e}")

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Generate Neo4j database statistics')
    parser.add_argument('--uri', default=NEO4J_URI, help='Neo4j URI')
    parser.add_argument('--username', default=NEO4J_USERNAME, help='Neo4j username')
    parser.add_argument('--password', default=NEO4J_PASSWORD, help='Neo4j password')
    parser.add_argument('--output', default='database_stats.json', help='Output JSON file')
    parser.add_argument('--visualize', action='store_true', help='Generate visualizations')
    parser.add_argument('--vis-dir', default='stats_visualizations', help='Directory for visualizations')
    
    args = parser.parse_args()
    
    try:
        # Create the stats generator
        stats_generator = Neo4jDatabaseStats(args.uri, args.username, args.password)
        
        # Generate all statistics
        stats = stats_generator.generate_all_stats()
        
        # Print summary to console
        stats_generator.print_stats_summary(stats)
        
        # Save to JSON file
        with open(args.output, 'w') as f:
            json.dump(stats, f, indent=2)
        
        logger.info(f"Statistics saved to {args.output}")
        
        # Generate visualizations if requested
        if args.visualize:
            stats_generator.generate_visualizations(stats, args.vis_dir)
        
        # Close the connection
        stats_generator.close()
        
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())