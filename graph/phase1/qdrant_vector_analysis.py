#!/usr/bin/env python3
"""
Qdrant Vector Analysis
Analyzes vector patterns, clustering, and quality in Qdrant database

READ-ONLY: Only reads vector data for analysis
"""

import json
import os
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import Counter, defaultdict
from qdrant_client import QdrantClient
from qdrant_client.http import models

class QdrantVectorAnalyzer:
    """Analyzes Qdrant vector database patterns and clustering"""
    
    def __init__(self):
        self.output_dir = f"qdrant_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Qdrant connection details from .env
        self.qdrant_url = "https://9ac8ffa1-c5b7-47e2-a832-3ce559f42042.us-east4-0.gcp.cloud.qdrant.io"
        self.qdrant_api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.zz1R7TKuAT4A0dX-M-oZbgX9sYT-x6bwT1EMPGKZ6Jg"
        self.collection_name = "fashion_products"
    
    def connect_to_qdrant(self) -> Optional[QdrantClient]:
        """Connect to Qdrant cloud instance"""
        try:
            client = QdrantClient(
                url=self.qdrant_url,
                api_key=self.qdrant_api_key
            )
            # Test connection
            collections = client.get_collections()
            print(f"✅ Connected to Qdrant - Found {len(collections.collections)} collections")
            return client
        except Exception as e:
            print(f"❌ Failed to connect to Qdrant: {e}")
            return None
    
    def analyze_collection_info(self, client: QdrantClient) -> Dict:
        """Analyze basic collection information"""
        print("🔍 Analyzing collection information...")
        
        try:
            # Get collection info
            collection_info = client.get_collection(self.collection_name)
            
            # Get collection statistics
            count_result = client.count(collection_name=self.collection_name)
            
            info = {
                'collection_name': self.collection_name,
                'total_vectors': count_result.count,
                'vector_size': collection_info.config.params.vectors.size,
                'distance_metric': collection_info.config.params.vectors.distance.value,
                'status': collection_info.status.value,
                'optimizer_status': collection_info.optimizer_status,
                'indexed_vectors': collection_info.vectors_count or 0,
                'points_count': collection_info.points_count or 0
            }
            
            print(f"📊 Collection: {info['collection_name']}")
            print(f"📊 Total Vectors: {info['total_vectors']:,}")
            print(f"📊 Vector Dimension: {info['vector_size']}")
            print(f"📊 Distance Metric: {info['distance_metric']}")
            
            return info
            
        except Exception as e:
            print(f"❌ Error analyzing collection info: {e}")
            return {}
    
    def analyze_vector_sample(self, client: QdrantClient, sample_size: int = 1000) -> Dict:
        """Analyze a sample of vectors for patterns"""
        print(f"🔍 Analyzing vector sample ({sample_size:,} vectors)...")
        
        try:
            # Scroll through vectors to get sample
            vectors_sample = []
            metadata_sample = []
            
            scroll_result = client.scroll(
                collection_name=self.collection_name,
                limit=sample_size,
                with_vectors=True,
                with_payload=True
            )
            
            points = scroll_result[0]  # Get points from scroll result
            
            for point in points:
                if point.vector is not None:
                    vectors_sample.append(np.array(point.vector))
                    metadata_sample.append(point.payload or {})
            
            if not vectors_sample:
                print("❌ No vectors found in sample")
                return {}
            
            vectors_array = np.array(vectors_sample)
            
            # Calculate vector statistics
            vector_stats = {
                'sample_size': len(vectors_sample),
                'vector_dimension': vectors_array.shape[1],
                'mean_vector': np.mean(vectors_array, axis=0),
                'std_vector': np.std(vectors_array, axis=0),
                'vector_norms': [np.linalg.norm(v) for v in vectors_array],
                'metadata_keys': set()
            }
            
            # Analyze metadata patterns
            for metadata in metadata_sample:
                vector_stats['metadata_keys'].update(metadata.keys())
            
            # Convert sets to lists for JSON serialization
            vector_stats['metadata_keys'] = list(vector_stats['metadata_keys'])
            
            # Statistical summaries
            norms = vector_stats['vector_norms']
            vector_stats['norm_stats'] = {
                'mean_norm': float(np.mean(norms)),
                'std_norm': float(np.std(norms)),
                'min_norm': float(np.min(norms)),
                'max_norm': float(np.max(norms))
            }
            
            print(f"📊 Sample size: {vector_stats['sample_size']:,}")
            print(f"📊 Vector dimension: {vector_stats['vector_dimension']}")
            print(f"📊 Average norm: {vector_stats['norm_stats']['mean_norm']:.3f}")
            print(f"📊 Metadata keys: {len(vector_stats['metadata_keys'])}")
            
            return vector_stats
            
        except Exception as e:
            print(f"❌ Error analyzing vector sample: {e}")
            return {}
    
    def analyze_metadata_patterns(self, client: QdrantClient, sample_size: int = 2000) -> Dict:
        """Analyze metadata patterns and quality"""
        print(f"🔍 Analyzing metadata patterns ({sample_size:,} records)...")
        
        try:
            # Scroll through records to analyze metadata
            metadata_analysis = {
                'total_analyzed': 0,
                'field_frequency': Counter(),
                'field_types': defaultdict(Counter),
                'missing_fields': Counter(),
                'sample_values': defaultdict(list)
            }
            
            scroll_result = client.scroll(
                collection_name=self.collection_name,
                limit=sample_size,
                with_payload=True,
                with_vectors=False  # Don't need vectors for metadata analysis
            )
            
            points = scroll_result[0]
            
            expected_fields = ['title', 'description', 'price', 'product_id']
            
            for point in points:
                metadata_analysis['total_analyzed'] += 1
                payload = point.payload or {}
                
                # Track field frequency
                for field in expected_fields:
                    if field in payload:
                        metadata_analysis['field_frequency'][field] += 1
                        # Track field types
                        value_type = type(payload[field]).__name__
                        metadata_analysis['field_types'][field][value_type] += 1
                        
                        # Sample values (first 5)
                        if len(metadata_analysis['sample_values'][field]) < 5:
                            metadata_analysis['sample_values'][field].append(payload[field])
                    else:
                        metadata_analysis['missing_fields'][field] += 1
                
                # Track all fields present
                for field in payload.keys():
                    if field not in expected_fields:
                        metadata_analysis['field_frequency'][field] += 1
            
            # Convert to regular dicts for JSON serialization
            metadata_analysis['field_frequency'] = dict(metadata_analysis['field_frequency'])
            metadata_analysis['field_types'] = {k: dict(v) for k, v in metadata_analysis['field_types'].items()}
            metadata_analysis['missing_fields'] = dict(metadata_analysis['missing_fields'])
            metadata_analysis['sample_values'] = dict(metadata_analysis['sample_values'])
            
            print(f"📊 Analyzed {metadata_analysis['total_analyzed']:,} records")
            print("📊 Field coverage:")
            total = metadata_analysis['total_analyzed']
            for field in expected_fields:
                present = metadata_analysis['field_frequency'].get(field, 0)
                coverage = (present / total) * 100 if total > 0 else 0
                print(f"  {field}: {present:,}/{total:,} ({coverage:.1f}%)")
            
            return metadata_analysis
            
        except Exception as e:
            print(f"❌ Error analyzing metadata patterns: {e}")
            return {}
    
    def analyze_vector_clustering(self, client: QdrantClient, sample_size: int = 500) -> Dict:
        """Analyze vector clustering patterns using simple sampling"""
        print(f"🔍 Analyzing vector clustering patterns ({sample_size:,} vectors)...")
        
        try:
            # Get sample vectors
            scroll_result = client.scroll(
                collection_name=self.collection_name,
                limit=sample_size,
                with_vectors=True,
                with_payload=True
            )
            
            points = scroll_result[0]
            
            if len(points) < 10:
                print("❌ Insufficient vectors for clustering analysis")
                return {}
            
            # Extract vectors and metadata
            vectors = []
            titles = []
            
            for point in points:
                if point.vector is not None:
                    vectors.append(np.array(point.vector))
                    payload = point.payload or {}
                    titles.append(payload.get('title', 'Unknown'))
            
            vectors_array = np.array(vectors)
            
            # Simple clustering analysis using pairwise distances
            n_sample = min(100, len(vectors))  # Sample for distance analysis
            sample_indices = np.random.choice(len(vectors), n_sample, replace=False)
            sample_vectors = vectors_array[sample_indices]
            
            # Calculate pairwise distances
            from scipy.spatial.distance import pdist, squareform
            distances = pdist(sample_vectors, metric='cosine')
            distance_matrix = squareform(distances)
            
            # Analyze distance distribution
            cluster_analysis = {
                'sample_size': n_sample,
                'distance_stats': {
                    'mean_distance': float(np.mean(distances)),
                    'std_distance': float(np.std(distances)),
                    'min_distance': float(np.min(distances)),
                    'max_distance': float(np.max(distances)),
                    'median_distance': float(np.median(distances))
                },
                'similarity_clusters': [],
                'outlier_detection': {}
            }
            
            # Find highly similar pairs (low cosine distance)
            similar_threshold = np.percentile(distances, 10)  # Bottom 10% distances
            similar_pairs = np.where(distance_matrix < similar_threshold)
            
            # Analyze similar products
            similar_products = []
            for i, j in zip(similar_pairs[0], similar_pairs[1]):
                if i < j:  # Avoid duplicates
                    title1 = titles[sample_indices[i]]
                    title2 = titles[sample_indices[j]]
                    distance = distance_matrix[i, j]
                    similar_products.append({
                        'product1': title1[:50] + '...' if len(title1) > 50 else title1,
                        'product2': title2[:50] + '...' if len(title2) > 50 else title2,
                        'similarity': 1 - distance  # Convert distance to similarity
                    })
            
            cluster_analysis['similar_products'] = sorted(
                similar_products, 
                key=lambda x: x['similarity'], 
                reverse=True
            )[:10]
            
            print(f"📊 Distance stats: mean={cluster_analysis['distance_stats']['mean_distance']:.3f}")
            print(f"📊 Found {len(similar_products)} highly similar pairs")
            
            return cluster_analysis
            
        except Exception as e:
            print(f"❌ Error analyzing clustering: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def create_analysis_report(self, collection_info: Dict, vector_stats: Dict, 
                              metadata_analysis: Dict, cluster_analysis: Dict) -> str:
        """Generate comprehensive Qdrant analysis report"""
        
        report_lines = [
            "# Qdrant Vector Database Analysis Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Executive Summary",
            f"📊 **Collection**: {collection_info.get('collection_name', 'Unknown')}",
            f"📊 **Total Vectors**: {collection_info.get('total_vectors', 0):,}",
            f"📊 **Vector Dimension**: {collection_info.get('vector_size', 0)}",
            f"📊 **Distance Metric**: {collection_info.get('distance_metric', 'Unknown')}",
            "",
            "## Vector Analysis",
            f"### Sample Statistics ({vector_stats.get('sample_size', 0):,} vectors)",
            f"- **Mean Vector Norm**: {vector_stats.get('norm_stats', {}).get('mean_norm', 0):.3f}",
            f"- **Std Vector Norm**: {vector_stats.get('norm_stats', {}).get('std_norm', 0):.3f}",
            f"- **Min Vector Norm**: {vector_stats.get('norm_stats', {}).get('min_norm', 0):.3f}",
            f"- **Max Vector Norm**: {vector_stats.get('norm_stats', {}).get('max_norm', 0):.3f}",
            "",
            "## Metadata Quality Analysis",
            f"### Field Coverage ({metadata_analysis.get('total_analyzed', 0):,} records)",
        ]
        
        # Metadata coverage table
        total_analyzed = metadata_analysis.get('total_analyzed', 1)
        field_freq = metadata_analysis.get('field_frequency', {})
        
        for field, count in field_freq.items():
            coverage = (count / total_analyzed) * 100
            report_lines.append(f"- **{field}**: {count:,}/{total_analyzed:,} ({coverage:.1f}%)")
        
        # Clustering analysis
        if cluster_analysis.get('distance_stats'):
            dist_stats = cluster_analysis['distance_stats']
            report_lines.extend([
                "",
                "## Vector Clustering Analysis",
                f"### Distance Statistics ({cluster_analysis.get('sample_size', 0)} vectors)",
                f"- **Mean Cosine Distance**: {dist_stats.get('mean_distance', 0):.3f}",
                f"- **Std Cosine Distance**: {dist_stats.get('std_distance', 0):.3f}",
                f"- **Min Distance**: {dist_stats.get('min_distance', 0):.3f}",
                f"- **Max Distance**: {dist_stats.get('max_distance', 0):.3f}",
            ])
            
            # Similar products
            similar_products = cluster_analysis.get('similar_products', [])
            if similar_products:
                report_lines.extend([
                    "",
                    "### Most Similar Product Pairs",
                ])
                for i, pair in enumerate(similar_products[:5]):
                    similarity_pct = pair['similarity'] * 100
                    report_lines.append(f"{i+1}. **{similarity_pct:.1f}% similar**")
                    report_lines.append(f"   - {pair['product1']}")
                    report_lines.append(f"   - {pair['product2']}")
                    report_lines.append("")
        
        # Quality assessment
        report_lines.extend([
            "## Quality Assessment",
            "",
            "### ✅ Strengths",
        ])
        
        if collection_info.get('total_vectors', 0) > 1000000:
            report_lines.append("- **Scale**: Large vector database with 1M+ vectors")
        
        if vector_stats.get('norm_stats', {}).get('std_norm', 1) < 0.5:
            report_lines.append("- **Consistency**: Vectors have consistent norms")
        
        metadata_coverage = field_freq.get('title', 0) / total_analyzed if total_analyzed > 0 else 0
        if metadata_coverage > 0.9:
            report_lines.append(f"- **Metadata**: High title coverage ({metadata_coverage*100:.1f}%)")
        
        # Issues
        report_lines.extend([
            "",
            "### ⚠️ Issues Identified",
        ])
        
        if metadata_coverage < 0.5:
            report_lines.append(f"- **Metadata**: Low title coverage ({metadata_coverage*100:.1f}%)")
        
        if vector_stats.get('norm_stats', {}).get('std_norm', 0) > 1.0:
            report_lines.append("- **Vector Quality**: High norm variance indicates inconsistent embeddings")
        
        # Recommendations
        report_lines.extend([
            "",
            "## Recommendations",
            "",
            "### Immediate Actions",
            "- **Cross-reference** vector IDs with Neo4j product IDs",
            "- **Validate** metadata completeness for core fields",
            "- **Test** vector search quality with sample queries",
            "",
            "### Phase 2 Integration",
            "- **Correlation Analysis**: Compare extracted attributes with vector similarity",
            "- **Quality Validation**: Ensure similar vectors have similar extracted attributes",
            "- **Search Enhancement**: Use attribute filters with vector search",
            "",
            "---",
            f"**Analysis Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | **Analyzer**: Qdrant Vector Analysis System"
        ])
        
        return "\n".join(report_lines)

def main():
    """Run Qdrant vector analysis"""
    print("🔍 Qdrant Vector Analysis Starting...")
    
    analyzer = QdrantVectorAnalyzer()
    
    # Connect to Qdrant
    client = analyzer.connect_to_qdrant()
    if not client:
        print("❌ Cannot proceed without Qdrant connection")
        return
    
    try:
        # Run all analyses
        collection_info = analyzer.analyze_collection_info(client)
        vector_stats = analyzer.analyze_vector_sample(client, sample_size=1000)
        metadata_analysis = analyzer.analyze_metadata_patterns(client, sample_size=2000)
        cluster_analysis = analyzer.analyze_vector_clustering(client, sample_size=500)
        
        # Generate comprehensive report
        report_content = analyzer.create_analysis_report(
            collection_info, vector_stats, metadata_analysis, cluster_analysis
        )
        
        # Save report
        report_file = os.path.join(analyzer.output_dir, "QDRANT_VECTOR_ANALYSIS.md")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        # Save raw data
        raw_data = {
            'analysis_timestamp': datetime.now().isoformat(),
            'collection_info': collection_info,
            'vector_statistics': vector_stats,
            'metadata_analysis': metadata_analysis,
            'clustering_analysis': cluster_analysis
        }
        
        # Convert numpy arrays to lists for JSON serialization
        if 'mean_vector' in vector_stats:
            vector_stats['mean_vector'] = vector_stats['mean_vector'].tolist()
        if 'std_vector' in vector_stats:  
            vector_stats['std_vector'] = vector_stats['std_vector'].tolist()
        
        data_file = os.path.join(analyzer.output_dir, "qdrant_analysis_data.json")
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)
        
        print("🎉 Qdrant vector analysis complete!")
        print(f"📁 Report: {report_file}")
        print(f"📊 Data: {data_file}")
        
        # Quick summary
        print(f"\n📊 SUMMARY:")
        print(f"✅ Vectors: {collection_info.get('total_vectors', 0):,}")
        print(f"✅ Dimension: {collection_info.get('vector_size', 0)}")
        print(f"✅ Sample analyzed: {vector_stats.get('sample_size', 0):,}")
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()