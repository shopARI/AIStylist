"""
Neo4j Data-Driven Product Analysis

This script uses purely data-driven approaches to discover product types,
categories, and patterns without any predefined lists or assumptions.
"""

import os
import logging
import sys
import time
import argparse
import json
import re
import numpy as np
from collections import Counter, defaultdict
from typing import Dict, List, Any, Optional, Tuple, Set
from neo4j import GraphDatabase
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("neo4j_data_driven_analysis")

# Download required NLTK data
try:
    nltk.download('stopwords', quiet=True)
    nltk.download('punkt', quiet=True)
    nltk.download('wordnet', quiet=True)
except:
    logger.warning("Could not download NLTK data, using basic text processing")

# Neo4j connection settings
NEO4J_URI = os.environ.get("NEO4J_URL", "bolt://34.135.40.119:7687")
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "shopari1234")

class DataDrivenProductAnalyzer:
    """
    Analyzes products using data-driven methods without predefined categories.
    """
    
    def __init__(self, uri, username, password):
        """Initialize with Neo4j connection details"""
        logger.info(f"Connecting to Neo4j at {uri}")
        self.uri = uri
        self.username = username
        self.password = password
        
        try:
            self.driver = GraphDatabase.driver(uri, auth=(username, password))
            self._verify_connection()
            logger.info("Successfully connected to Neo4j database")
            
            # Initialize text processing tools
            self._init_text_processing()
            
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise ConnectionError(f"Could not connect to Neo4j: {e}")
    
    def _verify_connection(self):
        """Verify the Neo4j connection"""
        with self.driver.session() as session:
            result = session.run("RETURN 1 as test")
            record = result.single()
            if not record or record.get("test") != 1:
                raise ConnectionError("Could not verify Neo4j connection")
    
    def _init_text_processing(self):
        """Initialize text processing tools"""
        try:
            # Extended stopwords including e-commerce specific terms
            self.stop_words = set(stopwords.words('english'))
            self.stop_words.update([
                'new', 'sale', 'free', 'shipping', 'exclusive', 'limited',
                'edition', 'collection', 'premium', 'luxury', 'best', 'top',
                'quality', 'authentic', 'genuine', 'original', 'official'
            ])
            self.lemmatizer = WordNetLemmatizer()
        except:
            # Fallback to basic stopwords if NLTK fails
            self.stop_words = {
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
                'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were',
                'been', 'be', 'have', 'has', 'had', 'do', 'does', 'did'
            }
            self.lemmatizer = None
    
    def close(self):
        """Close the Neo4j connection"""
        if hasattr(self, 'driver') and self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
    
    def query(self, cypher_query, params=None):
        """Execute a Cypher query against Neo4j"""
        try:
            with self.driver.session() as session:
                result = session.run(cypher_query, params or {})
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Neo4j query failed: {e}")
            return []
    
    def extract_product_titles(self, limit=None):
        """Extract all product titles from the database"""
        logger.info("Extracting product titles...")
        
        query = "MATCH (p:Product) WHERE p.title IS NOT NULL RETURN p.title as title"
        if limit:
            query += f" LIMIT {limit}"
        
        results = self.query(query)
        return [r['title'] for r in results]
    
    def tokenize_and_clean(self, text):
        """Tokenize and clean text"""
        # Convert to lowercase
        text = text.lower()
        
        # Remove special characters but keep spaces
        text = re.sub(r'[^a-z0-9\s-]', ' ', text)
        
        # Tokenize
        tokens = text.split()
        
        # Remove stopwords and single characters
        tokens = [t for t in tokens if t not in self.stop_words and len(t) > 1]
        
        # Lemmatize if available
        if self.lemmatizer:
            try:
                tokens = [self.lemmatizer.lemmatize(t) for t in tokens]
            except:
                pass
        
        return tokens
    
    def discover_product_vocabulary(self, sample_size=10000):
        """
        Discover the vocabulary of product types using statistical methods
        
        Returns:
            Dictionary with discovered patterns
        """
        logger.info("Discovering product vocabulary using data-driven methods...")
        
        # Get sample of titles
        titles = self.extract_product_titles(sample_size)
        logger.info(f"Analyzing {len(titles)} product titles...")
        
        # Extract n-grams
        unigrams = Counter()
        bigrams = Counter()
        trigrams = Counter()
        
        for title in titles:
            tokens = self.tokenize_and_clean(title)
            
            # Unigrams
            unigrams.update(tokens)
            
            # Bigrams
            for i in range(len(tokens) - 1):
                bigram = f"{tokens[i]} {tokens[i+1]}"
                bigrams[bigram] += 1
            
            # Trigrams
            for i in range(len(tokens) - 2):
                trigram = f"{tokens[i]} {tokens[i+1]} {tokens[i+2]}"
                trigrams[trigram] += 1
        
        # Find significant terms using TF-IDF
        logger.info("Calculating TF-IDF scores...")
        
        # Prepare documents (titles grouped by first significant word)
        doc_groups = defaultdict(list)
        for title in titles:
            tokens = self.tokenize_and_clean(title)
            if tokens:
                # Group by first significant token
                doc_groups[tokens[0]].append(title)
        
        # Calculate TF-IDF
        documents = [' '.join(group) for group in doc_groups.values() if len(group) > 5]
        
        if documents:
            vectorizer = TfidfVectorizer(max_features=100, ngram_range=(1, 2))
            tfidf_matrix = vectorizer.fit_transform(documents)
            feature_names = vectorizer.get_feature_names_out()
            
            # Get top terms by TF-IDF score
            scores = np.mean(tfidf_matrix.toarray(), axis=0)
            top_indices = np.argsort(scores)[::-1][:50]
            top_tfidf_terms = [(feature_names[i], scores[i]) for i in top_indices]
        else:
            top_tfidf_terms = []
        
        return {
            "vocabulary_stats": {
                "total_titles": len(titles),
                "unique_unigrams": len(unigrams),
                "unique_bigrams": len(bigrams),
                "unique_trigrams": len(trigrams)
            },
            "top_unigrams": unigrams.most_common(50),
            "top_bigrams": bigrams.most_common(30),
            "top_trigrams": trigrams.most_common(20),
            "top_tfidf_terms": top_tfidf_terms
        }
    
    def discover_product_clusters(self, sample_size=5000, n_topics=15):
        """
        Use topic modeling to discover natural product groupings
        
        Returns:
            Dictionary with discovered topics/clusters
        """
        logger.info(f"Discovering product clusters using topic modeling (n_topics={n_topics})...")
        
        # Get titles
        titles = self.extract_product_titles(sample_size)
        
        # Preprocess titles
        processed_titles = []
        for title in titles:
            tokens = self.tokenize_and_clean(title)
            if tokens:
                processed_titles.append(' '.join(tokens))
        
        if not processed_titles:
            return {"error": "No valid titles to process"}
        
        # Create TF-IDF matrix
        vectorizer = TfidfVectorizer(max_features=100, ngram_range=(1, 2))
        doc_term_matrix = vectorizer.fit_transform(processed_titles)
        
        # Apply LDA topic modeling
        lda = LatentDirichletAllocation(
            n_components=n_topics,
            random_state=42,
            max_iter=10
        )
        lda.fit(doc_term_matrix)
        
        # Extract topics
        feature_names = vectorizer.get_feature_names_out()
        topics = []
        
        for topic_idx, topic in enumerate(lda.components_):
            top_indices = np.argsort(topic)[::-1][:10]
            top_terms = [feature_names[i] for i in top_indices]
            top_weights = [topic[i] for i in top_indices]
            
            topics.append({
                "topic_id": topic_idx,
                "terms": list(zip(top_terms, top_weights)),
                "top_terms": top_terms[:5]
            })
        
        return {
            "discovered_topics": topics,
            "n_documents": len(processed_titles),
            "n_features": len(feature_names)
        }
    
    def analyze_co_occurrence_patterns(self, sample_size=5000):
        """
        Analyze which words frequently appear together
        
        Returns:
            Dictionary with co-occurrence patterns
        """
        logger.info("Analyzing word co-occurrence patterns...")
        
        titles = self.extract_product_titles(sample_size)
        
        # Build co-occurrence matrix
        co_occurrence = defaultdict(Counter)
        
        for title in titles:
            tokens = self.tokenize_and_clean(title)
            
            # Count co-occurrences within the same title
            for i, token1 in enumerate(tokens):
                for j, token2 in enumerate(tokens):
                    if i != j:
                        co_occurrence[token1][token2] += 1
        
        # Find strong associations
        associations = []
        
        for word1, partners in co_occurrence.items():
            if len(partners) > 0:
                # Get top co-occurring words
                top_partners = partners.most_common(5)
                total_occurrences = sum(partners.values())
                
                for word2, count in top_partners:
                    # Calculate association strength (simple PMI-like score)
                    if count > 5:  # Minimum threshold
                        associations.append({
                            "word1": word1,
                            "word2": word2,
                            "co_occurrence_count": count,
                            "strength": count / total_occurrences
                        })
        
        # Sort by co-occurrence count
        associations.sort(key=lambda x: x["co_occurrence_count"], reverse=True)
        
        return {
            "top_associations": associations[:50],
            "unique_word_pairs": len(associations)
        }
    
    def identify_product_attributes(self):
        """
        Identify product attributes by analyzing node properties and relationships
        
        Returns:
            Dictionary with discovered attributes
        """
        logger.info("Identifying product attributes from graph structure...")
        
        # Analyze node properties
        property_query = """
        MATCH (p:Product)
        WITH keys(p) as properties
        UNWIND properties as prop
        RETURN prop, count(*) as count
        ORDER BY count DESC
        """
        
        property_results = self.query(property_query)
        
        # Analyze relationships
        relationship_query = """
        MATCH (p:Product)-[r]->()
        RETURN type(r) as rel_type, labels(endNode(r))[0] as target_label, count(*) as count
        ORDER BY count DESC
        """
        
        rel_results = self.query(relationship_query)
        
        # Analyze connected node types
        node_type_query = """
        MATCH (p:Product)-[]->(n)
        WITH labels(n)[0] as node_type, n
        RETURN node_type, count(DISTINCT n) as unique_values, count(*) as total_connections
        ORDER BY total_connections DESC
        """
        
        node_results = self.query(node_type_query)
        
        return {
            "product_properties": property_results,
            "relationship_types": rel_results,
            "connected_node_types": node_results
        }
    
    def generate_dynamic_product_categories(self):
        """
        Generate product categories based on discovered patterns
        
        Returns:
            Dictionary with dynamically generated categories
        """
        logger.info("Generating dynamic product categories based on data patterns...")
        
        # Step 1: Get vocabulary
        vocab = self.discover_product_vocabulary(sample_size=5000)
        
        # Step 2: Get frequent terms that could be product types
        # Focus on nouns that appear frequently
        potential_types = []
        
        for term, count in vocab["top_unigrams"][:100]:
            # Simple heuristic: frequent terms that are likely nouns
            if count > 50 and not term.isdigit():
                potential_types.append((term, count))
        
        # Step 3: For each potential type, count actual products
        categories = []
        
        for term, _ in potential_types[:30]:  # Check top 30
            count_query = """
            MATCH (p:Product)
            WHERE toLower(p.title) CONTAINS $term
            RETURN count(p) as count,
                   avg(p.price) as avg_price,
                   count(DISTINCT p.brand) as unique_brands
            """
            
            result = self.query(count_query, {"term": term})
            
            if result and result[0]["count"] > 100:  # Minimum threshold
                # Get sample products
                sample_query = """
                MATCH (p:Product)
                WHERE toLower(p.title) CONTAINS $term
                RETURN p.title as title
                LIMIT 5
                """
                
                samples = self.query(sample_query, {"term": term})
                
                categories.append({
                    "category": term,
                    "product_count": result[0]["count"],
                    "avg_price": round(result[0]["avg_price"], 2) if result[0]["avg_price"] else None,
                    "unique_brands": result[0]["unique_brands"],
                    "sample_products": [s["title"] for s in samples]
                })
        
        # Sort by product count
        categories.sort(key=lambda x: x["product_count"], reverse=True)
        
        # Step 4: Find category relationships using co-occurrence
        category_relationships = []
        
        for i, cat1 in enumerate(categories[:20]):
            for cat2 in categories[i+1:20]:
                # Check how many products contain both terms
                overlap_query = """
                MATCH (p:Product)
                WHERE toLower(p.title) CONTAINS $term1 
                AND toLower(p.title) CONTAINS $term2
                RETURN count(p) as overlap_count
                """
                
                result = self.query(overlap_query, {
                    "term1": cat1["category"],
                    "term2": cat2["category"]
                })
                
                if result and result[0]["overlap_count"] > 50:
                    category_relationships.append({
                        "category1": cat1["category"],
                        "category2": cat2["category"],
                        "overlap_count": result[0]["overlap_count"]
                    })
        
        return {
            "discovered_categories": categories,
            "category_relationships": category_relationships
        }
    
    def analyze_price_based_segments(self):
        """
        Discover natural price segments using statistical methods
        
        Returns:
            Dictionary with price-based segments
        """
        logger.info("Discovering natural price segments...")
        
        # Get price distribution
        price_query = """
        MATCH (p:Product)
        WHERE p.price IS NOT NULL AND p.price > 0
        RETURN p.price as price
        ORDER BY price
        """
        
        results = self.query(price_query)
        prices = [r["price"] for r in results]
        
        if not prices:
            return {"error": "No price data available"}
        
        # Calculate percentiles
        percentiles = np.percentile(prices, [10, 25, 50, 75, 90, 95, 99])
        
        # Find natural breaks using Jenks optimization (simplified)
        # For now, use percentile-based segmentation
        segments = []
        
        # Define segments based on percentiles
        segment_ranges = [
            (0, percentiles[0], "Budget"),
            (percentiles[0], percentiles[1], "Economy"),
            (percentiles[1], percentiles[2], "Mid-Range"),
            (percentiles[2], percentiles[3], "Premium"),
            (percentiles[3], percentiles[4], "Luxury"),
            (percentiles[4], percentiles[5], "Ultra-Luxury"),
            (percentiles[5], float('inf'), "Super-Premium")
        ]
        
        for start, end, label in segment_ranges:
            # Count products in this segment
            if end == float('inf'):
                count_query = """
                MATCH (p:Product)
                WHERE p.price >= $start
                RETURN count(p) as count,
                       avg(p.price) as avg_price,
                       min(p.price) as min_price,
                       max(p.price) as max_price
                """
                params = {"start": start}
            else:
                count_query = """
                MATCH (p:Product)
                WHERE p.price >= $start AND p.price < $end
                RETURN count(p) as count,
                       avg(p.price) as avg_price,
                       min(p.price) as min_price,
                       max(p.price) as max_price
                """
                params = {"start": start, "end": end}
            
            result = self.query(count_query, params)
            
            if result and result[0]["count"] > 0:
                segments.append({
                    "segment": label,
                    "price_range": f"${start:,.0f} - ${end:,.0f}" if end != float('inf') else f"${start:,.0f}+",
                    "product_count": result[0]["count"],
                    "avg_price": round(result[0]["avg_price"], 2),
                    "min_price": round(result[0]["min_price"], 2),
                    "max_price": round(result[0]["max_price"], 2)
                })
        
        return {
            "price_segments": segments,
            "percentiles": {
                "p10": round(percentiles[0], 2),
                "p25": round(percentiles[1], 2),
                "p50": round(percentiles[2], 2),
                "p75": round(percentiles[3], 2),
                "p90": round(percentiles[4], 2),
                "p95": round(percentiles[5], 2),
                "p99": round(percentiles[6], 2)
            },
            "total_products_with_price": len(prices)
        }
    
    def generate_comprehensive_analysis(self):
        """
        Generate a comprehensive data-driven analysis
        
        Returns:
            Dictionary with all analysis results
        """
        logger.info("Generating comprehensive data-driven analysis...")
        
        start_time = time.time()
        
        analysis = {
            "vocabulary_discovery": self.discover_product_vocabulary(sample_size=10000),
            "product_clusters": self.discover_product_clusters(sample_size=5000, n_topics=15),
            "co_occurrence_patterns": self.analyze_co_occurrence_patterns(sample_size=5000),
            "product_attributes": self.identify_product_attributes(),
            "dynamic_categories": self.generate_dynamic_product_categories(),
            "price_segments": self.analyze_price_based_segments()
        }
        
        # Add metadata
        analysis["metadata"] = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "execution_time": time.time() - start_time,
            "analysis_type": "data-driven",
            "predefined_categories": False
        }
        
        logger.info(f"Analysis completed in {analysis['metadata']['execution_time']:.2f} seconds")
        
        return analysis
    
    def print_analysis_summary(self, analysis):
        """Print a summary of the analysis results"""
        print("\n" + "="*70)
        print(" DATA-DRIVEN PRODUCT ANALYSIS SUMMARY")
        print("="*70)
        
        # Vocabulary stats
        vocab = analysis["vocabulary_discovery"]
        print("\nVOCABULARY DISCOVERY:")
        print(f"  Analyzed titles: {vocab['vocabulary_stats']['total_titles']:,}")
        print(f"  Unique terms: {vocab['vocabulary_stats']['unique_unigrams']:,}")
        print(f"  Unique bigrams: {vocab['vocabulary_stats']['unique_bigrams']:,}")
        
        print("\n  Top 10 Terms (by frequency):")
        for term, count in vocab["top_unigrams"][:10]:
            print(f"    {term}: {count:,}")
        
        # Discovered topics
        clusters = analysis["product_clusters"]
        print("\nDISCOVERED PRODUCT CLUSTERS:")
        if "discovered_topics" in clusters:
            for topic in clusters["discovered_topics"][:5]:
                print(f"  Topic {topic['topic_id']}: {', '.join(topic['top_terms'])}")
        
        # Dynamic categories
        categories = analysis["dynamic_categories"]
        print("\nDYNAMICALLY DISCOVERED CATEGORIES:")
        for cat in categories["discovered_categories"][:15]:
            print(f"  {cat['category'].title()}: {cat['product_count']:,} products (avg ${cat['avg_price']:,.2f})")
        
        # Price segments
        segments = analysis["price_segments"]
        print("\nNATURAL PRICE SEGMENTS:")
        for seg in segments["price_segments"]:
            print(f"  {seg['segment']}: {seg['price_range']} ({seg['product_count']:,} products)")
        
        # Co-occurrence patterns
        patterns = analysis["co_occurrence_patterns"]
        print("\nTOP CO-OCCURRENCE PATTERNS:")
        for assoc in patterns["top_associations"][:10]:
            print(f"  '{assoc['word1']}' + '{assoc['word2']}' ({assoc['co_occurrence_count']} times)")
        
        print("\n" + "="*70)
        print(f"Analysis completed on: {analysis['metadata']['timestamp']}")
        print(f"Execution time: {analysis['metadata']['execution_time']:.2f} seconds")
        print("="*70 + "\n")

def main():
    parser = argparse.ArgumentParser(description='Data-driven product analysis for Neo4j')
    parser.add_argument('--uri', default=NEO4J_URI, help='Neo4j URI')
    parser.add_argument('--username', default=NEO4J_USERNAME, help='Neo4j username')
    parser.add_argument('--password', default=NEO4J_PASSWORD, help='Neo4j password')
    parser.add_argument('--output', default='data_driven_analysis.json', help='Output JSON file')
    
    args = parser.parse_args()
    
    try:
        # Create analyzer
        analyzer = DataDrivenProductAnalyzer(args.uri, args.username, args.password)
        
        # Generate analysis
        analysis = analyzer.generate_comprehensive_analysis()
        
        # Print summary
        analyzer.print_analysis_summary(analysis)
        
        # Save to JSON
        with open(args.output, 'w') as f:
            json.dump(analysis, f, indent=2)
        
        logger.info(f"Analysis saved to {args.output}")
        
        # Close connection
        analyzer.close()
        
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())